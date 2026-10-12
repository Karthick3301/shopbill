"""Create demo users: owner/demo123 (Owner) and staff/demo123 (Staff)."""

from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = "Create demo Owner and Staff users (idempotent)."

    def handle(self, *args, **options):
        # Owner gets admin access so they can manage everything.
        owner, created = User.objects.get_or_create(
            username="owner",
            defaults={"role": User.Roles.OWNER, "is_staff": True, "is_superuser": True},
        )
        owner.role = User.Roles.OWNER
        owner.is_staff = True
        owner.is_superuser = True
        owner.set_password("demo123")
        owner.save()
        self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} owner/demo123"))

        # Staff is a plain user: billing + view products only (no admin).
        staff, created = User.objects.get_or_create(
            username="staff",
            defaults={"role": User.Roles.STAFF, "is_staff": False, "is_superuser": False},
        )
        staff.role = User.Roles.STAFF
        staff.is_staff = False
        staff.is_superuser = False
        staff.set_password("demo123")
        staff.save()
        self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} staff/demo123"))
