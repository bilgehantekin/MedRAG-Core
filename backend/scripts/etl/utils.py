"""
ETL Utility Functions
- Turkish typo generation
- Slugify for IDs
- Text normalization
- Translation helpers
"""

import re
import hashlib
from typing import List, Set, Optional
from html import unescape

from .config import TR_CHAR_MAP, MEDICAL_TERM_TRANSLATIONS


def slugify(text: str) -> str:
    """
    Convert text to URL-safe slug format for IDs
    Example: "Headache (Cephalalgia)" -> "headache_cephalalgia"
    """
    # Remove parentheses content or convert it
    text = text.lower()
    # Remove special characters but keep alphanumeric and spaces
    text = re.sub(r'[^\w\s-]', '', text)
    # Replace spaces and hyphens with underscore
    text = re.sub(r'[-\s]+', '_', text)
    # Remove leading/trailing underscores
    text = text.strip('_')
    return text


def generate_short_hash(text: str, length: int = 4) -> str:
    """Generate a short hash for uniqueness"""
    return hashlib.md5(text.encode()).hexdigest()[:length]


def generate_id(title: str, counter: int = 1, prefix: str = "") -> str:
    """
    Generate unique ID from title
    Format: slugified_title_###
    Example: "Headache" -> "headache_001"
    """
    slug = slugify(title)
    if prefix:
        return f"{prefix}_{slug}_{counter:03d}"
    return f"{slug}_{counter:03d}"


def strip_html(text: str) -> str:
    """Remove HTML tags and decode entities"""
    if not text:
        return ""
    # Decode HTML entities
    text = unescape(text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def normalize_text(text: str) -> str:
    """Normalize text: strip HTML, normalize whitespace"""
    text = strip_html(text)
    # Remove multiple spaces
    text = re.sub(r' +', ' ', text)
    return text.strip()


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """Truncate text to max length at sentence boundary if possible"""
    if len(text) <= max_length:
        return text

    # Try to truncate at sentence boundary
    truncated = text[:max_length]
    last_period = truncated.rfind('.')

    if last_period > max_length * 0.5:  # Found a period in reasonable range
        return text[:last_period + 1]

    # Truncate at word boundary
    last_space = truncated.rfind(' ')
    if last_space > max_length * 0.7:
        return text[:last_space] + suffix

    return truncated + suffix


def remove_turkish_chars(text: str) -> str:
    """
    Remove Turkish special characters
    Example: "baş ağrısı" -> "bas agrisi"
    """
    result = text
    for tr_char, replacement in TR_CHAR_MAP.items():
        result = result.replace(tr_char, replacement)
    return result


def generate_typos_tr(keywords: List[str]) -> List[str]:
    """
    Generate common Turkish typos for keywords
    Rules:
    1. Remove Turkish special characters (ğ->g, ş->s, etc.)
    2. Remove spaces
    3. Common misspellings
    """
    typos = set()

    for keyword in keywords:
        keyword_lower = keyword.lower().strip()

        # Rule 1: Remove Turkish characters
        typo = remove_turkish_chars(keyword_lower)
        if typo != keyword_lower:
            typos.add(typo)

        # Rule 2: Without spaces (for multi-word)
        if ' ' in keyword_lower:
            typos.add(keyword_lower.replace(' ', ''))
            typos.add(remove_turkish_chars(keyword_lower.replace(' ', '')))

        # Rule 3: Common character confusions
        # i/ı confusion
        if 'i' in keyword_lower or 'ı' in keyword_lower:
            typos.add(keyword_lower.replace('ı', 'i'))
            typos.add(keyword_lower.replace('i', 'ı'))

        # ö/o confusion
        if 'ö' in keyword_lower or 'o' in keyword_lower:
            typos.add(keyword_lower.replace('ö', 'o'))

        # ü/u confusion
        if 'ü' in keyword_lower or 'u' in keyword_lower:
            typos.add(keyword_lower.replace('ü', 'u'))

    # Remove empty and duplicates that match original keywords
    original_set = {k.lower().strip() for k in keywords}
    typos = {t for t in typos if t and t not in original_set}

    return list(typos)


def translate_term(term: str) -> Optional[str]:
    """
    Translate medical term from English to Turkish using dictionary
    Returns None if translation not found
    """
    term_lower = term.lower().strip()
    return MEDICAL_TERM_TRANSLATIONS.get(term_lower)


def generate_keywords_tr(english_keywords: List[str], title_tr: Optional[str] = None) -> List[str]:
    """
    Generate Turkish keywords from English keywords
    Uses translation dictionary and adds common variations
    """
    keywords_tr = set()

    # Add Turkish title if provided
    if title_tr:
        keywords_tr.add(title_tr.lower())

    for keyword in english_keywords:
        # Try to translate
        translation = translate_term(keyword)
        if translation:
            keywords_tr.add(translation.lower())

            # Add colloquial variations for common terms
            # "başım ağrıyor" style phrases
            if "ağrısı" in translation:
                body_part = translation.replace(" ağrısı", "")
                keywords_tr.add(f"{body_part}m ağrıyor")

        # Also add original if it's commonly used in Turkish
        keyword_lower = keyword.lower()
        if keyword_lower in ['migraine', 'migren', 'vertigo', 'diabetes', 'grip']:
            keywords_tr.add(keyword_lower)

    return list(keywords_tr)


def dedupe_keywords(keywords: List[str]) -> List[str]:
    """Deduplicate keywords while preserving order"""
    seen = set()
    result = []
    for kw in keywords:
        kw_lower = kw.lower().strip()
        if kw_lower and kw_lower not in seen:
            seen.add(kw_lower)
            result.append(kw_lower)
    return result


def classify_category(title: str, content: str, groups: Optional[List[str]] = None) -> str:
    """
    Classify content into category based on keywords
    Returns: 'symptoms', 'diseases', 'mental_health', or 'general'
    """
    from .config import MENTAL_HEALTH_KEYWORDS, SYMPTOM_KEYWORDS

    text = f"{title} {content}".lower()

    # Check for mental health first (highest priority)
    for keyword in MENTAL_HEALTH_KEYWORDS:
        if keyword in text:
            return "mental_health"

    # Check MedlinePlus groups if available
    if groups:
        groups_lower = [g.lower() for g in groups]
        if any('mental' in g or 'behavioral' in g for g in groups_lower):
            return "mental_health"
        if any('symptom' in g for g in groups_lower):
            return "symptoms"

    # Check for symptoms
    for keyword in SYMPTOM_KEYWORDS:
        if keyword in text:
            return "symptoms"

    # Default to diseases
    return "diseases"


def classify_safety_level(title: str, content: str, category: str) -> str:
    """
    Classify safety level based on content
    Returns: 'general', 'sensitive', 'emergency', or 'medication'
    """
    from .config import SENSITIVE_KEYWORDS, EMERGENCY_SAFETY_KEYWORDS

    text = f"{title} {content}".lower()

    # Check for emergency
    for keyword in EMERGENCY_SAFETY_KEYWORDS:
        if keyword in text:
            return "emergency"

    # Check for sensitive topics (mental health)
    for keyword in SENSITIVE_KEYWORDS:
        if keyword in text:
            return "sensitive"

    # Mental health category is always sensitive
    if category == "mental_health":
        return "sensitive"

    return "general"


def extract_sections_from_text(text: str) -> dict:
    """
    Try to extract structured sections from free text
    Looks for patterns like "Causes:", "Symptoms:", "Treatment:" etc.
    """
    sections = {}

    # Common section headers
    headers = [
        "symptoms", "causes", "treatment", "treatments", "prevention",
        "diagnosis", "risk factors", "complications", "when to see",
        "see a doctor", "emergency", "warning signs"
    ]

    text_lower = text.lower()

    for header in headers:
        # Look for "Header:" or "Header\n" patterns
        patterns = [
            rf'{header}[:\s]+([^.]+(?:\.[^A-Z])*)',
            rf'{header}[:\s]+(.+?)(?={"|".join(headers)}|$)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL)
            if match:
                content = match.group(1).strip()
                if content:
                    # Normalize header name
                    key = header.replace(' ', '_')
                    sections[key] = content
                    break

    return sections


def parse_list_from_text(text: str) -> List[str]:
    """
    Parse bullet points or numbered lists from text
    """
    items = []

    # Split by common list patterns
    # - item
    # * item
    # 1. item
    # • item
    lines = re.split(r'[\n\r]+', text)

    for line in lines:
        line = line.strip()
        # Remove list markers
        line = re.sub(r'^[-*•]\s*', '', line)
        line = re.sub(r'^\d+[.)]\s*', '', line)

        if line and len(line) > 3:  # Skip very short items
            items.append(line)

    return items
