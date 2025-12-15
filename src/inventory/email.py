import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

def safe_send_mail(*, subject, message, recipient_list):
    """
    Production-safe email sender.
    - No Celery
    - No Redis
    - No crash on SMTP failure
    """

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        logger.info("Email sent to %s", recipient_list)

    except Exception as e:
        # Never crash request
        logger.exception("Email failed but app continues: %s", e)
