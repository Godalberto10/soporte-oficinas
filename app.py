"""Office support web: thin layer over orchestrate() (milestone 8).

Start: uv run --group web streamlit run app.py
Nothing is decided here: everything is done by office_support.web / orchestrate().
No custom CSS: colors come from the theme (light or dark, .streamlit/config.toml).
"""

import streamlit as st

from office_support import web
from office_support.state import Action

FINALS = {
    "resolved": ("green", "Resolved at first level"),
    "escalated": ("orange", "Escalated to second level"),
    "rejected": ("red", "Not processed"),
    "step_limit_reached": ("gray", "Step limit reached"),
}
PRIORITY_COLOR = {"P1": "red", "P2": "orange", "P3": "yellow", "P4": "green"}
STATUS_COLOR = {"down": "red", "degraded": "orange"}
AGENT_NAMES = {"classifier": "Classifier", "diagnosis": "Diagnosis",
               "knowledge": "Knowledge", "escalation": "Escalation"}


def _badge(color: str, text: str) -> str:
    return f":{color}-badge[{text}]"


# --- Button actions (run before the page is drawn) ---------------------------------

def _launch(incident: str, office: str, ticket: str) -> None:
    """Example button: fills in the form and launches the query."""
    st.session_state.update(incident=incident, office=office, ticket=ticket)
    _submit()


def _submit() -> None:
    """Does not rewrite the form fields: it only creates the run."""
    s = st.session_state
    if not s.incident.strip():
        s.execution = None
        return
    s.execution = web.Execution(s.incident, s.office, s.ticket,
                                web.create_model(s.get("model", web.SIMULATED)))


def _respond(yes: bool) -> None:
    st.session_state.execution.respond(yes)


# --- Parts of the page ---------------------------------------------------------------

def _header() -> None:
    st.caption("MULTI-AGENT SYSTEM · FIRST-LEVEL SUPPORT")
    st.title("Technical support for an office network")
    st.markdown("Four agents handle each incident: classifier, diagnosis and "
                "knowledge; whatever is not solved goes to second level. Irreversible "
                "actions need your confirmation.")


def _sidebar() -> None:
    real = web.ollama_models()
    st.sidebar.subheader("Model")
    st.sidebar.radio("Model", [web.SIMULATED, *real], key="model",
                     label_visibility="collapsed",
                     format_func=lambda m: "Simulated" if m == web.SIMULATED else f"Real · {m}")
    st.sidebar.caption("The simulated model answers instantly using keywords. Real "
                       "models appear if Ollama is running on this computer.")
    st.sidebar.subheader("Example cases")
    for i, example in enumerate(web.EXAMPLES):
        st.sidebar.button(f"{example.title} — “{example.incident}”, {example.office}",
                          key=f"ex_{i}", width="stretch", on_click=_launch,
                          args=(example.incident, example.office, example.ticket))
    st.sidebar.subheader("Network status")
    for office, services in web.outages().items():
        badges = " ".join(_badge(STATUS_COLOR.get(st_, "gray"), f"{s} {st_}")
                          for s, st_ in services.items())
        st.sidebar.markdown(f"**{office}**  {badges or _badge('green', 'all ok')}")
    st.sidebar.caption("Each query starts from this state; changes are not saved.")


def _form() -> None:
    with st.form("incident_form", border=True):
        st.text_area("Incident", key="incident",
                     placeholder="Describe the problem, e.g. “I have no internet”")
        office_col, ticket_col = st.columns(2)
        office_col.selectbox("Office", web.OFFICES, key="office")
        ticket_col.text_input("Ticket (optional)", key="ticket", placeholder="T-0007")
        st.form_submit_button("Handle incident", type="primary", on_click=_submit)


def _guide() -> None:
    with st.expander("How to read the result"):
        priorities, finals = st.columns(2)
        priorities.markdown("**Priority** (proposed by the classifier; the code raises it "
                            "if the data require more)\n\n"
                            + "\n".join(f"- {_badge(PRIORITY_COLOR[p], p)} "
                                        f"{web.PRIORITY_CRITERIA[p]}. First response: "
                                        f"{web.RESPONSE_TIMES[p]}."
                                        for p in web.PRIORITY_CRITERIA))
        finals.markdown("**Final**\n\n"
                        + "\n".join(f"- {_badge(color, title)} "
                                    f"{web.FINAL_MEANING[final]}"
                                    for final, (color, title) in FINALS.items())
                        + "\n\nCritical services: vpn, email, erp, files and intranet.")


def _ask_confirmation(action: Action) -> None:
    with st.container(border=True):
        st.markdown("##### Confirmation needed")
        st.warning(f"The system proposes an **irreversible** action: "
                   f"`{web.describe_action(action)}`. Do you confirm it?")
        confirm, reject = st.columns(2)
        confirm.button("Confirm", key="confirm", type="primary", width="stretch",
                       on_click=_respond, args=(True,))
        reject.button("Reject", key="reject", width="stretch",
                      on_click=_respond, args=(False,))


def _path(result) -> str:
    steps = [_badge("primary" if active else "gray", AGENT_NAMES[agent])
             for agent, active in web.stages(result)]
    return "  →  ".join(steps)


def _show(result, answer: bool | None) -> None:
    color, title = FINALS.get(result.final, ("gray", result.final))
    header = _badge(color, title)
    if result.priority:
        header += " " + _badge(PRIORITY_COLOR[result.priority], f"Priority {result.priority}")
    st.markdown(header)
    explanation = f"**{title}:** {web.FINAL_MEANING.get(result.final, '')}"
    if result.priority:
        explanation += f"  \n**Priority {web.explain_priority(result.priority)}**"
    st.caption(explanation)
    st.markdown(f"**Path**  {_path(result)}")
    type_, priority, escalation = st.columns(3)
    type_.metric("Type", result.type or "—", border=True)
    priority.metric("Priority", result.priority or "—", border=True)
    escalation.metric("Escalation", result.escalation or "—", border=True)
    if answer is not None:
        st.caption("Your answer to the proposed action: "
                   + ("confirmed" if answer else "rejected") + ".")
    with st.container(border=True):
        st.markdown("##### Answer to the employee")
        st.markdown(result.answer.split("\n\nSources:")[0].replace("\n", "  \n"))
        if result.citations:
            st.markdown("**Sources**  " + " ".join(_badge("gray", c)
                                                   for c in result.citations))
    with st.expander(f"Full trace · {len(result.trace)} steps"):
        st.dataframe(web.trace_rows(result.trace), width="stretch", hide_index=True)


def main() -> None:
    st.set_page_config(page_title="Office support", layout="wide")
    _header()
    _sidebar()
    _form()
    _guide()
    execution = st.session_state.get("execution")
    if execution is None:
        st.info("Type an incident or choose an example case in the sidebar.")
        return
    with st.spinner("The agents are working…"):
        execution.wait()
    if execution.error is not None:
        st.error(f"The model did not respond: {execution.error}")
    elif execution.pending is not None:
        _ask_confirmation(execution.pending)
    else:
        _show(execution.result, execution.answer)


main()
