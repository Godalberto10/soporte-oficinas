"""Evaluación (hito 7): mis casos con resultado y trayectoria esperados.

Los fallos conocidos se marcan xfail(strict=True): si se arreglan, la prueba
avisa para quitar la marca. No se cambia lo esperado para que pase.
"""

import pytest

from soporte_oficinas.evaluacion import CASOS, evaluar, main
from soporte_oficinas.modelo import ModeloSimulado

POR_NUMERO = {c.n: c for c in CASOS}

FALLOS_GUION = {
    7: "un rechazo fuera de ámbito conserva la prioridad del clasificador (P4); "
       "yo espero que no tenga prioridad",
    11: "no existe un artículo sobre equipos lentos: la cita a kb-hardware-03 se "
        "elimina (R5) y se escala",
}
FALLOS_SIMULADO = {
    4: "el simulado siempre propone P3 y la prioridad solo se sube: no llega a P4",
    7: "el simulado no reconoce lo que está fuera de ámbito: lo clasifica como 'otro'",
    11: "el simulado no reconoce 'ordenador' (tipo otro, P3) y cita kb-red-02, "
        "que no trata de equipos lentos",
}


def _parametros(casos, fallos):
    return [pytest.param(c, id=f"{c.n}-{c.nombre}",
                         marks=[pytest.mark.xfail(reason=fallos[c.n], strict=True)]
                         if c.n in fallos else [])
            for c in casos]


@pytest.mark.parametrize("caso", _parametros(CASOS, FALLOS_GUION))
def test_caso_con_guion(caso):
    evaluacion = evaluar(caso)
    assert evaluacion.obtenido() == caso.esperado


@pytest.mark.parametrize("caso", _parametros([c for c in CASOS if c.simulado],
                                             FALLOS_SIMULADO))
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
