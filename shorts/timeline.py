"""Montagem da timeline: cenas em sequência, palavras em tempo absoluto e quadros de legenda.

Módulo puro (sem I/O nem ffmpeg): recebe a duração e os tempos das palavras de cada cena
e devolve tudo o que o renderizador precisa. É o que os testes exercitam.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .captions import CaptionFrame, build_frames
from .theme import CaptionStyle
from .tts.base import Word

SCENE_TAIL = 0.15  # respiro (s) ao fim de cada cena


@dataclass(frozen=True)
class SceneAudio:
    text: str
    audio_duration: float
    words: List[Word]


@dataclass(frozen=True)
class ScenePlan:
    index: int
    text: str
    start: float
    duration: float

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass(frozen=True)
class Timeline:
    scenes: List[ScenePlan]
    words: List[Word]  # tempo absoluto
    frames: List[CaptionFrame]
    total: float


def build_timeline(audios: List[SceneAudio], style: CaptionStyle, tail: float = SCENE_TAIL) -> Timeline:
    scenes: List[ScenePlan] = []
    words: List[Word] = []
    cursor = 0.0
    for i, a in enumerate(audios):
        duration = a.audio_duration + tail
        scenes.append(ScenePlan(i, a.text, cursor, duration))
        for w in a.words:
            start = cursor + min(w.start, a.audio_duration)
            end = cursor + min(max(w.end, w.start), a.audio_duration)
            words.append(Word(w.text, start, end, w.pause))
        cursor += duration
    # a legenda de uma cena nunca invade a seguinte: fecha em `pause` no fim da cena
    if words:
        for sc in scenes:
            inside = [w for w in words if sc.start <= w.start < sc.end]
            if inside:
                inside[-1].pause = True
    return Timeline(scenes, words, build_frames(words, cursor, style), cursor)
