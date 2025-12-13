from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
import logging

from inventory.models import Issue

logger = logging.getLogger(__name__)


# ============================================================
# EMAIL TASK (PRODUCTION SAFE)
# ============================================================
@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 5, "countdown": 30},
    retry_backoff=True
)
def send_email_task(self, subject, message, from_email, recipient_list):
    """
    Sends email asynchronously via Celery.

    - NEVER runs inside HTTP request
    - Retries automatically
    - Safe for production
    """
    send_mail(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=recipient_list,
        fail_silently=False,
    )


# ============================================================
# ISSUE ESCALATION TASK (YOUR EXISTING LOGIC, CLEANED)
# ============================================================
@shared_task
def escalate_expired_issues():
    """
    Escalates issues whose TAT has expired.
    Runs safely in background.
    """
    now = timezone.now()

    expired_issues = Issue.objects.filter(
        tat_deadline__lt=now,
        escalation_level__lt=2  # 0 = room incharge, 1 = sub admin, 2 = central admin
    )

    count = expired_issues.count()

    for issue in expired_issues:
        try:
            result = issue.escalate()
            issue.save(update_fields=["escalation_level", "status", "updated_on"])
            logger.info("Escalated %s → %s", issue.ticket_id, result)
        except Exception as e:
            logger.exception("Escalation failed for %s: %s", issue.ticket_id, e)

    return f"Escalated {count} issues"
