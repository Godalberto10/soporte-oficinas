# Ninguna impresora de la oficina imprime: servicio de impresión degradado

## Síntomas
- Ninguna impresora de la oficina recibe trabajos o tardan varios minutos.
- Aparece el error "servidor de impresión no disponible".
- Las impresoras encienden con normalidad y no muestran avisos.

## Causa
El servidor de colas de impresión de la oficina está `degradado` o `caido`.
`impresion` es un servicio no crítico, por lo que puede reiniciarse también
en horario laboral con confirmación.

## Pasos
1. Consultar el estado del servicio `impresion` en la oficina.
2. Si está `degradado` o `caido`, solicitar un reinicio de `impresion`
   (requiere confirmación, ver `politica-reinicios.md`).
3. Pedir al empleado que vuelva a enviar el trabajo tras el reinicio.
4. Si el ticket ya se había reabierto antes, no repetir el reinicio:
   escalar a segundo nivel.
