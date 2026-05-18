# Azzam Autocare - Flask + Bootstrap + SQLite
# ------------------------------------------------------------
# Converted from temporary in-memory list to SQLite database.
# Data will now be saved in garage.db even after you close the app.
#
# How to use locally:
# 1. Save this file as app.py
# 2. Run: pip install flask
# 3. Run: python app.py
# 4. Open: http://127.0.0.1:5000
#
# How to run tests:
# python app.py --test

from __future__ import annotations

import os
import sqlite3
import sys
from typing import Any

import os
print(os.getcwd())
print("THIS IS SQLITE VERSION")

from flask import Flask, g, redirect, render_template_string, request, url_for

app = Flask(__name__)
DATABASE = "garage.db"


# -----------------------------
# Database helpers
# -----------------------------
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error: Exception | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS quotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quotation_no TEXT UNIQUE NOT NULL,
            invoice_no TEXT,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            plate_no TEXT NOT NULL,
            car_model TEXT NOT NULL,
            mileage TEXT,
            notes TEXT,
            subtotal REAL NOT NULL DEFAULT 0,
            tax REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS quotation_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quotation_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            qty INTEGER NOT NULL,
            price REAL NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY (quotation_id) REFERENCES quotations(id) ON DELETE CASCADE
        );
        """
    )
    db.commit()


def calculate_totals(items: list[dict[str, Any]], tax_rate: float = 0.06) -> dict[str, float]:
    """Calculate subtotal, service tax and total for quotation/invoice."""
    subtotal = sum(float(item["qty"]) * float(item["price"]) for item in items)
    tax = subtotal * tax_rate
    total = subtotal + tax
    return {
        "subtotal": round(subtotal, 2),
        "tax": round(tax, 2),
        "total": round(total, 2),
    }


def quotation_number(quotation_id: int) -> str:
    return f"QT-2026-{quotation_id:04d}"


def invoice_number(quotation_id: int) -> str:
    return f"INV-2026-{quotation_id:04d}"


def get_quotation(quotation_id: int) -> sqlite3.Row | None:
    db = get_db()
    return db.execute("SELECT * FROM quotations WHERE id = ?", (quotation_id,)).fetchone()


def get_items(quotation_id: int) -> list[sqlite3.Row]:
    db = get_db()
    return db.execute(
        "SELECT * FROM quotation_items WHERE quotation_id = ? ORDER BY id",
        (quotation_id,),
    ).fetchall()


BASE_HTML = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background: #f4f6f9;
        }
        .app-navbar {
            background: #1f2937;
        }
        .brand-badge {
            background: #f59e0b;
            color: #111827;
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 700;
        }
        .card {
            border: 0;
            border-radius: 18px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
        }
        .btn-rounded {
            border-radius: 12px;
        }
        .status-pill {
            border-radius: 999px;
            padding: 5px 12px;
            font-size: 13px;
            font-weight: 600;
        }
        .status-draft {
            background: #fef3c7;
            color: #92400e;
        }
        .status-approved {
            background: #dcfce7;
            color: #166534;
        }
        .print-area {
            background: white;
            padding: 28px;
            border-radius: 18px;
        }
        @media print {
            .no-print {
                display: none !important;
            }
            body {
                background: white;
            }
            .print-area {
                box-shadow: none;
                border-radius: 0;
                padding: 0;
            }
        }
    </style>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark app-navbar no-print">
    <div class="container">
        <a class="navbar-brand fw-bold" href="/">Azzam Autocare</a>
        <span class="brand-badge">Quotation & Invoice</span>
    </div>
</nav>

<main class="container py-4">
    {{ content|safe }}
</main>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
function addItemRow() {
    const container = document.getElementById('repair-items');
    const row = document.createElement('div');
    row.className = 'row g-2 align-items-end repair-row mb-2';
    row.innerHTML = `
        <div class="col-12 col-md-6">
            <label class="form-label">Repair / Parts</label>
            <input type="text" name="item_name[]" class="form-control" placeholder="e.g. Brake pad replacement" required>
        </div>
        <div class="col-6 col-md-2">
            <label class="form-label">Qty</label>
            <input type="number" name="qty[]" class="form-control qty" value="1" min="1" oninput="calculateTotal()" required>
        </div>
        <div class="col-6 col-md-3">
            <label class="form-label">Price (RM)</label>
            <input type="number" name="price[]" class="form-control price" value="0" min="0" step="0.01" oninput="calculateTotal()" required>
        </div>
        <div class="col-12 col-md-1 d-grid">
            <button type="button" class="btn btn-outline-danger btn-rounded" onclick="this.closest('.repair-row').remove(); calculateTotal();">X</button>
        </div>
    `;
    container.appendChild(row);
}

function calculateTotal() {
    let subtotal = 0;
    document.querySelectorAll('.repair-row').forEach(row => {
        const qty = parseFloat(row.querySelector('.qty').value) || 0;
        const price = parseFloat(row.querySelector('.price').value) || 0;
        subtotal += qty * price;
    });
    const tax = subtotal * 0.06;
    const total = subtotal + tax;
    const subtotalEl = document.getElementById('subtotal');
    const taxEl = document.getElementById('tax');
    const totalEl = document.getElementById('total');
    if (subtotalEl) subtotalEl.textContent = subtotal.toFixed(2);
    if (taxEl) taxEl.textContent = tax.toFixed(2);
    if (totalEl) totalEl.textContent = total.toFixed(2);
}
</script>
</body>
</html>
"""


def page(title: str, content: str) -> str:
    return render_template_string(BASE_HTML, title=title, content=content)


@app.route("/")
def dashboard():
    db = get_db()
    quotations = db.execute("SELECT * FROM quotations ORDER BY id DESC").fetchall()

    rows = ""
    if not quotations:
        rows = '<tr><td colspan="6" class="text-muted text-center py-4">No quotation yet. Create your first quotation.</td></tr>'
    else:
        for q in quotations:
            badge = "status-approved" if q["status"] == "Approved" else "status-draft"
            rows += f"""
            <tr>
                <td class="fw-semibold">{q['quotation_no']}</td>
                <td>{q['customer_name']}</td>
                <td>{q['plate_no']}</td>
                <td><span class="status-pill {badge}">{q['status']}</span></td>
                <td>RM {q['total']:.2f}</td>
                <td><a class="btn btn-sm btn-outline-dark btn-rounded" href="/quotation/{q['id']}">View</a></td>
            </tr>
            """

    total_q = db.execute("SELECT COUNT(*) AS count FROM quotations").fetchone()["count"]
    draft_q = db.execute("SELECT COUNT(*) AS count FROM quotations WHERE status = 'Draft'").fetchone()["count"]
    approved_q = db.execute("SELECT COUNT(*) AS count FROM quotations WHERE status = 'Approved'").fetchone()["count"]
    invoice_q = db.execute("SELECT COUNT(*) AS count FROM quotations WHERE invoice_no IS NOT NULL").fetchone()["count"]

    content = """
    <div class="d-flex flex-column flex-md-row justify-content-between gap-3 mb-4">
        <div>
            <h1 class="fw-bold mb-1">Azzam Autocare Dashboard</h1>
            <p class="text-muted mb-0">Manage repair quotation and invoice workflow.</p>
        </div>
        <div class="d-grid d-md-block">
            <a href="/quotation/new" class="btn btn-warning btn-rounded fw-semibold">+ New Quotation</a>
        </div>
    </div>

    <div class="row g-3 mb-4">
        <div class="col-6 col-md-3"><div class="card p-3"><div class="text-muted small">Total Quotations</div><div class="fs-3 fw-bold">{{ total_q }}</div></div></div>
        <div class="col-6 col-md-3"><div class="card p-3"><div class="text-muted small">Draft</div><div class="fs-3 fw-bold">{{ draft_q }}</div></div></div>
        <div class="col-6 col-md-3"><div class="card p-3"><div class="text-muted small">Approved</div><div class="fs-3 fw-bold">{{ approved_q }}</div></div></div>
        <div class="col-6 col-md-3"><div class="card p-3"><div class="text-muted small">Invoices</div><div class="fs-3 fw-bold">{{ invoice_q }}</div></div></div>
    </div>

    <div class="card p-3 p-md-4">
        <h5 class="fw-bold mb-3">Recent Quotations</h5>
        <div class="table-responsive">
            <table class="table align-middle">
                <thead>
                    <tr>
                        <th>Quotation No.</th>
                        <th>Customer</th>
                        <th>Vehicle</th>
                        <th>Status</th>
                        <th>Total</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>{{ rows|safe }}</tbody>
            </table>
        </div>
    </div>
    """
    content = render_template_string(
        content,
        total_q=total_q,
        draft_q=draft_q,
        approved_q=approved_q,
        invoice_q=invoice_q,
        rows=rows,
    )
    return page("Azzam Autocare Dashboard", content)


@app.route("/quotation/new", methods=["GET", "POST"])
def new_quotation():
    if request.method == "POST":
        db = get_db()
        item_names = request.form.getlist("item_name[]")
        qtys = request.form.getlist("qty[]")
        prices = request.form.getlist("price[]")

        items = []
        for name, qty, price in zip(item_names, qtys, prices):
            qty_value = max(int(float(qty or 0)), 1)
            price_value = max(float(price or 0), 0)
            items.append({
                "name": name.strip() or "Unnamed repair item",
                "qty": qty_value,
                "price": price_value,
                "amount": qty_value * price_value,
            })

        totals = calculate_totals(items)

        cursor = db.execute(
            """
            INSERT INTO quotations (
                quotation_no, invoice_no, customer_name, phone, plate_no,
                car_model, mileage, notes, subtotal, tax, total, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TEMP",
                None,
                request.form.get("customer_name", "").strip(),
                request.form.get("phone", "").strip(),
                request.form.get("plate_no", "").strip().upper(),
                request.form.get("car_model", "").strip(),
                request.form.get("mileage", "").strip(),
                request.form.get("notes", "").strip(),
                totals["subtotal"],
                totals["tax"],
                totals["total"],
                "Draft",
            ),
        )
        quotation_id = cursor.lastrowid
        q_no = quotation_number(quotation_id)
        db.execute("UPDATE quotations SET quotation_no = ? WHERE id = ?", (q_no, quotation_id))

        for item in items:
            db.execute(
                """
                INSERT INTO quotation_items (quotation_id, name, qty, price, amount)
                VALUES (?, ?, ?, ?, ?)
                """,
                (quotation_id, item["name"], item["qty"], item["price"], item["amount"]),
            )

        db.commit()
        return redirect(url_for("view_quotation", quotation_id=quotation_id))

    content = """
    <div class="mb-4">
        <a href="/" class="text-decoration-none">← Back to Dashboard</a>
        <h1 class="fw-bold mt-2">New Repair Quotation</h1>
        <p class="text-muted">Mechanic can fill this form using phone.</p>
    </div>

    <form method="POST">
        <div class="row g-4">
            <div class="col-lg-8">
                <div class="card p-3 p-md-4 mb-4">
                    <h5 class="fw-bold mb-3">Customer Details</h5>
                    <div class="row g-3">
                        <div class="col-md-6">
                            <label class="form-label">Customer Name</label>
                            <input type="text" name="customer_name" class="form-control" placeholder="e.g. Ahmad Razif" required>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">Phone Number</label>
                            <input type="text" name="phone" class="form-control" placeholder="e.g. 012-3456789" required>
                        </div>
                    </div>
                </div>

                <div class="card p-3 p-md-4 mb-4">
                    <h5 class="fw-bold mb-3">Vehicle Details</h5>
                    <div class="row g-3">
                        <div class="col-md-4">
                            <label class="form-label">Plate No.</label>
                            <input type="text" name="plate_no" class="form-control" placeholder="e.g. SAA 1234 B" required>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Car Model</label>
                            <input type="text" name="car_model" class="form-control" placeholder="e.g. Myvi 1.5" required>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">Mileage</label>
                            <input type="text" name="mileage" class="form-control" placeholder="e.g. 82,000 km">
                        </div>
                        <div class="col-12">
                            <label class="form-label">Mechanic Notes / Customer Complaint</label>
                            <textarea name="notes" class="form-control" rows="3" placeholder="e.g. Brake noise, engine oil service due"></textarea>
                        </div>
                    </div>
                </div>

                <div class="card p-3 p-md-4">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h5 class="fw-bold mb-0">Repair Items</h5>
                        <button type="button" class="btn btn-sm btn-outline-dark btn-rounded" onclick="addItemRow()">+ Add Item</button>
                    </div>

                    <div id="repair-items">
                        <div class="row g-2 align-items-end repair-row mb-2">
                            <div class="col-12 col-md-6">
                                <label class="form-label">Repair / Parts</label>
                                <input type="text" name="item_name[]" class="form-control" placeholder="e.g. Brake pad replacement" required>
                            </div>
                            <div class="col-6 col-md-2">
                                <label class="form-label">Qty</label>
                                <input type="number" name="qty[]" class="form-control qty" value="1" min="1" oninput="calculateTotal()" required>
                            </div>
                            <div class="col-6 col-md-3">
                                <label class="form-label">Price (RM)</label>
                                <input type="number" name="price[]" class="form-control price" value="0" min="0" step="0.01" oninput="calculateTotal()" required>
                            </div>
                            <div class="col-12 col-md-1 d-grid">
                                <button type="button" class="btn btn-outline-danger btn-rounded" onclick="this.closest('.repair-row').remove(); calculateTotal();">X</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-lg-4">
                <div class="card p-3 p-md-4 sticky-lg-top" style="top: 20px;">
                    <h5 class="fw-bold mb-3">Summary</h5>
                    <div class="d-flex justify-content-between mb-2">
                        <span class="text-muted">Subtotal</span>
                        <span>RM <span id="subtotal">0.00</span></span>
                    </div>
                    <div class="d-flex justify-content-between mb-2">
                        <span class="text-muted">Service Tax 6%</span>
                        <span>RM <span id="tax">0.00</span></span>
                    </div>
                    <hr>
                    <div class="d-flex justify-content-between fs-5 fw-bold mb-3">
                        <span>Total</span>
                        <span>RM <span id="total">0.00</span></span>
                    </div>
                    <div class="d-grid gap-2">
                        <button type="submit" class="btn btn-warning btn-rounded fw-semibold">Save Quotation</button>
                        <a href="/" class="btn btn-outline-secondary btn-rounded">Cancel</a>
                    </div>
                </div>
            </div>
        </div>
    </form>
    """
    return page("New Quotation", content)


@app.route("/quotation/<int:quotation_id>")
def view_quotation(quotation_id: int):
    q = get_quotation(quotation_id)
    if not q:
        return page("Not Found", "<h3>Quotation not found.</h3>")

    items = get_items(quotation_id)
    item_rows = ""
    for idx, item in enumerate(items, 1):
        item_rows += f"""
        <tr>
            <td>{idx}</td>
            <td>{item['name']}</td>
            <td class="text-center">{item['qty']}</td>
            <td class="text-end">RM {item['price']:.2f}</td>
            <td class="text-end">RM {item['amount']:.2f}</td>
        </tr>
        """

    approve_button = ""
    invoice_button = ""
    if q["status"] == "Draft":
        approve_button = f'<a href="/quotation/{q["id"]}/approve" class="btn btn-success btn-rounded">Mark as Customer Approved</a>'
    if q["status"] == "Approved" and not q["invoice_no"]:
        invoice_button = f'<a href="/quotation/{q["id"]}/invoice" class="btn btn-warning btn-rounded fw-semibold">Generate Invoice</a>'
    if q["invoice_no"]:
        invoice_button = f'<a href="/invoice/{q["id"]}" class="btn btn-dark btn-rounded">View Invoice</a>'

    badge = "status-approved" if q["status"] == "Approved" else "status-draft"

    content = f"""
    <div class="no-print mb-4 d-flex flex-column flex-md-row justify-content-between gap-2">
        <div>
            <a href="/" class="text-decoration-none">← Back to Dashboard</a>
            <h1 class="fw-bold mt-2">Quotation Preview</h1>
        </div>
        <div class="d-grid d-md-flex gap-2 align-self-md-end">
            {approve_button}
            {invoice_button}
            <button onclick="window.print()" class="btn btn-outline-dark btn-rounded">Print / Save PDF</button>
        </div>
    </div>

    <div class="print-area card">
        <div class="d-flex justify-content-between align-items-start mb-4">
            <div>
                <h2 class="fw-bold mb-1">AZZAM AUTOCARE SERVICE</h2>
                <div class="text-muted">Repair Quotation</div>
                <div class="text-muted small">Kota Kinabalu, Sabah</div>
            </div>
            <div class="text-end">
                <h4 class="fw-bold">{q['quotation_no']}</h4>
                <span class="status-pill {badge}">{q['status']}</span>
            </div>
        </div>

        <div class="row g-3 mb-4">
            <div class="col-md-6">
                <div class="border rounded-3 p-3 h-100">
                    <div class="fw-bold mb-2">Customer</div>
                    <div>{q['customer_name']}</div>
                    <div class="text-muted">{q['phone']}</div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="border rounded-3 p-3 h-100">
                    <div class="fw-bold mb-2">Vehicle</div>
                    <div>{q['plate_no']} - {q['car_model']}</div>
                    <div class="text-muted">Mileage: {q['mileage']}</div>
                </div>
            </div>
        </div>

        <div class="mb-4">
            <div class="fw-bold mb-2">Mechanic Notes</div>
            <div class="border rounded-3 p-3 text-muted">{q['notes'] or '-'}</div>
        </div>

        <div class="table-responsive mb-4">
            <table class="table table-bordered align-middle">
                <thead class="table-light">
                    <tr>
                        <th style="width: 5%;">#</th>
                        <th>Repair / Parts</th>
                        <th class="text-center">Qty</th>
                        <th class="text-end">Price</th>
                        <th class="text-end">Amount</th>
                    </tr>
                </thead>
                <tbody>{item_rows}</tbody>
            </table>
        </div>

        <div class="row justify-content-end">
            <div class="col-md-5">
                <div class="d-flex justify-content-between mb-2">
                    <span class="text-muted">Subtotal</span>
                    <span>RM {q['subtotal']:.2f}</span>
                </div>
                <div class="d-flex justify-content-between mb-2">
                    <span class="text-muted">Service Tax 6%</span>
                    <span>RM {q['tax']:.2f}</span>
                </div>
                <hr>
                <div class="d-flex justify-content-between fs-5 fw-bold">
                    <span>Total</span>
                    <span>RM {q['total']:.2f}</span>
                </div>
            </div>
        </div>

        <hr class="my-4">
        <div class="small text-muted">
            This quotation is valid for 7 days. Repair work will proceed after customer approval.
        </div>
    </div>
    """
    return page("Quotation Preview", content)


@app.route("/quotation/<int:quotation_id>/approve")
def approve_quotation(quotation_id: int):
    db = get_db()
    db.execute("UPDATE quotations SET status = 'Approved' WHERE id = ?", (quotation_id,))
    db.commit()
    return redirect(url_for("view_quotation", quotation_id=quotation_id))


@app.route("/quotation/<int:quotation_id>/invoice")
def generate_invoice(quotation_id: int):
    db = get_db()
    inv_no = invoice_number(quotation_id)
    db.execute(
        "UPDATE quotations SET status = 'Approved', invoice_no = ? WHERE id = ?",
        (inv_no, quotation_id),
    )
    db.commit()
    return redirect(url_for("view_invoice", quotation_id=quotation_id))


@app.route("/invoice/<int:quotation_id>")
def view_invoice(quotation_id: int):
    q = get_quotation(quotation_id)
    if not q or not q["invoice_no"]:
        return page("Not Found", "<h3>Invoice not found.</h3>")

    items = get_items(quotation_id)
    item_rows = ""
    for idx, item in enumerate(items, 1):
        item_rows += f"""
        <tr>
            <td>{idx}</td>
            <td>{item['name']}</td>
            <td class="text-center">{item['qty']}</td>
            <td class="text-end">RM {item['price']:.2f}</td>
            <td class="text-end">RM {item['amount']:.2f}</td>
        </tr>
        """

    content = f"""
    <div class="no-print mb-4 d-flex flex-column flex-md-row justify-content-between gap-2">
        <div>
            <a href="/quotation/{q['id']}" class="text-decoration-none">← Back to Quotation</a>
            <h1 class="fw-bold mt-2">Invoice Preview</h1>
        </div>
        <div class="d-grid d-md-flex gap-2 align-self-md-end">
            <button onclick="window.print()" class="btn btn-outline-dark btn-rounded">Print / Save PDF</button>
        </div>
    </div>

    <div class="print-area card">
        <div class="d-flex justify-content-between align-items-start mb-4">
            <div>
                <h2 class="fw-bold mb-1">AZZAM AUTOCARE SERVICE</h2>
                <div class="text-muted">Invoice</div>
                <div class="text-muted small">Kota Kinabalu, Sabah</div>
            </div>
            <div class="text-end">
                <h4 class="fw-bold">{q['invoice_no']}</h4>
                <div class="text-muted small">Based on {q['quotation_no']}</div>
            </div>
        </div>

        <div class="row g-3 mb-4">
            <div class="col-md-6">
                <div class="border rounded-3 p-3 h-100">
                    <div class="fw-bold mb-2">Bill To</div>
                    <div>{q['customer_name']}</div>
                    <div class="text-muted">{q['phone']}</div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="border rounded-3 p-3 h-100">
                    <div class="fw-bold mb-2">Vehicle</div>
                    <div>{q['plate_no']} - {q['car_model']}</div>
                    <div class="text-muted">Mileage: {q['mileage']}</div>
                </div>
            </div>
        </div>

        <div class="table-responsive mb-4">
            <table class="table table-bordered align-middle">
                <thead class="table-light">
                    <tr>
                        <th style="width: 5%;">#</th>
                        <th>Description</th>
                        <th class="text-center">Qty</th>
                        <th class="text-end">Price</th>
                        <th class="text-end">Amount</th>
                    </tr>
                </thead>
                <tbody>{item_rows}</tbody>
            </table>
        </div>

        <div class="row justify-content-end">
            <div class="col-md-5">
                <div class="d-flex justify-content-between mb-2">
                    <span class="text-muted">Subtotal</span>
                    <span>RM {q['subtotal']:.2f}</span>
                </div>
                <div class="d-flex justify-content-between mb-2">
                    <span class="text-muted">Service Tax 6%</span>
                    <span>RM {q['tax']:.2f}</span>
                </div>
                <hr>
                <div class="d-flex justify-content-between fs-5 fw-bold">
                    <span>Total Payable</span>
                    <span>RM {q['total']:.2f}</span>
                </div>
            </div>
        </div>

        <hr class="my-4">
        <div class="row g-3 small text-muted">
            <div class="col-md-6">
                <strong>Payment Method</strong><br>
                Cash / Bank Transfer / QR Pay
            </div>
            <div class="col-md-6 text-md-end">
                <strong>Payment Status</strong><br>
                Unpaid
            </div>
        </div>
    </div>
    """
    return page("Invoice Preview", content)


def run_tests() -> None:
    """Basic smoke tests for SQLite calculation and Flask routes."""
    global DATABASE
    DATABASE = "test_garage.db"
    if os.path.exists(DATABASE):
        os.remove(DATABASE)

    with app.app_context():
        init_db()
        totals = calculate_totals([
            {"qty": 1, "price": 180.0},
            {"qty": 2, "price": 50.0},
        ])
        assert totals["subtotal"] == 280.00
        assert totals["tax"] == 16.80
        assert totals["total"] == 296.80

    client = app.test_client()

    dashboard_response = client.get("/")
    assert dashboard_response.status_code == 200
    assert b"Azzam Autocare Dashboard" in dashboard_response.data

    create_response = client.post(
        "/quotation/new",
        data={
            "customer_name": "Ahmad Razif",
            "phone": "012-3456789",
            "plate_no": "saa 1234 b",
            "car_model": "Perodua Myvi",
            "mileage": "82000 km",
            "notes": "Brake noise",
            "item_name[]": ["Brake pad", "Engine oil"],
            "qty[]": ["1", "1"],
            "price[]": ["180", "120"],
        },
        follow_redirects=True,
    )
    assert create_response.status_code == 200
    assert b"QT-2026-0001" in create_response.data
    assert b"RM 318.00" in create_response.data

    approve_response = client.get("/quotation/1/approve", follow_redirects=True)
    assert approve_response.status_code == 200

    invoice_response = client.get("/quotation/1/invoice", follow_redirects=True)
    assert invoice_response.status_code == 200
    assert b"INV-2026-0001" in invoice_response.data

    with app.app_context():
        q = get_quotation(1)
        assert q is not None
        assert q["plate_no"] == "SAA 1234 B"
        assert q["status"] == "Approved"
        assert q["invoice_no"] == "INV-2026-0001"
        items = get_items(1)
        assert len(items) == 2

    if os.path.exists(DATABASE):
        os.remove(DATABASE)

    print("All tests passed.")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_tests()
    else:
        with app.app_context():
            init_db()

        # debug=False and use_reloader=False avoid Werkzeug debug tools that may require _multiprocessing.
        app.run(
            host="0.0.0.0",
            port=5000,
            debug=False,
            use_reloader=False,
            use_debugger=False,
        )
