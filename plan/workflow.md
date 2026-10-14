# Життєвий цикл задачі з ролями

Статуси відповідають колонкам дошки GitHub Project «Library System SDD».

Ролі проєкту:
- **Студент** — людина: власник проєкту, ухвалює рішення, перевіряє, закриває.
- **Агент** — кодинговий агент (Claude Code): виконує технічну роботу, пропонує, готує зведення; рішень Gate і валідації не ухвалює (`plan/roles.md`).

```mermaid
flowchart TD
    START((" ")) -->|"створення<br/>Студент, Агент"| BL["Backlog"]
    BL -->|"є незавершена залежність<br/>Студент, Агент"| BK["Blocked"]
    BK -->|"блокер завершено<br/>Студент, Агент"| BL
    BL -->|"взято в роботу<br/>Студент, Агент"| IP["In Progress"]
    IP -->|"нова залежність<br/>Студент, Агент"| BK
    IP -->|"роботу виконано<br/>Агент, Студент"| IR["In Review"]
    IR -->|"є зауваження<br/>лише Студент"| IP
    IR -->|"перевірку пройдено<br/>лише Студент"| DN["Done"]
    DN -->|"повторне відкриття, REVISE<br/>лише Студент"| IP
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
| Створення (→ Backlog) | Студент, Агент | Студент, Агент | Студент, Агент | Студент, Агент |
| Backlog → In Progress | Студент, Агент | Студент, Агент | Студент (агент лише готує зведення) | Студент, Агент |
| In Progress → In Review | Агент, Студент | Агент, Студент | Студент | Агент (пропонує), Студент |
| In Review → Done | **Студент** | **Студент** | **Студент** (рішення GO/REVISE не делегується) | **Студент** |
| In Review → In Progress | Студент | Студент | Студент | Студент |
| Done → In Progress | Студент | Студент | Студент | Студент |

Правило: статус **Done** виставляє лише студент. Агент не закриває тікети
самостійно, а рішення Gate і валідацію не ухвалює ні за яких умов.
