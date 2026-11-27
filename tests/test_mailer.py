import smtplib
import unittest
from unittest.mock import patch

from secret_santa.mailer import Contact, Mailer, MailerSettings

SETTINGS = MailerSettings("smtp.example.com", 465, "login", "password")
SENDER = Contact("Santa", "santa@example.com")


@patch("secret_santa.mailer.smtplib.SMTP_SSL")
class TestMailer(unittest.TestCase):

    def test_single_connection_and_login_for_many_emails(self, smtp_ssl):
        with Mailer(SETTINGS) as mailer:
            for name in "ABC":
                mailer.send_email(Contact(name, f"{name}@example.com"), SENDER, "Subject", "Body")

        smtp_ssl.assert_called_once()
        smtp = smtp_ssl.return_value
        smtp.login.assert_called_once_with("login", "password")
        self.assertEqual(smtp.send_message.call_count, 3)
        smtp.quit.assert_called_once()

    def test_certificate_is_verified(self, smtp_ssl):
        with Mailer(SETTINGS):
            pass
        context = smtp_ssl.call_args.kwargs["context"]
        self.assertTrue(context.check_hostname)

    def test_login_failure_raises_before_sending(self, smtp_ssl):
        smtp = smtp_ssl.return_value
        smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad credentials")
        with self.assertRaises(smtplib.SMTPAuthenticationError):
            with Mailer(SETTINGS):
                self.fail("body must not run when login fails")
        smtp.send_message.assert_not_called()
        smtp.close.assert_called_once()

    def test_no_login_without_credentials(self, smtp_ssl):
        with Mailer(MailerSettings("smtp.example.com", 465, None, None)):
            pass
        smtp_ssl.return_value.login.assert_not_called()

    def test_send_outside_context_manager_raises(self, smtp_ssl):
        with self.assertRaises(RuntimeError):
            Mailer(SETTINGS).send_email(Contact("A", "a@example.com"), SENDER, "Subject", "Body")


if __name__ == '__main__':
    unittest.main()
