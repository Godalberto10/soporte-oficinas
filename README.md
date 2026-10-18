# soporte-oficinas

Soporte técnico de una red de oficinas. Tiene como objetivo resolver las
incidencias de primer nivel de los empleados (sin conexión, impresora, acceso a
una aplicación) con varios pasos de diagnóstico sobre un estado simulado de
servicios, y escalar las que no se resuelven.

Cuatro agentes trabajan en cadena (clasificador → diagnóstico → conocimiento →
resuelto o escalado). Las reglas de seguridad (confirmación de acciones
irreversibles, guardarraíl, tope de pasos, errores como observaciones y citas
comprobadas) están en el código, no en el prompt.

## Requisitos
- [uv](https://docs.astral.sh/uv/) (instala Python 3.12 si no está).
- No hace falta token para las pruebas ni para el modelo simulado.

## Instalación
```
uv sync
```

## Pruebas
```
uv run pytest
```
Sin red y sin token: usan un modelo con respuestas fijadas (`ScriptedModel`).

## Ejecución
```
uv run soporte-oficinas "<incidencia>" --oficina <MAD-01|MAD-02|BCN-01|VAL-01> [--ticket T-NNNN] [--modelo simulado|ollama|hf] [--traza]
```
Por defecto usa el modelo simulado (sin token). `--traza` muestra cada paso de
cada agente. Si hay que reiniciar un servicio, el programa pregunta `[s/N]`.

### Ejemplos (los casos difíciles del enunciado)
```
# 1. Pide confirmación: la vpn de MAD-01 está caída (P1). Responde "s" o "n".
uv run soporte-oficinas "no tengo internet" --oficina MAD-01 --traza

# 2. Mismo síntoma, otra causa: en VAL-01 los servicios van bien; el equipo
#    tiene la tarjeta de red averiada. No se reinicia nada.
uv run soporte-oficinas "no tengo internet" --oficina VAL-01 --ticket T-0002 --traza

# 3. Avería en varias oficinas: el ERP está caído en MAD-02 y BCN-01 → escalado P1.
uv run soporte-oficinas "no puedo entrar en el ERP" --oficina MAD-02 --traza

# 4. Ticket reabierto: T-0007 ya se reabrió 2 veces → escalado directo.
uv run soporte-oficinas "la impresora no imprime" --oficina MAD-02 --ticket T-0007 --traza
```

## Evaluación
```
uv run python -m soporte_oficinas.evaluacion                     # con guion
uv run python -m soporte_oficinas.evaluacion --modelo simulado   # con el simulado
```
Imprime la tabla de casos (resultado y trayectoria esperados frente a obtenidos).

## Modelo real en local (Ollama), opcional
Gratis, sin token ni créditos. Es el que se usó para las trazas del informe.
1. Instala [Ollama](https://ollama.com/download) y descarga el modelo:
   ```
   ollama pull qwen2.5:7b
   ```
2. Con Ollama abierto, ejecuta con `--modelo ollama`, por ejemplo:
   ```
   uv run soporte-oficinas "no tengo internet" --oficina MAD-01 --modelo ollama --traza
   ```
   Opcional: `OLLAMA_MODEL=<modelo>` y `OLLAMA_URL=<url>` en el entorno o en `.env`.

## Modelo real (Hugging Face), opcional
1. Crea un token en Hugging Face con permiso "Make calls to Inference Providers".
2. Crea un fichero `.env` en la raíz del proyecto (no se sube a git ni se
   entrega) con:
   ```
   HF_TOKEN=tu_token
   ```
   Opcional: `HF_MODEL=<modelo>` (por defecto `Qwen/Qwen2.5-72B-Instruct`).
3. Ejecuta con `--modelo hf`, por ejemplo:
   ```
   uv run soporte-oficinas "no tengo internet" --oficina MAD-01 --modelo hf --traza
   ```
Cada incidencia hace unas 5–10 llamadas al modelo y gasta créditos de la cuenta.

## Estructura
```
src/soporte_oficinas/   estado, modelo, herramientas, recuperacion (BM25),
                        agentes, orquestador, evaluacion, cli
data/                   estado simulado: servicios, inventario, tickets
docs/                   base de conocimiento (artículos kb-* y políticas)
tests/                  pruebas pytest
CLAUDE.md, .claude/     especificación, permisos y órdenes de cada hito
worklog.md              bitácora de decisiones
```
