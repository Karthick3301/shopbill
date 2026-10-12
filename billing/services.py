"""Invoice saving logic (Stage 3).

Must run inside transaction.atomic(): product rows are locked with
select_for_update(), stock is reduced with F() (no save() call, so no
model-level logging fires), and a SALE StockMovement is written
explicitly per item. Any insufficient stock aborts the whole sale.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from inventory.models import Product, StockMovement

from .models import Invoice, InvoiceItem


def create_invoice(*, created_by, customer, lines, tax=0, discount=0):
    """Create an invoice + items and reduce stock atomically.

    lines: iterable of {"product_id": int, "quantity": int,
                        "unit_price": Decimal | None (defaults to product price)}.
    Raises ValidationError if any line is invalid/inactive/out of stock.
    """
    lines = list(lines)
    if not lines:
        raise ValidationError("Add at least one item to the invoice.")
    tax = Decimal(tax or 0)
    discount = Decimal(discount or 0)
    if tax < 0 or discount < 0:
        raise ValidationError("Tax and discount cannot be negative.")

    # Merge duplicate product rows so locking/checks happen once per product.
    merged = {}
    for line in lines:
        try:
            pid = int(line.get("product_id"))
            qty = int(line.get("quantity"))
        except (TypeError, ValueError):
            raise ValidationError("Invalid product or quantity.")
        if qty < 1:
            raise ValidationError("Quantity must be at least 1.")
        entry = merged.setdefault(pid, {"quantity": 0, "unit_price": line.get("unit_price")})
        entry["quantity"] += qty
        # Last explicit unit price wins; None means "use current product price".
        if line.get("unit_price") is not None:
            entry["unit_price"] = line.get("unit_price")

    with transaction.atomic():
        # Lock product rows so two concurrent sales cannot oversell.
        products = list(
            Product.objects.select_for_update().filter(pk__in=list(merged.keys()))
        )
        by_id = {p.pk: p for p in products}
        missing = set(merged) - set(by_id)
        if missing:
            raise ValidationError("A selected product does not exist.")
        inactive = [p for p in products if not p.is_active]
        if inactive:
            raise ValidationError("A selected product is no longer sold.")
        for pid, entry in merged.items():
            if by_id[pid].stock < entry["quantity"]:
                raise ValidationError(
                    f"Insufficient stock for {by_id[pid].name} "
                    f"(have {by_id[pid].stock}, need {entry['quantity']})."
                )

        subtotal = Decimal("0")
        prepared = []  # (product, qty, unit_price)
        for pid, entry in merged.items():
            product = by_id[pid]
            unit_price = entry["unit_price"]
            unit_price = product.price if unit_price in (None, "") else Decimal(unit_price)
            if unit_price < 0:
                raise ValidationError("Unit price cannot be negative.")
            subtotal += unit_price * entry["quantity"]
            prepared.append((product, entry["quantity"], unit_price))

        total = subtotal + tax - discount
        if total < 0:
            total = Decimal("0")

        invoice = Invoice.objects.create(
            customer=customer,
            created_by=created_by,
            subtotal=subtotal,
            tax=tax,
            discount=discount,
            total=total,
        )
        InvoiceItem.objects.bulk_create(
            InvoiceItem(
                invoice=invoice, product=p, quantity=qty, unit_price=price
            )
            for p, qty, price in prepared
        )
        # F() update: single query per product, no save() -> log SALE manually.
        for product, qty, _price in prepared:
            Product.objects.filter(pk=product.pk).update(stock=F("stock") - qty)
        StockMovement.objects.bulk_create(
            StockMovement(product=p, change=-qty, reason=StockMovement.Reasons.SALE)
            for p, qty, _price in prepared
        )
        return invoice
