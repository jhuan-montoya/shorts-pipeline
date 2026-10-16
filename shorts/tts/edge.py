"""Edge TTS: gratuito, sem chave de API, com tempos reais por palavra. Requer internet."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional

from .base import Word, mark_pauses


class EdgeProvider:
    name = "edge"
    default_voice = "pt-BR-AntonioNeural"

    def synthesize(self, text: str, dest: Path, voice: Optional[str], rate: Optional[str]) -> List[Word]:
        try:
            import edge_tts
        except ImportError as exc:  # pragma: no cover - depende do ambiente
            raise RuntimeError("provedor 'edge' requer: pip install edge-tts") from exc

        async def run() -> List[Word]:
            comm = edge_tts.Communicate(text, voice or self.default_voice, rate=rate or "+0%", boundary="WordBoundary")
            words: List[Word] = []
            with open(dest, "wb") as fh:
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        fh.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        start = chunk["offset"] / 1e7
                        words.append(Word(chunk["text"], start, start + chunk["duration"] / 1e7))
            return words

        words = asyncio.run(run())
        if not words:
            raise RuntimeError("edge-tts não devolveu palavras (voz inválida ou sem conexão?)")
        mark_pauses(text, words)
        return words
