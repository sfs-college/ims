from django.conf import settings
from inventory.tasks import send_email_task


def safe_send_mail(subject, message, from_email=None, recipient_list=None, **kwargs):
    """
    Enqueue email to Celery.
    NEVER sends synchronously.
    """
    if not recipient_list:
        return

    if from_email is None:
        from_email = settings.DEFAULT_FROM_EMAIL

    send_email_task.delay(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=recipient_list,
    )
