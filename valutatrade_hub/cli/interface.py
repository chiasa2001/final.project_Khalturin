"""Командный интерфейс: только разбор аргументов и вызовы usecases."""

import argparse

from ..core import usecases
from ..core.usecases import AppError


def build_parser():
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Платформа для отслеживания и симуляции торговли валютами")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("register", help="создать нового пользователя")
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)

    p = sub.add_parser("login", help="войти в систему")
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)

    sub.add_parser("logout", help="выйти из системы")

    p = sub.add_parser("show-portfolio", help="кошельки и итог в базовой валюте")
    p.add_argument("--base", default="USD")

    p = sub.add_parser("buy", help="купить валюту")
    p.add_argument("--currency", required=True)
    p.add_argument("--amount", required=True)

    p = sub.add_parser("sell", help="продать валюту")
    p.add_argument("--currency", required=True)
    p.add_argument("--amount", required=True)

    p = sub.add_parser("get-rate", help="курс одной валюты к другой")
    p.add_argument("--from", dest="from_cur", required=True)
    p.add_argument("--to", dest="to_cur", required=True)

    p = sub.add_parser("deposit", help="пополнить кошелёк (бонус)")
    p.add_argument("--currency", required=True)
    p.add_argument("--amount", required=True)

    return parser


def run(args):
    if args.command == "register":
        print(usecases.register_user(args.username, args.password))
    elif args.command == "login":
        print(usecases.login_user(args.username, args.password))
    elif args.command == "logout":
        print(usecases.logout_user())
    elif args.command == "show-portfolio":
        print(usecases.show_portfolio(args.base))
    elif args.command == "buy":
        print(usecases.buy_currency(args.currency, args.amount))
    elif args.command == "sell":
        print(usecases.sell_currency(args.currency, args.amount))
    elif args.command == "get-rate":
        print(usecases.get_rate_cmd(args.from_cur, args.to_cur))
    elif args.command == "deposit":
        print(usecases.deposit_funds(args.currency, args.amount))


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except (AppError, ValueError) as exc:
        print(exc)
