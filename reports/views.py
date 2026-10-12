"""Owner-only reports: dashboard aggregates + sales CSV export."""

import calendar
import csv
from datetime import date

from django.db.models import Count, F, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from accounts.mixins import OwnerRequiredMixin
from billing.models import Invoice, InvoiceItem
from inventory.models import Product


def _month_starts(today, n):
    """First days of the last n calendar months, oldest first (e.g. 6)."""
    starts = []
    y, m = today.year, today.month
    for _ in range(n):
        starts.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return starts[::-1]


class DashboardView(OwnerRequiredMixin, TemplateView):
    """Sales overview. All numbers come from ORM aggregation, not loops."""

    template_name = "reports/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        month_start = today.replace(day=1)

        today_agg = Invoice.objects.filter(created_at__date=today).aggregate(
            total=Sum("total"), count=Count("pk")
        )
        ctx["today_total"] = today_agg["total"] or 0
        ctx["today_count"] = today_agg["count"] or 0
        month_agg = Invoice.objects.filter(created_at__date__gte=month_start).aggregate(
            total=Sum("total")
        )
        ctx["month_total"] = month_agg["total"] or 0

        # Daily sales for the current month (ORM groups; Python only zero-fills).
        daily = {
            row["day"]: row["total"]
            for row in Invoice.objects.filter(created_at__date__gte=month_start)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Sum("total"))
        }
        days_in_month = calendar.monthrange(today.year, today.month)[1]
        ctx["daily_labels"] = [f"{today.year}-{today.month:02d}-{d:02d}" for d in range(1, days_in_month + 1)]
        ctx["daily_data"] = [float(daily.get(date(today.year, today.month, d)) or 0) for d in range(1, days_in_month + 1)]

        # Monthly sales for the last 6 calendar months.
        starts = _month_starts(today, 6)
        monthly = {
            row["month"]: row["total"]
            for row in Invoice.objects.filter(created_at__date__gte=starts[0])
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(total=Sum("total"))
        }
        ctx["monthly_labels"] = [s.strftime("%b %Y") for s in starts]
        # TruncMonth returns datetime; match keys by year/month.
        by_ym = {(k.year, k.month): v for k, v in monthly.items()}
        ctx["monthly_data"] = [float(by_ym.get((s.year, s.month)) or 0) for s in starts]

        # Top 5 products by quantity sold.
        ctx["top_products"] = list(
            InvoiceItem.objects.values("product__name")
            .annotate(qty=Sum("quantity"))
            .order_by("-qty")[:5]
        )

        # Active products at or below their low-stock limit.
        ctx["low_stock"] = list(
            Product.objects.active()
            .filter(stock__lte=F("low_stock_limit"))
            .select_related("category")
            .order_by("stock", "name")[:50]
        )
        return ctx


def _csv_safe(value):
    """Prefix spreadsheet-formula triggers so exports can't inject formulas."""
    s = "" if value is None else str(value)
    if s[:1] in ("=", "+", "-", "@"):
        return "'" + s
    return s


class SalesCsvView(OwnerRequiredMixin, View):
    """One row per invoice: number, date, customer, subtotal, discount, tax, total."""

    def get(self, request):
        qs = Invoice.objects.select_related("customer").order_by("pk")
        # Optional ?from=YYYY-MM-DD&to=YYYY-MM-DD filter on the invoice date.
        try:
            if request.GET.get("from"):
                qs = qs.filter(created_at__date__gte=date.fromisoformat(request.GET["from"]))
            if request.GET.get("to"):
                qs = qs.filter(created_at__date__lte=date.fromisoformat(request.GET["to"]))
        except ValueError:
            pass  # ignore malformed dates, export unfiltered

        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="sales.csv"'
        writer = csv.writer(resp)
        writer.writerow(["invoice", "date", "customer", "subtotal", "discount", "tax", "total"])
        for inv in qs:
            local = timezone.localtime(inv.created_at)
            writer.writerow(
                [
                    _csv_safe(inv.pk),
                    _csv_safe(local.strftime("%Y-%m-%d %H:%M")),
                    _csv_safe(inv.customer.name),
                    _csv_safe(f"{inv.subtotal:.2f}"),
                    _csv_safe(f"{inv.discount:.2f}"),
                    _csv_safe(f"{inv.tax:.2f}"),
                    _csv_safe(f"{inv.total:.2f}"),
                ]
            )
        return resp
