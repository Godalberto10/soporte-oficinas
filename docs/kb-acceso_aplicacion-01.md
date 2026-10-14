# No se puede entrar en el ERP porque el servicio está caído

## Síntomas
- Al abrir el ERP aparece "servicio no disponible" o la pantalla se queda en blanco.
- Afecta a todos los empleados de la oficina.
- Puede ocurrir en varias oficinas a la vez.

## Causa
El servidor del ERP está `caido` o `degradado`. Cuando falla en más de una
oficina el origen está en el centro de datos y no en la oficina.

## Pasos
1. Consultar el estado de `erp` en la oficina del empleado.
2. Buscar tickets abiertos con el mismo síntoma en otras oficinas.
3. Si `erp` está caído en más de una oficina: avería multioficina, prioridad
   P1, escalar a segundo nivel sin reiniciar (ver `procedimiento-escalado.md`).
4. Si solo afecta a una oficina, puede solicitarse un reinicio de `erp`
   según `politica-reinicios.md`.
5. Informar al empleado del tiempo de respuesta según `catalogo-servicios.md`.
