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
