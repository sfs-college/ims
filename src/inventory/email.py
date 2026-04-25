import requests
from django.conf import settings
import logging
from django.utils.html import escape

logger = logging.getLogger(__name__)

MAILJET_SEND_URL = "https://api.mailjet.com/v3.1/send"


def safe_send_mail(
    *,
    subject,
    message,
    recipient_list,
    from_email=None,
    html_message=None,
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
                **({"HTMLPart": html_message} if html_message else {}),
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


def build_email_shell(*, title, intro_html, accent="#4f46e5", sections=None, outro_html=""):
    rendered_sections = []
    for section in sections or []:
        section_title = section.get("title")
        rows = section.get("rows") or []
        body_html = section.get("body_html", "")

        rows_html = ""
        if rows:
            rows_html = "".join(
                (
                    '<tr>'
                    f'<td style="padding:10px 0;color:#64748b;font-size:13px;vertical-align:top;">{escape(row["label"])}</td>'
                    f'<td style="padding:10px 0;color:#0f172a;font-size:13px;font-weight:600;vertical-align:top;">{escape(row["value"])}</td>'
                    "</tr>"
                )
                for row in rows
            )
            rows_html = (
                '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
                'style="border-collapse:collapse;">'
                f"{rows_html}"
                "</table>"
            )

        rendered_sections.append(
            '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:16px;'
            'padding:18px 20px;margin-top:16px;">'
            + (
                f'<div style="font-size:12px;font-weight:800;letter-spacing:0.08em;'
                f'text-transform:uppercase;color:{accent};margin-bottom:12px;">{section_title}</div>'
                if section_title else ""
            )
            + rows_html
            + body_html
            + "</div>"
        )

    return f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:24px;background:#eef2ff;font-family:Arial,sans-serif;color:#0f172a;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:720px;margin:0 auto;background:#ffffff;border-radius:24px;overflow:hidden;border:1px solid #dbe4ff;">
    <tr>
      <td style="padding:28px 32px;background:linear-gradient(135deg,{accent},#0f172a);color:#ffffff;">
        <div style="font-size:12px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;opacity:0.85;">Blixtro IMS</div>
        <div style="font-size:28px;line-height:1.2;font-weight:800;margin-top:8px;">{title}</div>
      </td>
    </tr>
    <tr>
      <td style="padding:28px 32px;">
        <div style="font-size:15px;line-height:1.7;color:#334155;">{intro_html}</div>
        {''.join(rendered_sections)}
        <div style="font-size:13px;line-height:1.7;color:#64748b;margin-top:20px;">{outro_html}</div>
      </td>
    </tr>
  </table>
</body>
</html>
""".strip()
