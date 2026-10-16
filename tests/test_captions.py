from shorts.captions import build_frames, group_words, srt_timestamp, to_srt
from shorts.theme import CaptionStyle
from shorts.tts.base import Word, estimate_word_timings, mark_pauses, parse_rate_percent

import pytest


def words(*items):
    return [Word(t, s, e, p) for t, s, e, p in items]


def test_estimate_covers_whole_duration_and_is_monotonic():
    ws = estimate_word_timings("Olá mundo, isto é um teste.", 5.0)
    assert [w.text for w in ws] == ["Olá", "mundo", "isto", "é", "um", "teste"]
    assert ws[0].start == 0.0
    assert ws[-1].end <= 5.0 and ws[-1].end > 3.5  # última palavra termina antes da pausa final
    for a, b in zip(ws, ws[1:]):
        assert a.start < a.end <= b.start


def test_estimate_longer_words_get_more_time():
    ws = estimate_word_timings("a internacionalização", 4.0)
    assert (ws[1].end - ws[1].start) > 5 * (ws[0].end - ws[0].start)


def test_estimate_marks_punctuation_as_pause():
    ws = estimate_word_timings("sim, não. talvez", 3.0)
    assert [w.pause for w in ws] == [True, True, False]


def test_estimate_empty_text():
    assert estimate_word_timings("   ", 2.0) == []


def test_mark_pauses_recovers_punctuation_from_text():
    ws = [Word("Olá", 0, 1), Word("mundo", 1, 2), Word("tudo", 2, 3), Word("bem", 3, 4)]
    mark_pauses("Olá mundo, tudo bem?", ws)
    assert [w.pause for w in ws] == [False, True, False, True]


@pytest.mark.parametrize("rate, expected", [(None, 0.0), ("+10%", 0.10), ("-25%", -0.25), ("5%", 0.05)])
def test_parse_rate(rate, expected):
    assert parse_rate_percent(rate) == pytest.approx(expected)


def test_parse_rate_invalid():
    with pytest.raises(ValueError):
        parse_rate_percent("rápido")


def test_group_respects_max_words_and_max_chars():
    ws = words(*[(f"w{i}", i, i + 0.5, False) for i in range(7)])
    assert [len(g.words) for g in group_words(ws, max_words=3, max_chars=99)] == [3, 3, 1]
    long = words(("internacional", 0, 1, False), ("construção", 1, 2, False))
    assert [len(g.words) for g in group_words(long, max_words=3, max_chars=16)] == [1, 1]


def test_group_breaks_on_pause():
    ws = words(("a", 0, 1, False), ("b", 1, 2, True), ("c", 2, 3, False))
    assert [g.text for g in group_words(ws, 3, 99)] == ["a b", "c"]


def test_word_mode_one_frame_per_word_with_active_index():
    ws = words(("um", 0.0, 0.4, False), ("dois", 0.5, 0.9, False), ("três", 1.0, 1.4, True))
    frames = build_frames(ws, total=3.0, style=CaptionStyle(mode="word"))
    assert [f.active for f in frames] == [0, 1, 2]
    assert all(f.tokens == ["um", "dois", "três"] for f in frames)
    # troca de palavra sem buraco entre quadros do mesmo grupo
    assert frames[0].end == pytest.approx(frames[1].start)
    assert frames[1].end == pytest.approx(frames[2].start)


def test_group_mode_one_frame_per_group_without_highlight():
    ws = words(("um", 0, 0.4, False), ("dois", 0.5, 0.9, True), ("três", 2.0, 2.4, False))
    frames = build_frames(ws, 4.0, CaptionStyle(mode="group"))
    assert [f.active for f in frames] == [None, None]
    assert frames[0].tokens == ["um", "dois"]


def test_hold_is_capped_by_max_hold_and_total():
    ws = words(("fim", 0.0, 0.5, True), ("depois", 5.0, 5.5, True))
    frames = build_frames(ws, 6.0, CaptionStyle(mode="group", max_hold=0.35))
    assert frames[0].end == pytest.approx(0.85)  # não fica na tela durante a pausa longa
    assert frames[1].end == pytest.approx(5.85)
    short = build_frames(ws, 5.6, CaptionStyle(mode="group", max_hold=0.35))
    assert short[1].end == pytest.approx(5.6)


def test_frames_are_sorted_non_overlapping_and_positive():
    ws = estimate_word_timings("uma frase razoavelmente longa para gerar vários grupos de legenda, ok?", 6.0)
    frames = build_frames(ws, 6.5, CaptionStyle())
    for f in frames:
        assert f.end > f.start
    for a, b in zip(frames, frames[1:]):
        assert a.end <= b.start + 1e-9


def test_srt_timestamp_format():
    assert srt_timestamp(0) == "00:00:00,000"
    assert srt_timestamp(61.5) == "00:01:01,500"
    assert srt_timestamp(3661.0239) == "01:01:01,024"


def test_srt_output():
    ws = words(("olá", 0.1, 0.5, False), ("mundo", 0.5, 1.0, True))
    srt = to_srt(ws, CaptionStyle(), total=2.0)
    assert srt.startswith("1\n00:00:00,100 --> 00:00:01,350\nolá mundo\n")
