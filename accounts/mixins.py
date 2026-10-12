"""Reusable role checks for class-based views (Stage 1).

Owner = full access. Staff = billing + view products only.
Later stages use these mixins on inventory/billing/reports views.
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class OwnerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Allow only logged-in Owners."""

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.role == user.Roles.OWNER


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Allow only logged-in users whose role is in `allowed_roles`."""

    allowed_roles = ()

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.role in self.allowed_roles
