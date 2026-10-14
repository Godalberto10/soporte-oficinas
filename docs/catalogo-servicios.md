# Catálogo de servicios

## Servicios
- **Servicios críticos:** `vpn`, `correo`, `erp`, `ficheros`, `intranet`.
- **Servicios no críticos:** `impresion`, `wifi_invitados`.
- **Horario laboral:** de lunes a viernes, de 08:00 a 18:00 (hora local).

| Servicio | Descripción | Crítico |
|---|---|---|
| `vpn` | Túnel de la oficina con el centro de datos y salida a internet | sí |
| `correo` | Correo corporativo (Outlook y webmail) | sí |
| `erp` | Aplicación de gestión (pedidos, facturación, almacén) | sí |
| `ficheros` | Carpetas compartidas de la oficina | sí |
| `impresion` | Servidor de colas de impresión | no |
| `wifi_invitados` | Red inalámbrica para visitas | no |
| `intranet` | Portal interno y autoservicio de contraseñas | sí |

## Tiempos de respuesta
| Prioridad | Criterio | Primera respuesta | Resolución objetivo |
|---|---|---|---|
| P1 | afecta a más de una oficina, o un servicio crítico está `caido` | 15 minutos | 4 horas |
| P2 | afecta a una oficina entera, o un servicio crítico está `degradado` | 30 minutos | 8 horas |
| P3 | un empleado no puede trabajar y no hay alternativa | 2 horas | 2 días laborables |
| P4 | molestia con alternativa (otra impresora, webmail…) | 1 día laborable | 5 días laborables |

Los tiempos cuentan en horario laboral, salvo P1, que se atiende también
fuera de horario mediante la guardia de segundo nivel.
