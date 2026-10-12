"""Seed demo shop data. Safe to run twice (get_or_create + guards)."""

import datetime
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from billing.models import Customer, Invoice
from billing.services import create_invoice
from inventory.models import Category, Product, StockMovement

PRODUCTS = [
    # (name, category, price, stock, low_stock_limit)
    # Stocks are generous so 25 sample invoices never drive them negative.
    ("Cola 500ml", "Beverages", 25, 400, 10),
    ("Orange Juice 1L", "Beverages", 60, 250, 8),
    ("Mango Drink 200ml", "Beverages", 15, 400, 15),
    ("Potato Chips", "Snacks", 35, 300, 10),
    ("Chocolate Bar", "Snacks", 30, 300, 10),
    ("Biscuits Pack", "Snacks", 20, 350, 15),
    ("Notebook A4", "Stationery", 50, 250, 8),
    ("Ball Pen", "Stationery", 10, 500, 20),
]

CUSTOMERS = [
    ("Walk-in Customer", "9876500000"),
    ("Priya Sharma", "9876500001"),
    ("Rahul Verma", "9876500002"),
]

N_SAMPLE_INVOICES = 25
TAX_CHOICES = (Decimal("0"), Decimal("5"), Decimal("10"))
DISCOUNT_CHOICES = (Decimal("0"), Decimal("0"), Decimal("5"), Decimal("10"))


def _sample_dates(n, rng):
    """Sale datetimes over the last ~5 months, weighted toward recent weeks.

    Oldest first so invoice numbers increase with date; never in the
    future (latest is at least 1 hour before now).
    """
    latest = timezone.now() - datetime.timedelta(hours=1)
    dates = []
    for _ in range(n):
        days_ago = int(150 * (rng.random() ** 1.5))  # exponent biases toward now
        day = latest - datetime.timedelta(days=days_ago)
        # Shop hours: 10:00-20:00 local time.
        day = day.replace(hour=rng.randint(10, 20), minute=rng.randint(0, 59), second=0)
        dates.append(min(day, latest))
    return sorted(dates)


class Command(BaseCommand):
    help = "Seed demo users, catalog, customers and sample invoices (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        owner, _ = User.objects.update_or_create(
            username="owner",
            defaults={"role": User.Roles.OWNER, "is_staff": True, "is_superuser": False},
        )
        owner.set_password("demo123")
        owner.save()
        self.stdout.write(self.style.SUCCESS("Demo user owner/demo123 (Owner, not superuser)"))

        staff, _ = User.objects.update_or_create(
            username="staff",
            defaults={"role": User.Roles.STAFF, "is_staff": False, "is_superuser": False},
        )
        staff.set_password("demo123")
        staff.save()
        self.stdout.write(self.style.SUCCESS("Demo user staff/demo123 (Staff)"))

        categories = {}
        for name in ("Beverages", "Snacks", "Stationery"):
            categories[name], _ = Category.objects.get_or_create(name=name)

        for name, cat, price, stock, limit in PRODUCTS:
            # Stock is only set on first create so re-runs log no movements.
            product, created = Product.objects.get_or_create(
                name=name,
                defaults={
                    "category": categories[cat],
                    "price": price,
                    "stock": stock,
                    "low_stock_limit": limit,
                },
            )
            if not created:
                product.category = categories[cat]
                product.price = price
                product.low_stock_limit = limit
                product.save()
        self.stdout.write(self.style.SUCCESS(f"{len(PRODUCTS)} products ready"))

        customers = []
        for name, phone in CUSTOMERS:
            customer, _ = Customer.objects.get_or_create(
                name=name, defaults={"phone": phone}
            )
            customers.append(customer)
        self.stdout.write(self.style.SUCCESS(f"{len(customers)} customers ready"))

        if Invoice.objects.exists():
            # Invoices go through the real atomic save path, which reduces
            # stock; re-creating them would double-charge, so skip on re-run.
            self.stdout.write("Invoices already exist, skipping sample invoices")
            return

        rng = random.Random(42)  # deterministic demo data
        by_name = {p.name: p for p in Product.objects.filter(is_active=True)}
        names = [name for name, _cat, _price, _s, _l in PRODUCTS]
        for target in _sample_dates(N_SAMPLE_INVOICES, rng):
            lines = [
                {
                    "product_id": by_name[name].pk,
                    "quantity": rng.randint(1, 4),
                    "unit_price": None,  # current product price
                }
                for name in rng.sample(names, rng.randint(1, 3))
            ]
            before = set(StockMovement.objects.values_list("pk", flat=True))
            invoice = create_invoice(
                created_by=owner,
                customer=rng.choice(customers),
                lines=lines,
                tax=rng.choice(TAX_CHOICES),
                discount=rng.choice(DISCOUNT_CHOICES),
            )
            # Backdate the invoice and its matching SALE movements together
            # via queryset updates (no save(), so no extra movement rows).
            new_pks = set(StockMovement.objects.values_list("pk", flat=True)) - before
            Invoice.objects.filter(pk=invoice.pk).update(created_at=target)
            StockMovement.objects.filter(pk__in=new_pks).update(created_at=target)
        self.stdout.write(self.style.SUCCESS(f"{N_SAMPLE_INVOICES} sample invoices created"))

        # Leave 2 products at/below their limit through the normal save()
        # path, so ADJUSTMENT movements exist and low-stock UI has data.
        for name, offset in (("Orange Juice 1L", 0), ("Notebook A4", 3)):
            product = Product.objects.get(name=name)
            product.stock = max(0, product.low_stock_limit - offset)
            product.save()
        self.stdout.write(self.style.SUCCESS("2 products set to low stock"))
