"""Pruebas del bucle común de agente y de los cuatro agentes."""

import json
from pathlib import Path

import pytest

from soporte_oficinas.agentes import (
    AGENTES,
    SERVICIOS,
    TIPOS,
    ejecutar_agente,
    extraer_json,
    prompt_sistema,
)
from soporte_oficinas import agentes
from soporte_oficinas.estado import Accion, Estado
from soporte_oficinas.herramientas import Red, crear_herramientas
from soporte_oficinas.modelo import ScriptedModel


def j(datos: dict) -> str:
    return json.dumps(datos, ensure_ascii=False)


def llamada(herramienta: str, **argumentos) -> str:
    return j({"herramienta": herramienta, "argumentos": argumentos})


@pytest.fixture
def red() -> Red:
    return Red.desde_directorio()


@pytest.fixture
def h(red):
    return crear_herramientas(red)


@pytest.fixture
def estado() -> Estado:
    return Estado("no tengo internet", "MAD-01", ticket="T-0001")


PROCEDIMIENTO_VPN = {
    "procedimiento": "La VPN de la oficina está caída; se reinicia y se reabre el navegador.",
    "citas": ["docs/kb-red-01.md#Pasos"],
    "accion": None,
}


# --- Criterio 1: extraer_json -----------------------------------------------

@pytest.mark.parametrize("texto", [
    '{"a": 1}',
    '```json\n{"a": 1}\n```',
    'Claro, aquí está:\n```json\n{"a": 1}\n```\nEspero que sirva.',
    'Mi respuesta es {"a": 1} y nada más.',
])
def test_extraer_json_acepta(texto):
    assert extraer_json(texto) == {"a": 1}


@pytest.mark.parametrize("texto", ["no sé qué decir", "[1, 2]", '[{"a": 1}]', "", "{roto"])
def test_extraer_json_rechaza(texto):
    with pytest.raises(ValueError):
        extraer_json(texto)


# --- Criterio 2: prompt de sistema ------------------------------------------

@pytest.mark.parametrize("nombre", list(AGENTES))
def test_prompt_solo_herramientas_permitidas(nombre, h):
    agente = AGENTES[nombre]
    prompt = prompt_sistema(agente, h)
    for clave in agente.claves:
        assert clave in prompt
    for herramienta in h.values():
        if herramienta.nombre in agente.herramientas:
            assert herramienta.nombre in prompt
            assert herramienta.descripcion in prompt
        else:
            assert herramienta.nombre not in prompt, herramienta.nombre
    assert "único objeto JSON" in prompt


def test_prompt_conocimiento_separa_proponibles(h):
    prompt = prompt_sistema(AGENTES["conocimiento"], h)
    resto, proponibles = prompt.split("Acciones que puedes proponer")
    llamables = resto.split("Herramientas que puedes llamar")[1]  # solo la lista
    assert "buscar_docs(consulta: str, k: int = 3)" in llamables
    assert "reiniciar_servicio" not in llamables
    assert "reiniciar_servicio(servicio: str, oficina: str)" in proponibles


# --- Criterio 3: conocimiento, camino feliz ---------------------------------

def test_conocimiento_camino_feliz(estado, h):
    modelo = ScriptedModel([llamada("buscar_docs", consulta="vpn caída"), j(PROCEDIMIENTO_VPN)])
    salida = agentes.conocimiento(estado, modelo, h)
    assert salida.motivo == "ok"
    assert estado.procedimiento == PROCEDIMIENTO_VPN["procedimiento"]
    assert estado.citas == ["docs/kb-red-01.md#Pasos"]
    assert estado.acciones == []
    assert estado.pasos == 3
    modelo1, herramienta, modelo2 = estado.traza
    assert [p.n for p in estado.traza] == [1, 2, 3]
    assert modelo1.herramienta is None and modelo2.herramienta is None
    assert herramienta.herramienta == "buscar_docs"
    assert herramienta.observacion["fragmentos"][0]["doc"] == "docs/kb-red-01.md"
    assert all(p.agente == "conocimiento" for p in estado.traza)


# --- Criterio 4: acción propuesta, no ejecutada ----------------------------

def test_conocimiento_con_accion(estado, h, red):
    salida_json = dict(PROCEDIMIENTO_VPN, accion={
        "herramienta": "reiniciar_servicio",
        "argumentos": {"servicio": "vpn", "oficina": "MAD-01"},
    })
    modelo = ScriptedModel([llamada("buscar_docs", consulta="vpn"), j(salida_json)])
    salida = agentes.conocimiento(estado, modelo, h)
    assert salida.motivo == "ok"
    assert estado.acciones == [Accion("reiniciar_servicio", {"servicio": "vpn", "oficina": "MAD-01"})]
    assert red.servicios["MAD-01"]["vpn"] == "caido"


def test_conocimiento_accion_reversible_es_ilegible(estado, h):
    mala = dict(PROCEDIMIENTO_VPN, accion={"herramienta": "buscar_docs", "argumentos": {}})
    salida = agentes.conocimiento(estado, ScriptedModel([j(mala), j(mala)]), h)
    assert salida.motivo == "ilegible"
    assert estado.acciones == []


# --- Criterio 5: irreversible llamada como turno -----------------------------

@pytest.mark.parametrize("turno", [
    llamada("reiniciar_servicio", servicio="vpn", oficina="MAD-01"),
    llamada("cerrar_ticket", ticket="T-0001", resolucion="arreglado"),
])
def test_irreversible_como_turno_no_se_ejecuta(estado, h, red, turno):
    modelo = ScriptedModel([turno, j(PROCEDIMIENTO_VPN)])
    salida = agentes.conocimiento(estado, modelo, h)
    assert salida.motivo == "ok"
    assert red.servicios["MAD-01"]["vpn"] == "caido"
    assert red.ticket("T-0001")["estado"] == "abierto"
    bloqueo = estado.traza[1]
    assert bloqueo.herramienta is None
    assert "irreversible" in bloqueo.observacion["error"]
    assert not any(p.herramienta in {"reiniciar_servicio", "cerrar_ticket"}
                   for p in estado.traza)
    assert "accion" in modelo.llamadas[1]["mensajes"][-1]["content"]


CLASIFICACION = {"tipo": "red", "prioridad": "P1", "motivo": "vpn crítica caída"}
DIAGNOSTICO = {"causa": "VPN de MAD-01 caída", "servicio": "vpn",
               "evidencias": ["consultar_servicio(vpn, MAD-01) = caido"]}
ESCALADO = {"resumen": "VPN caída en MAD-01, reinicio rechazado",
            "probado": ["consultar estado de la vpn"], "prioridad": "P1"}


# --- Criterio 6: herramienta no permitida ------------------------------------

def test_herramienta_no_permitida(estado, h):
    modelo = ScriptedModel([llamada("consultar_servicio", servicio="vpn", oficina="MAD-01"),
                            j(CLASIFICACION)])
    salida = agentes.clasificador(estado, modelo, h)
    assert salida.motivo == "ok"
    bloqueo = estado.traza[1]
    assert bloqueo.herramienta is None
    assert "no permitida" in bloqueo.observacion["error"]
    assert not any(p.herramienta == "consultar_servicio" for p in estado.traza)
    assert "no permitida" in modelo.llamadas[1]["mensajes"][-1]["content"]


# --- Criterio 7: ErrorHerramienta como observación ----------------------------

def test_error_herramienta_como_observacion(estado, h):
    modelo = ScriptedModel([
        llamada("consultar_servicio", servicio="vpn", oficina="SEV-01"),
        llamada("consultar_servicio", servicio="vpn", oficina="MAD-01"),
        j(DIAGNOSTICO),
    ])
    salida = agentes.diagnostico(estado, modelo, h)
    assert salida.motivo == "ok"
    error, correcta = estado.traza[1], estado.traza[3]
    assert error.herramienta == "consultar_servicio"
    assert "oficina desconocida" in error.observacion["error"]
    assert correcta.observacion["estado"] == "caido"


# --- Criterio 8: respuestas ilegibles -----------------------------------------

def test_una_ilegible_y_luego_valida(estado, h):
    salida = agentes.clasificador(estado, ScriptedModel(["no sé", j(CLASIFICACION)]), h)
    assert salida.motivo == "ok"
    assert "no válida" in estado.traza[0].observacion


def test_dos_ilegibles_seguidas(estado, h):
    salida = agentes.clasificador(estado, ScriptedModel(["no sé", "tampoco"]), h)
    assert salida.motivo == "ilegible"
    assert salida.datos is None
    assert estado.tipo is None and estado.pasos == 2


@pytest.mark.parametrize("mala", [
    {"tipo": "red", "prioridad": "P1"},                      # falta motivo
    {"tipo": "router", "prioridad": "P1", "motivo": "x"},    # tipo inválido
    {"tipo": "red", "prioridad": "P9", "motivo": "x"},       # prioridad inválida
])
def test_contrato_incumplido_cuenta_como_ilegible(estado, h, mala):
    salida = agentes.clasificador(estado, ScriptedModel([j(mala), j(mala)]), h)
    assert salida.motivo == "ilegible"


def test_ilegibles_no_seguidas_no_paran(estado, h):
    modelo = ScriptedModel(["no sé", llamada("buscar_tickets", oficina="MAD-01"),
                            "otra vez no", j(CLASIFICACION)])
    assert agentes.clasificador(estado, modelo, h).motivo == "ok"


# --- Criterio 9: tope de pasos ------------------------------------------------

def test_tope(estado, h):
    modelo = ScriptedModel([llamada("buscar_tickets")] * 10)
    salida = agentes.clasificador(estado, modelo, h, max_pasos=3)
    assert salida.motivo == "tope"
    assert estado.pasos == 3 and len(estado.traza) == 3


def test_tope_cuenta_pasos_previos(estado, h):
    estado.pasos = 12
    modelo = ScriptedModel([j(CLASIFICACION)])
    assert agentes.clasificador(estado, modelo, h).motivo == "tope"
    assert modelo.llamadas == []


# --- Criterio 10: clasificador y diagnóstico rellenan el estado ----------------

def test_clasificador_rellena_estado(estado, h):
    modelo = ScriptedModel([llamada("buscar_tickets", sintoma="internet"),
                            j(dict(CLASIFICACION, prioridad="P3"))])
    agentes.clasificador(estado, modelo, h)
    assert estado.tipo == "red"
    assert estado.prioridad == "P3"  # tal cual; la sube el orquestador (hito 5)


def test_diagnostico_rellena_estado(estado, h):
    agentes.diagnostico(estado, ScriptedModel([j(DIAGNOSTICO)]), h)
    assert estado.causa == "VPN de MAD-01 caída"
    assert estado.servicio == "vpn"


def test_diagnostico_servicio_nulo_para_equipo(h):
    estado = Estado("no tengo internet", "VAL-01", ticket="T-0002")
    respuesta = {"causa": "tarjeta de red averiada en PC-VAL01-002", "servicio": None,
                 "evidencias": ["PC-VAL01-002: averiado_tarjeta_red"]}
    modelo = ScriptedModel([llamada("consultar_equipo", id_equipo="PC-VAL01-002"), j(respuesta)])
    assert agentes.diagnostico(estado, modelo, h).motivo == "ok"
    assert estado.servicio is None


# --- Criterio 11: escalado ----------------------------------------------------

def test_escalado_crea_en_la_red(estado, h, red):
    salida = agentes.escalado(estado, ScriptedModel([j(ESCALADO)]), h)
    assert salida.motivo == "ok"
    assert salida.datos["escalado"] == "ESC-0001"
    assert red.escalados == [{"id": "ESC-0001", "ticket": "T-0001",
                              "resumen": ESCALADO["resumen"], "prioridad": "P1"}]
    ultimo = estado.traza[-1]
    assert (ultimo.agente, ultimo.herramienta) == ("escalado", "crear_escalado")
    assert ultimo.observacion["escalado"] == "ESC-0001"


def test_escalado_no_duplica_si_el_agente_lo_creo(estado, h, red):
    modelo = ScriptedModel([
        llamada("crear_escalado", ticket="T-0001", resumen="VPN caída", prioridad="P1"),
        j(ESCALADO),
    ])
    salida = agentes.escalado(estado, modelo, h)
    assert salida.datos["escalado"] == "ESC-0001"
    assert len(red.escalados) == 1


def test_escalado_con_ticket_inexistente_crea_sin_ticket(h, red):
    estado = Estado("x", "MAD-01", ticket="T-9999")
    salida = agentes.escalado(estado, ScriptedModel([j(ESCALADO)]), h)
    assert salida.datos["escalado"] == "ESC-0001"
    assert red.escalados[0]["ticket"] is None


# --- Criterio 12: mensajes enviados al modelo -----------------------------------

def test_mensajes_llevan_contexto_y_observaciones(estado, h):
    estado.tipo, estado.prioridad = "red", "P1"
    estado.causa, estado.servicio = "VPN de MAD-01 caída", "vpn"
    modelo = ScriptedModel([llamada("buscar_docs", consulta="vpn caída"), j(PROCEDIMIENTO_VPN)])
    agentes.conocimiento(estado, modelo, h)
    primero = json.loads(modelo.llamadas[0]["mensajes"][0]["content"])
    assert primero["incidencia"] == "no tengo internet"
    assert primero["oficina"] == "MAD-01" and primero["ticket"] == "T-0001"
    assert primero["averiguado"] == {"tipo": "red", "prioridad": "P1",
                                     "causa": "VPN de MAD-01 caída", "servicio": "vpn"}
    segunda = modelo.llamadas[1]["mensajes"]
    assert [m["role"] for m in segunda] == ["user", "assistant", "user"]
    assert "kb-red-01.md" in segunda[-1]["content"]
    assert "conocimiento" in modelo.llamadas[0]["sistema"]


# --- Tras la prueba con el modelo real: formato exacto en el prompt --------------

@pytest.mark.parametrize("nombre", sorted(AGENTES))
def test_prompt_incluye_formato_exacto(nombre, h):
    prompt = prompt_sistema(AGENTES[nombre], h)
    assert AGENTES[nombre].formato and AGENTES[nombre].formato in prompt


def test_prompt_diagnostico_valores_y_listas(h):
    prompt = prompt_sistema(AGENTES["diagnostico"], h)
    assert all(s in prompt for s in SERVICIOS)
    assert '"evidencias": ["<texto>"' in prompt
    assert "consulta al menos una herramienta" in prompt


def test_prompt_clasificador_tipos_permitidos(h):
    prompt = prompt_sistema(AGENTES["clasificador"], h)
    assert "|".join(sorted(TIPOS)) in prompt


def test_descripcion_servicios_igual_que_el_catalogo():
    catalogo = (Path(__file__).resolve().parents[1] / "docs" / "catalogo-servicios.md"
                ).read_text(encoding="utf-8")
    assert set(agentes.DESCRIPCION_SERVICIOS) == SERVICIOS
    for servicio, descripcion in agentes.DESCRIPCION_SERVICIOS.items():
        assert f"| `{servicio}` | {descripcion} |" in catalogo


def test_prompt_conocimiento_busca_primero(h):
    assert "primer turno es SIEMPRE una llamada a buscar_docs" in prompt_sistema(
        AGENTES["conocimiento"], h)
