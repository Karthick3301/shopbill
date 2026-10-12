"""Render an invoice PDF with ReportLab (no extra dependencies)."""

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def render_invoice_pdf(invoice):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 50

    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, y, "ShopBill")
    y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Invoice #{invoice.pk}  |  {invoice.created_at:%Y-%m-%d %H:%M}")
    y -= 16
    c.drawString(40, y, f"Customer: {invoice.customer.name}")
    y -= 16
    if invoice.created_by:
        c.drawString(40, y, f"Billed by: {invoice.created_by.username}")
        y -= 16
    y -= 8

    # Table header.
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Product")
    c.drawRightString(380, y, "Qty x Price")
    c.drawRightString(480, y, "Amount")
    y -= 14
    c.line(40, y, 480, y)
    y -= 16

    c.setFont("Helvetica", 11)
    for item in invoice.items.all():
        if y < 120:  # new page when running out of room
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 11)
        c.drawString(40, y, item.product.name[:40])
        c.drawRightString(380, y, f"{item.quantity} x {item.unit_price}")
        c.drawRightString(480, y, f"{item.line_total:.2f}")
        y -= 16

    y -= 8
    c.line(40, y, 480, y)
    y -= 18
    c.drawRightString(480, y, f"Subtotal: {invoice.subtotal:.2f}")
    y -= 16
    c.drawRightString(480, y, f"Tax: {invoice.tax:.2f}")
    y -= 16
    c.drawRightString(480, y, f"Discount: {invoice.discount:.2f}")
    y -= 18
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(480, y, f"Total: {invoice.total:.2f}")

    c.showPage()
    c.save()
    return buf.getvalue()
