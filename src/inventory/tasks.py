from django.utils import timezone
from inventory.models import Issue
from django.core.mail import EmailMultiAlternatives, get_connection
from django.conf import settings
import logging
import smtplib
import socket

logger = logging.getLogger(__name__)


def send_email_async(subject, plain_body, html_body, from_email, to_emails, max_retries=3):
    """
    Celery task to send email asynchronously with retry logic.
    Falls back to file-based backend if SMTP fails.
    """
    for attempt in range(max_retries):
        try:
            connection = get_connection(
                timeout=30,
                fail_silently=False
            )
            
            msg = EmailMultiAlternatives(
                subject=subject,
                body=plain_body,
                from_email=from_email,
                to=to_emails,
                connection=connection,
            )
            msg.attach_alternative(html_body, 'text/html')
            msg.send()
            connection.close()
            
            logger.info(f"Email sent successfully to {to_emails}")
            return {'success': True, 'message': 'Email sent'}
            
        except (smtplib.SMTPException, socket.timeout, TimeoutError, OSError) as e:
            logger.warning(f"Email attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(2 ** attempt)
            else:
                # All retries failed - try file-based backend as last resort
                try:
                    from django.core.mail import get_connection
                    file_connection = get_connection(
                        backend='django.core.mail.backends.filebased.EmailBackend',
                        file_path=settings.EMAIL_FILE_PATH
                    )
                    msg = EmailMultiAlternatives(
                        subject=subject,
                        body=plain_body,
                        from_email=from_email,
                        to=to_emails,
                        connection=file_connection,
                    )
                    msg.attach_alternative(html_body, 'text/html')
                    msg.send()
                    logger.info(f"Email saved to file for {to_emails}")
                    return {'success': True, 'message': 'Email queued to file'}
                except Exception as file_err:
                    logger.error(f"Failed to save email to file: {file_err}")
                    return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected email error: {e}")
            return {'success': False, 'error': str(e)}


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
