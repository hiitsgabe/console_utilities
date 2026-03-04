# PyGameNX — Nintendo Switch Homebrew Port Plan

## Overview

This document outlines the plan to run Console Utilities as a native Nintendo Switch homebrew application (.nro). Rather than rewriting the app in C, we port the Python + PyGame runtime itself to Switch, building on proven open-source infrastructure.

## Background

### The Challenge
Console Utilities is a PyGame-based Python application. The Nintendo Switch homebrew ecosystem uses C/C++ with devkitPro's toolchain and libnx. There's no official Python or PyGame runtime for Switch.

### The Solution: pygame_sdl2
The [Ren'Py](https://www.renpy.org/) visual novel engine maintains [pygame_sdl2](https://github.com/renpy/pygame_sdl2) — a reimplementation of the PyGame API built directly on SDL2. Critically, it has **already been built for Switch** via [switch-librenpy-switch-modules](https://github.com/uyjulian/switch-librenpy-switch-modules), proving the full chain works:

```
CPython interpreter + pygame_sdl2 + SDL2 portlibs + libnx → working .nro
```

This means we don't need to rewrite the app — we port the runtime and adapt the app to run on it.

### Why pygame_sdl2 (not mainline PyGame)
- Lighter codebase, no legacy SDL1 baggage
- Already proven on Switch hardware (Ren'Py games run on Switch)
- Covers all APIs Console Utilities uses: display, surface, font, image, draw, transform, event, joystick, time
- Zlib + LGPL2 licensed

## Architecture

### How it works

The NRO binary bundles everything into a single executable:

```
┌──────────────────────────────────────────────┐
│                 .nro binary                  │
│                                              │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐ │
│  │  libnx   │  │ CPython   │  │ pygame    │ │
│  │ (Switch  │  │ 3.11      │  │ _sdl2     │ │
│  │  OS API) │  │ (interp)  │  │ (modules) │ │
│  └──────────┘  └───────────┘  └───────────┘ │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐ │
│  │  SDL2    │  │ zstandard │  │ pycrypto  │ │
│  │ +image   │  │ (C ext)   │  │ dome AES  │ │
│  │ +ttf+gfx │  │           │  │ (C ext)   │ │
│  └──────────┘  └───────────┘  └───────────┘ │
└──────────────────────────────────────────────┘
                      │
                      ▼
        SD card (sdmc:/switch/console_utilities/)
        ├── console_utilities.nro
        ├── python311.zip        ← Python stdlib
        ├── lib/                 ← App source + pure Python deps
        │   ├── app.py
        │   ├── src/
        │   ├── requests/
        │   └── urllib3/
        └── assets/              ← Fonts, configs, download.json
```

### Boot sequence (main.c)

```c
// 1. Initialize Switch services
__libnx_initheap()      // 384 MiB heap
socketInitializeDefault() // BSD sockets for networking
romfsInit()              // Read-only filesystem

// 2. Register all Python C extension modules
struct _inittab inittab[] = {
    {"pygame_sdl2.display", PyInit_display},
    {"pygame_sdl2.surface", PyInit_surface},
    {"pygame_sdl2.event",   PyInit_event},
    // ... all pygame_sdl2 + zstandard + pycryptodome modules
    {NULL, NULL}
};
PyImport_ExtendInittab(inittab);

// 3. Initialize Python
Py_Initialize();
PySys_SetPath("sdmc:/switch/console_utilities/python311.zip:"
              "sdmc:/switch/console_utilities/lib");

// 4. Run the app
PyRun_SimpleFile("sdmc:/switch/console_utilities/lib/app.py");
```

## API Compatibility

### What works out of the box

| pygame API | Status in pygame_sdl2 |
|------------|----------------------|
| `display.set_mode`, `display.flip`, `display.Info` | Supported |
| `Surface` (fill, blit, get_size, get_rect, convert_alpha, subsurface) | Supported |
| `Rect` (collidepoint, inflate, union, center, edges) | Supported |
| `font.Font` (load, render, size) | Supported (SDL2_ttf) |
| `image.load/save` (PNG, JPG, BytesIO) | Supported (SDL2_image) |
| `transform.smoothscale`, `transform.scale` | Supported |
| `draw.circle`, `draw.line`, `draw.polygon`, `draw.ellipse` | Supported |
| `event` (KEYDOWN, JOYBUTTONDOWN, JOYHATMOTION, MOUSE*, FINGER*) | Supported |
| `joystick` (init, get_count, Joystick, get_hat, get_button) | Supported |
| `time.Clock`, `time.get_ticks` | Supported |
| `key.get_pressed` | Supported |
| `SRCALPHA`, alpha blending | Supported |

### Critical gap: `border_radius`

`pygame.draw.rect(surface, color, rect, border_radius=N)` is used throughout the app for rounded UI elements but is **not** in pygame_sdl2.

**Fix**: Patch `draw.pyx` to call SDL2_gfx's `roundedBoxRGBA` / `roundedRectangleRGBA` when `border_radius > 0`. This is ~30 lines of Cython code.

### Not needed (app doesn't use)

- `pygame.mixer` / sound — no audio in the app
- `pygame.SCALED` — Android-only; Switch uses `FULLSCREEN` at native 1280x720

## Implementation Phases

### Phase 0: Build Infrastructure
**Difficulty: Medium | ~1-2 weeks**

Set up the Docker-based cross-compilation environment.

**What gets built:**
- `switch/Dockerfile` — based on `devkitpro/devkita64:latest` with SDL2 portlibs
- `switch/CMakeLists.txt` — cross-compilation config
- `switch/cmake/SwitchToolchain.cmake` — aarch64-none-elf toolchain
- `switch/source/main.c` — minimal NRO: init libnx → SDL2 window → draw rect → exit on button

**devkitPro packages needed:**
```
switch-sdl2  switch-sdl2_image  switch-sdl2_ttf  switch-sdl2_gfx
switch-freetype  switch-libpng  switch-libjpeg-turbo  switch-zlib
```

**Test**: NRO boots on Switch, shows a colored rectangle, exits on B press.

### Phase 1: Cross-compile CPython 3.11
**Difficulty: Hard | ~3-4 weeks**

Cross-compile a static `libpython3.11.a` for `aarch64-none-elf`.

**Key challenges:**
- CPython's autoconf probes test for POSIX features (fork, signals, ptys) that don't exist on Switch. Solved with a `config.site` file that pre-caches the correct answers.
- Many POSIX functions (fork, kill, pipe, exec, utime) must be patched out of the source.
- The `_socket` module needs patching for libnx's BSD socket limitations.

**Static modules to include:**
`_io`, `_thread`, `time`, `math`, `struct`, `_json`, `_socket`, `zlib`, `_hashlib`, `select`, `array`, `binascii`, `_collections`, `itertools`, `functools`, `_datetime`

**Stdlib delivery:** Stripped and bundled as `python311.zip` (no tests, no __pycache__, no unused modules).

**Fallback chain:** If 3.11 fails → try 3.10 → try 3.8 (proven by [switch-libpython](https://github.com/nx-python/switch-libpython)).

**Test**: NRO runs `print("Hello Python 3.11")`, output visible in SD card log file.

### Phase 2: Build pygame_sdl2 + Integration
**Difficulty: Hard | ~3-4 weeks**

Cross-compile pygame_sdl2 as a static library and integrate with CPython.

**Build process:**
1. Download pygame_sdl2 source from [renpy/pygame_sdl2](https://github.com/renpy/pygame_sdl2)
2. Run Cython **on the host** to generate `.c` files from `.pyx` (Cython can't cross-compile)
3. Apply `border_radius` patch to `draw.pyx` before Cython generation
4. Cross-compile all generated `.c` files with `aarch64-none-elf-gcc`
5. Link into `libpygame_sdl2.a`

**Modules to build** (only what the app needs):
`color`, `display`, `draw`, `error`, `event`, `font`, `image`, `joystick`, `key`, `locals`, `mouse`, `rect`, `rwobject`, `surface`, `time`, `transform`, `gfxdraw`

**Integration** (following [renpy-switch](https://github.com/uyjulian/renpy-switch) pattern):
- Register all `PyMODINIT_FUNC` entries in `_inittab` before `Py_Initialize()`
- Set `sys.path` to include app directory and stdlib zip
- Execute app entry point

**Test**: Window opens at 720p, draws shapes, handles Joy-Con D-pad and buttons, renders text with fonts.

### Phase 3: Networking
**Difficulty: Medium | ~2-3 weeks** *(parallel with Phase 4)*

Enable HTTP downloads — the app's core functionality.

- libnx provides BSD sockets via `socketInitializeDefault()` (already initialized in main.c)
- CPython's `_socket` module from Phase 1 provides the Python socket layer
- Bundle `requests` and its dependencies as pure Python: `urllib3`, `certifi`, `charset_normalizer`, `idna`
- **No HTTPS initially** — most ROM hosting sites support HTTP. SSL (via mbedTLS cross-compilation) can be added later.

**Test**: Fetch an HTTP URL on Switch over WiFi, display the response text.

### Phase 4: C Extension Dependencies
**Difficulty: Medium-Hard | ~2-3 weeks** *(parallel with Phase 3)*

Cross-compile the C extensions needed for NSZ decompression.

**zstandard:**
- The python-zstandard package bundles libzstd source code
- Extract and cross-compile the C sources
- Register `_zstd` module in `_inittab`

**pycryptodome (AES only):**
- Extract just the AES cipher C source (`_raw_aes.c`)
- Stub `_cpuid` detection for Switch (no x86 CPUID on ARM)
- Register in `_inittab`

**Pillow:** Skip entirely — only used by `logo_analyzer.py` and `tim_generator.py` (non-essential features). Guard with conditional imports.

**Test**: Decompress a zstd-compressed file, perform AES decryption on Switch.

### Phase 5: App Port
**Difficulty: Medium | ~2-3 weeks**

Adapt Console Utilities for the Switch environment.

**Changes to `src/constants.py`:**
```python
BUILD_TARGET = "switch"  # Injected at build time
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720

# Switch SD card paths
if BUILD_TARGET == "switch":
    WORK_DIR = "sdmc:/switch/console_utilities/"
    ROMS_DIR = "sdmc:/roms/"
```

**Display:** 1280x720 fullscreen (Switch native resolution). No `SCALED` flag.

**Input:** Joy-Con controllers appear as standard HID gamepads via SDL2 — the existing `controller.py` joystick mapping should work with minor button ID adjustments.

**Touch:** Switch has a capacitive touchscreen. SDL2 FINGER* events (already handled by `touch.py`) work natively.

**Conditional skips:**
- Pillow-dependent features (`logo_analyzer`, `tim_generator`)
- `web_companion` / `stream_server`
- Android-specific code (`src/droid/`)

**Font scaling:** Increase from 28pt (800x600) to ~34pt (1280x720) for readability.

**Build target:** `make build-switch` in root Makefile assembles the full SD card directory structure.

**Test**: Full app boots, browse systems, navigate menus, download a ROM file.

## Key References

| Resource | What it provides |
|----------|-----------------|
| [switch-librenpy-switch-modules](https://github.com/uyjulian/switch-librenpy-switch-modules) | Proven pygame_sdl2 Switch build (our primary template) |
| [renpy-switch](https://github.com/uyjulian/renpy-switch) | NRO assembly pattern (main.c, _inittab, heap, sockets) |
| [renpy/pygame_sdl2](https://github.com/renpy/pygame_sdl2) | pygame_sdl2 source code |
| [nx-python/switch-libpython](https://github.com/nx-python/switch-libpython) | CPython 3.8 cross-compile PKGBUILD for Switch |
| [nx-python/PyNX](https://github.com/nx-python/PyNX) | CPython 3.5 Switch port (older reference) |
| [devkitPro SDL2](https://github.com/devkitPro/SDL/tree/switch-sdl2) | SDL2 port for Switch |

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| CPython 3.11 cross-compile fails | High | Medium | Fall back to 3.10, then 3.8 (proven) |
| pygame_sdl2 Cython version mismatch | High | Low | Pin to same Cython version Ren'Py uses |
| SDL2 rendering bugs on Switch | Medium | Low | SDL2 on Switch is mature, used by many homebrew apps |
| No HTTPS support | Medium | N/A | Ship HTTP-only v1; add mbedTLS cross-compilation for v2 |
| libnx socket quirks / buffer limits | Medium | Medium | Test networking early; implement retry logic |
| border_radius visual differences | Low | Medium | SDL2_gfx rounded rects are visually close enough |
| Memory exhaustion | Low | Low | 384 MiB heap is generous; typical usage ~50-100 MiB |

## Timeline

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Phase 0: Build infrastructure | 1-2 weeks | 1-2 weeks |
| Phase 1: CPython cross-compile | 3-4 weeks | 4-6 weeks |
| Phase 2: pygame_sdl2 integration | 3-4 weeks | 7-10 weeks |
| Phase 3+4: Network + C extensions (parallel) | 2-3 weeks | 9-13 weeks |
| Phase 5: App port | 2-3 weeks | 12-16 weeks |

## Requirements

**Development machine:**
- Docker (for reproducible cross-compilation builds)
- macOS or Linux host

**Testing hardware:**
- Nintendo Switch with Atmosphere CFW + Hekate bootloader
- SD card with homebrew menu (hbmenu)
- WiFi connectivity for networking tests

## What Claude Code generates vs what you test

**AI writes:** Dockerfile, CMake configs, main.c, CPython patches, config.site, pygame_sdl2 border_radius patch, build scripts, constants.py Switch paths, conditional imports, packaging scripts.

**You test on Switch:** Each phase produces an NRO that you copy to the SD card and run. You report what works, what crashes, what looks wrong — and the AI iterates.
