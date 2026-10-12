Project: ShopBill, a billing and inventory web app for a small retail shop.

Stack: Django, PostgreSQL (SQLite in development), Django templates with
Bootstrap 5, vanilla JavaScript, Chart.js, ReportLab for PDF invoices.

Apps: accounts, inventory, billing, reports.

Roles: Owner (full access) and Staff (billing and viewing products only).

Models: Category, Product (name, category, price, stock, low_stock_limit),
Customer, Invoice (customer, created_by, date, subtotal, tax, discount, total),
InvoiceItem (invoice, product, quantity, unit_price),
StockMovement (product, change, reason, date).

Rules:
- Saving an invoice must use transaction.atomic() and update stock with
  F() expressions. Reject the sale if stock is insufficient.
- Every stock change creates a StockMovement record.
- Use class-based views, Django forms, and permission checks by role.
- Keep code simple and readable, with short comments explaining why.
- Write tests with pytest-django for invoice and stock logic.
- Mobile responsive UI.
- Never hardcode secrets; use environment variables.

Work one stage at a time. After each stage, explain what you built and
list the files changed. Do not start the next stage until I say so.