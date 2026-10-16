"""Renderização: roteiro + TTS + timeline -> MP4 vertical via ffmpeg."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from PIL import Image

from . import visuals
from .captions import to_srt
from .media import ffmpeg, probe_duration, require_ffmpeg
from .script import Script, Visual
from .theme import Theme
from .timeline import SceneAudio, Timeline, build_timeline
from .tts import DEFAULT_PROVIDER, get_provider
from .visuals import H, W

FPS = 30
DEFAULT_MAX_MB = 9.5


@dataclass
class RenderResult:
    video: Path
    srt: Path
    duration: float
    size_mb: float
    timeline: Timeline


def synthesize_scenes(script: Script, provider_name: str, voice: Optional[str], rate: Optional[str], tmp: Path) -> List[SceneAudio]:
    provider = get_provider(provider_name)
    voice = voice or script.voice
    rate = rate or script.rate
    audios = []
    for i, scene in enumerate(script.scenes):
        dest = tmp / f"voice{i}.mp3"
        words = provider.synthesize(scene.text, dest, voice, rate)
        audios.append(SceneAudio(scene.text, probe_duration(dest), words))
    return audios


def _pexels(query: str, dest: Path) -> bool:
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return False
    url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
        {"query": query, "orientation": "portrait", "per_page": 5, "size": "medium"})
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "shorts-pipeline/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    for video in data.get("videos", []):
        files = [f for f in video["video_files"] if f.get("height") and f["height"] >= f.get("width", 0)]
        files.sort(key=lambda f: abs(f["height"] - H))
        if files:
            urllib.request.urlretrieve(files[0]["link"], dest)
            return True
    return False


def scene_clip(visual: Visual, duration: float, idx: int, tmp: Path, base_dir: Path, theme: Theme) -> Path:
    out = tmp / f"scene{idx}.mp4"
    encode = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    fit = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1"

    source: Optional[Path] = None
    if visual.type == "video":
        source = (base_dir / str(visual.file)).resolve()
    elif visual.type == "pexels":
        cached = tmp / f"pexels_{idx}.mp4"
        if _pexels(str(visual.query), cached):  # sem chave/resultado: cai no gradiente
            source = cached
    if source:
        ffmpeg("-stream_loop", "-1", "-i", str(source), "-t", f"{duration:.3f}", "-an", "-vf", fit, *encode, str(out))
        return out

    still = tmp / f"still{idx}.png"
    if visual.type == "image":
        still = (base_dir / str(visual.file)).resolve()
    elif visual.type == "card":
        visuals.card(visual, theme, idx).save(still)
    else:
        visuals.gradient(visual.colors or theme.gradient(idx)).save(still)
    zoom_step, zoom_max = ("0.0002", "1.04") if visual.type == "card" else ("0.0007", "1.12")
    frames = max(1, int(duration * FPS))
    ffmpeg("-loop", "1", "-i", str(still), "-t", f"{duration:.3f}", "-vf",
           f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
           f"zoompan=z='min(zoom+{zoom_step},{zoom_max})':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},setsar=1",
           *encode, str(out))
    return out


def caption_track(timeline: Timeline, theme: Theme, tmp: Path) -> Path:
    """Sequência de PNGs transparentes (um por quadro de legenda) concatenada em .mov com alfa."""
    blank = tmp / "blank.png"
    Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(blank)
    entries, cursor = [], 0.0
    for i, fr in enumerate(timeline.frames):
        if fr.start > cursor + 1e-3:
            entries.append((blank, fr.start - cursor))
        png = tmp / f"cap{i}.png"
        visuals.caption_png(fr.tokens, fr.active, theme).save(png)
        entries.append((png, fr.end - fr.start))
        cursor = fr.end
    if cursor < timeline.total:
        entries.append((blank, timeline.total - cursor))
    listing = tmp / "captions.txt"
    listing.write_text("".join(f"file '{p}'\nduration {d:.3f}\n" for p, d in entries) + f"file '{entries[-1][0]}'\n")
    out = tmp / "captions.mov"
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), "-vf", f"fps={FPS},format=rgba",
           "-c:v", "png", "-t", f"{timeline.total:.3f}", str(out))
    return out


def render(script: Script, theme: Theme, out_dir: Path, provider_name: str = DEFAULT_PROVIDER,
           voice: Optional[str] = None, rate: Optional[str] = None, max_mb: float = DEFAULT_MAX_MB) -> RenderResult:
    require_ffmpeg()
    tmp = out_dir / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)

    audios = synthesize_scenes(script, provider_name, voice, rate, tmp)
    timeline = build_timeline(audios, theme.caption)

    clips = [scene_clip(sc.visual, plan.duration, plan.index, tmp, script.base_dir, theme)
             for sc, plan in zip(script.scenes, timeline.scenes)]
    (tmp / "clips.txt").write_text("".join(f"file '{c}'\n" for c in clips))
    background = tmp / "background.mp4"
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(tmp / "clips.txt"), "-c", "copy", str(background))

    inputs, filters = [], []
    for j, (a, plan) in enumerate(zip(audios, timeline.scenes)):
        inputs += ["-i", str(tmp / f"voice{j}.mp3")]
        filters.append(f"[{j}:a]apad=whole_dur={plan.duration:.3f}[a{j}]")
    voice_track = tmp / "voice.m4a"
    ffmpeg(*inputs, "-filter_complex",
           ";".join(filters) + ";" + "".join(f"[a{j}]" for j in range(len(audios))) + f"concat=n={len(audios)}:v=0:a=1[a]",
           "-map", "[a]", "-c:a", "aac", "-b:a", "128k", str(voice_track))

    args = ["-i", str(background), "-i", str(caption_track(timeline, theme, tmp)), "-i", str(voice_track)]
    graph, last = "[0:v][1:v]overlay=0:0[v1]", "v1"
    if script.title:
        title = tmp / "title.png"
        visuals.title_png(script.title, theme).save(title)
        args += ["-loop", "1", "-i", str(title)]
        graph += ";[v1][3:v]overlay=0:0:shortest=1[v2]"
        last = "v2"

    video = out_dir / "video.mp4"
    total_kbps = int(max_mb * 1e6 * 8 / timeline.total / 1000 * 0.92) - 128
    vkbps = max(300, min(3500, total_kbps))
    ffmpeg(*args, "-filter_complex", graph, "-map", f"[{last}]", "-map", "2:a",
           "-c:v", "libx264", "-preset", "medium", "-b:v", f"{vkbps}k", "-maxrate", f"{vkbps}k",
           "-bufsize", f"{vkbps * 2}k", "-pix_fmt", "yuv420p", "-c:a", "copy",
           "-t", f"{timeline.total:.3f}", "-movflags", "+faststart", str(video))

    srt = out_dir / "captions.srt"
    srt.write_text(to_srt(timeline.words, theme.caption, timeline.total), encoding="utf-8")
    return RenderResult(video, srt, timeline.total, video.stat().st_size / 1e6, timeline)
