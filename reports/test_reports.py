"""Stage 4 tests: dashboard permissions, aggregates, low stock, CSV export."""

import csv
import datetime
from decimal import Decimal
from io import StringIO

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from billing.models import Customer, Invoice
from billing.services import create_invoice
from inventory.models import Category, Product


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="owner", password="pw", role=User.Roles.OWNER)


@pytest.fixture
def staff(db):
    return User.objects.create_user(username="staff", password="pw", role=User.Roles.STAFF)


@pytest.fixture
def category(db):
    return Category.objects.create(name="Drinks")


@pytest.fixture
def customer(db):
    return Customer.objects.create(name="Walk-in")


def make_product(category, name, price=10, stock=50, limit=5):
    return Product.objects.create(
        name=name, category=category, price=price, stock=stock, low_stock_limit=limit
    )


def backdate(invoice, days_ago):
    """Move an invoice's date back N days (keeps the time-of-day)."""
    Invoice.objects.filter(pk=invoice.pk).update(
        created_at=timezone.now() - datetime.timedelta(days=days_ago)
    )


# --- Permissions: Owner only ---


@pytest.mark.django_db
def test_staff_gets_403_and_anonymous_redirected(client, staff):
    client.force_login(staff)
    assert client.get(reverse("reports:dashboard")).status_code == 403
    assert client.get(reverse("reports:sales-csv")).status_code == 403
    client.logout()
    for url in (reverse("reports:dashboard"), reverse("reports:sales-csv")):
        resp = client.get(url)
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# --- Aggregates ---


@pytest.mark.django_db
def test_today_totals_are_correct(client, owner, category, customer):
    cola = make_product(category, "Cola", price=20)
    chips = make_product(category, "Chips", price=15)
    create_invoice(
        created_by=owner, customer=customer,
        lines=[{"product_id": cola.pk, "quantity": 2, "unit_price": None}],  # 40
    )
    old = create_invoice(
        created_by=owner, customer=customer,
        lines=[{"product_id": chips.pk, "quantity": 1, "unit_price": None}],  # 15
    )
    backdate(old, 2)  # yesterday-ish sale must not count toward today
    client.force_login(owner)
    resp = client.get(reverse("reports:dashboard"))
    assert resp.status_code == 200
    assert resp.context["today_total"] == Decimal("40")
    assert resp.context["today_count"] == 1
    assert resp.context["month_total"] >= Decimal("55")


@pytest.mark.django_db
def test_top_products_ordered_by_quantity(client, owner, category, customer):
    a = make_product(category, "A", stock=100)
    b = make_product(category, "B", stock=100)
    c = make_product(category, "C", stock=100)
    create_invoice(
        created_by=owner, customer=customer,
        lines=[
            {"product_id": a.pk, "quantity": 5, "unit_price": None},
            {"product_id": b.pk, "quantity": 3, "unit_price": None},
            {"product_id": c.pk, "quantity": 8, "unit_price": None},
        ],
    )
    client.force_login(owner)
    top = client.get(reverse("reports:dashboard")).context["top_products"]
    assert [(r["product__name"], r["qty"]) for r in top] == [("C", 8), ("A", 5), ("B", 3)]


@pytest.mark.django_db
def test_low_stock_excludes_inactive(client, owner, category):
    low = make_product(category, "LowActive", stock=2, limit=5)
    dead = make_product(category, "LowDead", stock=1, limit=5)
    dead.is_active = False
    dead.save(update_fields=["is_active", "updated_at"])
    make_product(category, "Fine", stock=50, limit=5)
    client.force_login(owner)
    names = [p.name for p in client.get(reverse("reports:dashboard")).context["low_stock"]]
    assert low.name in names
    assert dead.name not in names
    assert "Fine" not in names


# --- CSV export ---


@pytest.mark.django_db
def test_csv_rows_and_date_filter(client, owner, category, customer):
    tz = timezone.get_current_timezone()
    cola = make_product(category, "Cola", price=20)
    inv1 = create_invoice(
        created_by=owner, customer=customer,
        lines=[{"product_id": cola.pk, "quantity": 1, "unit_price": None}],
    )
    inv2 = create_invoice(
        created_by=owner, customer=customer,
        lines=[{"product_id": cola.pk, "quantity": 2, "unit_price": None}],
    )
    Invoice.objects.filter(pk=inv1.pk).update(
        created_at=timezone.make_aware(datetime.datetime(2026, 9, 5, 12, 0), tz)
    )
    Invoice.objects.filter(pk=inv2.pk).update(
        created_at=timezone.make_aware(datetime.datetime(2026, 9, 20, 12, 0), tz)
    )
    client.force_login(owner)

    resp = client.get(reverse("reports:sales-csv"))
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    rows = list(csv.reader(StringIO(resp.content.decode())))
    assert rows[0] == ["invoice", "date", "customer", "subtotal", "discount", "tax", "total"]
    assert len(rows) == 3  # header + 2 invoices

    resp = client.get(reverse("reports:sales-csv") + "?from=2026-09-01&to=2026-09-10")
    rows = list(csv.reader(StringIO(resp.content.decode())))
    assert len(rows) == 2  # header + inv1 only
    assert rows[1][0] == str(inv1.pk)
    assert rows[1][2] == "Walk-in"
    assert rows[1][6] == "20.00"


@pytest.mark.django_db
def test_csv_injection_protected(client, owner, category):
    evil = Customer.objects.create(name="=2+2+cmd|' /C calc'!A0")
    cola = make_product(category, "Cola", price=10)
    create_invoice(
        created_by=owner, customer=evil,
        lines=[{"product_id": cola.pk, "quantity": 1, "unit_price": None}],
    )
    client.force_login(owner)
    rows = list(csv.reader(StringIO(client.get(reverse("reports:sales-csv")).content.decode())))
    assert rows[1][2].startswith("'=")
