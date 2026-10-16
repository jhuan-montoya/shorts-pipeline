import json

import pytest

from shorts.script import ScriptError, load_script, parse_script
from shorts.theme import ThemeError, theme_from_dict


def minimal(**extra):
    return {"id": "x", "scenes": [{"text": "olá mundo"}], **extra}


def test_parse_minimal_defaults():
    s = parse_script(minimal())
    assert s.id == "x" and len(s.scenes) == 1
    assert s.scenes[0].visual.type == "color"
    assert s.tts is None and s.title is None


def test_text_whitespace_is_normalized():
    s = parse_script({"id": "x", "scenes": [{"text": "  a \n  b   c "}]})
    assert s.scenes[0].text == "a b c"


@pytest.mark.parametrize("data, fragment", [
    ({"scenes": [{"text": "a"}]}, "'id'"),
    ({"id": "x"}, "'scenes'"),
    ({"id": "x", "scenes": []}, "'scenes'"),
    ({"id": "x", "scenes": [{"text": "  "}]}, "scenes[0].text"),
    ({"id": "x", "scenes": [{"text": "a", "visual": {"type": "gif"}}]}, "visual.type"),
    ({"id": "x", "scenes": [{"text": "a", "visual": {"type": "image"}}]}, "visual.file"),
    ({"id": "x", "scenes": [{"text": "a", "visual": {"type": "card", "style": "zzz"}}]}, "visual.style"),
    ({"id": "x", "scenes": [{"text": "a", "visual": {"type": "color", "colors": ["#000000"]}}]}, "visual.colors"),
    ({"id": "x", "scenes": [{"text": "a", "visual": {"type": "pexels"}}]}, "visual.query"),
])
def test_invalid_scripts_report_where(data, fragment):
    with pytest.raises(ScriptError) as exc:
        parse_script(data)
    assert fragment in str(exc.value)


def test_load_yaml_and_json_are_equivalent(tmp_path):
    data = minimal(title="T", theme={"accent": "#112233"})
    (tmp_path / "a.json").write_text(json.dumps(data))
    (tmp_path / "a.yaml").write_text(
        "id: x\ntitle: T\ntheme:\n  accent: '#112233'\nscenes:\n  - text: olá mundo\n")
    assert load_script(tmp_path / "a.json") == load_script(tmp_path / "a.yaml")


def test_theme_as_path_is_kept_as_reference():
    s = parse_script(minimal(theme="tema.yaml"))
    assert s.theme_file == "tema.yaml" and s.theme is None


def test_invalid_yaml_is_script_error(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("id: [unclosed")
    with pytest.raises(ScriptError):
        load_script(p)


def test_root_must_be_mapping(tmp_path):
    p = tmp_path / "list.yaml"
    p.write_text("- a\n- b\n")
    with pytest.raises(ScriptError):
        load_script(p)


def test_theme_defaults_and_overrides():
    t = theme_from_dict({"accent": "#00FF00", "caption": {"mode": "group", "max_words": 2}})
    assert t.accent == "#00FF00" and t.background == "#0E1A2B"
    assert t.caption.mode == "group" and t.caption.max_words == 2


def test_theme_gradient_wraps_around():
    t = theme_from_dict({"gradients": [["#000000", "#111111"], ["#222222", "#333333"]]})
    assert t.gradient(2) == t.gradient(0)


@pytest.mark.parametrize("data", [
    {"accent": "amarelo"},
    {"nope": 1},
    {"caption": {"mode": "karaoke"}},
    {"caption": {"max_words": 0}},
    {"gradients": [["#000000"]]},
])
def test_invalid_theme(data):
    with pytest.raises(ThemeError):
        theme_from_dict(data)
