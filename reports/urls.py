"""Reports URLs: Owner-only dashboard + CSV export (Stage 4)."""

from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("sales.csv", views.SalesCsvView.as_view(), name="sales-csv"),
]
