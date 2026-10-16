"""Identidade visual configurável: cores, fonte, legenda e marca."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

DEFAULT_GRADIENTS: Tuple[Tuple[str, str], ...] = (
    ("#0E1A2B", "#1E3A5F"),
    ("#0E1A2B", "#2B1E4F"),
    ("#0E1A2B", "#123B3A"),
    ("#0E1A2B", "#3A1E2B"),
)


class ThemeError(ValueError):
    pass


@dataclass(frozen=True)
class CaptionStyle:
    mode: str = "word"  # "word": destaca a palavra falada | "group": bloco de palavras fixo
    size: int = 96
    y: float = 0.80  # posição vertical (fração da altura)
    stroke: int = 10
    max_words: int = 3
    max_chars: int = 16
    max_hold: float = 0.35  # quanto a legenda permanece na tela após a última palavra
    uppercase: bool = True


@dataclass(frozen=True)
class Theme:
    background: str = "#0E1A2B"
    accent: str = "#FFE14D"
    alert: str = "#E5484D"
    ok: str = "#30A46C"
    screen: str = "#F4F6FA"
    ink: str = "#0E1A2B"
    text: str = "#FFFFFF"
    gradients: Tuple[Tuple[str, str], ...] = DEFAULT_GRADIENTS
    handle: str = "@seucanal"
    avatar: Optional[str] = None
    font: Optional[str] = None
    font_bold: Optional[str] = None
    caption: CaptionStyle = field(default_factory=CaptionStyle)

    def gradient(self, idx: int) -> Tuple[str, str]:
        return self.gradients[idx % len(self.gradients)]


def _check_hex(name: str, value: Any) -> str:
    if not isinstance(value, str) or not HEX.match(value):
        raise ThemeError(f"theme.{name}: cor inválida {value!r} (use #RRGGBB)")
    return value


def theme_from_dict(data: Optional[Dict[str, Any]], base_dir: Path = Path(".")) -> Theme:
    """Constrói um Theme a partir de um dict (campos ausentes usam o padrão)."""
    data = dict(data or {})
    known = {f.name for f in fields(Theme)}
    unknown = set(data) - known
    if unknown:
        raise ThemeError(f"theme: campos desconhecidos {sorted(unknown)}")

    kwargs: Dict[str, Any] = {}
    for key in ("background", "accent", "alert", "ok", "screen", "ink", "text"):
        if key in data:
            kwargs[key] = _check_hex(key, data[key])
    for key in ("handle",):
        if key in data:
            kwargs[key] = str(data[key])
    for key in ("avatar", "font", "font_bold"):
        if data.get(key):
            kwargs[key] = str((base_dir / str(data[key])).resolve())
    if "gradients" in data:
        grads = data["gradients"]
        if not grads or any(not isinstance(g, (list, tuple)) or len(g) != 2 for g in grads):
            raise ThemeError("theme.gradients: lista de pares [cor_topo, cor_base]")
        kwargs["gradients"] = tuple((_check_hex("gradients", a), _check_hex("gradients", b)) for a, b in grads)
    if "caption" in data:
        cap = dict(data["caption"] or {})
        cap_known = {f.name for f in fields(CaptionStyle)}
        if set(cap) - cap_known:
            raise ThemeError(f"theme.caption: campos desconhecidos {sorted(set(cap) - cap_known)}")
        style = CaptionStyle(**cap)
        if style.mode not in ("word", "group"):
            raise ThemeError("theme.caption.mode deve ser 'word' ou 'group'")
        if style.max_words < 1 or style.max_chars < 1:
            raise ThemeError("theme.caption: max_words e max_chars devem ser >= 1")
        kwargs["caption"] = style
    return Theme(**kwargs)
