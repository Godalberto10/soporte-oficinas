# Guía de prioridades

## Servicios
- **Servicios críticos:** `vpn`, `correo`, `erp`, `ficheros`, `intranet`.
- **Servicios no críticos:** `impresion`, `wifi_invitados`.
- **Horario laboral:** de lunes a viernes, de 08:00 a 18:00 (hora local).

## Niveles
- **P1**: afecta a más de una oficina, o un servicio crítico está `caido`.
- **P2**: afecta a una oficina entera, o un servicio crítico está `degradado`.
- **P3**: un empleado no puede trabajar y no hay alternativa.
- **P4**: molestia con alternativa (otra impresora, webmail…).

## Cómo decidir
1. Se aplica siempre el nivel más alto que cumpla la incidencia.
2. Se consulta el estado real de los servicios antes de fijar la prioridad:
   la percepción del empleado no basta.
3. Si los datos exigen una prioridad mayor que la propuesta (por ejemplo,
   P3 con un servicio crítico `caido`), se sube la prioridad y se deja
   constancia en la traza.

## Ejemplos
- `erp` caído en MAD-02 y BCN-01 a la vez → P1 (varias oficinas).
- `correo` degradado en una oficina → P2.
- Un portátil que no enciende y no hay equipo de préstamo → P3.
- Una impresora atascada con otra disponible en la oficina → P4.
