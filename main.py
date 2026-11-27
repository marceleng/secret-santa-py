from __future__ import annotations

import errno
import json
import os
import shlex
import smtplib
import sys
import tempfile

from getpass import getpass

from optparse import OptionParser

from secret_santa.mailer import Mailer, Contact, MailerSettings
from secret_santa.secret_santa.gift_graph import NGiftGraph
from secret_santa.secret_santa.incompatibility import Incompatibility
from secret_santa.secret_santa.player import Player


def format_recipient_names(recipients: set[Player], and_word="and") -> str:
    if not recipients:
        raise ValueError("Recipients should not be empty")
    elif len(recipients) == 1:
        return next(iter(recipients)).name
    else:
        recipient_names = [r.name for r in recipients]
        return f'{", ".join(recipient_names[:-1])} {and_word} {recipient_names[-1]}'

Assignments = dict[Player, set[Player]]


def save_draw(path: str, assignments: Assignments):
    """Write the draw to `path`, refusing to overwrite an existing draw."""
    draw = {"assignments": {santa.name: sorted(r.name for r in recipients)
                            for santa, recipients in assignments.items()}}
    # Serialize first, write to a temporary file, then link it into place: a failure
    # never leaves a truncated draw behind, and os.link refuses to overwrite `path`.
    content = json.dumps(draw, indent=2) + '\n'
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)),
                                    prefix='.draw-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(tmp_path, path)
        except OSError as e:
            if e.errno not in (errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP):
                raise
            # No hard links on this filesystem (FAT/exFAT, some network shares):
            # create the file exclusively instead, and remove it if the write fails.
            # 0o600 like mkstemp: the draw reveals every assignment.
            f = os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w')
            try:
                with f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())
            except BaseException:
                # Unlink after closing: some network shares refuse to delete an open file.
                os.unlink(path)
                raise
    finally:
        os.unlink(tmp_path)


def load_draw(path: str, players_by_name: dict[str, Player]) -> Assignments:
    with open(path) as f:
        try:
            draw = [(santa, [*recipients]) for santa, recipients in json.load(f)["assignments"].items()]
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            raise ValueError(f"{path} is not a draw file saved by this script ({e!r})") from e
    unknown = {name for santa, recipients in draw
               for name in [santa, *recipients] if name not in players_by_name}
    if unknown:
        raise ValueError(f"Draw file {path} names unknown players: {', '.join(sorted(unknown))}")
    return {players_by_name[santa]: {players_by_name[r] for r in recipients}
            for santa, recipients in draw}


def draw_assignments(players: set[Player], incompatibilities: set[Incompatibility], giftNumber: int) -> Assignments:
    graph = NGiftGraph(
         players=players,
         incompatibilities=incompatibilities,
         number_of_gifts=giftNumber,
         allow_2cycles=False)
    graph.verify_assignments()
    print("Graph is correct!")
    return dict(graph.assignments)


def report_unsent(messages: list[tuple[Contact, str]], sent: list[str], refused: list[str],
                 in_flight: str | None, rerun_command: list[str]):
    remaining = [c.name for c, _ in messages if c.name not in sent]
    print(f'Already sent: {", ".join(sent) or "nobody"}.')
    if refused:
        print(f'Address refused for: {", ".join(refused)}. Fix their email in the input file first.')
    if in_flight is not None:
        print(f'Sending to {in_flight} was interrupted: they may already have received the email, '
              'check before resending to them.')
    if remaining:
        only_args = [arg for name in remaining for arg in ('--only', name)]
        print('To send the rest from the same draw, run:')
        print('  ' + shlex.join(rerun_command + only_args))


def main(assignments: Assignments, mailer_settings: MailerSettings, email_subject: str,
         email_body_template: str, src_contact: Contact, dry: bool, only: set[str] | None = None,
         rerun_command: list[str] | None = None):
    messages = [
        (Contact(src.name, src.email),
         email_body_template.format(santa=src.name, recipient=format_recipient_names(dsts)))
        for src, dsts in assignments.items()
        if only is None or src.name in only]

    if dry:
        for dst_contact, message_body in messages:
            print(f'Mail to {dst_contact.name} ({dst_contact.email}):')
            print(message_body)
        return

    if rerun_command is None:
        rerun_command = ['python', 'main.py', '--resend']
    sent: list[str] = []
    refused: list[str] = []
    in_flight: str | None = None
    try:
        # Connect and log in once, before sending anything.
        with Mailer(mailer_settings) as mailer:
            for dst_contact, message_body in messages:
                in_flight = dst_contact.name
                try:
                    mailer.send_email(dst_contact, src_contact, email_subject, message_body)
                except smtplib.SMTPRecipientsRefused as e:
                    in_flight = None
                    if not all(code >= 500 for code, _ in e.recipients.values()):
                        # 4xx is a temporary server refusal, not a bad address: stop here.
                        raise
                    # A bad address only affects this player: carry on with the others.
                    refused.append(dst_contact.name)
                    print(f'Address of {dst_contact.name} ({dst_contact.email}) refused: {e.recipients}')
                    continue
                in_flight = None
                sent.append(dst_contact.name)
                print(f'Sent to {dst_contact.name}')
    except BaseException:
        # BaseException: also report on Ctrl-C.
        print('Sending failed.')
        report_unsent(messages, sent, refused, in_flight, rerun_command)
        raise
    if refused:
        report_unsent(messages, sent, refused, None, rerun_command)
        raise SystemExit(1)


if __name__ == '__main__':
    # Imported here so that the tests can import this module without configobj.
    from configobj import ConfigObj

    usage = "usage: %prog [options] input_file"
    parser = OptionParser(usage=usage)
    parser.add_option("-d", "--dry", dest="dry_run", action="store_true", default=False,
                      help="Dry run - do not send emails nor save the draw")
    parser.add_option("--smtp-login", dest="login", action="store",
                      help="Login for the SMTP server. The password is read from the SMTP_PASSWORD "
                           "environment variable, or prompted for if it is not set")
    parser.add_option("-c", "--config", dest="config_file", action="store", default="config.ini",
                      help="path to configuration file")
    parser.add_option("--draw-file", dest="draw_file", action="store", default="draw.json",
                      help="where the draw is saved before sending emails (default: %default). "
                           "An existing file is never overwritten")
    parser.add_option("--resend", dest="resend", action="store_true", default=False,
                      help="send emails from the draw saved in --draw-file instead of drawing again")
    parser.add_option("--only", dest="only", action="append", metavar="NAME",
                      help="with --resend, only email this player (repeatable)")

    (options, [inputfile]) = parser.parse_args()
    dry = options.dry_run
    if options.only and not options.resend:
        parser.error("--only requires --resend")
    if options.resend and not os.path.exists(options.draw_file):
        parser.error(f"--resend: draw file {options.draw_file} does not exist")
    if not options.resend and not dry and os.path.exists(options.draw_file):
        parser.error(f"draw file {options.draw_file} already exists: use --resend to send it again, "
                     "or move it away to draw again")

    # Never take the password as an argument: it would leak into shell history and `ps`.
    password = None
    if options.login and not dry:
        password = os.environ.get("SMTP_PASSWORD") or getpass(f"SMTP password for {options.login}: ")

    config = ConfigObj(options.config_file)

    mailer_settings = MailerSettings(
        server_fqdn=config["SMTP Server"]["domain"],
        server_port=config["SMTP Server"]["port"],
        login=options.login,
        password=password
    )

    src_contact = Contact(name=config["Email Template"]["sender name"],
                          email=config["Email Template"]["sender email"])
    email_subject = config["Email Template"]["subject"]
    email_body_template = config["Email Template"]["email template"]

    input_data = json.load(open(inputfile))

    giftNumber: int = 1 if not "giftNumber" in input_data else input_data["giftNumber"]
    input_players = set(map(lambda x: Player(**x), input_data["players"]))
    players_by_name = {p.name: p for p in input_players}
    input_incompatibilities = set(map(
        lambda inc: Incompatibility(players_by_name[inc["fst"]],
                                    players_by_name[inc["snd"]],
                                    # Optional: only "fst" gifting "snd" is forbidden.
                                    one_way=inc.get("oneWay", False)),
        input_data["incompatibilities"]))

    if options.resend:
        try:
            assignments = load_draw(options.draw_file, players_by_name)
        except ValueError as e:
            parser.error(str(e))
        if options.only and (unknown := set(options.only) - {p.name for p in assignments}):
            parser.error(f"--only: unknown players in the draw: {', '.join(sorted(unknown))}")
    else:
        assignments = draw_assignments(input_players, input_incompatibilities, giftNumber)
        if not dry:
            save_draw(options.draw_file, assignments)
            print(f"Draw saved to {options.draw_file}")

    rerun_command = [sys.executable,sys.argv[0],
                     '-c', options.config_file, '--draw-file', options.draw_file]
    if options.login:
        rerun_command += ['--smtp-login', options.login]
    rerun_command += [inputfile, '--resend']

    main(assignments, mailer_settings, email_subject, email_body_template, src_contact, dry,
         set(options.only) if options.only else None, rerun_command)
