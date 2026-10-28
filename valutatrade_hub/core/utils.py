"""Вспомогательные функции: JSON-хранилище, форматирование, сервис курсов."""

import datetime as dt
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(ROOT, "data")

USERS_FILE = os.path.join(DATA_DIR, "users.json")
PORTFOLIOS_FILE = os.path.join(DATA_DIR, "portfolios.json")
RATES_FILE = os.path.join(DATA_DIR, "rates.json")
SESSION_FILE = os.path.join(DATA_DIR, "session.json")

CACHE_TTL = 5 * 60  # секунд

# Заглушка Parser Service: стоимость 1 единицы валюты в USD.
STUB_RATES = {
    "USD": 1.0,
    "EUR": 1.0786,
    "RUB": 0.01016,
    "BTC": 59337.21,
    "ETH": 3728.86,
}


def read_json(path, default):
    """Читает JSON-файл. Нет файла или он повреждён — возвращаем default."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, data):
    """Атомарная запись: сначала во временный файл, потом замена."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def fmt_amount(value):
    """150 -> '150.00', 0.05 -> '0.0500', 2965 -> '2,965.00'."""
    if abs(value) >= 1:
        return f"{value:,.2f}"
    return f"{value:.4f}"


def fmt_rate(rate):
    """59337.21 -> '59,337.21', 0.00001818 -> '0.00001818'."""
    if rate >= 1:
        return f"{rate:,.2f}"
    return f"{rate:.8f}".rstrip("0")


def is_known_currency(code):
    return isinstance(code, str) and code.upper() in STUB_RATES


class ParserService:
    """Заглушка внешнего сервиса: имитирует запрос актуального курса."""

    @staticmethod
    def fetch_rate(code):
        return STUB_RATES.get(code.upper())


class RateService:
    """Единый контракт: get_rate(base, quote) -> (rate, updated_at) или (None, None).

    В кеше rates.json хранятся пары к USD ("BTC_USD", "USD_BTC"...).
    Кросс-курсы (например BTC -> EUR) считаются арифметически:
    rate(base -> USD) / rate(quote -> USD).
    """

    def __init__(self, path=RATES_FILE, ttl=CACHE_TTL):
        self._path = path
        self._ttl = ttl

    def get_rate(self, base, quote):
        base, quote = base.upper(), quote.upper()
        now_iso = dt.datetime.now().isoformat(timespec="seconds")
        if base == quote:
            return 1.0, now_iso
        if base not in STUB_RATES or quote not in STUB_RATES:
            return None, None

        data = read_json(self._path, {})
        base_rec = self._usd_record(data, base)
        quote_rec = self._usd_record(data, quote)
        if not (self._ok(base_rec) and self._ok(quote_rec)):
            self._refresh()
            data = read_json(self._path, {})
            base_rec = self._usd_record(data, base)
            quote_rec = self._usd_record(data, quote)
        if not (base_rec and quote_rec):
            return None, None

        rate = base_rec["rate"] / quote_rec["rate"]
        updated = max(base_rec["updated_at"], quote_rec["updated_at"])
        return rate, updated

    # ---------- внутренние методы ----------
    def _usd_record(self, data, code):
        """Запись курса валюты к USD; для USD — константа 1.0."""
        if code == "USD":
            return {"rate": 1.0, "updated_at": data.get("last_refresh")}
        return data.get(f"{code}_USD")

    def _ok(self, record):
        return bool(record) and self._is_fresh(record)

    def _is_fresh(self, record):
        try:
            updated = dt.datetime.fromisoformat(record["updated_at"])
        except (KeyError, TypeError, ValueError):
            return False
        return (dt.datetime.now() - updated).total_seconds() < self._ttl

    def _refresh(self):
        """Обновляет кеш через Parser Service (пока заглушку)."""
        try:
            now = dt.datetime.now().isoformat(timespec="seconds")
            data = {"source": "ParserService", "last_refresh": now}
            for code, usd_rate in STUB_RATES.items():
                if code == "USD":
                    continue
                data[f"{code}_USD"] = {"rate": usd_rate, "updated_at": now}
            write_json(self._path, data)
            return True
        except OSError:
            return False
