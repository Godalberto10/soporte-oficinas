---
description: Hito 3 — índice BM25 propio sobre docs/ y herramienta buscar_docs
---
# Hito 3 — Recuperación BM25 y `buscar_docs`

Lee CLAUDE.md (secciones "Herramientas", "Documentos" y la regla 5 "Citas
comprobadas").
En este hito NO se escriben agentes, orquestador, `ModeloHF` ni CLI. No se
añaden dependencias: BM25 se implementa a mano (nada de `rank_bm25`,
scikit-learn ni similares).

## Objetivo
Que los agentes puedan recuperar fragmentos de la base de conocimiento y
citarlos con un formato que el orquestador pueda comprobar en el hito 5.

## Ficheros esperados
- `src/soporte_oficinas/recuperacion.py`
- `src/soporte_oficinas/herramientas.py` (añadir `buscar_docs` al registro)
- `tests/test_recuperacion.py` y ampliar `tests/test_herramientas.py`

## Decisiones de este hito
- **Unidad de recuperación = sección `## ` de un documento.** Cada fragmento
  es `{"doc": "docs/<fichero>.md", "seccion": "<título de la sección>",
  "texto": "<contenido>"}`. El texto que se indexa incluye también el título
  `# ` del documento, para que "Pasos" de kb-red-01 se distinga de "Pasos"
  de kb-correo-01.
- **Formato de cita:** `docs/<fichero>.md#<seccion>`, p. ej.
  `docs/kb-red-01.md#Pasos`. `cita(fragmento) -> str` lo construye.
- **Tokenización:** minúsculas, sin tildes (`unicodedata`), separando por lo
  que no sea letra o dígito, y quitando una lista corta de palabras vacías
  en español. Así "contraseña" y "contrasena" coinciden.
- **BM25** con `k1=1.5`, `b=0.75` e IDF `log(1 + (N - df + 0.5) / (df + 0.5))`.
  Los fragmentos con puntuación 0 no se devuelven. Empates: por `doc` y
  `seccion`, para que el orden sea determinista.
- `crear_herramientas(red, indice=None)`: si no se pasa índice se construye
  uno sobre `docs/`. `buscar_docs` devuelve `{"fragmentos": [...]}` (todas las
  herramientas devuelven `dict`) y es reversible.
- Registrar qué fragmentos se han recuperado en cada ejecución (para la
  regla 5) es trabajo del orquestador, en el hito 5. Aquí no.

## Criterios de aceptación
1. `recuperacion.py` define `tokenizar(texto)`, `trocear(ruta_docs)` (lista
   de fragmentos), la clase `IndiceBM25` con `desde_directorio(ruta)` y
   `buscar(consulta, k=3)`, y `cita(fragmento)`.
2. `trocear` produce un fragmento por cada sección `## ` de cada `.md` de
   `docs/`; cada artículo `kb-*` aporta exactamente 3 (Síntomas, Causa, Pasos).
3. `tokenizar("¿Contraseña CADUCADA?")` == `tokenizar("contrasena caducada")`,
   y las palabras vacías ("el", "de", "la", "que"…) no aparecen.
4. BM25 correcto sobre un corpus pequeño de prueba (en `tmp_path`): un término
   raro pesa más que uno frecuente, y con la misma frecuencia el fragmento más
   corto puntúa más. Una consulta sin términos del corpus devuelve `[]`.
5. Calidad sobre los documentos reales (el primer resultado es el esperado):
   | Consulta | Documento esperado |
   |---|---|
   | "no tengo internet, la vpn está caída" | `kb-red-01.md` |
   | "tarjeta de red averiada, cable desconectado" | `kb-red-02.md` |
   | "atasco de papel en la impresora" | `kb-impresora-01.md` |
   | "contraseña caducada, cuenta bloqueada" | `kb-acceso_aplicacion-02.md` |
   | "buzón lleno, no recibo correos" | `kb-correo-02.md` |
   | "tiempos de respuesta por prioridad" | `catalogo-servicios.md` |
   | "reiniciar un servicio crítico en horario laboral" | `politica-reinicios.md` |
6. `buscar(consulta, k)` devuelve como mucho `k` fragmentos, ordenados de
   mayor a menor puntuación, y el mismo resultado en dos llamadas iguales.
7. `buscar_docs` está en el registro con descripción no vacía y
   `reversible=True`; `ejecutar(h, "buscar_docs", {"consulta": "vpn caída"})`
   devuelve `{"fragmentos": [...]}` con claves `doc`, `seccion`, `texto`.
8. `buscar_docs` lanza `ErrorHerramienta` con consulta vacía o que no es
   texto, y con `k` que no es entero entre 1 y 10.
9. `cita` de cada fragmento devuelto tiene la forma `docs/<fichero>.md#<seccion>`
   y el fichero existe.
10. Código en español, tipado, funciones cortas. `uv run pytest` en verde,
    sin red y sin `HF_TOKEN`.

## Al terminar
Resume en una tabla qué prueba cubre cada criterio. No hagas commit.
