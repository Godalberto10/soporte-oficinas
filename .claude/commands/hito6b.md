---
description: Hito 6b — modelo local con Ollama para las trazas reales
---
# Hito 6b — Modelo local (Ollama)

Lee CLAUDE.md (sección "Contrato del modelo") y `ModeloHF` en `modelo.py`.
En este hito NO se cambian agentes, orquestador ni reglas, NO se toca `.env`
y NO se añaden dependencias (Ollama se usa con `huggingface_hub`, que ya está).

## Objetivo
Poder ejecutar el sistema con un modelo de lenguaje real en mi ordenador
(`--modelo ollama`) para sacar las dos trazas reales del informe.

## Contexto
Dos cuentas de Hugging Face dan `402 Payment Required: You have no remaining
credits`: HF ya no da créditos gratuitos. El profesor indicó en clase que, sin
créditos, se usaran más cuentas u Ollama. Las cuentas no sirven; uso Ollama.

## Decisiones (mías)
- `ModeloOllama` reutiliza `ModeloHF` (mismo `generar`, `temperature=0`,
  `max_tokens=512` y reintento solo de fallos transitorios) con
  `InferenceClient(base_url=...)` hacia el servidor local de Ollama, que
  habla el mismo protocolo. Sin token.
- Modelo por defecto `qwen2.5:7b` (misma familia que el de HF, buen JSON y
  español, cabe en mi equipo). Configurable con `OLLAMA_MODEL`; dirección
  con `OLLAMA_URL` (por defecto `http://localhost:11434/v1`).
- `ModeloHF` sigue intacto: si consigo créditos, `--modelo hf` funciona igual.

## Criterios de aceptación
1. `ModeloOllama(cliente=falso)` no necesita `HF_TOKEN` y envía el nombre del
   modelo en cada llamada, con `temperature=0` y `max_tokens=512`.
2. `OLLAMA_MODEL` cambia el modelo; sin variable, `qwen2.5:7b`.
3. `--modelo ollama` en la CLI crea un `ModeloOllama`.
4. CLAUDE.md y README explican la opción; las pruebas no necesitan Ollama
   instalado (cliente falso) y siguen sin red.
5. `uv run pytest` en verde.

## Al terminar
Tabla criterio → prueba. No hagas commit.
