"""Web del soporte de oficinas: capa fina sobre orquestar() (hito 8).

Arranque: uv run --group web streamlit run app.py
Aquí no se decide nada: todo lo hace soporte_oficinas.web / orquestar().
Sin CSS propio: los colores salen del tema (claro u oscuro, .streamlit/config.toml).
"""

import streamlit as st

from soporte_oficinas import web
from soporte_oficinas.estado import Accion

FINALES = {
    "resuelto": ("green", "Resuelto en primer nivel"),
    "escalado": ("orange", "Escalado a segundo nivel"),
    "rechazado": ("red", "No se tramita"),
    "tope_alcanzado": ("gray", "Tope de pasos alcanzado"),
}
COLOR_PRIORIDAD = {"P1": "red", "P2": "orange", "P3": "yellow", "P4": "green"}
COLOR_ESTADO = {"caido": "red", "degradado": "orange"}
NOMBRES_AGENTE = {"clasificador": "Clasificador", "diagnostico": "Diagnóstico",
                  "conocimiento": "Conocimiento", "escalado": "Escalado"}


def _etiqueta(color: str, texto: str) -> str:
    return f":{color}-badge[{texto}]"


# --- Acciones de los botones (se ejecutan antes de dibujar la página) -----------

def _lanzar(incidencia: str, oficina: str, ticket: str) -> None:
    """Botón de ejemplo: rellena el formulario y lanza la consulta."""
    st.session_state.update(incidencia=incidencia, oficina=oficina, ticket=ticket)
    _enviar()


def _enviar() -> None:
    """No reescribe los campos del formulario: solo crea la ejecución."""
    s = st.session_state
    if not s.incidencia.strip():
        s.ejecucion = None
        return
    s.ejecucion = web.Ejecucion(s.incidencia, s.oficina, s.ticket,
                                web.crear_modelo(s.get("modelo", web.SIMULADO)))


def _responder(si: bool) -> None:
    st.session_state.ejecucion.responder(si)


# --- Partes de la página ------------------------------------------------------------

def _cabecera() -> None:
    st.caption("SISTEMA MULTIAGENTE · SOPORTE DE PRIMER NIVEL")
    st.title("Soporte técnico de una red de oficinas")
    st.markdown("Cuatro agentes atienden cada incidencia: clasificador, diagnóstico y "
                "conocimiento; lo que no se resuelve pasa a segundo nivel. Las acciones "
                "irreversibles necesitan tu confirmación.")


def _barra_lateral() -> None:
    reales = web.modelos_ollama()
    st.sidebar.subheader("Modelo")
    st.sidebar.radio("Modelo", [web.SIMULADO, *reales], key="modelo",
                     label_visibility="collapsed",
                     format_func=lambda m: "Simulado" if m == web.SIMULADO else f"Real · {m}")
    st.sidebar.caption("El simulado responde al instante por palabras clave. Los modelos "
                       "reales aparecen si Ollama funciona en este equipo.")
    st.sidebar.subheader("Casos de ejemplo")
    for i, ejemplo in enumerate(web.EJEMPLOS):
        st.sidebar.button(f"{ejemplo.titulo} — «{ejemplo.incidencia}», {ejemplo.oficina}",
                          key=f"ej_{i}", width="stretch", on_click=_lanzar,
                          args=(ejemplo.incidencia, ejemplo.oficina, ejemplo.ticket))
    st.sidebar.subheader("Estado de la red")
    for oficina, servicios in web.averias().items():
        etiquetas = " ".join(_etiqueta(COLOR_ESTADO.get(e, "gray"), f"{s} {e}")
                             for s, e in servicios.items())
        st.sidebar.markdown(f"**{oficina}**  {etiquetas or _etiqueta('green', 'todo ok')}")
    st.sidebar.caption("Cada consulta parte de este estado; los cambios no se guardan.")


def _formulario() -> None:
    with st.form("incidencia_form", border=True):
        st.text_area("Incidencia", key="incidencia",
                     placeholder="Describe el problema, p. ej. «no tengo internet»")
        col_oficina, col_ticket = st.columns(2)
        col_oficina.selectbox("Oficina", web.OFICINAS, key="oficina")
        col_ticket.text_input("Ticket (opcional)", key="ticket", placeholder="T-0007")
        st.form_submit_button("Atender incidencia", type="primary", on_click=_enviar)


def _guia() -> None:
    with st.expander("Cómo se lee el resultado"):
        prioridades, finales = st.columns(2)
        prioridades.markdown("**Prioridad** (la propone el clasificador; el código la sube "
                             "si los datos exigen más)\n\n"
                             + "\n".join(f"- {_etiqueta(COLOR_PRIORIDAD[p], p)} "
                                         f"{web.CRITERIO_PRIORIDAD[p]}. Primera respuesta: "
                                         f"{web.TIEMPOS_RESPUESTA[p]}."
                                         for p in web.CRITERIO_PRIORIDAD))
        finales.markdown("**Final**\n\n"
                         + "\n".join(f"- {_etiqueta(color, titulo)} "
                                     f"{web.SIGNIFICADO_FINAL[final]}"
                                     for final, (color, titulo) in FINALES.items())
                         + "\n\nServicios críticos: vpn, correo, erp, ficheros e intranet.")


def _pedir_confirmacion(accion: Accion) -> None:
    with st.container(border=True):
        st.markdown("##### Confirmación necesaria")
        st.warning(f"El sistema propone una acción **irreversible**: "
                   f"`{web.describir_accion(accion)}`. ¿La confirmas?")
        confirmar, rechazar = st.columns(2)
        confirmar.button("Confirmar", key="confirmar", type="primary", width="stretch",
                         on_click=_responder, args=(True,))
        rechazar.button("Rechazar", key="rechazar", width="stretch",
                        on_click=_responder, args=(False,))


def _recorrido(resultado) -> str:
    pasos = [_etiqueta("primary" if activo else "gray", NOMBRES_AGENTE[agente])
             for agente, activo in web.etapas(resultado)]
    return "  →  ".join(pasos)


def _mostrar(resultado, respuesta: bool | None) -> None:
    color, titulo = FINALES.get(resultado.final, ("gray", resultado.final))
    cabecera = _etiqueta(color, titulo)
    if resultado.prioridad:
        cabecera += " " + _etiqueta(COLOR_PRIORIDAD[resultado.prioridad],
                                    f"Prioridad {resultado.prioridad}")
    st.markdown(cabecera)
    explicacion = f"**{titulo}:** {web.SIGNIFICADO_FINAL.get(resultado.final, '')}"
    if resultado.prioridad:
        explicacion += f"  \n**Prioridad {web.explicar_prioridad(resultado.prioridad)}**"
    st.caption(explicacion)
    st.markdown(f"**Recorrido**  {_recorrido(resultado)}")
    tipo, prioridad, escalado = st.columns(3)
    tipo.metric("Tipo", resultado.tipo or "—", border=True)
    prioridad.metric("Prioridad", resultado.prioridad or "—", border=True)
    escalado.metric("Escalado", resultado.escalado or "—", border=True)
    if respuesta is not None:
        st.caption("Tu respuesta a la acción propuesta: "
                   + ("confirmada" if respuesta else "rechazada") + ".")
    with st.container(border=True):
        st.markdown("##### Respuesta al empleado")
        st.markdown(resultado.respuesta.split("\n\nFuentes:")[0].replace("\n", "  \n"))
        if resultado.citas:
            st.markdown("**Fuentes**  " + " ".join(_etiqueta("gray", c)
                                                   for c in resultado.citas))
    with st.expander(f"Traza completa · {len(resultado.traza)} pasos"):
        st.dataframe(web.filas_traza(resultado.traza), width="stretch", hide_index=True)


def main() -> None:
    st.set_page_config(page_title="Soporte de oficinas", layout="wide")
    _cabecera()
    _barra_lateral()
    _formulario()
    _guia()
    ejecucion = st.session_state.get("ejecucion")
    if ejecucion is None:
        st.info("Escribe una incidencia o elige un caso de ejemplo en el panel lateral.")
        return
    with st.spinner("Los agentes están trabajando…"):
        ejecucion.esperar()
    if ejecucion.error is not None:
        st.error(f"El modelo no ha respondido: {ejecucion.error}")
    elif ejecucion.pendiente is not None:
        _pedir_confirmacion(ejecucion.pendiente)
    else:
        _mostrar(ejecucion.resultado, ejecucion.respuesta)


main()
