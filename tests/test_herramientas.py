"""Pruebas de las herramientas, su registro y ejecutar()."""

import hashlib
import shutil
from pathlib import Path

import pytest

from soporte_oficinas.herramientas import (
    RUTA_DATOS,
    ErrorHerramienta,
    Herramienta,
    Red,
    crear_herramientas,
    ejecutar,
)

NOMBRES = {
    "consultar_servicio", "consultar_equipo", "buscar_tickets",
    "crear_escalado", "reiniciar_servicio", "cerrar_ticket",
}
IRREVERSIBLES = {"reiniciar_servicio", "cerrar_ticket"}


@pytest.fixture
def red(tmp_path: Path) -> Red:
    for fichero in RUTA_DATOS.glob("*.json"):
        shutil.copy(fichero, tmp_path)
    return Red.desde_directorio(tmp_path)


@pytest.fixture
def h(red: Red) -> dict[str, Herramienta]:
    return crear_herramientas(red)


# --- Criterios 3 y 4: registro --------------------------------------------

def test_registro_completo_y_reversibilidad(h):
    assert set(h) == NOMBRES
    for nombre, herramienta in h.items():
        assert isinstance(herramienta, Herramienta)
        assert herramienta.nombre == nombre
        assert herramienta.descripcion.strip()
        assert herramienta.reversible == (nombre not in IRREVERSIBLES)


def test_buscar_docs_aun_no_registrada(h):
    assert "buscar_docs" not in h


# --- Criterio 5: resultados -------------------------------------------------

def test_consultar_servicio(h):
    assert ejecutar(h, "consultar_servicio", {"servicio": "vpn", "oficina": "MAD-01"}) == {
        "servicio": "vpn", "oficina": "MAD-01", "estado": "caido",
    }


def test_consultar_equipo(h):
    ficha = ejecutar(h, "consultar_equipo", {"id_equipo": "PC-VAL01-002"})
    assert ficha["oficina"] == "VAL-01"
    assert ficha["estado"] == "averiado_tarjeta_red"


def test_buscar_tickets_filtros(h):
    todos = ejecutar(h, "buscar_tickets", {})["tickets"]
    assert len(todos) == 10
    mad = ejecutar(h, "buscar_tickets", {"oficina": "MAD-01"})["tickets"]
    assert {t["id"] for t in mad} == {"T-0001", "T-0009"}
    internet = ejecutar(h, "buscar_tickets", {"sintoma": "NO TENGO INTERNET"})["tickets"]
    assert {t["id"] for t in internet} == {"T-0001", "T-0002"}
    ambos = ejecutar(h, "buscar_tickets", {"oficina": "VAL-01", "sintoma": "internet"})
    assert [t["id"] for t in ambos["tickets"]] == ["T-0002"]


def test_crear_escalado_ids_crecientes(h, red):
    primero = ejecutar(h, "crear_escalado",
                       {"ticket": "T-0007", "resumen": "impresión caída", "prioridad": "P2"})
    segundo = ejecutar(h, "crear_escalado",
                       {"ticket": None, "resumen": "erp en dos oficinas", "prioridad": "P1"})
    assert primero["escalado"] == "ESC-0001"
    assert segundo["escalado"] == "ESC-0002"
    assert len(red.escalados) == 2


def test_reiniciar_servicio_deja_ok(h):
    salida = ejecutar(h, "reiniciar_servicio", {"servicio": "vpn", "oficina": "MAD-01"})
    assert salida["estado_anterior"] == "caido"
    assert ejecutar(h, "consultar_servicio",
                    {"servicio": "vpn", "oficina": "MAD-01"})["estado"] == "ok"


def test_cerrar_ticket(h, red):
    ejecutar(h, "cerrar_ticket", {"ticket": "T-0001", "resolucion": "VPN reiniciada"})
    ticket = red.ticket("T-0001")
    assert ticket["estado"] == "cerrado"
    assert ticket["resolucion"] == "VPN reiniciada"


# --- Criterio 6: errores de las herramientas ------------------------------

@pytest.mark.parametrize("nombre, argumentos", [
    ("consultar_servicio", {"servicio": "vpn", "oficina": "SEV-01"}),
    ("consultar_servicio", {"servicio": "telefonia", "oficina": "MAD-01"}),
    ("consultar_servicio", {"servicio": ["vpn"], "oficina": "MAD-01"}),
    ("consultar_equipo", {"id_equipo": "PC-XXX-999"}),
    ("buscar_tickets", {"oficina": "SEV-01"}),
    ("crear_escalado", {"ticket": "T-9999", "resumen": "x", "prioridad": "P1"}),
    ("crear_escalado", {"ticket": "T-0001", "resumen": "x", "prioridad": "P5"}),
    ("crear_escalado", {"ticket": "T-0001", "resumen": "  ", "prioridad": "P1"}),
    ("reiniciar_servicio", {"servicio": "vpn", "oficina": "SEV-01"}),
    ("cerrar_ticket", {"ticket": "T-0001", "resolucion": ""}),
    ("cerrar_ticket", {"ticket": "T-0003", "resolucion": "ya estaba cerrado"}),
    ("cerrar_ticket", {"ticket": "T-9999", "resolucion": "x"}),
])
def test_errores_de_herramienta(h, nombre, argumentos):
    with pytest.raises(ErrorHerramienta) as error:
        ejecutar(h, nombre, argumentos)
    assert str(error.value)


def test_error_no_modifica_estado(h, red):
    with pytest.raises(ErrorHerramienta):
        ejecutar(h, "cerrar_ticket", {"ticket": "T-0001", "resolucion": ""})
    assert red.ticket("T-0001")["estado"] == "abierto"


# --- Criterio 7: ejecutar() -------------------------------------------------

@pytest.mark.parametrize("nombre, argumentos", [
    ("borrar_todo", {}),
    ("consultar_servicio", {"servicio": "vpn", "oficina": "MAD-01", "extra": 1}),
    ("consultar_servicio", {"servicio": "vpn"}),
    ("consultar_servicio", {"red": None, "servicio": "vpn", "oficina": "MAD-01"}),
    ("consultar_servicio", ["vpn", "MAD-01"]),
])
def test_ejecutar_convierte_fallos_de_uso(h, nombre, argumentos):
    with pytest.raises(ErrorHerramienta):
        ejecutar(h, nombre, argumentos)


def test_ejecutar_no_oculta_fallos_internos(red):
    def rota(servicio: str) -> dict:
        raise TypeError("fallo de programación")

    h = {"rota": Herramienta("rota", "falla", True, rota)}
    with pytest.raises(TypeError):
        ejecutar(h, "rota", {"servicio": "vpn"})


# --- Criterio 8: aislamiento ------------------------------------------------

def test_redes_independientes():
    a, b = Red.desde_directorio(), Red.desde_directorio()
    ejecutar(crear_herramientas(a), "reiniciar_servicio",
             {"servicio": "vpn", "oficina": "MAD-01"})
    assert a.servicios["MAD-01"]["vpn"] == "ok"
    assert b.servicios["MAD-01"]["vpn"] == "caido"


def _huellas(directorio: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directorio.glob("*.json"))}


def test_irreversibles_no_escriben_los_json():
    antes = _huellas(RUTA_DATOS)
    h = crear_herramientas(Red.desde_directorio())
    ejecutar(h, "reiniciar_servicio", {"servicio": "erp", "oficina": "MAD-02"})
    ejecutar(h, "cerrar_ticket", {"ticket": "T-0007", "resolucion": "prueba"})
    ejecutar(h, "crear_escalado", {"ticket": None, "resumen": "prueba", "prioridad": "P1"})
    assert _huellas(RUTA_DATOS) == antes
