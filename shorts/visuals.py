"""Imagens geradas com Pillow: gradientes, cartões e quadros de legenda."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from .script import Visual
from .theme import Theme

W, H = 1080, 1920

_FONT_CANDIDATES = {
    False: [
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/ariblk.ttf",
    ],
    True: [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ],
}


@lru_cache(maxsize=64)
def load_font(configured: Optional[str], bold: bool, size: int) -> ImageFont.ImageFont:
    """Fonte do tema; senão a primeira disponível no sistema; senão a embutida do Pillow."""
    for path in ([configured] if configured else []) + _FONT_CANDIDATES[bold]:
        if path and Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _font(theme: Theme, size: int, bold: bool = False) -> ImageFont.ImageFont:
    return load_font(theme.font_bold if bold else theme.font, bold, size)


def _rgb(color: str) -> Tuple[int, int, int]:
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def gradient(colors: Sequence[str]) -> Image.Image:
    top = Image.new("RGB", (W, H), _rgb(colors[0]))
    bottom = Image.new("RGB", (W, H), _rgb(colors[1]))
    mask = Image.linear_gradient("L").resize((W, H))
    return Image.composite(bottom, top, mask)


def wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> List[str]:
    lines, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if draw.textlength(trial, font=font) > width and line:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line]


def _centered(draw, y, text, font, fill, stroke=0, stroke_fill="black", width=W):
    draw.text(((width - draw.textlength(text, font=font)) // 2, y), text, font=font, fill=fill,
              stroke_width=stroke, stroke_fill=stroke_fill)


def card(visual: Visual, theme: Theme, idx: int) -> Image.Image:
    img = gradient(theme.gradient(idx))
    d = ImageDraw.Draw(img)
    top, bottom = int(H * 0.22), int(H * 0.72)
    label, lines = visual.label, visual.lines

    if visual.style == "step":
        lw, x0 = 640, (W - 640) // 2
        d.rounded_rectangle([x0, top, x0 + lw, bottom], radius=70, fill="#05080F")
        d.rounded_rectangle([x0 + 18, top + 18, x0 + lw - 18, bottom - 18], radius=56, fill=theme.screen)
        d.rounded_rectangle([W // 2 - 70, top + 34, W // 2 + 70, top + 58], radius=12, fill="#05080F")
        f_label, f_line = _font(theme, 46), _font(theme, 42, bold=True)
        d.text((x0 + 60, top + 100), label.upper(), font=f_label, fill=theme.ink)
        y = top + 200
        for i, line in enumerate(lines):
            last = i == len(lines) - 1
            parts = wrap(d, line, f_line, lw - 190)
            height = 56 * len(parts) + 44
            d.rounded_rectangle([x0 + 45, y, x0 + lw - 45, y + height], radius=24,
                                fill=theme.accent if last else "white", outline="#D5DAE3", width=3)
            for j, part in enumerate(parts):
                d.text((x0 + 80, y + 22 + j * 56), part, font=f_line, fill=theme.ink)
            d.text((x0 + lw - 95, y + height // 2 - 28), ">", font=f_label, fill=theme.ink)
            if last:  # círculo de "toque aqui"
                cx, cy = x0 + lw - 80, y + height // 2
                d.ellipse([cx - 42, cy - 42, cx + 42, cy + 42], outline=theme.alert, width=8)
            y += height + 26

    elif visual.style == "alert":
        size = 110
        while size > 50 and d.textlength(label.upper(), font=_font(theme, size)) > W - 280:
            size -= 6
        f_label, f_line = _font(theme, size), _font(theme, 64)
        width = d.textlength(label.upper(), font=f_label)
        d.rounded_rectangle([(W - width) // 2 - 60, top, (W + width) // 2 + 60, top + 190], radius=40,
                            fill=visual.color or theme.alert)
        d.text(((W - width) // 2, top + 95 - size // 2 - 10), label.upper(), font=f_label, fill="white")
        y = top + 290
        for line in lines:
            for part in wrap(d, line.upper(), f_line, W - 200):
                _centered(d, y, part, f_line, "white", stroke=6)
                y += 90
            y += 20

    elif visual.style == "number":
        f_num, f_line = _font(theme, 380), _font(theme, 80)
        _centered(d, top - 40, label, f_num, theme.accent, stroke=10)
        y = top + 470
        for line in lines:
            for part in wrap(d, line.upper(), f_line, W - 180):
                _centered(d, y, part, f_line, "white", stroke=6)
                y += 105

    elif visual.style == "signature":
        if theme.avatar and Path(theme.avatar).exists():
            av = Image.open(theme.avatar).convert("RGB").resize((520, 520))
            mask = Image.new("L", av.size, 0)
            ImageDraw.Draw(mask).ellipse([0, 0, 520, 520], fill=255)
            img.paste(av, ((W - 520) // 2, top), mask)
        _centered(d, top + 600, theme.handle, _font(theme, 84), theme.accent)
    return img


def caption_png(tokens: List[str], active: Optional[int], theme: Theme) -> Image.Image:
    """Quadro RGBA transparente com a legenda; a palavra `active` usa a cor de destaque."""
    style = theme.caption
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _font(theme, style.size)
    shown = [t.upper() if style.uppercase else t for t in tokens]
    space = d.textlength(" ", font=font)

    rows: List[List[int]] = [[]]  # índices de tokens por linha
    for i, tok in enumerate(shown):
        trial = rows[-1] + [i]
        width = sum(d.textlength(shown[k], font=font) for k in trial) + space * (len(trial) - 1)
        if width > W - 140 and rows[-1]:
            rows.append([i])
        else:
            rows[-1] = trial

    line_h = style.size + 20
    y0 = int(H * style.y) - line_h * len(rows) // 2
    for r, row in enumerate(rows):
        width = sum(d.textlength(shown[k], font=font) for k in row) + space * (len(row) - 1)
        x = (W - width) / 2
        for k in row:
            color = theme.accent if k == active else theme.text
            d.text((x, y0 + r * line_h), shown[k], font=font, fill=color,
                   stroke_width=style.stroke, stroke_fill="black")
            x += d.textlength(shown[k], font=font) + space
    return img


def title_png(text: str, theme: Theme) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _font(theme, 80)
    lines = wrap(d, text.upper(), font, W - 140)
    y = int(H * 0.11) - 100 * len(lines) // 2
    for line in lines:
        _centered(d, y, line, font, theme.accent, stroke=10)
        y += 100
    return img
