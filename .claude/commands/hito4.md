---
description: Hito 4 — bucle común de agente y los 4 agentes (clasificador, diagnostico, conocimiento, escalado)
---
# Hito 4 — Agentes

Lee CLAUDE.md (secciones "Contrato del modelo", "Agentes", "Prioridades",
"Herramientas" y las reglas 4 y 5 de "Reglas que garantiza el código").
En este hito NO se escribe el orquestador (traspaso entre agentes, tope global,
confirmación, guardarraíl, comprobación de citas, subida de prioridad):
eso es el hito 5. Tampoco `ModeloHF` ni CLI. No se añaden dependencias.

## Objetivo
Que cada agente, dado el `Estado` y un `Modelo`, haga su trabajo en varios
turnos (pensar → llamar herramientas permitidas → observar → responder) y
devuelva su objeto JSON validado, dejándolo todo en la traza.

## Ficheros esperados
- `src/soporte_oficinas/agentes.py`
- `tests/test_agentes.py`

## Orden de trabajo
1. Bucle común + agente **conocimiento** (porción vertical: usa `buscar_docs`).
   Pruebas en verde antes de seguir.
2. Agentes clasificador, diagnostico y escalado sobre el mismo bucle.

## Decisiones de este hito
- **Protocolo de turnos.** En cada turno el modelo devuelve un único objeto JSON:
  - llamada a herramienta: `{"herramienta": "<nombre>", "argumentos": {...}}`;
  - respuesta final: el objeto con las claves del contrato del agente.
  Se acepta el JSON dentro de un bloque ```json; cualquier otro texto alrededor
  se ignora. `extraer_json(texto) -> dict` lanza `ValueError` si no hay objeto.
- **Definición de agente** como dato: `Agente(nombre, instrucciones,
  herramientas: tuple[str, ...], claves: tuple[str, ...], validar)`.
  `AGENTES: dict[str, Agente]` con los 4 de CLAUDE.md.
- **Prompt de sistema generado por código** (`prompt_sistema(agente, herramientas)`):
  rol, claves del contrato, protocolo de turnos y, para cada herramienta
  permitida, su nombre, firma (`inspect.signature`) y `descripcion` del
  registro. Nunca aparecen herramientas no permitidas.
- **Mensajes:** el primero (`user`) lleva incidencia, oficina, ticket y lo ya
  averiguado del `Estado` (tipo, prioridad, causa, servicio…) en JSON. Cada
  respuesta del modelo se añade como `assistant` y cada observación como `user`.
- **`ejecutar_agente(agente, estado, modelo, herramientas, max_pasos=12)
  -> SalidaAgente`**, con `SalidaAgente(datos: dict | None, motivo)` y
  `motivo` ∈ {`ok`, `ilegible`, `tope`}:
  - cada respuesta del modelo y cada ejecución de herramienta suma 1 a
    `estado.pasos` y añade un `Paso` a `estado.traza`;
  - herramienta no permitida para el agente → observación de error, no se ejecuta;
  - `ErrorHerramienta` → observación de error, el agente sigue (regla 4);
  - JSON ilegible o que no cumple el contrato (faltan claves, valores fuera de
    rango) → observación con el motivo; 2 seguidas → `motivo="ilegible"`;
  - si `estado.pasos` llega a `max_pasos` → `motivo="tope"`.
- **Las herramientas irreversibles nunca se ejecutan dentro del bucle.**
  `conocimiento` las propone en su clave `accion`
  (`{"herramienta": "reiniciar_servicio"|"cerrar_ticket", "argumentos": {...}}`);
  si intenta llamarlas como turno, se anota una observación que le dice que
  las proponga en `accion`. Confirmar y ejecutar es del orquestador (hito 5).
- **Escalado:** tras su respuesta final válida, el código llama a
  `crear_escalado` con `resumen` y `prioridad` (y el ticket del estado) y lo
  registra en la traza como paso del agente `escalado`. Así siempre hay id.
- **Aplicar al estado:** cada agente copia su salida al `Estado`
  (clasificador → `tipo`, `prioridad`; diagnostico → `causa`, `servicio`;
  conocimiento → `procedimiento`, `citas` y, si hay acción, la añade a
  `acciones`). El escalado guarda su id en la salida.

## Validación de contratos (en código)
- clasificador: `tipo` ∈ tipos de CLAUDE.md, `prioridad` ∈ P1–P4, `motivo` texto no vacío.
- diagnostico: `causa` texto no vacío; `servicio` uno de los 7 servicios o `null`;
  `evidencias` lista de textos.
- conocimiento: `procedimiento` texto o `null`; `citas` lista de textos;
  `accion` `null` o un objeto con `herramienta` irreversible y `argumentos` dict.
- escalado: `resumen` texto no vacío; `probado` lista de textos; `prioridad` ∈ P1–P4.

## Criterios de aceptación
1. `extraer_json` acepta un objeto suelto, dentro de ```json y con texto
   alrededor; lanza `ValueError` con texto sin objeto o con una lista.
2. `prompt_sistema` de cada agente contiene sus claves y sus herramientas
   permitidas (con descripción) y ninguna otra herramienta del registro.
3. **Conocimiento, camino feliz:** con un `ScriptedModel` que primero llama a
   `buscar_docs` y luego responde, la salida es `ok`, el estado tiene
   `procedimiento` y `citas`, y la traza tiene 3 pasos (modelo, herramienta,
   modelo) con la observación real de `buscar_docs`.
4. **Conocimiento con acción:** una `accion` de `reiniciar_servicio` queda en
   `estado.acciones` y el servicio sigue sin reiniciar en la `Red`.
5. **Irreversible como turno:** si conocimiento llama a `reiniciar_servicio`
   directamente, no se ejecuta (la `Red` no cambia) y la traza lo anota.
6. **Herramienta no permitida:** clasificador llamando a `consultar_servicio`
   → observación de error, no se ejecuta, el agente sigue y termina `ok`.
7. **ErrorHerramienta como observación:** diagnostico consulta una oficina
   inexistente, recibe el error en la traza y luego responde bien → `ok`.
8. **Ilegible:** 1 respuesta ilegible seguida de una válida → `ok`;
   2 seguidas → `ilegible`. Una salida con claves que faltan o `tipo` inválido
   cuenta como ilegible.
9. **Tope:** con `max_pasos=3` y un modelo que solo llama herramientas →
   `motivo="tope"` y `estado.pasos == 3`.
10. **Clasificador y diagnostico** rellenan `tipo`/`prioridad` y
    `causa`/`servicio` en el estado. La prioridad del modelo se guarda tal
    cual (subirla es del hito 5).
11. **Escalado** crea el escalado en la `Red` (id `ESC-0001`) con la prioridad
    de su salida, y el id aparece en la salida y en la traza.
12. Los mensajes enviados al modelo (`ScriptedModel.llamadas`) incluyen la
    incidencia, lo averiguado por agentes anteriores y las observaciones.
13. Código en español, tipado, funciones cortas. `uv run pytest` en verde,
    sin red y sin `HF_TOKEN`.

## Al terminar
Resume en una tabla qué prueba cubre cada criterio. No hagas commit.
