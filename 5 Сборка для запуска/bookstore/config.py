from pathlib import Path


BUILD_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BUILD_DIR.parent
IMPORT_DIR = PROJECT_DIR / "import"
UPLOADED_IMAGES_DIR = BUILD_DIR / "images"
ER_DIR = PROJECT_DIR / "1 ER и блок-схемы"
DATABASE_DIR = PROJECT_DIR / "2 База Данных"
DB_PATH = DATABASE_DIR / "bookstore.db"
SCHEMA_PATH = DATABASE_DIR / "schema.sql"
ER_PDF_PATH = ER_DIR / "er_diagram.pdf"
ALGORITHM_PDF_PATH = ER_DIR / "algorithm.pdf"
ICON_PATH = IMPORT_DIR / "icon.ico"
LOGO_PATH = IMPORT_DIR / "icon.png"
PLACEHOLDER_IMAGE_PATH = IMPORT_DIR / "picture.png"

WINDOW_TITLE = "ООО «ЧитайГород»"

MAIN_BG = "#FFFFFF"
SECONDARY_BG = "#ABCFCE"
ACCENT_BG = "#546F94"
HIGHLIGHT_BG = "#23E1EF"
OUT_OF_STOCK_BG = "#D9D9D9"
TEXT_COLOR = "#1F1F1F"

FONT_FAMILY = "Comic Sans MS"
