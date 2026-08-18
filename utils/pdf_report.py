"""
utils/pdf_report.py
====================
PURPOSE: Generate a professional PDF report of all student drift scores.
         The teacher clicks "Download Report" on the dashboard and gets
         a PDF they can save, print, or email to parents/management.

LIBRARY: reportlab — install with: pip install reportlab
"""

import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, HRFlowable
)


# Colour constants matching the dashboard
RED    = colors.HexColor("#e74c3c")
ORANGE = colors.HexColor("#e67e22")
GREEN  = colors.HexColor("#27ae60")
BLUE   = colors.HexColor("#2c3e50")
LIGHT  = colors.HexColor("#f8f9fa")
WHITE  = colors.white


def generate_pdf(alerted: list, watched: list, healthy: list) -> bytes:
    """
    Builds the PDF in memory and returns it as bytes.

    alerted / watched / healthy: lists of (Student, DriftRecord) tuples
    Returns: raw PDF bytes — we send these directly to the browser.

    Why bytes?
      We never save to disk — we build the PDF in memory using io.BytesIO
      and stream it straight to the browser. Faster and cleaner.
    """

    buffer = io.BytesIO()   # In-memory file — no disk needed

    doc = SimpleDocTemplate(
        buffer,
        pagesize      = A4,
        rightMargin   = 2 * cm,
        leftMargin    = 2 * cm,
        topMargin     = 2 * cm,
        bottomMargin  = 2 * cm,
    )

    styles  = getSampleStyleSheet()
    content = []   # List of flowable elements — reportlab renders them top to bottom

    # ── Title ────────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "Title",
        parent    = styles["Heading1"],
        fontSize  = 20,
        textColor = BLUE,
        spaceAfter= 4,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent    = styles["Normal"],
        fontSize  = 10,
        textColor = colors.grey,
        spaceAfter= 16,
    )

    content.append(Paragraph("Behavior Drift Detection Report", title_style))
    content.append(Paragraph(
        f"Generated: {datetime.utcnow().strftime('%d %B %Y, %H:%M UTC')}  |  "
        f"Total students: {len(alerted) + len(watched) + len(healthy)}",
        subtitle_style
    ))
    content.append(HRFlowable(width="100%", thickness=1, color=BLUE))
    content.append(Spacer(1, 0.4 * cm))

    # ── Summary box ──────────────────────────────────────────────────
    summary_data = [
        ["Need Attention", "On Watch List", "Healthy", "Total"],
        [
            str(len(alerted)),
            str(len(watched)),
            str(len(healthy)),
            str(len(alerted) + len(watched) + len(healthy))
        ],
    ]
    summary_table = Table(summary_data, colWidths=[4 * cm] * 4)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR",   (0, 0), (-1, 0), WHITE),
        ("FONTSIZE",    (0, 0), (-1, 0), 10),
        ("FONTSIZE",    (0, 1), (-1, 1), 18),
        ("FONTNAME",    (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR",   (0, 1), (0, 1),  RED),
        ("TEXTCOLOR",   (1, 1), (1, 1),  ORANGE),
        ("TEXTCOLOR",   (2, 1), (2, 1),  GREEN),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, 1), [LIGHT]),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("TOPPADDING",  (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
    ]))
    content.append(summary_table)
    content.append(Spacer(1, 0.6 * cm))

    # ── Section helper ───────────────────────────────────────────────
    section_style = ParagraphStyle(
        "Section",
        parent    = styles["Heading2"],
        fontSize  = 13,
        textColor = WHITE,
        spaceAfter= 0,
    )

    def section_header(text: str, bg_color) -> Table:
        """Returns a colored section header as a table row."""
        t = Table([[Paragraph(text, section_style)]], colWidths=[17 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), bg_color),
            ("TOPPADDING",   (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
            ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ]))
        return t

    def student_table(pairs: list) -> Table:
        """
        Builds the table of student rows.
        pairs: list of (Student, DriftRecord)
        """
        header = ["Student", "Course", "Drift", "Score", "Session", "Submit", "Notes"]
        rows   = [header]

        for student, record in pairs:
            rows.append([
                student.name,
                student.course,
                f"{record.drift_score:.2f}",
                f"{record.score_drift:.2f}",
                f"{record.session_drift:.2f}",
                f"{record.submission_drift:.2f}",
                (record.notes or "")[:40],   # Truncate long notes
            ])

        col_widths = [4*cm, 3.5*cm, 1.5*cm, 1.5*cm, 1.8*cm, 1.5*cm, 3.2*cm]
        t = Table(rows, colWidths=col_widths)
        t.setStyle(TableStyle([
            # Header row
            ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#ecf0f1")),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("ALIGN",         (2, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("GRID",          (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            # Alternate row shading
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT]),
        ]))
        return t

    # ── Alert section ─────────────────────────────────────────────────
    content.append(section_header(f"Needs Immediate Attention ({len(alerted)})", RED))
    content.append(Spacer(1, 0.2 * cm))
    if alerted:
        content.append(student_table(alerted))
    else:
        content.append(Paragraph(
            "No students above alert threshold.",
            ParagraphStyle("ok", parent=styles["Normal"],
                           textColor=GREEN, fontSize=10)
        ))
    content.append(Spacer(1, 0.5 * cm))

    # ── Watch section ─────────────────────────────────────────────────
    content.append(section_header(f"Watch List ({len(watched)})", ORANGE))
    content.append(Spacer(1, 0.2 * cm))
    if watched:
        content.append(student_table(watched))
    else:
        content.append(Paragraph(
            "No students on watch list.",
            ParagraphStyle("ok", parent=styles["Normal"],
                           textColor=colors.grey, fontSize=10)
        ))
    content.append(Spacer(1, 0.5 * cm))

    # ── Healthy section ───────────────────────────────────────────────
    content.append(section_header(f"Healthy Students ({len(healthy)})", GREEN))
    content.append(Spacer(1, 0.2 * cm))
    if healthy:
        content.append(student_table(healthy))
    content.append(Spacer(1, 0.5 * cm))

    # ── Footer note ───────────────────────────────────────────────────
    content.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    content.append(Spacer(1, 0.2 * cm))
    content.append(Paragraph(
        "Drift scores range from 0.00 (no drift) to 1.00 (maximum drift). "
        f"Alert threshold: 0.35 | Watch threshold: 0.20 | "
        f"Scores calculated from last 7 days vs 30-day baseline.",
        ParagraphStyle("footer", parent=styles["Normal"],
                       fontSize=8, textColor=colors.grey)
    ))

    # Build the PDF — this writes everything into the buffer
    doc.build(content)

    # Return the raw bytes
    return buffer.getvalue()