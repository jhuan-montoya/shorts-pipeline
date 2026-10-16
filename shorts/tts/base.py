"""Contrato dos provedores de TTS e utilitários de temporização compartilhados."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Protocol

PAUSE_MARKS = ".?!,;:"
# Pausa extra (em "caracteres equivalentes") depois de cada tipo de pontuação.
PAUSE_WEIGHT = {".": 6, "!": 6, "?": 6, ";": 4, ":": 4, ",": 3}


@dataclass
class Word:
    text: str
    start: float
    end: float
    pause: bool = False  # a frase pausa depois desta palavra (pontuação)


class TTSProvider(Protocol):
    name: str
    default_voice: str

    def synthesize(self, text: str, dest: Path, voice: Optional[str], rate: Optional[str]) -> List[Word]:
        """Grava o áudio em `dest` e devolve os tempos de cada palavra (segundos, relativos à cena)."""
        ...


def mark_pauses(text: str, words: List[Word]) -> None:
    """Alguns TTS devolvem palavras sem pontuação; recupera do texto onde a frase pausa."""
    tokens, i = text.split(), 0
    for w in words:
        target = w.text.lower()
        j = i
        while j < len(tokens) and target not in tokens[j].lower():
            j += 1
        if j < len(tokens):
            w.pause = tokens[j][-1:] in PAUSE_MARKS
            i = j + 1


def parse_rate_percent(rate: Optional[str]) -> float:
    """'+10%' -> 0.10, '-20%' -> -0.20, None -> 0.0."""
    if not rate:
        return 0.0
    m = re.fullmatch(r"\s*([+-]?\d+(?:\.\d+)?)\s*%\s*", rate)
    if not m:
        raise ValueError(f"rate inválido {rate!r}: use algo como '+10%' ou '-5%'")
    return float(m.group(1)) / 100.0


def estimate_word_timings(text: str, duration: float) -> List[Word]:
    """Distribui `duration` entre as palavras proporcionalmente ao tamanho (+ peso de pontuação).

    Usado por provedores que não informam tempo por palavra. É uma aproximação:
    suficiente para legenda palavra a palavra legível, mas sem sincronia fonética exata.
    """
    tokens = text.split()
    if not tokens:
        return []
    weights = []
    for t in tokens:
        core = t.strip(PAUSE_MARKS + "\"'()")
        weights.append(max(len(core), 1) + PAUSE_WEIGHT.get(t[-1:], 0))
    total = float(sum(weights))
    words, cursor = [], 0.0
    for t, wgt in zip(tokens, weights):
        span = duration * wgt / total
        # a pausa de pontuação ocupa o fim do intervalo: a palavra em si termina antes
        extra = PAUSE_WEIGHT.get(t[-1:], 0)
        spoken = span * (1 - extra / wgt)
        words.append(Word(t.strip(PAUSE_MARKS + "\"'()") or t, cursor, cursor + spoken, t[-1:] in PAUSE_MARKS))
        cursor += span
    return words
