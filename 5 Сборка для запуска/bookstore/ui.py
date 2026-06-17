from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.font import Font

from PIL import Image, ImageTk

from bookstore.config import (
    ACCENT_BG,
    FONT_FAMILY,
    HIGHLIGHT_BG,
    ICON_PATH,
    LOGO_PATH,
    MAIN_BG,
    OUT_OF_STOCK_BG,
    SECONDARY_BG,
    TEXT_COLOR,
    WINDOW_TITLE,
)
from bookstore.database import Database, SessionUser


class BookStoreApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.database = Database()
        self.current_user = self.database.guest_user()
        self.product_form_window: ProductFormWindow | None = None
        self.order_form_window: OrderFormWindow | None = None

        self.title(WINDOW_TITLE)
        self.geometry("1260x820")
        self.configure(bg=MAIN_BG)
        self.minsize(1080, 720)
        if ICON_PATH.exists():
            self.iconbitmap(default=str(ICON_PATH))

        self.default_font = Font(family=FONT_FAMILY, size=10)
        self.option_add("*Font", self.default_font)

        self.container = tk.Frame(self, bg=MAIN_BG)
        self.container.pack(fill="both", expand=True)

        self.frames: dict[str, tk.Frame] = {}
        self.show_login()

    def show_login(self) -> None:
        self.current_user = self.database.guest_user()
        self._show_frame(LoginFrame)

    def show_catalog(self, user: SessionUser | None = None) -> None:
        if user is not None:
            self.current_user = user
        self._show_frame(CatalogFrame)

    def show_orders(self) -> None:
        self._show_frame(OrdersFrame)

    def _show_frame(self, frame_cls: type[tk.Frame]) -> None:
        for frame in self.frames.values():
            frame.destroy()
        self.frames.clear()
        frame = frame_cls(self.container, self)
        self.frames[frame_cls.__name__] = frame
        frame.pack(fill="both", expand=True)

    def show_error(self, message: str) -> None:
        messagebox.showerror("Ошибка", message, parent=self)

    def show_info(self, message: str) -> None:
        messagebox.showinfo("Информация", message, parent=self)

    def ask_yes_no(self, message: str) -> bool:
        return messagebox.askyesno("Подтверждение", message, parent=self)


class LoginFrame(tk.Frame):
    def __init__(self, master: tk.Misc, app: BookStoreApp) -> None:
        super().__init__(master, bg=MAIN_BG)
        self.app = app
        self.logo_image = self._load_logo()

        content = tk.Frame(self, bg=MAIN_BG)
        content.place(relx=0.5, rely=0.5, anchor="center")

        if self.logo_image:
            tk.Label(content, image=self.logo_image, bg=MAIN_BG).pack(pady=(0, 10))

        tk.Label(
            content,
            text="Вход в систему",
            bg=MAIN_BG,
            fg=TEXT_COLOR,
            font=(FONT_FAMILY, 18, "bold"),
        ).pack(pady=(0, 15))

        tk.Label(content, text="Логин", bg=MAIN_BG, anchor="w").pack(fill="x")
        self.login_entry = tk.Entry(content, width=36)
        self.login_entry.pack(pady=(0, 10))

        tk.Label(content, text="Пароль", bg=MAIN_BG, anchor="w").pack(fill="x")
        self.password_entry = tk.Entry(content, width=36, show="*")
        self.password_entry.pack(pady=(0, 15))
        self.password_entry.bind("<Return>", lambda _event: self.login())

        button_panel = tk.Frame(content, bg=MAIN_BG)
        button_panel.pack(fill="x", pady=(0, 15))
        tk.Button(
            button_panel,
            text="Войти",
            command=self.login,
            bg=ACCENT_BG,
            fg="white",
            width=16,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            button_panel,
            text="Войти как гость",
            command=lambda: self.app.show_catalog(self.app.database.guest_user()),
            bg=SECONDARY_BG,
            width=18,
        ).pack(side="left")

        demo_accounts = self.app.database.get_demo_accounts()
        demo_lines = ["Тестовые учетные записи:"]
        for account in demo_accounts:
            demo_lines.append(
                f"{account['role_name']}: {account['login']} / {account['password']}"
            )
        tk.Label(
            content,
            text="\n".join(demo_lines),
            justify="left",
            bg=SECONDARY_BG,
            padx=12,
            pady=12,
        ).pack(fill="x")

        self.login_entry.focus_set()

    def _load_logo(self) -> ImageTk.PhotoImage | None:
        if not LOGO_PATH.exists():
            return None
        image = Image.open(LOGO_PATH)
        image.thumbnail((220, 220))
        return ImageTk.PhotoImage(image)

    def login(self) -> None:
        user = self.app.database.authenticate(self.login_entry.get(), self.password_entry.get())
        if user is None:
            self.app.show_error("Неверный логин или пароль. Проверьте данные и повторите попытку.")
            return
        self.app.show_catalog(user)


class BaseAuthenticatedFrame(tk.Frame):
    def __init__(self, master: tk.Misc, app: BookStoreApp, title_text: str) -> None:
        super().__init__(master, bg=MAIN_BG)
        self.app = app
        self.title_text = title_text
        self._build_header()

    @property
    def role_name(self) -> str:
        return self.app.current_user.role_name

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=SECONDARY_BG, padx=12, pady=10)
        header.pack(fill="x")
        tk.Label(
            header,
            text=self.title_text,
            bg=SECONDARY_BG,
            font=(FONT_FAMILY, 16, "bold"),
        ).pack(side="left")
        tk.Label(
            header,
            text=f"{self.app.current_user.full_name} ({self.role_name})",
            bg=SECONDARY_BG,
        ).pack(side="right", padx=(12, 0))
        tk.Button(
            header,
            text="Выход",
            command=self.app.show_login,
            bg=ACCENT_BG,
            fg="white",
        ).pack(side="right")


class CatalogFrame(BaseAuthenticatedFrame):
    def __init__(self, master: tk.Misc, app: BookStoreApp) -> None:
        super().__init__(master, app, "Каталог товаров")
        self.search_var = tk.StringVar()
        self.discount_var = tk.StringVar(value="Все диапазоны")
        self.sort_field_var = tk.StringVar(value="name")
        self.sort_direction_var = tk.StringVar(value="asc")
        self.photo_cache: dict[str, ImageTk.PhotoImage] = {}

        self._build_toolbar()
        self._build_catalog_area()
        self.refresh_products()

    def _build_toolbar(self) -> None:
        toolbar = tk.Frame(self, bg=MAIN_BG, padx=12, pady=10)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Обновить", command=self.refresh_products, bg=SECONDARY_BG).pack(side="left")

        if self.role_name in {"Менеджер", "Администратор"}:
            tk.Label(toolbar, text="Поиск", bg=MAIN_BG).pack(side="left", padx=(15, 4))
            search_entry = tk.Entry(toolbar, textvariable=self.search_var, width=24)
            search_entry.pack(side="left")
            self.search_var.trace_add("write", lambda *_args: self.refresh_products())

            tk.Label(toolbar, text="Скидка", bg=MAIN_BG).pack(side="left", padx=(15, 4))
            discount_box = ttk.Combobox(
                toolbar,
                textvariable=self.discount_var,
                values=["Все диапазоны", "0-12.99", "13-16.99", "17+"],
                width=12,
                state="readonly",
            )
            discount_box.pack(side="left")
            discount_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_products())

            tk.Label(toolbar, text="Сортировка", bg=MAIN_BG).pack(side="left", padx=(15, 4))
            sort_box = ttk.Combobox(
                toolbar,
                textvariable=self.sort_field_var,
                values=["name", "price", "stock"],
                width=10,
                state="readonly",
            )
            sort_box.pack(side="left")
            sort_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_products())

            direction_box = ttk.Combobox(
                toolbar,
                textvariable=self.sort_direction_var,
                values=["asc", "desc"],
                width=8,
                state="readonly",
            )
            direction_box.pack(side="left", padx=(4, 0))
            direction_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_products())

        if self.role_name in {"Менеджер", "Администратор"}:
            tk.Button(toolbar, text="Заказы", command=self.app.show_orders, bg=SECONDARY_BG).pack(side="right", padx=(8, 0))
        if self.role_name == "Администратор":
            tk.Button(toolbar, text="Добавить товар", command=self.open_add_product, bg=ACCENT_BG, fg="white").pack(side="right")

    def _build_catalog_area(self) -> None:
        wrapper = tk.Frame(self, bg=MAIN_BG)
        wrapper.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.canvas = tk.Canvas(wrapper, bg=MAIN_BG, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=MAIN_BG)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def refresh_products(self) -> None:
        for child in self.scrollable_frame.winfo_children():
            child.destroy()

        products = self.app.database.get_products(
            search_text=self.search_var.get(),
            discount_filter=self.discount_var.get(),
            sort_field=self.sort_field_var.get(),
            sort_descending=self.sort_direction_var.get() == "desc",
        )

        if not products:
            tk.Label(
                self.scrollable_frame,
                text="Товары не найдены.",
                bg=MAIN_BG,
                fg=TEXT_COLOR,
                pady=20,
            ).pack(fill="x")
            return

        for product in products:
            self._render_product_card(product)

    def _render_product_card(self, product: tk.Misc) -> None:
        background = MAIN_BG
        if product["stock"] == 0:
            background = OUT_OF_STOCK_BG
        elif product["discount"] > 25:
            background = HIGHLIGHT_BG

        card = tk.Frame(self.scrollable_frame, bg=background, bd=1, relief="solid", padx=10, pady=10)
        card.pack(fill="x", pady=(0, 10))

        image_label = tk.Label(card, bg=background)
        image_label.pack(side="left", padx=(0, 12))
        photo = self._load_product_photo(product["image_path"])
        image_label.configure(image=photo)
        image_label.image = photo

        body = tk.Frame(card, bg=background)
        body.pack(side="left", fill="both", expand=True)

        title = tk.Label(
            body,
            text=f"{product['name']} ({product['article']})",
            bg=background,
            fg=TEXT_COLOR,
            font=(FONT_FAMILY, 13, "bold"),
            anchor="w",
        )
        title.pack(fill="x")
        if self.role_name == "Администратор":
            title.bind("<Button-1>", lambda _event, product_id=product["id"]: self.open_edit_product(product_id))

        tk.Label(
            body,
            text=f"Категория: {product['category_name']} | Производитель: {product['manufacturer_name']} | Поставщик: {product['supplier_name']}",
            bg=background,
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(4, 2))
        tk.Label(
            body,
            text=f"Ед. изм.: {product['unit']} | На складе: {product['stock']} | Скидка: {product['discount']:.0f}%",
            bg=background,
            anchor="w",
        ).pack(fill="x", pady=(0, 2))
        tk.Label(
            body,
            text=product["description"] or "Описание отсутствует.",
            bg=background,
            justify="left",
            wraplength=730,
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        price_frame = tk.Frame(body, bg=background)
        price_frame.pack(fill="x")
        final_price = product["price"] * (1 - product["discount"] / 100)
        if product["discount"] > 0:
            tk.Label(
                price_frame,
                text=f"{product['price']:.2f} ₽",
                bg=background,
                fg="red",
                font=(FONT_FAMILY, 11, "overstrike"),
            ).pack(side="left")
            tk.Label(
                price_frame,
                text=f"  {final_price:.2f} ₽",
                bg=background,
                fg=TEXT_COLOR,
                font=(FONT_FAMILY, 11, "bold"),
            ).pack(side="left")
        else:
            tk.Label(
                price_frame,
                text=f"{product['price']:.2f} ₽",
                bg=background,
                fg=TEXT_COLOR,
                font=(FONT_FAMILY, 11, "bold"),
            ).pack(side="left")

        if self.role_name == "Администратор":
            button_bar = tk.Frame(card, bg=background)
            button_bar.pack(side="right", anchor="n")
            tk.Button(
                button_bar,
                text="Редактировать",
                command=lambda product_id=product["id"]: self.open_edit_product(product_id),
                bg=SECONDARY_BG,
            ).pack(fill="x", pady=(0, 6))
            tk.Button(
                button_bar,
                text="Удалить",
                command=lambda product_id=product["id"]: self.delete_product(product_id),
                bg=ACCENT_BG,
                fg="white",
            ).pack(fill="x")

    def _load_product_photo(self, stored_path: str | None) -> ImageTk.PhotoImage:
        cache_key = stored_path or "placeholder"
        if cache_key in self.photo_cache:
            return self.photo_cache[cache_key]
        path = self.app.database.resolve_image_path(stored_path)
        image = Image.open(path)
        image.thumbnail((160, 110))
        photo = ImageTk.PhotoImage(image)
        self.photo_cache[cache_key] = photo
        return photo

    def open_add_product(self) -> None:
        if self.app.product_form_window and self.app.product_form_window.winfo_exists():
            self.app.product_form_window.focus_force()
            return
        self.app.product_form_window = ProductFormWindow(self.app, self)

    def open_edit_product(self, product_id: int) -> None:
        if self.app.product_form_window and self.app.product_form_window.winfo_exists():
            self.app.product_form_window.focus_force()
            return
        self.app.product_form_window = ProductFormWindow(self.app, self, product_id=product_id)

    def delete_product(self, product_id: int) -> None:
        if not self.app.ask_yes_no("Удалить выбранный товар?"):
            return
        try:
            self.app.database.delete_product(product_id)
        except ValueError as error:
            self.app.show_error(str(error))
            return
        self.refresh_products()
        self.app.show_info("Товар удален.")


class OrdersFrame(BaseAuthenticatedFrame):
    def __init__(self, master: tk.Misc, app: BookStoreApp) -> None:
        super().__init__(master, app, "Заказы")
        self._build_toolbar()
        self._build_table()
        self.refresh_orders()

    def _build_toolbar(self) -> None:
        toolbar = tk.Frame(self, bg=MAIN_BG, padx=12, pady=10)
        toolbar.pack(fill="x")
        tk.Button(toolbar, text="Назад к товарам", command=self.app.show_catalog, bg=SECONDARY_BG).pack(side="left")
        tk.Button(toolbar, text="Обновить", command=self.refresh_orders, bg=SECONDARY_BG).pack(side="left", padx=(8, 0))
        if self.role_name == "Администратор":
            tk.Button(toolbar, text="Добавить заказ", command=self.open_add_order, bg=ACCENT_BG, fg="white").pack(side="right")
            tk.Button(toolbar, text="Удалить заказ", command=self.delete_selected_order, bg=SECONDARY_BG).pack(side="right", padx=(0, 8))
            tk.Button(toolbar, text="Редактировать", command=self.open_edit_order, bg=SECONDARY_BG).pack(side="right", padx=(0, 8))

    def _build_table(self) -> None:
        container = tk.Frame(self, bg=MAIN_BG, padx=12, pady=(0, 12))
        container.pack(fill="both", expand=True)
        columns = ("number", "customer", "dates", "pickup", "status", "amount")
        self.tree = ttk.Treeview(container, columns=columns, show="headings", height=18)
        headings = {
            "number": "Номер",
            "customer": "Клиент",
            "dates": "Даты",
            "pickup": "Пункт выдачи",
            "status": "Статус",
            "amount": "Сумма",
        }
        widths = {"number": 80, "customer": 240, "dates": 180, "pickup": 360, "status": 120, "amount": 120}
        for key in columns:
            self.tree.heading(key, text=headings[key])
            self.tree.column(key, width=widths[key], anchor="w")

        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _event: self.open_edit_order() if self.role_name == "Администратор" else None)

        self.details_var = tk.StringVar(value="Выберите заказ для просмотра состава.")
        tk.Label(
            container,
            textvariable=self.details_var,
            bg=SECONDARY_BG,
            justify="left",
            anchor="w",
            padx=10,
            pady=10,
            wraplength=1180,
        ).pack(fill="x", pady=(10, 0))
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.show_selected_order_details())

    def refresh_orders(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for order in self.app.database.get_orders():
            self.tree.insert(
                "",
                "end",
                iid=str(order["id"]),
                values=(
                    order["order_number"],
                    order["customer_name"],
                    f"{order['order_date']} -> {order['delivery_date']}",
                    order["pickup_address"],
                    order["status_name"],
                    f"{order['total_amount']:.2f} ₽",
                ),
            )
        self.details_var.set("Выберите заказ для просмотра состава.")

    def selected_order_id(self) -> int | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return int(selection[0])

    def show_selected_order_details(self) -> None:
        order_id = self.selected_order_id()
        if order_id is None:
            return
        items_text = self.app.database.get_order_items_text(order_id)
        self.details_var.set(f"Состав заказа: {items_text}")

    def open_add_order(self) -> None:
        if self.app.order_form_window and self.app.order_form_window.winfo_exists():
            self.app.order_form_window.focus_force()
            return
        self.app.order_form_window = OrderFormWindow(self.app, self)

    def open_edit_order(self) -> None:
        order_id = self.selected_order_id()
        if order_id is None:
            self.app.show_error("Сначала выберите заказ.")
            return
        if self.app.order_form_window and self.app.order_form_window.winfo_exists():
            self.app.order_form_window.focus_force()
            return
        self.app.order_form_window = OrderFormWindow(self.app, self, order_id=order_id)

    def delete_selected_order(self) -> None:
        order_id = self.selected_order_id()
        if order_id is None:
            self.app.show_error("Сначала выберите заказ.")
            return
        if not self.app.ask_yes_no("Удалить выбранный заказ?"):
            return
        self.app.database.delete_order(order_id)
        self.refresh_orders()
        self.app.show_info("Заказ удален.")


class ProductFormWindow(tk.Toplevel):
    def __init__(self, app: BookStoreApp, catalog_frame: CatalogFrame, product_id: int | None = None) -> None:
        super().__init__(app)
        self.app = app
        self.catalog_frame = catalog_frame
        self.product_id = product_id
        self.selected_image_path: Path | None = None
        self.preview_photo: ImageTk.PhotoImage | None = None
        self.title("Добавление товара" if product_id is None else "Редактирование товара")
        self.geometry("760x700")
        self.configure(bg=MAIN_BG)
        self.transient(app)
        self.grab_set()
        if ICON_PATH.exists():
            self.iconbitmap(default=str(ICON_PATH))
        self.protocol("WM_DELETE_WINDOW", self.close_window)

        self.references = self.app.database.get_reference_data()
        self._build_form()
        if product_id is not None:
            self._fill_form()

    def _build_form(self) -> None:
        form = tk.Frame(self, bg=MAIN_BG, padx=16, pady=16)
        form.pack(fill="both", expand=True)

        self.id_var = tk.StringVar(value=str(self.app.database.next_product_id()))
        self.article_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.category_var = tk.StringVar()
        self.manufacturer_var = tk.StringVar()
        self.supplier_var = tk.StringVar()
        self.price_var = tk.StringVar(value="0")
        self.unit_var = tk.StringVar(value="шт.")
        self.stock_var = tk.StringVar(value="0")
        self.discount_var = tk.StringVar(value="0")
        self.image_path_var = tk.StringVar(value="")

        if self.product_id is not None:
            tk.Label(form, text="ID", bg=MAIN_BG, anchor="w").pack(fill="x")
            tk.Entry(form, textvariable=self.id_var, state="readonly").pack(fill="x", pady=(0, 8))

        fields = [
            ("Артикул", self.article_var, True),
            ("Наименование", self.name_var, True),
            ("Цена", self.price_var, True),
            ("Единица измерения", self.unit_var, True),
            ("Количество на складе", self.stock_var, True),
            ("Скидка, %", self.discount_var, True),
        ]
        for label_text, variable, editable in fields:
            tk.Label(form, text=label_text, bg=MAIN_BG, anchor="w").pack(fill="x")
            state = "normal" if editable else "readonly"
            tk.Entry(form, textvariable=variable, state=state).pack(fill="x", pady=(0, 8))

        tk.Label(form, text="Категория", bg=MAIN_BG, anchor="w").pack(fill="x")
        ttk.Combobox(
            form,
            textvariable=self.category_var,
            values=[row["name"] for row in self.references["categories"]],
        ).pack(fill="x", pady=(0, 8))

        tk.Label(form, text="Производитель", bg=MAIN_BG, anchor="w").pack(fill="x")
        ttk.Combobox(
            form,
            textvariable=self.manufacturer_var,
            values=[row["name"] for row in self.references["manufacturers"]],
        ).pack(fill="x", pady=(0, 8))

        tk.Label(form, text="Поставщик", bg=MAIN_BG, anchor="w").pack(fill="x")
        ttk.Combobox(
            form,
            textvariable=self.supplier_var,
            values=[row["name"] for row in self.references["suppliers"]],
        ).pack(fill="x", pady=(0, 8))

        tk.Label(form, text="Описание", bg=MAIN_BG, anchor="w").pack(fill="x")
        self.description_text = tk.Text(form, height=6, wrap="word")
        self.description_text.pack(fill="x", pady=(0, 8))

        tk.Label(form, text="Изображение", bg=MAIN_BG, anchor="w").pack(fill="x")
        image_controls = tk.Frame(form, bg=MAIN_BG)
        image_controls.pack(fill="x", pady=(0, 8))
        tk.Entry(image_controls, textvariable=self.image_path_var, state="readonly").pack(side="left", fill="x", expand=True)
        tk.Button(image_controls, text="Выбрать", command=self.choose_image, bg=SECONDARY_BG).pack(side="left", padx=(8, 0))

        self.preview_label = tk.Label(form, bg=MAIN_BG)
        self.preview_label.pack(pady=(0, 12))

        button_panel = tk.Frame(form, bg=MAIN_BG)
        button_panel.pack(fill="x")
        tk.Button(button_panel, text="Сохранить", command=self.save_product, bg=ACCENT_BG, fg="white").pack(side="left")
        tk.Button(button_panel, text="Отмена", command=self.close_window, bg=SECONDARY_BG).pack(side="left", padx=(8, 0))

    def _fill_form(self) -> None:
        row = self.app.database.get_product_by_id(self.product_id)
        if row is None:
            self.app.show_error("Товар не найден.")
            self.close_window()
            return
        self.id_var.set(str(row["id"]))
        self.article_var.set(row["article"])
        self.name_var.set(row["name"])
        self.category_var.set(row["category_name"])
        self.manufacturer_var.set(row["manufacturer_name"])
        self.supplier_var.set(row["supplier_name"])
        self.price_var.set(str(row["price"]))
        self.unit_var.set(row["unit"])
        self.stock_var.set(str(row["stock"]))
        self.discount_var.set(str(row["discount"]))
        self.image_path_var.set(row["image_path"] or "")
        self.description_text.insert("1.0", row["description"])
        self._show_preview(self.app.database.resolve_image_path(row["image_path"]))

    def choose_image(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Выберите изображение",
            filetypes=[("Изображения", "*.png;*.jpg;*.jpeg;*.bmp")],
        )
        if not path:
            return
        self.selected_image_path = Path(path)
        self.image_path_var.set(path)
        self._show_preview(self.selected_image_path)

    def _show_preview(self, path: Path) -> None:
        image = Image.open(path)
        image.thumbnail((300, 200))
        self.preview_photo = ImageTk.PhotoImage(image)
        self.preview_label.configure(image=self.preview_photo)

    def save_product(self) -> None:
        try:
            payload = {
                "id": self.product_id,
                "article": self.article_var.get(),
                "name": self.name_var.get(),
                "category_name": self.category_var.get(),
                "manufacturer_name": self.manufacturer_var.get(),
                "supplier_name": self.supplier_var.get(),
                "price": float(self.price_var.get().replace(",", ".")),
                "unit": self.unit_var.get(),
                "stock": int(self.stock_var.get()),
                "discount": float(self.discount_var.get().replace(",", ".")),
                "description": self.description_text.get("1.0", "end").strip(),
                "image_path": self.image_path_var.get() or None,
            }
            self.app.database.save_product(payload, self.selected_image_path)
        except Exception as error:
            self.app.show_error(str(error))
            return
        self.catalog_frame.refresh_products()
        self.app.show_info("Товар сохранен.")
        self.close_window()

    def close_window(self) -> None:
        self.app.product_form_window = None
        self.destroy()


class OrderFormWindow(tk.Toplevel):
    def __init__(self, app: BookStoreApp, orders_frame: OrdersFrame, order_id: int | None = None) -> None:
        super().__init__(app)
        self.app = app
        self.orders_frame = orders_frame
        self.order_id = order_id
        self.references = self.app.database.get_reference_data()
        self.title("Добавление заказа" if order_id is None else "Редактирование заказа")
        self.geometry("720x620")
        self.configure(bg=MAIN_BG)
        self.transient(app)
        self.grab_set()
        if ICON_PATH.exists():
            self.iconbitmap(default=str(ICON_PATH))
        self.protocol("WM_DELETE_WINDOW", self.close_window)

        self._build_form()
        if order_id is not None:
            self._fill_form()

    def _build_form(self) -> None:
        form = tk.Frame(self, bg=MAIN_BG, padx=16, pady=16)
        form.pack(fill="both", expand=True)

        self.order_number_var = tk.StringVar(value=str(self.app.database.next_order_number()))
        self.order_date_var = tk.StringVar(value="")
        self.delivery_date_var = tk.StringVar(value="")
        self.pickup_code_var = tk.StringVar()
        self.pickup_point_var = tk.StringVar()
        self.customer_var = tk.StringVar()
        self.status_var = tk.StringVar()

        for label_text, variable in [
            ("Номер заказа", self.order_number_var),
            ("Дата заказа (YYYY-MM-DD)", self.order_date_var),
            ("Дата доставки (YYYY-MM-DD)", self.delivery_date_var),
            ("Код получения", self.pickup_code_var),
        ]:
            tk.Label(form, text=label_text, bg=MAIN_BG, anchor="w").pack(fill="x")
            tk.Entry(form, textvariable=variable).pack(fill="x", pady=(0, 8))

        tk.Label(form, text="Пункт выдачи", bg=MAIN_BG, anchor="w").pack(fill="x")
        ttk.Combobox(
            form,
            textvariable=self.pickup_point_var,
            values=[f"{row['id']} | {row['address']}" for row in self.references["pickup_points"]],
            state="readonly",
        ).pack(fill="x", pady=(0, 8))

        tk.Label(form, text="Клиент", bg=MAIN_BG, anchor="w").pack(fill="x")
        ttk.Combobox(
            form,
            textvariable=self.customer_var,
            values=[f"{row['id']} | {row['full_name']}" for row in self.references["clients"]],
            state="readonly",
        ).pack(fill="x", pady=(0, 8))

        tk.Label(form, text="Статус", bg=MAIN_BG, anchor="w").pack(fill="x")
        ttk.Combobox(
            form,
            textvariable=self.status_var,
            values=[f"{row['id']} | {row['name']}" for row in self.references["statuses"]],
            state="readonly",
        ).pack(fill="x", pady=(0, 8))

        tk.Label(
            form,
            text="Состав заказа: Артикул, количество, Артикул, количество",
            bg=MAIN_BG,
            anchor="w",
        ).pack(fill="x")
        self.items_text = tk.Text(form, height=10, wrap="word")
        self.items_text.pack(fill="both", expand=True, pady=(0, 12))

        button_panel = tk.Frame(form, bg=MAIN_BG)
        button_panel.pack(fill="x")
        tk.Button(button_panel, text="Сохранить", command=self.save_order, bg=ACCENT_BG, fg="white").pack(side="left")
        tk.Button(button_panel, text="Отмена", command=self.close_window, bg=SECONDARY_BG).pack(side="left", padx=(8, 0))

    def _fill_form(self) -> None:
        row = self.app.database.get_order_by_id(self.order_id)
        if row is None:
            self.app.show_error("Заказ не найден.")
            self.close_window()
            return
        self.order_number_var.set(str(row["order_number"]))
        self.order_date_var.set(row["order_date"])
        self.delivery_date_var.set(row["delivery_date"])
        self.pickup_code_var.set(row["pickup_code"])
        self.pickup_point_var.set(f"{row['pickup_point_id']} | {row['pickup_address']}")
        self.customer_var.set(f"{row['customer_id']} | {row['customer_name']}")
        self.status_var.set(f"{row['status_id']} | {row['status_name']}")
        self.items_text.insert("1.0", self.app.database.get_order_items_text(self.order_id))

    def save_order(self) -> None:
        try:
            if not self.pickup_point_var.get().strip():
                raise ValueError("Выберите пункт выдачи.")
            if not self.customer_var.get().strip():
                raise ValueError("Выберите клиента.")
            if not self.status_var.get().strip():
                raise ValueError("Выберите статус заказа.")
            payload = {
                "id": self.order_id,
                "order_number": int(self.order_number_var.get()),
                "order_date": self.order_date_var.get().strip(),
                "delivery_date": self.delivery_date_var.get().strip(),
                "pickup_code": self.pickup_code_var.get().strip(),
                "pickup_point_id": int(self.pickup_point_var.split("|", 1)[0].strip()),
                "customer_id": int(self.customer_var.split("|", 1)[0].strip()),
                "status_id": int(self.status_var.split("|", 1)[0].strip()),
                "items_text": self.items_text.get("1.0", "end").strip(),
            }
            self.app.database.save_order(payload)
        except Exception as error:
            self.app.show_error(str(error))
            return
        self.orders_frame.refresh_orders()
        self.app.show_info("Заказ сохранен.")
        self.close_window()

    def close_window(self) -> None:
        self.app.order_form_window = None
        self.destroy()
