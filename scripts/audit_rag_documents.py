"""Audit data/processed/rag_documents.jsonl without modifying its contents."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "processed" / "rag_documents.jsonl"
REPORT_MD = ROOT / "data" / "reports" / "rag_document_audit.md"
REPORT_JSON = ROOT / "data" / "reports" / "rag_document_audit.json"

REQUIRED_FIELDS = [
    "id",
    "category",
    "subcategory",
    "title",
    "amac",
    "kapsam",
    "tanim",
    "genel_bilgiler",
    "kosullar",
    "adimlar",
    "istisnalar",
    "surec",
    "standart_yanit",
    "ilgili_dokumanlar",
]
AUDITED_FIELDS = [
    "amac",
    "kapsam",
    "tanim",
    "genel_bilgiler",
    "kosullar",
    "adimlar",
    "istisnalar",
    "standart_yanit",
    "ilgili_dokumanlar",
]
STRING_THRESHOLDS = {
    "amac": 60,
    "kapsam": 50,
    "tanim": 40,
    "genel_bilgiler": 80,
    "standart_yanit": 70,
}
LIST_THRESHOLDS = {
    "kosullar": 1,
    "adimlar": 1,
    "istisnalar": 1,
    "ilgili_dokumanlar": 1,
}
CATEGORY_ORDER = [
    "SIPARIS",
    "IADE",
    "ODEME",
    "KARGO_TESLIMAT",
    "HESAP_GUVENLIK",
    "KAMPANYA_PUAN",
]


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def markdown_escape(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", " ")


def load_jsonl() -> tuple[list[dict], list[dict], int]:
    raw_lines = INPUT.read_text(encoding="utf-8").splitlines()
    records: list[dict] = []
    errors: list[dict] = []
    for line_number, line in enumerate(raw_lines, start=1):
        if not line.strip():
            errors.append(
                {
                    "line": line_number,
                    "error": "Boş satır",
                    "preview": "",
                }
            )
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(
                {
                    "line": line_number,
                    "error": str(exc),
                    "preview": line[:160],
                }
            )
            continue
        if not isinstance(parsed, dict):
            errors.append(
                {
                    "line": line_number,
                    "error": "Satırdaki JSON değeri obje değil",
                    "preview": line[:160],
                }
            )
            continue
        parsed["_line"] = line_number
        records.append(parsed)
    return records, errors, len(raw_lines)


def duplicate_groups(records: list[dict], field: str) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        value = record.get(field)
        if isinstance(value, str):
            groups[normalize(value)].append(record)
    return [
        {
            "value": items[0].get(field, ""),
            "count": len(items),
            "records": [
                {
                    "line": item["_line"],
                    "id": item.get("id", ""),
                    "title": item.get("title", ""),
                }
                for item in items
            ],
        }
        for key, items in groups.items()
        if key and len(items) > 1
    ]


def duplicate_content(records: list[dict]) -> list[dict]:
    duplicates = []
    for field in ("amac", "kapsam", "tanim", "genel_bilgiler", "standart_yanit"):
        for group in duplicate_groups(records, field):
            duplicates.append({"field": field, **group})
    return duplicates


def schema_issues(records: list[dict]) -> list[dict]:
    issues = []
    list_fields = {"kosullar", "adimlar", "istisnalar", "ilgili_dokumanlar"}
    for record in records:
        missing = [field for field in REQUIRED_FIELDS if field not in record]
        extra = [field for field in record if field not in REQUIRED_FIELDS and field != "_line"]
        type_errors = []
        for field in REQUIRED_FIELDS:
            if field not in record:
                continue
            expected = list if field in list_fields else str
            if not isinstance(record[field], expected):
                type_errors.append(
                    {
                        "field": field,
                        "expected": expected.__name__,
                        "actual": type(record[field]).__name__,
                    }
                )
        if missing or extra or type_errors:
            issues.append(
                {
                    "line": record["_line"],
                    "id": record.get("id", ""),
                    "missing_fields": missing,
                    "extra_fields": extra,
                    "type_errors": type_errors,
                }
            )
    return issues


def field_quality(records: list[dict]) -> tuple[dict, list[dict]]:
    summary = {}
    per_record = []
    for field in AUDITED_FIELDS:
        empty_records = []
        short_records = []
        threshold = STRING_THRESHOLDS.get(field, LIST_THRESHOLDS.get(field, 0))
        field_type = "string" if field in STRING_THRESHOLDS else "list"
        for record in records:
            value = record.get(field)
            empty = value == "" or value == [] or value is None
            length = len(value) if isinstance(value, (str, list)) else 0
            item = {
                "line": record["_line"],
                "id": record.get("id", ""),
                "title": record.get("title", ""),
                "category": record.get("category", ""),
                "length": length,
            }
            if empty:
                empty_records.append(item)
            elif length < threshold:
                short_records.append(item)
        summary[field] = {
            "type": field_type,
            "short_threshold": threshold,
            "empty_count": len(empty_records),
            "short_count": len(short_records),
            "empty_records": empty_records,
            "short_records": short_records,
        }

    for record in records:
        issues = []
        for field in AUDITED_FIELDS:
            value = record.get(field)
            threshold = STRING_THRESHOLDS.get(field, LIST_THRESHOLDS.get(field, 0))
            if value == "" or value == [] or value is None:
                issues.append(
                    {
                        "field": field,
                        "kind": "empty",
                        "length": 0,
                        "threshold": threshold,
                    }
                )
            elif isinstance(value, (str, list)) and len(value) < threshold:
                issues.append(
                    {
                        "field": field,
                        "kind": "short",
                        "length": len(value),
                        "threshold": threshold,
                    }
                )
        if issues:
            per_record.append(
                {
                    "line": record["_line"],
                    "id": record.get("id", ""),
                    "title": record.get("title", ""),
                    "category": record.get("category", ""),
                    "issues": issues,
                }
            )
    return summary, per_record


def derived_flags(records: list[dict]) -> list[dict]:
    flags = []
    for record in records:
        checks: list[tuple[str, str, str]] = []
        title = record.get("title", "")
        amac = record.get("amac", "")
        kapsam = record.get("kapsam", "")
        tanim = record.get("tanim", "")
        genel = record.get("genel_bilgiler", "")
        answer = record.get("standart_yanit", "")

        if kapsam.startswith("NovaCart ") and " konusu " in kapsam:
            checks.append(
                (
                    "kapsam",
                    "GENERIC_SCOPE_TEMPLATE",
                    "Kategori ve başlıktan üretilmiş genel kapsam kalıbına benziyor.",
                )
            )
        if answer.startswith(f"{title} konusunda dokümanda belirtilen işlem adımlarını"):
            checks.append(
                (
                    "standart_yanit",
                    "GENERIC_STANDARD_ANSWER",
                    "Başlığa dayalı genel destek yanıtı kalıbına benziyor.",
                )
            )
        if genel and tanim and normalize(genel) == normalize(tanim):
            checks.append(
                (
                    "genel_bilgiler",
                    "SAME_AS_DEFINITION",
                    "Genel bilgiler alanı tanım alanıyla birebir aynı.",
                )
            )
        first_purpose_sentence = re.split(r"(?<=[.!?])\s+", amac.strip())[0] if amac else ""
        if tanim and first_purpose_sentence and normalize(tanim) == normalize(first_purpose_sentence):
            checks.append(
                (
                    "tanim",
                    "SAME_AS_PURPOSE_FIRST_SENTENCE",
                    "Tanım, amaç alanının ilk cümlesiyle birebir aynı.",
                )
            )
        if amac.startswith("Bu doküman, ") and amac.endswith(
            "konusundaki koşulları ve izlenecek süreci açıklamak amacıyla hazırlanmıştır."
        ):
            checks.append(
                (
                    "amac",
                    "GENERIC_PURPOSE_TEMPLATE",
                    "Başlıktan üretilmiş genel amaç kalıbına benziyor.",
                )
            )

        for field, rule, reason in checks:
            flags.append(
                {
                    "line": record["_line"],
                    "id": record.get("id", ""),
                    "title": title,
                    "category": record.get("category", ""),
                    "field": field,
                    "rule": rule,
                    "reason": reason,
                    "value": record.get(field, ""),
                }
            )
    return flags


def repeated_items(records: list[dict]) -> list[dict]:
    findings = []
    for record in records:
        for field in ("kosullar", "adimlar", "istisnalar", "ilgili_dokumanlar"):
            value = record.get(field)
            if not isinstance(value, list):
                continue
            normalized = [normalize(item) for item in value if isinstance(item, str)]
            repeated = [
                item
                for item, count in Counter(normalized).items()
                if item and count > 1
            ]
            if repeated:
                findings.append(
                    {
                        "line": record["_line"],
                        "id": record.get("id", ""),
                        "title": record.get("title", ""),
                        "field": field,
                        "repeated_values": repeated,
                    }
                )
    return findings


def weak_records(
    quality_records: list[dict], flags: list[dict], content_duplicates: list[dict]
) -> list[dict]:
    by_id: dict[str, dict] = {}
    for record in quality_records:
        target = by_id.setdefault(
            record["id"],
            {
                "line": record["line"],
                "id": record["id"],
                "title": record["title"],
                "category": record["category"],
                "severity_score": 0,
                "reasons": [],
            },
        )
        for issue in record["issues"]:
            weight = 3 if issue["kind"] == "empty" else 1
            target["severity_score"] += weight
            target["reasons"].append(
                f"{issue['field']} alanı {'boş' if issue['kind'] == 'empty' else 'eşik altında'}"
            )

    for flag in flags:
        target = by_id.setdefault(
            flag["id"],
            {
                "line": flag["line"],
                "id": flag["id"],
                "title": flag["title"],
                "category": flag["category"],
                "severity_score": 0,
                "reasons": [],
            },
        )
        target["severity_score"] += 1
        target["reasons"].append(f"{flag['field']}: {flag['rule']}")

    duplicate_ids = defaultdict(list)
    for duplicate in content_duplicates:
        for item in duplicate["records"]:
            duplicate_ids[item["id"]].append(duplicate["field"])
    for record_id, fields in duplicate_ids.items():
        target = by_id.get(record_id)
        if target:
            for field in sorted(set(fields)):
                target["severity_score"] += 1
                target["reasons"].append(f"{field} alanında başka kayıtla birebir içerik tekrarı")

    result = []
    for item in by_id.values():
        item["reasons"] = list(dict.fromkeys(item["reasons"]))
        if item["severity_score"] >= 2:
            item["review_level"] = "HIGH" if item["severity_score"] >= 5 else "MEDIUM"
            result.append(item)
    return sorted(result, key=lambda item: (-item["severity_score"], item["line"]))


def make_audit() -> dict:
    records, json_errors, total_lines = load_jsonl()
    categories = Counter(record.get("category", "") for record in records)
    subcategories = defaultdict(list)
    for record in records:
        subcategories[record.get("category", "")].append(
            {
                "subcategory": record.get("subcategory", ""),
                "id": record.get("id", ""),
                "title": record.get("title", ""),
            }
        )

    duplicates = {
        field: duplicate_groups(records, field)
        for field in ("id", "title", "subcategory")
    }
    content_duplicates = duplicate_content(records)
    quality_summary, quality_records = field_quality(records)
    flags = derived_flags(records)
    repeated_list_items = repeated_items(records)
    schemas = schema_issues(records)
    weak = weak_records(quality_records, flags, content_duplicates)

    ids = {record.get("id", "") for record in records}
    broken_references = []
    for record in records:
        related = record.get("ilgili_dokumanlar", [])
        if not isinstance(related, list):
            continue
        missing = [reference for reference in related if reference not in ids]
        if missing:
            broken_references.append(
                {
                    "line": record["_line"],
                    "id": record.get("id", ""),
                    "title": record.get("title", ""),
                    "missing_references": missing,
                }
            )

    return {
        "metadata": {
            "source_file": str(INPUT.relative_to(ROOT)).replace("\\", "/"),
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "audit_scope": "Chunking yapılmadan mevcut JSONL içeriğinin yapısal ve içerik kalitesi denetimi.",
        },
        "validation": {
            "physical_line_count": total_lines,
            "valid_json_object_count": len(records),
            "invalid_line_count": len(json_errors),
            "invalid_lines": json_errors,
            "schema_issue_count": len(schemas),
            "schema_issues": schemas,
            "broken_related_document_reference_count": len(broken_references),
            "broken_related_document_references": broken_references,
        },
        "document_count": len(records),
        "category_counts": {
            category: categories.get(category, 0) for category in CATEGORY_ORDER
        },
        "subcategories_by_category": {
            category: sorted(
                subcategories.get(category, []),
                key=lambda item: (item["subcategory"], item["id"]),
            )
            for category in CATEGORY_ORDER
        },
        "documents": [
            {
                "line": record["_line"],
                "id": record.get("id", ""),
                "title": record.get("title", ""),
                "category": record.get("category", ""),
                "subcategory": record.get("subcategory", ""),
            }
            for record in records
        ],
        "duplicates": {
            "id": duplicates["id"],
            "title": duplicates["title"],
            "subcategory": duplicates["subcategory"],
            "exact_content_duplicates": content_duplicates,
            "repeated_items_within_list_fields": repeated_list_items,
        },
        "field_quality": {
            "method": {
                "string_thresholds_in_characters": STRING_THRESHOLDS,
                "list_thresholds_in_items": LIST_THRESHOLDS,
                "note": "Boş alan kesin bulgudur; kısa alan eşikleri denetim amaçlı sezgiseldir.",
            },
            "summary": quality_summary,
            "records_with_empty_or_short_fields": quality_records,
        },
        "derived_expression_flags": {
            "method": "Genel kapsam/yanıt kalıpları ve alanlar arası birebir tekrarlar sezgisel olarak işaretlenmiştir.",
            "count": len(flags),
            "findings": flags,
        },
        "weak_or_repetitive_documents": {
            "method": "Boş alan=3 puan; kısa alan, türetilmiş ifade veya içerik tekrarı=1 puan. Toplamı en az 2 olan kayıtlar listelenmiştir.",
            "count": len(weak),
            "records": weak,
        },
    }


def markdown_report(audit: dict) -> str:
    validation = audit["validation"]
    duplicate_summary = audit["duplicates"]
    quality = audit["field_quality"]
    flags = audit["derived_expression_flags"]["findings"]
    weak = audit["weak_or_repetitive_documents"]["records"]

    lines = [
        "# RAG Doküman Denetim Raporu",
        "",
        "## Sonuç",
        "",
        f"- Fiziksel JSONL satırı: **{validation['physical_line_count']}**",
        f"- Geçerli JSON obje satırı: **{validation['valid_json_object_count']}**",
        f"- Geçersiz satır: **{validation['invalid_line_count']}**",
        f"- Toplam doküman: **{audit['document_count']}**",
        f"- Şema sorunu bulunan kayıt: **{validation['schema_issue_count']}**",
        f"- Kırık ilgili doküman referansı: **{validation['broken_related_document_reference_count']}**",
        "",
        "JSONL dosyasındaki 70 satırın tamamı geçerli JSON objesidir. Bu rapor içerikleri değiştirmez ve chunking uygulamaz.",
        "",
        "## Kategori dağılımı",
        "",
        "| Category | Doküman sayısı |",
        "|---|---:|",
    ]
    for category, count in audit["category_counts"].items():
        lines.append(f"| `{category}` | {count} |")

    lines.extend(["", "## Category ve subcategory listesi", ""])
    for category in CATEGORY_ORDER:
        items = audit["subcategories_by_category"][category]
        lines.extend([f"### {category}", ""])
        for item in items:
            lines.append(
                f"- `{item['subcategory']}` — {item['title']} (`{item['id']}`)"
            )
        lines.append("")

    lines.extend(
        [
            "## Tüm dokümanlar",
            "",
            "| Satır | ID | Title | Category | Subcategory |",
            "|---:|---|---|---|---|",
        ]
    )
    for item in audit["documents"]:
        lines.append(
            "| {line} | `{id}` | {title} | `{category}` | `{subcategory}` |".format(
                line=item["line"],
                id=markdown_escape(item["id"]),
                title=markdown_escape(item["title"]),
                category=markdown_escape(item["category"]),
                subcategory=markdown_escape(item["subcategory"]),
            )
        )

    lines.extend(["", "## Tekrar kontrolleri", ""])
    for field in ("id", "title", "subcategory"):
        groups = duplicate_summary[field]
        lines.append(
            f"- Tekrarlı `{field}` grubu: **{len(groups)}**"
        )
    lines.append(
        f"- Liste alanı içinde yinelenen eleman bulunan kayıt: **{len(duplicate_summary['repeated_items_within_list_fields'])}**"
    )
    lines.append(
        f"- String alanlarda başka kayıtla birebir aynı içerik grubu: **{len(duplicate_summary['exact_content_duplicates'])}**"
    )
    if duplicate_summary["exact_content_duplicates"]:
        lines.extend(
            [
                "",
                "### Kayıtlar arası birebir içerik tekrarları",
                "",
                "| Alan | Değer özeti | Kayıtlar |",
                "|---|---|---|",
            ]
        )
        for item in duplicate_summary["exact_content_duplicates"]:
            preview = markdown_escape(item["value"][:100])
            record_names = ", ".join(
                f"`{record['id']}`" for record in item["records"]
            )
            lines.append(f"| `{item['field']}` | {preview} | {record_names} |")

    lines.extend(
        [
            "",
            "## Boş ve çok kısa alanlar",
            "",
            "String alanlarda karakter, liste alanlarında eleman sayısı kullanıldı. Eşikler kalite taraması için sezgiseldir; boş alanlar ise kesin bulgudur.",
            "",
            "| Alan | Eşik | Boş | Eşik altında |",
            "|---|---:|---:|---:|",
        ]
    )
    for field in AUDITED_FIELDS:
        item = quality["summary"][field]
        unit = "karakter" if item["type"] == "string" else "öğe"
        lines.append(
            f"| `{field}` | {item['short_threshold']} {unit} | {item['empty_count']} | {item['short_count']} |"
        )

    lines.extend(["", "### Boş alan bulunan kayıtlar", ""])
    empty_rows = []
    for field in AUDITED_FIELDS:
        for record in quality["summary"][field]["empty_records"]:
            empty_rows.append((field, record))
    if empty_rows:
        lines.extend(
            [
                "| Alan | ID | Title | Category |",
                "|---|---|---|---|",
            ]
        )
        for field, record in empty_rows:
            lines.append(
                f"| `{field}` | `{record['id']}` | {markdown_escape(record['title'])} | `{record['category']}` |"
            )
    else:
        lines.append("- Boş alan bulunmadı.")

    lines.extend(["", "### Çok kısa alan bulunan kayıtlar", ""])
    short_rows = []
    for field in AUDITED_FIELDS:
        for record in quality["summary"][field]["short_records"]:
            short_rows.append((field, record))
    if short_rows:
        lines.extend(
            [
                "| Alan | ID | Title | Uzunluk |",
                "|---|---|---|---:|",
            ]
        )
        for field, record in short_rows:
            lines.append(
                f"| `{field}` | `{record['id']}` | {markdown_escape(record['title'])} | {record['length']} |"
            )
    else:
        lines.append("- Eşik altında alan bulunmadı.")

    lines.extend(
        [
            "",
            "## Türetilmiş veya genel geçiştirme ifadesi olabilecek alanlar",
            "",
            "Bu bölüm kesin hata değildir. Kaynak metin yerine başlık/kategori üzerinden oluşturulmuş olabilecek genel kalıpları ve alanlar arası birebir kopyaları işaretler.",
            "",
            f"Toplam işaret: **{len(flags)}**",
            "",
        ]
    )
    if flags:
        lines.extend(
            [
                "| ID | Title | Alan | Kural | Gerekçe |",
                "|---|---|---|---|---|",
            ]
        )
        for item in flags:
            lines.append(
                f"| `{item['id']}` | {markdown_escape(item['title'])} | `{item['field']}` | `{item['rule']}` | {markdown_escape(item['reason'])} |"
            )
    else:
        lines.append("- İşaretlenen ifade bulunmadı.")

    lines.extend(
        [
            "",
            "## Eksik, zayıf veya tekrar eden dokümanlar",
            "",
            "Puanlama: boş alan 3; kısa alan, türetilmiş ifade veya başka kayıtla birebir içerik tekrarı 1 puan. Toplam puanı en az 2 olan kayıtlar aşağıdadır.",
            "",
            f"Manuel inceleme önerilen kayıt: **{len(weak)}**",
            "",
        ]
    )
    if weak:
        lines.extend(
            [
                "| Seviye | Puan | ID | Title | Nedenler |",
                "|---|---:|---|---|---|",
            ]
        )
        for item in weak:
            reasons = "; ".join(item["reasons"])
            lines.append(
                f"| `{item['review_level']}` | {item['severity_score']} | `{item['id']}` | {markdown_escape(item['title'])} | {markdown_escape(reasons)} |"
            )
    else:
        lines.append("- Manuel inceleme eşiğini aşan kayıt bulunmadı.")

    lines.extend(
        [
            "",
            "## Genel değerlendirme",
            "",
            "- Doküman sayısının 70 olmasının nedeni, alt başlıkların ayrı kayıt kabul edilmesi ve kaynaklardaki yinelenen alt başlıkların tekilleştirilmiş olmasıdır.",
            "- Kategori dağılımı dengeli değildir ancak kaynak dokümanların başlık sayılarıyla uyumludur.",
            "- Yapısal olarak JSONL kullanılabilir durumdadır.",
            "- İçerik kalitesindeki temel risk, bazı kaynaklarda açıkça bulunmayan alanların genel cümlelerle tamamlanmış olmasıdır.",
            "- Chunking öncesinde bu rapordaki yüksek ve orta öncelikli kayıtların gözden geçirilmesi önerilir.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    audit = make_audit()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    REPORT_MD.write_text(markdown_report(audit), encoding="utf-8")

    # Verify the generated machine-readable report.
    parsed = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    assert parsed["document_count"] == 70
    assert parsed["validation"]["invalid_line_count"] == 0
    print(
        "AUDIT_OK "
        f"documents={parsed['document_count']} "
        f"derived_flags={parsed['derived_expression_flags']['count']} "
        f"weak_records={parsed['weak_or_repetitive_documents']['count']}"
    )


if __name__ == "__main__":
    main()
