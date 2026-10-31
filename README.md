# Бібліотечна інформаційна система

REST API бібліотечної системи, розроблений за Specification Driven Development (SDD):
специфікація → контракт API → тести → реалізація. Навчальний проєкт (лабораторні №1–5).

## Швидкий старт

```bash
pip install -r requirements.txt
python -m uvicorn library.main:app --app-dir src --port 8000
```

Після запуску: інтерактивна документація — `http://127.0.0.1:8000/docs` (вона показує
затверджений контракт `spec/openapi.yaml`). База даних — файл `var/library.db`, створюється
сама; головний адміністратор створюється при першому запуску (`chief@library.local` /
`Chief-Pass-2026`, змінюється змінними середовища `LIBRARY_CHIEF_EMAIL`,
`LIBRARY_CHIEF_PASSWORD`). Листи з токенами (підтвердження email, скидання пароля) пишуться
у `var/mail/outbox.jsonl`, системний журнал — у `var/log/library.log`.

Демо-дані з простроченими видачами для перевірки вручну:

```bash
python tests/seed_demo.py --reset
```

## Перевірка

| Що | Команда |
|---|---|
| Усі тести застосунку | `python -m pytest` |
| Контракт валідний і пов'язаний із SRS | `python tests/api/lint_contract.py` |
| Кожна вимога SRS має тести й вони зелені | `python tests/verify_requirements.py` |
| Контрактні сценарії проти mock (лаб. №4) | `python tests/api/mock_server.py`, потім `python tests/api/run.py` |
| Оновити матрицю простежуваності | `python tests/update_traceability.py` |

## Структура

| Тека | Вміст |
|---|---|
| `spec/` | SRS (`srs.md`), контракт OpenAPI (`openapi.yaml`), адендуми (`addendum-*.md`) |
| `src/library/` | реалізація (FastAPI, SQLite через SQLAlchemy) |
| `tests/app/` | тести застосунку (pytest); `tests/api/` — інструменти контракту й mock |
| `plan/` | тікети, ризики, ролі, матриця простежуваності |
| `logs/` | рішення контрольних точок (gate), звіти запусків, верифікація й валідація |
| `docs/` | опис дизайну API, стек, інструкція з валідації, конвенція комітів |

## Процес

Кожна зміна поведінки: вимога (SRS або адендум) → тест, що падає (`test:`) → рішення gate
(`logs/*gate*.md`) → реалізація (`feat:`) → рефакторинг без зміни поведінки (`refactor:`).
Конвенція комітів — `docs/commit-convention.md`; простежуваність «вимога → тест → реалізація» —
`plan/traceability.md`.
