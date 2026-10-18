---
description: Hito 7b — arreglar lo que encontró mi evaluación (rechazo, equipo lento, simulado)
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(uv run pytest:*), Bash(uv run python -m soporte_oficinas.evaluacion:*)
---
# Hito 7b — Arreglos tras la evaluación

Lee CLAUDE.md, `tests/test_evaluacion.py` (los `xfail` y sus motivos) y la
entrada "Hito 7" de `worklog.md`.
En este hito NO se cambian los casos ni lo esperado de la evaluación, ni las
reglas R1–R5, ni la web. No se añaden dependencias.

## Objetivo
Que los 5 fallos conocidos de mi evaluación pasen por haber arreglado su
causa, no por haber cambiado la prueba.

## Ficheros esperados
- `src/soporte_oficinas/orquestador.py` (rechazo sin prioridad)
- `docs/kb-hardware-03.md` (nuevo)
- `src/soporte_oficinas/modelo.py` (`ModeloSimulado`)
- `tests/test_evaluacion.py` (quitar los `xfail` arreglados), y pruebas nuevas
  en `tests/test_orquestador.py` y `tests/test_modelo.py`

## Decisiones (mías)
- **D1 — Un rechazo no tiene prioridad.** Lo que no se tramita no se prioriza:
  con `final="rechazado"`, `Resultado.prioridad` es `None` (el tipo
  `fuera_de_ambito` se conserva).
- **Artículo `kb-hardware-03.md` "El equipo va lento"**, con `## Síntomas`
  (frases de empleado: "me va lento el ordenador", "el PC se cuelga"…),
  `## Causa` y `## Pasos`: reiniciar el equipo, cerrar programas que no se
  usan y, si sigue igual, contactar con el equipo técnico (escalar).
- **ModeloSimulado** (es el que usará la web pública):
  - más palabras clave de hardware: ordenador, pc, equipo, lento, ratón…;
  - si no encaja en ningún tipo: `otro` solo si suena a soporte (no funciona,
    error, fallo, problema, no puedo, programa…); si no, `fuera_de_ambito`;
  - prioridad inicial P4 para impresora (suele haber otra disponible, D2) y P3
    para el resto; el orquestador la sigue subiendo con los datos;
  - conocimiento solo cita artículos `kb-<tipo>-NN.md` de su tipo; si no hay
    ninguno entre los recuperados, no da procedimiento (y se escala).

## Criterios de aceptación
1. Caso 7 con guion: `rechazado`, `fuera_de_ambito`, sin prioridad.
   Prueba en el orquestador: un rechazo no conserva la prioridad del clasificador.
2. `kb-hardware-03.md` cumple las pruebas de `test_datos.py` (3 secciones) y
   la búsqueda "me va lento el ordenador" lo devuelve primero.
3. Simulado: "¿me recomiendas un restaurante?" → `fuera_de_ambito`;
   "me va lento el ordenador" → `hardware`; "la impresora no imprime" → P4;
   "no tengo internet" sigue siendo `red` con P3.
4. Simulado: con fragmentos de otro tipo solamente, `procedimiento` es `null`.
5. En `test_evaluacion.py` desaparecen los 5 `xfail` y todos los casos pasan
   en las dos pasadas, sin cambiar ni un valor esperado.
6. `uv run pytest` en verde, sin red y sin `HF_TOKEN`.

## Al terminar
Pega las dos tablas de evaluación y una tabla criterio → prueba. No hagas commit.

## Qué reviso yo
1. Que los `xfail` desaparecen porque se arregla la causa, no la prueba.
2. Que ningún valor esperado de la evaluación ha cambiado.
3. Que "me va lento el ordenador" da el procedimiento de `kb-hardware-03`.
