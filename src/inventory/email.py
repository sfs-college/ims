import logging
import socket
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _redis_available(host: str, port: int, timeout=0.3) -> bool:
    """Fast, non-blocking Redis DNS + TCP check"""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except Exception:
        return False


def safe_send_mail(*, subject, message, recipient_list, from_email=None):
    """
    ABSOLUTELY SAFE email sender.
    - Never blocks request
    - Never crashes Gunicorn
    - Uses Celery ONLY if Redis is reachable
    - Falls back to SMTP otherwise
    """

    if not recipient_list:
        return

    from_email = from_email or settings.DEFAULT_FROM_EMAIL

    redis_host = getattr(settings, "REDIS_HOST", "redis")
    redis_port = int(getattr(settings, "REDIS_PORT", 6379))

    # 1️⃣ Try Celery ONLY if Redis is reachable
    if _redis_available(redis_host, redis_port):
        try:
            from inventory.tasks import send_email_task

            send_email_task.delay(
                subject=subject,
                message=message,
                recipient_list=recipient_list,
                from_email=from_email,
            )
            return

        except Exception as exc:
            logger.warning(
                "[safe_send_mail] Celery failed, falling back to SMTP: %s",
                exc,
                exc_info=True,
            )

    # 2️⃣ SMTP fallback (never crashes)
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=True,
        )
    except Exception as exc:
        logger.error(
            "[safe_send_mail] SMTP fallback failed: %s",
            exc,
            exc_info=True,
        )
