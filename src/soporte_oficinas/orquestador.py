"""Orquestación por traspaso y reglas R1–R5 garantizadas en código."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime

from soporte_oficinas import agentes
from soporte_oficinas.agentes import SalidaAgente
from soporte_oficinas.estado import Accion, Estado, Paso, Resultado
from soporte_oficinas.herramientas import (
    ErrorHerramienta,
    Herramienta,
    Red,
    crear_herramientas,
    ejecutar,
)
from soporte_oficinas.modelo import Modelo
from soporte_oficinas.recuperacion import IndiceBM25, cita

CRITICOS = frozenset({"vpn", "correo", "erp", "ficheros", "intranet"})
ORDEN_PRIORIDAD = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
TIEMPOS_RESPUESTA = {"P1": "15 minutos", "P2": "30 minutos",
                     "P3": "2 horas", "P4": "1 día laborable"}
PRIORIDAD_POR_DEFECTO = "P3"


@dataclass
class Contexto:
    """Lo que comparten los pasos del flujo en una ejecución."""

    estado: Estado
    modelo: Modelo
    herramientas: dict[str, Herramienta]
    red: Red
    max_pasos: int


# --- Utilidades ------------------------------------------------------------

def en_horario(momento: datetime) -> bool:
    """Lunes a viernes, de 08:00 a 18:00 (18:00 ya no es horario)."""
    return momento.weekday() < 5 and 8 <= momento.hour < 18


def anotar(estado: Estado, observacion: str) -> None:
    """Anotación del orquestador: queda en la traza pero no cuenta para el tope."""
    estado.traza.append(Paso(len(estado.traza) + 1, "orquestador", None, {}, observacion))


def trayectoria(traza: list[Paso]) -> list[str]:
    """Secuencia de agentes por los que ha pasado la ejecución (sin repetir seguidos)."""
    agentes_vistos: list[str] = []
    for paso in traza:
        if paso.agente != "orquestador" and agentes_vistos[-1:] != [paso.agente]:
            agentes_vistos.append(paso.agente)
    return agentes_vistos


def mas_urgente(a: str | None, b: str | None) -> str | None:
    """La prioridad más alta de las dos (P1 > P4); ignora valores no válidos."""
    validas = [p for p in (a, b) if p in ORDEN_PRIORIDAD]
    return min(validas, key=ORDEN_PRIORIDAD.__getitem__) if validas else a


# --- Prioridad y multioficina ---------------------------------------------

def oficinas_afectadas(red: Red, servicio: str | None) -> list[str]:
    """Oficinas donde el servicio no está ok."""
    if servicio is None:
        return []
    return [o for o, estados in red.servicios.items() if estados.get(servicio, "ok") != "ok"]


def prioridad_minima(red: Red, oficina: str, servicio: str | None) -> str | None:
    """Prioridad que exigen los datos para el servicio diagnosticado."""
    if len(oficinas_afectadas(red, servicio)) >= 2:
        return "P1"
    if servicio in CRITICOS:
        return {"caido": "P1", "degradado": "P2"}.get(red.servicios[oficina].get(servicio))
    return None


def subir_prioridad(estado: Estado, red: Red) -> None:
    """Sube (nunca baja) la prioridad a la mínima que exigen los datos y lo anota."""
    minima = prioridad_minima(red, estado.oficina, estado.servicio)
    if minima is None or mas_urgente(minima, estado.prioridad) == estado.prioridad:
        return
    anotar(estado, f"prioridad subida de {estado.prioridad} a {minima}: servicio "
                   f"{estado.servicio} afectado en {', '.join(oficinas_afectadas(red, estado.servicio))}")
    estado.prioridad = minima


# --- R5: citas comprobadas -------------------------------------------------

def citas_recuperadas(estado: Estado) -> set[str]:
    """Citas de los fragmentos que devolvió buscar_docs en esta ejecución."""
    return {
        cita(fragmento)
        for paso in estado.traza
        if paso.herramienta == "buscar_docs" and isinstance(paso.observacion, dict)
        for fragmento in paso.observacion.get("fragmentos", [])
    }


def comprobar_citas(estado: Estado) -> None:
    """Elimina (y anota) las citas que no se recuperaron en esta ejecución."""
    recuperadas = citas_recuperadas(estado)
    validas = [c for c in dict.fromkeys(estado.citas) if c in recuperadas]
    eliminadas = [c for c in estado.citas if c not in recuperadas]
    if eliminadas:
        anotar(estado, f"citas eliminadas por no haberse recuperado: {', '.join(eliminadas)}")
    estado.citas = validas


# --- R2: guardarraíl -------------------------------------------------------

def reinicios_hechos(estado: Estado, servicio: str) -> int:
    """Reinicios ejecutados con éxito de un servicio en esta ejecución."""
    return sum(
        1 for p in estado.traza
        if p.herramienta == "reiniciar_servicio" and p.argumentos.get("servicio") == servicio
        and not (isinstance(p.observacion, dict) and "error" in p.observacion)
    )


def _guardarrail_reinicio(argumentos: dict, estado: Estado, red: Red,
                          ahora: datetime) -> str | None:
    servicio, oficina = argumentos.get("servicio"), argumentos.get("oficina")
    if oficina != estado.oficina:
        return f"la oficina de la acción ({oficina}) no es la de la incidencia ({estado.oficina})"
    if reinicios_hechos(estado, servicio) >= 1:
        return f"ya se ha reiniciado {servicio} en esta ejecución (máximo 1)"
    if servicio in CRITICOS and en_horario(ahora):
        if servicio != estado.servicio:
            return (f"{servicio} es crítico y en horario laboral solo se reinicia el "
                    f"servicio diagnosticado ({estado.servicio})")
        actual = red.servicios.get(oficina, {}).get(servicio)
        if actual not in {"caido", "degradado"}:
            return f"{servicio} es crítico, está {actual} y es horario laboral"
    return None


def guardarrail(accion: Accion, estado: Estado, red: Red, ahora: datetime) -> str | None:
    """Motivo por el que se bloquea la acción sin preguntar, o None si puede confirmarse."""
    if accion.herramienta == "reiniciar_servicio":
        return _guardarrail_reinicio(accion.argumentos, estado, red, ahora)
    if accion.herramienta == "cerrar_ticket" and accion.argumentos.get("ticket") != estado.ticket:
        return "solo se puede cerrar el ticket de esta incidencia"
    return None


# --- Final de la ejecución -------------------------------------------------

def _redactar(estado: Estado, final: str, escalado: str | None, motivo: str | None) -> str:
    if final == "resuelto":
        return f"{estado.procedimiento}\n\nFuentes: {', '.join(estado.citas)}"
    if final == "escalado":
        return (f"Tu incidencia se ha escalado a segundo nivel con el identificador "
                f"{escalado} (prioridad {estado.prioridad}). Tiempo de primera respuesta: "
                f"{TIEMPOS_RESPUESTA.get(estado.prioridad, 'según el catálogo')}.")
    if final == "rechazado":
        return f"No se tramita la solicitud: {motivo}."
    return ("No se ha podido completar la atención automática en el número máximo de "
            "pasos. Un técnico revisará la incidencia.")


def terminar(ctx: Contexto, final: str, escalado: str | None = None,
             motivo: str | None = None) -> Resultado:
    """Fija el final y construye el Resultado."""
    estado = ctx.estado
    estado.final = final
    return Resultado(final=final, respuesta=_redactar(estado, final, escalado, motivo),
                     citas=list(estado.citas), traza=estado.traza, tipo=estado.tipo,
                     prioridad=estado.prioridad, escalado=escalado)


def _rechazar(ctx: Contexto, motivo: str) -> Resultado:
    """Lo que no se tramita no tiene prioridad (decisión D1 del hito 7b)."""
    ctx.estado.prioridad = None
    anotar(ctx.estado, f"rechazado: {motivo}")
    return terminar(ctx, "rechazado", motivo=motivo)


# --- Escalado --------------------------------------------------------------

def _herramientas_escalado(herramientas: dict[str, Herramienta],
                           minima: str | None) -> dict[str, Herramienta]:
    """crear_escalado nunca usa una prioridad menor que la del estado."""
    original = herramientas["crear_escalado"]

    def crear_escalado(ticket: str | None, resumen: str, prioridad: str) -> dict:
        return original.funcion(ticket=ticket, resumen=resumen,
                                prioridad=mas_urgente(prioridad, minima))

    return {**herramientas, "crear_escalado": replace(original, funcion=crear_escalado)}


def _resumen_automatico(estado: Estado) -> str:
    return (f"Incidencia en {estado.oficina}: {estado.incidencia}. "
            f"Causa probable: {estado.causa or 'sin diagnosticar'}.")


def escalar(ctx: Contexto) -> Resultado:
    """Agente escalado; si su respuesta es ilegible, el código crea el escalado igualmente."""
    estado = ctx.estado
    herramientas = _herramientas_escalado(ctx.herramientas, estado.prioridad)
    salida = agentes.escalado(estado, ctx.modelo, herramientas, ctx.max_pasos)
    if salida.motivo == "ok":
        id_escalado = salida.datos["escalado"]
    elif salida.motivo == "ilegible" and estado.pasos < ctx.max_pasos:
        anotar(estado, "respuesta del agente escalado ilegible: escalado automático")
        datos = {"resumen": _resumen_automatico(estado),
                 "prioridad": estado.prioridad or PRIORIDAD_POR_DEFECTO}
        id_escalado = agentes.asegurar_escalado(estado, datos, herramientas)
    else:
        return terminar(ctx, "tope_alcanzado")
    estado.prioridad = next(e["prioridad"] for e in ctx.red.escalados if e["id"] == id_escalado)
    return terminar(ctx, "escalado", escalado=id_escalado)


def _tras_agente(ctx: Contexto, salida: SalidaAgente, agente: str) -> Resultado | None:
    """tope → tope_alcanzado; ilegible → escalado (R4); ok → seguir."""
    if salida.motivo == "tope":
        return terminar(ctx, "tope_alcanzado")
    if salida.motivo == "ilegible":
        anotar(ctx.estado, f"2 respuestas ilegibles seguidas de {agente}: se escala")
        return escalar(ctx)
    return None


# --- Flujo -----------------------------------------------------------------

def _entrada_no_valida(red: Red, oficina: str, ticket: str | None) -> str | None:
    if oficina not in red.servicios:
        return f"la oficina {oficina} no existe"
    if ticket is not None and not any(t["id"] == ticket for t in red.tickets):
        return f"el ticket {ticket} no existe"
    return None


def _motivo_escalado_directo(ctx: Contexto) -> str | None:
    """Reglas de traspaso tras el diagnóstico: ticket reabierto o avería multioficina."""
    estado = ctx.estado
    if estado.ticket is not None:
        reaperturas = ctx.red.ticket(estado.ticket)["reaperturas"]
        if reaperturas >= 1:
            return f"el ticket {estado.ticket} se ha reabierto {reaperturas} vez/veces"
    afectadas = oficinas_afectadas(ctx.red, estado.servicio)
    if len(afectadas) >= 2:
        return f"avería multioficina de {estado.servicio}: {', '.join(afectadas)}"
    return None


def _ejecutar_accion(ctx: Contexto, accion: Accion) -> bool:
    """Ejecuta la acción confirmada; True si ha ido bien."""
    try:
        observacion = ejecutar(ctx.herramientas, accion.herramienta, accion.argumentos)
    except ErrorHerramienta as error:
        observacion = {"error": str(error)}
    agentes.registrar(ctx.estado, "conocimiento", accion.herramienta,
                      dict(accion.argumentos), observacion)
    return "error" not in observacion


def _tramitar_accion(ctx: Contexto, accion: Accion,
                     confirmar: Callable[[Accion], bool], ahora: datetime) -> Resultado:
    """R2 (guardarraíl) y R1 (confirmación) antes de ejecutar una irreversible."""
    estado = ctx.estado
    if estado.pasos >= ctx.max_pasos:
        return terminar(ctx, "tope_alcanzado")
    motivo = guardarrail(accion, estado, ctx.red, ahora)
    if motivo is not None:
        anotar(estado, f"acción {accion.herramienta} bloqueada por el guardarraíl: {motivo}")
        return escalar(ctx)
    if not confirmar(accion):
        anotar(estado, f"acción {accion.herramienta} rechazada por el usuario: no se ejecuta")
        return escalar(ctx)
    if not _ejecutar_accion(ctx, accion):
        anotar(estado, f"la acción {accion.herramienta} ha fallado: se escala")
        return escalar(ctx)
    return terminar(ctx, "resuelto")


def _flujo(ctx: Contexto, confirmar: Callable[[Accion], bool],
           ahora: Callable[[], datetime]) -> Resultado:
    estado, m, h, tope = ctx.estado, ctx.modelo, ctx.herramientas, ctx.max_pasos
    if fin := _tras_agente(ctx, agentes.clasificador(estado, m, h, tope), "clasificador"):
        return fin
    if estado.tipo == "fuera_de_ambito":
        return _rechazar(ctx, "la petición no es una incidencia de soporte de oficinas")
    if fin := _tras_agente(ctx, agentes.diagnostico(estado, m, h, tope), "diagnostico"):
        return fin
    subir_prioridad(estado, ctx.red)
    if motivo := _motivo_escalado_directo(ctx):
        anotar(estado, f"escalado directo: {motivo}")
        return escalar(ctx)
    if fin := _tras_agente(ctx, agentes.conocimiento(estado, m, h, tope), "conocimiento"):
        return fin
    comprobar_citas(estado)
    if not estado.procedimiento or not estado.citas:
        anotar(estado, "sin procedimiento con citas válidas: se escala")
        return escalar(ctx)
    if estado.acciones:
        return _tramitar_accion(ctx, estado.acciones[-1], confirmar, ahora())
    return terminar(ctx, "resuelto")


def orquestar(incidencia: str, oficina: str, modelo: Modelo,
              confirmar: Callable[[Accion], bool],
              ahora: Callable[[], datetime] = datetime.now,
              ticket: str | None = None, max_pasos: int = 12, *,
              red: Red | None = None, indice: IndiceBM25 | None = None) -> Resultado:
    """Atiende una incidencia: clasificador → diagnostico → conocimiento → fin | escalado."""
    if red is None:
        red = Red.desde_directorio()
    estado = Estado(incidencia, oficina, ticket)
    ctx = Contexto(estado, modelo, {}, red, max_pasos)
    if motivo := _entrada_no_valida(red, oficina, ticket):
        return _rechazar(ctx, motivo)
    ctx.herramientas = crear_herramientas(red, indice)
    return _flujo(ctx, confirmar, ahora)
