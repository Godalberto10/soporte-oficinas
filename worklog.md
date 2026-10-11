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
**Comprobación:** pendiente — pedir a Claude Code que lea .env y verificar que lo deniega.
**Rechazado:** —
