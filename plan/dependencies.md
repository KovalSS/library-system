# Схема залежностей між тікетами

Скорочена схема: тікети одного етапу й типу об'єднано в один блок. Жовтий — Gate, зелений — Test, синій — Feature, фіолетовий — Verification, червоний — Validation, сірий — Documentation, помаранчевий — Addendum. Повний перелік зв'язків: `plan/tickets.md` (стовпець «Blocked by»).

```mermaid
flowchart TD
    G01["LS-01<br/>PLAN-GATE"] --> D02["LS-02<br/>Каркас"]
    D02 --> T2["LS-03…07<br/>Тести ядра"]
    T2 --> G08["LS-08<br/>TEST-GATE-2"]
    G08 --> F2["LS-09…13<br/>Реалізація ядра"]
    F2 --> V14["LS-14<br/>Верифікація"]

    A40["LS-40<br/>Addendum REQ-F-022"] --> T3
    V14 --> T3["LS-15…17<br/>Тести: видача, бронювання, штрафи"]
    V14 --> T4["LS-24…28<br/>Тести: пошук, звіти, інше"]
    T3 --> G18["LS-18<br/>TEST-GATE-3 посилений"]
    G18 --> F3["LS-19…21<br/>Видача, бронювання, штрафи"]
    F3 --> V22["LS-22<br/>Верифікація"]
    V22 --> G23["LS-23<br/>STAGE-GATE-3"]

    T4 --> G29["LS-29<br/>TEST-GATE-4"]
    G29 --> F4["LS-30…34<br/>Реалізація решти"]
    G23 --> F4
    F4 --> V35["LS-35<br/>Верифікація"]
    V35 --> V36["LS-36<br/>Наскрізна верифікація"]
    V36 --> VAL["LS-37<br/>Валідація"]
    V36 --> D38["LS-38<br/>Документація"]
    VAL --> G39["LS-39<br/>RELEASE-GATE"]
    D38 --> G39

    style G01 fill:#ffe9a3,stroke:#555,color:#111
    style G08 fill:#ffe9a3,stroke:#555,color:#111
    style G18 fill:#ffe9a3,stroke:#555,color:#111
    style G23 fill:#ffe9a3,stroke:#555,color:#111
    style G29 fill:#ffe9a3,stroke:#555,color:#111
    style G39 fill:#ffe9a3,stroke:#555,color:#111
    style T2 fill:#b8e6b8,stroke:#555,color:#111
    style T3 fill:#b8e6b8,stroke:#555,color:#111
    style T4 fill:#b8e6b8,stroke:#555,color:#111
    style F2 fill:#bcd6f7,stroke:#555,color:#111
    style F3 fill:#bcd6f7,stroke:#555,color:#111
    style F4 fill:#bcd6f7,stroke:#555,color:#111
    style V14 fill:#e5d4f5,stroke:#555,color:#111
    style V22 fill:#e5d4f5,stroke:#555,color:#111
    style V35 fill:#e5d4f5,stroke:#555,color:#111
    style V36 fill:#e5d4f5,stroke:#555,color:#111
    style VAL fill:#f8c4c4,stroke:#555,color:#111
    style D02 fill:#e5e7eb,stroke:#555,color:#111
    style D38 fill:#e5e7eb,stroke:#555,color:#111
    style A40 fill:#ffd7a8,stroke:#555,color:#111
```
