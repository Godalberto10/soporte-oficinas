"""Pruebas del índice BM25 y del troceado de docs/."""

import re
from collections import Counter
from pathlib import Path

import pytest

from soporte_oficinas.recuperacion import (
    RUTA_DOCS,
    IndiceBM25,
    cita,
    raiz,
    tokenizar,
    trocear,
)

RAIZ = RUTA_DOCS.parent


@pytest.fixture(scope="module")
def indice() -> IndiceBM25:
    return IndiceBM25.desde_directorio()


def _corpus(tmp_path: Path, docs: dict[str, str]) -> IndiceBM25:
    for nombre, texto in docs.items():
        (tmp_path / nombre).write_text(texto, encoding="utf-8")
    return IndiceBM25.desde_directorio(tmp_path)


# --- Criterios 1 y 2: troceado -------------------------------------------

def test_un_fragmento_por_seccion():
    fragmentos = trocear()
    esperadas = sum(
        len(re.findall(r"^## ", p.read_text(encoding="utf-8"), re.MULTILINE))
        for p in RUTA_DOCS.glob("*.md")
    )
    assert len(fragmentos) == esperadas
    for f in fragmentos:
        assert {"doc", "seccion", "texto"} <= set(f)
        assert f["doc"].startswith("docs/") and f["texto"]


def test_cada_kb_aporta_tres_secciones():
    por_doc = Counter(f["doc"] for f in trocear() if "/kb-" in f["doc"])
    assert len(por_doc) >= 8
    assert set(por_doc.values()) == {3}


def test_el_titulo_distingue_secciones_iguales(indice):
    """Entre todas las secciones "Pasos", gana la del documento sobre la VPN."""
    pasos = [r for r in indice.buscar("pasos vpn", k=50) if r["seccion"] == "Pasos"]
    assert pasos[0]["doc"] == "docs/kb-red-01.md"


# --- Criterio 3: tokenización ----------------------------------------------

def test_tokenizar_sin_tildes_ni_mayusculas():
    assert tokenizar("¿Contraseña CADUCADA?") == tokenizar("contrasena caducada")
    assert tokenizar("¿Contraseña CADUCADA?") == ["contrasena", "caducada"]


def test_tokenizar_quita_palabras_vacias():
    tokens = tokenizar("el correo de la oficina que no llega")
    assert not {"el", "de", "la", "que"} & set(tokens)
    assert {"correo", "oficina", "llega"} <= set(tokens)


@pytest.mark.parametrize("variantes", [
    ["reiniciar", "reinicio", "reinicios", "reiniciarse"],
    ["caida", "caido", "caidas"],
    ["critico", "criticos", "critica"],
    ["red", "redes"],
    ["impresora", "impresoras"],
])
def test_raiz_une_variantes(variantes):
    assert len({raiz(v) for v in variantes}) == 1


def test_raiz_no_toca_palabras_cortas():
    assert raiz("vpn") == "vpn"
    assert raiz("erp") == "erp"


# --- Criterio 4: BM25 sobre corpus pequeño ----------------------------------

def test_termino_raro_pesa_mas(tmp_path):
    indice = _corpus(tmp_path, {
        "a.md": "# A\n## S\nred red impresora",
        "b.md": "# B\n## S\nred red toner",
        "c.md": "# C\n## S\nred red papel",
    })
    # "red" está en todos; "toner" solo en b.md.
    assert indice.buscar("red toner")[0]["doc"] == "docs/b.md"


def test_fragmento_corto_puntua_mas(tmp_path):
    indice = _corpus(tmp_path, {
        "corto.md": "# X\n## S\nvpn caida",
        "largo.md": "# X\n## S\nvpn caida oficina equipo cable monitor teclado raton",
    })
    resultado = indice.buscar("vpn")
    assert [r["doc"] for r in resultado] == ["docs/corto.md", "docs/largo.md"]
    assert resultado[0]["puntuacion"] > resultado[1]["puntuacion"]


def test_consulta_sin_coincidencias_devuelve_vacio(indice):
    assert indice.buscar("helicoptero submarino") == []
    assert indice.buscar("el de la") == []


# --- Criterio 5: calidad sobre los documentos reales -----------------------

@pytest.mark.parametrize("consulta, esperado", [
    ("no tengo internet, la vpn está caída", "kb-red-01.md"),
    ("tarjeta de red averiada, cable desconectado", "kb-red-02.md"),
    ("atasco de papel en la impresora", "kb-impresora-01.md"),
    ("contraseña caducada, cuenta bloqueada", "kb-acceso_aplicacion-02.md"),
    ("buzón lleno, no recibo correos", "kb-correo-02.md"),
    ("tiempos de respuesta por prioridad", "catalogo-servicios.md"),
    ("reiniciar un servicio crítico en horario laboral", "politica-reinicios.md"),
    ("reinicio de servicios críticos", "politica-reinicios.md"),
    ("el portátil no enciende", "kb-hardware-01.md"),
    ("me va lento el ordenador", "kb-hardware-03.md"),
    ("ninguna impresora imprime", "kb-impresora-02.md"),
])
def test_calidad_primer_resultado(indice, consulta, esperado):
    assert indice.buscar(consulta)[0]["doc"] == f"docs/{esperado}"


def _margen(indice: IndiceBM25, consulta: str, esperado: str) -> float:
    """Puntuación del documento esperado / la del mejor documento distinto."""
    resultado = indice.buscar(consulta, k=50)
    mejor = next(r["puntuacion"] for r in resultado if r["doc"] == esperado)
    otro = next(r["puntuacion"] for r in resultado if r["doc"] != esperado)
    return mejor / otro


@pytest.mark.parametrize("consulta", [
    "reiniciar un servicio crítico en horario laboral",
    "reinicio de servicios críticos",
])
def test_margen_politica_reinicios(indice, consulta):
    """kb-impresora-02 también habla de reiniciar; la política debe ganar con holgura."""
    assert _margen(indice, consulta, "docs/politica-reinicios.md") >= 1.2


# --- Criterio 6: k, orden y determinismo -------------------------------------

@pytest.mark.parametrize("k", [1, 3, 5])
def test_como_mucho_k_ordenados(indice, k):
    resultado = indice.buscar("servicio caido oficina", k)
    assert 0 < len(resultado) <= k
    puntuaciones = [r["puntuacion"] for r in resultado]
    assert puntuaciones == sorted(puntuaciones, reverse=True)


def test_determinista(indice):
    assert indice.buscar("impresora no imprime", 5) == indice.buscar("impresora no imprime", 5)
    otro = IndiceBM25.desde_directorio()
    assert otro.buscar("impresora no imprime", 5) == indice.buscar("impresora no imprime", 5)


# --- Criterio 9: citas --------------------------------------------------------

def test_citas_comprobables(indice):
    for fragmento in indice.buscar("servicio caido reinicio escalado", 10):
        referencia = cita(fragmento)
        fichero, seccion = referencia.split("#")
        assert re.fullmatch(r"docs/[a-z0-9_-]+\.md", fichero)
        assert (RAIZ / fichero).is_file()
        assert seccion == fragmento["seccion"]


def test_cita_formato_exacto():
    assert cita({"doc": "docs/kb-red-01.md", "seccion": "Pasos"}) == "docs/kb-red-01.md#Pasos"
