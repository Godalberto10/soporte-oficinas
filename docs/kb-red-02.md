# Un solo equipo sin conexión por tarjeta de red averiada

## Síntomas
- El empleado indica "no tengo internet", pero sus compañeros sí navegan.
- El icono de red muestra "cable desconectado" o "sin red".
- Los servicios de la oficina (`vpn`, `intranet`) están `ok`.

## Causa
La tarjeta de red del equipo está averiada o el cable está dañado. Es un
problema de hardware local, no de los servicios de la oficina. En el
inventario el equipo aparece con estado `averiado_tarjeta_red`.

## Pasos
1. Consultar el estado de `vpn` en la oficina; si está `ok`, descartar caída general.
2. Consultar la ficha del equipo en el inventario con `consultar_equipo`.
3. Pedir al empleado que pruebe otro cable y otra toma de red.
4. Si el inventario indica tarjeta averiada, ofrecer un portátil de préstamo
   y escalar a segundo nivel para la sustitución de la tarjeta.
5. No reiniciar servicios de la oficina: no resuelven una avería local.
