from pathlib import Path

import pytest

from shorts.cli import main
from shorts.tts import get_provider, register

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "roteiro.yaml"


def test_validate_example(capsys):
    assert main(["validate", str(EXAMPLE)]) == 0
    assert "ceu-azul" in capsys.readouterr().out


def test_plan_example_is_offline_and_reports_total(capsys):
    assert main(["plan", str(EXAMPLE)]) == 0
    out = capsys.readouterr().out
    assert "cena  1" in out and "total estimado" in out


def test_invalid_script_returns_error_code(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text("id: x\nscenes: []\n")
    assert main(["validate", str(bad)]) == 1
    assert "erro:" in capsys.readouterr().err


def test_unknown_tts_provider():
    with pytest.raises(ValueError):
        get_provider("nao-existe")


def test_custom_provider_registration_and_dotted_path():
    class Fake:
        name, default_voice = "fake", "v"

    register("fake", Fake)
    assert isinstance(get_provider("fake"), Fake)
    assert get_provider("shorts.tts.mock:MockProvider").name == "mock"
