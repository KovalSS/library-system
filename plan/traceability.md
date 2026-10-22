# Простежуваність вимог до тікетів та API operations (лаб. №3, оновлено в лаб. №4)

Доповнює матрицю `spec/srs.md` (розд. 9): для кожної вимоги вказано тікети
ланцюжка `Вимога → Test → Gate → Feature → Verification`. Ідентифікатори
`LS-NN` — з `plan/tickets.md`; у таблиці нижче вказано номери GitHub Issues `#N` (відповідність у `plan/issue-map.md`). Наскрізні тікети: LS-01 (PLAN-GATE), LS-02 (каркас),
LS-36 (наскрізна верифікація), LS-37 (валідація), LS-38, LS-39.

Колонку «API operation» додано в лаб. №4: це `operationId` із `spec/openapi.yaml`
(джерело — розширення `x-req-ids` кожної операції). Вимоги без операції:
REQ-F-022 скасовано рішенням LS-40; REQ-NF-001, 002, 004, 005 — наскрізні властивості
системи, не операції API (REQ-NF-005 відображено полем `requestId` у моделі `Error`).

| ID вимоги | Група | Test | Gate | Feature | Verification | API operation |
|---|---|---|---|---|---|---|
| **REQ-F-001** | G1 | #4 | #9 | #10 | #15, #37 | `listGenres`, `createEdition`, `getEdition` |
| **REQ-F-002** | G1 | #4 | #9 | #10 | #15, #37 | `createEdition`, `updateEdition` |
| **REQ-F-003** | G1 | #4 | #9 | #10 | #15, #37 | `listGenres`, `createGenre`, `updateGenre` |
| **REQ-F-004** | G1 | #4 | #9 | #10 | #15, #37 | `listCopies`, `createCopy` |
| **REQ-F-005** | G1 | #4 | #9 | #10 | #15, #37 | `createCopy` |
| **REQ-F-006** | G1 | #4 | #9 | #10 | #15, #37 | `updateCopy` |
| **REQ-F-007** | G1 | #4 | #9 | #10 | #15, #37 | `listCopies`, `writeOffCopy` |
| **REQ-F-008** | G1 | #4 | #9 | #10 | #15, #37 | `getEdition`, `updateEdition` |
| **REQ-F-009** | G2 | #5 | #9 | #11 | #15, #37 | `login` |
| **REQ-F-010** | G2 | #5 | #9 | #11 | #15, #37 | `login`, `listAdministrators`, `createAdministrator` |
| **REQ-F-011** | G2 | #5 | #9 | #11 | #15, #37 | `updateAdministrator` |
| **REQ-F-012** | G2 | #5 | #9 | #11 | #15, #37 | `login`, `listAdministrators`, `updateAdministrator` |
| **REQ-F-013** | G2 | #5 | #9 | #11 | #15, #37 | `login`, `listLibrarians`, `createLibrarian` |
| **REQ-F-014** | G2 | #5 | #9 | #11 | #15, #37 | `login`, `listLibrarians`, `updateLibrarian` |
| **REQ-F-015** | G3 | #6 | #9 | #12 | #15, #37 | `registerReader` |
| **REQ-F-016** | G3 | #6 | #9 | #12 | #15, #37 | `login`, `confirmReaderEmail` |
| **REQ-F-017** | G3 | #6 | #9 | #12 | #15, #37 | `registerReader` |
| **REQ-F-018** | G6 | #16 | #19 | #20 | #23, #37 | `listReaders`, `createLoan` |
| **REQ-F-019** | G6 | #16 | #19 | #20 | #23, #37 | `createLoan` |
| **REQ-F-020** | G6 | #16 | #19 | #20 | #23, #37 | `returnLoan` |
| **REQ-F-021** | G6 | #16 | #19 | #20 | #23, #37 | `listReaderLoans`, `getLoan` |
| **REQ-F-022** | G6 | #16 | #19 | #20 | #23, #37 | — (скасовано, LS-40) |
| **REQ-F-023** | G7 | #17 | #19 | #21 | #23, #37 | `listReaderReservations`, `createReservation` |
| **REQ-F-024** | G7 | #17 | #19 | #21 | #23, #37 | `listReaderReservations`, `createReservation` |
| **REQ-F-025** | G7 | #17 | #19 | #21 | #23, #37 | `listReaderReservations` |
| **REQ-F-026** | G7 | #17 | #19 | #21 | #23, #37 | `listReaderReservations`, `returnLoan` |
| **REQ-F-027** | G8 | #18 | #19 | #22 | #23, #37 | `getReaderFines`, `createLoan`, `getLoan`, `returnLoan` |
| **REQ-F-028** | G8 | #18 | #19 | #22 | #23, #37 | `getReaderFines`, `getLoan`, `returnLoan` |
| **REQ-F-029** | G8 | #18 | #19 | #22 | #23, #37 | `listReaderLoans`, `getLoan` |
| **REQ-F-030** | G8 | #18 | #19 | #22 | #23, #37 | `payReaderFines` |
| **REQ-F-031** | G8 | #18 | #19 | #22 | #23, #37 | `getReaderFines` |
| **REQ-F-032** | G11 | #27 | #30 | #33 | #36, #37 | `listReaderRecommendations` |
| **REQ-F-033** | G11 | #27 | #30 | #33 | #36, #37 | `listReaderRecommendations` |
| **REQ-F-034** | G11 | #27 | #30 | #33 | #36, #37 | `listReaderRecommendations` |
| **REQ-F-035** | G12 | #28 | #30 | #34 | #36, #37 | `listReaderNotifications` |
| **REQ-F-036** | G12 | #28 | #30 | #34 | #36, #37 | `listReaderReservations`, `listReaderNotifications` |
| **REQ-F-037** | G12 | #28 | #30 | #34 | #36, #37 | `listReaderNotifications` |
| **REQ-F-038** | G12 | #28 | #30 | #34 | #36, #37 | `listReaderNotifications` |
| **REQ-F-039** | G10 | #26 | #30 | #32 | #36, #37 | `getTopEditionsReport` |
| **REQ-F-040** | G10 | #26 | #30 | #32 | #36, #37 | `getDebtorsReport` |
| **REQ-F-041** | G10 | #26 | #30 | #32 | #36, #37 | `getLibraryLoadReport` |
| **REQ-F-042** | G10 | #26 | #30 | #32 | #36, #37 | `getTopEditionsReport`, `getDebtorsReport`, `getLibraryLoadReport` |
| **REQ-F-043** | G9 | #25 | #30 | #31 | #36, #37 | `searchEditions` |
| **REQ-F-044** | G9 | #25 | #30 | #31 | #36, #37 | `searchEditions` |
| **REQ-F-045** | G9 | #25 | #30 | #31 | #36, #37 | `searchEditions` |
| **REQ-F-046** | G9 | #25 | #30 | #31 | #36, #37 | `listGenres`, `searchEditions`, `getEdition` |
| **REQ-F-047** | G4 | #7 | #9 | #13 | #15, #37 | `requestPasswordReset`, `resetPassword` |
| **REQ-F-048** | G4 | #7 | #9 | #13 | #15, #37 | `login` |
| **REQ-F-049** | G5 | #8 | #9 | #14 | #15, #37 | `listAuditLogEntries` |
| **REQ-F-050** | G4 | #7 | #9 | #13 | #15, #37 | `listReaders`, `getReader` |
| **REQ-NF-001** | G13 | #29 | #30 | #35 | #36, #37 | — (наскрізна, не операція API) |
| **REQ-NF-002** | G13 | #29 | #30 | #35 | #36, #37 | — (наскрізна, не операція API) |
| **REQ-NF-003** | G4 | #7 | #9 | #13 | #15, #37 | `login`, `resetPassword`, `getReader` |
| **REQ-NF-004** | G13 | #29 | #30 | #35 | #36, #37 | — (наскрізна, не операція API) |
| **REQ-NF-005** | G5 | #8 | #9 | #14 | #15, #37 | — (наскрізна, не операція API) |
