# Política de reinicios de servicios

## Servicios
- **Servicios críticos:** `vpn`, `correo`, `erp`, `ficheros`, `intranet`.
- **Servicios no críticos:** `impresion`, `wifi_invitados`.
- **Horario laboral:** de lunes a viernes, de 08:00 a 18:00 (hora local).

## Reglas
1. Reiniciar un servicio es una acción **irreversible**: corta las sesiones
   abiertas. Siempre requiere confirmación explícita antes de ejecutarse.
2. Un servicio **crítico** solo puede reiniciarse en horario laboral si:
   - es el servicio identificado en el diagnóstico de la incidencia, y
   - su estado actual es `caido` o `degradado`.
   Si no se cumplen ambas condiciones, el reinicio se bloquea sin preguntar.
3. Fuera del horario laboral, y para servicios no críticos, basta con la
   confirmación.
4. Como máximo se hace **un reinicio por servicio** en cada atención. Si no
   resuelve, se escala a segundo nivel.
5. No se reinicia nada cuando la avería afecta a más de una oficina: es P1
   y la gestiona segundo nivel.

## Si se rechaza el reinicio
Si quien confirma rechaza el reinicio, no se ejecuta y la incidencia se
escala a segundo nivel según `procedimiento-escalado.md`.
