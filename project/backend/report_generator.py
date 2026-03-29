from __future__ import annotations

import datetime
import os
import tempfile
from typing import Any

from PIL import Image as PILImage
from PIL import ImageDraw
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _extract_score(det: dict[str, Any]) -> float:
    raw = det.get("score", det.get("confidence", det.get("confidence_score", 0.0)))
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _extract_bbox(det: dict[str, Any]) -> tuple[float, float, float, float]:
    bbox = det.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        x1, y1, x2, y2 = bbox
        return float(x1), float(y1), float(x2), float(y2)

    bbox_zyx = det.get("bbox_zyx")
    if isinstance(bbox_zyx, (list, tuple)) and len(bbox_zyx) == 6:
        _z1, y1, x1, _z2, y2, x2 = bbox_zyx
        return float(x1), float(y1), float(x2), float(y2)

    center = det.get("center")
    if isinstance(center, (list, tuple)) and len(center) >= 3:
        cx = float(center[2])
        cy = float(center[1])
        half = 18.0
        return cx - half, cy - half, cx + half, cy + half

    return 0.0, 0.0, 0.0, 0.0


def _risk_from_total(total: int) -> str:
    if total == 0:
        return "Low"
    if total <= 2:
        return "Medium"
    return "High"


def _clinical_notes(risk: str) -> str:
    if risk == "Low":
        return "No significant nodules detected. Routine monitoring recommended."
    if risk == "Medium":
        return "Few nodules detected. Follow-up scan in 3-6 months advised."
    return "Multiple nodules detected. Immediate clinical evaluation required."


def _prepare_overlay_image(image_path: str, detections: list[dict[str, Any]]) -> str | None:
    if not image_path or not os.path.exists(image_path):
        return None

    with PILImage.open(image_path) as src:
        img = src.convert("RGB")

    draw = ImageDraw.Draw(img)
    for idx, det in enumerate(detections, start=1):
        x1, y1, x2, y2 = _extract_bbox(det)
        if x2 <= x1 or y2 <= y1:
            continue

        draw.rectangle((x1, y1, x2, y2), outline=(220, 38, 38), width=3)
        label = f"Nodule {idx} ({_extract_score(det):.2f})"
        label_y = max(0, y1 - 16)
        draw.rectangle((x1, label_y, min(img.width - 1, x1 + 170), label_y + 14), fill=(220, 38, 38))
        draw.text((x1 + 4, label_y), label, fill=(255, 255, 255))

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp_path = tmp.name
    tmp.close()
    img.save(tmp_path)
    return tmp_path


def generate_pdf(
    report_path: str,
    image_path: str,
    detections: list[dict[str, Any]],
    scan_id: str = "N/A",
    report_text: str | None = None,
) -> None:
    doc = SimpleDocTemplate(report_path, pagesize=A4)
    styles = getSampleStyleSheet()

    elements = []

    title_style = ParagraphStyle(
        "title",
        parent=styles["Title"],
        fontSize=18,
        textColor=colors.HexColor("#1f2937"),
        spaceAfter=10,
    )
    section_style = ParagraphStyle(
        "section",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#2563eb"),
        spaceAfter=6,
    )
    normal = styles["Normal"]

    elements.append(Paragraph("🫁 Lung Nodule Detection Report", title_style))
    elements.append(Spacer(1, 8))

    meta_table = Table(
        [
            ["Scan ID", scan_id],
            ["Date", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")],
        ],
        colWidths=[2 * inch, 4 * inch],
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ]
        )
    )

    elements.append(meta_table)
    elements.append(Spacer(1, 16))

    total = len(detections)
    risk = _risk_from_total(total)
    risk_color = colors.green if risk == "Low" else colors.orange if risk == "Medium" else colors.red

    elements.append(Paragraph("Summary", section_style))

    summary_table = Table([["Total Nodules", total], ["Risk Level", risk]])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                ("TEXTCOLOR", (1, 1), (1, 1), risk_color),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ]
        )
    )
    elements.extend([summary_table, Spacer(1, 16)])

    elements.append(Paragraph("Detected Nodules", section_style))

    table_data = [["#", "Confidence", "Size", "Location"]]
    for i, det in enumerate(detections):
        x1, y1, x2, y2 = _extract_bbox(det)
        size = int(max(x2 - x1, y2 - y1))
        score = _extract_score(det)
        table_data.append([
            i + 1,
            f"{score:.2f}",
            f"{size}px",
            f"({int(x1)}, {int(y1)})",
        ])

    if len(table_data) == 1:
        table_data.append(["-", "0.00", "0px", "(0, 0)"])

    table = Table(table_data, colWidths=[0.8 * inch, 1.4 * inch, 1.2 * inch, 2.6 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    elements.extend([table, Spacer(1, 20)])

    if report_text:
        safe_text = report_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        elements.extend(
            [
                Paragraph("AI Clinical Summary", section_style),
                Spacer(1, 8),
                Paragraph(safe_text.replace("\n", "<br/>"), normal),
                Spacer(1, 20),
            ]
        )

    elements.append(Paragraph("CT Scan with Detection", section_style))
    if image_path and os.path.exists(image_path):
        try:
            img = RLImage(image_path, width=5 * inch, height=5 * inch)
            img.hAlign = "CENTER"
            framed = Table([[img]], colWidths=[5.2 * inch])
            framed.setStyle(
                TableStyle(
                    [
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                        ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            elements.append(framed)
        except Exception:
            elements.append(Paragraph("Image not available", normal))
    else:
        elements.append(Paragraph("Image not available", normal))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("Clinical Notes", section_style))
    notes = Paragraph(_clinical_notes(risk), normal)
    elements.append(notes)

    doc.build(elements)


def generate_pdf_bytes(
    detections: list[dict[str, Any]],
    scan_id: str = "N/A",
    report_text: str | None = None,
    image_path: str | None = None,
    preview_image: PILImage.Image | None = None,
) -> bytes:
    temp_paths: list[str] = []

    if preview_image is not None:
        preview_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        preview_path = preview_tmp.name
        preview_tmp.close()
        preview_image.convert("RGB").save(preview_path)
        image_path = preview_path
        temp_paths.append(preview_path)

    overlay_path = _prepare_overlay_image(image_path or "", detections)
    if overlay_path:
        temp_paths.append(overlay_path)

    pdf_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf_path = pdf_tmp.name
    pdf_tmp.close()
    temp_paths.append(pdf_path)

    try:
        generate_pdf(
            report_path=pdf_path,
            image_path=overlay_path or (image_path or ""),
            detections=detections,
            scan_id=scan_id,
            report_text=report_text,
        )
        with open(pdf_path, "rb") as f:
            return f.read()
    finally:
        for path in temp_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
