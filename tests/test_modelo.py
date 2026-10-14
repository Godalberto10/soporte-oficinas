"""Pruebas del modelo guionizado."""

import pytest

from soporte_oficinas.modelo import Modelo, ScriptedModel


def test_devuelve_respuestas_en_orden():
    modelo = ScriptedModel(['{"a": 1}', '{"b": 2}'])
    assert modelo.generar("s", []) == '{"a": 1}'
    assert modelo.generar("s", []) == '{"b": 2}'


def test_agotado_lanza_runtime_error():
    modelo = ScriptedModel(["uno"])
    modelo.generar("s", [])
    with pytest.raises(RuntimeError):
        modelo.generar("s", [])


def test_guarda_las_llamadas():
    modelo = ScriptedModel(["r"])
    mensajes = [{"role": "user", "content": "no tengo internet"}]
    modelo.generar("eres el clasificador", mensajes)
    mensajes.append({"role": "assistant", "content": "cambio posterior"})
    assert modelo.llamadas == [{
        "sistema": "eres el clasificador",
        "mensajes": [{"role": "user", "content": "no tengo internet"}],
    }]


def test_no_modifica_la_lista_original():
    respuestas = ["a", "b"]
    ScriptedModel(respuestas).generar("s", [])
    assert respuestas == ["a", "b"]


def test_cumple_el_protocolo():
    def usar(modelo: Modelo) -> str:
        return modelo.generar("s", [])

    assert usar(ScriptedModel(["ok"])) == "ok"
