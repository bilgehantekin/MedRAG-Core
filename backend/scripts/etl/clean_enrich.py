#!/usr/bin/env python3
"""
MedlinePlus Data Cleaning and Enrichment Script

Outputs:
1. symptoms_diseases_medlineplus_clean_en.json - English only, safety_level recalculated
2. symptoms_diseases_medlineplus_tr_enriched.json - Above + Turkish translations

Usage:
    python -m scripts.etl.clean_enrich [--input FILE] [--skip-translation]
"""

import json
import re
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional, Set
from collections import Counter
from functools import partial

# Force unbuffered output
print = partial(print, flush=True)

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.etl.config import OUTPUT_DIR, TR_CHAR_MAP
from scripts.etl.utils import dedupe_keywords

# Try to import translator
try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
except ImportError:
    TRANSLATOR_AVAILABLE = False
    print("Warning: deep-translator not available. Run: pip install deep-translator")


# Emergency patterns for safety_level detection
# These patterns should match ACTION-ORIENTED emergency instructions, not educational content
# "can be life-threatening" is educational, "call 911 immediately" is actionable

# Strong patterns - these alone indicate emergency
STRONG_EMERGENCY_PATTERNS = [
    r'\bcall\s+911\s+(?:immediately|right\s+away|now)\b',
    r'\bdial\s+911\b',
    r'\bcall\s+112\b',
    r'\bcall\s+emergency\s+services?\s+(?:immediately|right\s+away|now)\b',
    r'\bgo\s+to\s+(?:the\s+)?emergency\s+room\s+(?:immediately|right\s+away|now)\b',
    r'\b(?:call|get)\s+(?:an?\s+)?ambulance\s+(?:immediately|right\s+away|now)\b',
    r'\bthis\s+is\s+a\s+medical\s+emergency\b',
    r'\bseek\s+emergency\s+(?:medical\s+)?(?:care|help|attention)\b',
]

# Medium patterns - need context (imperative mood suggests emergency)
MEDIUM_EMERGENCY_PATTERNS = [
    r'\bcall\s+911\b',  # Without "immediately" but still actionable
    r'\bgo\s+to\s+(?:the\s+)?(?:nearest\s+)?emergency\s+room\b',
    r'\bseek\s+immediate\s+medical\s+(?:attention|help|care)\b',
]

# Conditions that are inherently emergencies (specific titles)
EMERGENCY_CONDITIONS = {
    'anaphylaxis', 'cardiac arrest', 'heart attack', 'stroke', 'choking',
    'severe bleeding', 'poisoning', 'overdose', 'seizure', 'unconscious',
    'drowning', 'severe allergic reaction', 'shock', 'trauma'
}

STRONG_EMERGENCY_REGEX = re.compile('|'.join(STRONG_EMERGENCY_PATTERNS), re.IGNORECASE)
MEDIUM_EMERGENCY_REGEX = re.compile('|'.join(MEDIUM_EMERGENCY_PATTERNS), re.IGNORECASE)


class MedlinePlusCleaner:
    """Clean and enrich MedlinePlus data"""

    def __init__(self, input_file: Optional[Path] = None):
        self.input_file = input_file or OUTPUT_DIR / "symptoms_diseases_medlineplus.json"
        self.data: List[Dict] = []
        self.translator = None
        self.translation_cache: Dict[str, str] = {}
        self.stats = {
            'total_input': 0,
            'spanish_filtered': 0,
            'english_kept': 0,
            'safety_emergency': 0,
            'safety_sensitive': 0,
            'safety_general': 0,
            'translations_done': 0,
            'translations_cached': 0,
            'translations_failed': 0,
        }

    def load_data(self) -> int:
        """Load input JSON file"""
        print(f"Loading data from: {self.input_file}")
        with open(self.input_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        self.stats['total_input'] = len(self.data)
        print(f"Loaded {len(self.data)} records")
        return len(self.data)

    def filter_spanish(self) -> List[Dict]:
        """Filter out Spanish records based on source_url"""
        english_records = []
        spanish_count = 0

        for record in self.data:
            source_url = record.get('source_url', '')
            # Check if it's a Spanish page
            if '/spanish/' in source_url.lower():
                spanish_count += 1
                continue
            english_records.append(record)

        self.stats['spanish_filtered'] = spanish_count
        self.stats['english_kept'] = len(english_records)

        print(f"Filtered {spanish_count} Spanish records")
        print(f"Kept {len(english_records)} English records")

        return english_records

    def recalculate_safety_level(self, record: Dict) -> str:
        """
        Recalculate safety_level based on rules:
        1. mental_health category → sensitive
        2. Known emergency conditions (by title) → emergency
        3. Strong emergency patterns in content → emergency
        4. Medium emergency patterns with context → emergency
        5. Otherwise → general
        """
        category = record.get('category', '')
        content = record.get('content', '')
        title = record.get('title', '')
        title_lower = title.lower()

        # Rule 1: Mental health is always sensitive
        if category == 'mental_health':
            return 'sensitive'

        # Rule 2: Known emergency conditions (by title)
        for condition in EMERGENCY_CONDITIONS:
            if condition in title_lower:
                return 'emergency'

        text_to_check = f"{title} {content}"

        # Rule 3: Strong emergency patterns (action-oriented with "immediately")
        if STRONG_EMERGENCY_REGEX.search(text_to_check):
            return 'emergency'

        # Rule 4: Medium patterns - only if they appear as instructions
        # Check if content has imperative mood indicators
        if MEDIUM_EMERGENCY_REGEX.search(text_to_check):
            # Additional context check: look for imperative language
            imperative_indicators = [
                r'\bif\s+you\s+(?:think|suspect|believe)\b',
                r'\bget\s+(?:medical\s+)?help\b',
                r'\bdo\s+not\s+(?:delay|wait)\b',
                r'\bimmediately\b',
                r'\bright\s+away\b',
            ]
            for pattern in imperative_indicators:
                if re.search(pattern, text_to_check, re.IGNORECASE):
                    return 'emergency'

        # Rule 5: Default to general
        return 'general'

    def apply_safety_levels(self, records: List[Dict]) -> List[Dict]:
        """Apply safety_level recalculation to all records"""
        for record in records:
            new_level = self.recalculate_safety_level(record)
            record['safety_level'] = new_level

            # Track stats
            if new_level == 'emergency':
                self.stats['safety_emergency'] += 1
            elif new_level == 'sensitive':
                self.stats['safety_sensitive'] += 1
            else:
                self.stats['safety_general'] += 1

        print(f"Safety levels: emergency={self.stats['safety_emergency']}, "
              f"sensitive={self.stats['safety_sensitive']}, "
              f"general={self.stats['safety_general']}")

        return records

    def init_translator(self):
        """Initialize Google Translator"""
        if not TRANSLATOR_AVAILABLE:
            print("Translator not available!")
            return False

        try:
            self.translator = GoogleTranslator(source='en', target='tr')
            # Test translation
            test = self.translator.translate("test")
            print(f"Translator initialized (test: 'test' → '{test}')")
            return True
        except Exception as e:
            print(f"Failed to initialize translator: {e}")
            return False

    def translate_text(self, text: str) -> Optional[str]:
        """Translate text from English to Turkish with caching"""
        if not text or not text.strip():
            return ""

        text = text.strip()

        # Check cache
        if text in self.translation_cache:
            self.stats['translations_cached'] += 1
            return self.translation_cache[text]

        if not self.translator:
            return None

        try:
            # Rate limiting - be nice to the API
            time.sleep(0.1)

            translated = self.translator.translate(text)
            self.translation_cache[text] = translated
            self.stats['translations_done'] += 1
            return translated

        except Exception as e:
            self.stats['translations_failed'] += 1
            # Return None to indicate failure, not empty string
            return None

    def translate_batch(self, texts: List[str], batch_size: int = 10) -> Dict[str, str]:
        """Translate multiple texts with batching"""
        results = {}

        for text in texts:
            if not text:
                continue

            # Try to translate
            translated = self.translate_text(text)
            if translated:
                results[text] = translated

        return results

    def generate_typos_tr(self, keywords: List[str]) -> List[str]:
        """Generate Turkish typo variants"""
        typos = set()

        for keyword in keywords:
            if not keyword:
                continue

            keyword_lower = keyword.lower().strip()

            # Rule 1: Remove Turkish special characters
            typo = keyword_lower
            for tr_char, replacement in TR_CHAR_MAP.items():
                typo = typo.replace(tr_char.lower(), replacement.lower())

            if typo != keyword_lower:
                typos.add(typo)

            # Rule 2: Remove spaces (for multi-word)
            if ' ' in keyword_lower:
                typos.add(keyword_lower.replace(' ', ''))
                # Also without TR chars and spaces
                typo_no_space = typo.replace(' ', '')
                typos.add(typo_no_space)

            # Rule 3: Common confusions
            # ı/i confusion
            if 'ı' in keyword_lower:
                typos.add(keyword_lower.replace('ı', 'i'))
            # ö/o confusion
            if 'ö' in keyword_lower:
                typos.add(keyword_lower.replace('ö', 'o'))
            # ü/u confusion
            if 'ü' in keyword_lower:
                typos.add(keyword_lower.replace('ü', 'u'))
            # ş/s confusion
            if 'ş' in keyword_lower:
                typos.add(keyword_lower.replace('ş', 's'))
            # ç/c confusion
            if 'ç' in keyword_lower:
                typos.add(keyword_lower.replace('ç', 'c'))
            # ğ/g confusion
            if 'ğ' in keyword_lower:
                typos.add(keyword_lower.replace('ğ', 'g'))

        # Remove empty strings and originals
        original_set = {k.lower().strip() for k in keywords}
        typos = {t for t in typos if t and t not in original_set and len(t) >= 2}

        return list(typos)

    def enrich_turkish(self, records: List[Dict], skip_translation: bool = False) -> List[Dict]:
        """Add Turkish translations and keywords"""

        if not skip_translation:
            if not self.init_translator():
                print("Cannot enrich without translator. Use --skip-translation to skip.")
                return records

        total = len(records)
        print(f"\nEnriching {total} records with Turkish translations...")

        for i, record in enumerate(records):
            if (i + 1) % 100 == 0:
                print(f"  Progress: {i + 1}/{total} "
                      f"(translated: {self.stats['translations_done']}, "
                      f"cached: {self.stats['translations_cached']}, "
                      f"failed: {self.stats['translations_failed']})")

            title = record.get('title', '')
            keywords_en = record.get('keywords_en', [])

            # Translate title
            if not skip_translation and title:
                title_tr = self.translate_text(title)
                if title_tr:
                    record['title_tr'] = title_tr
                else:
                    # Fallback: keep original or empty
                    record['title_tr'] = record.get('title_tr', '')

            # Build keywords_tr
            keywords_tr = []

            # Add translated title
            if record.get('title_tr'):
                keywords_tr.append(record['title_tr'].lower())

            # Translate keywords_en
            if not skip_translation:
                for kw in keywords_en[:10]:  # Limit to avoid too many API calls
                    if len(kw) < 2 or len(kw) > 50:
                        continue
                    translated = self.translate_text(kw)
                    if translated:
                        keywords_tr.append(translated.lower())

            # Dedupe and filter by length
            keywords_tr = dedupe_keywords(keywords_tr)
            keywords_tr = [k for k in keywords_tr if 2 <= len(k) <= 40]

            # Ensure minimum 5 keywords (add variations if needed)
            if record.get('title_tr') and len(keywords_tr) < 5:
                # Add title variations
                title_tr = record['title_tr'].lower()
                keywords_tr.append(title_tr)
                # Add "X nedir" pattern
                keywords_tr.append(f"{title_tr} nedir")
                keywords_tr.append(f"{title_tr} belirtileri")
                keywords_tr = dedupe_keywords(keywords_tr)

            record['keywords_tr'] = keywords_tr[:15]  # Cap at 15

            # Generate typos
            record['typos_tr'] = self.generate_typos_tr(record['keywords_tr'])[:10]

        print(f"\nTranslation stats:")
        print(f"  Done: {self.stats['translations_done']}")
        print(f"  Cached: {self.stats['translations_cached']}")
        print(f"  Failed: {self.stats['translations_failed']}")

        return records

    def validate_quality(self, records: List[Dict]) -> Dict:
        """Run quality control checks"""
        issues = {
            'empty_title_tr': 0,
            'few_keywords_tr': 0,
            'no_content': 0,
        }

        for record in records:
            if not record.get('title_tr'):
                issues['empty_title_tr'] += 1
            if len(record.get('keywords_tr', [])) < 5:
                issues['few_keywords_tr'] += 1
            if not record.get('content'):
                issues['no_content'] += 1

        print(f"\nQuality control:")
        print(f"  Empty title_tr: {issues['empty_title_tr']}")
        print(f"  Few keywords_tr (<5): {issues['few_keywords_tr']}")
        print(f"  No content: {issues['no_content']}")

        return issues

    def save_results(self, records: List[Dict], filename: str) -> Path:
        """Save records to JSON file"""
        output_path = OUTPUT_DIR / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(records)} records to: {output_path}")
        return output_path

    def run(self, skip_translation: bool = False) -> Dict:
        """Run the full cleaning and enrichment pipeline"""
        print("=" * 60)
        print("MedlinePlus Data Cleaning & Enrichment")
        print("=" * 60)

        # Load
        self.load_data()

        # Step 1: Filter Spanish
        print("\n--- Step 1: Filtering Spanish records ---")
        english_records = self.filter_spanish()

        # Step 2: Recalculate safety_level
        print("\n--- Step 2: Recalculating safety levels ---")
        english_records = self.apply_safety_levels(english_records)

        # Save clean English version
        print("\n--- Saving clean English version ---")
        self.save_results(english_records, "symptoms_diseases_medlineplus_clean_en.json")

        # Step 3: Turkish enrichment
        print("\n--- Step 3: Turkish enrichment ---")
        enriched_records = self.enrich_turkish(english_records, skip_translation)

        # Step 4: Quality control
        print("\n--- Step 4: Quality control ---")
        quality = self.validate_quality(enriched_records)

        # Save enriched version
        print("\n--- Saving Turkish enriched version ---")
        self.save_results(enriched_records, "symptoms_diseases_medlineplus_tr_enriched.json")

        # Summary
        print("\n" + "=" * 60)
        print("Summary")
        print("=" * 60)
        print(f"Input records: {self.stats['total_input']}")
        print(f"Spanish filtered: {self.stats['spanish_filtered']}")
        print(f"English kept: {self.stats['english_kept']}")
        print(f"Safety levels: emergency={self.stats['safety_emergency']}, "
              f"sensitive={self.stats['safety_sensitive']}, "
              f"general={self.stats['safety_general']}")

        return {
            'stats': self.stats,
            'quality': quality,
            'output_files': [
                'symptoms_diseases_medlineplus_clean_en.json',
                'symptoms_diseases_medlineplus_tr_enriched.json'
            ]
        }


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Clean and enrich MedlinePlus data')
    parser.add_argument('--input', '-i', type=Path, help='Input JSON file')
    parser.add_argument('--skip-translation', action='store_true',
                        help='Skip Turkish translation (just clean)')

    args = parser.parse_args()

    cleaner = MedlinePlusCleaner(input_file=args.input)
    result = cleaner.run(skip_translation=args.skip_translation)

    return 0 if result else 1


if __name__ == '__main__':
    sys.exit(main())
