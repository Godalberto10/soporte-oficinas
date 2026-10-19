"""Generates report.pdf at the project root.

Usage (it does not add dependencies to the project):
    uv run --no-project --with reportlab python report/generate.py
The real traces are read from report/trace1.txt and report/trace2.txt
(output of `office-support ... --model ollama --trace`).
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

ROOT = Path(__file__).resolve().parents[1]
FONTS = Path("C:/Windows/Fonts")
AUTHOR = "Alberto Olmos"
TITLE = "Technical support for an office network"

pdfmetrics.registerFont(TTFont("Text", str(FONTS / "arial.ttf")))
pdfmetrics.registerFont(TTFont("Text-B", str(FONTS / "arialbd.ttf")))
pdfmetrics.registerFont(TTFont("Text-I", str(FONTS / "ariali.ttf")))
pdfmetrics.registerFont(TTFont("Mono", str(FONTS / "consola.ttf")))
pdfmetrics.registerFontFamily("Text", normal="Text", bold="Text-B", italic="Text-I")

INK = colors.HexColor("#1B2A41")
ACCENT = colors.HexColor("#0F766E")
SOFT = colors.HexColor("#E6F2F1")
GREY = colors.HexColor("#5B6573")
RULE = colors.HexColor("#C9D3DC")

S = {
    "title": ParagraphStyle("title", fontName="Text-B", fontSize=19, leading=23,
                            textColor=INK),
    "sub": ParagraphStyle("sub", fontName="Text", fontSize=10.5, leading=14,
                          textColor=GREY),
    "h1": ParagraphStyle("h1", fontName="Text-B", fontSize=12, leading=15,
                         textColor=ACCENT, spaceBefore=9, spaceAfter=3),
    "p": ParagraphStyle("p", fontName="Text", fontSize=10, leading=13.6,
                        textColor=INK, alignment=TA_LEFT, spaceAfter=4),
    "li": ParagraphStyle("li", fontName="Text", fontSize=10, leading=13.4,
                         textColor=INK, leftIndent=10, bulletIndent=2, spaceAfter=1.5),
    "cell": ParagraphStyle("cell", fontName="Text", fontSize=8.8, leading=11,
                           textColor=INK),
    "cell-b": ParagraphStyle("cell-b", fontName="Text-B", fontSize=8.8, leading=11,
                             textColor=colors.white),
    "mono": ParagraphStyle("mono", fontName="Mono", fontSize=7.4, leading=9,
                           textColor=INK, backColor=SOFT, borderPadding=5,
                           leftIndent=5, rightIndent=5, spaceBefore=6, spaceAfter=6),
    "note": ParagraphStyle("note", fontName="Text-I", fontSize=8.5, leading=11,
                           textColor=GREY),
}


def p(text: str) -> Paragraph:
    return Paragraph(text, S["p"])


def h(text: str) -> Paragraph:
    return Paragraph(text, S["h1"])


def bullets(*items: str) -> list[Paragraph]:
    return [Paragraph(i, S["li"], bulletText="•") for i in items]


def table(rows: list[list[str]], widths: list[float]) -> Table:
    data = [[Paragraph(c, S["cell-b"] if i == 0 else S["cell"]) for c in row]
            for i, row in enumerate(rows)]
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def box(content, background=SOFT) -> Table:
    t = Table([[content]], colWidths=[17 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), background),
                           ("LINEBEFORE", (0, 0), (0, -1), 2.5, ACCENT),
                           ("LEFTPADDING", (0, 0), (-1, -1), 7),
                           ("TOPPADDING", (0, 0), (-1, -1), 5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def trace(n: int, title: str) -> list:
    path = ROOT / "report" / f"trace{n}.txt"
    header = Paragraph(f"<b>Trace {n}.</b> {title}", S["p"])
    if path.exists():
        raw = path.read_bytes()  # PowerShell may save in UTF-16
        text = raw.decode("utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff")
                          else "utf-8-sig").strip()
        # Preformatted outside a table: it can be split across pages
        return [header, Preformatted(text, S["mono"], maxLineLength=106,
                                     newLineChars="      ")]
    notice = "Pending: it will be run with <font name='Mono'>--model ollama --trace</font>."
    return [header, box(Paragraph(notice, S["note"]))]


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Text", 7.5)
    canvas.setFillColor(GREY)
    canvas.drawString(2 * cm, 1.2 * cm, f"{AUTHOR} · {TITLE}")
    canvas.drawRightString(19 * cm, 1.2 * cm, f"Page {doc.page}")
    canvas.setStrokeColor(RULE)
    canvas.line(2 * cm, 1.5 * cm, 19 * cm, 1.5 * cm)
    canvas.restoreState()


def content() -> list:
    c: list = [
        Paragraph(TITLE, S["title"]),
        Paragraph(f"Multi-agent system with safety rules in code · {AUTHOR} · "
                  "Laboratory Practice I, Agentic AI · October 2026", S["sub"]),
        Spacer(1, 8),

        h("1. Problem and scope"),
        p("The system acts as <b>first-level support</b> for the employees of four "
          "offices (MAD-01, MAD-02, BCN-01, VAL-01). The input is the incident text, the "
          "office and an optional ticket; the output is a <b>Result</b> with the final status "
          "(<i>resolved</i>, <i>escalated</i>, <i>rejected</i> or <i>step_limit_reached</i>), "
          "the answer to the employee with citations to the knowledge base, and the full "
          "trace. Whatever is not resolved is escalated to the second level with a summary of "
          "what was tried. Requests that are not office support (rejected) and any physical "
          "repair are out of scope. It is written in Python 3.12 <b>without agent "
          "frameworks</b>: the loop and the rules are my own code, which I can explain and test."),

        h("2. Multi-agent architecture"),
        table([
            ["Agent", "Decides", "Output (validated JSON)", "Tools"],
            ["classifier", "type and priority", "type, priority, reason", "search_tickets"],
            ["diagnosis", "probable cause", "cause, service, evidence",
             "check_service, check_device, search_tickets"],
            ["knowledge", "procedure", "procedure, citations, action",
             "search_docs; <i>proposes</i> restart_service and close_ticket"],
            ["escalation", "handoff to level 2", "summary, tried, priority", "create_escalation"],
        ], [2.5, 3, 4.5, 7]),
        Spacer(1, 4),
        p("<b>Handoff orchestration</b>: classifier → diagnosis → knowledge → resolved or "
          "escalated. Support is sequential (a solution cannot be proposed without knowing the "
          "cause), so a supervisor would only add model calls and points of failure. The "
          "exceptions are fixed rules in code: a reopened ticket, an outage in several "
          "offices or a safety hazard → escalation after diagnosis; no valid citation or a "
          "rejected action → escalation."),
        p("<b>State and messages</b>: a shared <font name='Mono'>State</font> keeps what has "
          "been found out (type, priority, cause, service, citations, actions, trace and "
          "steps). Each agent receives a JSON summary of that state, not the whole "
          "conversation: less text, fewer credits and less confusion. In each turn the model "
          "returns a single JSON object (a tool call or the final output); the code validates "
          "the contract, and the prompt is generated from the registry with <b>only</b> the "
          "tools allowed to that agent (least privilege)."),
        p("<b>Priorities.</b> The classifier proposes them; the code <b>raises</b> the "
          "priority if the data require more (it never lowers it), a safety hazard "
          "(explosion, fire, smoke, sparks) is at least P2, and a rejection has no "
          "priority. Critical services: vpn, email, erp, files and intranet (the intranet "
          "hosts password self-service: if it fails, it is a security problem). Non-critical: "
          "printing and guest wifi."),
        table([
            ["", "Criterion", "Example in the data", "1st response"],
            ["P1", "Affects more than one office, or a critical service is down",
             "vpn down in MAD-01; erp down in MAD-02 and BCN-01", "15 min"],
            ["P2", "Affects an entire office, or a critical service is degraded",
             "email degraded in BCN-01", "30 min"],
            ["P3", "An employee cannot work and there is no alternative",
             "PC without network in VAL-01 (faulty card)", "2 h"],
            ["P4", "Inconvenience with an alternative",
             "a printer (there are others), the computer is slow", "1 business day"],
        ], [1, 6.5, 6.8, 2.7]),

        h("3. Language models"),
        p("The four models meet the same contract, <font name='Mono'>generate(system, "
          "messages) → text</font>, so the rest of the system does not know which one it is "
          "using and the rules apply equally to all of them."),
        table([
            ["Model", "What it is", "What it is used for", "What it needs"],
            ["ScriptedModel", "Responses fixed in advance",
             "The 341 tests and the evaluation", "Nothing"],
            ["SimulatedModel", "Keyword rules, deterministic",
             "Demo without a token and web (default)", "Nothing"],
            ["OllamaModel (qwen2.5:14b)", "Real model run on my computer with Ollama",
             "The two real traces of the report", "Free: install Ollama and the model (9 GB)"],
            ["HFModel (Qwen2.5-72B)", "Real model on Hugging Face servers",
             "Optional", "Token and paid credits"],
        ], [3.6, 4.6, 4.4, 4.4]),
        Spacer(1, 4),
        p("The initial plan was Hugging Face, but it no longer gives free credits: two "
          "accounts returned <i>402 Payment Required</i>. As the professor indicated in class, "
          "I used Ollama, which runs the model locally with no token and no cost. The Hugging "
          "Face code is still available with <font name='Mono'>--model hf</font>. Neither is "
          "needed for grading: the tests and the README use the simulated model."),

        h("4. Tools and knowledge"),
        p("Seven tools in a registry with a <b>description</b> and a <b>reversible</b> flag; "
          "all go through a single entry point (<font name='Mono'>execute</font>) that turns "
          "any failure into a <font name='Mono'>ToolError</font>. The two irreversible ones "
          "(restart_service, close_ticket) are never run inside an agent's loop: knowledge "
          "only proposes them. The network data are loaded in memory, so every run starts "
          "from the same state."),
        p("Retrieval is a <b>hand-written BM25</b> over 15 documents of my own (11 kb-* "
          "articles with Symptoms, Cause and Steps, and 4 policies: service catalog, "
          "escalation, restarts and priorities). Each fragment is a section, so citations are "
          "precise (<font name='Mono'>docs/kb-network-01.md#Steps</font>). I chose it over "
          "embeddings because it needs no network or dependencies, and it is deterministic and "
          "explainable. Limitation: it does not understand synonyms; this is mitigated with "
          "employee phrasings in each Symptoms section."),

        h("5. Robustness and safety"),
        table([
            ["Rule (in code)", "What it guarantees"],
            ["R1 Confirmation", "An irreversible action only runs if confirm() returns true. "
             "If the person says no, it does not run and the incident is escalated."],
            ["R2 Guardrail", "A critical service during business hours is only restarted if "
             "it is the diagnosed one and is down or degraded; never in another office; at most "
             "one restart per service. If it blocks, the user is not even asked."],
            ["R3 Step limit", "12 steps (model responses and tool calls): prevents loops and "
             "caps spending. When exceeded, step_limit_reached."],
            ["R4 Errors", "Tool errors, disallowed tools and unreadable JSON become "
             "observations; two unreadable responses in a row → escalation."],
            ["R5 Citations", "A citation only counts if search_docs returned that fragment in "
             "this run; made-up ones are removed. Without a valid citation there is no "
             "resolved."],
        ], [3.2, 13.8]),
        Spacer(1, 4),
        p("In addition: the code raises the priority if the data require it (a critical "
          "service down is P1 even if the model says P3) and never lowers it; the answer to "
          "the employee is written by a template, so the model cannot promise response times. "
          "In Claude Code, <font name='Mono'>settings.json</font> only allows reading and "
          "testing, asks for permission for dependencies, credit-spending runs and commits, "
          "and denies reading <font name='Mono'>.env</font> (also via the terminal), deleting, "
          "pushing and sending data out. The token lives only in my "
          "<font name='Mono'>.env</font>: it is not in the code or in the submission."),

        h("6. Tests and evaluation"),
        p("341 tests with <b>model doubles</b> (ScriptedModel with fixed responses and a fake "
          "client for Hugging Face): deterministic, without network and without a token. Each "
          "rule R1–R5 has tests that fail if it breaks; this was checked by breaking each rule "
          "on purpose (mutations)."),
        p("The <b>evaluation</b> consists of 11 cases whose expected result I defined by "
          "applying my rules, without looking at the code (independent oracle). It measures "
          "the <b>result</b> (final, type, priority) and the <b>trajectory</b> (C = classifier, "
          "D = diagnosis, K = knowledge, E = escalation). It runs with a script (it checks the "
          "rules) and with the simulated model (what a user without a token would see; cases "
          "9 and 10 need scripted model errors, so they only run with the script)."),
        table([
            ["#", "Case", "Expected: final · type · priority · trajectory"],
            ["1", "“I have no internet”, MAD-01, confirms (vpn down)",
             "resolved · network · P1 · C-D-K"],
            ["2", "Same, but rejects the restart (R1)", "escalated · network · P1 · C-D-K-E"],
            ["3", "“I have no internet”, VAL-01 (broken card): same symptom, different cause",
             "resolved · network · P3 · C-D-K"],
            ["4", "Printer, MAD-02, T-0007 reopened", "escalated · printer · P4 · C-D-E"],
            ["5", "ERP down in MAD-02 and BCN-01; the model says P2",
             "escalated · app_access · P1 · C-D-E"],
            ["6", "Email degraded, BCN-01; the model says P4", "resolved · email · P2 · C-D-K"],
            ["7", "“Can you recommend a restaurant?”", "rejected · out_of_scope · — · C"],
            ["8", "Nonexistent office (SEV-01)", "rejected · — · — · no agents"],
            ["9", "Citation made up by the model (R5)", "escalated · network · P1 · C-D-K-E"],
            ["10", "Proposes restarting the ERP with the vpn diagnosed (R2)",
             "escalated · network · P1 · C-D-K-E"],
            ["11", "“My computer is slow” (my own case)", "resolved · hardware · P4 · C-D-K"],
        ], [0.8, 8.2, 8]),
        Spacer(1, 4),
        p("<b>First pass: 9/11 with the script and 6/9 with the simulated model.</b> I did not "
          "change the expected results; I analysed each failure. One was in the code (a "
          "rejection kept the classifier's P4 priority: what is not processed should have no "
          "priority), one was content (there was no article on slow computers) and three were "
          "in the simulated model (it did not recognise out-of-scope requests or "
          "“computer”, and always started at P3). Case 11 with the simulated model <b>got the "
          "final right by chance</b>: “resolved” citing the network-card article. That is why "
          "the trajectory and the data are also evaluated. After the fixes: <b>11/11 and "
          "9/9</b>."),

        h("7. Two real traces"),
        p("With Ollama (section 3, <font name='Mono'>--model ollama</font>). The first "
          "traces, produced with the Spanish version of the system and <b>qwen2.5:7b</b>, "
          "ended escalated: the model returned JSON outside the contract (R4), did not call "
          "tools and made up citations (R5 removed them). The rules prevented any harm, but "
          "the prompt did not state the exact format, the allowed values or what each service "
          "is. I added them (generated from the same lists the code validates) and switched to "
          "<b>qwen2.5:14b</b>; with that, the Spanish trace 1 ended resolved after I confirmed "
          "the vpn restart. After translating the system to English, I re-ran both traces "
          "with qwen2.5:14b (temperature 0, 19 October 2026). They are shown exactly as "
          "<font name='Mono'>--trace</font> prints them: one inside the domain and one "
          "outside it, as the assignment requires."),
        *trace(1, "“I have no internet” in MAD-01, ticket T-0001: escalated with P1; the "
                  "restart is never proposed."),
        p("<b>Trace 1 does not match my case 1.</b> Diagnosis checks the vpn (down) and the "
          "code raises the priority from P2 to P1. The knowledge agent, however, skips "
          "search_docs and cites a document it never retrieved "
          "(<font name='Mono'>docs/network_services.md#vpn-tunnel-restart</font>, which does "
          "not exist): R5 removes the citation, without a cited procedure there is no "
          "“resolved”, and the code escalates with P1 (ESC-0001). The restart never reaches "
          "the user, so R1 is not exercised. The code-level rules worked; what failed is the "
          "prompt instruction “your first turn is ALWAYS a call to search_docs”, which is not "
          "enough with this model in English. Future work: enforce that rule in code."),
        *trace(2, "Outside the domain, “Can you recommend a restaurant for lunch near the "
                  "office?”: rejected without going through more agents and without priority "
                  "(the model proposed P4), like my case 7."),

        h("8. Way of working and limitations"),
        p("I directed Claude Code with a <b>CLAUDE.md</b> of fewer than 200 lines (contracts, "
          "rules and closed values), least-privilege permissions and <b>one command per "
          "milestone</b> with checkable criteria (milestones 0 to 9). The decisions are mine; "
          "Claude Code drafted from them and generated the code, which I reviewed. "
          "<font name='Mono'>worklog.md</font> records decisions, problems, checks and who "
          "drafted each thing."),
        *bullets(
            "The simulated model works by keywords: a sentence with none it knows may be "
            "misclassified. With the real model, the classifier decides.",
            "R5 checks that a citation was retrieved, not that it is relevant; and nothing in "
            "code forces knowledge to search before answering (trace 1).",
            "BM25 does not understand synonyms; with more documents a hybrid search would help.",
            "With a small real model, the escalation agent may list in “tried” things nobody "
            "tried (trace 1: the vpn restart); it is not dangerous, but it is inaccurate.",
            "The 12-step limit was enough with the real model, with little margin: trace 1 "
            "used 7 steps, but another real run (ERP in MAD-02, <font name='Mono'>"
            "report/trace_erp_domain.txt</font>) used all 12 before escalating.",
        ),
        Spacer(1, 3),
        p("<b>Reproduce:</b> <font name='Mono'>uv sync</font> · <font name='Mono'>uv run "
          "pytest</font> · README commands (simulated model by default, no token). Web "
          "console with the agents working live (React): <font name='Mono'>uv run "
          "office-support-web</font>."),
    ]
    return c


def main() -> None:
    output = ROOT / "report.pdf"
    doc = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.7 * cm, bottomMargin=2 * cm, author=AUTHOR,
                            title=TITLE)
    doc.build(content(), onFirstPage=footer, onLaterPages=footer)
    print(output)


if __name__ == "__main__":
    main()
