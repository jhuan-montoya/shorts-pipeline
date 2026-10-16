"""Registro de provedores de TTS. Adicione o seu com `register` ou use 'pacote.modulo:Classe'."""
from __future__ import annotations

import importlib
from typing import Callable, Dict

from .base import TTSProvider, Word, estimate_word_timings, mark_pauses
from .edge import EdgeProvider
from .mock import MockProvider
from .say import SayProvider

DEFAULT_PROVIDER = "edge"

_REGISTRY: Dict[str, Callable[[], TTSProvider]] = {
    "edge": EdgeProvider,
    "say": SayProvider,
    "mock": MockProvider,
}


def register(name: str, factory: Callable[[], TTSProvider]) -> None:
    _REGISTRY[name] = factory


def get_provider(name: str) -> TTSProvider:
    if name in _REGISTRY:
        return _REGISTRY[name]()
    if ":" in name:  # "meu_pacote.meu_modulo:MinhaClasse"
        module, _, cls = name.partition(":")
        return getattr(importlib.import_module(module), cls)()
    raise ValueError(f"provedor de TTS desconhecido {name!r}; disponíveis: {', '.join(sorted(_REGISTRY))}")


__all__ = ["DEFAULT_PROVIDER", "TTSProvider", "Word", "estimate_word_timings", "get_provider", "mark_pauses", "register"]
