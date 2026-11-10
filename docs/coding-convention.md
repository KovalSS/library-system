# Конвенція оформлення коду (Coding Convention)

Цей документ визначає правила оформлення та структурування програмного коду для проєкту «Бібліотечна інформаційна система». Конвенція базується на офіційних рекомендаціях екосистеми Python та враховує специфіку розробки за методологією SDD/TDD.

---

## 1. Базові стандарти

1. **Стиль коду:** [PEP 8](https://peps.python.org/pep-0008/) — офіційний стиль програмування на Python.
2. **Документування коду:** [PEP 257](https://peps.python.org/pep-0257/) — конвенція рядків документації (docstrings).
3. **Анотації типів:** [PEP 484](https://peps.python.org/pep-0484/), [PEP 585](https://peps.python.org/pep-0585/) та [PEP 604](https://peps.python.org/pep-0604/) (використання вбудованих типів та синтаксису `X | Y` для об'єднань і `None`).
4. **Конвенція комітів:** [docs/commit-convention.md](file:///D:/library-system/docs/commit-convention.md) (`spec:`, `test:`, `feat:`, `refactor:`, `fix:`, `docs:`, `gate:`).

---

## 2. Іменування та відповідність глосарію

Усі назви сутностей, полів моделей, функцій та ендпоінтів повинні чітко відповідати англомовній термінології **Глосарію предметної області** (`spec/srs.md`, розділ 3):

| Термін предметної області | Сутність у коді (клас / модель) | Поля / параметри |
|---|---|---|
| **Видання** (Edition) | `Edition` | `title`, `author`, `year`, `isbn`, `genre_id`, `price` |
| **Екземпляр** (Copy) | `Copy` | `inventory_number`, `location`, `status` (`available`, `issued`, `reserved`) |
| **Читач** (Reader) | `Account(role="reader")` | `email`, `full_name`, `phone`, `birth_date` |
| **Бібліотекар** (Librarian) | `Account(role="librarian")` | `email`, `full_name`, `role` |
| **Адміністратор** (Admin) | `Account(role="admin")` | `email`, `full_name`, `role` |
| **Головний адміністратор** (Chief Admin) | `Account(role="chief_admin")` / `ChiefAdmin` | створюється під час ініціалізації системи |
| **Видача** (Loan) | `Loan` | `reader_id`, `copy_id`, `edition_id`, `issued_on`, `due_on`, `returned_on` |
| **Бронювання / Черга** (Reservation) | `Reservation` | `reader_id`, `edition_id`, `copy_id`, `status` (`queued`, `ready`, `fulfilled`, `cancelled`), `pickup_deadline` |
| **Штраф** (Fine) | `FineState`, `FinePayment` | `overdue_days`, `amount`, `fine_paid`, `fine_rate_percent`, `compensated` |
| **Заборгованість** (Debt) | `Debt` | `overdue_loans`, `unpaid` |
| **Аудит-лог** (Audit Log) | `AuditEntry` | `actor_id`, `actor_role`, `action`, `object_type`, `object_id`, `occurred_at` |
| **Жанр** (Genre) | `Genre` | `name` |

### Правила регістру (Case Conventions)
* **Класи, типи, Pydantic-схеми, SQLAlchemy-моделі:** `PascalCase` (`LoanCreate`, `FineState`, `DailyBackup`).
* **Функції, методи, змінні, параметри:** `snake_case` (`create_loan`, `reader_debt`, `fine_state`).
* **Константи:** `UPPER_SNAKE_CASE` (`DEFAULT_ITERATIONS`, `TERM_WITH_QUEUE`, `PICKUP_PERIOD`).
* **Модулі та пакети:** короткі назви в нижньому регістрі `lowercase` (`circulation.py`, `editions.py`).
* **Зовнішні контракти API (OpenAPI JSON):** `camelCase` для ключів JSON (`readerId`, `dueDate`, `accessToken`), як затверджено в `spec/openapi.yaml`.

---

## 3. Форматування коду та структура файлів

1. **Відступи:** 4 пробіли (жодних символів табуляції).
2. **Довжина рядка:** рекомендована межа — до 120 символів.
3. **Порожні рядки:**
   * 2 порожні рядки між функціями та класами верхнього рівня.
   * 1 порожній рядок між методами всередині класу або логічними блоками у функції.
4. **Імпорти:** групуються за стандартом PEP 8 з одним порожнім рядком між групами:
   1. Стандартна бібліотека Python (`datetime`, `os`, `pathlib`, `uuid`).
   2. Сторонні бібліотеки (`fastapi`, `pydantic`, `sqlalchemy`, `yaml`).
   3. Внутрішні модулі проєкту (`library.db`, `library.errors`, `library.deps`).

---

## 4. Документування (Docstrings, PEP 257)

Кожен модуль, клас і публічна функція повинні містити структурований docstring:
* **Модуль:** перший рядок фіксує призначення модуля та перелік реалізованих вимог SRS (наприклад, `REQ-F-018...021`).
* **Публічна функція / метод роутера:**
  * Короткий опис призначення операції.
  * Посилання на вимогу SRS або адендум (якщо релевантно).
  * Параметри (`Args:` або лаконічний опис вхідних даних).
  * Результат (`Returns:`).
  * Можливі винятки та коди помилок (`Raises: ApiError`).
* Коментарі всередині функцій використовуються виключно для пояснення нетривіальних бізнес-рішень або обмежень алгоритму, а не очевидного коду.

---

## 5. Обробка помилок та контракт API

* Усі клієнтські помилки та відмови бізнес-логіки генеруються через єдиний тип винятку: `ApiError(status_code, code, message)` (`src/library/errors.py`).
* Відповіді про помилки суворо відповідають схемі `Error` з `spec/openapi.yaml`:
  ```json
  {
    "code": "debtor_cannot_borrow",
    "message": "Читач має заборгованість: 1 прострочена книга, 50.00 грн несплачених штрафів."
  }
  ```
* Заборонено перехоплювати винятки «мовчки» без логування або повернення інформативної відповіді.

---

## 6. Системне логування (REQ-NF-005)

* Логування ведеться через спільний логер `library` (`src/library/logging_setup.py`).
* Кожен HTTP-запит логується на рівні `INFO` з фіксацією методу, шляху, статусу відповіді, тривалості та `requestId`.
* Непередбачені винятки логуються на рівні `ERROR` зі збереженням стек-трейсу (`exc_info=True`).
* Бізнес-відмови (наприклад, відмова у видачі книги боржнику) логуються на рівні `WARNING`.
