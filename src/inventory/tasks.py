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
    retry_backoff=5,
    retry_kwargs={"max_retries": 3},
)
def send_email_task(self, subject, message, recipient_list, from_email=None):
    send_mail(
        subject=subject,
        message=message,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_list,
        fail_silently=False,
    )


# ============================================================
# ISSUE ESCALATION TASK (UNCHANGED)
# ============================================================
@shared_task
def escalate_expired_issues():
    now = timezone.now()

    expired_issues = Issue.objects.filter(
        tat_deadline__lt=now,
        escalation_level__lt=2,
    )

    count = expired_issues.count()

    for issue in expired_issues:
        try:
            issue.escalate()
            issue.save(update_fields=["escalation_level", "status", "updated_on"])
            logger.info("Escalated %s", issue.ticket_id)
        except Exception:
            logger.exception("Escalation failed for %s", issue.ticket_id)

    return f"Escalated {count} issues"
