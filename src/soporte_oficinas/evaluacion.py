"""Evaluación: casos con resultado y trayectoria esperados (hito 7).

Lo esperado de cada caso lo define el autor del proyecto aplicando sus reglas,
sin mirar el código. El guion de cada caso solo hace de modelo.
"""

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime

from soporte_oficinas.estado import Accion, Resultado
from soporte_oficinas.herramientas import Red
from soporte_oficinas.modelo import Modelo, ModeloSimulado, ScriptedModel
from soporte_oficinas.orquestador import orquestar, trayectoria

LUNES_10 = datetime(2026, 10, 12, 10, 0)
SIGLAS = {"clasificador": "C", "diagnostico": "D", "conocimiento": "K", "escalado": "E"}
COLUMNAS = ("final", "tipo", "prioridad", "trayectoria")


# --- Piezas de guion (respuestas de un ScriptedModel) ----------------------

def _j(datos: dict) -> str:
    return json.dumps(datos, ensure_ascii=False)


def _llamada(herramienta: str, **argumentos) -> str:
    return _j({"herramienta": herramienta, "argumentos": argumentos})


def _clasificar(tipo: str, prioridad: str) -> str:
    return _j({"tipo": tipo, "prioridad": prioridad, "motivo": "según la incidencia"})


def _diagnosticar(servicio: str | None, oficina: str, causa: str) -> list[str]:
    consulta = (_llamada("consultar_servicio", servicio=servicio, oficina=oficina)
                if servicio else _llamada("consultar_equipo", id_equipo="PC-VAL01-002"))
    return [consulta, _j({"causa": causa, "servicio": servicio,
                          "evidencias": ["observado con la herramienta"]})]


def _resolver(consulta: str, cita: str, accion: dict | None = None) -> list[str]:
    return [_llamada("buscar_docs", consulta=consulta, k=5),
            _j({"procedimiento": "Seguir los pasos del artículo citado.",
                "citas": [cita], "accion": accion})]


def _reinicio(servicio: str, oficina: str) -> dict:
    return {"herramienta": "reiniciar_servicio",
            "argumentos": {"servicio": servicio, "oficina": oficina}}


def _escalar(prioridad: str) -> list[str]:
    return [_j({"resumen": "no resuelto en primer nivel", "probado": ["diagnóstico"],
                "prioridad": prioridad})]


# --- Casos -------------------------------------------------------------------

@dataclass(frozen=True)
class Esperado:
    final: str
    tipo: str | None
    prioridad: str | None
    trayectoria: str


@dataclass(frozen=True)
class Caso:
    n: int
    nombre: str
    incidencia: str
    oficina: str
    ticket: str | None
    confirmar: bool
    guion: tuple[str, ...]
    esperado: Esperado
    simulado: bool = True  # entra también en la pasada con ModeloSimulado


INTERNET = "no tengo internet"
_VPN_MAD01 = (_clasificar("red", "P3"),
              *_diagnosticar("vpn", "MAD-01", "vpn caída en MAD-01"))

CASOS: tuple[Caso, ...] = (
    Caso(1, "internet MAD-01, confirma", INTERNET, "MAD-01", "T-0001", True,
         (*_VPN_MAD01, *_resolver("vpn caída", "docs/kb-red-01.md#Pasos",
                                  _reinicio("vpn", "MAD-01"))),
         Esperado("resuelto", "red", "P1", "C-D-K")),
    Caso(2, "internet MAD-01, rechaza", INTERNET, "MAD-01", "T-0001", False,
         (*_VPN_MAD01, *_resolver("vpn caída", "docs/kb-red-01.md#Pasos",
                                  _reinicio("vpn", "MAD-01")), *_escalar("P1")),
         Esperado("escalado", "red", "P1", "C-D-K-E")),
    Caso(3, "internet VAL-01, tarjeta rota", INTERNET, "VAL-01", "T-0002", False,
         (_clasificar("red", "P3"),
          *_diagnosticar(None, "VAL-01", "tarjeta de red averiada en PC-VAL01-002"),
          *_resolver("tarjeta de red averiada cable", "docs/kb-red-02.md#Pasos")),
         Esperado("resuelto", "red", "P3", "C-D-K")),
    Caso(4, "impresora MAD-02, reabierto", "la impresora no imprime", "MAD-02",
         "T-0007", False,
         (_clasificar("impresora", "P4"),
          *_diagnosticar("impresion", "MAD-02", "impresión degradada"), *_escalar("P4")),
         Esperado("escalado", "impresora", "P4", "C-D-E")),
    Caso(5, "ERP MAD-02, varias oficinas", "no puedo entrar en el ERP", "MAD-02",
         "T-0004", False,
         (_clasificar("acceso_aplicacion", "P2"),
          *_diagnosticar("erp", "MAD-02", "erp caído"), *_escalar("P2")),
         Esperado("escalado", "acceso_aplicacion", "P1", "C-D-E")),
    Caso(6, "correo BCN-01, modelo dice P4", "el correo tarda mucho en llegar",
         "BCN-01", "T-0006", True,
         (_clasificar("correo", "P4"),
          *_diagnosticar("correo", "BCN-01", "correo degradado en BCN-01"),
          *_resolver("correo tarda en llegar servicio degradado",
                     "docs/kb-correo-01.md#Pasos", _reinicio("correo", "BCN-01"))),
         Esperado("resuelto", "correo", "P2", "C-D-K")),
    Caso(7, "restaurante", "¿me recomiendas un restaurante?", "MAD-01", None, False,
         (_clasificar("fuera_de_ambito", "P4"),),
         Esperado("rechazado", "fuera_de_ambito", None, "C")),
    Caso(8, "oficina inexistente", INTERNET, "SEV-01", None, False, (),
         Esperado("rechazado", None, None, "")),
    Caso(9, "cita inventada", INTERNET, "MAD-01", None, False,
         (*_VPN_MAD01, *_resolver("vpn caída", "docs/kb-red-07.md#Pasos"),
          *_escalar("P1")),
         Esperado("escalado", "red", "P1", "C-D-K-E"), simulado=False),
    Caso(10, "propone reiniciar el ERP", INTERNET, "MAD-01", None, False,
         (*_VPN_MAD01, *_resolver("vpn caída", "docs/kb-red-01.md#Pasos",
                                  _reinicio("erp", "MAD-01")), *_escalar("P1")),
         Esperado("escalado", "red", "P1", "C-D-K-E"), simulado=False),
    Caso(11, "ordenador lento", "me va lento el ordenador", "MAD-01", None, False,
         (_clasificar("hardware", "P4"),
          _j({"causa": "equipo lento", "servicio": None,
              "evidencias": ["ningún servicio afectado"]}),
          *_resolver("equipo lento reiniciar", "docs/kb-hardware-03.md#Pasos"),
          *_escalar("P4")),
         Esperado("resuelto", "hardware", "P4", "C-D-K")),
)


# --- Ejecutar y comparar ----------------------------------------------------

class ModeloContado:
    """Envuelve un modelo y cuenta cuántas veces se le llama."""

    def __init__(self, modelo: Modelo) -> None:
        self.modelo = modelo
        self.llamadas = 0

    def generar(self, sistema: str, mensajes: list[dict]) -> str:
        self.llamadas += 1
        return self.modelo.generar(sistema, mensajes)


@dataclass
class Evaluacion:
    caso: Caso
    resultado: Resultado
    red: Red
    llamadas_modelo: int
    preguntas: list[Accion] = field(default_factory=list)

    def obtenido(self) -> Esperado:
        siglas = "-".join(SIGLAS[a] for a in trayectoria(self.resultado.traza))
        return Esperado(self.resultado.final, self.resultado.tipo,
                        self.resultado.prioridad, siglas)

    def aciertos(self) -> dict[str, bool]:
        obtenido = self.obtenido()
        return {c: getattr(obtenido, c) == getattr(self.caso.esperado, c) for c in COLUMNAS}


def evaluar(caso: Caso, modelo: Modelo | None = None) -> Evaluacion:
    """Ejecuta un caso con una Red nueva; sin modelo, usa el guion del caso."""
    red = Red.desde_directorio()
    contado = ModeloContado(modelo or ScriptedModel(list(caso.guion)))
    preguntas: list[Accion] = []

    def confirmar(accion: Accion) -> bool:
        preguntas.append(accion)
        return caso.confirmar

    resultado = orquestar(caso.incidencia, caso.oficina, contado, confirmar,
                          ahora=lambda: LUNES_10, ticket=caso.ticket, red=red)
    return Evaluacion(caso, resultado, red, contado.llamadas, preguntas)


# --- Tabla para el informe ----------------------------------------------------

def _celda(esperado: str | None, obtenido: str | None) -> str:
    texto = esperado or "—"
    return texto if esperado == obtenido else f"{texto} ✘ ({obtenido or '—'})"


def tabla(evaluaciones: list[Evaluacion]) -> str:
    """Tabla Markdown: esperado por columna, con ✘ (obtenido) si no coincide."""
    filas = ["| # | Caso | Final | Tipo | Prioridad | Trayectoria |",
             "|---|---|---|---|---|---|"]
    for ev in evaluaciones:
        esp, obt = ev.caso.esperado, ev.obtenido()
        celdas = [_celda(getattr(esp, c), getattr(obt, c)) for c in COLUMNAS]
        filas.append(f"| {ev.caso.n} | {ev.caso.nombre} | " + " | ".join(celdas) + " |")
    totales = [sum(ev.aciertos()[c] for ev in evaluaciones) for c in COLUMNAS]
    filas.append(f"| | **Aciertos** | " + " | ".join(
        f"{t}/{len(evaluaciones)}" for t in totales) + " |")
    return "\n".join(filas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluación con mis casos.")
    parser.add_argument("--modelo", choices=["guion", "simulado"], default="guion")
    args = parser.parse_args(argv)
    if args.modelo == "guion":
        evaluaciones = [evaluar(c) for c in CASOS]
    else:
        evaluaciones = [evaluar(c, ModeloSimulado()) for c in CASOS if c.simulado]
    print(tabla(evaluaciones))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
