from __future__ import annotations

import os
import sys
from pathlib import Path


def _configure_tk_environment() -> None:
    python_base = Path(sys.executable).resolve().parent
    tcl_path = python_base / "tcl" / "tcl8.6"
    tk_path = python_base / "tcl" / "tk8.6"
    if tcl_path.exists():
        os.environ.setdefault("TCL_LIBRARY", str(tcl_path))
    if tk_path.exists():
        os.environ.setdefault("TK_LIBRARY", str(tk_path))


def main() -> None:
    _configure_tk_environment()
    try:
        from bookstore.ui import BookStoreApp
    except Exception as error:
        print("Не удалось запустить графический интерфейс.")
        print(f"Причина: {error}")
        print("Проверьте, что Python установлен вместе с компонентом Tcl/Tk.")
        return

    try:
        app = BookStoreApp()
    except Exception as error:
        print("Приложение не смогло инициализировать окно.")
        print(f"Причина: {error}")
        print("Обычно это связано с отсутствием рабочего Tcl/Tk в локальном Python.")
        return
    app.mainloop()


if __name__ == "__main__":
    main()
