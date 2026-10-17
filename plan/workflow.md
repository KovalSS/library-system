# Життєвий цикл задачі з ролями

Статуси відповідають колонкам дошки GitHub Project «Library System SDD».

Ролі проєкту:
- **Людина** — власник проєкту: ухвалює рішення, перевіряє, закриває.
- **Агент** — кодинговий агент (Claude Code): виконує технічну роботу, пропонує, готує зведення; рішень Gate і валідації не ухвалює (`plan/roles.md`).

```mermaid
flowchart TD
    START((" ")) -->|"створення<br/>Людина, Агент"| BL["Backlog"]
    BL -->|"є незавершена залежність<br/>Людина, Агент"| BK["Blocked"]
    BK -->|"блокер завершено<br/>Людина, Агент"| BL
    BL -->|"взято в роботу<br/>Людина, Агент"| IP["In Progress"]
    IP -->|"нова залежність<br/>Людина, Агент"| BK
    IP -->|"роботу виконано<br/>Агент, Людина"| IR["In Review"]
    IR -->|"є зауваження<br/>лише Людина"| IP
    IR -->|"перевірку пройдено<br/>лише Людина"| DN["Done"]
    DN -->|"повторне відкриття, REVISE<br/>лише Людина"| IP
    DN --> END((" "))

    style START fill:#fff,stroke:#fff
    style END fill:#555,stroke:#fff,stroke-width:3px
    style BL fill:#e5e7eb,stroke:#555,color:#111
    style BK fill:#f8c4c4,stroke:#a33,color:#111
    style IP fill:#ffe9a3,stroke:#a80,color:#111
    style IR fill:#bcd6f7,stroke:#36a,color:#111
    style DN fill:#b8e6b8,stroke:#3a3,color:#111
```

## Перехід за типами тікетів

| Перехід | Test, Feature, Documentation | Verification | Gate, Validation | Addendum, Specification |
|---|---|---|---|---|
| Створення (→ Backlog) | Людина, Агент | Людина, Агент | Людина, Агент | Людина, Агент |
| Backlog → In Progress | Людина, Агент | Людина, Агент | Людина (агент лише готує зведення) | Людина, Агент |
| In Progress → In Review | Агент, Людина | Агент, Людина | Людина | Агент (пропонує), Людина |
| In Review → Done | **Людина** | **Людина** | **Людина** (рішення GO/REVISE не делегується) | **Людина** |
| In Review → In Progress | Людина | Людина | Людина | Людина |
| Done → In Progress | Людина | Людина | Людина | Людина |

Правило: статус **Done** виставляє лише людина. Агент не закриває тікети
самостійно, а рішення Gate і валідацію не ухвалює ні за яких умов.
