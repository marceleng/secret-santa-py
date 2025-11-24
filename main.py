from __future__ import annotations

import json

from optparse import OptionParser
from configobj import ConfigObj

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

def main(players: set[Player], incompatibilities: set[Incompatibility], giftNumber: int, mailer_settings: MailerSettings,
         email_subject: str, email_body_template: str, src_contact: Contact, dry: bool, logfile: str | None):
    #graph = GiftGraph(players, incompatibilities)
    graph = NGiftGraph(
         players=players,
         incompatibilities=incompatibilities,
         number_of_gifts=giftNumber,
         allow_2cycles=False)
    graph.verify_assignments()
    print("Graph is correct!")
    mailer = Mailer(mailer_settings)
    if logfile:
        with open(logfile, 'w') as l:
            lines = [ f'{santa.name} {format_recipient_names(dsts)}\n' for santa, dsts in graph.assignments.items()]
            l.writelines(lines)
    for src, dsts in graph.assignments.items():
        message_body = email_body_template.format(santa=src.name, recipient=format_recipient_names(dsts))
        if dry:
            print(f'Mail to {src.name} ({src.email}):')
            print(message_body)
        else:
            dst_contact = Contact(src.name, src.email)
            mailer.send_email(dst_contact,
                            src_contact,
                            email_subject,
                            message_body)


if __name__ == '__main__':

    usage = "usage: %prog [options] input_file"
    parser = OptionParser(usage=usage)
    parser.add_option("-d", "--dry", dest="dry_run", action="store_true", default=False,
                      help="Dry run - do not send emails")
    parser.add_option("--smtp-login", dest="login", action="store", help="Login for the SMTP server")
    parser.add_option("--smtp-password", dest="password", action="store", help="Password for the SMTP server")
    parser.add_option("-c", "--config", dest="config_file", action="store", default="config.ini",
                      help="path to configuration file")
    parser.add_option("--logfile", dest="logfile", action="store", default=None, help="path to log file")

    (options, [inputfile]) = parser.parse_args()
    if options.login and not options.password:
        parser.error("Got a login but no password for SMTP server")
    if not options.login and options.password:
        parser.error("Got a password but no login for SMTP server")

    dry = options.dry_run
    logfile = options.logfile

    config = ConfigObj(options.config_file)

    mailer_settings = MailerSettings(
        server_fqdn=config["SMTP Server"]["domain"],
        server_port=config["SMTP Server"]["port"],
        login=options.login,
        password=options.password
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
                                    players_by_name[inc["snd"]]),
        input_data["incompatibilities"]))

    main(input_players, input_incompatibilities, giftNumber, mailer_settings,
         email_subject, email_body_template, src_contact,  dry, logfile)
