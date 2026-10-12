from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from accounts.mixins import OwnerRequiredMixin, RoleRequiredMixin
from accounts.models import User
from inventory.models import Product

from .forms import CustomerForm, InvoiceForm
from .models import Customer, Invoice
from .pdf import render_invoice_pdf
from .services import create_invoice

# Owner = full access; Staff = billing + view products. Customers: both
# roles may create/edit (shop counter workflow); delete stays Owner-only.
BILLING_ROLES = (User.Roles.OWNER, User.Roles.STAFF)


class CustomerListView(RoleRequiredMixin, ListView):
    model = Customer
    template_name = "billing/customer_list.html"
    allowed_roles = BILLING_ROLES
    paginate_by = 25
    ordering = ["name"]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(name__icontains=q)
        return qs


class CustomerCreateView(RoleRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = "billing/customer_form.html"
    allowed_roles = BILLING_ROLES
    success_url = reverse_lazy("billing:customer-list")


class CustomerUpdateView(RoleRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = "billing/customer_form.html"
    allowed_roles = BILLING_ROLES
    success_url = reverse_lazy("billing:customer-list")


class CustomerDeleteView(OwnerRequiredMixin, DeleteView):
    model = Customer
    template_name = "billing/customer_confirm_delete.html"
    success_url = reverse_lazy("billing:customer-list")

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except ProtectedError:
            messages.error(request, "Cannot delete: this customer has invoices.")
            return redirect("billing:customer-list")


class InvoiceListView(RoleRequiredMixin, ListView):
    model = Invoice
    template_name = "billing/invoice_list.html"
    allowed_roles = BILLING_ROLES
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset().select_related("customer", "created_by")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(customer__name__icontains=q)
        return qs


class InvoiceDetailView(RoleRequiredMixin, DetailView):
    model = Invoice
    template_name = "billing/invoice_detail.html"
    allowed_roles = BILLING_ROLES

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("customer", "created_by")
            .prefetch_related("items__product")
        )


class InvoiceCreateView(RoleRequiredMixin, CreateView):
    """Invoice page with a vanilla-JS live cart (see invoice_form.html)."""

    model = Invoice
    form_class = InvoiceForm
    template_name = "billing/invoice_form.html"
    allowed_roles = BILLING_ROLES

    def form_valid(self, form):
        try:
            self.object = create_invoice(
                created_by=self.request.user,
                customer=form.cleaned_data["customer"],
                lines=form.cleaned_data["items_json"],
                tax=form.cleaned_data.get("tax") or 0,
                discount=form.cleaned_data.get("discount") or 0,
            )
        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("billing:invoice-detail", args=[self.object.pk])


class ProductSearchView(RoleRequiredMixin, View):
    """JSON endpoint for the cart: only active products, max 10 rows."""

    allowed_roles = BILLING_ROLES

    def get(self, request):
        q = request.GET.get("q", "").strip()
        qs = Product.objects.active().select_related("category")
        if q:
            qs = qs.filter(name__icontains=q)
        rows = [
            {
                "id": p.pk,
                "name": p.name,
                "price": str(p.price),
                "stock": p.stock,
                "category": p.category.name,
            }
            for p in qs[:10]
        ]
        return JsonResponse({"results": rows})


class InvoicePdfView(RoleRequiredMixin, View):
    """Download the invoice as a PDF (ReportLab)."""

    allowed_roles = BILLING_ROLES

    def get(self, request, pk):
        invoice = (
            Invoice.objects.select_related("customer", "created_by")
            .prefetch_related("items__product")
            .get(pk=pk)
        )
        pdf_bytes = render_invoice_pdf(invoice)
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="invoice-{invoice.pk}.pdf"'
        return resp
