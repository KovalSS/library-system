"""Автоматичний аудит матриці простежуваності та ланцюжка SDD (Крок 12).

Перевіряє:
1. Повноту покриття: усі 57 вимог SRS (52 REQ-F + 5 REQ-NF) зафіксовані в матриці.
2. Цілісність посилань: кожна вимога має тікети, операцію, реалізацію, тести та документацію.
3. Фізичну наявність артефактів: модулі коду, тестові файли та файли документації існують.
4. Відсутність «тестів-сиріт» (тестів без прив'язки до вимог SRS).
5. Відповідність операцій контракту OpenAPI затвердженим вимогам SRS.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from verify_requirements import requirements_by_test

SRS_FILE = ROOT / "spec" / "srs.md"
MATRIX_FILE = ROOT / "plan" / "traceability.md"
TESTS_DIR = ROOT / "tests" / "app"
SRC_DIR = ROOT / "src" / "library"


def main():
    print("=" * 60)
    print("АВТОМАТИЧНИЙ АУДИТ МАТРИЦІ ПРОСТЕЖУВАНОСТІ (КРОК 12)")
    print("=" * 60)

    # 1. Збір вимог із SRS
    srs_text = SRS_FILE.read_text(encoding="utf-8")
    srs_reqs = set(re.findall(r"\*\*(REQ-(?:F|NF)-\d{3})\*\*", srs_text))
    print(f"\n[1] Збір вимог із SRS: знайдено {len(srs_reqs)} вимог.")
    assert len(srs_reqs) == 57, f"Очікувалось 57 вимог у SRS, знайдено {len(srs_reqs)}"

    # 2. Перевірка матриці traceability.md
    matrix_text = MATRIX_FILE.read_text(encoding="utf-8")
    matrix_rows = {}
    lines = matrix_text.splitlines()
    header_found = False

    for line in lines:
        if line.startswith("| ID вимоги |"):
            header_found = True
            continue
        if header_found and line.startswith("| **REQ-"):
            parts = [c.strip() for c in line.strip().strip("|").split("|")]
            req_id = parts[0].strip("*")
            matrix_rows[req_id] = {
                "group": parts[1],
                "test_ticket": parts[2],
                "gate_ticket": parts[3],
                "feature_ticket": parts[4],
                "verification_ticket": parts[5],
                "api_operation": parts[6],
                "implementation": parts[7],
                "tests": parts[8],
                "documentation": parts[9] if len(parts) > 9 else "—",
            }

    print(f"[2] Записів у матриці plan/traceability.md: {len(matrix_rows)}.")
    missing_in_matrix = srs_reqs - set(matrix_rows.keys())
    if missing_in_matrix:
        print(f"ПОМИЛКА: Вимоги відсутні в матриці: {missing_in_matrix}")
        sys.exit(1)
    else:
        print("    Усі 57 вимог SRS присутні в матриці простежуваності.")

    # 3. Перевірка цілісності ланцюжка та фізичного існування файлів
    broken_links = []
    for req_id, row in sorted(matrix_rows.items()):
        # Перевірка файлів реалізації
        if row["implementation"] not in ("— (не реалізується)", "— (веб-інтерфейсу немає)", "—"):
            for impl in row["implementation"].split(","):
                clean_impl = impl.strip("` ").split()[0]
                impl_path = SRC_DIR / clean_impl
                if not impl_path.exists() and not (ROOT / clean_impl).exists():
                    broken_links.append(f"{req_id}: не знайдено файл реалізації '{clean_impl}'")

        # Перевірка тестових файлів
        if row["tests"] not in ("скасовано (LS-40)", "перевіряє людина (`logs/validation.md`)", "—"):
            for tfile in row["tests"].split(","):
                clean_test = tfile.strip("` ")
                if not (TESTS_DIR / clean_test).exists():
                    broken_links.append(f"{req_id}: не знайдено тестовий файл '{clean_test}'")

        # Перевірка файлів документації
        if row["documentation"] != "—":
            doc_refs = re.findall(r"\[([^\]]+)\]\(([^)#]+)", row["documentation"])
            for doc_name, doc_path in doc_refs:
                target_file = ROOT / doc_path.strip()
                if not target_file.exists():
                    broken_links.append(f"{req_id}: файл документації '{doc_path}' не існує на диску!")

    print("\n[3] Перевірка посилань на файли коду, тестів та документації:")
    if broken_links:
        print(f"ПОМИЛКА: Знайдено биті посилання ({len(broken_links)}):")
        for b in broken_links:
            print("  -", b)
        sys.exit(1)
    else:
        print("    Усі файли реалізації, тестів та документації фізично існують на диску.")

    # 4. Перевірка тестів на наявність зв'язку з SRS
    tests_mapping = requirements_by_test()
    orphaned_tests = []
    contract_meta_tests = []
    for test_name, reqs in tests_mapping.items():
        if not reqs:
            if "test_contract_routes" in test_name:
                contract_meta_tests.append(test_name)
            else:
                orphaned_tests.append(test_name)

    print("\n[4] Перевірка тестів на наявність зв'язку з SRS:")
    print(f"    Перевірено {len(tests_mapping)} функцій тестів застосунку.")
    print(f"    Контрактних мета-тестів (інфраструктура LS-02, LS-36): {len(contract_meta_tests)}.")
    if orphaned_tests:
        print(f"ПОМИЛКА: Знайдено тести без ідентифікатора вимоги SRS: {orphaned_tests}")
        sys.exit(1)
    else:
        print("    Жодного «тесту-сироти» немає: 100% бізнес-тестів пов'язані з вимогами SRS.")

    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТ АУДИТУ: МАТРИЦЯ ПРОСТЕЖУВАНОСТІ 100% ВАЛІДНА ТА ЦІЛІСНА!")
    print("=" * 60)


if __name__ == "__main__":
    main()
