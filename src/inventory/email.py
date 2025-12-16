import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

MAILJET_SEND_URL = "https://api.mailjet.com/v3.1/send"


def safe_send_mail(
    *,
    subject,
    message,
    recipient_list,
    from_email=None,
    fail_silently=True,
):
    """
    Production-safe email sender.
    - Uses Mailjet REST API (Railway-safe)
    - Keyword-only arguments enforced
    - Never crashes app
    """

    api_key = getattr(settings, "EMAIL_HOST_USER", None)
    api_secret = getattr(settings, "EMAIL_HOST_PASSWORD", None)
    sender_email = from_email or getattr(settings, "DEFAULT_FROM_EMAIL", None)

    if not api_key or not api_secret or not sender_email:
        logger.error("[safe_send_mail] Missing Mailjet credentials")
        return False

    if not recipient_list:
        logger.warning("[safe_send_mail] Empty recipient list")
        return False

    payload = {
        "Messages": [
            {
                "From": {
                    "Email": sender_email,
                    "Name": "Blixtro IMS",
                },
                "To": [{"Email": r} for r in recipient_list],
                "Subject": subject,
                "TextPart": message,
            }
        ]
    }

    try:
        response = requests.post(
            MAILJET_SEND_URL,
            auth=(api_key, api_secret),
            json=payload,
            timeout=10,
        )

        if response.status_code not in (200, 201):
            logger.error(
                "[safe_send_mail] Mailjet error %s → %s",
                response.status_code,
                response.text,
            )
            return False

        logger.info("[safe_send_mail] Email sent successfully")
        return True

    except Exception as e:
        logger.exception("[safe_send_mail] Unexpected failure")
        if not fail_silently:
            raise
        return False
