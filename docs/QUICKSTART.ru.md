# Быстрый старт (русский)

> Первичная настройка Aegis Protocol на одной машине разработчика.
> Английская версия: [QUICKSTART.en.md](QUICKSTART.en.md).

## Требования

| Инструмент | Зачем нужен | Как установить |
|---|---|---|
| Python 3.12+ | Среда выполнения | <https://www.python.org/downloads/> |
| uv | Менеджер пакетов и lock-файла | `pip install uv` или см. <https://docs.astral.sh/uv/> |
| Docker (с Compose) | Postgres + Redis + Qdrant | <https://docs.docker.com/get-docker/> |
| Git | Контроль версий | По вашей ОС |
| (Опционально) RPC 0G testnet | Реальная on-chain демонстрация | <https://docs.0g.ai> |
| (Опционально) Telegram bot token | Демо канала Telegram | `@BotFather` |
| (Опционально) Discord bot token | Демо канала Discord | <https://discord.com/developers> |

## 1. Клонирование и установка зависимостей

```bash
git clone https://github.com/devAsmodeus/Aegis-Protocol.git
cd Aegis-Protocol
uv sync
```

Опциональные «extras» — ставьте только то, что вам нужно:

```bash
uv sync --extra rerank      # Кросс-энкодер FlashRank для реранкинга
uv sync --extra telegram    # Канал Telegram через AIOgram
uv sync --extra discord     # Канал Discord через discord.py
uv sync --extra contracts   # py-solc-x для деплой-скрипта реестра
```

## 2. Поднимаем инфраструктуру

```bash
docker compose up -d
```

Будут запущены:

- `postgres` — мульти-тенант БД (порт 5432)
- `redis` — кэш (порт 6379)
- `qdrant` — векторное хранилище (порт 6333)

Проверка:

```bash
docker compose ps
```

## 3. Конфигурация окружения

```bash
cp .env.example .env
```

Отредактируйте `.env`. Минимально необходимое для базового запуска:

```dotenv
DATABASE_URL=postgresql+asyncpg://aegis:aegis_dev_password@localhost:5432/aegis
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333
```

Опциональные переменные для отдельных демо:

| Переменная | Зачем |
|---|---|
| `ETH_RPC_URL` | Реальное разрешение ENS. Подойдёт Sepolia или mainnet. |
| `ZEROG_RPC_URL` / `ZEROG_PRIVATE_KEY` | Деплой `AegisRegistry.sol` в 0G testnet. **Только testnet.** |
| `ENS_PARENT_DOMAIN` | Корневой ENS проекта, например `aegis-protocol.eth`. |
| `TELEGRAM_BOT_TOKEN` | Запуск адаптера Telegram. |
| `DISCORD_BOT_TOKEN` | Запуск адаптера Discord. |
| `KEEPER_SIGNING_SECRET` | HMAC-секрет для аутентификации webhook keeper-а. Без него endpoint отвечает 503. |
| `ADMIN_API_TOKEN` | Bearer-токен для `/v1/admin/*`. |

## 4. Применяем миграции БД

```bash
uv run alembic upgrade head
```

## 5. Запускаем API

```bash
uv run uvicorn aegis.main:app --reload
```

Smoke-проверки:

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0"}

curl http://localhost:8000/v1/keeper/tasks
# {"tasks":["healthcheck_upstreams","refresh_documents","rotate_agent_sessions"]}
```

## 6. Запускаем тесты

```bash
uv run pytest -m "not integration"
uv run ruff check . && uv run ruff format --check .
uv run mypy aegis
```

В CI по умолчанию docker не нужен; интеграционные тесты (реальные
Postgres / Qdrant / Redis / RPC) включаются явно через `-m integration`.

## 7. Демо-проход

```bash
uv run python -m scripts.demo_walkthrough
```

Скрипт печатает сценарий с подписями: регистрация агента → ответ
агента → receipt → проверка ENS → keeper-задача. Без сети, без docker.

## Опционально: включаем Telegram

```bash
uv sync --extra telegram
export TELEGRAM_BOT_TOKEN=...
# Подключите `aegis/channels/telegram.py:TelegramChannel` в свой
# entry-скрипт — см. in-memory адаптер как минимальный пример.
```

## Опционально: включаем Discord

```bash
uv sync --extra discord
export DISCORD_BOT_TOKEN=...
# Аналогично подключите `aegis/channels/discord.py:DiscordChannel`.
```

## Опционально: деплой `AegisRegistry.sol` в 0G testnet

```bash
uv sync --extra contracts
export ZEROG_RPC_URL=...
export ZEROG_PRIVATE_KEY=...        # ТОЛЬКО testnet
uv run python -m contracts.scripts.deploy_registry
```

Скрипт отказывается работать на известных mainnet-сетях (Ethereum,
Optimism, Polygon, Arbitrum, Base) и требует `APP_ENV=development`.

## Опционально: регистрация ENS-subname

```python
from aegis.chain.ens_subname import register_subname
# Возвращает unsigned-транзакцию. Подпись и broadcast — на стороне вызывающего.
```

## Опционально: настройка keeper webhook-ов

KeeperHub (или любой cron-вызыватель) подписывает тело запроса
HMAC-SHA256 секретом `KEEPER_SIGNING_SECRET`:

```bash
SECRET=$KEEPER_SIGNING_SECRET
BODY='{}'
SIG=$(printf "%s" "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')
curl -X POST http://localhost:8000/v1/keeper/tasks/healthcheck_upstreams/run \
  -H "X-Aegis-Keeper-Signature: $SIG" \
  -d "$BODY"
```

## Что чаще всего ломается

| Симптом | Вероятная причина | Что делать |
|---|---|---|
| `connection refused` к localhost:5432/6379/6333 | Docker не запущен. | `docker compose up -d` |
| `alembic.util.exc.CommandError: Can't locate revision identified by 'XYZ'` | В БД другая ревизия. | Удалить dev-БД и заново `alembic upgrade head` или написать новую миграцию. |
| `solcx.exceptions.SolcNotInstalled` | Не установлен `contracts` extra или нет кэша solc 0.8.24. | `uv sync --extra contracts && python -c "import solcx; solcx.install_solc('0.8.24')"` |
| `web3.exceptions.ConnectionError` | `ETH_RPC_URL` / `ZEROG_RPC_URL` пустой или недоступен. | Заполнить переменную или пропустить этот шаг демо. |
| `mypy` ругается на `web3` / `aiogram` / `discord` | Опциональные extras не установлены в активный venv. | `uv sync --extra <имя>` или опирайтесь на `[[tool.mypy.overrides]]` в `pyproject.toml`. |

## Что читать дальше

- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — архитектура.
- [docs/DEMO.md](DEMO.md) — сценарий для судей.
- [docs/AI_USAGE.md](AI_USAGE.md) — раскрытие AI-инструментов согласно правилам ETHGlobal.
