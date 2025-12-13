import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def safe_send_mail(*, subject, message, recipient_list, from_email=None):
    """
    Production-safe email trigger.
    - Never blocks request
    - Never crashes Gunicorn
    - Emails still send via Celery when Redis is available
    """

    if not recipient_list:
        return

    try:
        from inventory.tasks import send_email_task

        # IMPORTANT:
        # apply_async + ignore_result prevents backend blocking
        send_email_task.apply_async(
            kwargs={
                "subject": subject,
                "message": message,
                "recipient_list": recipient_list,
                "from_email": from_email or settings.DEFAULT_FROM_EMAIL,
            },
            ignore_result=True,
        )

    except Exception as exc:
        # Do NOT crash request
        logger.error(
            "[safe_send_mail] Celery/Redis unavailable: %s",
            exc,
            exc_info=True,
        )
