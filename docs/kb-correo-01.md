# El correo tarda en llegar o no se envía: servicio de correo degradado

## Síntomas
- Los mensajes tardan muchos minutos en llegar o se quedan en la bandeja de salida.
- Outlook muestra "intentando conectar".
- Afecta a varios empleados de la oficina.

## Causa
El servicio `correo` de la oficina está `degradado` (cola de envío saturada)
o `caido`. Es un servicio crítico.

## Pasos
1. Consultar el estado de `correo` en la oficina.
2. Mientras tanto, recomendar el webmail como alternativa.
3. Si el estado es `degradado` o `caido`, puede solicitarse un reinicio de
   `correo` según `politica-reinicios.md` (en horario laboral solo si es el
   servicio diagnosticado).
4. Si no mejora en 15 minutos, escalar a segundo nivel.
