"""
MedlinePlus XML ETL Module
Downloads and processes MedlinePlus health topics XML data
"""

import xml.etree.ElementTree as ET
import requests
import zipfile
import io
from pathlib import Path
from typing import List, Dict, Optional, Generator
from datetime import date
import json
import re

from .config import (
    DOWNLOADS_DIR, OUTPUT_DIR, RETRIEVED_DATE,
    MAX_RECORDS_PER_SOURCE
)
from .utils import (
    generate_id, strip_html, normalize_text, truncate_text,
    generate_keywords_tr, generate_typos_tr, dedupe_keywords,
    classify_category, classify_safety_level, slugify
)
from .schemas import SymptomDiseaseEntry, validate_symptom_disease_entry


class MedlinePlusETL:
    """
    ETL pipeline for MedlinePlus XML data

    MedlinePlus XML structure (simplified):
    <health-topics>
      <health-topic>
        <title>Headache</title>
        <full-summary>Description text...</full-summary>
        <url>https://medlineplus.gov/headache.html</url>
        <group>Symptoms</group>
        <also-called>Cephalalgia</also-called>
        <see-reference>Migraine</see-reference>
        ...
      </health-topic>
    </health-topics>
    """

    def __init__(self):
        self.downloaded_file: Optional[Path] = None
        self.processed_count = 0
        self.id_counter: Dict[str, int] = {}  # Track IDs for uniqueness

    def download_xml(self, url: str, filename: str = "medlineplus_topics.xml") -> Path:
        """
        Download MedlinePlus XML file

        Args:
            url: URL to download from
            filename: Output filename

        Returns:
            Path to downloaded file
        """
        output_path = DOWNLOADS_DIR / filename
        print(f"Downloading MedlinePlus XML from {url}...")

        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()

        # Check if it's a ZIP file
        content_type = response.headers.get('content-type', '')

        if url.endswith('.zip') or 'zip' in content_type:
            # Extract XML from ZIP
            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                # Find XML file in archive
                xml_files = [f for f in zf.namelist() if f.endswith('.xml')]
                if not xml_files:
                    raise ValueError("No XML file found in ZIP archive")

                xml_content = zf.read(xml_files[0])
                output_path.write_bytes(xml_content)
        else:
            # Direct XML download
            output_path.write_bytes(response.content)

        print(f"Downloaded to: {output_path}")
        self.downloaded_file = output_path
        return output_path

    def parse_xml(self, xml_path: Path) -> Generator[Dict, None, None]:
        """
        Parse MedlinePlus XML file and yield health topics

        Args:
            xml_path: Path to XML file

        Yields:
            Dict containing parsed health topic data
        """
        print(f"Parsing XML: {xml_path}")

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
        except ET.ParseError as e:
            print(f"XML parse error: {e}")
            # Try to parse with error recovery
            with open(xml_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            # Simple cleanup
            content = re.sub(r'&(?!amp;|lt;|gt;|apos;|quot;)', '&amp;', content)
            root = ET.fromstring(content)

        # Find all health topic elements
        # MedlinePlus XML might use different structures
        topics = root.findall('.//health-topic')
        if not topics:
            # Try alternate paths
            topics = root.findall('.//topic')
        if not topics:
            topics = list(root)  # Get direct children

        print(f"Found {len(topics)} health topics")

        for topic in topics:
            try:
                parsed = self._parse_topic(topic)
                if parsed:
                    yield parsed
            except Exception as e:
                print(f"Error parsing topic: {e}")
                continue

    def _parse_topic(self, topic_elem: ET.Element) -> Optional[Dict]:
        """
        Parse a single health topic XML element

        Returns:
            Dict with topic data or None if invalid
        """
        # Extract title
        title_elem = topic_elem.find('title')
        if title_elem is None or not title_elem.text:
            # Try alternate attribute
            title = topic_elem.get('title', '')
        else:
            title = title_elem.text

        if not title:
            return None

        # Extract full summary/description
        summary = ""
        for summary_tag in ['full-summary', 'summary', 'description', 'content']:
            summary_elem = topic_elem.find(summary_tag)
            if summary_elem is not None:
                # Get all text including nested elements
                summary = ET.tostring(summary_elem, encoding='unicode', method='text')
                if not summary:
                    summary = summary_elem.text or ""
                break

        # Clean and normalize
        title = strip_html(title).strip()
        summary = normalize_text(summary)

        if not summary:
            # Try to get from any text content
            summary = normalize_text(topic_elem.text or "")

        # Extract URL
        url = ""
        url_elem = topic_elem.find('url')
        if url_elem is not None:
            url = url_elem.text or url_elem.get('href', '')
        if not url:
            url = topic_elem.get('url', '')

        # Extract groups/categories
        groups = []
        for group_elem in topic_elem.findall('.//group'):
            if group_elem.text:
                groups.append(group_elem.text)
        # Also check group attribute
        group_attr = topic_elem.get('group', '')
        if group_attr:
            groups.append(group_attr)

        # Extract alternate names (also-called, synonyms)
        also_called = []
        for also_elem in topic_elem.findall('.//also-called'):
            if also_elem.text:
                also_called.append(also_elem.text.strip())

        # Extract see references
        see_refs = []
        for ref_elem in topic_elem.findall('.//see-reference'):
            if ref_elem.text:
                see_refs.append(ref_elem.text.strip())

        # Extract related topics
        related = []
        for rel_elem in topic_elem.findall('.//related-topic'):
            if rel_elem.text:
                related.append(rel_elem.text.strip())

        # Build the parsed data
        return {
            'title': title,
            'summary': summary,
            'url': url,
            'groups': groups,
            'also_called': also_called,
            'see_references': see_refs,
            'related': related
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
        Transform raw MedlinePlus data to our schema

        Args:
            raw_data: Parsed XML data

        Returns:
            Dict matching SymptomDiseaseEntry schema
        """
        title = raw_data.get('title', '')
        summary = raw_data.get('summary', '')

        if not title or not summary:
            return None

        # Classify category
        groups = raw_data.get('groups', [])
        category = classify_category(title, summary, groups)

        # Classify safety level
        safety_level = classify_safety_level(title, summary, category)

        # Generate ID
        doc_id = self._get_unique_id(title)

        # Build keywords from title, also-called, related
        keywords_en = [title.lower()]
        keywords_en.extend([a.lower() for a in raw_data.get('also_called', [])])
        keywords_en.extend([r.lower() for r in raw_data.get('related', [])[:5]])
        keywords_en = dedupe_keywords(keywords_en)

        # Generate Turkish keywords
        keywords_tr = generate_keywords_tr(keywords_en)

        # Generate typos
        typos_tr = generate_typos_tr(keywords_tr)

        # Truncate summary if too long
        content = truncate_text(summary, max_length=1000)

        # Build entry
        entry = {
            'id': doc_id,
            'title': title,
            'title_tr': '',  # Would need translation API for full translation
            'category': category,
            'source_name': 'MedlinePlus - NIH',
            'source_url': raw_data.get('url', ''),
            'retrieved_date': RETRIEVED_DATE,
            'content': content,
            'symptoms': [],  # MedlinePlus doesn't have structured symptoms
            'causes': [],
            'what_to_do': [],
            'do_not': [],
            'red_flags': [],
            'when_to_see_doctor': '',
            'keywords_en': keywords_en,
            'keywords_tr': keywords_tr,
            'typos_tr': typos_tr,
            'jurisdiction': 'TR',
            'safety_level': safety_level
        }

        # Add crisis info for mental health
        if category == 'mental_health':
            entry['crisis_info'] = "Acil risk varsa 112'yi arayın veya en yakın acil servise gidin."

        return entry

    def process(self, xml_path: Optional[Path] = None, url: Optional[str] = None) -> List[Dict]:
        """
        Run the full ETL process

        Args:
            xml_path: Path to local XML file (optional)
            url: URL to download XML from (optional)

        Returns:
            List of validated entries
        """
        # Download if URL provided and no local file
        if url and not xml_path:
            xml_path = self.download_xml(url)
        elif not xml_path and self.downloaded_file:
            xml_path = self.downloaded_file

        if not xml_path or not xml_path.exists():
            raise ValueError("No XML file available to process")

        results = []
        errors = []
        processed = 0

        for raw_data in self.parse_xml(xml_path):
            # Check limit
            if MAX_RECORDS_PER_SOURCE and processed >= MAX_RECORDS_PER_SOURCE:
                print(f"Reached processing limit: {MAX_RECORDS_PER_SOURCE}")
                break

            # Transform to schema
            transformed = self.transform_to_schema(raw_data)
            if not transformed:
                continue

            # Validate
            is_valid, entry, error = validate_symptom_disease_entry(transformed)
            if is_valid:
                results.append(entry.model_dump())
                processed += 1
            else:
                errors.append(f"{transformed.get('title', 'Unknown')}: {error}")

        print(f"Processed {processed} entries, {len(errors)} errors")

        if errors[:5]:  # Show first 5 errors
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
            output_path = OUTPUT_DIR / "symptoms_diseases_medlineplus.json"

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"Saved {len(results)} entries to: {output_path}")
        return output_path


def run_medlineplus_etl(url: Optional[str] = None, xml_path: Optional[Path] = None) -> Dict:
    """
    Convenience function to run MedlinePlus ETL

    Args:
        url: URL to download XML from
        xml_path: Path to local XML file

    Returns:
        ETL result summary
    """
    etl = MedlinePlusETL()

    try:
        results = etl.process(xml_path=xml_path, url=url)
        output_path = etl.save_results(results)

        return {
            'source': 'MedlinePlus',
            'total_records': etl.processed_count,
            'successful': len(results),
            'failed': etl.processed_count - len(results),
            'output_file': str(output_path)
        }
    except Exception as e:
        return {
            'source': 'MedlinePlus',
            'total_records': 0,
            'successful': 0,
            'failed': 0,
            'error': str(e)
        }


if __name__ == "__main__":
    # Test with a sample file or URL
    from .config import MEDLINEPLUS_XML_URLS

    result = run_medlineplus_etl(url=MEDLINEPLUS_XML_URLS['health_topics'])
    print(json.dumps(result, indent=2))
