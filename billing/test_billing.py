"""Stage 3 tests: invoice stock logic, SALE movements, rollback."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.urls import reverse

from accounts.models import User
from billing.models import Customer, Invoice, InvoiceItem
from billing.services import create_invoice
from inventory.models import Category, Product, StockMovement


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
def cola(db, category):
    return Product.objects.create(
        name="Cola", category=category, price=20, stock=10, low_stock_limit=5
    )


@pytest.fixture
def chips(db, category):
    return Product.objects.create(
        name="Chips", category=category, price=15, stock=5, low_stock_limit=2
    )


@pytest.fixture
def customer(db):
    return Customer.objects.create(name="Walk-in", phone="123")


# --- Customer permissions: both roles create/edit, only Owner deletes ---


@pytest.mark.django_db
def test_staff_can_create_and_edit_customer(client, staff):
    client.force_login(staff)
    resp = client.post(
        reverse("billing:customer-add"), {"name": "A", "phone": "", "email": "", "address": ""}
    )
    assert resp.status_code == 302
    c = Customer.objects.get(name="A")
    resp = client.post(
        reverse("billing:customer-edit", args=[c.pk]),
        {"name": "A2", "phone": "", "email": "", "address": ""},
    )
    assert resp.status_code == 302
    c.refresh_from_db()
    assert c.name == "A2"


@pytest.mark.django_db
def test_staff_cannot_delete_customer(client, staff, customer):
    client.force_login(staff)
    assert client.get(reverse("billing:customer-delete", args=[customer.pk])).status_code == 403
    assert client.post(reverse("billing:customer-delete", args=[customer.pk])).status_code == 403
    assert Customer.objects.filter(pk=customer.pk).exists()


@pytest.mark.django_db
def test_owner_can_delete_customer(client, owner, customer):
    client.force_login(owner)
    assert client.post(reverse("billing:customer-delete", args=[customer.pk])).status_code == 302
    assert not Customer.objects.filter(pk=customer.pk).exists()


@pytest.mark.django_db
def test_owner_cannot_delete_customer_with_invoices(client, owner, customer, cola):
    create_invoice(
        created_by=owner,
        customer=customer,
        lines=[{"product_id": cola.pk, "quantity": 1, "unit_price": None}],
    )
    client.force_login(owner)
    # Refused with a redirect + friendly message, never a 500.
    resp = client.post(reverse("billing:customer-delete", args=[customer.pk]), follow=True)
    assert resp.status_code == 200
    assert Customer.objects.filter(pk=customer.pk).exists()
    assert "Cannot delete" in resp.content.decode()


@pytest.mark.django_db
def test_customer_delete_page_warns_and_hides_button(client, owner, customer, cola):
    create_invoice(
        created_by=owner,
        customer=customer,
        lines=[{"product_id": cola.pk, "quantity": 1, "unit_price": None}],
    )
    client.force_login(owner)
    content = client.get(reverse("billing:customer-delete", args=[customer.pk])).content.decode()
    assert "cannot be deleted" in content
    assert ">Delete</button>" not in content
    # A customer without invoices still gets the Delete button.
    clean = Customer.objects.create(name="Clean")
    content = client.get(reverse("billing:customer-delete", args=[clean.pk])).content.decode()
    assert ">Delete</button>" in content


# --- Stock reduction + SALE movements ---


@pytest.mark.django_db
def test_create_invoice_reduces_stock_and_logs_sale(owner, customer, cola, chips):
    moves_before = StockMovement.objects.count()
    inv = create_invoice(
        created_by=owner,
        customer=customer,
        lines=[
            {"product_id": cola.pk, "quantity": 3, "unit_price": None},
            {"product_id": chips.pk, "quantity": 2, "unit_price": Decimal("15")},
        ],
        tax=Decimal("5"),
        discount=Decimal("2"),
    )
    cola.refresh_from_db()
    chips.refresh_from_db()
    assert cola.stock == 7
    assert chips.stock == 3
    # Totals: 3*20 + 2*15 = 90 subtotal; 90 + 5 - 2 = 93.
    inv.refresh_from_db()
    assert inv.subtotal == Decimal("90")
    assert inv.total == Decimal("93")
    assert InvoiceItem.objects.filter(invoice=inv).count() == 2
    # One SALE movement per item with negative change.
    new_moves = StockMovement.objects.order_by("pk")[moves_before:]
    assert [(m.product_id, m.change, m.reason) for m in new_moves] == [
        (cola.pk, -3, StockMovement.Reasons.SALE),
        (chips.pk, -2, StockMovement.Reasons.SALE),
    ]


@pytest.mark.django_db
def test_insufficient_stock_rolls_everything_back(owner, customer, cola, chips):
    with pytest.raises(ValidationError):
        create_invoice(
            created_by=owner,
            customer=customer,
            lines=[
                {"product_id": cola.pk, "quantity": 2, "unit_price": None},
                {"product_id": chips.pk, "quantity": 99, "unit_price": None},
            ],
        )
    # Whole sale rejected: no invoice/items/movements, stock untouched.
    assert Invoice.objects.count() == 0
    assert InvoiceItem.objects.count() == 0
    cola.refresh_from_db()
    chips.refresh_from_db()
    assert (cola.stock, chips.stock) == (10, 5)
    assert StockMovement.objects.filter(reason=StockMovement.Reasons.SALE).count() == 0


@pytest.mark.django_db
def test_inactive_product_rejected(owner, customer, cola):
    cola.is_active = False
    cola.save(update_fields=["is_active", "updated_at"])
    with pytest.raises(ValidationError):
        create_invoice(
            created_by=owner,
            customer=customer,
            lines=[{"product_id": cola.pk, "quantity": 1, "unit_price": None}],
        )
    assert Invoice.objects.count() == 0
    assert StockMovement.objects.filter(reason=StockMovement.Reasons.SALE).count() == 0


@pytest.mark.django_db
def test_sold_product_cannot_be_hard_deleted(owner, customer, cola):
    create_invoice(
        created_by=owner,
        customer=customer,
        lines=[{"product_id": cola.pk, "quantity": 1, "unit_price": None}],
    )
    # InvoiceItem.product is PROTECT: hard delete must fail, history survives.
    with pytest.raises(ProtectedError):
        cola.delete()
    assert Product.objects.filter(pk=cola.pk).exists()


# --- Views: search, create, PDF ---


@pytest.mark.django_db
def test_product_search_hides_inactive(client, staff, cola, category):
    dead = Product.objects.create(
        name="Cola Zero", category=category, price=20, stock=4, low_stock_limit=5
    )
    dead.is_active = False
    dead.save(update_fields=["is_active", "updated_at"])
    client.force_login(staff)
    data = client.get(reverse("billing:product-search") + "?q=cola").json()["results"]
    names = [r["name"] for r in data]
    assert "Cola" in names
    assert "Cola Zero" not in names


@pytest.mark.django_db
def test_invoice_create_view_and_pdf(client, staff, customer, cola):
    import json

    client.force_login(staff)  # Staff may bill too.
    resp = client.post(
        reverse("billing:invoice-create"),
        {
            "customer": customer.pk,
            "tax": "0",
            "discount": "0",
            "items_json": json.dumps([{"product_id": cola.pk, "quantity": 2}]),
        },
    )
    assert resp.status_code == 302
    inv = Invoice.objects.get()
    assert inv.total == Decimal("40")
    cola.refresh_from_db()
    assert cola.stock == 8
    pdf = client.get(reverse("billing:invoice-pdf", args=[inv.pk]))
    assert pdf.status_code == 200
    assert pdf["Content-Type"] == "application/pdf"
    assert pdf.content[:4] == b"%PDF"

    # Missing invoice -> 404, never a 500.
    assert client.get(reverse("billing:invoice-pdf", args=[999999])).status_code == 404


@pytest.mark.django_db
def test_invoice_list_and_detail(client, owner, customer, cola):
    inv = create_invoice(
        created_by=owner,
        customer=customer,
        lines=[{"product_id": cola.pk, "quantity": 1, "unit_price": None}],
    )
    client.force_login(owner)
    assert str(inv.pk) in client.get(reverse("billing:invoice-list")).content.decode()
    assert "Cola" in client.get(reverse("billing:invoice-detail", args=[inv.pk])).content.decode()
