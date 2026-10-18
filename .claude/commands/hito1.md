---
description: Hito 1 — datos simulados (data/) y base de conocimiento (docs/)
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(uv run pytest:*)
---

# Hito 1 — Datos y documentos

Lee CLAUDE.md (secciones "Datos", "Documentos", "Servicios", "Prioridades").
En este hito NO se escribe código del paquete salvo `tests/test_datos.py`.

## Objetivo
Crear el estado simulado de la red y la base de conocimiento sobre la que
trabajarán los agentes, con los tres casos difíciles del enunciado presentes.

## Ficheros esperados
- `data/servicios.json`, `data/inventario.json`, `data/tickets.json`
- `docs/`: 8+ artículos `kb-<tipo>-NN.md` + `catalogo-servicios.md`,
  `procedimiento-escalado.md`, `politica-reinicios.md`, `guia-prioridades.md`
- `tests/test_datos.py`

## Criterios de aceptación (todos comprobables en test_datos.py)
1. `servicios.json` tiene las 4 oficinas (MAD-01, MAD-02, BCN-01, VAL-01) y,
   en cada una, los 7 servicios de CLAUDE.md con valor `ok|degradado|caido`.
2. Al menos un servicio crítico `caido` en 2+ oficinas a la vez (avería
   multioficina) y al menos uno `degradado`.
3. `inventario.json`: 12+ equipos; cada uno con `id`, `tipo`, `oficina`,
   `modelo`, `estado`; toda `oficina` existe en servicios.json.
4. `tickets.json`: 8+ tickets con `id` (`T-NNNN`), `oficina`, `sintoma`,
   `estado` (`abierto|cerrado|reabierto`), `reaperturas` (entero ≥ 0).
   - Al menos 1 ticket con `reaperturas >= 1`.
   - Al menos 2 tickets con el **mismo** `sintoma` en oficinas cuyo estado
     de servicios lleve a causas distintas (p. ej. "no tengo internet":
     uno por `vpn` caída, otro por un equipo con tarjeta de red averiada).
5. Cada artículo `kb-*.md` tiene exactamente las secciones `## Síntomas`,
   `## Causa` y `## Pasos`; cubre entre todos los 5 tipos de CLAUDE.md.
6. Los 4 documentos de política son coherentes con CLAUDE.md:
   misma lista de críticos, mismo horario (L-V 08:00–18:00), mismas reglas P1–P4.
7. Contenido realista y en español; ningún dato personal real.
8. `uv run pytest` en verde, sin red.

## Al terminar
Resume en una tabla qué fichero cubre cada criterio. No hagas commit.

## Qué reviso yo
1. Que los tres casos difíciles están en los datos: mismo síntoma con causa distinta (T-0001/T-0002), ticket reabierto (T-0007) y ERP caído en MAD-02 y BCN-01.
2. Que las políticas de `docs/` dicen lo mismo que CLAUDE.md (críticos, horario, P1–P4); lo comprueba `test_datos.py`.
3. Que los datos son simulados y no hay datos personales reales.
