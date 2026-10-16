"""Parsing e validação do roteiro (YAML ou JSON)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

VISUAL_TYPES = ("color", "image", "video", "card", "pexels")
CARD_STYLES = ("step", "alert", "number", "signature")


class ScriptError(ValueError):
    pass


@dataclass(frozen=True)
class Visual:
    type: str = "color"
    colors: Optional[List[str]] = None  # color
    file: Optional[str] = None  # image / video
    query: Optional[str] = None  # pexels
    style: str = "step"  # card
    label: str = ""
    lines: List[str] = field(default_factory=list)
    color: Optional[str] = None  # cor de destaque do card "alert"


@dataclass(frozen=True)
class Scene:
    text: str
    visual: Visual = field(default_factory=Visual)


@dataclass(frozen=True)
class Script:
    id: str
    scenes: List[Scene]
    title: Optional[str] = None
    tts: Optional[str] = None
    voice: Optional[str] = None
    rate: Optional[str] = None
    theme: Optional[Dict[str, Any]] = None  # inline
    theme_file: Optional[str] = None
    base_dir: Path = Path(".")


def load_raw(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ScriptError(f"{path}: não foi possível ler o arquivo ({exc})") from exc
    if not isinstance(data, dict):
        raise ScriptError(f"{path}: o roteiro deve ser um objeto/mapa na raiz")
    return data


def parse_visual(raw: Any, where: str) -> Visual:
    if raw is None:
        return Visual()
    if not isinstance(raw, dict):
        raise ScriptError(f"{where}.visual: deve ser um objeto")
    vtype = raw.get("type", "color")
    if vtype not in VISUAL_TYPES:
        raise ScriptError(f"{where}.visual.type: {vtype!r} inválido (use {', '.join(VISUAL_TYPES)})")
    colors = raw.get("colors")
    if colors is not None and (not isinstance(colors, list) or len(colors) != 2):
        raise ScriptError(f"{where}.visual.colors: informe duas cores [topo, base]")
    if vtype in ("image", "video") and not raw.get("file"):
        raise ScriptError(f"{where}.visual.file: obrigatório para type={vtype}")
    if vtype == "pexels" and not raw.get("query"):
        raise ScriptError(f"{where}.visual.query: obrigatório para type=pexels")
    style = raw.get("style", "step")
    if vtype == "card" and style not in CARD_STYLES:
        raise ScriptError(f"{where}.visual.style: {style!r} inválido (use {', '.join(CARD_STYLES)})")
    lines = raw.get("lines", [])
    if not isinstance(lines, list):
        raise ScriptError(f"{where}.visual.lines: deve ser uma lista")
    return Visual(
        type=vtype,
        colors=colors,
        file=raw.get("file"),
        query=raw.get("query"),
        style=style,
        label=str(raw.get("label", "")),
        lines=[str(x) for x in lines],
        color=raw.get("color"),
    )


def parse_script(data: Dict[str, Any], base_dir: Path = Path(".")) -> Script:
    if not data.get("id"):
        raise ScriptError("campo 'id' é obrigatório")
    raw_scenes = data.get("scenes")
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise ScriptError("'scenes' deve ser uma lista com ao menos uma cena")
    scenes: List[Scene] = []
    for i, raw in enumerate(raw_scenes):
        where = f"scenes[{i}]"
        if not isinstance(raw, dict):
            raise ScriptError(f"{where}: deve ser um objeto")
        text = str(raw.get("text", "")).strip()
        if not text:
            raise ScriptError(f"{where}.text: obrigatório e não pode ser vazio")
        scenes.append(Scene(text=" ".join(text.split()), visual=parse_visual(raw.get("visual"), where)))

    theme = data.get("theme")
    theme_file = None
    if isinstance(theme, str):
        theme, theme_file = None, theme
    elif theme is not None and not isinstance(theme, dict):
        raise ScriptError("'theme' deve ser um caminho de arquivo ou um mapa")
    return Script(
        id=str(data["id"]),
        scenes=scenes,
        title=data.get("title"),
        tts=data.get("tts"),
        voice=data.get("voice"),
        rate=data.get("rate"),
        theme=theme,
        theme_file=theme_file,
        base_dir=base_dir,
    )


def load_script(path: Path) -> Script:
    path = Path(path).resolve()
    return parse_script(load_raw(path), base_dir=path.parent)
