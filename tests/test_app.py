"""The real web page, with streamlit.testing (milestone 8).

Skipped if Streamlit is not installed: `uv run pytest` does not need it.
To run them: uv run --group web pytest tests/test_app.py
"""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture(autouse=True)
def without_ollama(monkeypatch):
    """The tests do not depend on Ollama running on the computer."""
    from office_support.interfaces import web
    monkeypatch.setattr(web, "ollama_models", lambda *a, **k: [])


def _app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=30).run()


def _texts(app: AppTest) -> str:
    blocks = [*app.markdown, *app.success, *app.warning, *app.error, *app.info]
    return " ".join(str(b.value) for b in blocks)


def test_the_page_loads_without_errors():
    app = _app()
    assert not app.exception
    assert "Technical support" in app.title[0].value


def test_several_offices_example_shows_p1_escalation():
    app = _app()
    app.button(key="ex_2").click().run()
    assert "Escalated to second level" in _texts(app)
    assert any(m.value == "P1" for m in app.metric)


def test_confirming_with_button_resolves():
    app = _app()
    app.button(key="ex_0").click().run()
    assert "irreversible" in _texts(app)
    app.button(key="confirm").click().run()
    assert "Resolved at first level" in _texts(app)


def test_rejecting_with_button_escalates():
    app = _app()
    app.button(key="ex_0").click().run()
    app.button(key="reject").click().run()
    assert "Escalated to second level" in _texts(app)


def test_form_typed_by_hand():
    """Bug found by Alberto when trying the web: the form button broke the page."""
    app = _app()
    app.text_area(key="incident").input("My computer won't turn on")
    app.text_input(key="ticket").input("T-0001")
    next(b for b in app.button if b.label == "Handle incident").click().run()
    assert not app.exception
    assert any(m.value == "hardware" for m in app.metric)


def test_selector_shows_the_real_model_if_ollama_is_running(monkeypatch):
    from office_support.interfaces import web
    monkeypatch.setattr(web, "ollama_models", lambda *a, **k: ["qwen2.5:14b"])
    app = _app()
    assert app.radio(key="model").options == ["Simulated", "Real · qwen2.5:14b"]
