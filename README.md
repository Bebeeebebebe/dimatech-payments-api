# DimaTech Payments API

Асинхронный REST API тестового задания: пользователи, администраторы, счета и
идемпотентная обработка платёжных webhook-событий.

## Стек

- Python 3.12+
- Sanic 25.12
- PostgreSQL, SQLAlchemy 2.0 async, asyncpg
- Alembic
- JWT (HS256) и Argon2
- Docker Compose
- pytest + SQLite/aiosqlite для быстрых изолированных тестов

## Запуск в Docker

```bash
cp .env.example .env
docker compose up --build
```

Миграция и тестовые данные применяются автоматически. API будет доступен на
`http://localhost:8000/api/v1`, health check — `GET /api/v1/health`.

Остановить сервисы:

```bash
docker compose down
```

## Локальный запуск без Docker

Нужен запущенный PostgreSQL и Python 3.12+.

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -e ".[test]"
cp .env.example .env
alembic upgrade head
sanic app.server:app --host=0.0.0.0 --port=8000 --single-process
```

При необходимости измените `DATABASE_URL` в `.env`.

## Тестовые пользователи

| Роль | Email | Пароль |
|---|---|---|
| Пользователь | `user@example.com` | `UserPass123!` |
| Администратор | `admin@example.com` | `AdminPass123!` |

## Основные endpoints

| Метод | URL | Доступ |
|---|---|---|
| `POST` | `/api/v1/auth/login` | публичный |
| `GET` | `/api/v1/me` | пользователь/администратор |
| `GET` | `/api/v1/accounts` | пользователь |
| `GET` | `/api/v1/payments` | пользователь |
| `GET` | `/api/v1/admin/users` | администратор |
| `POST` | `/api/v1/admin/users` | администратор |
| `PATCH` | `/api/v1/admin/users/{id}` | администратор |
| `DELETE` | `/api/v1/admin/users/{id}` | администратор |
| `POST` | `/api/v1/payments/webhook` | публичный, с подписью |

Защищённые запросы используют заголовок:

```text
Authorization: Bearer <access_token>
```

Пример авторизации:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"UserPass123!"}'
```

## Платёжный webhook

Тело запроса:

```json
{
  "transaction_id": "5eae174f-7cd0-472c-bd36-35660f00132b",
  "user_id": 1,
  "account_id": 1,
  "amount": 100,
  "signature": "<sha256>"
}
```

Подпись — SHA-256 от конкатенации значений полей в алфавитном порядке ключей
без `signature`, после чего добавляется секрет:

```text
SHA256(account_id + amount + transaction_id + user_id + secret_key)
```

Для примера выше и секрета из `.env`:

```python
from decimal import Decimal
from app.security import build_webhook_signature

signature = build_webhook_signature(
    account_id=1,
    amount=Decimal("100"),
    transaction_id="5eae174f-7cd0-472c-bd36-35660f00132b",
    user_id=1,
    secret="gfdmhghif38yrf9ew0jkf32",
)
```

Обработка идемпотентна: уникальный индекс на `transaction_id` не позволяет
сохранить платёж повторно. Транзакция БД блокирует пользователя и счёт до
одновременной записи платежа и изменения баланса. Повторный webhook возвращает
`status: duplicate` и не меняет баланс.

Если передан ещё не существующий `account_id`, счёт создаётся для указанного
пользователя. Если счёт уже принадлежит другому пользователю, API возвращает
`409 account_owner_mismatch`.

## Тесты

```bash
pytest -q
```

Покрыты авторизация, просмотр профиля, успешный webhook, повторная доставка,
неверная подпись и CRUD пользователей администратором.

## Структура

```text
app/
  api.py         HTTP endpoints и транзакционный webhook
  models.py      SQLAlchemy-модели
  schemas.py     валидация Pydantic
  security.py    JWT, Argon2, подпись webhook
  server.py      фабрика Sanic-приложения
migrations/      Alembic и стартовые данные
tests/           интеграционные API-тесты
```

В production следует заменить `JWT_SECRET`, `WEBHOOK_SECRET` и пароль
PostgreSQL, а также запускать приложение за reverse proxy с TLS.
