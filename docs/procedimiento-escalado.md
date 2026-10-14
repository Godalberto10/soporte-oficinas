# Procedimiento de escalado a segundo nivel

## Cuándo escalar
- La avería afecta a más de una oficina (siempre con prioridad P1).
- El ticket ya se ha reabierto alguna vez (`reaperturas >= 1`).
- No hay un procedimiento documentado en la base de conocimiento.
- La acción propuesta (reinicio, cierre) se ha rechazado o no ha resuelto.
- El problema es de hardware y requiere sustitución o reparación.

## Qué incluir
1. Resumen de la incidencia: oficina, síntoma y causa probable.
2. Lista de lo que ya se ha probado en primer nivel.
3. Prioridad según `guia-prioridades.md`:
   - **P1**: afecta a más de una oficina, o un servicio crítico está `caido`.
   - **P2**: afecta a una oficina entera, o un servicio crítico está `degradado`.
   - **P3**: un empleado no puede trabajar y no hay alternativa.
   - **P4**: molestia con alternativa (otra impresora, webmail…).
4. Número de ticket, si existe.

## Servicios
- **Servicios críticos:** `vpn`, `correo`, `erp`, `ficheros`, `intranet`.
- **Horario laboral:** de lunes a viernes, de 08:00 a 18:00 (hora local).
- Fuera de horario solo se atiende P1, a través de la guardia de segundo nivel.

## Comunicación al empleado
Indicar al empleado que su incidencia se ha escalado, el identificador de
escalado y el tiempo de primera respuesta según `catalogo-servicios.md`.
