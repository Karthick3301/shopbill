"""Inventory URLs: categories and products CRUD (Stage 2)."""

from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("categories/", views.CategoryListView.as_view(), name="category-list"),
    path("categories/add/", views.CategoryCreateView.as_view(), name="category-add"),
    path("categories/<int:pk>/edit/", views.CategoryUpdateView.as_view(), name="category-edit"),
    path(
        "categories/<int:pk>/delete/",
        views.CategoryDeleteView.as_view(),
        name="category-delete",
    ),
    path("products/", views.ProductListView.as_view(), name="product-list"),
    path("products/add/", views.ProductCreateView.as_view(), name="product-add"),
    path("products/<int:pk>/edit/", views.ProductUpdateView.as_view(), name="product-edit"),
    path(
        "products/<int:pk>/delete/",
        views.ProductDeleteView.as_view(),
        name="product-delete",
    ),
]
