# La impresora no imprime por atasco o falta de tóner

## Síntomas
- Los trabajos se quedan en cola y no salen.
- La pantalla de la impresora muestra un aviso de atasco o de tóner bajo.
- Solo falla una impresora; las demás de la oficina funcionan.

## Causa
Fallo físico de la impresora: papel atascado o cartucho de tóner agotado.
En el inventario aparece con estado `atasco_papel` o `sin_toner`.

## Pasos
1. Consultar la ficha de la impresora con `consultar_equipo`.
2. Si hay atasco, indicar al empleado que abra la bandeja frontal y retire
   el papel siguiendo las flechas del panel.
3. Si falta tóner, solicitar cartucho al responsable de la oficina.
4. Mientras tanto, enviar el trabajo a otra impresora de la oficina
   (alternativa disponible: prioridad P4).
5. Si tras retirar el atasco sigue sin imprimir, escalar a segundo nivel.
