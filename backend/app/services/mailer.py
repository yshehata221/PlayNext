"""
Outgoing email.

Two modes, chosen by MAIL_MODE:
  console  - log the message and the link. Local development and CI, so the
             whole flow can be tested without a provider or a real inbox.
  smtp     - send for real via any SMTP provider (Resend, Brevo, Mailgun, or a
             Gmail app password).

Failures never propagate to the caller. A registration shouldn't fail because a
mail server is down - the account exists, and the link can be re-requested.
"""
import logging
import smtplib
from email.message import EmailMessage

from ..config import settings

log = logging.getLogger("uvicorn.error")


def _send_smtp(to: str, subject: str, text: str, html: str) -> None:
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)


def send(to: str, subject: str, text: str, html: str) -> bool:
    """Returns whether it was actually sent, for logging - not for the response."""
    if settings.mail_mode != "smtp" or not settings.smtp_host:
        log.info("[mail:console] to=%s subject=%r\n%s", to, subject, text)
        return False
    try:
        _send_smtp(to, subject, text, html)
        log.info("mail sent to %s (%s)", to, subject)
        return True
    except Exception as e:
        # the link can always be re-requested, so this is a warning not an error
        log.warning("mail to %s failed: %s", to, e)
        return False


def _shell(body: str) -> str:
    """Minimal inline-styled HTML: email clients ignore stylesheets."""
    return f"""\
<div style="font-family:system-ui,-apple-system,sans-serif;background:#0B141C;color:#E8EEF1;padding:32px">
  <div style="max-width:520px;margin:0 auto;background:#111F29;border-radius:16px;padding:32px">
    <p style="margin:0 0 24px;font-size:20px;font-weight:800">PlayNext</p>
    {body}
    <p style="margin:32px 0 0;font-size:12px;color:#8FA3AE">
      If you didn't expect this email you can ignore it.
    </p>
  </div>
</div>"""


def _button(url: str, label: str) -> str:
    return (f'<p style="margin:24px 0"><a href="{url}" '
            f'style="background:#F2B441;color:#0B141C;text-decoration:none;font-weight:700;'
            f'padding:12px 20px;border-radius:8px;display:inline-block">{label}</a></p>'
            f'<p style="margin:0;font-size:12px;color:#8FA3AE;word-break:break-all">{url}</p>')


def send_verification(to: str, name: str, url: str) -> bool:
    return send(
        to,
        "Confirm your PlayNext email",
        f"Hi {name},\n\nConfirm your email address to finish setting up PlayNext:\n{url}\n\n"
        f"The link works for {settings.verify_token_hours} hours.",
        _shell(f'<p style="margin:0;font-size:15px;line-height:1.6">Hi {name}, confirm your email address '
               f'to finish setting up your account.</p>{_button(url, "Confirm email")}'
               f'<p style="margin:16px 0 0;font-size:12px;color:#8FA3AE">'
               f'This link works for {settings.verify_token_hours} hours.</p>'),
    )


def send_password_reset(to: str, name: str, url: str) -> bool:
    return send(
        to,
        "Reset your PlayNext password",
        f"Hi {name},\n\nUse this link to choose a new password:\n{url}\n\n"
        f"It works for {settings.reset_token_hours} hour(s) and only once. "
        f"If you didn't ask for it, nothing has changed.",
        _shell(f'<p style="margin:0;font-size:15px;line-height:1.6">Hi {name}, use the button below to '
               f'choose a new password.</p>{_button(url, "Choose a new password")}'
               f'<p style="margin:16px 0 0;font-size:12px;color:#8FA3AE">'
               f'Works once, for {settings.reset_token_hours} hour(s). Your password hasn\'t changed yet.</p>'),
    )
