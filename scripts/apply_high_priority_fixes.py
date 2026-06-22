"""Apply only the HIGH priority field suggestions from manual_fix_plan.md."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from create_manual_fix_plan import HIGH_FIXES


ROOT = Path(__file__).resolve().parents[1]
JSONL_PATH = ROOT / "data" / "processed" / "rag_documents.jsonl"
AUDIT_PATH = ROOT / "data" / "reports" / "rag_document_audit.json"
REPORT_PATH = ROOT / "data" / "reports" / "high_priority_fix_report.md"

IDENTITY_FIELDS = {"id", "title", "category", "subcategory"}
LIST_FIELDS = {"kosullar", "adimlar", "istisnalar", "ilgili_dokumanlar"}
ALLOWED_CATEGORIES = {
    "SIPARIS",
    "IADE",
    "ODEME",
    "KARGO_TESLIMAT",
    "HESAP_GUVENLIK",
    "KAMPANYA_PUAN",
}


def load_rows() -> list[dict]:
    return [
        json.loads(line)
        for line in JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def validate(rows: list[dict]) -> None:
    assert len(rows) == 70
    assert len({row["id"] for row in rows}) == 70
    assert len({row["subcategory"] for row in rows}) == 70
    assert all(row["category"] in ALLOWED_CATEGORIES for row in rows)
    ids = {row["id"] for row in rows}
    assert all(
        reference in ids
        for row in rows
        for reference in row["ilgili_dokumanlar"]
    )
    for row in rows:
        for field, value in row.items():
            expected = list if field in LIST_FIELDS else str
            assert isinstance(value, expected), f"{row['id']} {field}"


def main() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    audit_high = {
        row["id"]
        for row in audit["weak_or_repetitive_documents"]["records"]
        if row["review_level"] == "HIGH"
    }
    assert audit_high == set(HIGH_FIXES)
    assert sum(len(fields) for fields in HIGH_FIXES.values()) == 43

    before = load_rows()
    validate(before)
    after = deepcopy(before)
    by_id = {row["id"]: row for row in after}
    changes = []

    for record_id, fields in HIGH_FIXES.items():
        row = by_id[record_id]
        for field, detail in fields.items():
            assert field not in IDENTITY_FIELDS
            old_value = deepcopy(row[field])
            new_value = deepcopy(detail["oneri"])
            expected = list if field in LIST_FIELDS else str
            assert isinstance(new_value, expected)
            assert new_value not in ("", [])
            row[field] = new_value
            changes.append(
                {
                    "id": record_id,
                    "title": row["title"],
                    "category": row["category"],
                    "field": field,
                    "old_value": old_value,
                    "new_value": new_value,
                }
            )

    validate(after)

    # Strict scope check: only the 43 planned fields may differ.
    planned = {
        (record_id, field)
        for record_id, fields in HIGH_FIXES.items()
        for field in fields
    }
    actual = set()
    before_by_id = {row["id"]: row for row in before}
    after_by_id = {row["id"]: row for row in after}
    for record_id in before_by_id:
        old = before_by_id[record_id]
        new = after_by_id[record_id]
        assert old.keys() == new.keys()
        for field in old:
            if old[field] != new[field]:
                actual.add((record_id, field))
    assert actual == planned, {
        "unexpected": sorted(actual - planned),
        "missing": sorted(planned - actual),
    }

    for record_id in HIGH_FIXES:
        old = before_by_id[record_id]
        new = after_by_id[record_id]
        for field in IDENTITY_FIELDS | {"ilgili_dokumanlar"}:
            assert old[field] == new[field]

    with JSONL_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        for row in after:
            handle.write(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            )

    persisted = load_rows()
    validate(persisted)
    assert persisted == after

    report = [
        "# HIGH Priority Düzeltme Raporu",
        "",
        "## Özet",
        "",
        f"- Uygulama zamanı: `{datetime.now().astimezone().isoformat(timespec='seconds')}`",
        "- Güncellenen doküman: **13**",
        "- Güncellenen alan: **43**",
        "- Değiştirilmeyen doküman: **57**",
        "- Kaynak plan: `data/reports/manual_fix_plan.md`",
        "- Güncellenen dosya: `data/processed/rag_documents.jsonl`",
        "",
        "Yalnızca HIGH priority kayıtlar için planda önerilen alanlar değiştirildi. ID, title, category, subcategory ve ilgili doküman referansları korundu.",
        "",
        "## Doküman bazında değişiklikler",
        "",
        "| ID | Başlık | Kategori | Güncellenen alanlar |",
        "|---|---|---|---|",
    ]
    for record_id, fields in HIGH_FIXES.items():
        row = after_by_id[record_id]
        field_list = ", ".join(f"`{field}`" for field in fields)
        report.append(
            f"| `{record_id}` | {row['title']} | `{row['category']}` | {field_list} |"
        )

    report.extend(["", "## Uygulanan değerler", ""])
    for record_id, fields in HIGH_FIXES.items():
        row = after_by_id[record_id]
        report.extend([f"### {row['title']} — `{record_id}`", ""])
        for field in fields:
            report.extend([f"#### `{field}`", ""])
            value = row[field]
            if isinstance(value, list):
                report.extend(f"- {item}" for item in value)
            else:
                report.append(f"> {value}")
            report.append("")

    report.extend(
        [
            "## Doğrulama",
            "",
            "- JSONL satır sayısı: **70**",
            "- Geçerli JSON kayıt sayısı: **70**",
            "- Benzersiz ID sayısı: **70**",
            "- Benzersiz subcategory sayısı: **70**",
            "- Geçersiz category: **0**",
            "- Kırık ilgili doküman referansı: **0**",
            "- Plan dışı değiştirilen alan: **0**",
            "- HIGH dışındaki değiştirilen kayıt: **0**",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
    print(
        f"HIGH_FIXES_OK documents={len(HIGH_FIXES)} fields={len(changes)} "
        f"report={REPORT_PATH}"
    )


if __name__ == "__main__":
    main()
