"""Índice BM25 propio sobre las secciones de los documentos de docs/."""

import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

RUTA_DOCS = Path(__file__).resolve().parents[2] / "docs"
K1 = 1.5
B = 0.75
LONGITUD_RAIZ = 6
PESO_TITULO = 3  # el título del documento cuenta como 3 apariciones

PALABRAS_VACIAS = frozenset("""
a al algo ante como con cual de del desde donde el ella ellos en entre es esa
ese esta este esto estos esta estan fue ha hay la las le les lo los mas me mi
mientras muy o otra otro para pero por que se segun si sin sobre son su sus
tambien te tiene tras tu un una uno unos y ya
""".split())


def tokenizar(texto: str) -> list[str]:
    """Minúsculas, sin tildes, solo letras y dígitos, sin palabras vacías."""
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return [t for t in re.findall(r"[a-z0-9]+", sin_tildes) if t not in PALABRAS_VACIAS]


def raiz(palabra: str) -> str:
    """Raíz aproximada: sin plural ni vocal final, truncada a 6 letras.

    Hace que "reiniciar", "reinicio" y "reinicios" (o "caída" y "caído")
    cuenten como el mismo término.
    """
    if len(palabra) > 4 and palabra.endswith("es") and palabra[-3] not in "aeiou":
        palabra = palabra[:-2]
    elif len(palabra) > 3 and palabra.endswith("s"):
        palabra = palabra[:-1]
    if len(palabra) > 3 and palabra[-1] in "aeo":
        palabra = palabra[:-1]
    return palabra[:LONGITUD_RAIZ]


def terminos(texto: str) -> list[str]:
    """Términos que se indexan y se buscan: raíces de los tokens."""
    return [raiz(t) for t in tokenizar(texto)]


def _secciones(texto: str) -> tuple[str, list[tuple[str, str]]]:
    """Título `# ` del documento y pares (sección `## `, contenido)."""
    titulo, secciones = "", []
    for linea in texto.splitlines():
        if linea.startswith("# "):
            titulo = linea[2:].strip()
        elif linea.startswith("## "):
            secciones.append((linea[3:].strip(), []))
        elif secciones:
            secciones[-1][1].append(linea)
    return titulo, [(s, "\n".join(lineas).strip()) for s, lineas in secciones]


def trocear(ruta_docs: Path = RUTA_DOCS) -> list[dict]:
    """Un fragmento {doc, seccion, texto, titulo} por cada sección `## `."""
    fragmentos = []
    for ruta in sorted(Path(ruta_docs).glob("*.md")):
        titulo, secciones = _secciones(ruta.read_text(encoding="utf-8"))
        for seccion, texto in secciones:
            fragmentos.append({"doc": f"docs/{ruta.name}", "seccion": seccion,
                               "texto": texto, "titulo": titulo})
    return fragmentos


def cita(fragmento: dict) -> str:
    """Cita comprobable de un fragmento: docs/<fichero>.md#<seccion>."""
    return f"{fragmento['doc']}#{fragmento['seccion']}"


def _texto_indexado(fragmento: dict) -> str:
    """Título (con más peso), nombre de la sección y contenido."""
    titulo = " ".join([fragmento.get("titulo", "")] * PESO_TITULO)
    return f"{titulo} {fragmento['seccion']} {fragmento['texto']}"


class IndiceBM25:
    """Índice BM25 (k1=1.5, b=0.75) sobre raíces de los términos de cada fragmento."""

    def __init__(self, fragmentos: list[dict]) -> None:
        self.fragmentos = fragmentos
        self._frecuencias = [Counter(terminos(_texto_indexado(f))) for f in fragmentos]
        self._longitudes = [sum(c.values()) for c in self._frecuencias]
        self._media = sum(self._longitudes) / len(fragmentos) if fragmentos else 0.0
        self._df = Counter(t for c in self._frecuencias for t in c)

    @classmethod
    def desde_directorio(cls, ruta: Path = RUTA_DOCS) -> "IndiceBM25":
        """Construye el índice con las secciones de los .md de un directorio."""
        return cls(trocear(ruta))

    def _idf(self, termino: str) -> float:
        n, df = len(self.fragmentos), self._df[termino]
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def _puntuar(self, i: int, buscados: set[str]) -> float:
        frecuencias, longitud = self._frecuencias[i], self._longitudes[i]
        total = 0.0
        for termino in buscados:
            f = frecuencias[termino]
            if f:
                norma = K1 * (1 - B + B * longitud / self._media)
                total += self._idf(termino) * f * (K1 + 1) / (f + norma)
        return total

    def buscar(self, consulta: str, k: int = 3) -> list[dict]:
        """Hasta k fragmentos {doc, seccion, texto, puntuacion}, de mayor a menor."""
        buscados = set(terminos(consulta))
        puntuados = [(self._puntuar(i, buscados), f) for i, f in enumerate(self.fragmentos)]
        positivos = [(p, f) for p, f in puntuados if p > 0]
        positivos.sort(key=lambda par: (-par[0], par[1]["doc"], par[1]["seccion"]))
        return [{"doc": f["doc"], "seccion": f["seccion"], "texto": f["texto"],
                 "puntuacion": round(p, 4)} for p, f in positivos[:k]]
