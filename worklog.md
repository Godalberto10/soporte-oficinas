# Bitácora

## Hito 0 — Esqueleto del proyecto (2026-10-06)
**Qué se hizo:** `uv init --package` (soporte_oficinas, Python 3.12); dependencias
huggingface-hub y python-dotenv; pytest como dependencia de desarrollo;
carpetas data/, docs/, tests/, .claude/commands/.
**Decisiones:** Python sin framework de agentes; orquestación por traspaso;
web con Streamlit como último hito (8), solo como capa sobre `orquestar()`.
**Problema:** `uv add --dev pytest` falló (os error 396) porque la carpeta está
en OneDrive y no admite hardlinks.
**Solución:** `link-mode = "copy"` en `[tool.uv]` del pyproject.toml.
**Rechazado:** —

## Hito 0b — Permisos (.claude/settings.json) (2026-10-06)
**Qué se hizo:** permisos con mínimo privilegio.
- allow: `uv run pytest`, `git status`, `git diff` (solo leen o prueban).
- ask: `uv add/remove` (cada dependencia la decido yo), `uv run python` y el
  programa (pueden llamar al modelo real con mi token), `git add/commit`.
- deny: leer o editar `.env` (el token no entra en el contexto del modelo),
  `git push`, `rm`, `curl`, `WebFetch` (no publicar, borrar ni sacar datos).
**Comprobación:** Claude Code tuvo denegado leer .env y hacer git push (dos
intentos reales bloqueados por settings.json).
**GitHub:** repositorio privado Godalberto10/soporte-oficinas; un commit por
hito; el push lo hago yo.
**Rechazado:** —

## Hito 0c — Token de Hugging Face (2026-10-11)
**Qué se hizo:** token fine-grained ("Make calls to Inference Providers") en
`.env` como `HF_TOKEN`; `.env` ignorado por git.
**Comprobación:** `whoami()` devuelve el usuario sin mostrar el token; el token
nunca se pegó en el chat.

## Hito 0d — CLAUDE.md (2026-10-11)
**Orden lanzada:** pedí a Claude Code un borrador del CLAUDE.md a partir de mis
decisiones: 5 tipos (red, impresora, acceso_aplicacion, correo, hardware + otro),
prioridad por alcance (P1–P4), críticos vpn/correo/erp/ficheros, horario L-V 08–18.
**Diferencias aceptadas:** contratos JSON de los 4 agentes; firma de `orquestar()`
con `confirmar` y `ahora` inyectables; guardarraíl (crítico en horario solo si es
el servicio diagnosticado y está caído o degradado; máx. 1 reinicio por servicio);
ticket reabierto → escalado directo; oficinas MAD-01, MAD-02, BCN-01, VAL-01;
tope de 12 pasos; 2 respuestas ilegibles seguidas → escalado.
**Diferencias rechazadas:** ninguna en esta versión (147 líneas, < 200).

## Hito 1 — Datos y documentos (2026-10-11)
**Orden lanzada:** `/hito1` (.claude/commands/hito1.md).
**Qué se hizo:** `data/servicios.json` (4 oficinas × 7 servicios),
`data/inventario.json` (14 equipos), `data/tickets.json` (10 tickets);
`docs/` con 10 artículos `kb-<tipo>-NN.md` (2 por tipo) y las 4 políticas;
`tests/test_datos.py` (45 pruebas, una o más por criterio de aceptación).
**Casos difíciles en los datos:**
- Mismo síntoma, causa distinta: "no tengo internet" en T-0001 (MAD-01, `vpn`
  caída) y T-0002 (VAL-01, servicios ok, PC-VAL01-002 con tarjeta de red averiada).
- Ticket reabierto: T-0007 (MAD-02, impresora, 2 reaperturas).
- Avería multioficina: `erp` caído en MAD-02 y BCN-01.
**Decisión — intranet pasa a crítica:** el borrador la tenía como no crítica.
La cambié porque por la intranet pasa el autoservicio de contraseñas y es un
punto sensible para la seguridad de la red interna. Consecuencias: intranet
caída → P1, degradada → P2; en horario laboral solo se reinicia si es el
servicio diagnosticado y está caída o degradada. Actualizados CLAUDE.md, las 4
políticas, `CRITICOS` en la prueba y la intranet de VAL-01 (de `degradado` a
`ok`, para que VAL-01 siga siendo el caso de avería de equipo).
**Comprobación:** al cambiar la lista, `test_mismo_sintoma_causas_distintas`
falló como se esperaba; tras corregir el dato, `uv run pytest` en verde (45).
**Coherencia:** las pruebas leen las reglas P1–P4 y la lista de críticos de
CLAUDE.md y exigen que coincidan con las políticas.
**Rechazado:** —

## Hito 2 — Orden `/hito2` (2026-10-14)
**Orden lanzada:** pedí a Claude Code un borrador de `.claude/commands/hito2.md`
(estado.py, modelo.py, herramientas.py y sus pruebas) siguiendo el formato de hito1.
**Decisiones del borrador que acepté:** `ModeloHF` se deja para el hito 6 y
`buscar_docs` para el hito 3 (no adelantar hitos); clase `Red` que carga los JSON
desde una ruta y aplica los cambios solo en memoria (las pruebas no ensucian
`data/`); confirmación y guardarraíl fuera de las herramientas (son del orquestador).
**Mejoras que pedí y acepté tras revisarlo:**
1. `crear_herramientas(red)` conserva las firmas de CLAUDE.md, y `ejecutar(...)`
   es el único punto de llamada: herramienta inexistente o argumentos mal formados
   → `ErrorHerramienta`, comprobando la firma con `inspect.signature().bind` para
   no ocultar fallos internos. Motivo: el orquestador solo captura un tipo de error (R4).
2. Campos de `Resultado` fijados (`final`, `respuesta`, `citas`, `traza`, `tipo`,
   `prioridad`, `escalado`), porque CLAUDE.md no los listaba y la evaluación del
   hito 7 comprueba `final`, tipo y prioridad.
3. Cada `Red` con su propia copia de los datos y prueba de aislamiento, para que
   el máximo de 1 reinicio por servicio no se mezcle entre ejecuciones.
**Rechazado / aplazado:** `parametros` en el registro (se verá en el hito 4, al
escribir los prompts) y tipos `Literal` (mejora menor).

## Hito 2 — Estado, modelo simulado y herramientas (2026-10-14)
**Orden lanzada:** `/hito2`.
**Qué se hizo:** `estado.py` (Paso, Accion, Estado, Resultado), `modelo.py`
(Protocol `Modelo` y `ScriptedModel`, que guarda las llamadas recibidas),
`herramientas.py` (`Red`, `ErrorHerramienta`, `Herramienta`,
`crear_herramientas`, `ejecutar` y las 6 herramientas; `buscar_docs` queda
para el hito 3). Pruebas: `test_estado.py`, `test_modelo.py`, `test_herramientas.py`.
**Decisiones de implementación:** cada herramienta se ata a su `Red` con
`functools.partial` y conserva la firma de CLAUDE.md; los argumentos se
validan como texto, para que una lista o un número enviados por el modelo den
`ErrorHerramienta`; `crear_escalado` admite `ticket=None` (el ticket es
opcional); todas las herramientas devuelven `dict` (`buscar_tickets` →
`{"tickets": [...]}`).
**Comprobación:** `uv run pytest` en verde (84 pruebas, 45 de test_datos).
Pruebas clave: `ejecutar` convierte herramienta inexistente y argumentos que
sobran o faltan en `ErrorHerramienta`, pero no oculta un `TypeError` interno;
dos `Red` no comparten datos; la huella SHA-256 de `data/*.json` no cambia
tras reiniciar, cerrar y escalar.
**Rechazado:** —

## Hito 3 — Recuperación BM25 y `buscar_docs` (2026-10-14)
**Orden lanzada:** borrador de `.claude/commands/hito3.md` escrito por Claude
Code a petición mía; lo revisé (qué es BM25, para qué sirve el hito, por qué
no se adelanta un agente) y lancé `/hito3` sin cambios.
**Qué se hizo:** `recuperacion.py` (tokenizar, trocear por secciones `## `,
`IndiceBM25` escrito a mano, `cita`), `buscar_docs` como 7.ª herramienta del
registro (`{"fragmentos": [...]}`, reversible, k entre 1 y 10) e índice
inyectable en `crear_herramientas(red, indice)`. Pruebas en
`test_recuperacion.py` y ampliación de `test_herramientas.py`.
**Decisiones:** unidad de recuperación = sección, con el título del documento
para distinguir secciones homónimas; cita `docs/<fichero>.md#<seccion>`;
sin tildes ni palabras vacías; k1=1.5, b=0.75; empates por doc y sección.
Por qué BM25 y no embeddings: sin dependencias ni red, determinista y explicable.
**Problema:** "reiniciar un servicio crítico en horario laboral" acertaba
`politica-reinicios.md` por muy poco (×1,02 frente a `kb-impresora-02.md`,
que también habla de reiniciar en horario laboral) y "reinicio" ≠ "reiniciar".
**Solución:** reducción a raíz ligera (sin plural ni vocal final, 6 letras) y
título con peso 3. Probé 12 combinaciones (longitud de raíz × peso) sobre 12
consultas y elegí la de mayor margen mínimo: ahora ×1,27 y ×1,46. Nueva prueba
`test_margen_politica_reinicios` (exige ≥ 1,2; con el código anterior fallaba).
**Coste aceptado:** "tiempos de respuesta por prioridad" baja de ×2,3 a ×1,17
porque "tiempo" coincide con `procedimiento-escalado.md`; sigue acertando.
**Limitación conocida:** BM25 no entiende sinónimos ("sin conexión" ≠ "no
tengo internet"); se mitiga con las expresiones de los empleados en `## Síntomas`.
**Comprobación:** `uv run pytest` en verde (124 pruebas).
**Rechazado:** adelantar el agente de conocimiento a este hito (se hace al
empezar el hito 4, junto con el bucle común de los agentes).

## Hito 4 — Agentes (2026-10-14)
**Orden lanzada:** borrador de `.claude/commands/hito4.md` escrito por Claude
Code a petición mía; antes pedí que me explicara qué hace cada agente y lancé
`/hito4` sin cambios.
**Qué se hizo:** `agentes.py` con el bucle común (`ejecutar_agente`), la
definición de los 4 agentes como datos (`AGENTES`), el prompt generado por
código y las funciones `clasificador`, `diagnostico`, `conocimiento` y
`escalado`. Pruebas en `test_agentes.py`. Orden de trabajo: primero bucle +
conocimiento (porción vertical, 19 pruebas en verde) y después los otros tres.
**Decisiones:**
- Protocolo: un único JSON por turno, llamada `{"herramienta", "argumentos"}`
  o salida final con las claves del contrato; se acepta dentro de ```json.
- Las irreversibles nunca se ejecutan en el bucle: conocimiento las propone en
  `accion` y, si las llama como turno, se bloquean y se le avisa. Así la
  confirmación y el guardarraíl del hito 5 no se pueden saltar.
- El prompt se genera desde el registro (firma con `inspect.signature` y
  descripción) y solo muestra las herramientas permitidas al agente.
- Contrato incumplido (faltan claves, `tipo` o prioridad fuera de rango) cuenta
  como respuesta ilegible; 2 seguidas → `motivo="ilegible"`.
- Llamadas bloqueadas quedan en la traza con `herramienta=None`, para que nunca
  parezcan ejecutadas (regla 1).
- Escalado: si el agente no crea el escalado, lo crea el código con su salida
  (sin ticket si el del estado no existe); nunca se duplica.
- La prioridad del clasificador se guarda tal cual; subirla es del hito 5.
**Comprobación:** `uv run pytest` en verde (160 pruebas).
**Problema:** un `cat >> ... <<'EOF'` doble en una misma orden de Bash falló
sin escribir nada; se añadió el código con el editor.
**Rechazado:** que el clasificador corrija ya la prioridad con los datos (se
deja al orquestador, que tiene la información de todos los agentes).
