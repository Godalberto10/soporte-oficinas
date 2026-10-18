"""Bucle común de agente y los cuatro agentes especialistas."""

import inspect
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from soporte_oficinas.estado import Accion, Estado, Paso
from soporte_oficinas.herramientas import (
    PRIORIDADES,
    ErrorHerramienta,
    Herramienta,
    ejecutar,
)
from soporte_oficinas.modelo import Modelo

TIPOS = frozenset({"red", "impresora", "acceso_aplicacion", "correo", "hardware", "otro",
                   "fuera_de_ambito"})
SERVICIOS = frozenset({"vpn", "correo", "erp", "ficheros", "intranet",
                       "impresion", "wifi_invitados"})
DESCRIPCION_SERVICIOS = {  # igual que docs/catalogo-servicios.md (lo comprueba una prueba)
    "vpn": "Túnel de la oficina con el centro de datos y salida a internet",
    "correo": "Correo corporativo (Outlook y webmail)",
    "erp": "Aplicación de gestión (pedidos, facturación, almacén)",
    "ficheros": "Carpetas compartidas de la oficina",
    "impresion": "Servidor de colas de impresión",
    "wifi_invitados": "Red inalámbrica para visitas",
    "intranet": "Portal interno y autoservicio de contraseñas",
}
ACCIONES_PROPONIBLES = frozenset({"reiniciar_servicio", "cerrar_ticket"})
MAX_ILEGIBLES = 2


@dataclass(frozen=True)
class Agente:
    """Definición de un agente: rol, herramientas permitidas y contrato de salida."""

    nombre: str
    instrucciones: str
    herramientas: tuple[str, ...]
    claves: tuple[str, ...]
    validar: Callable[[dict], None]
    formato: str = ""  # ejemplo exacto de la salida final, con tipos y valores permitidos


@dataclass
class SalidaAgente:
    """Resultado de ejecutar un agente: datos validados o motivo de parada."""

    datos: dict | None
    motivo: str  # ok | ilegible | tope


# --- JSON ------------------------------------------------------------------

_BLOQUE_JSON = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extraer_json(texto: str) -> dict:
    """Primer objeto JSON del texto (suelto, en bloque ```json o con texto alrededor)."""
    try:
        datos = json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        return _buscar_objeto(texto)
    if not isinstance(datos, dict):
        raise ValueError("se esperaba un objeto JSON, no otro tipo de valor")
    return datos


def _buscar_objeto(texto: str) -> dict:
    if not isinstance(texto, str):
        raise ValueError("la respuesta no es texto")
    bloque = _BLOQUE_JSON.search(texto)
    candidato = bloque.group(1) if bloque else texto
    decodificador = json.JSONDecoder()
    for inicio in (i for i, c in enumerate(candidato) if c == "{"):
        try:
            datos, _ = decodificador.raw_decode(candidato, inicio)
        except json.JSONDecodeError:
            continue
        if isinstance(datos, dict):
            return datos
    raise ValueError("no hay ningún objeto JSON en la respuesta")


# --- Validación de contratos ----------------------------------------------

def _texto(datos: dict, clave: str, nulo: bool = False) -> None:
    valor = datos.get(clave)
    if valor is None and nulo:
        return
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"'{clave}' debe ser un texto no vacío")


def _lista_textos(datos: dict, clave: str) -> None:
    valor = datos.get(clave)
    if not isinstance(valor, list) or not all(isinstance(v, str) for v in valor):
        raise ValueError(f"'{clave}' debe ser una lista de textos")


def _uno_de(datos: dict, clave: str, valores: frozenset[str], nulo: bool = False) -> None:
    valor = datos.get(clave)
    if valor is None and nulo:
        return
    if not isinstance(valor, str) or valor not in valores:
        raise ValueError(f"'{clave}' debe ser uno de {sorted(valores)}")


def _validar_clasificador(datos: dict) -> None:
    _uno_de(datos, "tipo", TIPOS)
    _uno_de(datos, "prioridad", PRIORIDADES)
    _texto(datos, "motivo")


def _validar_diagnostico(datos: dict) -> None:
    _texto(datos, "causa")
    _uno_de(datos, "servicio", SERVICIOS, nulo=True)
    _lista_textos(datos, "evidencias")


def _validar_conocimiento(datos: dict) -> None:
    _texto(datos, "procedimiento", nulo=True)
    _lista_textos(datos, "citas")
    accion = datos.get("accion")
    if accion is None:
        return
    if (not isinstance(accion, dict)
            or accion.get("herramienta") not in ACCIONES_PROPONIBLES
            or not isinstance(accion.get("argumentos"), dict)):
        raise ValueError("'accion' debe ser null o {\"herramienta\": "
                         f"uno de {sorted(ACCIONES_PROPONIBLES)}, \"argumentos\": {{...}}}}")


def _validar_escalado(datos: dict) -> None:
    _texto(datos, "resumen")
    _lista_textos(datos, "probado")
    _uno_de(datos, "prioridad", PRIORIDADES)


def validar_contrato(agente: Agente, datos: dict) -> dict:
    """Comprueba claves y valores; devuelve solo las claves del contrato."""
    faltan = [c for c in agente.claves if c not in datos]
    if faltan:
        raise ValueError(f"faltan claves del contrato: {', '.join(faltan)}")
    agente.validar(datos)
    return {c: datos[c] for c in agente.claves}


# --- Definición de los agentes ---------------------------------------------

def _opciones(valores: frozenset[str]) -> str:
    return "|".join(sorted(valores))


_P = _opciones(PRIORIDADES)

AGENTES: dict[str, Agente] = {
    "clasificador": Agente(
        "clasificador",
        "Decides el tipo de incidencia y su prioridad.\n"
        f"Tipos: {', '.join(sorted(TIPOS))}. Usa 'otro' para incidencias de soporte "
        "sin categoría y 'fuera_de_ambito' si la petición no es de soporte técnico "
        "de oficinas.\n"
        "Prioridades: P1 afecta a más de una oficina o un servicio crítico está "
        "caido; P2 afecta a una oficina entera o un crítico está degradado; P3 un "
        "empleado no puede trabajar y no hay alternativa; P4 molestia con alternativa.\n"
        "Servicios críticos: vpn, correo, erp, ficheros, intranet.",
        ("buscar_tickets",),
        ("tipo", "prioridad", "motivo"),
        _validar_clasificador,
        f'{{"tipo": "{_opciones(TIPOS)}", "prioridad": "{_P}", "motivo": "<texto>"}}',
    ),
    "diagnostico": Agente(
        "diagnostico",
        "Averiguas la causa probable consultando el estado real de los servicios, "
        "los equipos y los tickets. Indica el servicio afectado (o null si es un "
        "equipo) y, en evidencias, lo que has observado. Si la avería afecta a "
        "más de una oficina, dilo en las evidencias.\n"
        "Antes de concluir, consulta al menos una herramienta (por ejemplo, "
        "consultar_servicio del servicio relacionado en la oficina de la incidencia) "
        "y no inventes causas que no hayas observado.\n"
        "Servicios de cada oficina:\n"
        + "\n".join(f"- {s}: {d}" for s, d in DESCRIPCION_SERVICIOS.items()),
        ("consultar_servicio", "consultar_equipo", "buscar_tickets"),
        ("causa", "servicio", "evidencias"),
        _validar_diagnostico,
        f'{{"causa": "<texto>", "servicio": "{_opciones(SERVICIOS)}" o null, '
        '"evidencias": ["<texto>", "<texto>"]}',
    ),
    "conocimiento": Agente(
        "conocimiento",
        "Buscas en la base de conocimiento el procedimiento que resuelve la causa "
        "diagnosticada y lo redactas para el empleado. Tu primer turno es SIEMPRE "
        "una llamada a buscar_docs con la causa diagnosticada. Cita solo fragmentos que "
        "hayas recuperado con buscar_docs, con el formato docs/<fichero>.md#<seccion>. "
        "Si no encuentras procedimiento, devuelve procedimiento null y citas []. "
        "Las acciones irreversibles NO se llaman: se proponen en 'accion' como "
        "{\"herramienta\": ..., \"argumentos\": {...}} y una persona las confirmará.",
        ("buscar_docs", "reiniciar_servicio", "cerrar_ticket"),
        ("procedimiento", "citas", "accion"),
        _validar_conocimiento,
        '{"procedimiento": "<texto>" o null, "citas": ["docs/<fichero>.md#<seccion>"], '
        f'"accion": null o {{"herramienta": "{_opciones(ACCIONES_PROPONIBLES)}", '
        '"argumentos": {...}}}',
    ),
    "escalado": Agente(
        "escalado",
        "Preparas el traspaso a segundo nivel: un resumen claro de la incidencia y "
        "su causa, la lista de lo que ya se ha probado y la prioridad (P1–P4). Si "
        "no llamas a crear_escalado, el sistema lo creará con tu respuesta.",
        ("crear_escalado",),
        ("resumen", "probado", "prioridad"),
        _validar_escalado,
        f'{{"resumen": "<texto>", "probado": ["<texto>", "<texto>"], "prioridad": "{_P}"}}',
    ),
}


# --- Prompt y mensajes ------------------------------------------------------

def _firma(herramienta: Herramienta) -> str:
    firma = inspect.signature(herramienta.funcion)
    return f"{herramienta.nombre}{firma.replace(return_annotation=inspect.Signature.empty)}"


def prompt_sistema(agente: Agente, herramientas: dict[str, Herramienta]) -> str:
    """Prompt generado desde la definición del agente y el registro."""
    permitidas = [herramientas[n] for n in agente.herramientas if n in herramientas]
    llamables = [f"- {_firma(h)}: {h.descripcion}" for h in permitidas if h.reversible]
    proponibles = [f"- {_firma(h)}: {h.descripcion}" for h in permitidas if not h.reversible]
    partes = [
        f"Eres el agente «{agente.nombre}» del soporte técnico de primer nivel "
        "de una red de oficinas.",
        agente.instrucciones,
        "Responde SIEMPRE con un único objeto JSON, sin texto adicional.",
        'Para usar una herramienta: {"herramienta": "<nombre>", "argumentos": {...}}',
        f"Para terminar: un objeto con las claves {', '.join(agente.claves)}, "
        "exactamente con este formato (las listas son listas JSON; | separa los "
        f"valores permitidos):\n{agente.formato}",
        "Herramientas que puedes llamar:\n" + ("\n".join(llamables) or "- ninguna"),
    ]
    if proponibles:
        partes.append("Acciones que puedes proponer en 'accion' (no las llames):\n"
                      + "\n".join(proponibles))
    return "\n\n".join(partes)


def mensaje_inicial(estado: Estado) -> str:
    """Incidencia y lo averiguado hasta ahora, en JSON."""
    averiguado = {
        clave: getattr(estado, clave)
        for clave in ("tipo", "prioridad", "causa", "servicio", "procedimiento", "citas")
        if getattr(estado, clave)
    }
    mensaje = {"incidencia": estado.incidencia, "oficina": estado.oficina,
               "ticket": estado.ticket, "averiguado": averiguado}
    notas = [p.observacion for p in estado.traza if p.agente == "orquestador"]
    if notas:
        mensaje["notas_del_orquestador"] = notas
    return json.dumps(mensaje, ensure_ascii=False)


def _observacion(contenido: Any) -> dict[str, str]:
    texto = contenido if isinstance(contenido, str) else json.dumps(contenido, ensure_ascii=False)
    return {"role": "user", "content": f"Observación: {texto}"}


# --- Bucle común -----------------------------------------------------------

def registrar(estado: Estado, agente: str, herramienta: str | None,
              argumentos: dict, observacion: Any) -> None:
    """Añade un paso a la traza y lo cuenta para el tope (n = posición en la traza)."""
    estado.pasos += 1
    estado.traza.append(Paso(len(estado.traza) + 1, agente, herramienta, argumentos,
                             observacion))


def _es_llamada(datos: dict) -> bool:
    return "herramienta" in datos and set(datos) <= {"herramienta", "argumentos"}


def _llamar(agente: Agente, estado: Estado, herramientas: dict[str, Herramienta],
            datos: dict) -> Any:
    """Ejecuta la herramienta pedida si está permitida y es reversible."""
    nombre, argumentos = datos.get("herramienta"), datos.get("argumentos", {})
    herramienta = herramientas.get(nombre) if nombre in agente.herramientas else None
    if herramienta is None:
        motivo = f"herramienta no permitida para {agente.nombre}: {nombre}"
    elif not herramienta.reversible:
        motivo = f"{nombre} es irreversible: no se ejecuta; propónla en la clave 'accion'"
    else:
        try:
            observacion = ejecutar(herramientas, nombre, argumentos)
        except ErrorHerramienta as error:
            observacion = {"error": str(error)}
        registrar(estado, agente.nombre, nombre, argumentos, observacion)
        return observacion
    registrar(estado, agente.nombre, None, {"solicitada": nombre, "argumentos": argumentos},
              {"error": motivo})
    return {"error": motivo}


def ejecutar_agente(agente: Agente, estado: Estado, modelo: Modelo,
                    herramientas: dict[str, Herramienta], max_pasos: int = 12) -> SalidaAgente:
    """Turnos modelo → herramienta → observación hasta una salida válida."""
    sistema = prompt_sistema(agente, herramientas)
    mensajes = [{"role": "user", "content": mensaje_inicial(estado)}]
    ilegibles = 0
    while estado.pasos < max_pasos:
        texto = modelo.generar(sistema, mensajes)
        mensajes.append({"role": "assistant", "content": texto})
        try:
            datos = extraer_json(texto)
            if not _es_llamada(datos):
                datos = validar_contrato(agente, datos)
        except ValueError as error:
            ilegibles += 1
            registrar(estado, agente.nombre, None, {}, f"respuesta no válida ({error}): {texto}")
            if ilegibles >= MAX_ILEGIBLES:
                return SalidaAgente(None, "ilegible")
            mensajes.append(_observacion(f"respuesta no válida: {error}. "
                                         "Responde con un único objeto JSON."))
            continue
        ilegibles = 0
        registrar(estado, agente.nombre, None, {}, datos)
        if not _es_llamada(datos):
            return SalidaAgente(datos, "ok")
        if estado.pasos >= max_pasos:
            break
        mensajes.append(_observacion(_llamar(agente, estado, herramientas, datos)))
    return SalidaAgente(None, "tope")


# --- Agentes: ejecutar y aplicar al estado --------------------------------

def conocimiento(estado: Estado, modelo: Modelo, herramientas: dict[str, Herramienta],
                 max_pasos: int = 12) -> SalidaAgente:
    """Procedimiento y citas; una acción propuesta queda en estado.acciones."""
    salida = ejecutar_agente(AGENTES["conocimiento"], estado, modelo, herramientas, max_pasos)
    if salida.datos is not None:
        estado.procedimiento = salida.datos["procedimiento"]
        estado.citas = list(salida.datos["citas"])
        accion = salida.datos["accion"]
        if accion is not None:
            estado.acciones.append(Accion(accion["herramienta"], dict(accion["argumentos"])))
    return salida


def clasificador(estado: Estado, modelo: Modelo, herramientas: dict[str, Herramienta],
                 max_pasos: int = 12) -> SalidaAgente:
    """Tipo y prioridad (la prioridad se guarda tal cual; la valida el orquestador)."""
    salida = ejecutar_agente(AGENTES["clasificador"], estado, modelo, herramientas, max_pasos)
    if salida.datos is not None:
        estado.tipo = salida.datos["tipo"]
        estado.prioridad = salida.datos["prioridad"]
    return salida


def diagnostico(estado: Estado, modelo: Modelo, herramientas: dict[str, Herramienta],
                max_pasos: int = 12) -> SalidaAgente:
    """Causa probable y servicio afectado (o None si es un equipo)."""
    salida = ejecutar_agente(AGENTES["diagnostico"], estado, modelo, herramientas, max_pasos)
    if salida.datos is not None:
        estado.causa = salida.datos["causa"]
        estado.servicio = salida.datos["servicio"]
    return salida


def _escalado_ya_creado(estado: Estado, desde: int) -> str | None:
    for paso in estado.traza[desde:]:
        if paso.herramienta == "crear_escalado" and isinstance(paso.observacion, dict):
            if "escalado" in paso.observacion:
                return paso.observacion["escalado"]
    return None


def asegurar_escalado(estado: Estado, datos: dict,
                      herramientas: dict[str, Herramienta]) -> str:
    """Crea el escalado con la salida del agente; sin ticket si el del estado no vale."""
    for ticket in dict.fromkeys([estado.ticket, None]):
        argumentos = {"ticket": ticket, "resumen": datos["resumen"],
                      "prioridad": datos["prioridad"]}
        try:
            observacion = ejecutar(herramientas, "crear_escalado", argumentos)
        except ErrorHerramienta as error:
            registrar(estado, "escalado", "crear_escalado", argumentos, {"error": str(error)})
            continue
        registrar(estado, "escalado", "crear_escalado", argumentos, observacion)
        return observacion["escalado"]
    raise ErrorHerramienta("no se pudo crear el escalado")


def escalado(estado: Estado, modelo: Modelo, herramientas: dict[str, Herramienta],
             max_pasos: int = 12) -> SalidaAgente:
    """Traspaso a nivel 2; el código garantiza que queda un escalado creado."""
    desde = len(estado.traza)
    salida = ejecutar_agente(AGENTES["escalado"], estado, modelo, herramientas, max_pasos)
    if salida.datos is not None:
        id_escalado = _escalado_ya_creado(estado, desde)
        salida.datos["escalado"] = id_escalado or asegurar_escalado(
            estado, salida.datos, herramientas)
    return salida
