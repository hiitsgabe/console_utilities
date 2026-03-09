# Parallel Chunk Downloads Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Speed up large file downloads by splitting them into N parallel HTTP range requests, downloading chunks concurrently, then stitching them into the final file.

**Architecture:** Add a `_download_file_parallel()` method to the desktop `DownloadManager` that probes for `Accept-Ranges: bytes` support, splits the file into N chunks downloaded by a `ThreadPoolExecutor`, writes each chunk to a temp file, then concatenates. Falls back to the existing single-stream `_download_file()` if the server doesn't support ranges or the file is small. Android `AndroidDownloadManager` is untouched.

**Tech Stack:** Python stdlib (`threading`, `concurrent.futures.ThreadPoolExecutor`, `os`, `tempfile`), `requests`

---

### Task 1: Add parallel download worker count setting

**Files:**
- Modify: `src/services/download_manager.py` (the `_download_file` method, lines 267-410)

**Step 1: Add `_probe_range_support` method**

Add this method to `DownloadManager` right before `_download_file`:

```python
def _probe_range_support(self, url: str, headers: dict, cookies: dict) -> Optional[int]:
    """
    Send a HEAD request to check if server supports range requests.

    Returns:
        Content-Length if ranges supported, None otherwise.
    """
    try:
        resp = requests.head(
            url,
            headers=headers,
            cookies=cookies,
            timeout=(10, 15),
            allow_redirects=True,
        )
        accept_ranges = resp.headers.get("accept-ranges", "").lower()
        content_length = int(resp.headers.get("content-length", 0))
        if accept_ranges == "bytes" and content_length > 0:
            return content_length
    except Exception:
        pass
    return None
```

**Step 2: Add `_download_chunk` worker method**

Add this method to `DownloadManager`:

```python
def _download_chunk(
    self,
    url: str,
    headers: dict,
    cookies: dict,
    start: int,
    end: int,
    chunk_path: str,
    chunk_index: int,
    progress_array: list,
) -> bool:
    """
    Download a byte range to a temp file. Updates progress_array[chunk_index]
    with bytes downloaded so far for this chunk.

    Returns True on success.
    """
    range_headers = dict(headers)
    range_headers["Range"] = f"bytes={start}-{end}"

    try:
        resp = requests.get(
            url,
            headers=range_headers,
            cookies=cookies,
            stream=True,
            timeout=(15, 60),
            allow_redirects=True,
        )
        # Accept both 206 Partial Content and 200 OK
        if resp.status_code not in (200, 206):
            return False

        with open(chunk_path, "wb") as f:
            for data in resp.iter_content(chunk_size=262144):
                if self._cancel_current:
                    return False
                if data:
                    f.write(data)
                    progress_array[chunk_index] += len(data)
        return True
    except Exception:
        return False
```

**Step 3: Add `_download_file_parallel` method**

Add this method to `DownloadManager`:

```python
def _download_file_parallel(
    self,
    item: DownloadQueueItem,
    url: str,
    filename: str,
    total_size: int,
    headers: dict,
    cookies: dict,
    num_workers: int = 4,
) -> Optional[str]:
    """
    Download a file using parallel range requests.

    Returns file path on success, None on cancel/failure.
    """
    import concurrent.futures

    file_path = os.path.join(self.work_dir, filename)
    os.makedirs(self.work_dir, exist_ok=True)

    item.total_size = total_size
    item.downloaded = 0

    # Calculate chunk boundaries
    chunk_size = total_size // num_workers
    ranges = []
    for i in range(num_workers):
        start = i * chunk_size
        end = total_size - 1 if i == num_workers - 1 else (i + 1) * chunk_size - 1
        ranges.append((start, end))

    # Progress tracking per chunk
    progress_array = [0] * num_workers
    chunk_paths = [
        os.path.join(self.work_dir, f".{filename}.part{i}")
        for i in range(num_workers)
    ]

    start_time = time.time()
    last_update = start_time
    last_downloaded = 0
    speed_samples = []

    # Launch parallel downloads
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {
            executor.submit(
                self._download_chunk,
                url,
                headers,
                cookies,
                ranges[i][0],
                ranges[i][1],
                chunk_paths[i],
                i,
                progress_array,
            ): i
            for i in range(num_workers)
        }

        # Poll progress while workers run
        while not all(f.done() for f in futures):
            if self._cancel_current:
                executor.shutdown(wait=False, cancel_futures=True)
                self._cleanup_chunk_files(chunk_paths)
                return None

            total_downloaded = sum(progress_array)
            item.downloaded = total_downloaded

            current_time = time.time()
            elapsed = current_time - last_update
            if elapsed >= 0.5:
                instant_speed = (total_downloaded - last_downloaded) / elapsed
                speed_samples.append(instant_speed)
                if len(speed_samples) > 4:
                    speed_samples.pop(0)
                item.speed = sum(speed_samples) / len(speed_samples)
                last_downloaded = total_downloaded
                last_update = current_time

                if item.total_size > 0:
                    item.progress = total_downloaded / item.total_size

            time.sleep(0.1)

        # Check all chunks succeeded
        for future in futures:
            if not future.result():
                self._cleanup_chunk_files(chunk_paths)
                item.status = "failed"
                item.error = "Parallel chunk download failed"
                return None

    # Final progress update
    item.downloaded = total_size
    item.progress = 1.0

    # Stitch chunks into final file
    try:
        with open(file_path, "wb") as out:
            for cp in chunk_paths:
                with open(cp, "rb") as inp:
                    while True:
                        data = inp.read(1048576)  # 1MB read buffer
                        if not data:
                            break
                        out.write(data)
        self._cleanup_chunk_files(chunk_paths)
    except Exception as e:
        self._cleanup_chunk_files(chunk_paths)
        item.status = "failed"
        item.error = f"Stitch failed: {str(e)[:40]}"
        return None

    return file_path
```

**Step 4: Add cleanup helper**

```python
def _cleanup_chunk_files(self, chunk_paths: list):
    """Remove temporary chunk files."""
    for cp in chunk_paths:
        try:
            if os.path.exists(cp):
                os.remove(cp)
        except OSError:
            pass
```

**Step 5: Run lint**

Run: `cd /Users/gabe/Workspace/Games/console_utilities && make format && make lint`
Expected: PASS

**Step 6: Commit**

```bash
git add src/services/download_manager.py
git commit -m "feat: add parallel chunk download methods to DownloadManager"
```

---

### Task 2: Wire parallel downloads into `_download_file`

**Files:**
- Modify: `src/services/download_manager.py` (the `_download_file` method)

**Step 1: Extract auth/header setup into a helper**

Refactor `_download_file` to extract the auth header + cookie setup (lines 276-303) into a reusable method so both single-stream and parallel paths can share it:

```python
def _prepare_request(self, system_data: dict) -> tuple:
    """
    Build auth headers and cookies from system_data.

    Returns:
        (headers, cookies, is_ia_auth) tuple
    """
    headers = {}
    cookies = {}
    is_ia_auth = False

    if "auth" in system_data:
        auth_config = system_data["auth"]
        if auth_config.get("type") == "ia_s3":
            access_key = auth_config.get("access_key") or None
            secret_key = auth_config.get("secret_key") or None
            if access_key and secret_key:
                headers["authorization"] = f"LOW {access_key}:{secret_key}"
                is_ia_auth = True
        elif auth_config.get("cookies", False) and "token" in auth_config:
            cookie_name = auth_config.get("cookie_name", "auth_token")
            cookies[cookie_name] = auth_config["token"]
        elif "token" in auth_config:
            headers["Authorization"] = f"Bearer {auth_config['token']}"

    return headers, cookies, is_ia_auth
```

**Step 2: Add parallel download gate in `_download_file`**

After the response is obtained and `content-length` is known (line 355), but BEFORE starting `iter_content`, add the parallel path check. Insert right after `response = ...` and `response.raise_for_status()` resolves, before the streaming loop:

Replace the section from line 355 (`item.total_size = ...`) through line 392 (`return file_path`) with:

```python
            content_length = int(response.headers.get("content-length", 0))
            accept_ranges = response.headers.get("accept-ranges", "").lower()
            response.close()

            # Use parallel download if server supports ranges and file is >5MB
            min_parallel_size = 5 * 1024 * 1024  # 5MB
            if (
                accept_ranges == "bytes"
                and content_length > min_parallel_size
            ):
                return self._download_file_parallel(
                    item, url, filename, content_length,
                    request_headers, cookies, num_workers=4,
                )

            # Fall back to single-stream download
            # Re-open the connection since we closed it for the probe
            if "archive.org" in url and is_ia_auth:
                response = requests.get(
                    url,
                    stream=True,
                    timeout=(15, 30),
                    headers=request_headers,
                    cookies=cookies,
                    allow_redirects=False,
                )
                # Follow redirects manually for IA auth
                for _ in range(5):
                    if response.status_code in (301, 302, 303, 307, 308):
                        current_url = response.headers.get("Location", url)
                        response = requests.get(
                            current_url,
                            stream=True,
                            timeout=(15, 30),
                            headers=request_headers,
                            cookies=cookies,
                            allow_redirects=False,
                        )
                    else:
                        break
                response.raise_for_status()
            else:
                response = requests.get(
                    url,
                    stream=True,
                    timeout=(15, 30),
                    headers=request_headers,
                    cookies=cookies,
                    allow_redirects=True,
                )
                response.raise_for_status()

            # Original single-stream download path
            item.total_size = int(response.headers.get("content-length", 0))
            item.downloaded = 0
            start_time = time.time()
            last_update = start_time
            last_downloaded = 0
            speed_samples = []

            file_path = os.path.join(self.work_dir, filename)
            os.makedirs(self.work_dir, exist_ok=True)

            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=262144):
                    if self._cancel_current:
                        f.close()
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        return None

                    if chunk:
                        f.write(chunk)
                        item.downloaded += len(chunk)

                        current_time = time.time()
                        elapsed = current_time - last_update
                        if elapsed >= 0.5:
                            instant_speed = (item.downloaded - last_downloaded) / elapsed
                            speed_samples.append(instant_speed)
                            if len(speed_samples) > 4:
                                speed_samples.pop(0)
                            item.speed = sum(speed_samples) / len(speed_samples)
                            last_downloaded = item.downloaded
                            last_update = current_time

                            if item.total_size > 0:
                                item.progress = item.downloaded / item.total_size

            return file_path
```

**Important:** The key insight is that we can check `accept-ranges` from the FIRST response we already get (the streaming one). We close it, branch to parallel if supported, or re-open for single-stream fallback. This avoids an extra HEAD request.

**Step 3: Run lint**

Run: `cd /Users/gabe/Workspace/Games/console_utilities && make format && make lint`
Expected: PASS

**Step 4: Commit**

```bash
git add src/services/download_manager.py
git commit -m "feat: wire parallel chunk downloads into _download_file with auto-fallback"
```

---

### Task 3: Handle IA auth with parallel downloads

**Files:**
- Modify: `src/services/download_manager.py`

**Step 1: Pass auth headers through to parallel chunks**

The IA auth path manually follows redirects. The final URL after redirect resolution is what the parallel chunks should use. Update the IA auth section so it resolves the final URL first, then passes that to `_download_file_parallel`:

In the IA auth redirect loop (around line 306-328), after resolving to the final `response`, extract the final URL from the redirect chain and use that for range requests. The `response.url` attribute gives the final URL after redirects.

For the non-IA path, `response.url` is already the final URL.

Both paths should pass `response.url` (the resolved URL) to `_download_file_parallel`, not the original `url`, so range requests go directly to the CDN/edge node without re-redirecting.

**Step 2: Run lint and manual test**

Run: `cd /Users/gabe/Workspace/Games/console_utilities && make format && make lint`
Expected: PASS

**Step 3: Commit**

```bash
git add src/services/download_manager.py
git commit -m "feat: resolve final URL before parallel chunk dispatch for IA auth"
```

---

### Task 4: Manual integration test

**Step 1: Test with a small archive.org file**

Run the app with `make debug`, navigate to a small system (e.g., Game Boy), pick a small ROM, and download it. Observe:
- Console should log that parallel download is being used (add a `log_error` debug line temporarily if needed)
- Speed should be displayed in the UI
- Progress bar should advance smoothly
- File should appear in the target roms folder

**Step 2: Test with a file that doesn't support ranges**

If ultranx or any other source doesn't support ranges, verify it falls back to single-stream download gracefully.

**Step 3: Test cancellation**

Start a download, cancel it mid-way. Verify:
- Chunk temp files (`.filename.part0`, `.filename.part1`, etc.) are cleaned up
- Item shows as cancelled in the queue

**Step 4: Remove any debug logging and commit**

```bash
git add src/services/download_manager.py
git commit -m "test: verify parallel chunk downloads work end-to-end"
```
