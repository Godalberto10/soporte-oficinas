"""Pruebas de ModeloHF (con cliente falso, sin red) y de ModeloSimulado."""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from soporte_oficinas import modelo as modulo_modelo
from soporte_oficinas.herramientas import Red
from soporte_oficinas.modelo import MODELO_POR_DEFECTO, ModeloHF, ModeloSimulado
from soporte_oficinas.orquestador import orquestar, trayectoria

LUNES_10 = datetime(2026, 10, 12, 10, 0)
TOKEN_FALSO = "hf_tokenfalsoparapruebas123"


@pytest.fixture(autouse=True)
def sin_env_real(monkeypatch):
    """Ninguna prueba lee el .env real ni usa un token de verdad."""
    monkeypatch.setattr(modulo_modelo, "load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HF_MODEL", raising=False)


def respuesta(texto: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=texto))])


class ClienteFalso:
    """Imita InferenceClient.chat_completion; puede fallar las primeras veces."""

    def __init__(self, fallos: int = 0, texto: str = '{"ok": true}') -> None:
        self.fallos, self.texto = fallos, texto
        self.llamadas: list[dict] = []

    def chat_completion(self, **kwargs):
        self.llamadas.append(kwargs)
        if len(self.llamadas) <= self.fallos:
            raise ConnectionError(f"proveedor caído (token {TOKEN_FALSO})")
        return respuesta(self.texto)


# --- Criterio 1: mensajes y parámetros --------------------------------------

def test_envia_sistema_mensajes_y_parametros():
    cliente = ClienteFalso(texto='{"tipo": "red"}')
    mensajes = [{"role": "user", "content": "no tengo internet"}]
    texto = ModeloHF(cliente=cliente).generar("eres el clasificador", mensajes)
    assert texto == '{"tipo": "red"}'
    llamada = cliente.llamadas[0]
    assert llamada["messages"] == [{"role": "system", "content": "eres el clasificador"},
                                   *mensajes]
    assert llamada["temperature"] == 0 and llamada["max_tokens"] == 512


# --- Criterio 2: sin token ----------------------------------------------------

def test_sin_token_error_claro():
    with pytest.raises(RuntimeError, match="HF_TOKEN"):
        ModeloHF()


# --- Criterio 3: reintento y errores sin token --------------------------------

def test_reintenta_una_vez():
    cliente = ClienteFalso(fallos=1)
    assert ModeloHF(cliente=cliente).generar("s", []) == '{"ok": true}'
    assert len(cliente.llamadas) == 2


def test_falla_tras_dos_intentos_sin_mostrar_token(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", TOKEN_FALSO)
    cliente = ClienteFalso(fallos=99)
    with pytest.raises(RuntimeError) as error:
        ModeloHF(cliente=cliente).generar("s", [])
    assert len(cliente.llamadas) == 2
    assert TOKEN_FALSO not in str(error.value)
    assert "2 intento" in str(error.value)


class ErrorHTTP(Exception):
    """Imita HfHubHTTPError: lleva la respuesta con su código de estado."""

    def __init__(self, estado: int) -> None:
        super().__init__(f"HTTP {estado}")
        self.response = SimpleNamespace(status_code=estado)


class ClienteHTTP:
    def __init__(self, estado: int) -> None:
        self.estado, self.llamadas = estado, 0

    def chat_completion(self, **kwargs):
        self.llamadas += 1
        raise ErrorHTTP(self.estado)


@pytest.mark.parametrize("estado, llamadas", [
    (401, 1), (402, 1), (404, 1),    # no se arreglan reintentando
    (429, 2), (500, 2), (503, 2),    # transitorios
])
def test_solo_reintenta_fallos_transitorios(estado, llamadas):
    cliente = ClienteHTTP(estado)
    with pytest.raises(RuntimeError, match=str(estado)):
        ModeloHF(cliente=cliente).generar("s", [])
    assert cliente.llamadas == llamadas


# --- Criterio 4: HF_MODEL -------------------------------------------------------

def test_modelo_por_defecto_y_hf_model(monkeypatch):
    assert ModeloHF(cliente=ClienteFalso()).modelo == MODELO_POR_DEFECTO
    monkeypatch.setenv("HF_MODEL", "otro/modelo")
    assert ModeloHF(cliente=ClienteFalso()).modelo == "otro/modelo"
    assert ModeloHF("explicito/modelo", cliente=ClienteFalso()).modelo == "explicito/modelo"


# --- Criterio 5: ModeloSimulado con el orquestador --------------------------------

def correr(incidencia: str, oficina: str, confirmar: bool, ticket: str | None = None):
    red = Red.desde_directorio()
    resultado = orquestar(incidencia, oficina, ModeloSimulado(), lambda accion: confirmar,
                          ahora=lambda: LUNES_10, ticket=ticket, red=red)
    return resultado, red


def test_simulado_resuelve_con_reinicio():
    resultado, red = correr("no tengo internet", "MAD-01", True)
    assert resultado.final == "resuelto"
    assert (resultado.tipo, resultado.prioridad) == ("red", "P1")
    assert red.servicios["MAD-01"]["vpn"] == "ok"
    assert resultado.citas == ["docs/kb-red-01.md#Pasos"]


def test_simulado_rechazo_escala():
    resultado, red = correr("no tengo internet", "MAD-01", False)
    assert resultado.final == "escalado"
    assert red.servicios["MAD-01"]["vpn"] == "caido"


def test_simulado_multioficina():
    resultado, red = correr("no puedo entrar en el ERP", "MAD-02", True)
    assert resultado.final == "escalado" and resultado.prioridad == "P1"
    assert trayectoria(resultado.traza) == ["clasificador", "diagnostico", "escalado"]
    assert red.escalados[0]["prioridad"] == "P1"


def test_simulado_ticket_reabierto():
    resultado, _ = correr("la impresora no imprime", "MAD-02", True, ticket="T-0007")
    assert resultado.final == "escalado"
    assert trayectoria(resultado.traza) == ["clasificador", "diagnostico", "escalado"]


def test_simulado_equipo_sin_reinicio():
    resultado, red = correr("no tengo internet", "VAL-01", True, ticket="T-0002")
    assert resultado.final == "resuelto"
    assert not any(p.herramienta == "reiniciar_servicio" for p in resultado.traza)


@pytest.mark.parametrize("incidencia, tipo", [
    ("no tengo internet", "red"),
    ("la impresora no imprime", "impresora"),
    ("no puedo entrar en el ERP", "acceso_aplicacion"),
    ("mi contraseña ha caducado", "acceso_aplicacion"),
    ("el correo tarda mucho", "correo"),
    ("el portátil no enciende", "hardware"),
    ("la silla está rota", "otro"),
    ("me va lento el ordenador", "hardware"),
    ("el PC se cuelga", "hardware"),
    ("¿me recomiendas un restaurante?", "fuera_de_ambito"),
])
def test_simulado_clasifica_por_palabras(incidencia, tipo):
    assert modulo_modelo._tipo_por_palabras(incidencia) == tipo


@pytest.mark.parametrize("incidencia, prioridad", [
    ("la impresora no imprime", "P4"),      # suele haber otra impresora
    ("me va lento el ordenador", "P4"),     # molestia: puede seguir trabajando
    ("no tengo internet", "P3"),
])
def test_simulado_prioridad_inicial(incidencia, prioridad):
    contexto = {"incidencia": incidencia, "oficina": "MAD-01", "averiguado": {}}
    datos = ModeloSimulado()._clasificador(contexto, 0, [])
    assert datos["prioridad"] == prioridad


def test_simulado_no_cita_articulos_de_otro_tipo():
    contexto = {"incidencia": "me va lento el ordenador", "oficina": "MAD-01",
                "averiguado": {"tipo": "hardware", "causa": "equipo lento"}}
    observacion = {"fragmentos": [{"doc": "docs/kb-red-02.md", "seccion": "Pasos",
                                   "texto": "1. Probar otro cable."}]}
    mensajes = [{"role": "user", "content": json.dumps(contexto)},
                {"role": "assistant", "content": "{}"},
                {"role": "user", "content": "Observación: " + json.dumps(observacion)}]
    datos = ModeloSimulado()._conocimiento(contexto, 1, mensajes)
    assert datos["procedimiento"] is None and datos["citas"] == []
