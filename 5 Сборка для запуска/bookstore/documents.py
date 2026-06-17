from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from bookstore.config import ALGORITHM_PDF_PATH, ER_DIR, ER_PDF_PATH


LINE_COLOR = colors.black
HEADER_FILL = colors.HexColor("#DCEAF7")
BOX_FILL = colors.white


def _register_font() -> str:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            pdfmetrics.registerFont(TTFont("ProjectFont", str(candidate)))
            return "ProjectFont"
    return "Helvetica"


def generate_required_documents() -> None:
    ER_DIR.mkdir(parents=True, exist_ok=True)
    font_name = _register_font()
    _generate_er_diagram(font_name)
    _generate_algorithm_diagram(font_name)


def _draw_text_block(
    pdf: canvas.Canvas,
    lines: list[str],
    center_x: float,
    top_y: float,
    font_name: str,
    font_size: int,
    gap: int,
) -> None:
    pdf.setFont(font_name, font_size)
    current_y = top_y
    for line in lines:
        pdf.drawCentredString(center_x, current_y, line)
        current_y -= gap


def _draw_entity(
    pdf: canvas.Canvas,
    x: int,
    y: int,
    width: int,
    title: str,
    attributes: list[str],
    font_name: str,
) -> None:
    line_gap = 18
    height = 42 + len(attributes) * line_gap + 12
    pdf.setLineWidth(1.8)
    pdf.setStrokeColor(LINE_COLOR)
    pdf.setFillColor(BOX_FILL)
    pdf.roundRect(x, y, width, height, 8, fill=1)
    pdf.setFillColor(HEADER_FILL)
    pdf.rect(x, y + height - 34, width, 34, fill=1, stroke=1)
    pdf.setFillColor(colors.black)
    pdf.setFont(font_name, 15)
    pdf.drawString(x + 10, y + height - 22, title)
    pdf.setFont(font_name, 11)
    current_y = y + height - 50
    for item in attributes:
        pdf.drawString(x + 10, current_y, item)
        current_y -= line_gap


def _draw_arrow(
    pdf: canvas.Canvas,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
) -> None:
    pdf.setLineWidth(2.2)
    pdf.setStrokeColor(LINE_COLOR)
    pdf.line(start_x, start_y, end_x, end_y)
    if abs(start_x - end_x) < 1:
        direction = 1 if end_y < start_y else -1
        pdf.line(end_x, end_y, end_x - 7, end_y + 10 * direction)
        pdf.line(end_x, end_y, end_x + 7, end_y + 10 * direction)
    elif end_x > start_x:
        pdf.line(end_x, end_y, end_x - 12, end_y + 7)
        pdf.line(end_x, end_y, end_x - 12, end_y - 7)
    else:
        pdf.line(end_x, end_y, end_x + 12, end_y + 7)
        pdf.line(end_x, end_y, end_x + 12, end_y - 7)


def _process_box(
    pdf: canvas.Canvas,
    x: int,
    y: int,
    width: int,
    height: int,
    lines: list[str],
    font_name: str,
) -> None:
    pdf.setLineWidth(2)
    pdf.setStrokeColor(LINE_COLOR)
    pdf.setFillColor(BOX_FILL)
    pdf.roundRect(x, y, width, height, 10, fill=1)
    pdf.setFillColor(colors.black)
    _draw_text_block(pdf, lines, x + width / 2, y + height - 24, font_name, 18, 21)


def _terminal_box(
    pdf: canvas.Canvas,
    x: int,
    y: int,
    width: int,
    height: int,
    text: str,
    font_name: str,
) -> None:
    pdf.setLineWidth(2.2)
    pdf.setStrokeColor(LINE_COLOR)
    pdf.setFillColor(HEADER_FILL)
    pdf.roundRect(x, y, width, height, 28, fill=1)
    pdf.setFillColor(colors.black)
    pdf.setFont(font_name, 20)
    pdf.drawCentredString(x + width / 2, y + height / 2 - 7, text)


def _decision_box(
    pdf: canvas.Canvas,
    center_x: int,
    center_y: int,
    width: int,
    height: int,
    lines: list[str],
    font_name: str,
) -> None:
    path = pdf.beginPath()
    path.moveTo(center_x, center_y + height / 2)
    path.lineTo(center_x + width / 2, center_y)
    path.lineTo(center_x, center_y - height / 2)
    path.lineTo(center_x - width / 2, center_y)
    path.close()
    pdf.setLineWidth(2.2)
    pdf.setStrokeColor(LINE_COLOR)
    pdf.setFillColor(BOX_FILL)
    pdf.drawPath(path, fill=1, stroke=1)
    pdf.setFillColor(colors.black)
    _draw_text_block(pdf, lines, center_x, center_y + 14, font_name, 17, 20)


def _generate_er_diagram(font_name: str) -> None:
    pdf = canvas.Canvas(str(ER_PDF_PATH), pagesize=landscape(A3))
    pdf.setTitle("ER diagram")
    pdf.setFont(font_name, 24)
    pdf.drawString(36, 790, "ER diagram: bookstore database")
    pdf.setFont(font_name, 13)
    pdf.drawString(36, 768, "Large contrast layout with clear keys and relations.")

    _draw_entity(pdf, 40, 560, 250, "roles", ["id PK", "name UNIQUE"], font_name)
    _draw_entity(pdf, 340, 500, 330, "users", ["id PK", "full_name", "login UNIQUE", "password", "role_id FK -> roles.id"], font_name)
    _draw_entity(pdf, 40, 350, 250, "categories", ["id PK", "name UNIQUE"], font_name)
    _draw_entity(pdf, 40, 150, 250, "suppliers", ["id PK", "name UNIQUE"], font_name)
    _draw_entity(pdf, 340, 150, 280, "manufacturers", ["id PK", "name UNIQUE"], font_name)
    _draw_entity(
        pdf,
        720,
        290,
        360,
        "products",
        [
            "id PK",
            "article UNIQUE",
            "name",
            "unit, price",
            "discount, stock",
            "description",
            "image_path",
            "category_id FK",
            "supplier_id FK",
            "manufacturer_id FK",
        ],
        font_name,
    )
    _draw_entity(pdf, 1140, 560, 300, "pickup_points", ["id PK", "address UNIQUE"], font_name)
    _draw_entity(pdf, 1140, 390, 300, "order_statuses", ["id PK", "name UNIQUE"], font_name)
    _draw_entity(
        pdf,
        1140,
        130,
        340,
        "orders",
        [
            "id PK",
            "order_number UNIQUE",
            "order_date",
            "delivery_date",
            "pickup_code",
            "pickup_point_id FK",
            "customer_id FK -> users.id",
            "status_id FK",
        ],
        font_name,
    )
    _draw_entity(
        pdf,
        1540,
        130,
        300,
        "order_items",
        ["id PK", "order_id FK -> orders.id", "product_id FK -> products.id", "quantity", "unit_price"],
        font_name,
    )

    _draw_arrow(pdf, 290, 620, 340, 620)
    _draw_arrow(pdf, 290, 410, 720, 470)
    _draw_arrow(pdf, 290, 210, 720, 430)
    _draw_arrow(pdf, 620, 210, 720, 390)
    _draw_arrow(pdf, 1080, 620, 1140, 620)
    _draw_arrow(pdf, 1080, 450, 1140, 450)
    _draw_arrow(pdf, 500, 500, 1310, 340)
    _draw_arrow(pdf, 1310, 560, 1310, 490)
    _draw_arrow(pdf, 1480, 250, 1540, 250)
    _draw_arrow(pdf, 1080, 340, 1540, 210)

    pdf.save()


def _generate_algorithm_diagram(font_name: str) -> None:
    pdf = canvas.Canvas(str(ALGORITHM_PDF_PATH), pagesize=landscape(A3))
    pdf.setTitle("Algorithm flowchart")
    pdf.setFont(font_name, 24)
    pdf.drawString(36, 790, "Application flowchart")
    pdf.setFont(font_name, 13)
    pdf.drawString(36, 768, "Clear sequence of startup, authorization and work with goods and orders.")

    _terminal_box(pdf, 790, 670, 230, 70, "Start", font_name)
    _process_box(pdf, 700, 550, 410, 90, ["Initialize database", "and import source data"], font_name)
    _process_box(pdf, 670, 410, 470, 95, ["Open login window", "or continue as guest"], font_name)
    _decision_box(pdf, 905, 280, 280, 120, ["Authorization", "successful?"], font_name)
    _process_box(pdf, 120, 110, 430, 95, ["Show product catalog", "for guest or client"], font_name)
    _process_box(pdf, 690, 110, 430, 95, ["Show catalog with search,", "filter and sorting"], font_name)
    _process_box(pdf, 1260, 110, 460, 95, ["Manage products and orders", "for administrator"], font_name)
    _terminal_box(pdf, 790, 20, 230, 70, "Exit", font_name)

    _draw_arrow(pdf, 905, 670, 905, 640)
    _draw_arrow(pdf, 905, 550, 905, 505)
    _draw_arrow(pdf, 905, 410, 905, 340)
    _draw_arrow(pdf, 765, 280, 520, 160)
    _draw_arrow(pdf, 1045, 280, 905, 205)
    _draw_arrow(pdf, 1120, 160, 1260, 160)
    _draw_arrow(pdf, 1490, 110, 1015, 90)

    pdf.setFont(font_name, 15)
    pdf.drawString(610, 210, "No")
    pdf.drawString(1060, 210, "Yes")
    pdf.drawString(1135, 170, "Admin")

    pdf.save()
