"""Evaluación (hito 7): mis casos con resultado y trayectoria esperados.

Lo esperado no se cambia para que pase. Los 5 fallos que encontró la primera
pasada (hito 7) se arreglaron en el hito 7b; ver worklog.
"""

import pytest

from soporte_oficinas.evaluacion import CASOS, evaluar, main
from soporte_oficinas.modelo import ModeloSimulado

POR_NUMERO = {c.n: c for c in CASOS}


def _ids(casos) -> list[str]:
    return [f"{c.n}-{c.nombre}" for c in casos]


@pytest.mark.parametrize("caso", CASOS, ids=_ids(CASOS))
def test_caso_con_guion(caso):
    evaluacion = evaluar(caso)
    assert evaluacion.obtenido() == caso.esperado


SIMULABLES = [c for c in CASOS if c.simulado]


@pytest.mark.parametrize("caso", SIMULABLES, ids=_ids(SIMULABLES))
def test_caso_con_modelo_simulado(caso):
    evaluacion = evaluar(caso, ModeloSimulado())
    assert evaluacion.obtenido() == caso.esperado


def _herramientas_ejecutadas(evaluacion, nombre: str) -> list:
    return [p for p in evaluacion.resultado.traza if p.herramienta == nombre]


def test_caso_1_reinicia_la_vpn():
    evaluacion = evaluar(POR_NUMERO[1])
    assert evaluacion.red.servicios["MAD-01"]["vpn"] == "ok"
    assert len(evaluacion.preguntas) == 1


def test_caso_2_rechazo_no_reinicia_r1():
    evaluacion = evaluar(POR_NUMERO[2])
    assert evaluacion.red.servicios["MAD-01"]["vpn"] == "caido"
    assert _herramientas_ejecutadas(evaluacion, "reiniciar_servicio") == []
    assert evaluacion.resultado.escalado is not None


def test_caso_8_no_llama_al_modelo():
    assert evaluar(POR_NUMERO[8]).llamadas_modelo == 0


def test_caso_9_cita_inventada_eliminada_r5():
    resultado = evaluar(POR_NUMERO[9]).resultado
    assert "docs/kb-red-07.md#Pasos" not in resultado.citas
    assert "kb-red-07" not in resultado.respuesta


def test_caso_10_guardarrail_bloquea_sin_preguntar_r2():
    evaluacion = evaluar(POR_NUMERO[10])
    assert evaluacion.preguntas == []
    assert evaluacion.red.servicios["MAD-01"]["erp"] == "ok"
    assert _herramientas_ejecutadas(evaluacion, "reiniciar_servicio") == []


def test_tabla_para_el_informe(capsys):
    assert main(["--modelo", "guion"]) == 0
    salida = capsys.readouterr().out
    assert "| 1 | internet MAD-01, confirma |" in salida
    assert "**Aciertos**" in salida
