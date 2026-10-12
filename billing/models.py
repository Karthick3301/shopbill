from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Customer(models.Model):
    """Walk-in / regular shop customer."""

    name = models.CharField(max_length=200, db_index=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Invoice(models.Model):
    """A sale: header totals + items. Totals are computed server-side."""

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,  # keep sale history if customer still referenced
        related_name="invoices",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,  # keep invoice if the staff account is removed
        null=True,
        blank=True,
        related_name="invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)  # the "date" from the brief
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invoice #{self.pk} - {self.customer.name}"


class InvoiceItem(models.Model):
    """One line on an invoice."""

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        "inventory.Product",
        on_delete=models.PROTECT,  # sold products can never be removed
        related_name="invoice_items",
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
