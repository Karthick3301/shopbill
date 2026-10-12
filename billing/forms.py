"""Django forms for billing (used by the CBVs)."""

import json
from decimal import Decimal, InvalidOperation

from django import forms

from .models import Customer, Invoice


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "phone", "email", "address"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "address": forms.TextInput(attrs={"class": "form-control"}),
        }


class InvoiceForm(forms.ModelForm):
    """Header form; cart lines arrive as JSON from the vanilla-JS cart."""

    items_json = forms.CharField(widget=forms.HiddenInput())

    class Meta:
        model = Invoice
        fields = ["customer", "tax", "discount"]
        widgets = {
            "customer": forms.Select(attrs={"class": "form-select"}),
            "tax": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "discount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
        }

    def clean_tax(self):
        tax = self.cleaned_data.get("tax") or Decimal("0")
        if tax < 0:
            raise forms.ValidationError("Tax cannot be negative.")
        return tax

    def clean_discount(self):
        discount = self.cleaned_data.get("discount") or Decimal("0")
        if discount < 0:
            raise forms.ValidationError("Discount cannot be negative.")
        return discount

    def clean_items_json(self):
        """Parse the cart JSON into a validated lines list for the service."""
        raw = self.cleaned_data.get("items_json") or "[]"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid cart data.")
        if not isinstance(data, list) or not data:
            raise forms.ValidationError("Add at least one item to the invoice.")
        lines = []
        for row in data:
            if not isinstance(row, dict):
                raise forms.ValidationError("Invalid cart data.")
            try:
                pid = int(row.get("product_id"))
                qty = int(row.get("quantity"))
            except (TypeError, ValueError):
                raise forms.ValidationError("Invalid product or quantity.")
            if qty < 1:
                raise forms.ValidationError("Quantity must be at least 1.")
            unit_price = row.get("unit_price")
            if unit_price not in (None, ""):
                try:
                    unit_price = Decimal(str(unit_price))
                except InvalidOperation:
                    raise forms.ValidationError("Invalid unit price.")
                if unit_price < 0:
                    raise forms.ValidationError("Unit price cannot be negative.")
            else:
                unit_price = None
            lines.append({"product_id": pid, "quantity": qty, "unit_price": unit_price})
        return lines
