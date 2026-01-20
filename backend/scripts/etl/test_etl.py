#!/usr/bin/env python3
"""
Test script for ETL pipeline utilities
Run this to verify the ETL setup works correctly
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_utils():
    """Test utility functions"""
    print("Testing utility functions...")

    from scripts.etl.utils import (
        slugify, generate_typos_tr, generate_keywords_tr,
        strip_html, truncate_text, classify_category, classify_safety_level
    )

    # Test slugify
    assert slugify("Headache (Cephalalgia)") == "headache_cephalalgia"
    assert slugify("High Blood Pressure") == "high_blood_pressure"
    print("  slugify: OK")

    # Test strip_html
    html = "<p>This is <b>bold</b> text</p>"
    assert strip_html(html) == "This is bold text"
    print("  strip_html: OK")

    # Test truncate_text
    long_text = "This is a very long text. " * 50
    truncated = truncate_text(long_text, max_length=100)
    assert len(truncated) <= 103  # 100 + "..."
    print("  truncate_text: OK")

    # Test Turkish typo generation
    typos = generate_typos_tr(["baş ağrısı", "migren"])
    assert "bas agrisi" in typos
    print("  generate_typos_tr: OK")

    # Test category classification
    cat = classify_category("Depression", "A mental health condition involving persistent sadness", [])
    assert cat == "mental_health"

    cat = classify_category("Headache", "Pain in the head", ["Symptoms"])
    assert cat == "symptoms"
    print("  classify_category: OK")

    # Test safety level classification
    level = classify_safety_level("Heart Attack", "Call 911 immediately", "emergency")
    assert level == "emergency"

    level = classify_safety_level("Depression", "Mental health condition", "mental_health")
    assert level == "sensitive"
    print("  classify_safety_level: OK")

    print("All utility tests passed!")


def test_schemas():
    """Test Pydantic schemas"""
    print("\nTesting schemas...")

    from scripts.etl.schemas import (
        SymptomDiseaseEntry, MedicationEntry,
        validate_symptom_disease_entry, validate_medication_entry
    )

    # Test symptom/disease entry
    valid_entry = {
        "id": "headache_001",
        "title": "Headache",
        "title_tr": "Baş Ağrısı",
        "category": "symptoms",
        "source_name": "MedlinePlus",
        "retrieved_date": "2025-01-19",
        "content": "A headache is pain in the head.",
        "keywords_en": ["headache", "head pain"],
        "keywords_tr": ["baş ağrısı"]
    }

    is_valid, entry, error = validate_symptom_disease_entry(valid_entry)
    assert is_valid, f"Validation failed: {error}"
    print("  SymptomDiseaseEntry: OK")

    # Test medication entry
    med_entry = {
        "id": "paracetamol_001",
        "title": "Paracetamol",
        "category": "medications",
        "source_name": "openFDA",
        "retrieved_date": "2025-01-19",
        "content": "Pain reliever and fever reducer."
    }

    is_valid, entry, error = validate_medication_entry(med_entry)
    assert is_valid, f"Validation failed: {error}"
    print("  MedicationEntry: OK")

    # Test invalid entry
    invalid_entry = {
        "id": "test",
        "title": "Test",
        "category": "invalid_category",  # Invalid!
        "source_name": "Test",
        "retrieved_date": "2025-01-19",
        "content": "Test"
    }

    is_valid, entry, error = validate_symptom_disease_entry(invalid_entry)
    assert not is_valid, "Should have failed validation"
    print("  Invalid entry rejection: OK")

    print("All schema tests passed!")


def test_dedup():
    """Test deduplication functions"""
    print("\nTesting deduplication...")

    from scripts.etl.dedup import (
        similarity_score, are_duplicates, deduplicate_entries
    )

    # Test similarity
    score = similarity_score("headache", "headache")
    assert score == 1.0

    score = similarity_score("Headache", "Head Ache")
    assert score > 0.8
    print("  similarity_score: OK")

    # Test duplicate detection
    entry1 = {"title": "Headache", "category": "symptoms", "content": "Pain in head"}
    entry2 = {"title": "Headache", "category": "symptoms", "content": "Head pain"}
    entry3 = {"title": "Fever", "category": "symptoms", "content": "High temperature"}

    assert are_duplicates(entry1, entry2)
    assert not are_duplicates(entry1, entry3)
    print("  are_duplicates: OK")

    # Test deduplication
    entries = [entry1, entry2, entry3]
    deduped, removed = deduplicate_entries(entries)
    assert len(deduped) == 2
    assert removed == 1
    print("  deduplicate_entries: OK")

    print("All dedup tests passed!")


def test_sample_transform():
    """Test transformation without downloading"""
    print("\nTesting sample transformation...")

    from scripts.etl.medlineplus_etl import MedlinePlusETL
    from scripts.etl.openfda_etl import OpenFDAETL

    # Test MedlinePlus transform
    etl_mp = MedlinePlusETL()
    sample_data = {
        'title': 'Headache',
        'summary': 'A headache is pain or discomfort in the head. Most headaches are not serious.',
        'url': 'https://medlineplus.gov/headache.html',
        'groups': ['Symptoms'],
        'also_called': ['Cephalalgia'],
        'see_references': [],
        'related': ['Migraine']
    }

    result = etl_mp.transform_to_schema(sample_data)
    assert result is not None
    assert result['id'] == 'headache_001'
    assert result['category'] == 'symptoms'
    assert 'baş ağrısı' in result['keywords_tr'] or len(result['keywords_tr']) > 0
    print("  MedlinePlus transform: OK")

    # Test openFDA transform
    etl_fda = OpenFDAETL()
    sample_fda = {
        'title': 'Ibuprofen',
        'generic_name': 'Ibuprofen',
        'brand_name': 'Advil',
        'drug_class': 'NSAID',
        'indications': 'For temporary relief of minor aches and pains.',
        'dosage': 'Take 1-2 tablets every 4-6 hours.',
        'warnings': 'Do not take more than directed.',
        'adverse_reactions': 'Stomach upset may occur.',
        'contraindications': 'Do not use if allergic to ibuprofen.'
    }

    result = etl_fda.transform_to_schema(sample_fda)
    assert result is not None
    assert 'ibuprofen' in result['id']
    assert result['category'] == 'medications'
    print("  openFDA transform: OK")

    print("All transform tests passed!")


def main():
    """Run all tests"""
    print("=" * 50)
    print("ETL Pipeline Test Suite")
    print("=" * 50)

    try:
        test_utils()
        test_schemas()
        test_dedup()
        test_sample_transform()

        print("\n" + "=" * 50)
        print("All tests passed!")
        print("=" * 50)
        return 0

    except AssertionError as e:
        print(f"\nTest failed: {e}")
        return 1
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
