"""Реализация классов User, Wallet, Portfolio."""

import hashlib
import secrets
from datetime import datetime

from .utils import fmt_amount


class User:
    """Пользователь системы. Все атрибуты приватные (через __)."""

    def __init__(self, user_id, username, hashed_password, salt,
                 registration_date=None):
        self.__user_id = user_id
        self.username = username            # проверка сработает в сеттере (1.5)
        self.__hashed_password = hashed_password
        self.__salt = salt
        # тип datetime, как в задании; по умолчанию — текущее время
        self.__registration_date = registration_date or datetime.now()

    # ---------- геттеры ----------
    @property
    def user_id(self):
        return self.__user_id

    @property
    def username(self):
        return self.__username

    @username.setter
    def username(self, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self.__username = value.strip()

    @property
    def hashed_password(self):
        return self.__hashed_password

    @property
    def salt(self):
        return self.__salt

    @property
    def registration_date(self):
        """Возвращает объект datetime (тип из задания)."""
        return self.__registration_date

    # ---------- методы (1.2–1.4) ----------
    @staticmethod
    def hash_password(password, salt):
        """Односторонний псевдо-хеш: hashlib.sha256(password + salt)."""
        return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    @staticmethod
    def register(user_id, username, password):
        """Создаёт нового пользователя: генерирует соль и хеширует пароль."""
        user = User(user_id, username, "", secrets.token_hex(8))
        user.change_password(password)
        return user

    def get_user_info(self):
        """Информация о пользователе без пароля (1.3)."""
        return (f'Пользователь "{self.__username}" (id={self.__user_id}), '
                f"зарегистрирован "
                f"{self.__registration_date.isoformat(timespec='seconds')}")

    def verify_password(self, password):
        return self.hash_password(password, self.__salt) == self.__hashed_password

    def change_password(self, new_password):
        """Смена пароля: новая соль + новый хеш (1.4)."""
        if not isinstance(new_password, str) or len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        self.__salt = secrets.token_hex(8)
        self.__hashed_password = self.hash_password(new_password, self.__salt)

    # ---------- сериализация ----------
    def to_dict(self):
        return {
            "user_id": self.__user_id,
            "username": self.__username,
            "hashed_password": self.__hashed_password,
            "salt": self.__salt,
            "registration_date": self.__registration_date.isoformat(
                timespec="seconds"),
        }

    @classmethod
    def from_dict(cls, data):
        date_str = data.get("registration_date")
        date_obj = datetime.fromisoformat(date_str) if date_str else None
        return cls(data["user_id"], data["username"], data["hashed_password"],
                   data["salt"], date_obj)


def check_amount(amount):
    """Проверка суммы: положительное число (нужна и для 2.2, и для 2.3)."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
        raise ValueError("Некорректная сумма: 'amount' должен быть положительным числом")
    return float(amount)


class Wallet:
    """Кошелёк пользователя для одной валюты (2.1–2.7)."""

    def __init__(self, currency_code, balance=0.0):
        self.currency_code = currency_code   # сеттер проверит формат
        self._balance = 0.0
        self.balance = balance               # сеттер проверит значение

    # ---------- методы (2.2, 2.6) ----------
    def deposit(self, amount):
        """Пополнение баланса на положительную сумму."""
        self._balance += check_amount(amount)

    def withdraw(self, amount):
        """Списание средств. Не хватает денег — исключение (2.6)."""
        amount = check_amount(amount)
        if amount > self._balance:
            raise ValueError(
                f"Недостаточно средств: доступно {fmt_amount(self._balance)} "
                f"{self._currency_code}, требуется {fmt_amount(amount)} "
                f"{self._currency_code}")
        self._balance -= amount

    def get_balance_info(self):
        """Вывод информации о текущем балансе."""
        return f"{self._currency_code}: {fmt_amount(self._balance)}"

    # ---------- свойства (2.3–2.5) ----------
    @property
    def currency_code(self):
        return self._currency_code

    @currency_code.setter
    def currency_code(self, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Код валюты не может быть пустым")
        self._currency_code = value.strip().upper()

    @property
    def balance(self):
        return self._balance

    @balance.setter
    def balance(self, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    # ---------- сериализация ----------
    def to_dict(self):
        return {"currency_code": self._currency_code, "balance": self._balance}

    @classmethod
    def from_dict(cls, data):
        return cls(data["currency_code"], data.get("balance", 0.0))


class Portfolio:
    """Все кошельки одного пользователя. user_id -> {код валюты: Wallet}."""

    def __init__(self, user_id, wallets=None, user=None):
        self._user_id = user_id
        self._user = user
        self._wallets = {}
        for code, data in (wallets or {}).items():
            self._wallets[code.upper()] = (
                data if isinstance(data, Wallet)
                else Wallet(code, data.get("balance", 0.0)))

    # ---------- методы (3.2–3.4) ----------
    def add_currency(self, currency_code):
        """Добавляет новый кошелёк (3.2), проверяя уникальность (3.3)."""
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("Код валюты не может быть пустым")
        code = currency_code.strip().upper()
        if code in self._wallets:
            raise ValueError(f"Кошелёк {code} уже существует")
        wallet = Wallet(code)
        self._wallets[code] = wallet
        return wallet

    def get_wallet(self, currency_code):
        """Возвращает объект Wallet по коду валюты или None."""
        if not isinstance(currency_code, str):
            return None
        return self._wallets.get(currency_code.strip().upper())

    def get_total_value(self, base_currency="USD", rate_service=None):
        """Общая стоимость всех кошельков в базовой валюте (3.4)."""
        base = base_currency.upper()
        total = 0.0
        for code, wallet in self._wallets.items():
            if code == base:
                total += wallet.balance
                continue
            rate = rate_service.get_rate(code, base)[0] if rate_service else None
            if rate is not None:          # недоступный курс не рушит весь отчёт
                total += wallet.balance * rate
        return total

    # ---------- свойства (3.5) ----------
    @property
    def user_id(self):
        return self._user_id

    @property
    def user(self):
        return self._user

    @property
    def wallets(self):
        """Копия словаря: изменения снаружи не трогают реальные кошельки."""
        return dict(self._wallets)

    # ---------- сериализация ----------
    def to_dict(self):
        return {
            "user_id": self._user_id,
            "wallets": {code: w.to_dict() for code, w in self._wallets.items()},
        }

    @classmethod
    def from_dict(cls, data, user=None):
        return cls(data["user_id"], data.get("wallets", {}), user=user)
