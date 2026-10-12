"""Project URL routes (Stage 1)."""

from django.contrib import admin
from django.urls import include, path

from accounts.views import HomeView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", HomeView.as_view(), name="home"),
    path("accounts/", include("accounts.urls")),
    path("inventory/", include("inventory.urls")),
    path("billing/", include("billing.urls")),
    path("reports/", include("reports.urls")),
]
