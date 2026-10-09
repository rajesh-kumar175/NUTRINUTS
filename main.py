"""Local NUTRINUTS desktop shop.

Run with ``python main.py``. Product, cart, and order data are stored locally in
``nutrinuts.db``; no cloud credentials or third-party packages are required.
"""

from __future__ import annotations

import os
import sqlite3
import tkinter as tk
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Iterator


APP_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("NUTRINUTS_DB_PATH", str(APP_DIR / "nutrinuts.db")))
PRIMARY = "#54CFBB"
SECONDARY = "#A67B5B"
ACCENT = "#A3D636"
BACKGROUND = "#FFFAF0"
INK = "#6D9B22"
MUTED = "#00FA04"


@dataclass(frozen=True)
class Product:
    id: int
    name: str
    category: str
    price: int
    mrp: int
    weight: str
    rating: float
    emoji: str
    description: str


@dataclass(frozen=True)
class CartLine:
    product: Product
    quantity: int


PRODUCTS = (
    ("Premium Kashmiri Almonds", "Almonds", 499, 699, "250 g", 4.8, "🌰",
     "Crunchy, naturally sweet almonds sourced from Kashmir."),
    ("California Almonds", "Almonds", 399, 549, "250 g", 4.7, "🥜",
     "Carefully selected whole almonds, packed fresh."),
    ("Whole Cashews", "Cashews", 449, 599, "250 g", 4.8, "🥜",
     "Creamy whole cashews with a rich, buttery taste."),
    ("Roasted Salted Cashews", "Cashews", 499, 649, "250 g", 4.6, "🧂",
     "Gently roasted cashews with a light touch of salt."),
    ("Iranian Pistachios", "Pistachios", 599, 799, "200 g", 4.9, "💚",
     "Distinctive pistachios with a deep flavour and crisp bite."),
    ("Golden Afghan Raisins", "Raisins", 249, 349, "250 g", 4.5, "🍇",
     "Naturally sun-dried golden raisins, tender and sweet."),
    ("Medjool Dates", "Dates", 349, 449, "300 g", 4.8, "🌴",
     "Soft, caramel-like dates selected for their plump texture."),
    ("Dried Turkish Figs", "Figs", 399, 549, "250 g", 4.7, "🟤",
     "Naturally sweet dried figs with a pleasantly chewy centre."),
    ("Premium Walnut Kernels", "Walnuts", 549, 749, "200 g", 4.6, "🤎",
     "Fresh, crisp walnut halves packed to preserve their flavour."),
    ("NUTRINUTS Trail Mix", "Mixes", 299, 399, "250 g", 4.8, "✨",
     "A balanced snack mix of nuts, raisins, and dried fruit."),
)


class ShopStore:
    """Small local SQLite store for the catalogue, cart, and order history."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL,
                    price INTEGER NOT NULL CHECK (price >= 0),
                    mrp INTEGER NOT NULL CHECK (mrp >= price),
                    weight TEXT NOT NULL,
                    rating REAL NOT NULL,
                    emoji TEXT NOT NULL,
                    description TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cart (
                    product_id INTEGER PRIMARY KEY REFERENCES products(id),
                    quantity INTEGER NOT NULL CHECK (quantity > 0)
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    address TEXT NOT NULL,
                    total INTEGER NOT NULL CHECK (total >= 0),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS order_items (
                    order_id INTEGER NOT NULL REFERENCES orders(id),
                    product_name TEXT NOT NULL,
                    unit_price INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    PRIMARY KEY (order_id, product_name)
                );
                """
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO products
                    (name, category, price, mrp, weight, rating, emoji, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                PRODUCTS,
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _product(row: sqlite3.Row) -> Product:
        return Product(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            price=row["price"],
            mrp=row["mrp"],
            weight=row["weight"],
            rating=row["rating"],
            emoji=row["emoji"],
            description=row["description"],
        )

    def categories(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT category FROM products ORDER BY category"
            ).fetchall()
        return [row["category"] for row in rows]

    def products(self, category: str = "All", search: str = "") -> list[Product]:
        clauses: list[str] = []
        values: list[str] = []
        if category != "All":
            clauses.append("category = ?")
            values.append(category)
        if search.strip():
            clauses.append("(name LIKE ? OR category LIKE ? OR description LIKE ?)")
            term = f"%{search.strip()}%"
            values.extend((term, term, term))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM products {where} ORDER BY category, name", values
            ).fetchall()
        return [self._product(row) for row in rows]

    def cart(self) -> list[CartLine]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT p.*, c.quantity
                FROM cart c JOIN products p ON p.id = c.product_id
                ORDER BY p.name
                """
            ).fetchall()
        return [CartLine(self._product(row), row["quantity"]) for row in rows]

    def set_quantity(self, product_id: int, quantity: int) -> None:
        with self._connect() as connection:
            if quantity <= 0:
                connection.execute("DELETE FROM cart WHERE product_id = ?", (product_id,))
            else:
                connection.execute(
                    """
                    INSERT INTO cart (product_id, quantity) VALUES (?, ?)
                    ON CONFLICT(product_id) DO UPDATE SET quantity = excluded.quantity
                    """,
                    (product_id, quantity),
                )

    def add_to_cart(self, product_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cart (product_id, quantity) VALUES (?, 1)
                ON CONFLICT(product_id) DO UPDATE SET quantity = quantity + 1
                """,
                (product_id,),
            )

    def place_order(self, customer_name: str, phone: str, address: str) -> int:
        name, phone, address = customer_name.strip(), phone.strip(), address.strip()
        if not name or not address:
            raise ValueError("Enter your name and delivery address.")
        if not phone.isdigit() or not 10 <= len(phone) <= 15:
            raise ValueError("Enter a valid phone number (10 to 15 digits).")

        with self._connect() as connection:
            lines = connection.execute(
                """
                SELECT p.name, p.price, c.quantity
                FROM cart c JOIN products p ON p.id = c.product_id
                ORDER BY p.name
                """
            ).fetchall()
            if not lines:
                raise ValueError("Your cart is empty.")
            total = sum(row["price"] * row["quantity"] for row in lines)
            cursor = connection.execute(
                """
                INSERT INTO orders (customer_name, phone, address, total, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, phone, address, total, datetime.now().astimezone().isoformat(timespec="minutes")),
            )
            order_id = int(cursor.lastrowid)
            connection.executemany(
                """
                INSERT INTO order_items (order_id, product_name, unit_price, quantity)
                VALUES (?, ?, ?, ?)
                """,
                [(order_id, row["name"], row["price"], row["quantity"]) for row in lines],
            )
            connection.execute("DELETE FROM cart")
        return order_id

    def orders(self) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT o.*,
                    (SELECT COUNT(*) FROM order_items i WHERE i.order_id = o.id) AS item_count
                FROM orders o ORDER BY o.id DESC
                """
            ).fetchall()

    def order_items(self, order_id: int) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT product_name, unit_price, quantity FROM order_items
                WHERE order_id = ? ORDER BY product_name
                """,
                (order_id,),
            ).fetchall()


def money(amount: int) -> str:
    return f"₹{amount:,}"


class NutrinutsApp:
    def __init__(self, root: tk.Tk, store: ShopStore) -> None:
        self.root = root
        self.store = store
        self.root.title("NUTRINUTS | Naturally better snacking")
        self.root.geometry("1120x760")
        self.root.minsize(880, 620)
        self.root.configure(bg=BACKGROUND)
        self.category = tk.StringVar(value="All")
        self.search = tk.StringVar()
        self._configure_styles()
        self._build_layout()
        self.refresh_products()
        self.refresh_cart()

    def _configure_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("App.TFrame", background=BACKGROUND)
        style.configure("Panel.TFrame", background="white")
        style.configure("Title.TLabel", background=BACKGROUND, foreground=PRIMARY,
                        font=("Segoe UI", 25, "bold"))
        style.configure("Subtitle.TLabel", background=BACKGROUND, foreground=MUTED,
                        font=("Segoe UI", 10))
        style.configure("Section.TLabel", background=BACKGROUND, foreground=INK,
                        font=("Segoe UI", 15, "bold"))
        style.configure("Card.TFrame", background="white")
        style.configure("CardName.TLabel", background="white", foreground=INK,
                        font=("Segoe UI", 11, "bold"))
        style.configure("CardInfo.TLabel", background="white", foreground=MUTED,
                        font=("Segoe UI", 9))
        style.configure("Price.TLabel", background="white", foreground=PRIMARY,
                        font=("Segoe UI", 12, "bold"))
        style.configure("CartHeading.TLabel", background="white", foreground=PRIMARY,
                        font=("Segoe UI", 15, "bold"))
        style.configure("Total.TLabel", background="white", foreground=PRIMARY,
                        font=("Segoe UI", 15, "bold"))
        style.configure("Accent.TButton", background=PRIMARY, foreground="white",
                        font=("Segoe UI", 10, "bold"), padding=(12, 8), borderwidth=0)
        style.map("Accent.TButton", background=[("active", SECONDARY)])
        style.configure("Soft.TButton", background="#F3EBDD", foreground=PRIMARY,
                        font=("Segoe UI", 9, "bold"), padding=(7, 5), borderwidth=0)
        style.map("Soft.TButton", background=[("active", "#EBD9C1")])
        style.configure("Treeview", rowheight=29, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_layout(self) -> None:
        header = ttk.Frame(self.root, style="App.TFrame", padding=(24, 18, 24, 14))
        header.pack(fill="x")
        brand = ttk.Frame(header, style="App.TFrame")
        brand.pack(side="left")
        ttk.Label(brand, text="NUTRINUTS", style="Title.TLabel").pack(anchor="w")
        ttk.Label(brand, text="Premium dry fruits · naturally better snacking",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(2, 0))
        ttk.Button(header, text="Order history", style="Soft.TButton",
                   command=self.show_orders).pack(side="right", anchor="center")

        toolbar = ttk.Frame(self.root, style="App.TFrame", padding=(24, 0, 24, 15))
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Find something delicious", style="Section.TLabel").pack(
            side="left", padx=(0, 14)
        )
        self.search_entry = ttk.Entry(toolbar, textvariable=self.search, width=30)
        self.search_entry.pack(side="left", ipady=5)
        self.search_entry.bind("<KeyRelease>", lambda _event: self.refresh_products())
        ttk.Label(toolbar, text="Category", style="Subtitle.TLabel").pack(
            side="left", padx=(18, 7)
        )
        self.category_box = ttk.Combobox(
            toolbar, textvariable=self.category,
            values=["All", *self.store.categories()], state="readonly", width=15
        )
        self.category_box.pack(side="left", ipady=4)
        self.category_box.bind("<<ComboboxSelected>>",
                               lambda _event: self.refresh_products())

        main = ttk.Frame(self.root, style="App.TFrame", padding=(24, 0, 24, 20))
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=3, uniform="main")
        main.columnconfigure(1, weight=2, uniform="main")
        main.rowconfigure(0, weight=1)
        catalog_wrap = ttk.Frame(main, style="App.TFrame")
        catalog_wrap.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        catalog_wrap.columnconfigure(0, weight=1)
        catalog_wrap.rowconfigure(0, weight=1)
        self.catalog_canvas = tk.Canvas(
            catalog_wrap, bg=BACKGROUND, highlightthickness=0, borderwidth=0
        )
        catalog_scrollbar = ttk.Scrollbar(
            catalog_wrap, orient="vertical", command=self.catalog_canvas.yview
        )
        self.catalog_canvas.configure(yscrollcommand=catalog_scrollbar.set)
        self.catalog_canvas.grid(row=0, column=0, sticky="nsew")
        catalog_scrollbar.grid(row=0, column=1, sticky="ns")
        self.catalog = ttk.Frame(self.catalog_canvas, style="App.TFrame")
        self.catalog_window = self.catalog_canvas.create_window(
            (0, 0), window=self.catalog, anchor="nw"
        )
        self.catalog.bind("<Configure>", self._resize_catalog_scrollregion)
        self.catalog_canvas.bind("<Configure>", self._resize_catalog_width)
        self.catalog.columnconfigure((0, 1), weight=1, uniform="cards")
        self.cart_panel = ttk.Frame(main, style="Panel.TFrame", padding=18)
        self.cart_panel.grid(row=0, column=1, sticky="nsew")
        self.cart_panel.columnconfigure(0, weight=1)

        ttk.Label(self.cart_panel, text="Your basket", style="CartHeading.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.cart_count_label = ttk.Label(
            self.cart_panel, text="", style="CardInfo.TLabel"
        )
        self.cart_count_label.grid(row=1, column=0, sticky="w", pady=(3, 12))
        tree_frame = ttk.Frame(self.cart_panel, style="Panel.TFrame")
        tree_frame.grid(row=2, column=0, sticky="nsew")
        self.cart_panel.rowconfigure(2, weight=1)
        self.cart_tree = ttk.Treeview(
            tree_frame, columns=("quantity", "price"), show="tree headings",
            selectmode="browse", height=12
        )
        self.cart_tree.heading("#0", text="Item")
        self.cart_tree.heading("quantity", text="Qty")
        self.cart_tree.heading("price", text="Price")
        self.cart_tree.column("#0", width=160, minwidth=110)
        self.cart_tree.column("quantity", width=42, anchor="center")
        self.cart_tree.column("price", width=76, anchor="e")
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical",
                                  command=self.cart_tree.yview)
        self.cart_tree.configure(yscrollcommand=scrollbar.set)
        self.cart_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        controls = ttk.Frame(self.cart_panel, style="Panel.TFrame")
        controls.grid(row=3, column=0, sticky="ew", pady=(10, 12))
        ttk.Button(controls, text="− Remove one", style="Soft.TButton",
                   command=lambda: self.adjust_selected(-1)).pack(side="left")
        ttk.Button(controls, text="+ Add one", style="Soft.TButton",
                   command=lambda: self.adjust_selected(1)).pack(side="left", padx=7)
        ttk.Button(controls, text="Clear", style="Soft.TButton",
                   command=self.clear_cart).pack(side="right")
        ttk.Separator(self.cart_panel).grid(row=4, column=0, sticky="ew", pady=5)
        self.total_label = ttk.Label(self.cart_panel, text="Total  ₹0",
                                     style="Total.TLabel")
        self.total_label.grid(row=5, column=0, sticky="e", pady=(8, 12))
        ttk.Button(self.cart_panel, text="Checkout · Cash on delivery",
                   style="Accent.TButton", command=self.checkout).grid(
                       row=6, column=0, sticky="ew"
                   )
        ttk.Label(
            self.cart_panel, text="Local demo · orders are saved on this computer",
            style="CardInfo.TLabel", wraplength=300
        ).grid(row=7, column=0, sticky="w", pady=(10, 0))

        footer = ttk.Label(
            self.root,
            text="Freshly selected · Secure local checkout · No account required",
            background=BACKGROUND, foreground=MUTED, font=("Segoe UI", 9),
            padding=(24, 0, 24, 12)
        )
        footer.pack(fill="x")

    def _resize_catalog_scrollregion(self, _event: tk.Event) -> None:
        self.catalog_canvas.configure(scrollregion=self.catalog_canvas.bbox("all"))

    def _resize_catalog_width(self, event: tk.Event) -> None:
        self.catalog_canvas.itemconfigure(self.catalog_window, width=event.width)

    def refresh_products(self) -> None:
        for child in self.catalog.winfo_children():
            child.destroy()
        products = self.store.products(self.category.get(), self.search.get())
        if not products:
            ttk.Label(self.catalog, text="No products found. Try another search.",
                      style="Subtitle.TLabel").grid(row=0, column=0, sticky="w", pady=20)
            return
        for index, product in enumerate(products):
            card = ttk.Frame(self.catalog, style="Card.TFrame", padding=13)
            card.grid(row=index // 2, column=index % 2, sticky="nsew",
                      padx=(0, 10 if index % 2 == 0 else 0), pady=(0, 12))
            card.columnconfigure(0, weight=1)
            ttk.Label(card, text=product.emoji, background="white",
                      font=("Segoe UI Emoji", 25)).grid(row=0, column=0, sticky="w")
            ttk.Label(card, text=product.name, style="CardName.TLabel",
                      wraplength=220).grid(row=1, column=0, sticky="w", pady=(5, 2))
            ttk.Label(card, text=f"{product.category}  ·  {product.weight}  ·  ★ {product.rating}",
                      style="CardInfo.TLabel").grid(row=2, column=0, sticky="w")
            ttk.Label(card, text=product.description, style="CardInfo.TLabel",
                      wraplength=230).grid(row=3, column=0, sticky="w", pady=(5, 7))
            bottom = ttk.Frame(card, style="Card.TFrame")
            bottom.grid(row=4, column=0, sticky="ew")
            bottom.columnconfigure(0, weight=1)
            ttk.Label(bottom, text=money(product.price), style="Price.TLabel").grid(
                row=0, column=0, sticky="w"
            )
            ttk.Label(bottom, text=money(product.mrp), background="white",
                      foreground=MUTED, font=("Segoe UI", 8, "overstrike")).grid(
                          row=1, column=0, sticky="w"
                      )
            ttk.Button(bottom, text="Add to basket", style="Soft.TButton",
                       command=lambda item=product: self.add_product(item)).grid(
                           row=0, column=1, rowspan=2, sticky="e"
                       )

    def refresh_cart(self) -> None:
        self.cart_tree.delete(*self.cart_tree.get_children())
        lines = self.store.cart()
        for line in lines:
            self.cart_tree.insert(
                "", "end", iid=str(line.product.id), text=line.product.name,
                values=(line.quantity, money(line.product.price * line.quantity))
            )
        count = sum(line.quantity for line in lines)
        total = sum(line.product.price * line.quantity for line in lines)
        self.cart_count_label.configure(
            text=f"{count} item{'s' if count != 1 else ''}"
        )
        self.total_label.configure(text=f"Total  {money(total)}")

    def add_product(self, product: Product) -> None:
        self.store.add_to_cart(product.id)
        self.refresh_cart()

    def adjust_selected(self, amount: int) -> None:
        selected = self.cart_tree.selection()
        if not selected:
            messagebox.showinfo("Your basket", "Select an item in your basket first.")
            return
        product_id = int(selected[0])
        current = next(
            line.quantity for line in self.store.cart()
            if line.product.id == product_id
        )
        self.store.set_quantity(product_id, current + amount)
        self.refresh_cart()

    def clear_cart(self) -> None:
        if not self.store.cart():
            return
        if messagebox.askyesno("Clear basket", "Remove all items from your basket?"):
            for line in self.store.cart():
                self.store.set_quantity(line.product.id, 0)
            self.refresh_cart()

    def checkout(self) -> None:
        if not self.store.cart():
            messagebox.showinfo("Checkout", "Add something to your basket first.")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Delivery details")
        dialog.configure(bg=BACKGROUND)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, style="App.TFrame", padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Where should we deliver?", style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 14)
        )
        fields: dict[str, ttk.Entry] = {}
        for row, (label, key, width) in enumerate((
            ("Full name", "name", 34),
            ("Phone number", "phone", 20),
        ), start=1):
            ttk.Label(frame, text=label, style="Subtitle.TLabel").grid(
                row=row, column=0, sticky="w", pady=5
            )
            fields[key] = ttk.Entry(frame, width=width)
            fields[key].grid(row=row, column=1, sticky="ew", pady=5)
        ttk.Label(frame, text="Delivery address", style="Subtitle.TLabel").grid(
            row=3, column=0, sticky="nw", pady=5
        )
        address = tk.Text(frame, width=34, height=4, font=("Segoe UI", 10),
                          wrap="word", relief="solid", borderwidth=1)
        address.grid(row=3, column=1, sticky="ew", pady=5)
        fields["name"].focus_set()

        def submit() -> None:
            try:
                order_id = self.store.place_order(
                    fields["name"].get(), fields["phone"].get(),
                    address.get("1.0", "end").strip()
                )
            except ValueError as error:
                messagebox.showerror("Check delivery details", str(error), parent=dialog)
                return
            except sqlite3.Error as error:
                messagebox.showerror("Could not place order", str(error), parent=dialog)
                return
            dialog.destroy()
            self.refresh_cart()
            messagebox.showinfo(
                "Order placed",
                f"Thank you! Order #{order_id} is confirmed.\n"
                "Payment method: Cash on delivery.",
                parent=self.root,
            )

        ttk.Button(frame, text="Place order · Cash on delivery",
                   style="Accent.TButton", command=submit).grid(
                       row=4, column=0, columnspan=2, sticky="ew", pady=(13, 0)
                   )

    def show_orders(self) -> None:
        orders = self.store.orders()
        dialog = tk.Toplevel(self.root)
        dialog.title("Order history")
        dialog.geometry("650x410")
        dialog.configure(bg=BACKGROUND)
        dialog.transient(self.root)
        frame = ttk.Frame(dialog, style="App.TFrame", padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Your orders", style="Section.TLabel").pack(
            anchor="w", pady=(0, 12)
        )
        if not orders:
            ttk.Label(frame, text="No orders yet. Your first order is a few clicks away.",
                      style="Subtitle.TLabel").pack(anchor="w")
            return
        tree = ttk.Treeview(
            frame, columns=("date", "items", "total", "customer"),
            show="headings", selectmode="browse"
        )
        for key, title, width in (
            ("date", "Placed", 145), ("items", "Items", 65),
            ("total", "Total", 95), ("customer", "Name", 180)
        ):
            tree.heading(key, text=title)
            tree.column(key, width=width)
        tree.pack(fill="both", expand=True)
        for order in orders:
            created = datetime.fromisoformat(order["created_at"]).strftime("%d %b %Y, %H:%M")
            tree.insert(
                "", "end", iid=str(order["id"]),
                values=(created, order["item_count"], money(order["total"]),
                        order["customer_name"])
            )
        details = tk.Text(frame, height=5, font=("Segoe UI", 9), wrap="word",
                          state="disabled")
        details.pack(fill="x", pady=(10, 0))

        def show_selected(_event: object = None) -> None:
            selected = tree.selection()
            if not selected:
                return
            items = self.store.order_items(int(selected[0]))
            text = "   ·   ".join(
                f"{row['product_name']} × {row['quantity']}"
                for row in items
            )
            details.configure(state="normal")
            details.delete("1.0", "end")
            details.insert("1.0", text)
            details.configure(state="disabled")

        tree.bind("<<TreeviewSelect>>", show_selected)
        tree.selection_set(str(orders[0]["id"]))
        show_selected()


def main() -> None:
    store = ShopStore()
    root = tk.Tk()
    NutrinutsApp(root, store)
    root.mainloop()


if __name__ == "__main__":
    main()
