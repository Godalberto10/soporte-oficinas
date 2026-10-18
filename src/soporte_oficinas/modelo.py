"""Contrato del modelo de lenguaje, modelo guionizado, simulado y Hugging Face."""

import json
import os
import re
from typing import Any, Protocol

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from soporte_oficinas.recuperacion import tokenizar

MODELO_POR_DEFECTO = "Qwen/Qwen2.5-72B-Instruct"
INTENTOS = 2


class Modelo(Protocol):
    """Cualquier modelo que, dado un prompt de sistema y mensajes, devuelve texto."""

    def generar(self, sistema: str, mensajes: list[dict]) -> str: ...


class ScriptedModel:
    """Devuelve respuestas fijadas de antemano, en orden. Solo para pruebas."""

    def __init__(self, respuestas: list[str]) -> None:
        self._respuestas = list(respuestas)
        self.llamadas: list[dict] = []

    def generar(self, sistema: str, mensajes: list[dict]) -> str:
        """Registra la llamada y devuelve la siguiente respuesta del guion."""
        self.llamadas.append({"sistema": sistema, "mensajes": list(mensajes)})
        if not self._respuestas:
            raise RuntimeError("ScriptedModel: no quedan respuestas en el guion")
        return self._respuestas.pop(0)


# --- Hugging Face ----------------------------------------------------------

class ModeloHF:
    """Modelo real vía huggingface_hub.InferenceClient (token en HF_TOKEN)."""

    def __init__(self, modelo: str | None = None, cliente: Any = None) -> None:
        load_dotenv()
        self.modelo = modelo or os.environ.get("HF_MODEL") or MODELO_POR_DEFECTO
        self._token = os.environ.get("HF_TOKEN")
        if cliente is None:
            if not self._token:
                raise RuntimeError("Falta HF_TOKEN: añádelo al fichero .env "
                                   "(HF_TOKEN=...) o usa --modelo simulado")
            cliente = InferenceClient(model=self.modelo, token=self._token)
        self._cliente = cliente

    def _sin_token(self, texto: str) -> str:
        return texto.replace(self._token, "***") if self._token else texto

    def generar(self, sistema: str, mensajes: list[dict]) -> str:
        """Una respuesta con temperature=0; reintenta una vez si el fallo es transitorio."""
        completos = [{"role": "system", "content": sistema}, *mensajes]
        for intento in range(1, INTENTOS + 1):
            try:
                respuesta = self._cliente.chat_completion(
                    messages=completos, temperature=0, max_tokens=512)
                return respuesta.choices[0].message.content or ""
            except Exception as error:  # red o proveedor
                if intento == INTENTOS or not es_transitorio(error):
                    motivo = self._sin_token(f"{type(error).__name__}: {error}")
                    raise RuntimeError(f"el modelo {self.modelo} no respondió tras "
                                       f"{intento} intento(s) ({motivo})") from None
        raise AssertionError("inalcanzable")


def es_transitorio(error: Exception) -> bool:
    """Fallo de red, 429 o 5xx: merece reintento. 401/402/404… no se arreglan reintentando."""
    estado = getattr(getattr(error, "response", None), "status_code", None)
    return estado is None or estado == 429 or estado >= 500


# --- Simulado ---------------------------------------------------------------

PALABRAS_TIPO = [  # el orden importa: "no puedo entrar en el ERP" no es red
    ("impresora", ("imprim", "impresora", "toner", "atasco")),
    ("acceso_aplicacion", ("erp", "contrasena", "acceso", "aplicacion", "entrar")),
    ("correo", ("correo", "buzon", "outlook")),
    ("hardware", ("portatil", "monitor", "enciende", "pantalla", "teclado",
                  "ordenador", "pc", "equipo", "lent", "raton", "cuelg")),
    ("red", ("internet", "vpn", "conexion", "red", "wifi", "navegar")),
]
PALABRAS_SOPORTE = ("funcion", "error", "fall", "problema", "puedo", "programa",
                    "instal", "actualiz", "oficina", "roto", "rota")
PRIORIDAD_TIPO = {"impresora": "P4"}  # suele haber otra impresora disponible
PALABRAS_MOLESTIA = ("lent", "tard", "cuelg")  # puede trabajar, aunque peor → P4
SERVICIO_TIPO = {"red": "vpn", "impresora": "impresion",
                 "acceso_aplicacion": "erp", "correo": "correo"}


def _tiene(tokens: list[str], raices: tuple[str, ...]) -> bool:
    return any(t.startswith(r) for t in tokens for r in raices)


def _tipo_por_palabras(texto: str) -> str:
    """Tipo por palabras clave; sin ninguna, `otro` si suena a soporte."""
    tokens = tokenizar(texto)
    for tipo, raices in PALABRAS_TIPO:
        if _tiene(tokens, raices):
            return tipo
    return "otro" if _tiene(tokens, PALABRAS_SOPORTE) else "fuera_de_ambito"


def _de_su_tipo(fragmentos: list[dict], tipo: str) -> list[dict]:
    """Solo artículos kb-<tipo>-NN.md: no se cita un artículo de otro tipo."""
    return [f for f in fragmentos if f["doc"].startswith(f"docs/kb-{tipo}-")]


def _ultima_observacion(mensajes: list[dict]) -> Any:
    contenido = mensajes[-1]["content"].removeprefix("Observación: ")
    try:
        return json.loads(contenido)
    except json.JSONDecodeError:
        return {"error": contenido}


class ModeloSimulado:
    """Modelo determinista por reglas para usar el sistema sin token.

    No aplica ninguna regla de seguridad: eso lo hace siempre el orquestador.
    """

    def generar(self, sistema: str, mensajes: list[dict]) -> str:
        agente = re.search(r"«(\w+)»", sistema)
        contexto = json.loads(mensajes[0]["content"])
        turno = sum(1 for m in mensajes if m["role"] == "assistant")
        responder = getattr(self, f"_{agente.group(1) if agente else 'desconocido'}",
                            self._desconocido)
        return json.dumps(responder(contexto, turno, mensajes), ensure_ascii=False)

    def _clasificador(self, ctx: dict, turno: int, mensajes: list[dict]) -> dict:
        tipo = _tipo_por_palabras(ctx["incidencia"])
        molestia = _tiene(tokenizar(ctx["incidencia"]), PALABRAS_MOLESTIA)
        prioridad = "P4" if molestia else PRIORIDAD_TIPO.get(tipo, "P3")
        return {"tipo": tipo, "prioridad": prioridad,
                "motivo": f"palabras clave de la incidencia: {tipo}"}

    def _diagnostico(self, ctx: dict, turno: int, mensajes: list[dict]) -> dict:
        servicio = SERVICIO_TIPO.get(ctx["averiguado"].get("tipo", ""))
        if servicio is None:
            return {"causa": "posible avería del equipo del empleado", "servicio": None,
                    "evidencias": ["el tipo de incidencia no depende de un servicio"]}
        if turno == 0:
            return {"herramienta": "consultar_servicio",
                    "argumentos": {"servicio": servicio, "oficina": ctx["oficina"]}}
        estado = _ultima_observacion(mensajes).get("estado", "desconocido")
        if estado == "ok":
            return {"causa": f"{servicio} ok en {ctx['oficina']}: posible fallo del equipo",
                    "servicio": None, "evidencias": [f"{servicio} = ok"]}
        return {"causa": f"{servicio} {estado} en {ctx['oficina']}", "servicio": servicio,
                "evidencias": [f"consultar_servicio({servicio}, {ctx['oficina']}) = {estado}"]}

    def _conocimiento(self, ctx: dict, turno: int, mensajes: list[dict]) -> dict:
        averiguado = ctx["averiguado"]
        if turno == 0:
            consulta = f"{ctx['incidencia']} {averiguado.get('causa', '')}"
            return {"herramienta": "buscar_docs", "argumentos": {"consulta": consulta, "k": 5}}
        fragmentos = _de_su_tipo(_ultima_observacion(mensajes).get("fragmentos", []),
                                 averiguado.get("tipo", ""))
        if not fragmentos:
            return {"procedimiento": None, "citas": [], "accion": None}
        elegido = next((f for f in fragmentos if f["seccion"] == "Pasos"), fragmentos[0])
        servicio, causa = averiguado.get("servicio"), averiguado.get("causa", "")
        accion = None
        if servicio and ("caido" in causa or "degradado" in causa):
            accion = {"herramienta": "reiniciar_servicio",
                      "argumentos": {"servicio": servicio, "oficina": ctx["oficina"]}}
        return {"procedimiento": elegido["texto"],
                "citas": [f"{elegido['doc']}#{elegido['seccion']}"], "accion": accion}

    def _escalado(self, ctx: dict, turno: int, mensajes: list[dict]) -> dict:
        averiguado = ctx["averiguado"]
        return {"resumen": f"{ctx['incidencia']} ({ctx['oficina']}). "
                           f"Causa: {averiguado.get('causa', 'sin diagnosticar')}.",
                "probado": [str(n) for n in ctx.get("notas_del_orquestador", [])],
                "prioridad": averiguado.get("prioridad", "P3")}

    def _desconocido(self, ctx: dict, turno: int, mensajes: list[dict]) -> dict:
        return {"error": "agente desconocido"}
