"""Entrega SMTP de correos de cuenta."""
import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from flask import current_app

logger = logging.getLogger(__name__)


def send_email(to, subject, body, *, background=False):
    app = current_app
    if app.testing and not app.config.get("TEST_REAL_SMTP"):
        app.extensions.setdefault("mail_outbox", []).append({"to": to, "subject": subject, "body": body})
        return True

    cfg = app.config
    sender = cfg["SMTP_FROM"] or cfg["SMTP_USER"]
    if not cfg["SMTP_HOST"] or not sender or (cfg["SMTP_USER"] and not cfg["SMTP_PASSWORD"]):
        logger.warning("SMTP incompleto: revisa host, remitente y credenciales.")
        return False

    message = EmailMessage()
    message["From"] = formataddr((cfg["SMTP_FROM_NAME"], sender))
    message["To"] = to
    message["Subject"] = subject
    message["Message-ID"] = make_msgid(domain=sender.partition("@")[2] or None)
    message.set_content(body)

    settings = {key: cfg[key] for key in
                ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_SSL", "SMTP_STARTTLS")}
    if background:
        threading.Thread(target=_deliver, args=(message, settings), daemon=True).start()
        return True
    return _deliver(message, settings)


def _deliver(message, settings):
    context = ssl.create_default_context()
    try:
        if settings["SMTP_SSL"]:
            server = smtplib.SMTP_SSL(settings["SMTP_HOST"], settings["SMTP_PORT"], context=context, timeout=10)
        else:
            server = smtplib.SMTP(settings["SMTP_HOST"], settings["SMTP_PORT"], timeout=10)
        try:
            if not settings["SMTP_SSL"] and settings["SMTP_STARTTLS"]:
                server.starttls(context=context)
            if settings["SMTP_USER"]:
                server.login(settings["SMTP_USER"], settings["SMTP_PASSWORD"])
            server.send_message(message)
        finally:
            server.close()
        return True
    except (OSError, smtplib.SMTPException) as error:
        logger.warning("Entrega SMTP fallida (%s).", type(error).__name__)
        return False
