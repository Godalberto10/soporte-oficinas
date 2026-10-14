"""Pruebas del hito 1: datos simulados (data/) y base de conocimiento (docs/)."""

import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
DOCS = RAIZ / "docs"

OFICINAS = {"MAD-01", "MAD-02", "BCN-01", "VAL-01"}
CRITICOS = {"vpn", "correo", "erp", "ficheros", "intranet"}
NO_CRITICOS = {"impresion", "wifi_invitados"}
ESTADOS_SERVICIO = {"ok", "degradado", "caido"}
TIPOS_KB = {"red", "impresora", "acceso_aplicacion", "correo", "hardware"}
POLITICAS = [
    "catalogo-servicios.md",
    "procedimiento-escalado.md",
    "politica-reinicios.md",
    "guia-prioridades.md",
]


def _cargar(nombre: str):
    return json.loads((DATA / nombre).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def servicios() -> dict:
    return _cargar("servicios.json")


@pytest.fixture(scope="module")
def inventario() -> list:
    return _cargar("inventario.json")


@pytest.fixture(scope="module")
def tickets() -> list:
    return _cargar("tickets.json")


def _articulos_kb() -> list[Path]:
    return sorted(DOCS.glob("kb-*.md"))


# --- Criterio 1 y 2: servicios.json ---------------------------------------

def test_servicios_tiene_oficinas_y_servicios(servicios):
    assert set(servicios) == OFICINAS
    for oficina, estados in servicios.items():
        assert set(estados) == CRITICOS | NO_CRITICOS, oficina
        assert set(estados.values()) <= ESTADOS_SERVICIO, oficina


def test_averia_critica_multioficina(servicios):
    multioficina = [
        s for s in CRITICOS
        if sum(servicios[o][s] == "caido" for o in OFICINAS) >= 2
    ]
    assert multioficina, "ningún crítico caído en 2+ oficinas"


def test_hay_algun_servicio_degradado(servicios):
    valores = [v for estados in servicios.values() for v in estados.values()]
    assert "degradado" in valores


# --- Criterio 3: inventario.json ------------------------------------------

def test_inventario(inventario, servicios):
    assert len(inventario) >= 12
    ids = [e["id"] for e in inventario]
    assert len(ids) == len(set(ids)), "ids de equipo repetidos"
    for equipo in inventario:
        assert set(equipo) == {"id", "tipo", "oficina", "modelo", "estado"}
        assert all(isinstance(v, str) and v for v in equipo.values())
        assert equipo["oficina"] in servicios


# --- Criterio 4: tickets.json ---------------------------------------------

def test_tickets_formato(tickets, servicios):
    assert len(tickets) >= 8
    for t in tickets:
        assert set(t) == {"id", "oficina", "sintoma", "estado", "reaperturas"}
        assert re.fullmatch(r"T-\d{4}", t["id"])
        assert t["oficina"] in servicios
        assert t["estado"] in {"abierto", "cerrado", "reabierto"}
        assert isinstance(t["reaperturas"], int) and t["reaperturas"] >= 0
    ids = [t["id"] for t in tickets]
    assert len(ids) == len(set(ids))


def test_ticket_reabierto(tickets):
    assert any(t["reaperturas"] >= 1 for t in tickets)


def _causa_por_servicio(servicios: dict, oficina: str) -> bool:
    return any(servicios[oficina][s] != "ok" for s in CRITICOS)


def _causa_por_equipo(servicios, inventario, oficina: str) -> bool:
    criticos_ok = not _causa_por_servicio(servicios, oficina)
    averiado = any(
        e["oficina"] == oficina and e["estado"] != "operativo" for e in inventario
    )
    return criticos_ok and averiado


def test_mismo_sintoma_causas_distintas(tickets, servicios, inventario):
    """Mismo síntoma: en una oficina falla un crítico, en otra un equipo."""
    pares = [
        (a["id"], b["id"])
        for a in tickets for b in tickets
        if a["sintoma"] == b["sintoma"] and a["oficina"] != b["oficina"]
        and _causa_por_servicio(servicios, a["oficina"])
        and _causa_por_equipo(servicios, inventario, b["oficina"])
    ]
    assert pares


# --- Criterio 5: artículos kb ---------------------------------------------

def test_hay_ocho_o_mas_articulos_y_doce_docs():
    assert len(_articulos_kb()) >= 8
    assert len(list(DOCS.glob("*.md"))) >= 12
    for nombre in POLITICAS:
        assert (DOCS / nombre).is_file(), nombre


@pytest.mark.parametrize("ruta", _articulos_kb(), ids=lambda p: p.name)
def test_articulo_kb_secciones(ruta: Path):
    assert re.fullmatch(r"kb-[a-z_]+-\d{2}\.md", ruta.name)
    texto = ruta.read_text(encoding="utf-8")
    secciones = re.findall(r"^## (.+?)\s*$", texto, flags=re.MULTILINE)
    assert secciones == ["Síntomas", "Causa", "Pasos"]


def test_articulos_cubren_los_cinco_tipos():
    tipos = {re.match(r"kb-(.+)-\d{2}\.md", p.name).group(1) for p in _articulos_kb()}
    assert TIPOS_KB <= tipos
    assert tipos <= TIPOS_KB | {"otro"}


# --- Criterio 6: coherencia de las políticas con CLAUDE.md ------------------

def _texto_claude() -> str:
    return (RAIZ / "CLAUDE.md").read_text(encoding="utf-8")


def _lista_backticks(linea: str) -> set[str]:
    return set(re.findall(r"`([a-z_]+)`", linea))


def test_criticos_de_claude_md_coinciden():
    linea = re.search(r"^- Críticos: (.+)$", _texto_claude(), re.MULTILINE).group(1)
    assert _lista_backticks(linea) == CRITICOS


def _reglas_prioridad_claude() -> list[str]:
    return re.findall(r"^- \*\*P[1-4]\*\*: .+$", _texto_claude(), re.MULTILINE)


@pytest.mark.parametrize("nombre", POLITICAS)
def test_politica_criticos_y_horario(nombre: str):
    texto = (DOCS / nombre).read_text(encoding="utf-8")
    linea = re.search(r"\*\*Servicios críticos:\*\* (.+)", texto).group(1)
    assert _lista_backticks(linea) == CRITICOS
    assert "de lunes a viernes, de 08:00 a 18:00" in texto


@pytest.mark.parametrize(
    "nombre", ["guia-prioridades.md", "procedimiento-escalado.md"]
)
def test_politica_reglas_prioridad_iguales(nombre: str):
    reglas = _reglas_prioridad_claude()
    assert len(reglas) == 4
    texto = (DOCS / nombre).read_text(encoding="utf-8")
    for regla in reglas:
        assert regla.strip() in texto, regla


def test_catalogo_tiempos_por_prioridad():
    texto = (DOCS / "catalogo-servicios.md").read_text(encoding="utf-8")
    filas = re.findall(r"^\| (P[1-4]) \|", texto, flags=re.MULTILINE)
    assert filas == ["P1", "P2", "P3", "P4"]


def test_politica_reinicios_reglas_guardarrail():
    texto = (DOCS / "politica-reinicios.md").read_text(encoding="utf-8")
    assert "irreversible" in texto
    assert "`caido` o `degradado`" in texto
    assert "un reinicio por servicio" in texto


# --- Criterio 7: sin datos personales ---------------------------------------

PATRONES_PERSONALES = {
    "email": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "telefono": r"(?<!\d)[679]\d{2}[ ]?\d{3}[ ]?\d{3}(?!\d)",
    "dni": r"(?<!\w)\d{8}[A-Z](?!\w)",
}


def _ficheros_contenido() -> list[Path]:
    return sorted(DATA.glob("*.json")) + sorted(DOCS.glob("*.md"))


@pytest.mark.parametrize("ruta", _ficheros_contenido(), ids=lambda p: p.name)
def test_sin_datos_personales(ruta: Path):
    texto = ruta.read_text(encoding="utf-8")
    for nombre, patron in PATRONES_PERSONALES.items():
        assert not re.search(patron, texto), f"{nombre} en {ruta.name}"
