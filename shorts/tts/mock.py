"""Provedor de mentira: áudio mudo com duração estimada pelo texto. Offline, qualquer SO (CI, dry-run)."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional

from .base import Word, estimate_word_timings, parse_rate_percent

CHARS_PER_SECOND = 14.0  # ritmo médio de fala em português


def estimate_duration(text: str, rate: Optional[str] = None) -> float:
    speed = CHARS_PER_SECOND * (1 + parse_rate_percent(rate))
    return max(0.6, len(text) / speed)


class MockProvider:
    name = "mock"
    default_voice = "silent"

    def synthesize(self, text: str, dest: Path, voice: Optional[str], rate: Optional[str]) -> List[Word]:
        dur = estimate_duration(text, rate)
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
             "anullsrc=r=24000:cl=mono", "-t", f"{dur:.3f}", str(dest)],
            check=True,
        )
        return estimate_word_timings(text, dur)
