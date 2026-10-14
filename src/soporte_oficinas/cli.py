"""Orden soporte-oficinas: atiende una incidencia desde la terminal."""

import argparse
import json
import sys
from collections.abc import Callable

from soporte_oficinas.estado import Accion, Paso, Resultado
from soporte_oficinas.modelo import Modelo, ModeloHF, ModeloSimulado
from soporte_oficinas.orquestador import orquestar

RESPUESTAS_SI = {"s", "si", "sí"}
LARGO_OBSERVACION = 160


def _argumentos() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="soporte-oficinas",
        description="Soporte técnico de primer nivel para la red de oficinas.")
    parser.add_argument("incidencia", help="texto de la incidencia del empleado")
    parser.add_argument("--oficina", required=True, help="MAD-01, MAD-02, BCN-01 o VAL-01")
    parser.add_argument("--ticket", help="id del ticket, p. ej. T-0007")
    parser.add_argument("--modelo", choices=["simulado", "hf"], default="simulado",
                        help="simulado (sin token, por defecto) o hf (Hugging Face)")
    parser.add_argument("--traza", action="store_true", help="muestra los pasos")
    return parser


def confirmador(entrada: Callable[[str], str]) -> Callable[[Accion], bool]:
    """confirmar() que pregunta en la terminal; sin respuesta (EOF) es False."""
    def confirmar(accion: Accion) -> bool:
        argumentos = ", ".join(f"{k}={v}" for k, v in accion.argumentos.items())
        try:
            respuesta = entrada(f"¿Confirmas {accion.herramienta}({argumentos})? [s/N] ")
        except EOFError:
            return False
        return respuesta.strip().lower() in RESPUESTAS_SI
    return confirmar


def _paso(paso: Paso) -> str:
    accion = (f"{paso.herramienta}({json.dumps(paso.argumentos, ensure_ascii=False)})"
              if paso.herramienta else "respuesta" if paso.agente != "orquestador" else "nota")
    observacion = (paso.observacion if isinstance(paso.observacion, str)
                   else json.dumps(paso.observacion, ensure_ascii=False))
    if len(observacion) > LARGO_OBSERVACION:
        observacion = observacion[:LARGO_OBSERVACION] + "…"
    return f"  {paso.n:>2}. [{paso.agente}] {accion} -> {observacion}"


def formatear(resultado: Resultado, traza: bool = False) -> str:
    """Texto que se muestra al terminar."""
    lineas = [f"Final: {resultado.final}",
              f"Tipo: {resultado.tipo or '-'} · Prioridad: {resultado.prioridad or '-'}"]
    if resultado.escalado:
        lineas.append(f"Escalado: {resultado.escalado}")
    lineas += ["", "Respuesta al empleado:", resultado.respuesta]
    if traza:
        lineas += ["", "Traza:", *(_paso(p) for p in resultado.traza)]
    return "\n".join(lineas)


def _crear_modelo(nombre: str) -> Modelo:
    return ModeloHF() if nombre == "hf" else ModeloSimulado()


def main(argv: list[str] | None = None, entrada: Callable[[str], str] = input) -> int:
    """Punto de entrada de la orden soporte-oficinas."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    args = _argumentos().parse_args(argv)
    try:
        resultado = orquestar(args.incidencia, args.oficina, _crear_modelo(args.modelo),
                              confirmador(entrada), ticket=args.ticket)
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    print(formatear(resultado, args.traza))
    return 0
