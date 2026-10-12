from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
    """Product grouping (e.g. Snacks, Drinks)."""

    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    """Reusable filters for products."""

    def active(self):
        """Only products visible in lists and billing search."""
        return self.filter(is_active=True)


class Product(models.Model):
    """Sellable item with price and stock level."""

    name = models.CharField(max_length=200, db_index=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,  # keep products from becoming orphaned
        related_name="products",
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    stock = models.PositiveIntegerField(default=0)
    low_stock_limit = models.PositiveIntegerField(default=5)
    # Soft delete flag: deactivated products stay in the DB (history kept)
    # but are hidden from lists and billing search.
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_low_stock(self):
        """Used by the list template to highlight rows needing restock."""
        return self.stock <= self.low_stock_limit

    def save(self, *args, **kwargs):
        """Log every stock change as a StockMovement (model-level guarantee)."""
        old_stock = None
        is_new = self._state.adding
        if not is_new:
            # Remember stock before saving so we can log the delta after.
            old_stock = (
                Product.objects.filter(pk=self.pk).values_list("stock", flat=True).first()
            )
        super().save(*args, **kwargs)
        if is_new:
            if self.stock:
                StockMovement.objects.create(
                    product=self,
                    change=self.stock,
                    reason=StockMovement.Reasons.INITIAL,
                )
        elif old_stock is not None and old_stock != self.stock:
            StockMovement.objects.create(
                product=self,
                change=self.stock - old_stock,
                reason=StockMovement.Reasons.ADJUSTMENT,
            )


class StockMovement(models.Model):
    """Audit log: one row per stock change (sale/restock/adjustment)."""

    class Reasons(models.TextChoices):
        INITIAL = "INITIAL", "Initial stock"
        ADJUSTMENT = "ADJUSTMENT", "Manual adjustment"
        SALE = "SALE", "Sale"  # used by the billing stage
        RESTOCK = "RESTOCK", "Restock"  # used by the billing stage

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="movements"
    )
    change = models.IntegerField()  # negative = stock out, positive = stock in
    reason = models.CharField(max_length=20, choices=Reasons.choices)
    created_at = models.DateTimeField(auto_now_add=True)  # the "date" from the brief

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        sign = "+" if self.change >= 0 else ""
        return f"{self.product.name}: {sign}{self.change} ({self.reason})"
