import smtplib
import unittest
import unittest.mock
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

    def test_quit_socket_error_after_all_sent_is_swallowed(self, smtp_ssl):
        smtp = smtp_ssl.return_value
        smtp.quit.side_effect = ConnectionResetError()
        with Mailer(SETTINGS) as mailer:
            mailer.send_email(Contact("A", "a@example.com"), SENDER, "Subject", "Body")
        smtp.close.assert_called_once()

    def test_original_error_is_not_hidden_by_quit(self, smtp_ssl):
        smtp = smtp_ssl.return_value
        smtp.send_message.side_effect = smtplib.SMTPServerDisconnected("gone")
        smtp.quit.side_effect = BrokenPipeError()
        with self.assertRaises(smtplib.SMTPServerDisconnected):
            with Mailer(SETTINGS) as mailer:
                mailer.send_email(Contact("A", "a@example.com"), SENDER, "Subject", "Body")
        smtp.quit.assert_not_called()
        smtp.close.assert_called_once()

    def test_reconnects_on_421_and_retries_once(self, smtp_ssl):
        first, second = unittest.mock.MagicMock(), unittest.mock.MagicMock()
        smtp_ssl.side_effect = [first, second]
        first.send_message.side_effect = smtplib.SMTPSenderRefused(421, b"too many", "santa@example.com")
        with Mailer(SETTINGS) as mailer:
            mailer.send_email(Contact("A", "a@example.com"), SENDER, "Subject", "Body")
        self.assertEqual(smtp_ssl.call_count, 2)
        second.login.assert_called_once_with("login", "password")
        second.send_message.assert_called_once()

    def test_reconnects_when_server_closed_connection(self, smtp_ssl):
        first, second = unittest.mock.MagicMock(), unittest.mock.MagicMock()
        smtp_ssl.side_effect = [first, second]
        first.sock = None
        with Mailer(SETTINGS) as mailer:
            mailer.send_email(Contact("A", "a@example.com"), SENDER, "Subject", "Body")
        first.send_message.assert_not_called()
        second.send_message.assert_called_once()

    def test_disconnect_during_send_is_not_retried(self, smtp_ssl):
        smtp = smtp_ssl.return_value
        smtp.send_message.side_effect = smtplib.SMTPServerDisconnected("gone")
        with self.assertRaises(smtplib.SMTPServerDisconnected):
            with Mailer(SETTINGS) as mailer:
                mailer.send_email(Contact("A", "a@example.com"), SENDER, "Subject", "Body")
        smtp_ssl.assert_called_once()
        smtp.send_message.assert_called_once()

    def test_permanent_errors_are_not_retried(self, smtp_ssl):
        smtp = smtp_ssl.return_value
        for error in (smtplib.SMTPRecipientsRefused({"a@example.com": (550, b"no such user")}),
                      smtplib.SMTPDataError(554, b"rejected"),
                      smtplib.SMTPDataError(451, b"try again later")):
            smtp.send_message.reset_mock()
            smtp.send_message.side_effect = error
            with self.assertRaises(type(error)):
                with Mailer(SETTINGS) as mailer:
                    mailer.send_email(Contact("A", "a@example.com"), SENDER, "Subject", "Body")
            smtp.send_message.assert_called_once()
        self.assertEqual(smtp_ssl.call_count, 3)  # one connection per Mailer, no reconnection

    def test_second_421_is_not_retried_again(self, smtp_ssl):
        first, second = unittest.mock.MagicMock(), unittest.mock.MagicMock()
        smtp_ssl.side_effect = [first, second]
        busy = smtplib.SMTPRecipientsRefused({"a@example.com": (421, b"too many")})
        first.send_message.side_effect = busy
        second.send_message.side_effect = busy
        with self.assertRaises(smtplib.SMTPRecipientsRefused):
            with Mailer(SETTINGS) as mailer:
                mailer.send_email(Contact("A", "a@example.com"), SENDER, "Subject", "Body")
        self.assertEqual(smtp_ssl.call_count, 2)
        first.send_message.assert_called_once()
        second.send_message.assert_called_once()


if __name__ == '__main__':
    unittest.main()
