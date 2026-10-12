from django.views.generic import TemplateView


class HomeView(TemplateView):
    """Landing page after login; links vary by role in the template."""

    template_name = "home.html"
