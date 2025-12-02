# ims/src/inventory/tasks.py
from celery import shared_task
from django.utils import timezone
from inventory.models import Issue

@shared_task
def escalate_expired_issues():
    """
    Escalates issues whose TAT has expired.
    """
    now = timezone.now()

    expired = Issue.objects.filter(
        tat_deadline__lt=now,
        escalation_level__lt=2  # 0 = room incharge, 1 = sub admin, 2 = central admin
    )

    count = expired.count()

    for issue in expired:
        try:
            result = issue.escalate()
            issue.save()
            print(f"Escalated {issue.ticket_id} → {result}")
        except Exception as e:
            print("Escalation error:", e)

    return f"Escalated {count} issues"
