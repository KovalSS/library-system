"""Синхронізує багтрекер (GitHub Issues + дошка «Library System SDD») з результатами лаб. №5.

    python plan/sync_tracker_lab5.py            # лише показати, що буде зроблено
    python plan/sync_tracker_lab5.py --apply    # виконати (потрібен gh з авторизацією)

1. Створює тікети адендумів LS-41…LS-50 і баг, знайдений на валідації, додає їх на дошку.
2. Для кожного виконаного тікета додає коментар із доказом (коміт, звіт) і закриває його.
   За `plan/workflow.md` статус Done виставляє лише людина — тому скрипт запускає студент.
3. Дописує нові номери в `plan/issue-map.md`.
Повторний запуск безпечний: наявні тікети знаходяться за префіксом «LS-NN» у назві.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

APPLY = "--apply" in sys.argv
ROOT = Path(__file__).resolve().parent
OWNER, PROJECT = "KovalSS", "2"
sys.stdout.reconfigure(encoding="utf-8")

# Нові тікети: (тип, назва) — з plan/tickets.md
NEW = {
    "LS-41": ("Addendum", "Відмова у видачі читачу із заборгованістю (REQ-F-051)"),
    "LS-42": ("Test", "Тести відмови боржнику, AC-1…AC-7, BDD 8.6"),
    "LS-43": ("Gate", "TEST-GATE-5: огляд тестів адендуму REQ-F-051"),
    "LS-44": ("Feature", "Перевірка заборгованості при видачі"),
    "LS-45": ("Verification", "Регресія та верифікація адендуму REQ-F-051"),
    "LS-46": ("Addendum", "Рекомендації без уже отриманих видань (REQ-F-052)"),
    "LS-47": ("Test", "Тести виключення отриманих видань, AC-1…AC-5"),
    "LS-48": ("Gate", "TEST-GATE-6: огляд тестів адендуму REQ-F-052"),
    "LS-49": ("Feature", "Виключення отриманих видань із рекомендацій"),
    "LS-50": ("Verification", "Регресія та верифікація адендуму REQ-F-052"),
}
BUG_TITLE = "BUG: пошук читача за ПІБ кирилицею повертає порожній список"
BUG_BODY = """Знайдено на валідації людиною (сценарій V-2, `logs/validation.md`).

**Кроки:** `GET /readers?q=Ольга` (бібліотекар).
**Очікувано:** знайдено «Ольга Шевчук» (контракт `listReaders`: «підрядок у ПІБ»).
**Фактично:** порожній список — SQLite `lower()` змінює регістр лише латиниці.
**Вплив:** бібліотекар не може знайти читача для видачі (REQ-F-018).

**Виправлено за TDD:** тест, що відтворює дефект, `03899ec`; виправлення `1ce5433`;
повторна перевірка валідатором — пройдено."""

# Доказ виконання для кожного тікета
EVIDENCE = {
    "LS-02": "Стек і каркас: `docs/stack.md`, `76c9e02`, `f612954`, `eb9be13`",
    "LS-03": "Тести (Red): `c930dd2`", "LS-04": "Тести (Red): `4bc2e4c`", "LS-05": "Тести (Red): `af38b50`",
    "LS-06": "Тести (Red): `7dcbacb`", "LS-07": "Тести (Red): `0b588cd`, `2c3cd32`",
    "LS-08": "Рішення GO: `logs/test-gate-2.md`, `03151be`",
    "LS-09": "Реалізація (Green): `24d4402`", "LS-10": "Реалізація (Green): `207b4ce`",
    "LS-11": "Реалізація (Green): `80d074f`", "LS-12": "Реалізація (Green): `b6dd6c0`",
    "LS-13": "Реалізація (Green): `c7283db`, `b9d7a37`",
    "LS-14": "Регресія й контрольний запуск: `logs/stage-2-run.md`, `914e81a`",
    "LS-15": "Тести (Red): `5683112`", "LS-16": "Тести (Red): `2f04841`", "LS-17": "Тести (Red): `8c481ed`",
    "LS-18": "Рішення GO (посилений): `logs/test-gate-3.md`, `d9077cd`",
    "LS-19": "Реалізація (Green): `c84c51b`", "LS-20": "Реалізація (Green): `c84c51b`",
    "LS-21": "Реалізація (Green): `c84c51b`",
    "LS-22": "Регресія й контрольний запуск: `logs/stage-3-run.md`, `d689b7a`",
    "LS-23": "Рішення GO: `logs/stage-gate-3.md`, `1cfd716`",
    "LS-24": "Тести (Red): `0d3f670`", "LS-25": "Тести (Red): `e92e1c9`", "LS-26": "Тести (Red): `3425533`",
    "LS-27": "Тести (Red): `06ab105`", "LS-28": "Тести (Red): `db1fc43`",
    "LS-29": "Рішення GO: `logs/test-gate-4.md`, `6e08dd5`",
    "LS-30": "Реалізація (Green): `9aba0f4`", "LS-31": "Реалізація (Green): `93b095c`",
    "LS-32": "Реалізація (Green): `80cac27`", "LS-33": "Реалізація (Green): `889ab92`",
    "LS-34": "Реалізація (Green): `a4c8188`",
    "LS-35": "Регресія й контрольний запуск: `logs/stage-4-run.md`, `8c1d61b`",
    "LS-36": "Верифікація: `logs/verification.md`, `logs/verification-matrix.md`",
    "LS-37": "Валідація людиною: `logs/validation.md`",
    "LS-38": "Матриця простежуваності: `plan/traceability.md` (`50b9769`), README",
    "LS-39": "Підсумкове рішення GO: `logs/lab5-final-gate.md`, `c72ebfb`",
    "LS-40": "Рішення: продовження скасовано; SRS оновлено `797d24b`",
    "LS-41": "Адендум `spec/addendum-loan-refusal-for-debtors.md` (`53fa408`); SPEC-ADDENDUM-GATE GO `2b60a6b`",
    "LS-42": "Тести (Red): `f96e593`", "LS-43": "Рішення GO: `logs/test-gate-5.md`, `f9fee24`",
    "LS-44": "Реалізація (Green): `fcd81f9`; рефакторинг `28f2d40`, `c198eaf`",
    "LS-45": "Регресія: `logs/addendum-run.md`, `c62d90d`",
    "LS-46": "Адендум `spec/addendum-recommendations-exclude-received.md` (`b92f6c7`); SPEC-ADDENDUM-GATE-2 GO `51d0492`",
    "LS-47": "Тести (Red): `1a7b512`", "LS-48": "Рішення GO: `logs/test-gate-6.md`, `d57e34c`",
    "LS-49": "Реалізація (Green): `4643956`; рефакторинг `332f31e`",
    "LS-50": "Регресія: `logs/addendum-2-run.md`, `8b79553`",
}


def gh(*args) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def act(description, *args):
    print(("ВИКОНУЮ  " if APPLY else "БУДЕ     ") + description)
    return gh(*args) if APPLY else ""


def main():
    issues = json.loads(gh("issue", "list", "--state", "all", "--limit", "200", "--json", "number,title,state,url"))
    by_ls = {m.group(1): i for i in issues if (m := re.match(r"(LS-\d+)", i["title"]))}
    bug = next((i for i in issues if i["title"] == BUG_TITLE), None)

    created = {}
    for ls, (kind, title) in NEW.items():
        if ls not in by_ls:
            url = act(f"створити {ls} [{kind}] {title}", "issue", "create", "--title", f"{ls} [{kind}] {title}",
                      "--label", kind.lower(), "--body", f"Тікет лаб. №5, див. `plan/tickets.md`.\n\n{EVIDENCE[ls]}").strip()
            if url:
                act(f"додати {ls} на дошку", "project", "item-add", PROJECT, "--owner", OWNER, "--url", url)
                created[ls] = url.rsplit("/", 1)[-1]
    if bug is None:
        url = act("створити баг: " + BUG_TITLE, "issue", "create", "--title", BUG_TITLE, "--label", "bug",
                  "--body", BUG_BODY).strip()
        if url:
            act("додати баг на дошку", "project", "item-add", PROJECT, "--owner", OWNER, "--url", url)
            bug = {"number": int(url.rsplit("/", 1)[-1]), "state": "OPEN"}

    if APPLY:
        issues = json.loads(gh("issue", "list", "--state", "all", "--limit", "200", "--json", "number,title,state"))
        by_ls = {m.group(1): i for i in issues if (m := re.match(r"(LS-\d+)", i["title"]))}
    for ls, evidence in EVIDENCE.items():
        issue = by_ls.get(ls)
        if issue is None:
            print(f"БУДЕ     закрити {ls} після створення")
            continue
        if issue["state"] == "OPEN":
            act(f"закрити #{issue['number']} {ls}: {evidence}", "issue", "close", str(issue["number"]),
                "--comment", f"Виконано в лаб. №5. {evidence}")
    if bug and bug.get("state") == "OPEN":
        act(f"закрити баг #{bug['number']}", "issue", "close", str(bug["number"]),
            "--comment", "Виправлено й перевірено повторно (див. опис).")

    if APPLY and created:
        mapping = ROOT / "issue-map.md"
        text = mapping.read_text(encoding="utf-8")
        text = re.sub(r"\| LS-41…LS-50 \|[^\n]*\n", "", text)
        text = text.rstrip("\n") + "\n" + "".join(f"| {ls} | #{n} |\n" for ls, n in created.items())
        mapping.write_text(text, encoding="utf-8")
        print("Оновлено plan/issue-map.md")


if __name__ == "__main__":
    main()
