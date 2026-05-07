"""
payments/pdf_generator.py
Rasmiylashtirilgan OSAGO polis PDF yaratish (ReportLab)
"""

import os
import logging
from io import BytesIO
from django.core.files.base import ContentFile
from django.conf import settings

logger = logging.getLogger(__name__)


def generate_policy_pdf(application):
    """
    OSAGO polisi uchun PDF fayl yaratish va modelga saqlash.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "Title", parent=styles["Title"],
            fontSize=16, textColor=colors.HexColor("#1a3a5c"),
            spaceAfter=12,
        )
        subtitle_style = ParagraphStyle(
            "Subtitle", parent=styles["Normal"],
            fontSize=10, textColor=colors.HexColor("#555555"),
            spaceAfter=20,
        )
        header_style = ParagraphStyle(
            "Header", parent=styles["Normal"],
            fontSize=11, fontName="Helvetica-Bold",
            textColor=colors.HexColor("#1a3a5c"), spaceAfter=6,
        )

        story = []

        # Sarlavha
        story.append(Paragraph("KAFIL-SUG'URTA", title_style))
        story.append(Paragraph("OSAGO — Majburiy sug'urta polisi", subtitle_style))
        story.append(Spacer(1, 0.3*cm))

        # Polis raqami
        story.append(Paragraph(f"Polis raqami: {application.external_policy_id or str(application.id)[:8].upper()}", header_style))
        story.append(Spacer(1, 0.5*cm))

        # Asosiy ma'lumotlar jadvali
        table_data = [
            ["Maydon", "Ma'lumot"],
            ["Avtomobil raqami", application.plate_number],
            ["Tex-pasport", application.tech_passport],
            ["Avtomobil", f"{application.vehicle_brand} {application.vehicle_model} ({application.vehicle_year or '—'})"],
            ["Egasining FIO", application.owner_full_name],
            ["Sug'urta boshlanishi", str(application.coverage_start)],
            ["Sug'urta tugashi", str(application.coverage_end)],
            ["Sug'urta muddati", f"{application.coverage_period_months} oy"],
            ["Sug'urta mukofoti", f"{application.premium_amount:,.0f} so'm"],
            ["Holat", "FAOL"],
        ]

        col_widths = [6*cm, 10*cm]
        t = Table(table_data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 1*cm))

        # Eslatma
        story.append(Paragraph(
            "Ushbu hujjat KAFIL-SUG'URTA tomonidan elektron tarzda yaratilgan va "
            "O'zbekiston qonunchiligiga muvofiq yuridik kuchga ega.",
            styles["Normal"]
        ))

        doc.build(story)

        pdf_bytes = buffer.getvalue()
        buffer.close()

        filename = f"osago_policy_{application.id}.pdf"
        application.policy_pdf.save(filename, ContentFile(pdf_bytes), save=True)
        logger.info(f"[PDF] Generated for application {application.id}")

    except Exception as e:
        logger.exception(f"[PDF] Error generating for {application.id}: {e}")
        raise
