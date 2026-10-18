"""La página web de verdad, con streamlit.testing (hito 8).

Se omite si Streamlit no está instalado: `uv run pytest` no lo necesita.
Para lanzarlas: uv run --group web pytest tests/test_app.py
"""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture(autouse=True)
def sin_ollama(monkeypatch):
    """Las pruebas no dependen de que Ollama esté funcionando en el equipo."""
    from soporte_oficinas import web
    monkeypatch.setattr(web, "modelos_ollama", lambda *a, **k: [])


def _app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=30).run()


def _textos(app: AppTest) -> str:
    bloques = [*app.markdown, *app.success, *app.warning, *app.error, *app.info]
    return " ".join(str(b.value) for b in bloques)


def test_la_pagina_carga_sin_errores():
    app = _app()
    assert not app.exception
    assert "Soporte técnico" in app.title[0].value


def test_ejemplo_varias_oficinas_muestra_escalado_p1():
    app = _app()
    app.button(key="ej_2").click().run()
    assert "Escalado a segundo nivel" in _textos(app)
    assert any(m.value == "P1" for m in app.metric)


def test_confirmar_con_boton_resuelve():
    app = _app()
    app.button(key="ej_0").click().run()
    assert "irreversible" in _textos(app)
    app.button(key="confirmar").click().run()
    assert "Resuelto en primer nivel" in _textos(app)


def test_rechazar_con_boton_escala():
    app = _app()
    app.button(key="ej_0").click().run()
    app.button(key="rechazar").click().run()
    assert "Escalado a segundo nivel" in _textos(app)


def test_formulario_escrito_a_mano():
    """Fallo encontrado por Alberto al probar la web: el botón del formulario rompía la página."""
    app = _app()
    app.text_area(key="incidencia").input("No me enciende el ordenador")
    app.text_input(key="ticket").input("T-0001")
    next(b for b in app.button if b.label == "Atender incidencia").click().run()
    assert not app.exception
    assert any(m.value == "hardware" for m in app.metric)


def test_selector_muestra_el_modelo_real_si_hay_ollama(monkeypatch):
    from soporte_oficinas import web
    monkeypatch.setattr(web, "modelos_ollama", lambda *a, **k: ["qwen2.5:14b"])
    app = _app()
    assert app.radio(key="modelo").options == ["Simulado", "Real · qwen2.5:14b"]
