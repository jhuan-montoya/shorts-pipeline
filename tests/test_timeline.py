import pytest

from shorts.theme import CaptionStyle
from shorts.timeline import SCENE_TAIL, SceneAudio, build_timeline
from shorts.tts.base import estimate_word_timings
from shorts.tts.mock import estimate_duration


def audio(text, dur):
    return SceneAudio(text, dur, estimate_word_timings(text, dur))


def test_scenes_are_sequential_with_tail():
    tl = build_timeline([audio("primeira cena", 2.0), audio("segunda cena aqui", 3.0)], CaptionStyle())
    a, b = tl.scenes
    assert a.start == 0 and a.duration == pytest.approx(2.0 + SCENE_TAIL)
    assert b.start == pytest.approx(a.end)
    assert tl.total == pytest.approx(5.0 + 2 * SCENE_TAIL)


def test_words_are_shifted_to_absolute_time():
    tl = build_timeline([audio("um dois", 1.0), audio("tres quatro", 1.0)], CaptionStyle())
    second_scene_words = [w for w in tl.words if w.text in ("tres", "quatro")]
    assert second_scene_words[0].start == pytest.approx(1.0 + SCENE_TAIL)
    assert all(tl.scenes[1].start <= w.start < tl.scenes[1].end for w in second_scene_words)


def test_word_timings_are_clamped_to_audio_duration():
    from shorts.tts.base import Word
    tl = build_timeline([SceneAudio("a b", 1.0, [Word("a", 0.0, 0.5), Word("b", 0.9, 1.7)])], CaptionStyle())
    assert tl.words[-1].end == pytest.approx(1.0)


def test_caption_never_crosses_scene_boundary_start():
    tl = build_timeline([audio("alpha beta gamma delta", 2.0), audio("omega", 1.0)], CaptionStyle(mode="group"))
    boundary = tl.scenes[1].start
    for f in tl.frames:
        starts_before = f.start < boundary
        ends_after = f.end > boundary + 1e-9
        assert not (starts_before and ends_after and "omega" in f.tokens)
    # a última palavra da cena 1 fecha o grupo: nenhum quadro mistura as duas cenas
    assert all(not ({"delta", "omega"} <= set(f.tokens)) for f in tl.frames)


def test_frames_stay_inside_total():
    tl = build_timeline([audio("texto de teste um", 2.0), audio("outro texto", 1.5)], CaptionStyle())
    assert tl.frames[0].start >= 0
    assert tl.frames[-1].end <= tl.total + 1e-9


def test_empty_audio_list():
    tl = build_timeline([], CaptionStyle())
    assert tl.total == 0 and tl.frames == [] and tl.scenes == []


def test_mock_duration_scales_with_text_and_rate():
    assert estimate_duration("a" * 140) == pytest.approx(10.0)
    assert estimate_duration("a" * 140, "+100%") == pytest.approx(5.0)
    assert estimate_duration("") == 0.6
