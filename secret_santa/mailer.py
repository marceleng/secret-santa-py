import smtplib
from dataclasses import dataclass
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
    settings: MailerSettings

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
        smtp_server = smtplib.SMTP_SSL(self.settings.server_fqdn, self.settings.server_port)
        smtp_server.ehlo()
        #smtp_server.starttls()
        #print("SSL started")
        #smtp_server.ehlo()
        #print("Ehlo again")
        if self.settings.login:
            smtp_server.login(self.settings.login, self.settings.password)

        msg = self.__generate_msg(dst, sender, subject, body)
        smtp_server.send_message(msg)
        smtp_server.quit()
