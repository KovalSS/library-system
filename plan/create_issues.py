"""Створює GitHub Issues з таблиці plan/tickets.md (потрібен gh з авторизацією).

Запуск:  python plan/create_issues.py [--dry-run]
Крок 1 створює Issues з міткою типу, крок 2 дописує до описів
"Blocked by: #N" вже з реальними номерами. Результат: plan/issue-map.md.
"""
import re
import subprocess
import sys
from pathlib import Path

DRY = "--dry-run" in sys.argv
ROOT = Path(__file__).resolve().parent
TYPE_LABEL = {
    "Gate": "gate", "Documentation": "documentation", "Test": "test",
    "Feature": "feature", "Verification": "verification",
    "Validation": "validation", "Specification": "specification",
    "Addendum": "addendum",
}
EXECUTOR = {
    "Gate": "Людина (рішення GO/REVISE не делегується агенту)",
    "Validation": "Людина (валідація не делегується агенту)",
    "Addendum": "Спільно, рішення за людиною",
    "Specification": "Спільно, рішення за людиною",
    "Test": "Переважно агент; перегляд людиною перед Gate",
    "Feature": "Переважно агент; перегляд diff людиною",
    "Verification": "Спільно",
    "Documentation": "Агент; вибір стеку за людиною",
}

rows = []
for line in (ROOT / "tickets.md").read_text(encoding="utf-8").splitlines():
    if not line.startswith("| LS-"):
        continue
    c = [x.strip() for x in line.strip().strip("|").split("|")]
    deps = []
    for tok in re.split(r"\s*,\s*", c[4]):
        m = re.fullmatch(r"(?:LS-)?(\d+)…(\d+)", tok)
        if m:
            deps += [f"LS-{n:02d}" for n in range(int(m[1]), int(m[2]) + 1)]
        elif re.fullmatch(r"(?:LS-)?\d+", tok):
            deps.append(f"LS-{int(tok.replace('LS-', '')):02d}")
    rows.append(dict(id=c[0], type=c[1], title=c[2], req=c[3], deps=deps))
def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True,
                          check=True, encoding="utf-8").stdout.strip()

def body(r, nums):
    deps = ", ".join(f"#{nums[d]} ({d})" if d in nums else d for d in r["deps"]) or "—"
    return (f"**Тип:** {r['type']}\n\n**Вимоги / джерело:** {r['req']}\n\n"
            f"**Blocked by:** {deps}\n\n**Виконавець:** {EXECUTOR[r['type']]}\n\n"
            f"Джерело планування: `plan/tickets.md` ({r['id']}).")

nums = {}
for r in rows:
    title = f"{r['id']} [{r['type']}] {r['title']}"
    if DRY:
        print(title, "| label:", TYPE_LABEL[r["type"]], "| deps:", r["deps"])
        continue
    url = gh("issue", "create", "--title", title, "--body", body(r, {}),
             "--label", TYPE_LABEL[r["type"]])
    nums[r["id"]] = int(url.rstrip("/").split("/")[-1])
    print(r["id"], "->", url)

if not DRY:
    for r in rows:
        gh("issue", "edit", str(nums[r["id"]]), "--body", body(r, nums))
    out = "# Відповідність LS-ID та GitHub Issues\n\n| LS-ID | Issue |\n|---|---|\n"
    out += "".join(f"| {k} | #{v} |\n" for k, v in nums.items())
    (ROOT / "issue-map.md").write_text(out, encoding="utf-8")
    print("Готово: plan/issue-map.md")
