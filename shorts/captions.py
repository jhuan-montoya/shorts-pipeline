"""Legendas: agrupamento de palavras, quadros de legenda (palavra destacada) e SRT."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .theme import CaptionStyle
from .tts.base import Word

MIN_FRAME = 0.04  # menor duração de um quadro (1 frame a 25 fps)


@dataclass(frozen=True)
class Group:
    words: List[Word]

    @property
    def start(self) -> float:
        return self.words[0].start

    @property
    def end(self) -> float:
        return self.words[-1].end

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


@dataclass(frozen=True)
class CaptionFrame:
    """Um estado visível da legenda: `tokens` na tela, `active` = índice da palavra em destaque."""
    start: float
    end: float
    tokens: List[str]
    active: Optional[int]


def group_words(words: List[Word], max_words: int = 3, max_chars: int = 16) -> List[Group]:
    """Agrupa palavras em blocos curtos, quebrando também em pausas de pontuação."""
    groups: List[List[Word]] = []
    current: List[Word] = []
    for w in words:
        candidate = " ".join(x.text for x in current + [w])
        if current and (len(current) >= max_words or len(candidate) > max_chars):
            groups.append(current)
            current = []
        current.append(w)
        if w.pause:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return [Group(g) for g in groups]


def build_frames(words: List[Word], total: float, style: CaptionStyle) -> List[CaptionFrame]:
    """Transforma palavras com tempo em quadros sem sobreposição, ordenados no tempo.

    Modo "word": um quadro por palavra (grupo inteiro na tela, palavra falada em destaque).
    Modo "group": um quadro por grupo. Em ambos, a legenda é mantida até `max_hold`
    segundos depois da última palavra, ou até o próximo grupo começar.
    """
    groups = group_words(words, style.max_words, style.max_chars)
    frames: List[CaptionFrame] = []
    for gi, g in enumerate(groups):
        next_start = groups[gi + 1].start if gi + 1 < len(groups) else total
        tail = max(min(next_start, g.end + style.max_hold, total), g.end)
        tokens = [w.text for w in g.words]
        if style.mode == "group":
            frames.append(CaptionFrame(g.start, tail, tokens, None))
            continue
        for wi, w in enumerate(g.words):
            end = g.words[wi + 1].start if wi + 1 < len(g.words) else tail
            frames.append(CaptionFrame(w.start, max(end, w.start + MIN_FRAME), tokens, wi))
    # garante ordem e ausência de sobreposição (arredondamentos dos provedores)
    frames.sort(key=lambda f: f.start)
    fixed: List[CaptionFrame] = []
    for i, f in enumerate(frames):
        end = f.end
        if i + 1 < len(frames):
            end = min(end, frames[i + 1].start)
        if end - f.start >= MIN_FRAME / 2:
            fixed.append(CaptionFrame(f.start, end, f.tokens, f.active))
    return fixed


def srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def to_srt(words: List[Word], style: CaptionStyle, total: float) -> str:
    """SRT por grupo de palavras (os players não animam destaque por palavra)."""
    groups = group_words(words, style.max_words, style.max_chars)
    blocks = []
    for i, g in enumerate(groups):
        nxt = groups[i + 1].start if i + 1 < len(groups) else total
        end = max(min(nxt, g.end + style.max_hold, total), g.end)
        blocks.append(f"{i + 1}\n{srt_timestamp(g.start)} --> {srt_timestamp(end)}\n{g.text}\n")
    return "\n".join(blocks)
