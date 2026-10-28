# Valutatrade Hub

Платформа для отслеживания и симуляции торговли валютами (учебный проект).

## Структура проекта

```
finalproject_<фамилия>_<группа>/
├── data/
│   ├── users.json           # список пользователей
│   ├── portfolios.json      # портфели и кошельки
│   └── rates.json           # курсы валют (кеш)
├── valutatrade_hub/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py        # реализация классов User, Wallet, Portfolio
│   │   ├── utils.py         # вспомогательные функции, сервис курсов
│   │   └── usecases.py      # бизнес-логика команд
│   └── cli/
│       ├── __init__.py
│       └── interface.py     # команды
├── main.py
├── pyproject.toml
├── README.md
└── .gitignore               # исключить dist/, __pycache__/ и т.п.
```

CLI построен на модуле `cli/interface.py` и является единственной точкой входа.
Файл запуска `main.py` не дублирует бизнес-логику — только вызывает методы из
`core/usecases.py`.

## Запуск

```bash
python main.py <команда> [аргументы]
```

## Команды

| Команда | Назначение |
|---|---|
| `register --username ИМЯ --password ПАРОЛЬ` | регистрация нового пользователя |
| `login --username ИМЯ --password ПАРОЛЬ` | вход в систему |
| `logout` | выход из системы |
| `show-portfolio [--base EUR]` | кошельки и итоговая стоимость (по умолчанию USD) |
| `buy --currency BTC --amount 0.05` | купить валюту (amount — в штуках) |
| `sell --currency BTC --amount 0.01` | продать валюту |
| `get-rate --from BTC --to EUR` | текущий курс одной валюты к другой |
| `deposit --currency USD --amount 5000` | пополнить кошелёк (бонус) |

## Сценарий проверки

```bash
python main.py register --username alice --password 12     # Пароль должен быть не короче 4 символов
python main.py register --username alice --password 1234   # Пользователь "alice" зарегистрирован (id=1)
python main.py register --username alice --password 4321   # Имя пользователя "alice" уже занято
python main.py login --username bob --password 1234        # Пользователь "bob" не найден
python main.py show-portfolio                              # Сначала выполните login
python main.py login --username alice --password 1234      # Вы вошли как "alice"
python main.py deposit --currency USD --amount 5000        # Кошелёк USD пополнен
python main.py buy --currency BTC --amount 0.05            # Покупка выполнена
python main.py show-portfolio                              # Портфель и ИТОГО
python main.py get-rate --from BTC --to EUR                # Курс BTC->EUR (кросс-курс)
python main.py sell --currency BTC --amount 5              # Недостаточно средств
```

## Примечания

- Пароли хранятся только в виде псевдо-хеша `sha256(password + salt)`,
  случайная соль генерируется при регистрации и при каждой смене пароля.
- Курсы валют пока берутся из заглушки Parser Service; кеш хранится в
  `data/rates.json` со временем обновления, срок жизни записи — 5 минут.
  Кросс-курсы (например BTC→EUR) считаются арифметически через USD.
- Сессия текущего пользователя хранится в `data/session.json`, так как каждая
  команда CLI — отдельный запуск процесса.
