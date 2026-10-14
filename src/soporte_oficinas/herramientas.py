"""Herramientas sobre el estado simulado de la red y su registro."""

import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

RUTA_DATOS = Path(__file__).resolve().parents[2] / "data"
PRIORIDADES = {"P1", "P2", "P3", "P4"}


class ErrorHerramienta(Exception):
    """Fallo de una herramienta; el orquestador lo anota como observación."""


@dataclass
class Red:
    """Estado simulado de la red. Los cambios solo se hacen en memoria."""

    servicios: dict[str, dict[str, str]]
    inventario: list[dict]
    tickets: list[dict]
    escalados: list[dict] = field(default_factory=list)

    @classmethod
    def desde_directorio(cls, ruta: Path = RUTA_DATOS) -> "Red":
        """Carga una copia nueva de servicios, inventario y tickets."""
        def cargar(nombre: str) -> Any:
            return json.loads((Path(ruta) / nombre).read_text(encoding="utf-8"))

        return cls(cargar("servicios.json"), cargar("inventario.json"),
                   cargar("tickets.json"))

    def estados_de(self, oficina: str) -> dict[str, str]:
        """Estados de los servicios de una oficina, o ErrorHerramienta."""
        _exigir_texto(oficina, "oficina")
        if oficina not in self.servicios:
            raise ErrorHerramienta(f"oficina desconocida: {oficina}")
        return self.servicios[oficina]

    def equipo(self, id_equipo: str) -> dict:
        """Ficha de un equipo del inventario, o ErrorHerramienta."""
        _exigir_texto(id_equipo, "id_equipo")
        for equipo in self.inventario:
            if equipo["id"] == id_equipo:
                return equipo
        raise ErrorHerramienta(f"equipo desconocido: {id_equipo}")

    def ticket(self, id_ticket: str) -> dict:
        """Ticket por id, o ErrorHerramienta."""
        _exigir_texto(id_ticket, "ticket")
        for ticket in self.tickets:
            if ticket["id"] == id_ticket:
                return ticket
        raise ErrorHerramienta(f"ticket desconocido: {id_ticket}")


@dataclass
class Herramienta:
    """Entrada del registro: qué hace, si es reversible y la función a llamar."""

    nombre: str
    descripcion: str
    reversible: bool
    funcion: Callable[..., dict]


def _exigir_texto(valor: Any, nombre: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorHerramienta(f"'{nombre}' debe ser un texto no vacío")
    return valor


def _estado_servicio(red: Red, servicio: str, oficina: str) -> dict[str, str]:
    estados = red.estados_de(oficina)
    _exigir_texto(servicio, "servicio")
    if servicio not in estados:
        raise ErrorHerramienta(f"servicio desconocido: {servicio}")
    return estados


def consultar_servicio(red: Red, servicio: str, oficina: str) -> dict:
    """Estado (ok|degradado|caido) de un servicio en una oficina."""
    estados = _estado_servicio(red, servicio, oficina)
    return {"servicio": servicio, "oficina": oficina, "estado": estados[servicio]}


def consultar_equipo(red: Red, id_equipo: str) -> dict:
    """Ficha del inventario de un equipo."""
    return dict(red.equipo(id_equipo))


def buscar_tickets(red: Red, oficina: str | None = None,
                   sintoma: str | None = None) -> dict:
    """Tickets que coinciden con la oficina y/o contienen el síntoma."""
    if oficina is not None:
        red.estados_de(oficina)
    if sintoma is not None:
        _exigir_texto(sintoma, "sintoma")
    encontrados = [
        dict(t) for t in red.tickets
        if (oficina is None or t["oficina"] == oficina)
        and (sintoma is None or sintoma.lower() in t["sintoma"].lower())
    ]
    return {"tickets": encontrados}


def crear_escalado(red: Red, ticket: str | None, resumen: str,
                   prioridad: str) -> dict:
    """Registra un escalado a segundo nivel y devuelve su id."""
    if ticket is not None:
        red.ticket(ticket)
    _exigir_texto(resumen, "resumen")
    if prioridad not in PRIORIDADES:
        raise ErrorHerramienta(f"prioridad no válida: {prioridad} (P1–P4)")
    id_escalado = f"ESC-{len(red.escalados) + 1:04d}"
    red.escalados.append({"id": id_escalado, "ticket": ticket,
                          "resumen": resumen, "prioridad": prioridad})
    return {"escalado": id_escalado, "ticket": ticket, "prioridad": prioridad}


def reiniciar_servicio(red: Red, servicio: str, oficina: str) -> dict:
    """Reinicia un servicio de una oficina: queda en estado ok."""
    estados = _estado_servicio(red, servicio, oficina)
    anterior = estados[servicio]
    estados[servicio] = "ok"
    return {"servicio": servicio, "oficina": oficina,
            "estado_anterior": anterior, "estado": "ok"}


def cerrar_ticket(red: Red, ticket: str, resolucion: str) -> dict:
    """Cierra un ticket abierto o reabierto guardando la resolución."""
    datos = red.ticket(ticket)
    _exigir_texto(resolucion, "resolucion")
    if datos["estado"] == "cerrado":
        raise ErrorHerramienta(f"el ticket {ticket} ya está cerrado")
    datos["estado"] = "cerrado"
    datos["resolucion"] = resolucion
    return {"ticket": ticket, "estado": "cerrado", "resolucion": resolucion}


_CATALOGO: list[tuple[Callable[..., dict], str, bool]] = [
    (consultar_servicio, "Estado ok|degradado|caido de un servicio en una oficina.", True),
    (consultar_equipo, "Ficha del inventario (tipo, oficina, modelo, estado) de un equipo.", True),
    (buscar_tickets, "Tickets filtrados por oficina y/o por texto del síntoma.", True),
    (crear_escalado, "Crea un escalado a segundo nivel con resumen y prioridad P1–P4.", True),
    (reiniciar_servicio, "Reinicia un servicio de una oficina. IRREVERSIBLE.", False),
    (cerrar_ticket, "Cierra un ticket con su resolución. IRREVERSIBLE.", False),
]


def crear_herramientas(red: Red) -> dict[str, Herramienta]:
    """Registro de herramientas atadas a una red concreta."""
    return {
        f.__name__: Herramienta(f.__name__, descripcion, reversible, partial(f, red))
        for f, descripcion, reversible in _CATALOGO
    }


def ejecutar(herramientas: dict[str, Herramienta], nombre: str,
             argumentos: dict[str, Any]) -> dict:
    """Único punto de llamada: todo fallo de uso se convierte en ErrorHerramienta."""
    herramienta = herramientas.get(nombre) if isinstance(nombre, str) else None
    if herramienta is None:
        raise ErrorHerramienta(f"herramienta desconocida: {nombre}")
    if not isinstance(argumentos, dict):
        raise ErrorHerramienta(f"los argumentos de {nombre} deben ser un objeto")
    try:
        inspect.signature(herramienta.funcion).bind(**argumentos)
    except TypeError as error:
        raise ErrorHerramienta(f"argumentos no válidos para {nombre}: {error}") from None
    return herramienta.funcion(**argumentos)
