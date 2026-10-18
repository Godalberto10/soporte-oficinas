"""Genera informe.pdf en la raíz del proyecto.

Uso (no añade dependencias al proyecto):
    uv run --no-project --with reportlab python informe/generar.py
Las trazas reales se leen de informe/traza1.txt y informe/traza2.txt
(salida de `soporte-oficinas ... --modelo hf --traza`).
"""

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

RAIZ = Path(__file__).resolve().parents[1]
FUENTES = Path("C:/Windows/Fonts")
AUTOR = "Alberto Olmos"

pdfmetrics.registerFont(TTFont("Texto", str(FUENTES / "arial.ttf")))
pdfmetrics.registerFont(TTFont("Texto-B", str(FUENTES / "arialbd.ttf")))
pdfmetrics.registerFont(TTFont("Texto-I", str(FUENTES / "ariali.ttf")))
pdfmetrics.registerFont(TTFont("Mono", str(FUENTES / "consola.ttf")))
pdfmetrics.registerFontFamily("Texto", normal="Texto", bold="Texto-B", italic="Texto-I")

TINTA = colors.HexColor("#1B2A41")
ACENTO = colors.HexColor("#0F766E")
SUAVE = colors.HexColor("#E6F2F1")
GRIS = colors.HexColor("#5B6573")
LINEA = colors.HexColor("#C9D3DC")

E = {
    "titulo": ParagraphStyle("titulo", fontName="Texto-B", fontSize=19, leading=23,
                             textColor=TINTA),
    "sub": ParagraphStyle("sub", fontName="Texto", fontSize=10.5, leading=14,
                          textColor=GRIS),
    "h1": ParagraphStyle("h1", fontName="Texto-B", fontSize=12, leading=15,
                         textColor=ACENTO, spaceBefore=9, spaceAfter=3),
    "p": ParagraphStyle("p", fontName="Texto", fontSize=10, leading=13.6,
                        textColor=TINTA, alignment=TA_LEFT, spaceAfter=4),
    "li": ParagraphStyle("li", fontName="Texto", fontSize=10, leading=13.4,
                         textColor=TINTA, leftIndent=10, bulletIndent=2, spaceAfter=1.5),
    "celda": ParagraphStyle("celda", fontName="Texto", fontSize=8.8, leading=11,
                            textColor=TINTA),
    "celda-b": ParagraphStyle("celda-b", fontName="Texto-B", fontSize=8.8, leading=11,
                              textColor=colors.white),
    "mono": ParagraphStyle("mono", fontName="Mono", fontSize=7.4, leading=9,
                           textColor=TINTA, backColor=SUAVE, borderPadding=5,
                           leftIndent=5, rightIndent=5, spaceBefore=6, spaceAfter=6),
    "nota": ParagraphStyle("nota", fontName="Texto-I", fontSize=8.5, leading=11,
                           textColor=GRIS),
}


def p(texto: str) -> Paragraph:
    return Paragraph(texto, E["p"])


def h(texto: str) -> Paragraph:
    return Paragraph(texto, E["h1"])


def lista(*elementos: str) -> list[Paragraph]:
    return [Paragraph(e, E["li"], bulletText="•") for e in elementos]


def tabla(filas: list[list[str]], anchos: list[float]) -> Table:
    datos = [[Paragraph(c, E["celda-b"] if i == 0 else E["celda"]) for c in fila]
             for i, fila in enumerate(filas)]
    t = Table(datos, colWidths=[a * cm for a in anchos], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TINTA),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SUAVE]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINEA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def recuadro(contenido, fondo=SUAVE) -> Table:
    t = Table([[contenido]], colWidths=[17 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), fondo),
                           ("LINEBEFORE", (0, 0), (0, -1), 2.5, ACENTO),
                           ("LEFTPADDING", (0, 0), (-1, -1), 7),
                           ("TOPPADDING", (0, 0), (-1, -1), 5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def traza(n: int, titulo: str) -> list:
    fichero = RAIZ / "informe" / f"traza{n}.txt"
    cabecera = Paragraph(f"<b>Traza {n}.</b> {titulo}", E["p"])
    if fichero.exists():
        crudo = fichero.read_bytes()  # PowerShell puede guardar en UTF-16
        texto = crudo.decode("utf-16" if crudo[:2] in (b"\xff\xfe", b"\xfe\xff")
                             else "utf-8-sig").strip()
        # Preformatted fuera de una tabla: puede partirse entre páginas
        return [cabecera, Preformatted(texto, E["mono"], maxLineLength=106,
                                       newLineChars="      ")]
    aviso = ("Pendiente: se ejecutará con <font name='Mono'>--modelo ollama --traza</font>.")
    return [cabecera, recuadro(Paragraph(aviso, E["nota"]))]


def pie(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Texto", 7.5)
    canvas.setFillColor(GRIS)
    canvas.drawString(2 * cm, 1.2 * cm, f"{AUTOR} · Soporte técnico de una red de oficinas")
    canvas.drawRightString(19 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.setStrokeColor(LINEA)
    canvas.line(2 * cm, 1.5 * cm, 19 * cm, 1.5 * cm)
    canvas.restoreState()


def contenido() -> list:
    c: list = [
        Paragraph("Soporte técnico de una red de oficinas", E["titulo"]),
        Paragraph(f"Sistema multiagente con reglas de seguridad en código · {AUTOR} · "
                  "Práctica de Laboratorio I, IA Agéntica · octubre 2026", E["sub"]),
        Spacer(1, 8),

        h("1. Problema y alcance"),
        p("El sistema hace de <b>soporte de primer nivel</b> para los empleados de cuatro "
          "oficinas (MAD-01, MAD-02, BCN-01, VAL-01). Entra el texto de la incidencia, la "
          "oficina y un ticket opcional; sale un <b>Resultado</b> con el estado final "
          "(<i>resuelto</i>, <i>escalado</i>, <i>rechazado</i> o <i>tope_alcanzado</i>), la "
          "respuesta al empleado con citas a la base de conocimiento y la traza completa. Lo "
          "que no se resuelve se escala a segundo nivel con un resumen de lo probado. Queda "
          "fuera lo que no es soporte de oficinas (se rechaza) y cualquier reparación física. "
          "Está escrito en Python 3.12 <b>sin frameworks de agentes</b>: el bucle y las "
          "reglas son código propio que puedo explicar y probar."),

        h("2. Arquitectura multiagente"),
        tabla([
            ["Agente", "Decide", "Salida (JSON validado)", "Herramientas"],
            ["clasificador", "tipo y prioridad", "tipo, prioridad, motivo", "buscar_tickets"],
            ["diagnóstico", "causa probable", "causa, servicio, evidencias",
             "consultar_servicio, consultar_equipo, buscar_tickets"],
            ["conocimiento", "procedimiento", "procedimiento, citas, accion",
             "buscar_docs; <i>propone</i> reiniciar_servicio y cerrar_ticket"],
            ["escalado", "traspaso a nivel 2", "resumen, probado, prioridad", "crear_escalado"],
        ], [2.5, 3, 4.5, 7]),
        Spacer(1, 4),
        p("<b>Orquestación por traspaso</b>: clasificador → diagnóstico → conocimiento → "
          "resuelto o escalado. El soporte es secuencial (no se puede proponer una solución "
          "sin conocer la causa), así que un supervisor solo añadiría llamadas al modelo y "
          "puntos de fallo. Las excepciones son reglas fijas en código: ticket reabierto o "
          "avería en varias oficinas → escalado tras el diagnóstico; sin cita válida o con "
          "la acción rechazada → escalado."),
        p("<b>Estado y mensajes</b>: un <font name='Mono'>Estado</font> compartido guarda lo "
          "averiguado (tipo, prioridad, causa, servicio, citas, acciones, traza y pasos). "
          "Cada agente recibe un resumen JSON de ese estado, no la conversación entera: menos "
          "texto, menos créditos y menos confusión. En cada turno el modelo devuelve un único "
          "JSON (llamada a herramienta o salida final); el código valida el contrato y su "
          "prompt se genera desde el registro, con <b>solo</b> las herramientas permitidas a "
          "ese agente (mínimo privilegio)."),
        p("<b>Prioridades.</b> Las propone el clasificador; el código la <b>sube</b> si los "
          "datos exigen más (nunca la baja) y un rechazo no tiene prioridad. Servicios "
          "críticos: vpn, correo, erp, ficheros e intranet (la intranet aloja el autoservicio "
          "de contraseñas: si falla es un problema de seguridad). No críticos: impresión y "
          "wifi de invitados."),
        tabla([
            ["", "Criterio", "Ejemplo en los datos", "1.ª respuesta"],
            ["P1", "Afecta a más de una oficina, o un servicio crítico está caído",
             "vpn caída en MAD-01; erp caído en MAD-02 y BCN-01", "15 min"],
            ["P2", "Afecta a una oficina entera, o un crítico está degradado",
             "correo degradado en BCN-01", "30 min"],
            ["P3", "Un empleado no puede trabajar y no tiene alternativa",
             "PC sin red en VAL-01 (tarjeta averiada)", "2 h"],
            ["P4", "Molestia con alternativa",
             "una impresora (hay otras), el equipo va lento", "1 día laborable"],
        ], [1, 6.5, 6.8, 2.7]),

        h("3. Modelos de lenguaje"),
        p("Los cuatro modelos cumplen el mismo contrato, <font name='Mono'>generar(sistema, "
          "mensajes) → texto</font>, así que el resto del sistema no sabe cuál usa y las "
          "reglas se aplican igual con todos."),
        tabla([
            ["Modelo", "Qué es", "Para qué se usa", "Qué necesita"],
            ["ScriptedModel", "Respuestas fijadas de antemano",
             "Las 289 pruebas y la evaluación", "Nada"],
            ["ModeloSimulado", "Reglas por palabras clave, determinista",
             "Demo sin token y web (por defecto)", "Nada"],
            ["ModeloOllama (qwen2.5:14b)", "Modelo real ejecutado en mi ordenador con Ollama",
             "Las dos trazas reales del informe", "Gratis: instalar Ollama y el modelo (9 GB)"],
            ["ModeloHF (Qwen2.5-72B)", "Modelo real en los servidores de Hugging Face",
             "Opcional", "Token y créditos de pago"],
        ], [3.6, 4.6, 4.4, 4.4]),
        Spacer(1, 4),
        p("El plan inicial era Hugging Face, pero ya no da créditos gratuitos: dos cuentas "
          "devolvieron <i>402 Payment Required</i>. Como indicó el profesor en clase, usé "
          "Ollama, que ejecuta el modelo en local sin token ni coste. El código de Hugging "
          "Face sigue disponible con <font name='Mono'>--modelo hf</font>. Para corregir no "
          "hace falta ninguno de los dos: las pruebas y el README usan el simulado."),

        h("4. Herramientas y conocimiento"),
        p("Siete herramientas en un registro con <b>descripción</b> y marca de "
          "<b>reversible</b>; todas pasan por un único punto (<font name='Mono'>ejecutar</font>) "
          "que convierte cualquier fallo en <font name='Mono'>ErrorHerramienta</font>. Las dos "
          "irreversibles (reiniciar_servicio, cerrar_ticket) nunca se ejecutan dentro del "
          "bucle de un agente: conocimiento solo las propone. Los datos de la red se cargan en "
          "memoria, así que cada ejecución parte del mismo estado."),
        p("La recuperación es un <b>BM25 escrito a mano</b> sobre 15 documentos propios "
          "(11 artículos kb-* con Síntomas, Causa y Pasos, y 4 políticas: catálogo de "
          "servicios, escalado, reinicios y prioridades). Cada fragmento es una sección, así "
          "que las citas son precisas (<font name='Mono'>docs/kb-red-01.md#Pasos</font>). Lo "
          "elegí frente a embeddings porque no necesita red ni dependencias, es determinista y "
          "explicable. Limitación: no entiende sinónimos; se mitiga con frases de empleados en "
          "cada sección de síntomas."),

        h("5. Robustez y seguridad"),
        tabla([
            ["Regla (en código)", "Qué garantiza"],
            ["R1 Confirmación", "Una acción irreversible solo se ejecuta si confirmar() devuelve "
             "verdadero. Si la persona dice que no, no se ejecuta y se escala."],
            ["R2 Guardarraíl", "Un servicio crítico en horario laboral solo se reinicia si es el "
             "diagnosticado y está caído o degradado; nunca en otra oficina; máximo un reinicio "
             "por servicio. Si bloquea, ni siquiera se pregunta."],
            ["R3 Tope", "12 pasos (respuestas del modelo y herramientas): evita bucles y limita "
             "el gasto. Al superarlo, tope_alcanzado."],
            ["R4 Errores", "Errores de herramienta, herramienta no permitida y JSON ilegible "
             "son observaciones; dos ilegibles seguidas → escalado."],
            ["R5 Citas", "Una cita solo vale si ese fragmento lo devolvió buscar_docs en esta "
             "ejecución; las inventadas se borran. Sin cita válida no hay resuelto."],
        ], [3.2, 13.8]),
        Spacer(1, 4),
        p("Además: la prioridad la sube el código si los datos lo exigen (un crítico caído es "
          "P1 aunque el modelo diga P3) y nunca la baja; la respuesta al empleado la redacta "
          "una plantilla, así que el modelo no puede prometer plazos. En Claude Code, "
          "<font name='Mono'>settings.json</font> permite solo leer y probar, pide permiso para "
          "dependencias, ejecuciones que gastan créditos y commits, y prohíbe leer "
          "<font name='Mono'>.env</font> (también por terminal), borrar, publicar y sacar "
          "datos. El token vive solo en mi <font name='Mono'>.env</font>: no está en el código "
          "ni en la entrega."),

        h("6. Pruebas y evaluación"),
        p("289 pruebas con <b>dobles del modelo</b> (ScriptedModel con respuestas fijadas y un "
          "cliente falso para Hugging Face): deterministas, sin red y sin token. Cada regla "
          "R1–R5 tiene pruebas que fallan si se rompe; se comprobó rompiendo cada regla a "
          "propósito (mutaciones)."),
        p("La <b>evaluación</b> son 11 casos cuyo resultado esperado definí yo aplicando mis "
          "reglas, sin mirar el código (oráculo independiente). Mide el <b>resultado</b> "
          "(final, tipo, prioridad) y la <b>trayectoria</b> (C = clasificador, D = diagnóstico, "
          "K = conocimiento, E = escalado). Se ejecuta con guion (comprueba las reglas) y con "
          "el modelo simulado (lo que vería un usuario sin token)."),
        tabla([
            ["#", "Caso", "Esperado: final · tipo · prioridad · trayectoria"],
            ["1", "«no tengo internet», MAD-01, confirma (vpn caída)", "resuelto · red · P1 · C-D-K"],
            ["2", "Igual, pero rechaza el reinicio (R1)", "escalado · red · P1 · C-D-K-E"],
            ["3", "«no tengo internet», VAL-01 (tarjeta rota): mismo síntoma, otra causa",
             "resuelto · red · P3 · C-D-K"],
            ["4", "Impresora, MAD-02, T-0007 reabierto", "escalado · impresora · P4 · C-D-E"],
            ["5", "ERP caído en MAD-02 y BCN-01; el modelo dice P2",
             "escalado · acceso_aplicacion · P1 · C-D-E"],
            ["6", "Correo degradado, BCN-01; el modelo dice P4", "resuelto · correo · P2 · C-D-K"],
            ["7", "«¿me recomiendas un restaurante?»", "rechazado · fuera_de_ambito · — · C"],
            ["8", "Oficina inexistente (SEV-01)", "rechazado · — · — · sin agentes"],
            ["9", "Cita inventada por el modelo (R5)", "escalado · red · P1 · C-D-K-E"],
            ["10", "Propone reiniciar el ERP con la vpn diagnosticada (R2)",
             "escalado · red · P1 · C-D-K-E"],
            ["11", "«me va lento el ordenador» (caso propio)", "resuelto · hardware · P4 · C-D-K"],
        ], [0.8, 8.2, 8]),
        Spacer(1, 4),
        p("<b>Primera pasada: 9/11 con guion y 6/9 con el simulado.</b> No cambié lo esperado; "
          "analicé cada fallo. Uno era del código (un rechazo conservaba la prioridad P4 del "
          "clasificador: lo que no se tramita no debe tener prioridad), otro de contenido (no "
          "había artículo de equipos lentos) y tres del simulado (no reconocía lo que está "
          "fuera de ámbito ni «ordenador», y empezaba siempre en P3). El caso 11 con el "
          "simulado <b>acertaba el final por casualidad</b>: «resuelto» citando el artículo de "
          "la tarjeta de red. Por eso se evalúa también la trayectoria y los datos. Tras los "
          "arreglos: <b>11/11 y 9/9</b>."),

        h("7. Dos trazas reales"),
        p("Con Ollama (sección 3, <font name='Mono'>--modelo ollama</font>). Con "
          "<b>qwen2.5:7b</b> las primeras trazas acabaron escaladas: el "
          "modelo devolvía JSON fuera de contrato (R4), no consultaba herramientas y se "
          "inventaba citas (R5 las eliminó). Las reglas evitaron cualquier daño, pero el "
          "prompt no decía el formato exacto, los valores permitidos ni qué es cada servicio. "
          "Lo añadí (generado desde las mismas listas que valida el código) y pasé a "
          "<b>qwen2.5:14b</b>. Estas son las trazas finales, tal cual las imprime "
          "<font name='Mono'>--traza</font>; coinciden con mis casos 1 y 5."),
        *traza(1, "«no tengo internet» en MAD-01: pide confirmación del reinicio de la vpn "
                  "(respondo «s»)."),
        Spacer(1, 4),
        *traza(2, "«no puedo entrar en el ERP» en MAD-02: avería en varias oficinas, "
                  "escalado P1."),

        h("8. Forma de trabajo y limitaciones"),
        p("Dirigí a Claude Code con un <b>CLAUDE.md</b> de menos de 200 líneas (contratos, "
          "reglas y valores cerrados), permisos de mínimo privilegio y <b>una orden por "
          "hito</b> con criterios comprobables (hitos 0 a 7b). Las decisiones son mías; Claude "
          "Code redactó a partir de ellas y generó el código, que revisé. El "
          "<font name='Mono'>worklog.md</font> recoge decisiones, problemas, comprobaciones y "
          "quién redactó cada cosa."),
        *lista(
            "El simulado funciona por palabras clave: una frase sin ninguna conocida puede "
            "clasificarse mal. Con el modelo real decide el clasificador.",
            "R5 comprueba que la cita se recuperó, no que sea relevante.",
            "BM25 no entiende sinónimos; con más documentos convendría una búsqueda híbrida.",
            "Con un modelo real pequeño, el agente de escalado puede listar en «probado» "
            "cosas que nadie probó; no es peligroso, pero sí inexacto.",
            "El tope de 12 pasos bastó con el modelo real (9 pasos en la traza más larga).",
        ),
        Spacer(1, 3),
        p("<b>Reproducir:</b> <font name='Mono'>uv sync</font> · <font name='Mono'>uv run "
          "pytest</font> · órdenes del README (modelo simulado por defecto, sin token)."),
    ]
    return c


def main() -> None:
    salida = RAIZ / "informe.pdf"
    doc = SimpleDocTemplate(str(salida), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.7 * cm, bottomMargin=2 * cm, author=AUTOR,
                            title="Soporte técnico de una red de oficinas")
    doc.build(contenido(), onFirstPage=pie, onLaterPages=pie)
    print(salida)


if __name__ == "__main__":
    main()
