"""Lógica de la página web, sin Streamlit: app.py solo muestra lo que devuelve.

La web no decide nada: llama a orquestar(). Para que `confirmar` sea un botón,
la ejecución corre en segundo plano y espera a que la persona pulse un botón,
como la terminal con [s/N].
"""

import json
import os
import threading
import urllib.request
from dataclasses import dataclass

from soporte_oficinas.estado import Accion, Paso, Resultado
from soporte_oficinas.herramientas import Red
from soporte_oficinas.modelo import (OLLAMA_URL_POR_DEFECTO, Modelo, ModeloOllama,
                                     ModeloSimulado)
from soporte_oficinas.orquestador import TIEMPOS_RESPUESTA, orquestar, trayectoria

OFICINAS = ("MAD-01", "MAD-02", "BCN-01", "VAL-01")
SIMULADO = "simulado"


@dataclass(frozen=True)
class Ejemplo:
    titulo: str
    incidencia: str
    oficina: str
    ticket: str = ""


EJEMPLOS = (
    Ejemplo("Pide confirmación", "no tengo internet", "MAD-01", "T-0001"),
    Ejemplo("Mismo síntoma, otra causa", "no tengo internet", "VAL-01", "T-0002"),
    Ejemplo("Avería en varias oficinas", "no puedo entrar en el ERP", "MAD-02", "T-0004"),
    Ejemplo("Ticket reabierto", "la impresora no imprime", "MAD-02", "T-0007"),
    Ejemplo("Equipo lento", "me va lento el ordenador", "MAD-01"),
    Ejemplo("Fuera de ámbito", "¿me recomiendas un restaurante?", "MAD-01"),
)


# --- Modelos ------------------------------------------------------------------

def modelos_ollama(url: str | None = None, espera: float = 1.0) -> list[str]:
    """Modelos instalados en Ollama, o [] si Ollama no está funcionando en este equipo."""
    base = (url or os.environ.get("OLLAMA_URL") or OLLAMA_URL_POR_DEFECTO).removesuffix("/v1")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=espera) as respuesta:
            return sorted(m["name"] for m in json.load(respuesta).get("models", []))
    except (OSError, ValueError, KeyError):
        return []


def crear_modelo(nombre: str) -> Modelo:
    """'simulado' o el nombre de un modelo de Ollama."""
    return ModeloSimulado() if nombre == SIMULADO else ModeloOllama(modelo=nombre)


# --- Ejecución que se para a preguntar ------------------------------------------

class Ejecucion:
    """Una ejecución de orquestar() en segundo plano que espera al botón de confirmar.

    Es una sola ejecución, como la terminal con [s/N]: el agente que pregunta es el
    mismo que recibe la respuesta. Repetirla no sirve con un modelo real, que puede
    responder distinto la segunda vez.
    """

    def __init__(self, incidencia: str, oficina: str, ticket: str = "",
                 modelo: Modelo | None = None) -> None:
        self.pendiente: Accion | None = None
        self.respuesta: bool | None = None
        self.resultado: Resultado | None = None
        self.error: Exception | None = None
        self._parada = threading.Event()        # terminó o está preguntando
        self._respondida = threading.Event()
        argumentos = (incidencia.strip(), oficina, modelo or ModeloSimulado(),
                      ticket.strip() or None)
        threading.Thread(target=self._correr, args=argumentos, daemon=True).start()

    def _correr(self, incidencia: str, oficina: str, modelo: Modelo,
                ticket: str | None) -> None:
        try:
            self.resultado = orquestar(incidencia, oficina, modelo, self._confirmar,
                                       ticket=ticket)
        except Exception as error:  # el modelo real no responde, por ejemplo
            self.error = error
        finally:
            self._parada.set()

    def _confirmar(self, accion: Accion) -> bool:
        self.pendiente = accion
        self._parada.set()
        self._respondida.wait()
        return bool(self.respuesta)

    def esperar(self, segundos: float | None = None) -> None:
        """Hasta que termine o pregunte."""
        self._parada.wait(segundos)

    def responder(self, si: bool) -> None:
        """La respuesta de la persona a la acción pendiente (R1); sin pregunta, no hace nada."""
        if self.pendiente is None:
            return
        self.respuesta, self.pendiente = si, None
        self._parada.clear()
        self._respondida.set()


# --- Presentación ---------------------------------------------------------------

def describir_accion(accion: Accion) -> str:
    argumentos = ", ".join(f"{k}={v}" for k, v in accion.argumentos.items())
    return f"{accion.herramienta}({argumentos})"


def trayectoria_texto(resultado: Resultado) -> str:
    agentes = trayectoria(resultado.traza)
    return " → ".join(agentes) if agentes else "sin agentes"


AGENTES = ("clasificador", "diagnostico", "conocimiento", "escalado")

# Mismo texto que docs/guia-prioridades.md y mismos tiempos que el orquestador (lo comprueban
# las pruebas): la web solo los explica, no decide nada.
CRITERIO_PRIORIDAD = {
    "P1": "afecta a más de una oficina, o un servicio crítico está caído",
    "P2": "afecta a una oficina entera, o un servicio crítico está degradado",
    "P3": "un empleado no puede trabajar y no hay alternativa",
    "P4": "molestia con alternativa (otra impresora, webmail…)",
}
SIGNIFICADO_FINAL = {
    "resuelto": "el primer nivel lo ha resuelto con un procedimiento documentado y citado.",
    "escalado": "lo atiende un técnico de segundo nivel, que recibe un resumen de lo ya "
                "probado y el identificador del escalado.",
    "rechazado": "no se tramita: la entrada no es válida o no es una incidencia de soporte.",
    "tope_alcanzado": "se agotaron los pasos permitidos; un técnico revisará la incidencia.",
}


def explicar_prioridad(prioridad: str) -> str:
    return (f"{prioridad}: {CRITERIO_PRIORIDAD[prioridad]}. Primera respuesta en "
            f"{TIEMPOS_RESPUESTA[prioridad]}.")


def etapas(resultado: Resultado) -> list[tuple[str, bool]]:
    """Los cuatro agentes en orden y si actuaron en esta ejecución."""
    actuaron = set(trayectoria(resultado.traza))
    return [(agente, agente in actuaron) for agente in AGENTES]


def averias() -> dict[str, dict[str, str]]:
    """Servicios que no están ok, por oficina (estado inicial de data/)."""
    servicios = Red.desde_directorio().servicios
    return {o: {s: e for s, e in servicios[o].items() if e != "ok"} for o in OFICINAS}


def filas_traza(traza: list[Paso]) -> list[dict[str, str]]:
    """Una fila por paso, para mostrarla como tabla."""
    return [{"n": str(p.n), "agente": p.agente, "herramienta": p.herramienta or "—",
             "observación": str(p.observacion)[:300]} for p in traza]
