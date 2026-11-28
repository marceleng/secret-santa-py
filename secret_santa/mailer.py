from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import localtime
from email.headerregistry import Address


@dataclass
class Contact:
    name: str
    email: str


@dataclass
class MailerSettings:
    server_fqdn: str
    server_port: int
    login: str | None
    password: str | None

def _is_service_closing(e: smtplib.SMTPException) -> bool:
    if isinstance(e, smtplib.SMTPRecipientsRefused):
        return bool(e.recipients) and all(code == 421 for code, _ in e.recipients.values())
    return getattr(e, "smtp_code", None) == 421


@dataclass
class Mailer:
    """Sends emails over a single SMTP connection.

    Use as a context manager: connecting and logging in happen on entry, so
    network and authentication errors surface before any email is sent.
    """
    settings: MailerSettings
    _smtp: smtplib.SMTP_SSL | None = field(default=None, init=False, repr=False)

    def __enter__(self) -> "Mailer":
        self._smtp = self._connect()
        return self

    def _connect(self) -> smtplib.SMTP_SSL:
        # Without an explicit context, SMTP_SSL does not verify the server certificate.
        smtp = smtplib.SMTP_SSL(self.settings.server_fqdn, self.settings.server_port,
                                context=ssl.create_default_context())
        try:
            if self.settings.login:
                smtp.login(self.settings.login, self.settings.password)
        except BaseException:
            smtp.close()
            raise
        return smtp

    def __exit__(self, exc_type, exc, tb):
        smtp, self._smtp = self._smtp, None
        if smtp is None:
            return
        if exc_type is not None:
            # The connection may be dead: don't let a QUIT error hide the original one.
            smtp.close()
            return
        try:
            smtp.quit()
        except (smtplib.SMTPException, OSError):
            # Every email was already sent: a failed goodbye is harmless.
            smtp.close()

    @classmethod
    def __generate_msg(cls, dst: Contact, sender: Contact, subject: str, body: str) -> str:
        sender_username, sender_domain = sender.email.split('@')
        email = EmailMessage()
        email["Subject"] = subject
        email["Date"] = localtime()
        email["From"] = Address(sender.name, sender_username, sender_domain)
        email["To"] = f"{dst.name} <{dst.email}>"
        email.set_content(body)
        return email

    def send_email(self, dst: Contact, sender: Contact, subject: str, body: str):
        if self._smtp is None:
            raise RuntimeError("Mailer is not connected: use it as a context manager")
        msg = self.__generate_msg(dst, sender, subject, body)
        if self._smtp.sock is None:
            # smtplib closed the connection after a 421 on the previous email. A server-side
            # drop (e.g. idle timeout) leaves sock set: send_message then raises
            # SMTPServerDisconnected, which is not retried (the email may have gone out).
            self._reconnect()
        try:
            self._smtp.send_message(msg)
        except (smtplib.SMTPResponseException, smtplib.SMTPRecipientsRefused) as e:
            # 421 means the server refused this email and is closing the connection, so
            # it was not delivered: retrying once on a new connection cannot duplicate it.
            # Any other disconnection may happen after the server accepted the email,
            # so it is not retried.
            if not _is_service_closing(e):
                raise
            self._reconnect()
            self._smtp.send_message(msg)

    def _reconnect(self):
        self._smtp.close()
        self._smtp = self._connect()
