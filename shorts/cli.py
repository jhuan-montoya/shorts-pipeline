"""CLI: python -m shorts {render,plan,validate} roteiro.yaml"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import List, Optional

import yaml

from .captions import to_srt
from .render import DEFAULT_MAX_MB, render
from .script import Script, ScriptError, load_script
from .theme import Theme, ThemeError, theme_from_dict
from .timeline import SceneAudio, build_timeline
from .tts import DEFAULT_PROVIDER
from .tts.base import estimate_word_timings
from .tts.mock import estimate_duration


def resolve_theme(script: Script, theme_path: Optional[str]) -> Theme:
    if theme_path:
        path = Path(theme_path).resolve()
        return theme_from_dict(yaml.safe_load(path.read_text(encoding="utf-8")), path.parent)
    if script.theme_file:
        path = (script.base_dir / script.theme_file).resolve()
        return theme_from_dict(yaml.safe_load(path.read_text(encoding="utf-8")), path.parent)
    return theme_from_dict(script.theme, script.base_dir)


def _plan(script: Script, theme: Theme, rate: Optional[str]) -> None:
    """Timeline estimada (sem TTS nem ffmpeg): útil para revisar o ritmo do roteiro."""
    audios = []
    for sc in script.scenes:
        dur = estimate_duration(sc.text, rate or script.rate)
        audios.append(SceneAudio(sc.text, dur, estimate_word_timings(sc.text, dur)))
    tl = build_timeline(audios, theme.caption)
    for p in tl.scenes:
        print(f"cena {p.index + 1:>2}  {p.start:6.2f}s -> {p.end:6.2f}s  ({p.duration:4.1f}s)  {p.text[:60]}")
    print(f"total estimado: {tl.total:.1f}s | quadros de legenda: {len(tl.frames)}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="shorts", description="Gera shorts verticais com narração e legenda palavra a palavra.")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render", help="renderiza o vídeo")
    r.add_argument("script")
    r.add_argument("--out", help="pasta de saída (padrão: out/<id>)")
    r.add_argument("--tts", help=f"provedor de TTS (padrão: roteiro ou {DEFAULT_PROVIDER}): edge, say, mock ou modulo:Classe")
    r.add_argument("--voice")
    r.add_argument("--rate", help="velocidade da fala, ex.: +10%%")
    r.add_argument("--theme", help="arquivo YAML de identidade visual (sobrepõe o do roteiro)")
    r.add_argument("--max-mb", type=float, default=DEFAULT_MAX_MB, help="limite aproximado de tamanho do MP4")
    r.add_argument("--keep-tmp", action="store_true", help="mantém os arquivos intermediários")

    pl = sub.add_parser("plan", help="mostra a timeline estimada (offline, sem renderizar)")
    pl.add_argument("script")
    pl.add_argument("--theme")
    pl.add_argument("--rate")

    v = sub.add_parser("validate", help="valida o roteiro e o tema")
    v.add_argument("script")
    v.add_argument("--theme")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        script = load_script(Path(args.script))
        theme = resolve_theme(script, args.theme)
        if args.cmd == "validate":
            print(f"ok: '{script.id}' com {len(script.scenes)} cenas")
        elif args.cmd == "plan":
            _plan(script, theme, args.rate)
        else:
            out = Path(args.out) if args.out else Path("out") / script.id
            res = render(script, theme, out, args.tts or script.tts or DEFAULT_PROVIDER,
                         args.voice, args.rate, args.max_mb)
            if not args.keep_tmp:
                shutil.rmtree(out / "tmp", ignore_errors=True)
            print(f"{res.video} | {res.duration:.1f}s | {res.size_mb:.2f} MB | legendas: {res.srt}")
    except (ScriptError, ThemeError, ValueError, RuntimeError, FileNotFoundError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    return 0
