"""Stage 2 tests: product/category permissions + stock movement logging."""

import pytest
from django.urls import reverse

from accounts.models import User
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
def product(db, category):
    # Creating with stock=10 logs one INITIAL movement (change=+10).
    return Product.objects.create(
        name="Cola", category=category, price=20, stock=10, low_stock_limit=5
    )


# --- Permission rules: Staff views, Owner mutates ---


@pytest.mark.django_db
def test_staff_can_view_product_list(client, staff, product):
    client.force_login(staff)
    resp = client.get(reverse("inventory:product-list"))
    assert resp.status_code == 200
    assert product.name in resp.content.decode()


@pytest.mark.django_db
def test_anonymous_redirected_to_login(client):
    resp = client.get(reverse("inventory:product-list"))
    assert resp.status_code == 302
    assert "login" in resp["Location"]


@pytest.mark.django_db
def test_staff_cannot_add_product(client, staff, category):
    client.force_login(staff)
    url = reverse("inventory:product-add")
    assert client.get(url).status_code == 403
    resp = client.post(
        url,
        {"name": "X", "category": category.id, "price": 10, "stock": 1, "low_stock_limit": 5},
    )
    assert resp.status_code == 403
    assert not Product.objects.filter(name="X").exists()


@pytest.mark.django_db
def test_staff_cannot_edit_or_delete_product(client, staff, product):
    client.force_login(staff)
    assert client.get(reverse("inventory:product-edit", args=[product.pk])).status_code == 403
    assert client.get(reverse("inventory:product-delete", args=[product.pk])).status_code == 403
    assert client.post(reverse("inventory:product-delete", args=[product.pk])).status_code == 403
    # Soft delete must not have run: row still exists and stays active.
    product.refresh_from_db()
    assert product.is_active is True


@pytest.mark.django_db
def test_staff_category_read_only(client, staff, category):
    client.force_login(staff)
    assert client.get(reverse("inventory:category-list")).status_code == 200
    assert client.get(reverse("inventory:category-add")).status_code == 403


@pytest.mark.django_db
def test_owner_can_create_product_and_logs_movement(client, owner, category):
    client.force_login(owner)
    resp = client.post(
        reverse("inventory:product-add"),
        {"name": "Chips", "category": category.id, "price": 15, "stock": 7, "low_stock_limit": 5},
    )
    assert resp.status_code == 302
    p = Product.objects.get(name="Chips")
    move = StockMovement.objects.get(product=p)
    assert move.change == 7
    assert move.reason == StockMovement.Reasons.INITIAL


# --- StockMovement logging ---


@pytest.mark.django_db
def test_create_logs_initial_movement(product):
    moves = StockMovement.objects.filter(product=product)
    assert moves.count() == 1
    assert moves.first().change == 10


@pytest.mark.django_db
def test_stock_increase_and_decrease_logged(product):
    product.stock = 13  # +3
    product.save()
    product.stock = 11  # -2
    product.save()
    changes = list(
        StockMovement.objects.filter(product=product).order_by("created_at").values_list(
            "change", flat=True
        )
    )
    assert changes == [10, 3, -2]


@pytest.mark.django_db
def test_price_only_edit_creates_no_movement(product):
    assert StockMovement.objects.filter(product=product).count() == 1
    product.price = 99
    product.save()
    assert StockMovement.objects.filter(product=product).count() == 1


@pytest.mark.django_db
def test_owner_edit_stock_via_view_logs_delta(client, owner, product):
    client.force_login(owner)
    url = reverse("inventory:product-edit", args=[product.pk])
    resp = client.post(
        url,
        {
            "name": product.name,
            "category": product.category_id,
            "price": str(product.price),
            "stock": 12,  # 10 -> 12, delta +2
            "low_stock_limit": product.low_stock_limit,
        },
    )
    assert resp.status_code == 302
    assert StockMovement.objects.filter(product=product, change=2).exists()


@pytest.mark.django_db
def test_low_stock_highlighted_in_list(client, owner, category):
    low = Product.objects.create(
        name="Rare", category=category, price=5, stock=2, low_stock_limit=5
    )
    assert low.is_low_stock
    client.force_login(owner)
    content = client.get(reverse("inventory:product-list")).content.decode()
    assert "Low stock" in content
    assert "table-warning" in content


# --- Soft delete (is_active) ---


@pytest.mark.django_db
def test_deactivate_page_says_deactivate(client, owner, product):
    client.force_login(owner)
    content = client.get(reverse("inventory:product-delete", args=[product.pk])).content.decode()
    assert "Deactivate" in content
    assert "Delete product" not in content


@pytest.mark.django_db
def test_owner_deactivate_keeps_row_and_history(client, owner, product):
    moves_before = StockMovement.objects.filter(product=product).count()
    assert moves_before == 1
    client.force_login(owner)
    resp = client.post(reverse("inventory:product-delete", args=[product.pk]))
    assert resp.status_code == 302
    # Row kept with is_active=False; history kept; no movement logged.
    product.refresh_from_db()
    assert product.is_active is False
    assert Product.objects.filter(pk=product.pk).exists()
    assert StockMovement.objects.filter(product=product).count() == moves_before


@pytest.mark.django_db
def test_deactivated_hidden_from_list_search_and_filter(client, owner, category, product):
    client.force_login(owner)
    product.is_active = False
    product.save(update_fields=["is_active", "updated_at"])
    # Check the table cell (not raw page: the search box echoes the query).
    content = client.get(reverse("inventory:product-list")).content.decode()
    assert "<td>Cola</td>" not in content
    # Name search and category filter (billing-style search) also hide it.
    assert "<td>Cola</td>" not in client.get(reverse("inventory:product-list") + "?q=Cola").content.decode()
    assert (
        "<td>Cola</td>"
        not in client.get(reverse("inventory:product-list") + f"?category={category.id}").content.decode()
    )


@pytest.mark.django_db
def test_active_manager_excludes_inactive(category, product):
    # Billing product search must use Product.objects.active().
    assert product.name in [p.name for p in Product.objects.active()]
    product.is_active = False
    product.save(update_fields=["is_active", "updated_at"])
    assert product.name not in [p.name for p in Product.objects.active()]
    # Full history still queryable via the default manager.
    assert Product.objects.filter(pk=product.pk).exists()
