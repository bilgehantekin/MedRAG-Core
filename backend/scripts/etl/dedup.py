"""
Deduplication Module
Handles detection and removal of duplicate entries
"""

from typing import List, Dict, Set, Tuple, Optional
from difflib import SequenceMatcher
import re


def normalize_for_comparison(text: str) -> str:
    """Normalize text for comparison (lowercase, remove punctuation, etc.)"""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def similarity_score(text1: str, text2: str) -> float:
    """Calculate similarity score between two texts (0-1)"""
    norm1 = normalize_for_comparison(text1)
    norm2 = normalize_for_comparison(text2)
    return SequenceMatcher(None, norm1, norm2).ratio()


def are_duplicates(entry1: Dict, entry2: Dict, threshold: float = 0.85) -> bool:
    """
    Check if two entries are duplicates based on title and content similarity

    Args:
        entry1: First entry
        entry2: Second entry
        threshold: Similarity threshold (0-1)

    Returns:
        True if entries are considered duplicates
    """
    # Compare titles
    title1 = entry1.get('title', '')
    title2 = entry2.get('title', '')

    title_sim = similarity_score(title1, title2)

    # Exact title match
    if title_sim > 0.95:
        return True

    # High title similarity and same category
    if title_sim > threshold:
        cat1 = entry1.get('category', '')
        cat2 = entry2.get('category', '')
        if cat1 == cat2:
            return True

    # Check content similarity if titles are somewhat similar
    if title_sim > 0.7:
        content1 = entry1.get('content', '')
        content2 = entry2.get('content', '')

        if content1 and content2:
            content_sim = similarity_score(content1[:500], content2[:500])
            if content_sim > threshold:
                return True

    return False


def find_duplicates(entries: List[Dict], threshold: float = 0.85) -> List[Tuple[int, int]]:
    """
    Find all duplicate pairs in a list of entries

    Args:
        entries: List of entries to check
        threshold: Similarity threshold

    Returns:
        List of (index1, index2) tuples for duplicate pairs
    """
    duplicates = []
    n = len(entries)

    for i in range(n):
        for j in range(i + 1, n):
            if are_duplicates(entries[i], entries[j], threshold):
                duplicates.append((i, j))

    return duplicates


def deduplicate_entries(
    entries: List[Dict],
    threshold: float = 0.85,
    prefer_longer: bool = True
) -> Tuple[List[Dict], int]:
    """
    Remove duplicate entries from list

    Args:
        entries: List of entries
        threshold: Similarity threshold for duplicate detection
        prefer_longer: When duplicates found, keep the one with longer content

    Returns:
        Tuple of (deduplicated list, number of duplicates removed)
    """
    if not entries:
        return [], 0

    # Build normalized title index for faster lookup
    title_index: Dict[str, List[int]] = {}
    for i, entry in enumerate(entries):
        norm_title = normalize_for_comparison(entry.get('title', ''))
        if norm_title not in title_index:
            title_index[norm_title] = []
        title_index[norm_title].append(i)

    # Track indices to remove
    to_remove: Set[int] = set()

    # First pass: exact title duplicates
    for norm_title, indices in title_index.items():
        if len(indices) > 1:
            # Keep the one with longest content
            if prefer_longer:
                best_idx = max(
                    indices,
                    key=lambda i: len(entries[i].get('content', ''))
                )
            else:
                best_idx = indices[0]

            for idx in indices:
                if idx != best_idx:
                    to_remove.add(idx)

    # Second pass: similar title duplicates (more expensive)
    remaining_indices = [i for i in range(len(entries)) if i not in to_remove]

    for i, idx1 in enumerate(remaining_indices):
        if idx1 in to_remove:
            continue

        for idx2 in remaining_indices[i + 1:]:
            if idx2 in to_remove:
                continue

            entry1 = entries[idx1]
            entry2 = entries[idx2]

            # Skip if different categories (less likely to be duplicates)
            if entry1.get('category') != entry2.get('category'):
                continue

            if are_duplicates(entry1, entry2, threshold):
                # Keep the better one
                if prefer_longer:
                    len1 = len(entry1.get('content', ''))
                    len2 = len(entry2.get('content', ''))
                    if len1 >= len2:
                        to_remove.add(idx2)
                    else:
                        to_remove.add(idx1)
                else:
                    to_remove.add(idx2)

    # Build result list
    result = [entry for i, entry in enumerate(entries) if i not in to_remove]
    removed_count = len(to_remove)

    return result, removed_count


def merge_entries(entries: List[Dict]) -> List[Dict]:
    """
    Merge duplicate entries by combining their data

    Args:
        entries: List of entries (assumed to be duplicates of each other)

    Returns:
        List with single merged entry
    """
    if not entries:
        return []

    if len(entries) == 1:
        return entries

    # Start with the entry that has the longest content
    base = max(entries, key=lambda e: len(e.get('content', '')))
    result = base.copy()

    # Merge list fields
    list_fields = [
        'symptoms', 'causes', 'what_to_do', 'do_not', 'red_flags',
        'uses', 'side_effects', 'contraindications', 'warnings',
        'drug_interactions', 'keywords_en', 'keywords_tr', 'typos_tr',
        'brand_examples_tr'
    ]

    for field in list_fields:
        merged_list = []
        seen = set()

        for entry in entries:
            for item in entry.get(field, []):
                item_lower = item.lower().strip()
                if item_lower and item_lower not in seen:
                    seen.add(item_lower)
                    merged_list.append(item)

        if merged_list:
            result[field] = merged_list

    # Take longest string fields
    string_fields = ['content', 'when_to_see_doctor', 'overdose_warning', 'safety_disclaimer']

    for field in string_fields:
        best = ''
        for entry in entries:
            val = entry.get(field, '')
            if len(val) > len(best):
                best = val
        if best:
            result[field] = best

    return [result]


def deduplicate_across_sources(
    source_entries: Dict[str, List[Dict]],
    threshold: float = 0.85
) -> Dict[str, List[Dict]]:
    """
    Deduplicate entries across multiple sources

    Args:
        source_entries: Dict mapping source name to list of entries
        threshold: Similarity threshold

    Returns:
        Dict with deduplicated entries per source
    """
    # Collect all entries with source info
    all_entries = []
    for source, entries in source_entries.items():
        for entry in entries:
            entry_with_source = entry.copy()
            entry_with_source['_source'] = source
            all_entries.append(entry_with_source)

    # Deduplicate
    deduped, removed = deduplicate_entries(all_entries, threshold)

    # Separate back by source
    result = {source: [] for source in source_entries.keys()}
    for entry in deduped:
        source = entry.pop('_source', 'unknown')
        if source in result:
            result[source].append(entry)

    return result


def validate_no_duplicates(entries: List[Dict], threshold: float = 0.95) -> List[str]:
    """
    Validate that a list has no exact duplicates

    Args:
        entries: List of entries to check
        threshold: High threshold for exact matches

    Returns:
        List of warning messages for any duplicates found
    """
    warnings = []
    seen_ids = set()
    seen_titles = {}

    for i, entry in enumerate(entries):
        # Check ID uniqueness
        entry_id = entry.get('id', '')
        if entry_id in seen_ids:
            warnings.append(f"Duplicate ID: {entry_id}")
        seen_ids.add(entry_id)

        # Check title uniqueness
        title = entry.get('title', '').lower()
        if title in seen_titles:
            prev_idx = seen_titles[title]
            warnings.append(
                f"Duplicate title: '{entry.get('title')}' at indices {prev_idx} and {i}"
            )
        seen_titles[title] = i

    return warnings
