from __future__ import annotations

import datetime as dt
import os
import xml.etree.ElementTree as element_tree
import zipfile
from dataclasses import dataclass
from pathlib import Path

from bookstore.config import IMPORT_DIR


EXCEL_NAMESPACE = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


@dataclass(slots=True)
class ProductSeed:
    article: str
    name: str
    unit: str
    price: float
    supplier: str
    manufacturer: str
    category: str
    discount: float
    stock: int
    description: str
    image_name: str


@dataclass(slots=True)
class UserSeed:
    role: str
    full_name: str
    login: str
    password: str


@dataclass(slots=True)
class OrderSeed:
    order_number: int
    items: list[tuple[str, int]]
    order_date: str
    delivery_date: str
    pickup_point_index: int
    customer_name: str
    pickup_code: str
    status: str


def _read_rows(xlsx_path: Path) -> list[list[str]]:
    namespace = {"a": EXCEL_NAMESPACE}
    with zipfile.ZipFile(xlsx_path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = element_tree.fromstring(archive.read("xl/sharedStrings.xml"))
            for shared_item in shared_root.findall("a:si", namespace):
                text = "".join(node.text or "" for node in shared_item.iterfind(".//a:t", namespace))
                shared_strings.append(text)

        workbook_root = element_tree.fromstring(archive.read("xl/workbook.xml"))
        rels_root = element_tree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels_root}
        sheet = next(iter(workbook_root.find(f"{{{EXCEL_NAMESPACE}}}sheets")))
        relation_id = sheet.attrib[f"{{{RELATIONSHIP_NAMESPACE}}}id"]
        sheet_path = "xl/" + rel_map[relation_id]
        worksheet_root = element_tree.fromstring(archive.read(sheet_path))

        rows: list[list[str]] = []
        for row in worksheet_root.findall(
            f".//{{{EXCEL_NAMESPACE}}}sheetData/{{{EXCEL_NAMESPACE}}}row"
        ):
            values: list[str] = []
            for cell in row.findall(f"{{{EXCEL_NAMESPACE}}}c"):
                cell_type = cell.attrib.get("t")
                value_node = cell.find(f"{{{EXCEL_NAMESPACE}}}v")
                value = "" if value_node is None else value_node.text or ""
                if cell_type == "s" and value:
                    value = shared_strings[int(value)]
                values.append(value)
            rows.append(values)
        return rows


def _excel_date_to_iso(serialized_value: str) -> str:
    value = serialized_value.strip()
    if "." in value:
        day, month, year = (int(part) for part in value.split("."))
        while day > 28:
            try:
                return dt.date(year, month, day).isoformat()
            except ValueError:
                day -= 1
        return dt.date(year, month, day).isoformat()
    base_date = dt.datetime(1899, 12, 30)
    return (base_date + dt.timedelta(days=int(float(value)))).date().isoformat()


def load_products() -> list[ProductSeed]:
    rows = _read_rows(IMPORT_DIR / "Tovar.xlsx")
    products: list[ProductSeed] = []
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        products.append(
            ProductSeed(
                article=row[0].strip(),
                name=row[1].strip(),
                unit=row[2].strip(),
                price=float(row[3]),
                supplier=row[4].strip(),
                manufacturer=row[5].strip(),
                category=row[6].strip(),
                discount=float(row[7]),
                stock=int(float(row[8])),
                description=row[9].strip(),
                image_name=row[10].strip(),
            )
        )
    return products


def load_staff_users() -> list[UserSeed]:
    rows = _read_rows(IMPORT_DIR / "user_import.xlsx")
    users: list[UserSeed] = []
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        role_name = row[0].strip()
        normalized_role = "Клиент" if "клиент" in role_name.lower() else role_name
        users.append(
            UserSeed(
                role=normalized_role,
                full_name=row[1].strip(),
                login=row[2].strip(),
                password=row[3].strip(),
            )
        )
    return users


def load_pickup_points() -> list[str]:
    path = next(file for file in IMPORT_DIR.iterdir() if file.suffix == ".xlsx" and "Пункты" in file.name)
    rows = _read_rows(path)
    return [row[0].strip() for row in rows if row and row[0].strip()]


def load_orders() -> list[OrderSeed]:
    path = next(file for file in IMPORT_DIR.iterdir() if file.suffix == ".xlsx" and "Заказ" in file.name)
    rows = _read_rows(path)
    orders: list[OrderSeed] = []
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        raw_parts = [part.strip() for part in row[1].split(",") if part.strip()]
        items = [(raw_parts[index], int(raw_parts[index + 1])) for index in range(0, len(raw_parts), 2)]
        orders.append(
            OrderSeed(
                order_number=int(row[0]),
                items=items,
                order_date=_excel_date_to_iso(row[2]),
                delivery_date=_excel_date_to_iso(row[3]),
                pickup_point_index=int(row[4]),
                customer_name=row[5].strip(),
                pickup_code=row[6].strip(),
                status=row[7].strip(),
            )
        )
    return orders


def build_client_accounts(order_seeds: list[OrderSeed]) -> list[UserSeed]:
    clients: list[UserSeed] = []
    for index, full_name in enumerate(sorted({order.customer_name for order in order_seeds}), start=1):
        clients.append(
            UserSeed(
                role="Клиент",
                full_name=full_name,
                login=f"client{index}",
                password="client123",
            )
        )
    return clients


def resolve_import_image(image_name: str) -> Path | None:
    if not image_name:
        return None
    candidate = IMPORT_DIR / os.path.basename(image_name)
    if candidate.exists():
        return candidate
    return None
