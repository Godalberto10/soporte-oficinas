"""Tests of the office-support command (no network, no .env)."""

import tomllib
from pathlib import Path

import pytest

from office_support.interfaces import cli
from office_support import model as model_module
from office_support.domain import Action

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def without_real_env(monkeypatch):
    monkeypatch.setattr(model_module, "load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("HF_TOKEN", raising=False)


def answers(text: str):
    questions: list[str] = []

    def read(question: str) -> str:
        questions.append(question)
        return text
    read.questions = questions
    return read


def no_terminal(question: str) -> str:
    raise EOFError


# --- Criterion 6: output and confirmation ----------------------------------------

def test_cli_confirming_yes_resolves(capsys):
    read = answers("y")
    code = cli.main(["I have no internet", "--office", "MAD-01"], read)
    output = capsys.readouterr().out
    assert code == 0
    assert "Final: resolved" in output
    assert "Type: network" in output and "Priority: P1" in output
    assert "docs/kb-network-01.md#Steps" in output
    assert read.questions == ["Confirm restart_service(service=vpn, office=MAD-01)? [y/N] "]


@pytest.mark.parametrize("read", [answers("n"), answers(""), no_terminal])
def test_cli_without_confirming_escalates(capsys, read):
    assert cli.main(["I have no internet", "--office", "MAD-01", "--trace"], read) == 0
    output = capsys.readouterr().out
    assert "Final: escalated" in output and "Escalation: ESC-0001" in output
    assert "restart_service({" not in output  # never appears as executed


def test_cli_numbered_trace(capsys):
    cli.main(["I have no internet", "--office", "VAL-01", "--trace"], no_terminal)
    output = capsys.readouterr().out
    assert "Trace:" in output
    assert "   1. [classifier]" in output
    assert "[diagnosis] check_service(" in output


def test_cli_non_existent_office(capsys):
    assert cli.main(["I have no internet", "--office", "SEV-01"], no_terminal) == 0
    output = capsys.readouterr().out
    assert "Final: rejected" in output and "SEV-01" in output


@pytest.mark.parametrize("text, expected", [
    ("y", True), ("Y", True), ("yes", True), (" y ", True),
    ("n", False), ("", False), ("ok", False),
])
def test_confirmer(text, expected):
    action = Action("restart_service", {"service": "vpn", "office": "MAD-01"})
    assert cli.confirmer(answers(text))(action) is expected


# --- Criterion 7: --model hf without a token ------------------------------------------

def test_cli_hf_without_token(capsys):
    code = cli.main(["I have no internet", "--office", "MAD-01", "--model", "hf"],
                    no_terminal)
    captured = capsys.readouterr()
    assert code == 2
    assert "HF_TOKEN" in captured.err
    assert "Traceback" not in captured.err and captured.out == ""


# --- Criterion 8: pyproject and --help ----------------------------------------------

def test_pyproject_points_to_cli():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["scripts"]["office-support"] == "office_support.interfaces.cli:main"


def test_help(capsys):
    with pytest.raises(SystemExit) as exit_:
        cli.main(["--help"])
    assert exit_.value.code == 0
    assert "--office" in capsys.readouterr().out


def test_office_is_required(capsys):
    with pytest.raises(SystemExit) as exit_:
        cli.main(["I have no internet"])
    assert exit_.value.code == 2
