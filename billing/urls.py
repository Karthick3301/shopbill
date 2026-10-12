"""Billing URLs: customers, invoices, product search JSON, PDF (Stage 3)."""

from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("customers/", views.CustomerListView.as_view(), name="customer-list"),
    path("customers/add/", views.CustomerCreateView.as_view(), name="customer-add"),
    path("customers/<int:pk>/edit/", views.CustomerUpdateView.as_view(), name="customer-edit"),
    path(
        "customers/<int:pk>/delete/",
        views.CustomerDeleteView.as_view(),
        name="customer-delete",
    ),
    path("invoices/", views.InvoiceListView.as_view(), name="invoice-list"),
    path("invoices/create/", views.InvoiceCreateView.as_view(), name="invoice-create"),
    path("invoices/<int:pk>/", views.InvoiceDetailView.as_view(), name="invoice-detail"),
    path("invoices/<int:pk>/pdf/", views.InvoicePdfView.as_view(), name="invoice-pdf"),
    path("api/products/", views.ProductSearchView.as_view(), name="product-search"),
]
