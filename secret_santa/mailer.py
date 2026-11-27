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
    login: str
    password: str

@dataclass
class Mailer:
    """Sends emails over a single SMTP connection.

    Use as a context manager: connecting and logging in happen on entry, so
    network and authentication errors surface before any email is sent.
    """
    settings: MailerSettings
    _smtp: smtplib.SMTP_SSL | None = field(default=None, init=False, repr=False)

    def __enter__(self) -> "Mailer":
        # Without an explicit context, SMTP_SSL does not verify the server certificate.
        smtp = smtplib.SMTP_SSL(self.settings.server_fqdn, self.settings.server_port,
                                context=ssl.create_default_context())
        try:
            if self.settings.login:
                smtp.login(self.settings.login, self.settings.password)
        except BaseException:
            smtp.close()
            raise
        self._smtp = smtp
        return self

    def __exit__(self, *exc_info):
        smtp, self._smtp = self._smtp, None
        try:
            smtp.quit()
        except smtplib.SMTPException:
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
        self._smtp.send_message(msg)
