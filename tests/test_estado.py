"""Pruebas de las dataclasses del estado compartido."""

from dataclasses import fields, is_dataclass

from soporte_oficinas.estado import Accion, Estado, Paso, Resultado


def _campos(clase) -> list[str]:
    return [f.name for f in fields(clase)]


def test_son_dataclasses():
    for clase in (Paso, Accion, Estado, Resultado):
        assert is_dataclass(clase)


def test_campos_de_claude_md():
    assert _campos(Paso) == ["n", "agente", "herramienta", "argumentos", "observacion"]
    assert _campos(Accion) == ["herramienta", "argumentos"]
    assert _campos(Estado) == [
        "incidencia", "oficina", "ticket", "tipo", "prioridad", "causa",
        "servicio", "procedimiento", "citas", "acciones", "traza", "pasos", "final",
    ]
    assert _campos(Resultado) == [
        "final", "respuesta", "citas", "traza", "tipo", "prioridad", "escalado",
    ]


def test_estado_valores_iniciales():
    estado = Estado("no tengo internet", "MAD-01")
    assert estado.traza == [] and estado.acciones == [] and estado.citas == []
    assert estado.pasos == 0
    assert estado.final is None
    assert estado.ticket is None and estado.servicio is None


def test_listas_no_compartidas_entre_instancias():
    a = Estado("x", "MAD-01")
    b = Estado("y", "VAL-01")
    a.traza.append(Paso(1, "clasificador", None, {}, "{}"))
    a.acciones.append(Accion("reiniciar_servicio", {"servicio": "vpn"}))
    a.citas.append("docs/kb-red-01.md#Pasos")
    assert b.traza == [] and b.acciones == [] and b.citas == []


def test_resultado_por_defecto_sin_escalado():
    resultado = Resultado(final="resuelto", respuesta="Hecho.")
    assert resultado.escalado is None
    assert resultado.citas == [] and resultado.traza == []
