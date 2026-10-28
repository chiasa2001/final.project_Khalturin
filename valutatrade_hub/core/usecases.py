"""Бизнес-логика команд. CLI не содержит бизнес-логики — только вызовы отсюда."""

import secrets

from .models import Portfolio, User
from .utils import (PORTFOLIOS_FILE, USERS_FILE,
                    RateService, fmt_amount, fmt_rate, is_known_currency,
                    read_json, write_json, SESSION_FILE)


class AppError(Exception):
    """Базовая ошибка приложения — CLI печатает её текст пользователю."""


class ValidationError(AppError):
    pass


class NotFoundError(AppError):
    pass


class RateUnavailableError(AppError):
    pass


class NotAuthorizedError(AppError):
    pass


class Session:
    """Сессия хранится в data/session.json, иначе «залогиненность»
    не пережила бы перезапуск процесса между командами CLI."""

    def __init__(self, path=SESSION_FILE):
        self._path = path
        self._user = None
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        self._loaded = True
        data = read_json(self._path, {})
        username = data.get("username")
        if not username:
            return
        record = next((u for u in read_json(USERS_FILE, [])
                       if u.get("username") == username), None)
        if record:
            self._user = User.from_dict(record)

    @property
    def user(self):
        self._load()
        return self._user

    def login(self, user):
        self._user = user
        write_json(self._path, {"username": user.username})

    def logout(self):
        user = self.user
        self._user = None
        write_json(self._path, {})
        return user

    def require_user(self):
        user = self.user
        if user is None:
            raise NotAuthorizedError("Сначала выполните login")
        return user


session = Session()
rate_service = RateService()


def _load_users():
    return read_json(USERS_FILE, [])


def _save_users(users):
    write_json(USERS_FILE, users)


def _load_portfolios():
    return read_json(PORTFOLIOS_FILE, [])


def _save_portfolios(portfolios):
    write_json(PORTFOLIOS_FILE, portfolios)


def _load_portfolio(user_id, user=None):
    record = next((p for p in _load_portfolios() if p.get("user_id") == user_id),
                  None)
    if record is None:
        record = {"user_id": user_id, "wallets": {}}
    return Portfolio.from_dict(record, user=user)


def _save_portfolio(portfolio):
    portfolios = [p for p in _load_portfolios()
                  if p.get("user_id") != portfolio.user_id]
    portfolios.append(portfolio.to_dict())
    _save_portfolios(portfolios)


def _validate_currency(code):
    if not isinstance(code, str) or not code.strip() \
            or not code.strip().isascii() or not code.strip().isalpha():
        raise ValidationError(f'Некорректный код валюты: "{code}"')
    return code.strip().upper()


def _validate_amount(amount):
    try:
        value = float(amount)
    except (TypeError, ValueError):
        raise ValidationError("Некорректная сумма: 'amount' должен быть положительным числом")
    if value <= 0:
        raise ValidationError("Некорректная сумма: 'amount' должен быть положительным числом")
    return value


def register_user(username, password):
    """Команда register."""
    if not isinstance(username, str) or not username.strip():
        raise ValidationError("Имя пользователя не может быть пустым")
    username = username.strip()
    if not isinstance(password, str) or len(password) < 4:
        raise ValidationError("Пароль должен быть не короче 4 символов")

    users = _load_users()
    if any(u.get("username", "").lower() == username.lower() for u in users):
        raise ValidationError(f'Имя пользователя "{username}" уже занято')

    user_id = max((u.get("user_id", 0) for u in users), default=0) + 1
    user = User.register(user_id, username, password)
    users.append(user.to_dict())
    _save_users(users)

    # пустой портфель для нового пользователя
    portfolios = _load_portfolios()
    portfolios.append({"user_id": user_id, "wallets": {}})
    _save_portfolios(portfolios)

    return (f'Пользователь "{username}" зарегистрирован (id={user_id}). '
            f"Войдите: login --username {username} --password <пароль>")


def login_user(username, password):
    """Команда login."""
    record = next((u for u in _load_users() if u.get("username") == username),
                  None)
    if record is None:
        raise NotFoundError(f'Пользователь "{username}" не найден')
    user = User.from_dict(record)
    if not user.verify_password(password):
        raise ValidationError("Неверный пароль")
    session.login(user)
    return f'Вы вошли как "{user.username}"'


def logout_user():
    """Команда logout."""
    user = session.logout()
    if user is None:
        raise NotAuthorizedError("Вы не залогинены")
    return f'Вы вышли из аккаунта "{user.username}"'


def show_portfolio(base="USD"):
    """Команда show-portfolio."""
    user = session.require_user()
    base = _validate_currency(base)
    if not is_known_currency(base):
        raise ValidationError(f'Неизвестная базовая валюта "{base}"')

    portfolio = _load_portfolio(user.user_id, user=user)
    wallets = portfolio.wallets
    if not wallets:
        return (f'Портфель пользователя "{user.username}" пуст. '
                f"Купите валюту командой buy.")

    lines = [f'Портфель пользователя "{user.username}" (база: {base}):']
    total = 0.0
    for code, wallet in wallets.items():
        rate, _ = rate_service.get_rate(code, base)
        if rate is None:
            lines.append(f"{code}: {fmt_amount(wallet.balance)} — курс недоступен")
            continue
        value = wallet.balance * rate
        total += value
        lines.append(f"{code}: {fmt_amount(wallet.balance)} → "
                     f"{fmt_amount(value)} {base}")
    lines.append("-" * 40)
    lines.append(f"ИТОГО: {fmt_amount(total)} {base}")
    return "\n".join(lines)


def buy_currency(currency, amount):
    """Команда buy."""
    user = session.require_user()
    currency = _validate_currency(currency)
    amount = _validate_amount(amount)

    rate, _ = rate_service.get_rate(currency, "USD")  # 1 currency = ? USD
    if rate is None:
        raise RateUnavailableError(
            f"Не удалось получить курс для {currency}-USD")

    cost = amount * rate

    portfolio = _load_portfolio(user.user_id, user=user)

    wallet = portfolio.get_wallet(currency)
    old_currency = wallet.balance if wallet else 0.0
    if wallet is None:
        wallet = portfolio.add_currency(currency)

    usd_wallet = portfolio.get_wallet("USD")
    old_usd = usd_wallet.balance if usd_wallet else 0.0
    if usd_wallet is None:
        usd_wallet = portfolio.add_currency("USD")

    # сначала проверяем, потом меняем — иначе при нехватке средств
    # портфель остался бы «обрезанным»
    if usd_wallet.balance < cost:
        raise ValidationError(
            f"Недостаточно средств: доступно {fmt_amount(usd_wallet.balance)} USD, "
            f"требуется {fmt_amount(cost)} USD")

    usd_wallet.withdraw(cost)   # списание с USD-кошелька
    wallet.deposit(amount)
    _save_portfolio(portfolio)

    lines = [
        f"Покупка выполнена: {fmt_amount(amount)} {currency} "
        f"по курсу {fmt_rate(rate)} USD/{currency}",
        "Изменения в портфеле:",
        f"{currency}: было {fmt_amount(old_currency)} → "
        f"стало {fmt_amount(wallet.balance)}",
        f"USD: было {fmt_amount(old_usd)} → "
        f"стало {fmt_amount(usd_wallet.balance)}",
        f"Оценочная стоимость покупки: {fmt_amount(cost)} USD",
    ]
    return "\n".join(lines)


def sell_currency(currency, amount):
    """Команда sell."""
    user = session.require_user()
    currency = _validate_currency(currency)
    if currency == "USD":
        raise ValidationError("Валюта USD является расчётной: продать её нельзя")
    amount = _validate_amount(amount)

    portfolio = _load_portfolio(user.user_id, user=user)
    wallet = portfolio.get_wallet(currency)
    if wallet is None:
        raise ValidationError(
            f'У вас нет кошелька "{currency}". Добавьте валюту: она создаётся '
            f"автоматически при первой покупке")

    rate, _ = rate_service.get_rate(currency, "USD")
    if rate is None:
        raise RateUnavailableError(
            f"Не удалось получить курс для {currency}-USD")

    proceeds = amount * rate
    usd_wallet = portfolio.get_wallet("USD") or portfolio.add_currency("USD")
    old_currency, old_usd = wallet.balance, usd_wallet.balance
    wallet.withdraw(amount)     # бросит ошибку, если средств недостаточно
    usd_wallet.deposit(proceeds)
    _save_portfolio(portfolio)

    lines = [
        f"Продажа выполнена: {fmt_amount(amount)} {currency} "
        f"по курсу {fmt_rate(rate)} USD/{currency}",
        "Изменения в портфеле:",
        f"{currency}: было {fmt_amount(old_currency)} → "
        f"стало {fmt_amount(wallet.balance)}",
        f"USD: было {fmt_amount(old_usd)} → "
        f"стало {fmt_amount(usd_wallet.balance)}",
        f"Оценочная выручка: {fmt_amount(proceeds)} USD",
    ]
    return "\n".join(lines)


def get_rate_cmd(currency_from, currency_to):
    """Команда get-rate."""
    currency_from = _validate_currency(currency_from)
    currency_to = _validate_currency(currency_to)

    rate, updated = rate_service.get_rate(currency_from, currency_to)
    if rate is None:
        raise RateUnavailableError(
            f"Курс {currency_from}-{currency_to} недоступен. "
            f"Повторите попытку позже.")

    updated_str = (updated or "").replace("T", " ") if updated else ""
    lines = [f"Курс {currency_from}->{currency_to}: {fmt_rate(rate)} "
             f"(обновлено: {updated_str})"]
    if currency_from != currency_to:
        reverse, _ = rate_service.get_rate(currency_to, currency_from)
        if reverse is not None:
            lines.append(f"Обратный курс {currency_to}->{currency_from}: "
                         f"{fmt_rate(reverse)}")
    return "\n".join(lines)


def deposit_funds(currency, amount):
    """Бонус сверх ТЗ: пополнение, без него новому пользователю не на что торговать."""
    user = session.require_user()
    currency = _validate_currency(currency)
    if not is_known_currency(currency):
        raise ValidationError(f'Неизвестная валюта "{currency}"')
    amount = _validate_amount(amount)

    portfolio = _load_portfolio(user.user_id, user=user)
    wallet = portfolio.get_wallet(currency) or portfolio.add_currency(currency)
    wallet.deposit(amount)
    _save_portfolio(portfolio)
    return f"Кошелёк {currency} пополнен на {fmt_amount(amount)} {currency}"
