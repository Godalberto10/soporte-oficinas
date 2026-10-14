"""Estado compartido entre agentes y resultado de una ejecución."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Paso:
    """Un paso de la traza: una respuesta del modelo o una llamada a herramienta."""

    n: int
    agente: str
    herramienta: str | None
    argumentos: dict[str, Any]
    observacion: Any


@dataclass
class Accion:
    """Llamada a una herramienta que un agente propone ejecutar."""

    herramienta: str
    argumentos: dict[str, Any] = field(default_factory=dict)


@dataclass
class Estado:
    """Lo averiguado hasta ahora; cada agente lo recibe y lo completa."""

    incidencia: str
    oficina: str
    ticket: str | None = None
    tipo: str | None = None
    prioridad: str | None = None
    causa: str | None = None
    servicio: str | None = None
    procedimiento: str | None = None
    citas: list[str] = field(default_factory=list)
    acciones: list[Accion] = field(default_factory=list)
    traza: list[Paso] = field(default_factory=list)
    pasos: int = 0
    final: str | None = None


@dataclass
class Resultado:
    """Salida de orquestar(): estado final, respuesta al empleado y traza."""

    final: str
    respuesta: str
    citas: list[str] = field(default_factory=list)
    traza: list[Paso] = field(default_factory=list)
    tipo: str | None = None
    prioridad: str | None = None
    escalado: str | None = None
