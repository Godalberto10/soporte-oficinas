---
description: Hito 5 — orquestador con traspaso y reglas R1–R5 garantizadas en código
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(uv run pytest:*)
---
# Hito 5 — Orquestador y reglas de seguridad

Lee CLAUDE.md (secciones "Prioridades", "Servicios", "Orquestación: traspaso",
"Reglas que garantiza el código") y `src/soporte_oficinas/agentes.py`.
En este hito NO se escribe `ModeloHF`, CLI ni web. No se añaden dependencias.

## Objetivo
`orquestar()` une los 4 agentes con el traspaso de CLAUDE.md y garantiza en
código, no en el prompt, las reglas R1–R5. Devuelve un `Resultado` con la
respuesta al empleado, las citas válidas y la traza completa.

## Ficheros esperados
- `src/soporte_oficinas/orquestador.py`
- `tests/test_orquestador.py`
- (si hace falta) ajuste mínimo en `agentes.py`, con su prueba

## Decisiones de este hito
- **Firma:** la de CLAUDE.md más dos parámetros opcionales solo con nombre
  para las pruebas: `red: Red | None = None` (por defecto, una `Red` nueva
  cargada de `data/`) e `indice: IndiceBM25 | None = None`.
- **`final="rechazado"`** solo en dos casos:
  - entrada no válida (oficina o ticket inexistentes), sin llamar al modelo;
  - el clasificador devuelve `tipo="fuera_de_ambito"` (la petición no es de
    soporte de oficinas): se para tras el clasificador, sin diagnóstico.
  Una acción que el usuario rechaza o no le parece bien **no** da `rechazado`:
  se escala a segundo nivel para que se busque otra solución (regla de traspaso).
- **Nuevo tipo `fuera_de_ambito`** (ya en CLAUDE.md): se añade a `TIPOS` en
  `agentes.py` y a las instrucciones del clasificador, distinguiéndolo de
  `otro` (incidencia de soporte sin categoría).
- **Anotaciones del orquestador** (subida de prioridad, citas eliminadas,
  guardarraíl, rechazo, traspaso) son `Paso(agente="orquestador")` y **no
  cuentan** para el tope: solo cuentan respuestas del modelo y herramientas.
  `Paso.n` es la posición en la traza.
- **Prioridad mínima** (`prioridad_minima(red, oficina, servicio)`), aplicada
  tras el diagnóstico con `estado.servicio`:
  - el servicio no está `ok` en 2+ oficinas → **P1** (multioficina);
  - servicio crítico `caido` en la oficina → **P1**; `degradado` → **P2**;
  - si no, no hay mínimo. Solo se sube, nunca se baja, y se anota en la traza.
- **Horario laboral:** `en_horario(dt)` → lunes a viernes, 08:00 ≤ hora < 18:00.
- **Respuesta al empleado** (`Resultado.respuesta`) la redacta el código:
  - resuelto: procedimiento + "Fuentes:" con las citas válidas;
  - escalado: id `ESC-NNNN`, prioridad y tiempo de primera respuesta del
    catálogo (P1 15 min, P2 30 min, P3 2 h, P4 1 día laborable);
  - rechazado: por qué no se tramita (entrada no válida o fuera del ámbito);
  - tope: que no se ha podido completar y que se revisará.

## Flujo (en código)
1. Validar oficina y ticket → si no existen, `rechazado`.
2. **clasificador**. `ilegible` → escalado; `tope` → `tope_alcanzado`;
   `tipo="fuera_de_ambito"` → `rechazado`.
3. **diagnostico**. Igual. Después, subir prioridad si hace falta.
4. Traspaso tras diagnóstico:
   - ticket con `reaperturas >= 1` → **escalado**;
   - avería multioficina → **escalado** con prioridad P1.
5. **conocimiento**. Comprobar citas (R5). Sin procedimiento o sin citas
   válidas → **escalado**.
6. Si hay `accion`: guardarraíl (R2) → si bloquea, anotar y **escalado** sin
   llamar a `confirmar`. Si pasa, `confirmar(accion)`:
   - `False` → anotar rechazo, no ejecutar, **escalado**;
   - `True` → ejecutar; si da `ErrorHerramienta`, **escalado**; si va bien, `resuelto`.
7. Sin `accion` y con citas válidas → `resuelto`.
8. **escalado**: si el agente acaba `ilegible`, el código crea igualmente un
   escalado con un resumen automático (incidencia, causa) y la prioridad del
   estado (o P3), para que siempre haya id. Si acaba en `tope` → `tope_alcanzado`.

## Reglas R1–R5 (cada una con prueba que fallaría si el código fallara)
- **R1 Confirmación:** una irreversible solo se ejecuta si `confirmar` devuelve
  True. Con False, la `Red` no cambia y en la traza no hay ningún paso con
  `herramienta="reiniciar_servicio"`/`"cerrar_ticket"`; final `escalado`.
- **R2 Guardarraíl** (`guardarrail(accion, estado, red, ahora) -> str | None`,
  devuelve el motivo del bloqueo): `reiniciar_servicio` de un crítico en
  horario laboral exige `servicio == estado.servicio` y estado `caido` o
  `degradado` en ese momento. Además, siempre: la oficina de la acción es la
  del estado y máximo 1 reinicio por servicio y ejecución. Si bloquea,
  `confirmar` no se llama.
- **R3 Tope:** 12 pasos globales (el contador sigue entre agentes); al
  superarlo, `final="tope_alcanzado"`.
- **R4 Errores como observaciones:** ya en el bucle (hito 4); aquí, `ilegible`
  de cualquier agente → escalado.
- **R5 Citas comprobadas:** una cita es válida solo si `docs/<fichero>.md#<seccion>`
  está entre los fragmentos devueltos por `buscar_docs` **en esta ejecución**
  (se leen de la traza). Las inválidas se eliminan y se anota cuáles. Sin
  citas válidas no hay `resuelto`.

## Criterios de aceptación
1. **Resuelto con reinicio** (MAD-01, "no tengo internet", lunes 10:00,
   `confirmar` → True): trayectoria clasificador → diagnostico → conocimiento;
   `final="resuelto"`, `tipo="red"`, `prioridad="P1"`, vpn en `ok`, cita
   `docs/kb-red-01.md#Pasos` en la respuesta.
2. **R1:** mismo caso con `confirmar` → False: vpn sigue `caido`, ningún paso
   ejecutado de `reiniciar_servicio`, trayectoria termina en escalado,
   `final="escalado"` con id.
3. **R2:** en horario laboral se bloquea sin llamar a `confirmar` (un
   `confirmar` que falla si se llama): reiniciar `erp` cuando el diagnosticado
   es `vpn`; reiniciar un crítico `ok`; reiniciar en otra oficina. Fuera de
   horario (sábado) el primer caso sí pide confirmación. `guardarrail` bloquea
   un segundo reinicio del mismo servicio.
4. **R3:** un modelo que solo llama herramientas → `tope_alcanzado` y
   `estado.pasos` no supera 12; las anotaciones del orquestador no cuentan.
5. **R4:** 2 respuestas ilegibles del clasificador → `final="escalado"`; si
   el agente escalado también es ilegible, igualmente hay id de escalado.
6. **R5:** una cita inventada (no recuperada) se elimina y se anota; si era
   la única, el final es `escalado`, no `resuelto`.
7. **Prioridad:** el clasificador dice P3 con `vpn` caída → sube a P1 y se
   anota en la traza; nunca se baja una prioridad mayor.
8. **Mismo síntoma, causa distinta:** "no tengo internet" en VAL-01 con
   diagnóstico de equipo (`servicio=None`) → no hay subida de prioridad ni
   reinicio; con procedimiento citado de `kb-red-02.md` → `resuelto`.
9. **Ticket reabierto:** T-0007 → tras diagnóstico pasa directo a escalado
   (conocimiento no se ejecuta).
10. **Multioficina:** `erp` caído en MAD-02 y BCN-01 → escalado con P1 aunque
    el clasificador dijera P2.
11. **Rechazado:** oficina `SEV-01` o ticket `T-9999` → `rechazado` y el modelo
    no se llama. "¿Me recomiendas un restaurante?" con el clasificador devolviendo
    `fuera_de_ambito` → `rechazado`, trayectoria solo clasificador, sin escalado.
    Una acción rechazada por el usuario nunca da `rechazado` (criterio 2).
12. `en_horario`: viernes 17:59 sí; viernes 18:00 no; sábado 10:00 no; lunes 08:00 sí.
13. Código en español, tipado, funciones cortas. `uv run pytest` en verde,
    sin red y sin `HF_TOKEN`.

## Al terminar
Resume en una tabla qué prueba cubre cada criterio y cada regla R1–R5. No hagas commit.

## Qué reviso yo
1. Que cada regla R1–R5 tiene una prueba que falla si se rompe la regla (mutaciones).
2. Que las trayectorias de los tres casos difíciles son las de CLAUDE.md.
3. Que con `confirmar` falso la red no cambia y la acción no aparece en la traza.
