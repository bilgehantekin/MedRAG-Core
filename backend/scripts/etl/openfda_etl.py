"""
openFDA Drug Label ETL Module
Downloads and processes openFDA drug label bulk JSON data
"""

import json
import requests
import zipfile
import io
from pathlib import Path
from typing import List, Dict, Optional, Generator, Any
import re

from .config import (
    DOWNLOADS_DIR, OUTPUT_DIR, RETRIEVED_DATE,
    MAX_RECORDS_PER_SOURCE
)
from .utils import (
    generate_id, strip_html, normalize_text, truncate_text,
    generate_keywords_tr, generate_typos_tr, dedupe_keywords,
    slugify
)
from .schemas import MedicationEntry, validate_medication_entry


class OpenFDAETL:
    """
    ETL pipeline for openFDA drug label data

    openFDA drug label structure (simplified):
    {
        "results": [
            {
                "openfda": {
                    "brand_name": ["Tylenol"],
                    "generic_name": ["Acetaminophen"],
                    "manufacturer_name": ["..."],
                    "route": ["ORAL"],
                    "pharm_class_epc": ["..."]
                },
                "indications_and_usage": ["..."],
                "dosage_and_administration": ["..."],
                "contraindications": ["..."],
                "warnings": ["..."],
                "adverse_reactions": ["..."],
                "drug_interactions": ["..."],
                "overdosage": ["..."],
                ...
            }
        ]
    }
    """

    def __init__(self):
        self.downloaded_file: Optional[Path] = None
        self.processed_count = 0
        self.id_counter: Dict[str, int] = {}

    def download_json(self, url: str, filename: str = "openfda_drug_labels.json") -> Path:
        """
        Download openFDA bulk JSON file

        Args:
            url: URL to download from
            filename: Output filename

        Returns:
            Path to downloaded file
        """
        output_path = DOWNLOADS_DIR / filename
        print(f"Downloading openFDA data from {url}...")
        print("Note: openFDA bulk files can be large (several GB)")

        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()

        # Check if it's a ZIP file
        if url.endswith('.zip'):
            print("Extracting ZIP archive...")
            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                # Find JSON file in archive
                json_files = [f for f in zf.namelist() if f.endswith('.json')]
                if not json_files:
                    raise ValueError("No JSON file found in ZIP archive")

                json_content = zf.read(json_files[0])
                output_path.write_bytes(json_content)
        else:
            output_path.write_bytes(response.content)

        print(f"Downloaded to: {output_path}")
        self.downloaded_file = output_path
        return output_path

    def parse_json(self, json_path: Path) -> Generator[Dict, None, None]:
        """
        Parse openFDA JSON file and yield drug labels

        Args:
            json_path: Path to JSON file

        Yields:
            Dict containing parsed drug label data
        """
        print(f"Parsing JSON: {json_path}")

        # Try to load entire file first
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # openFDA format has results array
            results = data.get('results', data)
            if not isinstance(results, list):
                results = [results]

            print(f"Found {len(results)} drug labels")

            for item in results:
                try:
                    parsed = self._parse_drug_label(item)
                    if parsed:
                        yield parsed
                except Exception as e:
                    print(f"Error parsing drug label: {e}")
                    continue

        except json.JSONDecodeError:
            # Try line-by-line for NDJSON format
            print("Trying NDJSON format...")
            with open(json_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                        parsed = self._parse_drug_label(item)
                        if parsed:
                            yield parsed
                    except Exception as e:
                        continue

    def _get_field(self, data: Dict, field: str, default: Any = None) -> Any:
        """
        Get field from openFDA data, handling array values

        openFDA often returns arrays even for single values
        """
        value = data.get(field, default)
        if isinstance(value, list) and len(value) > 0:
            # Join multiple values or return first
            if isinstance(value[0], str):
                return ' '.join(value)
            return value[0]
        return value or default

    def _get_list_field(self, data: Dict, field: str) -> List[str]:
        """Get field as list, parsing if needed"""
        value = data.get(field, [])

        if not value:
            return []

        if isinstance(value, str):
            # Parse bullet points or split by sentences
            return self._parse_text_to_list(value)

        if isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, str):
                    # Each item might be a long text, parse it
                    parsed = self._parse_text_to_list(item)
                    result.extend(parsed)
                elif item:
                    result.append(str(item))
            return result

        return []

    def _parse_text_to_list(self, text: str, max_items: int = 10) -> List[str]:
        """Parse long text into list items"""
        text = strip_html(text)

        # Split by common patterns
        # - Bullet points
        # - Numbers (1. 2. etc)
        # - Newlines with capital letters
        items = []

        # Try bullet/number patterns first
        patterns = [
            r'(?:^|\n)\s*[-•*]\s*(.+?)(?=\n\s*[-•*]|\n\n|$)',
            r'(?:^|\n)\s*\d+[.)]\s*(.+?)(?=\n\s*\d+[.)]|\n\n|$)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
            if matches:
                items = [m.strip() for m in matches if m.strip()]
                break

        if not items:
            # Fall back to sentence splitting
            sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
            items = [s.strip() for s in sentences if s.strip() and len(s) > 10]

        # Limit and clean
        return [truncate_text(item, 200) for item in items[:max_items]]

    def _parse_drug_label(self, label_data: Dict) -> Optional[Dict]:
        """
        Parse a single drug label

        Returns:
            Dict with drug label data or None if invalid
        """
        # Get openfda metadata
        openfda = label_data.get('openfda', {})

        # Get drug name (prefer generic, fall back to brand)
        generic_name = self._get_field(openfda, 'generic_name', '')
        brand_name = self._get_field(openfda, 'brand_name', '')

        title = generic_name or brand_name
        if not title:
            return None

        # Get drug class
        drug_class = self._get_field(openfda, 'pharm_class_epc', '')
        if not drug_class:
            drug_class = self._get_field(openfda, 'pharmacologic_class', '')

        # Get route of administration
        route = self._get_field(openfda, 'route', '')

        # Get manufacturer
        manufacturer = self._get_field(openfda, 'manufacturer_name', '')

        # Get main content fields
        indications = self._get_field(label_data, 'indications_and_usage', '')
        dosage = self._get_field(label_data, 'dosage_and_administration', '')
        contraindications = self._get_field(label_data, 'contraindications', '')
        warnings = self._get_field(label_data, 'warnings', '')
        warnings_precautions = self._get_field(label_data, 'warnings_and_precautions', '')
        adverse = self._get_field(label_data, 'adverse_reactions', '')
        interactions = self._get_field(label_data, 'drug_interactions', '')
        overdosage = self._get_field(label_data, 'overdosage', '')
        boxed_warning = self._get_field(label_data, 'boxed_warning', '')

        # Get SPL set ID for reference
        spl_set_id = self._get_field(label_data, 'set_id', '')

        return {
            'title': title,
            'brand_name': brand_name,
            'generic_name': generic_name,
            'drug_class': drug_class,
            'route': route,
            'manufacturer': manufacturer,
            'indications': indications,
            'dosage': dosage,
            'contraindications': contraindications,
            'warnings': warnings,
            'warnings_precautions': warnings_precautions,
            'adverse_reactions': adverse,
            'drug_interactions': interactions,
            'overdosage': overdosage,
            'boxed_warning': boxed_warning,
            'spl_set_id': spl_set_id
        }

    def _get_unique_id(self, title: str) -> str:
        """Generate unique ID, handling duplicates"""
        slug = slugify(title)
        if slug not in self.id_counter:
            self.id_counter[slug] = 0
        self.id_counter[slug] += 1
        return f"{slug}_{self.id_counter[slug]:03d}"

    def transform_to_schema(self, raw_data: Dict) -> Optional[Dict]:
        """
        Transform raw openFDA data to our medication schema

        Args:
            raw_data: Parsed drug label data

        Returns:
            Dict matching MedicationEntry schema
        """
        title = raw_data.get('title', '')
        if not title:
            return None

        # Generate ID
        doc_id = self._get_unique_id(title)

        # Create summary from indications
        indications = raw_data.get('indications', '')
        content = normalize_text(indications)
        content = truncate_text(content, max_length=500)

        if not content:
            # Fall back to any available description
            content = f"{title} is a medication."

        # Parse uses from indications
        uses = self._get_list_field({'indications': indications}, 'indications')

        # Parse dosage info
        dosage_text = raw_data.get('dosage', '')
        dosage_info = None
        if dosage_text:
            dosage_info = {
                'note': truncate_text(normalize_text(dosage_text), 300)
            }

        # Parse side effects from adverse reactions
        adverse = raw_data.get('adverse_reactions', '')
        side_effects = self._parse_text_to_list(adverse)[:8]

        # Parse contraindications
        contras = raw_data.get('contraindications', '')
        contraindications = self._parse_text_to_list(contras)[:8]

        # Parse warnings (combine multiple warning fields)
        warn_text = raw_data.get('warnings', '') + ' ' + raw_data.get('warnings_precautions', '')
        boxed = raw_data.get('boxed_warning', '')
        if boxed:
            warn_text = f"BOXED WARNING: {boxed} {warn_text}"
        warnings = self._parse_text_to_list(warn_text)[:8]

        # Parse drug interactions
        interact = raw_data.get('drug_interactions', '')
        drug_interactions = self._parse_text_to_list(interact)[:8]

        # Overdose warning
        overdose = raw_data.get('overdosage', '')
        overdose_warning = truncate_text(normalize_text(overdose), 300)

        # Build keywords
        keywords_en = [title.lower()]
        if raw_data.get('brand_name'):
            keywords_en.append(raw_data['brand_name'].lower())
        if raw_data.get('drug_class'):
            keywords_en.append(raw_data['drug_class'].lower())
        keywords_en = dedupe_keywords(keywords_en)

        # Turkish keywords - for medications, names often stay the same
        keywords_tr = [title.lower()]
        if raw_data.get('brand_name'):
            keywords_tr.append(raw_data['brand_name'].lower())

        # Common Turkish drug-related phrases
        keywords_tr.append(f"{title.lower()} ne işe yarar")
        keywords_tr.append(f"{title.lower()} yan etkileri")
        keywords_tr = dedupe_keywords(keywords_tr)

        # Generate typos
        typos_tr = generate_typos_tr(keywords_tr)

        # Build entry
        entry = {
            'id': doc_id,
            'title': title,
            'title_tr': title,  # Drug names usually same in Turkish
            'category': 'medications',
            'drug_class': raw_data.get('drug_class', ''),
            'source_name': 'openFDA (Drug Label)',
            'source_url': f"https://open.fda.gov/apis/drug/label/",
            'retrieved_date': RETRIEVED_DATE,
            'content': content,
            'uses': uses,
            'dosage_info': dosage_info,
            'side_effects': side_effects,
            'contraindications': contraindications,
            'warnings': warnings,
            'drug_interactions': drug_interactions,
            'overdose_warning': overdose_warning,
            'keywords_en': keywords_en,
            'keywords_tr': keywords_tr,
            'typos_tr': typos_tr,
            'brand_examples_tr': [],  # Would need TR-specific data
            'safety_disclaimer': (
                "Bu bilgiler ABD FDA verilere dayanmaktadır ve yalnızca genel bilgilendirme amaçlıdır. "
                "Türkiye'deki kullanım koşulları farklılık gösterebilir. "
                "İlaç kullanmadan önce mutlaka doktorunuza veya eczacınıza danışın."
            ),
            'jurisdiction': 'TR',
            'safety_level': 'medication',
            'source_jurisdiction': 'US'  # Important: data is from US FDA
        }

        return entry

    def process(self, json_path: Optional[Path] = None, url: Optional[str] = None) -> List[Dict]:
        """
        Run the full ETL process

        Args:
            json_path: Path to local JSON file (optional)
            url: URL to download JSON from (optional)

        Returns:
            List of validated entries
        """
        # Download if URL provided and no local file
        if url and not json_path:
            json_path = self.download_json(url)
        elif not json_path and self.downloaded_file:
            json_path = self.downloaded_file

        if not json_path or not json_path.exists():
            raise ValueError("No JSON file available to process")

        results = []
        errors = []
        processed = 0
        seen_titles = set()  # For deduplication

        for raw_data in self.parse_json(json_path):
            # Check limit
            if MAX_RECORDS_PER_SOURCE and processed >= MAX_RECORDS_PER_SOURCE:
                print(f"Reached processing limit: {MAX_RECORDS_PER_SOURCE}")
                break

            # Simple dedup by title
            title = raw_data.get('title', '').lower()
            if title in seen_titles:
                continue
            seen_titles.add(title)

            # Transform to schema
            transformed = self.transform_to_schema(raw_data)
            if not transformed:
                continue

            # Validate
            is_valid, entry, error = validate_medication_entry(transformed)
            if is_valid:
                results.append(entry.model_dump())
                processed += 1
            else:
                errors.append(f"{transformed.get('title', 'Unknown')}: {error}")

        print(f"Processed {processed} entries, {len(errors)} errors")

        if errors[:5]:
            print("Sample errors:")
            for err in errors[:5]:
                print(f"  - {err}")

        self.processed_count = processed
        return results

    def save_results(self, results: List[Dict], output_path: Optional[Path] = None) -> Path:
        """
        Save processed results to JSON file

        Args:
            results: List of validated entries
            output_path: Output file path (optional)

        Returns:
            Path to output file
        """
        if not output_path:
            output_path = OUTPUT_DIR / "medications_openfda.json"

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"Saved {len(results)} entries to: {output_path}")
        return output_path


def run_openfda_etl(url: Optional[str] = None, json_path: Optional[Path] = None) -> Dict:
    """
    Convenience function to run openFDA ETL

    Args:
        url: URL to download JSON from
        json_path: Path to local JSON file

    Returns:
        ETL result summary
    """
    etl = OpenFDAETL()

    try:
        results = etl.process(json_path=json_path, url=url)
        output_path = etl.save_results(results)

        return {
            'source': 'openFDA',
            'total_records': etl.processed_count,
            'successful': len(results),
            'failed': etl.processed_count - len(results),
            'output_file': str(output_path)
        }
    except Exception as e:
        return {
            'source': 'openFDA',
            'total_records': 0,
            'successful': 0,
            'failed': 0,
            'error': str(e)
        }


if __name__ == "__main__":
    from .config import OPENFDA_DRUG_LABEL_URL

    result = run_openfda_etl(url=OPENFDA_DRUG_LABEL_URL)
    print(json.dumps(result, indent=2))
