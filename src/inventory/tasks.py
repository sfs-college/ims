from django.utils import timezone
from inventory.models import Issue
import logging

logger = logging.getLogger(__name__)

def escalate_expired_issues():
    """
    Escalates issues whose TAT has expired.
    Runs via cron or management command.
    """
    now = timezone.now()

    issues = Issue.objects.filter(
        tat_deadline__lt=now,
        escalation_level__lt=2,
        status__in=["open", "in_progress"]
    )

    for issue in issues:
        try:
            issue.escalation_level += 1
            issue.status = "escalated"
            issue.save(update_fields=["escalation_level", "status", "updated_on"])
            logger.info("Escalated issue %s", issue.ticket_id)
        except Exception:
            logger.exception("Failed escalation for %s", issue.ticket_id)
