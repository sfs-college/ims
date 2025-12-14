import logging
from django.conf import settings
from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)


def safe_send_mail(*, subject, message, recipient_list, from_email=None):
    """
    Production-safe email sender.
    - Never crashes request
    - Never blocks response
    - Tries Celery first
    - Falls back to direct SMTP
    """

    from_email = from_email or settings.DEFAULT_FROM_EMAIL

    # 1️⃣ Try Celery (NON-BLOCKING)
    try:
        from inventory.tasks import send_email_task
        send_email_task.delay(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
        )
        return True
    except Exception as celery_err:
        logger.warning(
            f"[safe_send_mail] Celery unavailable, falling back to SMTP: {celery_err}"
        )

    # 2️⃣ Fallback to direct SMTP (still safe)
    try:
        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=from_email,
            to=recipient_list,
        )
        email.send(fail_silently=True)
        return True
    except Exception as smtp_err:
        logger.error(f"[safe_send_mail] SMTP failed: {smtp_err}")
        return False
