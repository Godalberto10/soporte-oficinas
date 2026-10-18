---
description: Hito 6 — ModeloHF (Hugging Face), ModeloSimulado y la orden soporte-oficinas
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(uv run pytest:*)
---
# Hito 6 — Modelo real y línea de órdenes

Lee CLAUDE.md (secciones "Entorno y órdenes", "Contrato del modelo") y
`src/soporte_oficinas/modelo.py`, `orquestador.py`.
En este hito NO se escribe la evaluación (hito 7) ni la web (hito 8). No se
añaden dependencias (`huggingface-hub` y `python-dotenv` ya están).
**Nunca leer, imprimir ni copiar `.env`.** Las pruebas no usan red ni `HF_TOKEN`.

## Objetivo
Poder atender una incidencia desde la terminal, con el modelo real de Hugging
Face o con un modelo simulado que no necesita token:
`uv run soporte-oficinas "no tengo internet" --oficina MAD-01 [--ticket T-0001] [--modelo simulado|hf]`

## Ficheros esperados
- `src/soporte_oficinas/modelo.py` (añadir `ModeloHF` y `ModeloSimulado`)
- `src/soporte_oficinas/cli.py`
- `pyproject.toml`: el script `soporte-oficinas` apunta a `soporte_oficinas.cli:main`
- `tests/test_modelo_hf.py`, `tests/test_cli.py`

## Decisiones de este hito
- **`ModeloHF(modelo=None, cliente=None)`:**
  - carga `.env` con `load_dotenv()` y lee `HF_TOKEN` y `HF_MODEL` de
    `os.environ`; sin `HF_TOKEN` lanza `RuntimeError` con un mensaje que dice
    cómo configurarlo (sin mostrar ningún valor);
  - usa `InferenceClient(model, token)`; `cliente` permite inyectar uno falso
    en las pruebas;
  - `generar()` llama a `chat_completion` con `[{"role": "system", ...}] +
    mensajes`, `temperature=0`, `max_tokens=512`, y devuelve el texto;
  - un fallo de red o del proveedor se reintenta 1 vez; si vuelve a fallar,
    `RuntimeError` con el motivo (nunca con el token).
- **Modelo por defecto (`HF_MODEL`):** se fija en este hito. Candidato:
  `Qwen/Qwen2.5-72B-Instruct` (buen JSON y español, disponible en Inference
  Providers). Se confirma con una ejecución real **que lanzo yo** (el
  programa está en `ask` porque gasta mi token); si falla, se prueba
  `meta-llama/Llama-3.3-70B-Instruct`. El elegido se escribe en CLAUDE.md.
- **`ModeloSimulado`** (no es `ScriptedModel`): modelo determinista por reglas
  para demostrar el sistema sin token. Identifica el agente por el prompt de
  sistema (`«clasificador»`, …) y responde:
  - clasificador: tipo por palabras clave (internet/vpn → red, imprim → impresora,
    ERP/contraseña → acceso_aplicacion, correo → correo, portátil/monitor →
    hardware; si no, otro) y P3;
  - diagnostico: consulta el servicio asociado al tipo y responde con lo observado;
  - conocimiento: `buscar_docs` con la causa y cita el primer fragmento; propone
    reiniciar el servicio solo si está `caido` o `degradado`;
  - escalado: resumen con la incidencia y la causa.
  Debe dejar que el orquestador aplique todas las reglas (no las imita).
- **CLI (`cli.py`, `argparse`):**
  - argumentos: incidencia, `--oficina` (obligatorio), `--ticket`,
    `--modelo` (`simulado` por defecto, o `hf`), `--traza` (muestra los pasos);
  - `confirmar` pregunta en la terminal "¿Confirmas <acción>? [s/N]"; solo
    "s"/"si"/"sí" es True; sin terminal interactiva (EOF) es False;
  - imprime final, tipo, prioridad, escalado (si hay) y la respuesta al empleado;
  - `main(argv=None, entrada=input) -> int`: devuelve 0, o 2 si falla el modelo
    (mensaje claro en stderr, sin traza de Python).

## Criterios de aceptación
1. `ModeloHF` con un cliente falso: envía el prompt de sistema como primer
   mensaje seguido de los mensajes, con `temperature=0` y `max_tokens=512`, y
   devuelve el texto de `choices[0].message.content`.
2. Sin `HF_TOKEN` (con `monkeypatch.delenv` y sin leer `.env` real:
   `load_dotenv` parcheado) → `RuntimeError` que menciona `HF_TOKEN`.
3. Un cliente que falla una vez y luego responde → devuelve la respuesta; uno
   que falla siempre → `RuntimeError` tras 2 intentos. El mensaje de error
   no contiene el token.
4. `HF_MODEL` del entorno tiene preferencia sobre el valor por defecto.
5. `ModeloSimulado` + `orquestar()` (reloj fijo):
   - "no tengo internet" en MAD-01, confirmar True → `resuelto`, vpn reiniciada;
   - "no tengo internet" en MAD-01, confirmar False → `escalado`;
   - "no puedo entrar en el ERP" en MAD-02 → `escalado` con P1 (multioficina);
   - "la impresora no imprime" en MAD-02 con T-0007 → `escalado` (reabierto).
6. CLI con `--modelo simulado`: imprime final, tipo, prioridad y respuesta;
   con entrada "s" se ejecuta el reinicio y con "n" o EOF no; `--traza`
   muestra los pasos numerados; oficina inexistente → `rechazado`.
7. `--modelo hf` sin token → código 2 y mensaje en stderr que menciona `HF_TOKEN`.
8. `pyproject.toml` apunta a `soporte_oficinas.cli:main` y
   `uv run soporte-oficinas --help` funciona.
9. Ninguna prueba hace llamadas de red ni lee `.env`. Código en español,
   tipado, funciones cortas. `uv run pytest` en verde.

## Comprobación manual (la hago yo, no Claude Code)
`uv run soporte-oficinas "no tengo internet" --oficina MAD-01 --modelo hf --traza`
y anoto en worklog.md el modelo elegido, el resultado y la trayectoria.

## Al terminar
Resume en una tabla qué prueba cubre cada criterio. No hagas commit.

## Qué reviso yo
1. Que ninguna prueba usa red ni lee `.env`.
2. Que un error del modelo sale sin el token y con código 2.
3. La ejecución real con `--modelo hf --traza` (la lanzo yo: gasta créditos).
