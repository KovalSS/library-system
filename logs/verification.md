# Крок 7 лаби, частина 1: верифікація реалізації

**Дата:** 31.10.2026. **Питання верифікації:** чи відповідає реалізація затвердженим
артефактам — SRS (`spec/srs.md`), актуальному контракту (`spec/openapi.yaml`) і
адендуму (`spec/addendum-loan-refusal-for-debtors.md`)? Перевірки автоматизовані й
відтворювані командами нижче.

## 1. Відповідність SRS

Команда: `python tests/verify_requirements.py --report logs/verification-matrix.md`.

| Показник | Значення |
|---|---|
| Вимог у SRS | 57 (52 REQ-F + 5 REQ-NF) |
| Верифіковано тестами | **55**, усі тести зелені |
| Свідомо без автоматичного тесту | 2: REQ-F-022 (скасовано, LS-40), REQ-NF-004 (немає веб-інтерфейсу — на валідацію) |
| Не верифіковано | **0** |
| Тестів | 244 функції, 263 запуски (з параметризацією) |

Повна таблиця «вимога → кількість тестів → результат» — `logs/verification-matrix.md`.

**Знахідка верифікації:** сім тестів оформлення видачі були позначені у файлі як
REQ-F-019 замість REQ-F-018, через що матриця показала для REQ-F-018 лише 1 тест.
Виправлено позначку без зміни перевірок (`4cf04e6`); тепер REQ-F-018 — 8 тестів.

### BDD-сценарії SRS

| Сценарій | Тест | Результат |
|---|---|---|
| 8.1 Видача книги | `test_loans.py::test_bdd_8_1_issue_available_copy_without_queue` | OK |
| 8.2 Повернення з простроченням (45 грн) | `test_fines.py::test_bdd_8_2_return_after_3_overdue_days_charges_45` | OK |
| 8.3 Бронювання вільного / зайнятого | `test_reservations.py::test_bdd_8_3_*` (2 тести) | OK |
| 8.4 Реєстрація читача | `test_reader_registration.py` (реєстрація → лист → підтвердження → вхід) | OK |
| 8.5 Вичерпання ліміту штрафу (200 грн) | `test_fines.py::test_bdd_8_5_fine_reaches_limit_and_loan_is_compensated` | OK |
| 8.6 Відмова боржнику (адендум) | `test_debtor_refusal.py::test_bdd_8_6_refused_then_paid_then_issued` | OK |

## 2. Відповідність актуальному контракту OpenAPI

| Перевірка | Команда / місце | Результат |
|---|---|---|
| Контракт валідний і пов'язаний із SRS | `python tests/api/lint_contract.py` | OpenAPI 3.1.0; 51 вимога пов'язана з операціями |
| Реалізовано рівно операції контракту | `tests/app/test_contract_routes.py` | 38 з 38, зайвих немає |
| Кожна відповідь у тестах відповідає схемі | `tests/app/contract.py` (у кожному тесті з `contract(...)`) | без розбіжностей |
| Опублікований опис `/openapi.json`, `/docs` = контракт | `test_published_api_description_is_the_approved_contract` | OK |
| Mock-сценарії лаб. №4 відтворюють контракт | `python tests/api/run.py` проти `mock_server.py` | 36/36 позитивних, 34/34 негативних |

## 3. Відповідність адендуму REQ-F-051

| Критерій | Тест | Результат |
|---|---|---|
| AC-1 прострочена неповернута видача | `test_reader_with_overdue_unreturned_loan_is_refused` | OK |
| AC-2 несплачений штраф | `test_reader_with_unpaid_fine_is_refused` | OK |
| AC-3 компенсована без оплати | `test_reader_with_unpaid_compensated_loan_is_refused` | OK |
| AC-4 після оплати й повернення | `test_reader_who_paid_and_returned_everything_can_borrow_again`, `test_paying_the_fine_is_not_enough_while_overdue_book_is_kept` | OK |
| AC-5 поточна непрострочена видача | `test_reader_with_current_loan_can_borrow_more`, `test_due_date_itself_is_not_yet_overdue` | OK |
| AC-6 запис у журналі | `test_refusal_is_written_to_system_log` | OK |
| AC-7 порядок перевірок | `test_debt_is_reported_even_when_copy_is_unavailable` | OK |
| Одне визначення боржника | `test_refused_readers_are_exactly_the_debtors_report` | OK |

## 4. Системний журнал за контрольними запусками

| Запуск | ERROR | Записів без `requestId` | Звіт |
|---|---|---|---|
| Етап 2 | 0 | 0 | `logs/stage-2-run.md` |
| Етап 3 | 0 | 0 | `logs/stage-3-run.md` |
| Етап 4 | 0 | 0 | `logs/stage-4-run.md` |
| Після рефакторингу (крок 3) | 0 | 0 | `logs/refactoring-base.md` |
| Після адендуму (кроки 5, 6) | 0 | 0 | `logs/addendum-run.md`, `logs/refactoring-addendum.md` |

## 5. Розбіжності й обмеження, виявлені верифікацією

| # | Що | Оцінка |
|---|---|---|
| V1 | `spec/idea.md` задає «стандартний термін 14 днів», реалізація — 14 або 30 днів | Не дефект: SRS (REQ-F-019) уточнила задум на SPEC-GATE; реалізація відповідає SRS. Варто підтвердити на валідації |
| V2 | Читачеві рекомендуються вже прочитані видання | Відповідає SRS (TEST-GATE-4, T22); корисність — питання валідації |
| V3 | Дії за часом (прострочення, штраф, автоскасування броні, сповіщення) не показати на живому сервері без очікування | Перевірено тестами з керованим годинником; для валідації — демо-дані з минулими датами (`tests/seed_demo.py`) |
| V4 | Справжньої пошти немає: листи з токенами пишуться у `var/mail/outbox.jsonl` | Свідоме рішення для локального розгортання (`docs/stack.md`) |
| V5 | Продуктивність (REQ-NF-001) перевірено в тестовому середовищі, не на цільовому обладнанні | TEST-GATE-4, T29 |

**Висновок верифікації:** реалізація відповідає SRS, актуальному контракту й адендуму;
невиконаних вимог немає. Пункти V1, V2 і REQ-NF-004 передано на валідацію людиною.
