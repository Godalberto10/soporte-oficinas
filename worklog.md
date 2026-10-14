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
