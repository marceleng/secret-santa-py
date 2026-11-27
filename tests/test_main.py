import io
import json
import os
import smtplib
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import main
from secret_santa.mailer import Contact, MailerSettings
from secret_santa.secret_santa.player import Player

SETTINGS = MailerSettings("smtp.example.com", 465, None, None)
SENDER = Contact("Santa", "santa@example.com")
RERUN = ["python", "main.py", "--resend"]


def players(*names):
    return [Player(name=n, email=f"{n.lower()}@example.com") for n in names]


class TestSaveDraw(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "draw.json")
        a, b = players("A", "B")
        self.assignments = {a: {b}, b: {a}}

    def tearDown(self):
        self.dir.cleanup()

    def test_writes_draw_and_leaves_no_temp_file(self):
        main.save_draw(self.path, self.assignments)
        with open(self.path) as f:
            self.assertEqual(json.load(f), {"assignments": {"A": ["B"], "B": ["A"]}})
        self.assertEqual(os.listdir(self.dir.name), ["draw.json"])

    def test_refuses_to_overwrite(self):
        with open(self.path, "w") as f:
            f.write("existing")
        with self.assertRaises(FileExistsError):
            main.save_draw(self.path, self.assignments)
        with open(self.path) as f:
            self.assertEqual(f.read(), "existing")
        self.assertEqual(os.listdir(self.dir.name), ["draw.json"])

    def test_failed_write_leaves_nothing(self):
        with patch("main.os.fsync", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                main.save_draw(self.path, self.assignments)
        self.assertEqual(os.listdir(self.dir.name), [])


@patch("main.Mailer")
class TestMainSending(unittest.TestCase):

    def setUp(self):
        a, b, c = players("A", "B", "Jean \"JJ\" Dupont")
        self.assignments = {a: {b}, b: {c}, c: {a}}

    def run_main(self, mailer_cls, side_effect):
        mailer = MagicMock()
        mailer.send_email.side_effect = side_effect
        mailer_cls.return_value.__enter__.return_value = mailer
        out = io.StringIO()
        with redirect_stdout(out):
            try:
                main.main(self.assignments, SETTINGS, "Subject", "{santa} -> {recipient}",
                          SENDER, dry=False, rerun_command=RERUN)
            except BaseException as e:
                return out.getvalue(), e, mailer
        return out.getvalue(), None, mailer

    def test_refused_address_does_not_stop_the_others(self, mailer_cls):
        refused = smtplib.SMTPRecipientsRefused({"a@example.com": (550, b"no such user")})
        out, exc, mailer = self.run_main(mailer_cls, [refused, None, None])
        self.assertEqual(mailer.send_email.call_count, 3)
        self.assertIsInstance(exc, SystemExit)
        self.assertIn("python main.py --resend --only A", out)
        self.assertNotIn("--only B", out)

    def test_interrupt_reports_and_flags_in_flight(self, mailer_cls):
        out, exc, _ = self.run_main(mailer_cls, [None, KeyboardInterrupt()])
        self.assertIsInstance(exc, KeyboardInterrupt)
        self.assertIn("Already sent: A.", out)
        self.assertIn("Sending to B was interrupted", out)
        self.assertIn("--only B --only 'Jean \"JJ\" Dupont'", out)

    def test_no_rerun_command_when_everything_was_sent(self, mailer_cls):
        out, exc, _ = self.run_main(mailer_cls, [None, None, None])
        self.assertIsNone(exc)
        self.assertNotIn("--resend", out)


class TestLoadDraw(unittest.TestCase):

    def test_load_rejects_non_draw_file(self):
        for content in ("Romain Luca\n", "[]", '{"other": 1}', '{"assignments": {"A": 1}}'):
            with self.subTest(content=content):
                with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                    f.write(content)
                self.addCleanup(os.unlink, f.name)
                with self.assertRaisesRegex(ValueError, "not a draw file"):
                    main.load_draw(f.name, {p.name: p for p in players("A")})


if __name__ == '__main__':
    unittest.main()
