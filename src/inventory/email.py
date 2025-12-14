# inventory/email.py

import logging
import threading

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _send_mail_smtp(subject, message, recipient_list, **kwargs):
    """
    Low-level SMTP sender.
    Runs ONLY in background thread.
    """
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=True,
        )
    except Exception as e:
        logger.error(f"[safe_send_mail] SMTP failed: {e}")


def safe_send_mail(subject, message, recipient_list, **kwargs):
    """
    Production-safe email sender.
    - NEVER blocks request
    - NEVER crashes worker
    - Works even if Redis/Celery/SMTP is flaky
    """

    try:
        # Run SMTP in background thread
        thread = threading.Thread(
            target=_send_mail_smtp,
            kwargs={
                "subject": subject,
                "message": message,
                "recipient_list": recipient_list,
            },
            daemon=True,
        )
        thread.start()

    except Exception as e:
        logger.error(f"[safe_send_mail] Unexpected error: {e}")
