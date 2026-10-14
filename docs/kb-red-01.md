# Sin acceso a internet ni a aplicaciones por caída de la VPN

## Síntomas
- El empleado indica "no tengo internet" o "no carga nada".
- No abren el ERP, la intranet ni las carpetas compartidas.
- Varios compañeros de la misma oficina notan lo mismo a la vez.
- El icono de red del equipo aparece conectado.

## Causa
El túnel VPN de la oficina con el centro de datos está caído. El tráfico
corporativo (y la salida a internet, que pasa por el centro de datos) se
interrumpe para toda la oficina. Si `consultar_servicio("vpn", oficina)`
devuelve `caido` o `degradado`, esta es la causa más probable.

## Pasos
1. Consultar el estado del servicio `vpn` en la oficina del empleado.
2. Comprobar si otras oficinas tienen también la `vpn` caída; si es así,
   la avería es multioficina: escalar con P1 sin reiniciar nada.
3. Si solo afecta a esta oficina y el servicio está `caido` o `degradado`,
   puede solicitarse un reinicio de `vpn` según `politica-reinicios.md`
   (requiere confirmación; en horario laboral solo si es el servicio diagnosticado).
4. Tras el reinicio, pedir al empleado que cierre y vuelva a abrir el navegador.
5. Si en 10 minutos no se recupera, escalar a segundo nivel.
