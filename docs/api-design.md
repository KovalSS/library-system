# Проєктування REST API (лаб. №4)

Контракт: [`spec/openapi.yaml`](../spec/openapi.yaml) (OpenAPI 3.1). Вхід — затверджена
`spec/srs.md`, `plan/traceability.md`, рішення LS-40. Реалізації немає: у цій
роботі API лише проєктується та відтворюється mock-сервером; сервер — лаб. №5 (TDD).

## 1. Які вимоги доступні через REST API (крок 1)

Через API доступні 49 з 50 функціональних вимог (кожна пов'язана з операцією
через `x-req-ids`). Єдина виняткова — **REQ-F-022**: самостійне продовження
терміну скасовано рішенням LS-40, тому операції немає; після терміну діє лише
штраф REQ-F-027.

Частина вимог описує поведінку, що виконується системою без виклику клієнта; вони
спостерігаються через стани й поля ресурсів, а не через власну операцію:

| Вимога | Як відображено в API |
|---|---|
| REQ-F-009 (попередньо створений головний адміністратор) | Створюється при розгортанні; вхід — `login`, роль `chief_admin` |
| REQ-F-025, 026 (автоскасування броні, передача наступному в черзі) | Стани `Reservation`: `ready`, `queued`, `expired`; `returnLoan` передає екземпляр першому в черзі |
| REQ-F-035…037 (генерація сповіщень) | Читаються через `listReaderNotifications` (REQ-F-038) |
| REQ-F-027, 029 (штраф на льоту, автостатус) | Поля `Loan.fineAmount`, `Loan.overdueDays`, статус `compensated` |

Нефункціональні: REQ-NF-003 відображено в операціях (`x-req-ids`). REQ-NF-001, 002 і
004 (продуктивність, резервне копіювання, зручність інтерфейсу) не є операціями API:
кількість кроків інтерфейсу API довести не може. REQ-NF-005 відображено полем
`requestId` моделі `Error`. Винятки (REQ-F-022 і чотири REQ-NF) закодовано в
`tests/api/lint_contract.py`.

## 2. Ресурси предметної області (крок 2)

Назви ресурсів походять із глосарія SRS (розд. 3); URI — англійською (SRS 2.4:
інтерфейс англійською), назви в `kebab-case`, іменники в множині.

| Термін глосарія | Ресурс | Примітка |
|---|---|---|
| Видання | `/editions` | Бібліографічний запис; пошук, фільтрація, сортування |
| Екземпляр | `/editions/{id}/copies`, `/copies/{id}` | Створюється в межах видання; змінюється за власним id |
| Довідник жанрів | `/genres` | Керується адміністратором |
| Читач | `/readers` | Реєстрація публічна; персональні дані — `GET /readers/{id}` |
| Бібліотекар, Адміністратор | `/librarians`, `/administrators` | Окремі ресурси: різні права на створення |
| Видача | `/loans` | Дата повернення, ставка штрафу, штраф, статус |
| Бронювання, Черга | `/reservations` | Один ресурс: `ready` (екземпляр утримується) або `queued` (позиція) |
| Штраф | `/readers/{id}/fines`, `/readers/{id}/fine-payments` | Штраф — похідна величина видачі; оплата — окремий ресурс |
| Рекомендація | `/readers/{id}/recommendations` | Лише читання |
| Сповіщення | `/readers/{id}/notifications` | Лише читання |
| Аудит-лог | `/audit-log-entries` | Лише читання |
| Звіти | `/reports/top-editions`, `/reports/debtors`, `/reports/library-load` | Лише читання; CSV через `Accept: text/csv` |

Внутрішні деталі (таблиці БД, хеші паролів, журнал системного логування) не
розкриваються: `password` позначено `writeOnly`, ідентифікатори — UUID, а не
послідовні номери.

## 3. Конвенції URI та HTTP-методів (крок 3)

* `GET` — читання, безпечне й ідемпотентне; `POST` — створення ресурсу або дія
  без власного ресурсу (`/loans/{id}/return`, `/copies/{id}/write-off`);
  `PATCH` — часткова зміна; `PUT` та `DELETE` не використовуються.
* `DELETE` відсутній свідомо: акаунти деактивуються (`active: false`), екземпляри
  списуються зі збереженням історії (REQ-F-007, REQ-F-011).
* Дії, що змінюють стан, ніколи не виконуються через `GET` (підтвердження email —
  `POST /email-confirmations`).
* Колекції фільтруються query-параметрами; списки з великою кількістю елементів
  мають `page` / `pageSize` і відповідь `{items, page, pageSize, total}`.
* Дати — ISO 8601 (`date` для днів, `date-time` для моментів); суми — у гривнях.

## 4. Операції, ролі, REQ-ID і коди відповідей (кроки 4, 7)

Ролі: читач, бібліотекар, адмін (адміністратор нижчого рівня), гол. адмін
(головний адміністратор; має всі права адміністратора). Кожна операція в
специфікації має `x-req-ids` і `x-roles`; лінтер вимагає їх наявності.

| operationId | Метод і URI | Ролі | REQ-ID | Коди відповідей |
|---|---|---|---|---|
| `login` | `POST /auth/login` | без автентифікації | REQ-F-009, REQ-F-010, REQ-F-012, REQ-F-013, REQ-F-014, REQ-F-016, REQ-F-048, REQ-NF-003 | 200, 400, 401, 403, 423 |
| `requestPasswordReset` | `POST /auth/password-reset-requests` | без автентифікації | REQ-F-047 | 202, 400 |
| `resetPassword` | `POST /auth/password-resets` | без автентифікації | REQ-F-047, REQ-NF-003 | 204, 400 |
| `listReaders` | `GET /readers` | бібліотекар, адмін, гол. адмін | REQ-F-018, REQ-F-050 | 200, 400, 401, 403 |
| `registerReader` | `POST /readers` | без автентифікації | REQ-F-015, REQ-F-017 | 201, 400, 409 |
| `getReader` | `GET /readers/{readerId}` | читач, бібліотекар, адмін, гол. адмін | REQ-F-050, REQ-NF-003 | 200, 401, 403, 404 |
| `confirmReaderEmail` | `POST /email-confirmations` | без автентифікації | REQ-F-016 | 200, 400 |
| `listReaderLoans` | `GET /readers/{readerId}/loans` | читач, бібліотекар, адмін, гол. адмін | REQ-F-021, REQ-F-029 | 200, 400, 401, 403, 404 |
| `listReaderReservations` | `GET /readers/{readerId}/reservations` | читач, бібліотекар, адмін, гол. адмін | REQ-F-023, REQ-F-024, REQ-F-025, REQ-F-026, REQ-F-036 | 200, 400, 401, 403, 404 |
| `getReaderFines` | `GET /readers/{readerId}/fines` | читач, бібліотекар, адмін, гол. адмін | REQ-F-027, REQ-F-028, REQ-F-031 | 200, 401, 403, 404 |
| `payReaderFines` | `POST /readers/{readerId}/fine-payments` | бібліотекар | REQ-F-030 | 201, 400, 401, 403, 404, 409 |
| `listReaderRecommendations` | `GET /readers/{readerId}/recommendations` | читач, бібліотекар, адмін, гол. адмін | REQ-F-032, REQ-F-033, REQ-F-034 | 200, 401, 403, 404 |
| `listReaderNotifications` | `GET /readers/{readerId}/notifications` | читач, бібліотекар, адмін, гол. адмін | REQ-F-035, REQ-F-036, REQ-F-037, REQ-F-038 | 200, 400, 401, 403, 404 |
| `listGenres` | `GET /genres` | читач, бібліотекар, адмін, гол. адмін | REQ-F-001, REQ-F-003, REQ-F-046 | 200, 401 |
| `createGenre` | `POST /genres` | адмін, гол. адмін | REQ-F-003 | 201, 400, 401, 403 |
| `updateGenre` | `PATCH /genres/{genreId}` | адмін, гол. адмін | REQ-F-003 | 200, 400, 401, 403, 404 |
| `searchEditions` | `GET /editions` | читач, бібліотекар, адмін, гол. адмін | REQ-F-043, REQ-F-044, REQ-F-045, REQ-F-046 | 200, 400, 401 |
| `createEdition` | `POST /editions` | бібліотекар | REQ-F-001, REQ-F-002 | 201, 400, 401, 403, 409 |
| `getEdition` | `GET /editions/{editionId}` | читач, бібліотекар, адмін, гол. адмін | REQ-F-001, REQ-F-008, REQ-F-046 | 200, 401, 404 |
| `updateEdition` | `PATCH /editions/{editionId}` | бібліотекар | REQ-F-008, REQ-F-002 | 200, 400, 401, 403, 404, 409 |
| `listCopies` | `GET /editions/{editionId}/copies` | бібліотекар, адмін, гол. адмін | REQ-F-004, REQ-F-007 | 200, 401, 403, 404 |
| `createCopy` | `POST /editions/{editionId}/copies` | бібліотекар | REQ-F-004, REQ-F-005 | 201, 400, 401, 403, 404, 409 |
| `updateCopy` | `PATCH /copies/{copyId}` | бібліотекар | REQ-F-006 | 200, 400, 401, 403, 404, 409 |
| `writeOffCopy` | `POST /copies/{copyId}/write-off` | бібліотекар | REQ-F-007 | 200, 401, 403, 404, 409 |
| `listAdministrators` | `GET /administrators` | гол. адмін | REQ-F-010, REQ-F-012 | 200, 401, 403 |
| `createAdministrator` | `POST /administrators` | гол. адмін | REQ-F-010 | 201, 400, 401, 403, 409 |
| `updateAdministrator` | `PATCH /administrators/{administratorId}` | гол. адмін | REQ-F-011, REQ-F-012 | 200, 400, 401, 403, 404, 409 |
| `listLibrarians` | `GET /librarians` | адмін, гол. адмін | REQ-F-013, REQ-F-014 | 200, 401, 403 |
| `createLibrarian` | `POST /librarians` | адмін, гол. адмін | REQ-F-013 | 201, 400, 401, 403, 409 |
| `updateLibrarian` | `PATCH /librarians/{librarianId}` | адмін, гол. адмін | REQ-F-014 | 200, 400, 401, 403, 404, 409 |
| `createLoan` | `POST /loans` | бібліотекар | REQ-F-018, REQ-F-019, REQ-F-027 | 201, 400, 401, 403, 404, 409 |
| `getLoan` | `GET /loans/{loanId}` | читач, бібліотекар, адмін, гол. адмін | REQ-F-021, REQ-F-027, REQ-F-028, REQ-F-029 | 200, 401, 403, 404 |
| `returnLoan` | `POST /loans/{loanId}/return` | бібліотекар | REQ-F-020, REQ-F-026, REQ-F-027, REQ-F-028 | 200, 401, 403, 404, 409 |
| `createReservation` | `POST /reservations` | читач | REQ-F-023, REQ-F-024 | 201, 400, 401, 403, 404 |
| `getTopEditionsReport` | `GET /reports/top-editions` | бібліотекар, адмін, гол. адмін | REQ-F-039, REQ-F-042 | 200, 400, 401, 403 |
| `getDebtorsReport` | `GET /reports/debtors` | бібліотекар, адмін, гол. адмін | REQ-F-040, REQ-F-042 | 200, 401, 403 |
| `getLibraryLoadReport` | `GET /reports/library-load` | бібліотекар, адмін, гол. адмін | REQ-F-041, REQ-F-042 | 200, 400, 401, 403 |
| `listAuditLogEntries` | `GET /audit-log-entries` | адмін, гол. адмін | REQ-F-049 | 200, 400, 401, 403 |

## 5. Схеми даних (крок 5)

Усі схеми — у `components/schemas`. Основні: `Edition`, `Copy`, `Genre`, `Reader`,
`Account`, `Loan`, `Reservation`, `FineSummary`, `FinePayment`, `Recommendation`,
`Notification`, `AuditLogEntry`, три моделі звітів. Для кожного змінюваного
ресурсу є окрема схема вводу (`EditionInput`, `EditionUpdate`, `CopyInput`,
`ReaderRegistration` тощо), щоб клієнт не міг задати поля, які визначає система.

Ключові рішення, що випливають із SRS:

* `Loan.termDays` ∈ {14, 30} і `Loan.fineRatePercent` ∈ {1, 5} фіксуються при
  видачі за наявністю черги (REQ-F-019, REQ-F-027) і далі не змінюються.
* `Loan.fineAmount` і `overdueDays` обчислюються на льоту за поточною датою
  (REQ-F-027); значення не перевищує ціни книги (REQ-F-028).
* `Loan.status = compensated` відповідає «не повернуто, компенсовано повною
  вартістю» (REQ-F-029).
* `Reservation.status`: `ready` (2 дні, `pickupDeadline`), `queued`
  (`queuePosition`), `fulfilled`, `expired` (REQ-F-023…026).
* `Copy.status`: `available`, `issued`, `damaged`, `written_off`; вручну
  встановлюються лише `available` і `damaged`, решту виставляють операції видачі
  та списання (REQ-F-006).
* Оплата штрафу не приймає суму: система стягує повну заборгованість, тож
  часткова оплата неможлива за конструкцією (REQ-F-030).

## 6. Єдина модель помилки (крок 6)

Усі відповіді 4xx мають тіло `Error` (`code`, `message`, `details[]`, `requestId`).
`code` — закритий перелік, за яким клієнт розрізняє причини; `requestId` зіставляє
відповідь із системним журналом (REQ-NF-005).

| HTTP | Коли | `code` |
|---|---|---|
| 400 | Тіло чи query-параметри не відповідають схемі; `from` пізніше за `to`; недійсний або прострочений токен із листа | `validation_failed`, `invalid_token` |
| 401 | Немає або недійсний токен; невірний пароль | `unauthorized`, `invalid_credentials` |
| 403 | Немає права на дію; акаунт неактивний; акаунт головного адміністратора | `forbidden`, `account_inactive`, `protected_account` |
| 404 | Ресурс не знайдено, зокрема некоректний ідентифікатор у шляху | `not_found` |
| 409 | Дубль унікального значення або несумісний стан ресурсу | `duplicate_email`, `duplicate_isbn`, `duplicate_inventory_number`, `copy_state_conflict`, `copy_not_available`, `loan_already_closed`, `no_outstanding_fine` |
| 423 | Акаунт заблоковано на 15 хв (REQ-F-048); заголовок `Retry-After` | `account_locked` |

## 7. Нова поведінка, якої немає в SRS (крок 14)

Рішення, ухвалені під час проєктування й не виведені прямо з тексту SRS, оформлено
в [`logs/api-addendum-1.md`](../logs/api-addendum-1.md). Текст SRS не змінювався.

## 8. Перевірка контракту (кроки 9–13)

Увесь інструментарій — Python (Node не потрібен).

| Дія | Команда |
|---|---|
| Встановити залежності | `pip install -r requirements.txt` |
| Автоматична валідація контракту | `python tests/api/lint_contract.py` |
| Запустити mock без серверної реалізації (термінал 1) | `python tests/api/mock_server.py` |
| Виконати позитивні й негативні сценарії проти mock (термінал 2) | `python tests/api/run.py` |

Валідація складається з `openapi-spec-validator` (відповідність стандарту
OpenAPI 3.1) і правил проєкту: кожна операція має `operationId`, `summary`,
`description`, `x-req-ids` (формат `REQ-F-NNN` / `REQ-NF-NNN`, ID існує в SRS),
`x-roles` і хоча б одну відповідь 4xx; операція з query-параметрами чи тілом описує
400, з параметром шляху — 404; усі відповіді помилок посилаються на схему `Error`;
усі приклади відповідають своїм схемам.

Mock (`tests/api/mock_server.py`) керується лише специфікацією: знаходить операцію
за шляхом, перевіряє токен (401), ідентифікатор у шляху (404) і форму запиту (400)
та повертає приклад із
контракту. Стану й бізнес-логіки в ньому немає, тому він не є серверною реалізацією.

Сценарії (`tests/api/scenarios.py`, раннер `tests/api/run.py` на Python) перевіряють, що статус і тіло відповіді mock
описані в контракті та відповідають схемі, а для BDD 8.1–8.5 — що приклади
відтворюють числа зі специфікації (30 днів і 1%; 5% × 3 × 300 = 45 грн; межа 200 грн;
позиція в черзі). Звіт останнього запуску — `logs/api-scenarios-report.md`.

Обмеження mock: він повертає приклади з контракту й перевіряє форму запиту, але
не виконує бізнес-логіку (ролі, стан даних, розрахунок штрафу). Тому негативні
бізнес-сценарії (403, 404, 409, 423) вибираються заголовком `Prefer: code=…`, а
правильність самих правил перевірятиметься тестами в лаб. №5. Правила, що пов'язують
кілька полів (напр., `from` пізніше за `to`), схемою не виражаються, тому mock їх не
перевіряє; вони записані в описі операцій.
