from django.contrib import admin

from .models import Customer, Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email")
    search_fields = ("name", "phone", "email")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("pk", "customer", "created_by", "total", "created_at")
    list_filter = ("created_at",)
    search_fields = ("customer__name",)
    inlines = [InvoiceItemInline]
