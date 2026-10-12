from django.contrib import messages
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from accounts.mixins import OwnerRequiredMixin, RoleRequiredMixin
from accounts.models import User

from .forms import CategoryForm, ProductForm
from .models import Category, Product

# Both roles may view lists; only Owners may mutate (Staff = view only).
VIEWER_ROLES = (User.Roles.OWNER, User.Roles.STAFF)


class CategoryListView(RoleRequiredMixin, ListView):
    """Category list with name search."""

    model = Category
    template_name = "inventory/category_list.html"
    allowed_roles = VIEWER_ROLES
    paginate_by = 25
    ordering = ["name"]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(name__icontains=q)
        # Show active product counts; inactive rows stay hidden from lists.
        return qs.annotate(active_count=Count("products", filter=Q(products__is_active=True)))


class CategoryCreateView(OwnerRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "inventory/category_form.html"
    success_url = reverse_lazy("inventory:category-list")


class CategoryUpdateView(OwnerRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "inventory/category_form.html"
    success_url = reverse_lazy("inventory:category-list")


class CategoryDeleteView(OwnerRequiredMixin, DeleteView):
    model = Category
    template_name = "inventory/category_confirm_delete.html"
    success_url = reverse_lazy("inventory:category-list")

    def post(self, request, *args, **kwargs):
        """Block deleting categories that still have products (PROTECT)."""
        try:
            return super().post(request, *args, **kwargs)
        except ProtectedError:
            messages.error(request, "Cannot delete: products still use this category.")
            return redirect("inventory:category-list")


class ProductListView(RoleRequiredMixin, ListView):
    """Product list with name search + category filter; highlights low stock."""

    model = Product
    template_name = "inventory/product_list.html"
    allowed_roles = VIEWER_ROLES
    paginate_by = 25

    def get_queryset(self):
        # Hide deactivated products from the list (history rows are kept).
        # Billing product search must use this same filter: Product.objects.active().
        qs = super().get_queryset().select_related("category").filter(is_active=True)
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(name__icontains=q)
        category_id = self.request.GET.get("category", "").strip()
        if category_id:
            qs = qs.filter(category_id=category_id)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Category dropdown for the filter; echo current filters back to the form.
        ctx["categories"] = Category.objects.all()
        ctx["q"] = self.request.GET.get("q", "")
        ctx["selected_category"] = self.request.GET.get("category", "")
        return ctx


class ProductCreateView(OwnerRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "inventory/product_form.html"
    success_url = reverse_lazy("inventory:product-list")


class ProductUpdateView(OwnerRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "inventory/product_form.html"
    success_url = reverse_lazy("inventory:product-list")


class ProductDeleteView(OwnerRequiredMixin, DeleteView):
    """Soft delete: set is_active=False so history (StockMovement) is kept."""

    model = Product
    template_name = "inventory/product_confirm_delete.html"
    success_url = reverse_lazy("inventory:product-list")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Deactivating never changes stock, so save() logs no movement.
        self.object.is_active = False
        self.object.save(update_fields=["is_active", "updated_at"])
        return redirect(self.get_success_url())
