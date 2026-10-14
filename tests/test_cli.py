"""Pruebas de la orden soporte-oficinas (sin red, sin .env)."""

import tomllib
from pathlib import Path

import pytest

from soporte_oficinas import cli
from soporte_oficinas import modelo as modulo_modelo
from soporte_oficinas.estado import Accion

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def sin_env_real(monkeypatch):
    monkeypatch.setattr(modulo_modelo, "load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("HF_TOKEN", raising=False)


def responde(texto: str):
    preguntas: list[str] = []

    def entrada(pregunta: str) -> str:
        preguntas.append(pregunta)
        return texto
    entrada.preguntas = preguntas
    return entrada


def sin_terminal(pregunta: str) -> str:
    raise EOFError


# --- Criterio 6: salida y confirmación ----------------------------------------

def test_cli_confirmar_si_resuelve(capsys):
    entrada = responde("s")
    codigo = cli.main(["no tengo internet", "--oficina", "MAD-01"], entrada)
    salida = capsys.readouterr().out
    assert codigo == 0
    assert "Final: resuelto" in salida
    assert "Tipo: red" in salida and "Prioridad: P1" in salida
    assert "docs/kb-red-01.md#Pasos" in salida
    assert entrada.preguntas == ["¿Confirmas reiniciar_servicio(servicio=vpn, oficina=MAD-01)? [s/N] "]


@pytest.mark.parametrize("entrada", [responde("n"), responde(""), sin_terminal])
def test_cli_sin_confirmar_escala(capsys, entrada):
    assert cli.main(["no tengo internet", "--oficina", "MAD-01", "--traza"], entrada) == 0
    salida = capsys.readouterr().out
    assert "Final: escalado" in salida and "Escalado: ESC-0001" in salida
    assert "reiniciar_servicio({" not in salida  # nunca aparece como ejecutado


def test_cli_traza_numerada(capsys):
    cli.main(["no tengo internet", "--oficina", "VAL-01", "--traza"], sin_terminal)
    salida = capsys.readouterr().out
    assert "Traza:" in salida
    assert "   1. [clasificador]" in salida
    assert "[diagnostico] consultar_servicio(" in salida


def test_cli_oficina_inexistente(capsys):
    assert cli.main(["no tengo internet", "--oficina", "SEV-01"], sin_terminal) == 0
    salida = capsys.readouterr().out
    assert "Final: rechazado" in salida and "SEV-01" in salida


@pytest.mark.parametrize("texto, esperado", [
    ("s", True), ("S", True), ("si", True), ("sí", True), (" s ", True),
    ("n", False), ("", False), ("vale", False),
])
def test_confirmador(texto, esperado):
    accion = Accion("reiniciar_servicio", {"servicio": "vpn", "oficina": "MAD-01"})
    assert cli.confirmador(responde(texto))(accion) is esperado


# --- Criterio 7: --modelo hf sin token ------------------------------------------

def test_cli_hf_sin_token(capsys):
    codigo = cli.main(["no tengo internet", "--oficina", "MAD-01", "--modelo", "hf"],
                      sin_terminal)
    capturado = capsys.readouterr()
    assert codigo == 2
    assert "HF_TOKEN" in capturado.err
    assert "Traceback" not in capturado.err and capturado.out == ""


# --- Criterio 8: pyproject y --help ----------------------------------------------

def test_pyproject_apunta_a_cli():
    datos = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    assert datos["project"]["scripts"]["soporte-oficinas"] == "soporte_oficinas.cli:main"


def test_help(capsys):
    with pytest.raises(SystemExit) as salida:
        cli.main(["--help"])
    assert salida.value.code == 0
    assert "--oficina" in capsys.readouterr().out


def test_oficina_obligatoria(capsys):
    with pytest.raises(SystemExit) as salida:
        cli.main(["no tengo internet"])
    assert salida.value.code == 2
