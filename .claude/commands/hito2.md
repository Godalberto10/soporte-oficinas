---
description: Hito 2 — estado compartido, ScriptedModel y herramientas con su registro
---
# Hito 2 — Estado, modelo simulado y herramientas

Lee CLAUDE.md (secciones "Contrato del modelo", "Orquestación: traspaso",
"Herramientas", "Datos", "Servicios").
En este hito NO se escriben agentes, orquestador, recuperación BM25, `ModeloHF`
ni CLI. No se añaden dependencias.

## Objetivo
Tener las piezas sobre las que se montarán los agentes: las dataclasses del
estado compartido, el modelo guionizado para las pruebas y las herramientas
que consultan y modifican el estado simulado de la red.

## Ficheros esperados
- `src/soporte_oficinas/estado.py`
- `src/soporte_oficinas/modelo.py`
- `src/soporte_oficinas/herramientas.py`
- `tests/test_estado.py`, `tests/test_modelo.py`, `tests/test_herramientas.py`

## Decisiones de este hito
- `ModeloHF` se deja para el hito 6; aquí solo `Modelo` (Protocol) y `ScriptedModel`.
- `buscar_docs` se registra en el hito 3, junto con el índice BM25.
- Las herramientas trabajan sobre una clase `Red` que carga los tres JSON
  desde una ruta (`Red.desde_directorio(ruta)`, por defecto `data/`). Los
  cambios (reinicios, cierres, escalados) se hacen **en memoria**: nunca se
  escriben los JSON. Cada `Red` tiene su propia copia de los datos, para que
  cada ejecución de `orquestar()` empiece desde el estado inicial.
- `crear_herramientas(red) -> dict[str, Herramienta]` ata las funciones a una
  `Red` y conserva las firmas de CLAUDE.md (p. ej. `consultar_servicio(servicio, oficina)`).
- `ejecutar(herramientas, nombre, argumentos) -> dict` es el único punto de
  llamada: convierte en `ErrorHerramienta` una herramienta inexistente y unos
  argumentos que no encajan con la firma (comprobada con
  `inspect.signature(...).bind`, no capturando cualquier `TypeError`). Así el orquestador
  solo captura un tipo de error (R4).
- La confirmación y el guardarraíl NO van en las herramientas: son del
  orquestador (hito 5). Las herramientas solo validan argumentos.

## Criterios de aceptación
1. `estado.py` define `Paso`, `Accion`, `Estado` y `Resultado` como
   dataclasses tipadas con los campos de CLAUDE.md. `Estado.traza`,
   `Estado.acciones` y `Estado.citas` empiezan vacías y no se comparten entre
   instancias; `Estado.pasos` empieza en 0 y `Estado.final` en `None`.
   `Accion` tiene `herramienta` y `argumentos`.
   `Resultado` tiene `final`, `respuesta`, `citas`, `traza`, `tipo`,
   `prioridad` y `escalado` (id de escalado o `None`).
2. `modelo.py` define el `Protocol` `Modelo` con
   `generar(sistema, mensajes) -> str`. `ScriptedModel(respuestas)` devuelve las
   respuestas en orden, guarda las llamadas recibidas (`sistema`, `mensajes`)
   para poder inspeccionarlas y lanza `RuntimeError` cuando se agotan.
3. `herramientas.py` define `ErrorHerramienta`, la dataclass `Herramienta`
   (`nombre`, `descripcion`, `reversible`, `funcion`), `crear_herramientas(red)`
   y `ejecutar(herramientas, nombre, argumentos)`. Toda `descripcion` es no vacía.
4. Están registradas `consultar_servicio`, `consultar_equipo`,
   `buscar_tickets`, `crear_escalado`, `reiniciar_servicio` y `cerrar_ticket`.
   Solo `reiniciar_servicio` y `cerrar_ticket` tienen `reversible=False`.
5. Cada herramienta devuelve un `dict`:
   - `consultar_servicio("vpn", "MAD-01")` → `{"servicio": "vpn", "oficina": "MAD-01", "estado": "caido"}`.
   - `consultar_equipo("PC-VAL01-002")` devuelve la ficha del inventario.
   - `buscar_tickets(oficina=None, sintoma=None)` filtra por oficina y/o por
     síntoma (subcadena, sin distinguir mayúsculas); sin filtros, todos.
   - `crear_escalado` devuelve un id `ESC-NNNN` creciente.
   - `reiniciar_servicio` deja el servicio en `ok` (en memoria).
   - `cerrar_ticket` pasa el ticket a `cerrado` y guarda la resolución.
6. Lanzan `ErrorHerramienta` con mensaje legible: oficina, servicio, equipo
   o ticket inexistente; prioridad fuera de P1–P4; resumen o resolución vacíos;
   cerrar un ticket ya cerrado.
7. `ejecutar` lanza `ErrorHerramienta` (no `KeyError` ni `TypeError`) con una
   herramienta inexistente, un argumento que sobra o uno que falta.
8. Aislamiento: reiniciar un servicio en una `Red` no cambia otra `Red`
   cargada de los mismos ficheros, y `data/*.json` no cambia tras ejecutar
   las herramientas irreversibles.
9. Código en español, tipado, funciones cortas. `uv run pytest` en verde,
   sin red y sin `HF_TOKEN` (incluidas las pruebas de `test_datos.py`).

## Al terminar
Resume en una tabla qué prueba cubre cada criterio. No hagas commit.
