"""
Smoothed speed/ETA tracker for long-running operations (extraction, etc).

Keeps a sliding window of (timestamp, bytes_processed) samples and exposes
an averaged throughput. Designed to mirror the speed-tracking pattern used
by the download path so the same UI ("123 MB/s - 12s") works during
extraction phases as well.
"""

import time
from typing import List, Tuple


class SpeedTracker:
    """Track speed and ETA from a stream of cumulative byte counts."""

    def __init__(self, max_samples: int = 5, sample_interval: float = 0.5):
        self._max_samples = max_samples
        self._sample_interval = sample_interval
        self._samples: List[Tuple[float, int]] = []
        self._speed: float = 0.0
        self._last_emit: float = 0.0
        self._last_processed: int = 0

    def reset(self):
        """Reset back to zero. Call at the start of a new phase."""
        self._samples.clear()
        self._speed = 0.0
        self._last_emit = 0.0
        self._last_processed = 0

    def update(self, processed: int) -> float:
        """Record a new cumulative processed-bytes value. Returns smoothed speed."""
        now = time.time()
        if not self._samples:
            self._samples.append((now, processed))
            self._last_emit = now
            self._last_processed = processed
            return 0.0

        elapsed = now - self._last_emit
        if elapsed < self._sample_interval:
            return self._speed

        dt = now - self._samples[-1][0]
        if dt > 0:
            instant = (processed - self._samples[-1][1]) / dt
            self._samples.append((now, processed))
            if len(self._samples) > self._max_samples:
                self._samples.pop(0)
            # Smoothed: average of (instant + previous samples)
            if len(self._samples) >= 2:
                first_t, first_b = self._samples[0]
                window_dt = now - first_t
                self._speed = (
                    (processed - first_b) / window_dt if window_dt > 0 else instant
                )
            else:
                self._speed = instant

        self._last_emit = now
        self._last_processed = processed
        return self._speed

    @property
    def speed(self) -> float:
        return self._speed

    @staticmethod
    def eta_seconds(total: int, processed: int, speed: float) -> int:
        """Compute remaining seconds, or 0 if unknown."""
        if speed <= 0 or total <= 0 or processed >= total:
            return 0
        return max(0, int((total - processed) / speed))
