from django.db.models import Count, F, Sum
from django.utils import timezone
from django.views.generic import TemplateView

from billing.models import Invoice
from inventory.models import Product


class HomeView(TemplateView):
    """Landing page after login; links vary by role in the template."""

    template_name = "home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        # Owner-only shop snapshot, reusing the reports dashboard queries.
        # Staff/anonymous get no sales figures in the context at all.
        if user.is_authenticated and getattr(user, "is_owner", False):
            today = timezone.localdate()
            month_start = today.replace(day=1)
            today_agg = Invoice.objects.filter(created_at__date=today).aggregate(
                total=Sum("total"), count=Count("pk")
            )
            month_agg = Invoice.objects.filter(
                created_at__date__gte=month_start
            ).aggregate(total=Sum("total"))
            ctx["today_total"] = today_agg["total"] or 0
            ctx["today_count"] = today_agg["count"] or 0
            ctx["month_total"] = month_agg["total"] or 0
            ctx["low_stock_count"] = (
                Product.objects.active()
                .filter(stock__lte=F("low_stock_limit"))
                .count()
            )
        return ctx
