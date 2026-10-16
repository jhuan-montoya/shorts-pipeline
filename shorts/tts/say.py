"""macOS `say`: offline e gratuito. Sem tempo por palavra: usa estimativa proporcional."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from .base import Word, estimate_word_timings, parse_rate_percent
from ..media import probe_duration

BASE_WPM = 175


class SayProvider:
    name = "say"
    default_voice = "Luciana"

    def synthesize(self, text: str, dest: Path, voice: Optional[str], rate: Optional[str]) -> List[Word]:
        if not shutil.which("say"):
            raise RuntimeError("provedor 'say' só existe no macOS; use 'edge' ou 'mock'")
        wpm = int(BASE_WPM * (1 + parse_rate_percent(rate)))
        raw = dest.with_suffix(".aiff")
        subprocess.run(["say", "-v", voice or self.default_voice, "-r", str(wpm), "-o", str(raw), text], check=True)
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw), str(dest)], check=True)
        raw.unlink()
        return estimate_word_timings(text, probe_duration(dest))
