# ims/src/inventory/utils/email.py
from django.core.mail import send_mail
from django.conf import settings

def safe_send_mail(subject, message, from_email=None, recipient_list=None, fail_silently=True, **kwargs):
    """
    Safe wrapper around django.core.mail.send_mail.
    - Uses DEFAULT_FROM_EMAIL when from_email is None (if that setting exists).
    - Catches all exceptions and returns False on failure, True on success.
    - Does NOT raise exceptions (avoid crashing Gunicorn workers when SMTP fails).
    """
    if recipient_list is None:
        recipient_list = []
    if from_email is None:
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    try:
        send_mail(subject, message, from_email, recipient_list, fail_silently=fail_silently, **kwargs)
        return True
    except Exception as e:
        # Print to stdout so host logs pick it up (prevents worker exit).
        try:
            print(f"[safe_send_mail] Failed to send email: {e}", flush=True)
        except Exception:
            pass
        return False
