"""Pruebas del orquestador: traspaso, casos difíciles y reglas R1–R5."""

import json
from datetime import datetime

import pytest

from soporte_oficinas.estado import Accion, Estado, Paso
from soporte_oficinas.herramientas import Red
from soporte_oficinas.modelo import ScriptedModel
from soporte_oficinas.orquestador import (
    en_horario,
    guardarrail,
    orquestar,
    prioridad_minima,
    trayectoria,
)

LUNES_10 = datetime(2026, 10, 12, 10, 0)
SABADO_10 = datetime(2026, 10, 17, 10, 0)
CITA_VPN = "docs/kb-red-01.md#Pasos"


def j(datos: dict) -> str:
    return json.dumps(datos, ensure_ascii=False)


def llamada(herramienta: str, **argumentos) -> str:
    return j({"herramienta": herramienta, "argumentos": argumentos})


def clasificacion(tipo: str = "red", prioridad: str = "P1") -> str:
    return j({"tipo": tipo, "prioridad": prioridad, "motivo": "según los datos"})


def diagnostico(servicio: str | None, oficina: str = "MAD-01") -> list[str]:
    consulta = (llamada("consultar_servicio", servicio=servicio, oficina=oficina)
                if servicio else llamada("consultar_equipo", id_equipo="PC-VAL01-002"))
    return [consulta, j({"causa": f"fallo de {servicio or 'equipo'}", "servicio": servicio,
                         "evidencias": ["observado en la herramienta"]})]


def conocimiento(accion: dict | None = None, citas: list[str] | None = None,
                 consulta: str = "pasos vpn caída") -> list[str]:
    return [llamada("buscar_docs", consulta=consulta, k=5),
            j({"procedimiento": "Seguir los pasos del artículo.",
               "citas": [CITA_VPN] if citas is None else citas, "accion": accion})]


def reinicio(servicio: str = "vpn", oficina: str = "MAD-01") -> dict:
    return {"herramienta": "reiniciar_servicio",
            "argumentos": {"servicio": servicio, "oficina": oficina}}


def escalado(prioridad: str = "P1") -> list[str]:
    return [j({"resumen": "no resuelto en primer nivel", "probado": ["diagnóstico"],
               "prioridad": prioridad})]


class Confirmar:
    """confirmar() inyectable que recuerda las acciones que se le preguntan."""

    def __init__(self, respuesta: bool | None) -> None:
        self.respuesta = respuesta
        self.preguntas: list[Accion] = []

    def __call__(self, accion: Accion) -> bool:
        if self.respuesta is None:
            raise AssertionError(f"no debía preguntarse: {accion}")
        self.preguntas.append(accion)
        return self.respuesta


@pytest.fixture
def red() -> Red:
    return Red.desde_directorio()


def correr(guion: list[str], red: Red, confirmar=None, oficina: str = "MAD-01",
           ticket: str | None = None, ahora: datetime = LUNES_10,
           incidencia: str = "no tengo internet", **opciones):
    modelo = ScriptedModel(guion)
    resultado = orquestar(incidencia, oficina, modelo, confirmar or Confirmar(None),
                          ahora=lambda: ahora, ticket=ticket, red=red, **opciones)
    return resultado, modelo


def ejecutadas(resultado, herramienta: str) -> list[Paso]:
    return [p for p in resultado.traza if p.herramienta == herramienta]


def notas(resultado) -> str:
    return " | ".join(str(p.observacion) for p in resultado.traza if p.agente == "orquestador")


# --- Criterio 1: resuelto con reinicio confirmado ----------------------------

def test_resuelto_con_reinicio(red):
    confirmar = Confirmar(True)
    guion = [clasificacion(), *diagnostico("vpn"), *conocimiento(reinicio())]
    resultado, _ = correr(guion, red, confirmar)
    assert resultado.final == "resuelto"
    assert (resultado.tipo, resultado.prioridad) == ("red", "P1")
    assert trayectoria(resultado.traza) == ["clasificador", "diagnostico", "conocimiento"]
    assert red.servicios["MAD-01"]["vpn"] == "ok"
    assert len(ejecutadas(resultado, "reiniciar_servicio")) == 1
    assert confirmar.preguntas == [Accion("reiniciar_servicio",
                                          {"servicio": "vpn", "oficina": "MAD-01"})]
    assert CITA_VPN in resultado.respuesta and resultado.citas == [CITA_VPN]
    assert resultado.escalado is None


# --- Criterio 2 / R1: confirmación rechazada ----------------------------------

def test_r1_rechazo_no_ejecuta_y_escala(red):
    guion = [clasificacion(), *diagnostico("vpn"), *conocimiento(reinicio()), *escalado()]
    resultado, modelo = correr(guion, red, Confirmar(False))
    assert red.servicios["MAD-01"]["vpn"] == "caido"
    assert ejecutadas(resultado, "reiniciar_servicio") == []
    assert ejecutadas(resultado, "cerrar_ticket") == []
    assert trayectoria(resultado.traza)[-1] == "escalado"
    assert resultado.final == "escalado" and resultado.final != "rechazado"
    assert resultado.escalado == "ESC-0001"
    assert "rechazada por el usuario" in notas(resultado)
    # el agente escalado se entera del rechazo
    assert "rechazada por el usuario" in modelo.llamadas[-1]["mensajes"][0]["content"]


def test_r1_cerrar_ticket_tambien_exige_confirmacion(red):
    accion = {"herramienta": "cerrar_ticket",
              "argumentos": {"ticket": "T-0001", "resolucion": "VPN restablecida"}}
    guion = [clasificacion(), *diagnostico("vpn"), *conocimiento(accion), *escalado()]
    resultado, _ = correr(guion, red, Confirmar(False), ticket="T-0001")
    assert red.ticket("T-0001")["estado"] == "abierto"
    assert ejecutadas(resultado, "cerrar_ticket") == []
    assert resultado.final == "escalado"


# --- Criterio 3 / R2: guardarraíl ---------------------------------------------

@pytest.mark.parametrize("diagnosticado, accion, motivo", [
    ("vpn", reinicio("erp"), "servicio diagnosticado"),
    ("correo", reinicio("correo"), "está ok"),
    ("vpn", reinicio("vpn", "MAD-02"), "oficina"),
])
def test_r2_bloquea_sin_preguntar(red, diagnosticado, accion, motivo):
    guion = [clasificacion(), *diagnostico(diagnosticado), *conocimiento(accion), *escalado()]
    resultado, _ = correr(guion, red, Confirmar(None))  # falla si se pregunta
    assert resultado.final == "escalado"
    assert ejecutadas(resultado, "reiniciar_servicio") == []
    assert "guardarraíl" in notas(resultado) and motivo in notas(resultado)
    assert red.servicios["MAD-01"]["erp"] == "ok"


def test_r2_fuera_de_horario_si_pregunta(red):
    confirmar = Confirmar(False)
    guion = [clasificacion(), *diagnostico("vpn"), *conocimiento(reinicio("erp")), *escalado()]
    correr(guion, red, confirmar, ahora=SABADO_10)
    assert confirmar.preguntas == [Accion("reiniciar_servicio",
                                          {"servicio": "erp", "oficina": "MAD-01"})]


def test_r2_no_critico_en_horario_si_pregunta(red):
    confirmar = Confirmar(True)
    guion = [clasificacion("impresora", "P4"), *diagnostico("impresion", "MAD-02"),
             *conocimiento(reinicio("impresion", "MAD-02"),
                           citas=["docs/kb-impresora-02.md#Pasos"],
                           consulta="ninguna impresora imprime servicio de impresión")]
    resultado, _ = correr(guion, red, confirmar, oficina="MAD-02",
                          incidencia="ninguna impresora imprime")
    assert resultado.final == "resuelto"
    assert red.servicios["MAD-02"]["impresion"] == "ok"


def test_r2_maximo_un_reinicio_por_servicio(red):
    estado = Estado("x", "MAD-01", servicio="vpn")
    accion = Accion("reiniciar_servicio", {"servicio": "vpn", "oficina": "MAD-01"})
    assert guardarrail(accion, estado, red, LUNES_10) is None
    estado.traza.append(Paso(1, "conocimiento", "reiniciar_servicio",
                             {"servicio": "vpn", "oficina": "MAD-01"}, {"estado": "ok"}))
    assert "máximo 1" in guardarrail(accion, estado, red, SABADO_10)


def test_r2_cerrar_otro_ticket_bloqueado(red):
    estado = Estado("x", "MAD-01", ticket="T-0001")
    accion = Accion("cerrar_ticket", {"ticket": "T-0009", "resolucion": "x"})
    assert guardarrail(accion, estado, red, LUNES_10) is not None


# --- Criterio 4 / R3: tope de pasos -------------------------------------------

def test_r3_tope(red):
    resultado, _ = correr([llamada("buscar_tickets")] * 30, red)
    assert resultado.final == "tope_alcanzado"
    contados = [p for p in resultado.traza if p.agente != "orquestador"]
    assert len(contados) == 12


def test_r3_anotaciones_no_cuentan(red):
    # P3 con vpn caída → anotación de subida; conocimiento solo busca hasta el tope
    guion = [clasificacion(prioridad="P3"), *diagnostico("vpn")] + [
        llamada("buscar_docs", consulta="vpn")] * 30
    resultado, _ = correr(guion, red)
    assert resultado.final == "tope_alcanzado"
    contados = [p for p in resultado.traza if p.agente != "orquestador"]
    assert len(contados) == 12
    assert len(resultado.traza) > 12


def test_r3_tope_antes_de_ejecutar_la_accion(red):
    # clasificador (1) + diagnostico (3) + conocimiento (3) = 7: ejecutar sería el 8.º
    guion = [clasificacion(), *diagnostico("vpn"), *conocimiento(reinicio())]
    resultado, _ = correr(guion, red, Confirmar(None), max_pasos=7)
    assert resultado.final == "tope_alcanzado"
    assert red.servicios["MAD-01"]["vpn"] == "caido"
    assert len([p for p in resultado.traza if p.agente != "orquestador"]) == 7


def test_r3_max_pasos_configurable(red):
    resultado, _ = correr([llamada("buscar_tickets")] * 30, red, max_pasos=4)
    assert resultado.final == "tope_alcanzado"
    assert len(resultado.traza) == 4


# --- Criterio 5 / R4: ilegibles ------------------------------------------------

def test_r4_clasificador_ilegible_escala(red):
    resultado, _ = correr(["no sé", "sigo sin saber", *escalado("P3")], red)
    assert resultado.final == "escalado"
    assert trayectoria(resultado.traza) == ["clasificador", "escalado"]
    assert resultado.escalado == "ESC-0001"


def test_r4_escalado_ilegible_crea_igualmente(red):
    resultado, _ = correr(["no sé", "sigo sin saber", "nada", "tampoco"], red)
    assert resultado.final == "escalado"
    assert resultado.escalado == "ESC-0001"
    assert red.escalados[0]["prioridad"] == "P3"
    assert "no tengo internet" in red.escalados[0]["resumen"]


def test_r4_error_de_herramienta_no_para(red):
    guion = [clasificacion(), llamada("consultar_servicio", servicio="vpn", oficina="XXX"),
             *diagnostico("vpn"), *conocimiento(reinicio())]
    resultado, _ = correr(guion, red, Confirmar(True))
    assert resultado.final == "resuelto"
    assert any(isinstance(p.observacion, dict) and "error" in p.observacion
               for p in resultado.traza)


# --- Criterio 6 / R5: citas comprobadas ---------------------------------------

def test_r5_cita_inventada_unica_escala(red):
    guion = [clasificacion(), *diagnostico("vpn"),
             j({"procedimiento": "Reinicia el router.",
                "citas": ["docs/kb-red-01.md#Pasos"], "accion": None}),  # sin buscar_docs
             *escalado()]
    resultado, _ = correr(guion, red)
    assert resultado.final == "escalado"
    assert resultado.citas == []
    assert "citas eliminadas" in notas(resultado)


def test_r5_elimina_solo_las_inventadas(red):
    citas = [CITA_VPN, "docs/kb-correo-02.md#Pasos", "docs/no-existe.md#X"]
    guion = [clasificacion(), *diagnostico("vpn"), *conocimiento(citas=citas)]
    resultado, _ = correr(guion, red)
    assert resultado.final == "resuelto"
    assert resultado.citas == [CITA_VPN]
    assert "kb-correo-02" not in resultado.respuesta
    assert "no-existe" in notas(resultado)


def test_r5_sin_procedimiento_escala(red):
    guion = [clasificacion(), *diagnostico("vpn"), llamada("buscar_docs", consulta="vpn"),
             j({"procedimiento": None, "citas": [], "accion": None}), *escalado()]
    resultado, _ = correr(guion, red)
    assert resultado.final == "escalado"


# --- Criterio 7: prioridad -----------------------------------------------------

def test_prioridad_se_sube_y_se_anota(red):
    guion = [clasificacion(prioridad="P3"), *diagnostico("vpn"), *conocimiento()]
    resultado, _ = correr(guion, red)
    assert resultado.prioridad == "P1"
    assert "prioridad subida de P3 a P1" in notas(resultado)


def test_prioridad_nunca_se_baja(red):
    guion = [clasificacion("correo", "P1"), *diagnostico("correo", "BCN-01"),
             *conocimiento(citas=["docs/kb-correo-01.md#Pasos"],
                           consulta="correo tarda servicio degradado")]
    resultado, _ = correr(guion, red, oficina="BCN-01")
    assert resultado.prioridad == "P1"
    assert "prioridad subida" not in notas(resultado)


@pytest.mark.parametrize("oficina, servicio, esperada", [
    ("MAD-01", "vpn", "P1"),          # crítico caído
    ("BCN-01", "correo", "P2"),       # crítico degradado
    ("MAD-02", "erp", "P1"),          # multioficina
    ("MAD-02", "impresion", None),    # no crítico, una oficina
    ("VAL-01", None, None),           # avería de equipo
])
def test_prioridad_minima(red, oficina, servicio, esperada):
    assert prioridad_minima(red, oficina, servicio) == esperada


# --- Criterio 8: mismo síntoma, causa distinta ---------------------------------

def test_mismo_sintoma_causa_de_equipo(red):
    guion = [clasificacion(prioridad="P3"), *diagnostico(None, "VAL-01"),
             *conocimiento(citas=["docs/kb-red-02.md#Pasos"], consulta="tarjeta de red averiada")]
    resultado, _ = correr(guion, red, Confirmar(None), oficina="VAL-01", ticket="T-0002")
    assert resultado.final == "resuelto"
    assert resultado.prioridad == "P3"
    assert "prioridad subida" not in notas(resultado)
    assert ejecutadas(resultado, "reiniciar_servicio") == []
    assert "kb-red-02.md#Pasos" in resultado.respuesta


# --- Criterio 9: ticket reabierto ----------------------------------------------

def test_ticket_reabierto_escala_tras_diagnostico(red):
    guion = [clasificacion("impresora", "P4"), *diagnostico("impresion", "MAD-02"),
             *escalado("P4")]
    resultado, _ = correr(guion, red, oficina="MAD-02", ticket="T-0007",
                          incidencia="la impresora no imprime")
    assert trayectoria(resultado.traza) == ["clasificador", "diagnostico", "escalado"]
    assert resultado.final == "escalado"
    assert "reabierto" in notas(resultado)
    assert red.escalados[0]["ticket"] == "T-0007"


# --- Criterio 10: multioficina ---------------------------------------------------

def test_multioficina_escala_con_p1(red):
    guion = [clasificacion("acceso_aplicacion", "P2"), *diagnostico("erp", "MAD-02"),
             *escalado("P2")]  # el agente escalado propone P2
    resultado, _ = correr(guion, red, oficina="MAD-02", ticket="T-0004",
                          incidencia="no puedo entrar en el ERP")
    assert trayectoria(resultado.traza) == ["clasificador", "diagnostico", "escalado"]
    assert resultado.final == "escalado"
    assert resultado.prioridad == "P1"
    assert red.escalados[0]["prioridad"] == "P1"
    assert "multioficina" in notas(resultado)
    assert "15 minutos" in resultado.respuesta


# --- Criterio 11: rechazado -------------------------------------------------------

@pytest.mark.parametrize("oficina, ticket", [("SEV-01", None), ("MAD-01", "T-9999")])
def test_entrada_no_valida_rechazada_sin_modelo(red, oficina, ticket):
    resultado, modelo = correr([], red, oficina=oficina, ticket=ticket)
    assert resultado.final == "rechazado"
    assert modelo.llamadas == []
    assert "no existe" in resultado.respuesta


def test_fuera_de_ambito_rechazado(red):
    resultado, _ = correr([clasificacion("fuera_de_ambito", "P4")], red,
                          incidencia="¿Me recomiendas un restaurante?")
    assert resultado.final == "rechazado"
    assert trayectoria(resultado.traza) == ["clasificador"]
    assert resultado.escalado is None and red.escalados == []


def test_rechazo_sin_prioridad(red):
    """Hito 7b, D1: lo que no se tramita no tiene prioridad."""
    resultado, _ = correr([clasificacion("fuera_de_ambito", "P4")], red,
                          incidencia="¿Me recomiendas un restaurante?")
    assert resultado.tipo == "fuera_de_ambito" and resultado.prioridad is None


# --- Criterio 12: horario laboral --------------------------------------------------

@pytest.mark.parametrize("momento, esperado", [
    (datetime(2026, 10, 16, 17, 59), True),   # viernes
    (datetime(2026, 10, 16, 18, 0), False),   # viernes 18:00
    (SABADO_10, False),
    (datetime(2026, 10, 12, 8, 0), True),     # lunes 08:00
    (datetime(2026, 10, 12, 7, 59), False),
])
def test_en_horario(momento, esperado):
    assert en_horario(momento) is esperado
