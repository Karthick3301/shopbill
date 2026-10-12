from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user with a simple Owner/Staff role flag."""

    class Roles(models.TextChoices):
        OWNER = "OWNER", "Owner"  # full access
        STAFF = "STAFF", "Staff"  # billing + view products only

    # Default to STAFF so new users get the least privilege.
    role = models.CharField(
        max_length=10,
        choices=Roles.choices,
        default=Roles.STAFF,
    )

    @property
    def is_owner(self):
        """Template-friendly check: True when this user is an Owner."""
        return self.role == self.Roles.OWNER
