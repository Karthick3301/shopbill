from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Show the role field alongside the standard user fields."""

    list_display = ("username", "email", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + ((None, {"fields": ("role",)}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + ((None, {"fields": ("role",)}),)
