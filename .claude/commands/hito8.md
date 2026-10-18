---
description: Hito 8 — web Streamlit como capa fina sobre orquestar()
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(uv run pytest:*), Bash(uv run --group web pytest:*), Bash(uv add --group web streamlit)
---
# Hito 8 — Interfaz web

Lee CLAUDE.md (secciones "Interfaz web" y "Orquestación") y `orquestar` en
`orquestador.py`.
En este hito NO se cambia la lógica de agentes, orquestador, modelos ni datos,
y la web NO contiene lógica de agentes: solo llama a `orquestar()`.

## Objetivo
Que el profesor pueda probar el sistema desde el navegador, sin terminal, con
los casos interesantes a un clic.

## Ficheros esperados
- `app.py` (Streamlit, en la raíz)
- `src/soporte_oficinas/web.py` (lógica de la página sin Streamlit, probada)
- `tests/test_web.py` (sin Streamlit) y `tests/test_app.py` (con
  `streamlit.testing`, se omite si Streamlit no está instalado)
- `pyproject.toml` (grupo opcional `web`), README y CLAUDE.md

## Decisiones (mías)
- Texto libre para la incidencia, desplegable con las 4 oficinas y ticket
  opcional. En una empresa real la oficina saldría del inicio de sesión.
- Botones de ejemplo con mis casos: internet en MAD-01 (pide confirmación),
  internet en VAL-01 (misma frase, otra causa), ERP en MAD-02 (varias
  oficinas), impresora con T-0007 (reabierto), equipo lento y restaurante
  (fuera de ámbito).
- `confirmar` es un botón (Confirmar / Rechazar): la primera ejecución se
  detiene al pedir confirmación y la página la repite con mi respuesta. Con
  el simulado y una `Red` nueva el camino es idéntico y nada irreversible se
  ejecuta antes de responder.
- Solo `ModeloSimulado`: la web pública no gasta créditos ni necesita token.
- Streamlit en un grupo opcional (`uv add --group web streamlit`): `uv sync`
  y `uv run pytest` no lo necesitan; la web se lanza con
  `uv run --group web streamlit run app.py`.

## Criterios de aceptación
1. `web.atender(incidencia, oficina, ticket, decision=None)` devuelve la
   `Accion` pendiente si hay que confirmar, y el `Resultado` si no.
2. Con la decisión: "no tengo internet" en MAD-01 → `resuelto` si confirmo y
   `escalado` con la vpn sin reiniciar si rechazo (R1 desde la web).
3. Los ejemplos dan el final de mi evaluación (casos 1, 3, 5, 4, 11 y 7).
4. Ticket vacío equivale a sin ticket; oficina o ticket inexistente →
   `rechazado` con el motivo.
5. `test_app.py`: la página carga, un ejemplo muestra el resultado y en el
   caso de MAD-01 aparecen los botones y "Confirmar" acaba en resuelto.
6. `uv run pytest` sigue en verde sin Streamlit; con `--group web`, también.

## Al terminar
Tabla criterio → prueba. No hagas commit.

## Qué reviso yo
1. Que `app.py` no decide nada: solo muestra y llama a `web.py`/`orquestar()`.
2. Que con "Rechazar" la vpn sigue caída y se escala.
3. La página en el navegador con los ejemplos.
