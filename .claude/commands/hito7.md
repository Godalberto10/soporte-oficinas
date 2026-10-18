---
description: Hito 7 — evaluación con mis casos de resultado y trayectoria esperados
---
# Hito 7 — Evaluación

Lee CLAUDE.md (secciones "Pruebas y evaluación", "Orquestación: traspaso",
"Prioridades", "Datos") y `orquestar` y `trayectoria` en `orquestador.py`.
En este hito NO se cambia la lógica de agentes, orquestador, modelos ni
`docs/`, y NO se escribe la web. No se añaden dependencias.
Si un caso no da lo esperado, NO se toca el código ni el caso para que pase:
se marca como fallo conocido y se me explica por qué falla.

## Objetivo
Comprobar si el sistema llega al resultado que yo espero (`final`, `tipo`,
`prioridad`) por el camino que yo espero (secuencia de agentes), y tener una
tabla de resultados para el informe.

## Ficheros esperados
- `src/soporte_oficinas/evaluacion.py` (casos como datos + ejecutar y comparar)
- `tests/test_evaluacion.py`

## Decisiones de este hito
- **Lo esperado lo he definido yo** aplicando mis reglas, sin mirar el código
  (oráculo independiente). Es la tabla de abajo y no se cambia para que pase.
- **El guion solo hace de modelo**: cada caso lleva las respuestas de un
  `ScriptedModel` que imitan a un modelo que se porta bien, o a uno tramposo
  en los casos 9 y 10. Así se comprueban mis reglas, no la suerte del modelo.
- **Dos pasadas:**
  1. `ScriptedModel` con guion: los 11 casos.
  2. `ModeloSimulado` sin guion: los casos 1–8 y 11 (lo que verá quien use
     el programa sin token). Espero que fallen el 7 y el 11 por los huecos
     del simulado que ya conozco; si fallan, quedan como fallo conocido.
- **Sin modelo real en la evaluación:** gastaría créditos de HF. Las dos
  trazas reales del informe se sacan aparte, con la orden del programa.
- `python -m soporte_oficinas.evaluacion` imprime la tabla de resultados en
  Markdown (caso, esperado, obtenido, ✔/✘) para el informe.

## Mis casos (reloj fijo: lunes 10:00)
| # | Caso | Oficina / ticket | Final | Tipo | Prior. | Trayectoria |
|---|---|---|---|---|---|---|
| 1 | "no tengo internet", confirma | MAD-01 / T-0001 | resuelto | red | P1 | C-D-K |
| 2 | "no tengo internet", rechaza | MAD-01 / T-0001 | escalado | red | P1 | C-D-K-E |
| 3 | "no tengo internet" (tarjeta rota) | VAL-01 / T-0002 | resuelto | red | P3 | C-D-K |
| 4 | "la impresora no imprime" (reabierto) | MAD-02 / T-0007 | escalado | impresora | P4 | C-D-E |
| 5 | "no puedo entrar en el ERP" (varias oficinas; modelo dice P2) | MAD-02 / T-0004 | escalado | acceso_aplicacion | P1 | C-D-E |
| 6 | "el correo tarda mucho en llegar" (modelo dice P4), confirma | BCN-01 / T-0006 | resuelto | correo | P2 | C-D-K |
| 7 | "¿me recomiendas un restaurante?" | MAD-01 | rechazado | fuera_de_ambito | — | C |
| 8 | "no tengo internet" | SEV-01 (no existe) | rechazado | — | — | — |
| 9 | cita inventada `docs/kb-red-07.md#Pasos` | MAD-01 | escalado | red | P1 | C-D-K-E |
| 10 | propone reiniciar `erp` (diagnosticado `vpn`) | MAD-01 | escalado | red | P1 | C-D-K-E |
| 11 | "me va lento el ordenador" | MAD-01 | resuelto | hardware | P4 | C-D-K |

C = clasificador, D = diagnostico, K = conocimiento, E = escalado.

## Criterios de aceptación
1. Prueba parametrizada (un id por caso) que, con guion, compara `final`,
   `tipo`, `prioridad` y `trayectoria` con mi tabla.
2. Además del resultado, se comprueba el efecto en los casos de seguridad:
   - 1: la `vpn` de MAD-01 queda `ok`; 2: sigue `caido` y no hay paso con
     `reiniciar_servicio` en la traza (R1);
   - 8: el modelo no se llama ninguna vez;
   - 9: el resultado no contiene la cita inventada (R5);
   - 10: `confirmar` no se llama y el `erp` no cambia (R2).
3. Pasada con `ModeloSimulado` sobre los casos 1–8 y 11; los que fallen se
   marcan `xfail` con el motivo (no se ocultan).
4. `python -m soporte_oficinas.evaluacion` imprime la tabla con el total de
   aciertos por columna.
5. Código en español, tipado, funciones cortas. `uv run pytest` en verde,
   sin red y sin `HF_TOKEN`.

## Al terminar
Pega la tabla de resultados de las dos pasadas y explícame cada fallo:
¿es del código o de mi expectativa? No hagas commit.
