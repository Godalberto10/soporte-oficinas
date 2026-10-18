"""Pruebas de la lógica de la web (hito 8), sin Streamlit."""

import pytest

from soporte_oficinas.estado import Accion
from soporte_oficinas.modelo import ModeloOllama, ModeloSimulado, ScriptedModel
from soporte_oficinas.web import (EJEMPLOS, OFICINAS, Ejecucion, averias, crear_modelo,
                                  describir_accion, etapas, filas_traza, modelos_ollama)

INTERNET = ("no tengo internet", "MAD-01", "T-0001")
REINICIO_VPN = Accion("reiniciar_servicio", {"servicio": "vpn", "oficina": "MAD-01"})


def terminar(ejecucion: Ejecucion, si: bool | None = None):
    """Espera; si pregunta, responde `si`; devuelve el resultado."""
    ejecucion.esperar(10)
    if si is not None:
        assert ejecucion.pendiente == REINICIO_VPN
        ejecucion.responder(si)
        ejecucion.esperar(10)
    assert ejecucion.pendiente is None and ejecucion.error is None
    return ejecucion.resultado


def test_se_para_a_preguntar_sin_ejecutar_nada():
    ejecucion = Ejecucion(*INTERNET)
    ejecucion.esperar(10)
    assert ejecucion.pendiente == REINICIO_VPN and ejecucion.resultado is None
    assert describir_accion(ejecucion.pendiente) == "reiniciar_servicio(servicio=vpn, oficina=MAD-01)"
    ejecucion.responder(False)  # no dejar el hilo esperando


def test_confirmar_desde_la_web_resuelve():
    resultado = terminar(Ejecucion(*INTERNET), si=True)
    assert (resultado.final, resultado.prioridad) == ("resuelto", "P1")
    assert any(p.herramienta == "reiniciar_servicio" for p in resultado.traza)


def test_rechazar_desde_la_web_escala_sin_reiniciar_r1():
    resultado = terminar(Ejecucion(*INTERNET), si=False)
    assert resultado.final == "escalado"
    assert not any(p.herramienta == "reiniciar_servicio" for p in resultado.traza)


@pytest.mark.parametrize("ejemplo, final", [
    (EJEMPLOS[1], "resuelto"),   # caso 3
    (EJEMPLOS[2], "escalado"),   # caso 5
    (EJEMPLOS[3], "escalado"),   # caso 4
    (EJEMPLOS[4], "resuelto"),   # caso 11
    (EJEMPLOS[5], "rechazado"),  # caso 7
], ids=lambda x: getattr(x, "titulo", x))
def test_ejemplos_dan_el_final_de_mi_evaluacion(ejemplo, final):
    resultado = terminar(Ejecucion(ejemplo.incidencia, ejemplo.oficina, ejemplo.ticket))
    assert resultado.final == final


def test_ticket_vacio_es_sin_ticket():
    resultado = terminar(Ejecucion("la impresora no imprime", "MAD-01", "   "))
    assert resultado.final != "rechazado"


@pytest.mark.parametrize("oficina, ticket, motivo", [
    ("SEV-01", "", "SEV-01 no existe"),
    ("MAD-01", "T-9999", "T-9999 no existe"),
])
def test_entrada_no_valida_rechazada(oficina, ticket, motivo):
    resultado = terminar(Ejecucion("no tengo internet", oficina, ticket))
    assert resultado.final == "rechazado" and motivo in resultado.respuesta


def test_un_fallo_del_modelo_se_muestra_como_error():
    ejecucion = Ejecucion(*INTERNET, modelo=ScriptedModel([]))  # guion vacío: RuntimeError
    ejecucion.esperar(10)
    assert isinstance(ejecucion.error, RuntimeError) and ejecucion.resultado is None


def test_ejemplos_usan_oficinas_validas_y_filas_de_traza():
    assert all(e.oficina in OFICINAS for e in EJEMPLOS)
    filas = filas_traza(terminar(Ejecucion(*INTERNET), si=True).traza)
    assert filas[0]["agente"] == "clasificador" and set(filas[0]) == {
        "n", "agente", "herramienta", "observación"}


def test_averias_muestra_el_estado_inicial_de_la_red():
    estado = averias()
    assert estado["MAD-01"]["vpn"] == "caido"
    assert estado["VAL-01"] == {}


def test_modelos_ollama_vacio_si_no_esta_funcionando():
    assert modelos_ollama("http://127.0.0.1:9/v1", espera=0.5) == []


def test_crear_modelo_por_nombre():
    assert isinstance(crear_modelo("simulado"), ModeloSimulado)
    real = crear_modelo("qwen2.5:14b")
    assert isinstance(real, ModeloOllama) and real.modelo == "qwen2.5:14b"


def test_responder_sin_pregunta_pendiente_no_bloquea():
    """Con un modelo real, la ejecución puede terminar sin preguntar: responder no debe colgarla."""
    ejecucion = Ejecucion("la impresora no imprime", "MAD-02", "T-0007")  # escala sin preguntar
    ejecucion.esperar(10)
    ejecucion.responder(True)
    ejecucion.esperar(2)
    assert ejecucion.resultado.final == "escalado" and ejecucion.respuesta is None


def test_etapas_marca_los_agentes_que_actuaron():
    resultado = terminar(Ejecucion("no puedo entrar en el ERP", "MAD-02", "T-0004"))
    assert etapas(resultado) == [("clasificador", True), ("diagnostico", True),
                                 ("conocimiento", False), ("escalado", True)]


def test_explicaciones_coinciden_con_la_guia_y_el_catalogo():
    from pathlib import Path

    from soporte_oficinas import web
    guia = (Path(__file__).resolve().parents[1] / "docs" / "guia-prioridades.md"
            ).read_text(encoding="utf-8").replace("`", "").replace("caido", "caído")
    for prioridad, criterio in web.CRITERIO_PRIORIDAD.items():
        assert criterio.split(",")[0] in guia
    assert web.explicar_prioridad("P1").endswith("Primera respuesta en 15 minutos.")
    assert set(web.SIGNIFICADO_FINAL) == {"resuelto", "escalado", "rechazado", "tope_alcanzado"}
