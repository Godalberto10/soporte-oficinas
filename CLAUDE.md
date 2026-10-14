# Soporte técnico de una red de oficinas — sistema multiagente

## Objetivo
Resolver incidencias de primer nivel de los empleados (sin conexión, impresora,
acceso a una aplicación…) con varios pasos de diagnóstico sobre un estado
simulado de servicios, y escalar a segundo nivel las que no se resuelven.
Entrada: texto de la incidencia + oficina + id de ticket opcional.
Salida: `Resultado` con estado final, respuesta al empleado con citas y traza.

## Entorno y órdenes
- Python 3.12, uv. Sin frameworks de agentes (ni LangGraph ni LangChain).
- Dependencias permitidas: `huggingface-hub`, `python-dotenv`; dev: `pytest`.
  Cualquier otra se pide antes (`uv add` está en ask).
- Ejecutar: `uv run soporte-oficinas "<incidencia>" --oficina MAD-01 [--ticket T-0007] [--modelo simulado|hf]`
- Pruebas: `uv run pytest` — sin red y sin `HF_TOKEN`.
- El token se lee de `.env` (`HF_TOKEN`) con python-dotenv. Nunca se lee,
  imprime ni copia `.env`; nunca aparece una clave en el código.

## Estructura
```
src/soporte_oficinas/
  estado.py        Estado, Paso, Accion, Resultado (dataclasses)
  modelo.py        Protocolo Modelo, ScriptedModel, ModeloHF
  herramientas.py  herramientas + registro con descripción y reversible
  recuperacion.py  índice BM25 propio sobre docs/
  agentes.py       clasificador, diagnostico, conocimiento, escalado
  orquestador.py   orquestar(): traspaso, tope de pasos, guardarraíles
  cli.py           main() de la orden soporte-oficinas
data/   inventario.json, servicios.json, tickets.json
docs/   base de conocimiento en Markdown (ver "Documentos")
tests/  pruebas pytest con ScriptedModel
```

## Contrato del modelo
```python
class Modelo(Protocol):
    def generar(self, sistema: str, mensajes: list[dict]) -> str: ...
```
- `ScriptedModel(respuestas: list[str])`: devuelve las respuestas en orden;
  si se agotan lanza `RuntimeError`. Solo para pruebas.
- `ModeloHF`: `huggingface_hub.InferenceClient`, modelo en `HF_MODEL`
  (por defecto se fija en el hito 6), `temperature=0`, `max_tokens=512`.
- Todo agente pide al modelo **un único objeto JSON** con las claves de su contrato.

## Agentes (rol · salida JSON · herramientas permitidas)
| Agente | Decide | Salida | Herramientas |
|---|---|---|---|
| clasificador | tipo y prioridad | `{"tipo", "prioridad", "motivo"}` | `buscar_tickets` |
| diagnostico | causa probable | `{"causa", "servicio", "evidencias": [..]}` | `consultar_servicio`, `consultar_equipo`, `buscar_tickets` |
| conocimiento | procedimiento | `{"procedimiento", "citas": [..], "accion": null \| {..}}` | `buscar_docs`, `reiniciar_servicio`, `cerrar_ticket` |
| escalado | traspaso a nivel 2 | `{"resumen", "probado": [..], "prioridad"}` | `crear_escalado` |

- `tipo` ∈ {`red`, `impresora`, `acceso_aplicacion`, `correo`, `hardware`, `otro`}.
- Un agente solo puede llamar a sus herramientas; otra llamada es una
  observación de error, no se ejecuta.

## Prioridades (las aplica el clasificador; el código las valida)
- **P1**: afecta a más de una oficina, o un servicio crítico está `caido`.
- **P2**: afecta a una oficina entera, o un servicio crítico está `degradado`.
- **P3**: un empleado no puede trabajar y no hay alternativa.
- **P4**: molestia con alternativa (otra impresora, webmail…).
- Si el modelo devuelve una prioridad menor que la que exigen los datos
  (p. ej. P3 con un crítico `caido`), el código la sube y lo anota en la traza.

## Servicios
- Críticos: `vpn`, `correo`, `erp`, `ficheros`, `intranet`.
- No críticos: `impresion`, `wifi_invitados`.
- Horario laboral: lunes a viernes, 08:00–18:00 (hora local, reloj inyectable).

## Orquestación: traspaso
`clasificador → diagnostico → conocimiento → (fin "resuelto" | escalado)`
Justificación: el flujo de soporte es secuencial y cada especialista recibe la
conversación con lo ya averiguado; no hace falta un supervisor que replanifique.
Reglas de traspaso (en código, no en el prompt):
- ticket con `reaperturas >= 1` → tras diagnóstico pasa directo a escalado.
- causa que afecta a más de una oficina → escalado con P1.
- conocimiento sin procedimiento citado, o acción rechazada → escalado.

```python
def orquestar(incidencia: str, oficina: str, modelo: Modelo,
              confirmar: Callable[[Accion], bool],
              ahora: Callable[[], datetime] = datetime.now,
              ticket: str | None = None, max_pasos: int = 12) -> Resultado
```
- `Estado` compartido: incidencia, oficina, ticket, tipo, prioridad, causa,
  servicio, procedimiento, citas, acciones, traza: list[Paso], pasos, final.
- `Paso`: n, agente, herramienta | None, argumentos, observacion.
- `final` ∈ {`resuelto`, `escalado`, `tope_alcanzado`, `rechazado`}.

## Herramientas (nombre · argumentos · reversible)
- `consultar_servicio(servicio, oficina)` → estado `ok|degradado|caido` · sí
- `consultar_equipo(id_equipo)` → ficha del inventario · sí
- `buscar_tickets(oficina=None, sintoma=None)` → tickets coincidentes · sí
- `buscar_docs(consulta, k=3)` → `[{doc, seccion, texto}]` · sí
- `crear_escalado(ticket, resumen, prioridad)` → id de escalado · sí
- `reiniciar_servicio(servicio, oficina)` · **NO** (irreversible)
- `cerrar_ticket(ticket, resolucion)` · **NO** (irreversible)
Cada herramienta tiene `descripcion` en el registro; devuelve dict o lanza
`ErrorHerramienta`.

## Reglas que garantiza el código (no el prompt)
1. **Confirmación**: una herramienta irreversible solo se ejecuta si
   `confirmar(accion)` devuelve True; si devuelve False, no aparece en la
   traza como ejecutada y el final es `escalado` o `rechazado`.
2. **Guardarraíl**: `reiniciar_servicio` de un servicio crítico en horario
   laboral exige además que `servicio == estado.servicio` diagnosticado y que
   ese servicio esté `caido` o `degradado`; si no, se bloquea sin preguntar.
   Máximo 1 reinicio por servicio y ejecución.
3. **Tope de pasos**: 12 pasos (cada respuesta del modelo o herramienta
   cuenta uno). Al superarlo, `final = "tope_alcanzado"`.
4. **Errores como observaciones**: `ErrorHerramienta`, herramienta no
   permitida y JSON ilegible se añaden a la traza como observación y el
   agente sigue. 2 respuestas ilegibles seguidas del mismo agente → escalado.
5. **Citas comprobadas**: toda cita `docs/<fichero>.md#<seccion>` debe estar
   entre los fragmentos recuperados en esa ejecución; si no, se elimina y se
   anota. Sin citas válidas no hay "resuelto".

## Datos (`data/`)
- `servicios.json`: `{"<oficina>": {"<servicio>": "ok|degradado|caido"}}`
- `inventario.json`: `[{"id", "tipo", "oficina", "modelo", "estado"}]`
- `tickets.json`: `[{"id", "oficina", "sintoma", "estado", "reaperturas"}]`
- Oficinas: `MAD-01`, `MAD-02`, `BCN-01`, `VAL-01`.
- Casos obligatorios en los datos: dos incidencias con el mismo síntoma y
  causa distinta; un ticket reabierto; una avería en varias oficinas.

## Documentos (`docs/`, mínimo 12)
- 8 o más artículos `kb-<tipo>-NN.md` con secciones `## Síntomas`, `## Causa`,
  `## Pasos`.
- `catalogo-servicios.md` (tiempos de respuesta por prioridad),
  `procedimiento-escalado.md`, `politica-reinicios.md`, `guia-prioridades.md`.

## Pruebas y evaluación
- Pruebas con `ScriptedModel` y `confirmar` falso o verdadero; reloj fijo.
- Cada requisito R1–R5 tiene al menos una prueba que fallaría si el código fallara.
- Evaluación (4+ casos) en `tests/test_evaluacion.py`: resultado esperado
  (`final`, tipo, prioridad) y trayectoria esperada (secuencia de agentes).

## Interfaz web (último hito)
Streamlit en `app.py`, arranque `uv run streamlit run app.py`. Solo llama a
`orquestar()`; `confirmar` es un botón. Sin lógica de agentes en la web.

## Forma de trabajar
- Un hito por orden en `.claude/commands/`; no se adelanta trabajo de otro hito.
- Cada cambio de código va con su prueba; `uv run pytest` en verde al cerrar.
- Código en español (nombres y docstrings), tipado, funciones cortas.
- No hacer: leer `.env`, añadir dependencias sin pedirlo, confiar una regla
  de seguridad solo al prompt, poner lógica en la web.
