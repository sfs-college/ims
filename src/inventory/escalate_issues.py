from django.core.management.base import BaseCommand
from django.utils import timezone
from inventory.models import Issue

class Command(BaseCommand):
    help = "Escalate issues whose TAT has expired"

    def handle(self, *args, **kwargs):
        now = timezone.now()

        issues = Issue.objects.filter(
            tat_deadline__lt=now,
            resolved=False,
            status__in=["open", "in_progress", "escalated"]
        )

        count = 0
        for issue in issues:
            result = issue.escalate()
            if result.get("escalated"):
                count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Escalated {count} issue(s)")
        )
