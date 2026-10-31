"""Верифікація: кожна вимога SRS -> тести, що її перевіряють, -> результат прогону.

    python tests/verify_requirements.py [--report logs/verification-matrix.md]

Тест пов'язується з вимогами за позначкою `# --- REQ-...` над ним; якщо позначки немає —
за ідентифікаторами в описі модуля. Скорочення на зразок «REQ-F-018, 019» і діапазони
«REQ-F-043...046» розгортаються.
"""
import argparse
import ast
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests" / "app"
# Вимоги, які свідомо не перевіряються автоматичним тестом (обґрунтування — в логах верифікації).
NOT_AUTOMATED = {
    "REQ-F-022": "скасовано рішенням LS-40",
    "REQ-NF-004": "веб-інтерфейсу немає; перевіряється людиною на валідації",
}


def expand_ids(text: str) -> set[str]:
    """REQ-ідентифікатори з тексту, включно зі скороченнями «REQ-F-018, 019» і діапазонами «043...046»."""
    ids = set()
    for match in re.finditer(r"REQ-(F|NF)-(\d{3})((?:\s*(?:,|…|\.\.\.)\s*\d{3})*)", text):
        kind, first, rest = match.groups()
        numbers = [int(first)]
        for sep, number in re.findall(r"\s*(,|…|\.\.\.)\s*(\d{3})", rest):
            numbers.extend(range(numbers[-1] + 1, int(number) + 1) if sep != "," else [int(number)])
        ids.update(f"REQ-{kind}-{n:03d}" for n in numbers)
    return ids


def requirements_by_test() -> dict[str, set[str]]:
    mapping = {}
    for path in sorted(TESTS.glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        module_ids = expand_ids(ast.get_docstring(ast.parse(source)) or "")
        current = None
        for line in source.splitlines():
            if line.startswith("# --- "):
                current = expand_ids(line) or None
            match = re.match(r"def (test_\w+)\(", line)
            if match:
                mapping[f"{path.stem}::{match.group(1)}"] = current or module_ids
    return mapping


def run_tests(junit: Path) -> dict[str, bool]:
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:logging", f"--junitxml={junit}"],
                   cwd=ROOT, capture_output=True)
    results = defaultdict(lambda: True)
    for case in ET.parse(junit).iter("testcase"):
        name = f"{case.get('classname').split('.')[-1]}::{case.get('name').split('[')[0]}"
        results[name] &= case.find("failure") is None and case.find("error") is None
    return results


def srs_requirements() -> list[str]:
    srs = (ROOT / "spec" / "srs.md").read_text(encoding="utf-8")
    return sorted(set(re.findall(r"\| \*\*(REQ-(?:F|NF)-\d{3})\*\* \|", srs)),
                  key=lambda r: (r.startswith("REQ-NF"), r))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report")
    args = parser.parse_args()

    results = run_tests(ROOT / "var" / "junit.xml")
    covering = defaultdict(list)
    for test, ids in requirements_by_test().items():
        for req in ids:
            covering[req].append(test)

    rows, failed = [], []
    for req in srs_requirements():
        tests = covering.get(req, [])
        passed = sum(results[t] for t in tests)
        if req in NOT_AUTOMATED:
            verdict = f"— ({NOT_AUTOMATED[req]})"
        elif not tests:
            verdict = "НЕМАЄ ТЕСТІВ"
            failed.append(req)
        elif passed == len(tests):
            verdict = "OK"
        else:
            verdict = f"FAIL ({len(tests) - passed})"
            failed.append(req)
        rows.append((req, len(tests), passed, verdict))

    total = len(results)
    green = sum(results.values())
    print(f"Тестів: {green}/{total} зелені")
    for req, count, passed, verdict in rows:
        print(f"{req:11} тестів {count:3}  пройшло {passed:3}  {verdict}")
    print("Не верифіковано:", ", ".join(failed) if failed else "немає")

    if args.report:
        lines = ["# Матриця верифікації: вимога SRS → тести → результат", "",
                 f"Згенеровано `python tests/verify_requirements.py`. Тестів: **{green}/{total}** зелені.", "",
                 "| Вимога | Тестів | Пройшло | Результат |", "|---|---|---|---|"]
        lines += [f"| {req} | {count} | {passed} | {verdict} |" for req, count, passed, verdict in rows]
        lines += ["", f"Не верифіковано: {', '.join(failed) if failed else 'немає'}.", ""]
        Path(args.report).write_text("\n".join(lines), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
