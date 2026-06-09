"""
CargoIQ — Extraction Accuracy Measurement Script
Day 4–5 task: measure and improve extraction accuracy.

Usage:
  1. Place sample PDF files in tests/extraction/samples/
  2. Create expected.json with expected field values
  3. Run: python -m pytest tests/extraction/accuracy_test.py -v -s

Output:
  - Per-field accuracy scores
  - Overall accuracy percentage
  - Failures with diff for prompt engineering
"""
import asyncio
import json
import os
from pathlib import Path
from typing import Optional

# ── Config ─────────────────────────────────────────────────
SAMPLES_DIR   = Path(__file__).parent / "samples"
EXPECTED_FILE = Path(__file__).parent / "expected.json"
RESULTS_FILE  = Path(__file__).parent / "results.json"

# Fields to measure (subset of 15 core fields)
MEASURED_FIELDS = [
    "shipper_name",
    "consignee_name",
    "origin_port",
    "destination_port",
    "cargo_description",
    "hs_code_primary",
    "gross_weight",
    "invoice_number",
    "invoice_value",
    "currency",
    "incoterms",
    "awb_or_bl_number",
    "shipment_type",
    "eta",
    "number_of_packages",
]


def load_expected() -> dict:
    """Load expected extraction results from JSON file."""
    if not EXPECTED_FILE.exists():
        # Create template if it doesn't exist
        template = {
            "sample_invoice.pdf": {
                "shipper_name":      "Example Shipper Co Ltd",
                "consignee_name":    "Example Consignee (Pty) Ltd",
                "origin_port":       "CNSHA",
                "destination_port":  "ZADUR",
                "cargo_description": "Electronic components",
                "hs_code_primary":   "85171100",
                "gross_weight":      "1250.5",
                "invoice_number":    "INV-2026-001",
                "invoice_value":     "15000.00",
                "currency":          "USD",
                "incoterms":         "FOB",
                "awb_or_bl_number":  "MSCUABCD123456",
                "shipment_type":     "fcl_import",
                "eta":               "2026-07-15",
                "number_of_packages": "10",
            }
        }
        EXPECTED_FILE.write_text(json.dumps(template, indent=2))
        print(f"Created expected.json template at {EXPECTED_FILE}")
        print("Fill in the expected values and run again.")
        return template
    return json.loads(EXPECTED_FILE.read_text())


def normalise(value: Optional[str]) -> str:
    """Normalise a field value for comparison."""
    if value is None:
        return ""
    return str(value).strip().lower().replace(",", "").replace(" ", "")


def field_matches(extracted: Optional[str], expected: Optional[str]) -> bool:
    """
    Check if extracted value matches expected.
    Uses normalised comparison with partial match fallback.
    """
    e = normalise(extracted)
    x = normalise(expected)
    if not x:  # No expected value = skip
        return True
    if not e:  # No extracted value = miss
        return False
    # Exact match
    if e == x:
        return True
    # Partial match (extracted contains expected or vice versa)
    if e in x or x in e:
        return True
    # Numeric match (strip trailing zeros)
    try:
        return abs(float(e) - float(x)) < 0.01
    except (ValueError, TypeError):
        pass
    return False


async def run_extraction_on_file(pdf_path: Path) -> dict:
    """Run extraction pipeline on a single PDF file."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from services.document_service import extract_text_from_pdf
    from services.extraction_service import extract_shipment_fields, extraction_to_shipment_dict

    print(f"\n📄 Processing: {pdf_path.name}")
    content = pdf_path.read_bytes()

    # Step 1: Extract text
    raw_text, method, pages = extract_text_from_pdf(content, pdf_path.name)
    print(f"   OCR method: {method} | Pages: {pages} | Chars: {len(raw_text)}")

    if not raw_text.strip():
        print("   ❌ No text extracted")
        return {}

    # Step 2: AI extraction
    extraction = await extract_shipment_fields(
        raw_text=raw_text,
        doc_types=["commercial_invoice"],
        filename=pdf_path.name
    )
    result = extraction_to_shipment_dict(extraction)
    print(f"   Confidence: {result.get('overall_confidence')} ({result.get('confidence_percentage')}%)")
    return result


def score_extraction(extracted: dict, expected: dict, filename: str) -> dict:
    """Score extraction against expected values."""
    scores = {}
    for field in MEASURED_FIELDS:
        exp_val = expected.get(field)
        ext_val = extracted.get(field)
        match = field_matches(str(ext_val) if ext_val else None, str(exp_val) if exp_val else None)
        scores[field] = {
            "expected":  exp_val,
            "extracted": ext_val,
            "match":     match,
            "skip":      exp_val is None,
        }
    return scores


def print_report(all_scores: dict):
    """Print human-readable accuracy report."""
    print("\n" + "="*60)
    print("EXTRACTION ACCURACY REPORT")
    print("="*60)

    field_totals: dict = {f: {"correct": 0, "total": 0} for f in MEASURED_FIELDS}
    file_totals  = {}

    for filename, scores in all_scores.items():
        file_correct = 0
        file_total   = 0
        for field, result in scores.items():
            if result["skip"]:
                continue
            field_totals[field]["total"] += 1
            file_total += 1
            if result["match"]:
                field_totals[field]["correct"] += 1
                file_correct += 1

        file_acc = (file_correct / file_total * 100) if file_total > 0 else 0
        file_totals[filename] = {"accuracy": file_acc, "correct": file_correct, "total": file_total}
        print(f"\n📄 {filename}: {file_acc:.1f}% ({file_correct}/{file_total})")

        for field, result in scores.items():
            if result["skip"]:
                continue
            status = "✓" if result["match"] else "✗"
            if not result["match"]:
                print(f"   {status} {field:<25} expected={result['expected']!r:<30} got={result['extracted']!r}")

    print("\n" + "-"*60)
    print("FIELD-LEVEL ACCURACY:")
    total_correct = 0
    total_fields  = 0
    for field, totals in field_totals.items():
        if totals["total"] == 0:
            continue
        acc = totals["correct"] / totals["total"] * 100
        bar = "█" * int(acc / 5) + "░" * (20 - int(acc / 5))
        print(f"  {field:<28} {bar} {acc:5.1f}%  ({totals['correct']}/{totals['total']})")
        total_correct += totals["correct"]
        total_fields  += totals["total"]

    overall = (total_correct / total_fields * 100) if total_fields > 0 else 0
    print("\n" + "="*60)
    print(f"OVERALL ACCURACY: {overall:.1f}% ({total_correct}/{total_fields} fields)")

    if overall >= 90:
        print("🟢 Target achieved (≥90%). Ready for pilot.")
    elif overall >= 75:
        print("🟡 Good progress. Focus prompt engineering on failing fields.")
    else:
        print("🔴 Below target. Significant prompt engineering needed.")
    print("="*60)

    # Save results for tracking
    results = {
        "overall_accuracy": overall,
        "file_results": file_totals,
        "field_accuracy": {
            f: (v["correct"] / v["total"] * 100) if v["total"] > 0 else None
            for f, v in field_totals.items()
        }
    }
    RESULTS_FILE.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to {RESULTS_FILE}")
    return overall


async def main():
    """Run accuracy test on all sample PDFs."""
    SAMPLES_DIR.mkdir(exist_ok=True)

    pdfs = list(SAMPLES_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"\n⚠️  No PDF files found in {SAMPLES_DIR}")
        print("Add real freight PDFs to tests/extraction/samples/ and run again.")
        return

    expected = load_expected()
    all_scores = {}

    for pdf_path in pdfs:
        filename = pdf_path.name
        if filename not in expected:
            print(f"\n⚠️  No expected values for {filename} — add to expected.json")
            continue

        extracted = await run_extraction_on_file(pdf_path)
        if extracted:
            all_scores[filename] = score_extraction(extracted, expected[filename], filename)

    if all_scores:
        print_report(all_scores)
    else:
        print("\n❌ No files processed. Check ANTHROPIC_API_KEY is set.")


# Pytest entry point
def test_extraction_accuracy():
    """Pytest wrapper for accuracy measurement."""
    import os
    if not os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY") == "test-key":
        import pytest
        pytest.skip("ANTHROPIC_API_KEY not set — skipping live extraction test")
    overall = asyncio.run(main_and_return_score())
    assert overall >= 70, f"Extraction accuracy {overall:.1f}% is below 70% minimum"


async def main_and_return_score() -> float:
    SAMPLES_DIR.mkdir(exist_ok=True)
    pdfs = list(SAMPLES_DIR.glob("*.pdf"))
    if not pdfs:
        return 0.0
    expected = load_expected()
    all_scores = {}
    for pdf_path in pdfs:
        if pdf_path.name in expected:
            extracted = await run_extraction_on_file(pdf_path)
            if extracted:
                all_scores[pdf_path.name] = score_extraction(
                    extracted, expected[pdf_path.name], pdf_path.name
                )
    if not all_scores:
        return 0.0
    return print_report(all_scores)


if __name__ == "__main__":
    asyncio.run(main())
