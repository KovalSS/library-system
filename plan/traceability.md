# Простежуваність вимог до тікетів, API operations, реалізації й тестів (лаб. №3–5)

Доповнює матрицю `spec/srs.md` (розд. 9): для кожної вимоги вказано тікети
ланцюжка `Вимога → Test → Gate → Feature → Verification`. Ідентифікатори
`LS-NN` — з `plan/tickets.md`; у таблиці нижче вказано номери GitHub Issues `#N` (відповідність у `plan/issue-map.md`). Наскрізні тікети: LS-01 (PLAN-GATE), LS-02 (каркас),
LS-36 (наскрізна верифікація), LS-37 (валідація), LS-38, LS-39.

Колонку «API operation» додано в лаб. №4: це `operationId` із `spec/openapi.yaml`
(джерело — розширення `x-req-ids` кожної операції). Вимоги без операції:
REQ-F-022 скасовано рішенням LS-40; REQ-NF-001, 002, 004, 005 — наскрізні властивості
системи, не операції API (REQ-NF-005 відображено полем `requestId` у моделі `Error`).

Колонки «Реалізація» і «Тести» додано в лаб. №5 і **генеруються** `python tests/update_traceability.py`
з коду (маршрути, позначки `# --- REQ-…` у тестах): разом із SRS вони замикають ланцюжок
`вимога → критерій прийняття → тест → реалізація` (SRS, розд. 1.4). Рядки REQ-F-051 і
REQ-F-052 додано адендумами (`spec/addendum-*.md`); їхні тікети LS-41…LS-50 ведуться лише
в `plan/tickets.md`, без GitHub Issues (група A1, A2).

| ID вимоги | Група | Test | Gate | Feature | Verification | API operation | Реалізація | Тести |
|---|---|---|---|---|---|---|---|---|
| **REQ-F-001** | G1 | #4 | #9 | #10 | #15, #37 | `listGenres`, `createEdition`, `getEdition` | `routers/catalog.py` | `test_catalog.py` |
| **REQ-F-002** | G1 | #4 | #9 | #10 | #15, #37 | `createEdition`, `updateEdition` | `routers/catalog.py` | `test_catalog.py` |
| **REQ-F-003** | G1 | #4 | #9 | #10 | #15, #37 | `listGenres`, `createGenre`, `updateGenre` | `routers/catalog.py` | `test_catalog.py` |
| **REQ-F-004** | G1 | #4 | #9 | #10 | #15, #37 | `listCopies`, `createCopy` | `routers/catalog.py` | `test_catalog.py` |
| **REQ-F-005** | G1 | #4 | #9 | #10 | #15, #37 | `createCopy` | `routers/catalog.py` | `test_catalog.py` |
| **REQ-F-006** | G1 | #4 | #9 | #10 | #15, #37 | `updateCopy` | `routers/catalog.py` | `test_catalog.py` |
| **REQ-F-007** | G1 | #4 | #9 | #10 | #15, #37 | `listCopies`, `writeOffCopy` | `routers/catalog.py` | `test_catalog.py` |
| **REQ-F-008** | G1 | #4 | #9 | #10 | #15, #37 | `getEdition`, `updateEdition` | `routers/catalog.py` | `test_catalog.py` |
| **REQ-F-009** | G2 | #5 | #9 | #11 | #15, #37 | `login` | `app.py`, `routers/auth.py` | `test_accounts.py` |
| **REQ-F-010** | G2 | #5 | #9 | #11 | #15, #37 | `login`, `listAdministrators`, `createAdministrator` | `routers/accounts.py`, `routers/auth.py` | `test_accounts.py` |
| **REQ-F-011** | G2 | #5 | #9 | #11 | #15, #37 | `updateAdministrator` | `routers/accounts.py` | `test_accounts.py` |
| **REQ-F-012** | G2 | #5 | #9 | #11 | #15, #37 | `login`, `listAdministrators`, `updateAdministrator` | `routers/accounts.py`, `routers/auth.py` | `test_accounts.py` |
| **REQ-F-013** | G2 | #5 | #9 | #11 | #15, #37 | `login`, `listLibrarians`, `createLibrarian` | `routers/accounts.py`, `routers/auth.py` | `test_accounts.py` |
| **REQ-F-014** | G2 | #5 | #9 | #11 | #15, #37 | `login`, `listLibrarians`, `updateLibrarian` | `routers/accounts.py`, `routers/auth.py` | `test_accounts.py` |
| **REQ-F-015** | G3 | #6 | #9 | #12 | #15, #37 | `registerReader` | `routers/readers.py` | `test_reader_registration.py` |
| **REQ-F-016** | G3 | #6 | #9 | #12 | #15, #37 | `login`, `confirmReaderEmail` | `routers/auth.py`, `routers/readers.py` | `test_reader_registration.py` |
| **REQ-F-017** | G3 | #6 | #9 | #12 | #15, #37 | `registerReader` | `routers/readers.py` | `test_reader_registration.py` |
| **REQ-F-018** | G6 | #16 | #19 | #20 | #23, #37 | `listReaders`, `createLoan` | `routers/loans.py`, `routers/readers.py` | `test_loans.py` |
| **REQ-F-019** | G6 | #16 | #19 | #20 | #23, #37 | `createLoan` | `routers/loans.py` | `test_loans.py` |
| **REQ-F-020** | G6 | #16 | #19 | #20 | #23, #37 | `returnLoan` | `routers/loans.py` | `test_fines.py`, `test_loans.py` |
| **REQ-F-021** | G6 | #16 | #19 | #20 | #23, #37 | `listReaderLoans`, `getLoan` | `routers/loans.py` | `test_loans.py` |
| **REQ-F-022** | G6 | #16 | #19 | #20 | #23, #37 | — (скасовано, LS-40) | — (не реалізується) | скасовано (LS-40) |
| **REQ-F-023** | G7 | #17 | #19 | #21 | #23, #37 | `listReaderReservations`, `createReservation` | `routers/reservations.py` | `test_reservations.py` |
| **REQ-F-024** | G7 | #17 | #19 | #21 | #23, #37 | `listReaderReservations`, `createReservation` | `routers/reservations.py` | `test_reservations.py` |
| **REQ-F-025** | G7 | #17 | #19 | #21 | #23, #37 | `listReaderReservations` | `circulation.py`, `routers/reservations.py` | `test_reservations.py` |
| **REQ-F-026** | G7 | #17 | #19 | #21 | #23, #37 | `listReaderReservations`, `returnLoan` | `circulation.py`, `routers/loans.py`, `routers/reservations.py` | `test_reservations.py` |
| **REQ-F-027** | G8 | #18 | #19 | #22 | #23, #37 | `getReaderFines`, `createLoan`, `getLoan`, `returnLoan` | `circulation.py`, `routers/fines.py`, `routers/loans.py` | `test_fines.py` |
| **REQ-F-028** | G8 | #18 | #19 | #22 | #23, #37 | `getReaderFines`, `getLoan`, `returnLoan` | `circulation.py`, `routers/fines.py`, `routers/loans.py` | `test_fines.py` |
| **REQ-F-029** | G8 | #18 | #19 | #22 | #23, #37 | `listReaderLoans`, `getLoan` | `circulation.py`, `routers/loans.py` | `test_fines.py` |
| **REQ-F-030** | G8 | #18 | #19 | #22 | #23, #37 | `payReaderFines` | `routers/fines.py` | `test_fines.py` |
| **REQ-F-031** | G8 | #18 | #19 | #22 | #23, #37 | `getReaderFines` | `routers/fines.py` | `test_fines.py` |
| **REQ-F-032** | G11 | #27 | #30 | #33 | #36, #37 | `listReaderRecommendations` | `routers/recommendations.py` | `test_recommendations.py` |
| **REQ-F-033** | G11 | #27 | #30 | #33 | #36, #37 | `listReaderRecommendations` | `routers/recommendations.py` | `test_recommendations.py` |
| **REQ-F-034** | G11 | #27 | #30 | #33 | #36, #37 | `listReaderRecommendations` | `routers/recommendations.py` | `test_recommendations.py` |
| **REQ-F-035** | G12 | #28 | #30 | #34 | #36, #37 | `listReaderNotifications` | `notifications.py`, `routers/notifications.py` | `test_notifications.py` |
| **REQ-F-036** | G12 | #28 | #30 | #34 | #36, #37 | `listReaderReservations`, `listReaderNotifications` | `notifications.py`, `routers/notifications.py`, `routers/reservations.py` | `test_notifications.py` |
| **REQ-F-037** | G12 | #28 | #30 | #34 | #36, #37 | `listReaderNotifications` | `notifications.py`, `routers/notifications.py` | `test_notifications.py` |
| **REQ-F-038** | G12 | #28 | #30 | #34 | #36, #37 | `listReaderNotifications` | `routers/notifications.py` | `test_notifications.py` |
| **REQ-F-039** | G10 | #26 | #30 | #32 | #36, #37 | `getTopEditionsReport` | `routers/reports.py` | `test_reports.py` |
| **REQ-F-040** | G10 | #26 | #30 | #32 | #36, #37 | `getDebtorsReport` | `routers/reports.py` | `test_debtor_refusal.py`, `test_reports.py` |
| **REQ-F-041** | G10 | #26 | #30 | #32 | #36, #37 | `getLibraryLoadReport` | `routers/reports.py` | `test_reports.py` |
| **REQ-F-042** | G10 | #26 | #30 | #32 | #36, #37 | `getTopEditionsReport`, `getDebtorsReport`, `getLibraryLoadReport` | `routers/reports.py` | `test_reports.py` |
| **REQ-F-043** | G9 | #25 | #30 | #31 | #36, #37 | `searchEditions` | `routers/catalog.py` | `test_search.py` |
| **REQ-F-044** | G9 | #25 | #30 | #31 | #36, #37 | `searchEditions` | `routers/catalog.py` | `test_search.py` |
| **REQ-F-045** | G9 | #25 | #30 | #31 | #36, #37 | `searchEditions` | `routers/catalog.py` | `test_search.py` |
| **REQ-F-046** | G9 | #25 | #30 | #31 | #36, #37 | `listGenres`, `searchEditions`, `getEdition` | `routers/catalog.py` | `test_search.py` |
| **REQ-F-047** | G4 | #7 | #9 | #13 | #15, #37 | `requestPasswordReset`, `resetPassword` | `routers/auth.py` | `test_auth_privacy.py` |
| **REQ-F-048** | G4 | #7 | #9 | #13 | #15, #37 | `login` | `routers/auth.py` | `test_auth_privacy.py` |
| **REQ-F-049** | G5 | #8 | #9 | #14 | #15, #37 | `listAuditLogEntries` | `audit.py`, `routers/audit_log.py` | `test_audit_log.py`, `test_loans.py` |
| **REQ-F-050** | G4 | #7 | #9 | #13 | #15, #37 | `listReaders`, `getReader` | `routers/readers.py` | `test_auth_privacy.py` |
| **REQ-F-051** | A1 | LS-42 | LS-43 | LS-44 | LS-45, LS-37 | `createLoan` | `circulation.py`, `routers/loans.py` | `test_debtor_refusal.py` |
| **REQ-F-052** | A2 | LS-47 | LS-48 | LS-49 | LS-50, LS-37 | `listReaderRecommendations` | `routers/recommendations.py` | `test_recommendations.py` |
| **REQ-NF-001** | G13 | #29 | #30 | #35 | #36, #37 | — (наскрізна, не операція API) | `app.py (журнал запитів)` | `test_nonfunctional.py` |
| **REQ-NF-002** | G13 | #29 | #30 | #35 | #36, #37 | — (наскрізна, не операція API) | `backup.py` | `test_nonfunctional.py` |
| **REQ-NF-003** | G4 | #7 | #9 | #13 | #15, #37 | `login`, `resetPassword`, `getReader` | `routers/auth.py`, `routers/readers.py`, `security.py` | `test_auth_privacy.py` |
| **REQ-NF-004** | G13 | #29 | #30 | #35 | #36, #37 | — (наскрізна, не операція API) | — (веб-інтерфейсу немає) | перевіряє людина (`logs/validation.md`) |
| **REQ-NF-005** | G5 | #8 | #9 | #14 | #15, #37 | — (наскрізна, не операція API) | `app.py`, `logging_setup.py` | `test_audit_log.py`, `test_loans.py`, `test_system_log.py` |

