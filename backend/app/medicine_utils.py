"""
İlaç İsim İşleme Yardımcıları
Hem main.py hem de RAG router tarafından kullanılır.
Multi-word ilaç tespiti, fuzzy matching, bağlam analizi.
"""

import re
from typing import Tuple, List, Optional

from app.medicines import TURKISH_MEDICINE_DICTIONARY, MEDICINE_TYPOS


# Çift anlamlı kelimeler - bağlam kontrolü gerektirenler
AMBIGUOUS_MEDICINE_NAMES = {
    "aferin": {
        "non_medicine_contexts": [
            "aferin sana", "aferin size", "aferin ona", "aferin bana",
            "aferin çocuğum", "aferin kızım", "aferin oğlum",
            "aferin be",
            "bravo", "tebrik", "helal olsun",
        ],
        "non_medicine_patterns": [
            r"\baferin\s+ya[!.?\s]*$",
            r"\baferin\s+valla[!.?\s]*$",
        ],
        "medicine_contexts": [
            "alsam", "almalı", "alayım", "aldım", "alıyor", "almak", "alınır",
            "içsem", "içmeliyim", "içeyim", "içtim", "içiyor", "içmek", "içilir",
            "kullansam", "kullanmalı", "kullanayım", "kullandım", "kullanıyor", "kullanılır", "kullanmak",
            "mg", "tablet", "hap", "şurup", "doz", "günde", "saatte",
            "ağrı", "ateş", "baş", "kafa", "grip", "soğuk algınlığı",
            "reçete", "doktor", "eczane", "ilaç",
            "forte", "plus", "cold", "hot",
            "neden", "niçin", "ne için", "ne zaman", "nasıl", "ne işe", "faydası",
            "etkisi", "yan etki", "yan etkisi", "zararlı", "faydalı", "işe yarar",
        ],
    },
}


# Türkçe hal ekleri
TURKISH_SUFFIXES = [
    "lerden", "lardan", "lerde", "larda", "lerin", "ların", "lere", "lara",
    "lerle", "larla", "leri", "ları", "ler", "lar",
    "ından", "inden", "undan", "ünden", "ında", "inde", "unda", "ünde",
    "ının", "inin", "unun", "ünün", "ına", "ine", "una", "üne",
    "ıyla", "iyle", "uyla", "üyle", "ını", "ini", "unu", "ünü",
    "dan", "den", "tan", "ten",
    "da", "de", "ta", "te",
    "a", "e", "ya", "ye",
    "ı", "i", "u", "ü",
    "ım", "im", "um", "üm",
    "ın", "in", "un", "ün",
    "sı", "si", "su", "sü",
    "mı", "mi", "mu", "mü",
]


def is_medicine_context(word: str, full_text: str) -> bool:
    """
    Kelimenin ilaç bağlamında mı yoksa günlük dilde mi kullanıldığını kontrol eder.
    """
    word_lower = word.lower()
    text_lower = full_text.lower()

    if word_lower not in AMBIGUOUS_MEDICINE_NAMES:
        return True

    context_info = AMBIGUOUS_MEDICINE_NAMES[word_lower]

    for non_med_phrase in context_info["non_medicine_contexts"]:
        if non_med_phrase in text_lower:
            return False

    if "non_medicine_patterns" in context_info:
        for pattern in context_info["non_medicine_patterns"]:
            if re.search(pattern, text_lower):
                return False

    for med_keyword in context_info["medicine_contexts"]:
        if med_keyword in text_lower:
            return True

    if re.match(r'^aferin[!.\s]*$', text_lower.strip()):
        return False

    if re.search(r'\baferin\s+(sana|size|ona|bana|bize|onlara)\b', text_lower):
        return False

    words_in_text = len(text_lower.split())
    health_hints = ["ağrı", "agri", "ateş", "ates", "hasta", "ilaç", "ilac",
                    "doktor", "eczane", "baş", "bas", "grip", "nezle"]
    has_health_hint = any(hint in text_lower for hint in health_hints)

    if words_in_text <= 3 and not has_health_hint:
        return False

    return True


def levenshtein_distance(s1: str, s2: str) -> int:
    """İki string arasındaki Levenshtein (edit) mesafesini hesaplar"""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def generate_suffix_candidates(word: str) -> list:
    """Kelime için kademeli ek kırpma adayları üretir."""
    word_lower = word.lower()
    candidates = [word_lower]

    current = word_lower
    for _ in range(3):
        for suffix in TURKISH_SUFFIXES:
            if current.endswith(suffix) and len(current) > len(suffix) + 2:
                stripped = current[:-len(suffix)]
                if stripped not in candidates:
                    candidates.append(stripped)
                current = stripped
                break
        else:
            break

    return candidates


def strip_turkish_suffix(word: str) -> str:
    """Türkçe ekleri kelimeden temizler."""
    word_lower = word.lower()
    candidates = generate_suffix_candidates(word_lower)

    for candidate in candidates:
        if candidate in TURKISH_MEDICINE_DICTIONARY or candidate in MEDICINE_TYPOS:
            return candidate

    return candidates[-1] if len(candidates[-1]) >= 3 else word_lower


def find_medicine_match(word: str, max_distance: int = 2) -> Tuple[Optional[str], Optional[str]]:
    """
    Verilen kelime için en yakın ilaç eşleşmesini bulur.

    Returns:
        tuple: (bulunan_ilaç_ismi, İngilizce_karşılık) veya (None, None)
    """
    word_lower = word.lower()

    if word_lower in MEDICINE_TYPOS:
        corrected = MEDICINE_TYPOS[word_lower]
        if corrected in TURKISH_MEDICINE_DICTIONARY:
            return (corrected, TURKISH_MEDICINE_DICTIONARY[corrected])

    if word_lower in TURKISH_MEDICINE_DICTIONARY:
        return (word_lower, TURKISH_MEDICINE_DICTIONARY[word_lower])

    candidates = generate_suffix_candidates(word_lower)
    for candidate in candidates[1:]:
        if candidate in TURKISH_MEDICINE_DICTIONARY:
            return (candidate, TURKISH_MEDICINE_DICTIONARY[candidate])
        if candidate in MEDICINE_TYPOS:
            corrected = MEDICINE_TYPOS[candidate]
            if corrected in TURKISH_MEDICINE_DICTIONARY:
                return (corrected, TURKISH_MEDICINE_DICTIONARY[corrected])

    best_match = None
    best_distance = max_distance + 1

    for candidate in candidates:
        if len(candidate) < 4:
            continue

        for medicine in TURKISH_MEDICINE_DICTIONARY.keys():
            if len(medicine) < 4:
                continue

            distance = levenshtein_distance(candidate, medicine)

            if len(medicine) <= 5 or len(candidate) <= 5:
                adjusted_max = 1
            else:
                adjusted_max = max_distance

            if distance <= adjusted_max and distance < best_distance:
                best_distance = distance
                best_match = medicine

    if best_match:
        return (best_match, TURKISH_MEDICINE_DICTIONARY[best_match])

    return (None, None)


def generate_ngrams(words: list, n: int) -> list:
    """N-gram'ları üretir (kelime listesinden)"""
    return [' '.join(words[i:i+n]) for i in range(len(words) - n + 1)]


def detect_medicines(text: str) -> list:
    """
    Metindeki ilaç isimlerini tespit eder (bağlam kontrolü dahil).
    Multi-word ilaç isimlerini de yakalar (aferin forte, tylol hot, vb.)

    Returns:
        list: Bulunan ilaç isimleri [(türkçe_isim, ingilizce_karşılık), ...]
    """
    text_lower = text.lower()
    words = re.findall(r'\b[\wğüşıöçĞÜŞİÖÇ]+\b', text_lower, re.UNICODE)
    found_medicines = []
    matched_positions = set()

    for n in [3, 2]:
        ngrams = generate_ngrams(words, n)
        for i, ngram in enumerate(ngrams):
            positions = set(range(i, i + n))
            if positions & matched_positions:
                continue

            if ngram in TURKISH_MEDICINE_DICTIONARY:
                if is_medicine_context(ngram, text):
                    found_medicines.append((ngram, TURKISH_MEDICINE_DICTIONARY[ngram]))
                    matched_positions.update(positions)
                    print(f"[MEDICINE-NGRAM] '{ngram}' bulundu")

    for i, word in enumerate(words):
        if i in matched_positions:
            continue
        if len(word) < 3:
            continue

        medicine_name, english_name = find_medicine_match(word)

        if medicine_name and english_name:
            if is_medicine_context(medicine_name, text):
                found_medicines.append((medicine_name, english_name))
                matched_positions.add(i)

    return found_medicines


def preprocess_turkish_medicine_names(text: str) -> str:
    """
    Çeviriden önce Türkçe ilaç isimlerini İngilizce karşılıklarına dönüştürür.
    - Multi-word ilaç isimlerini yakalar (aferin forte, tylol hot)
    - Türkçe ekleri handle eder (parolü, parolden, parole)
    - Yanlış yazımları düzeltir (paroll, tilol, apranaks)
    - Fuzzy matching ile benzer kelimeleri yakalar
    - Bağlam analizi yapar (aferin sana vs aferin almalı mıyım)
    """
    text_lower = text.lower()
    words = re.findall(r'\b[\wğüşıöçĞÜŞİÖÇ]+\b', text_lower, re.UNICODE)
    original_words = re.findall(r'\b[\wğüşıöçĞÜŞİÖÇ]+\b', text, re.UNICODE)
    result = text

    replacements = []
    matched_positions = set()

    for n in [3, 2]:
        ngrams = generate_ngrams(words, n)
        original_ngrams = generate_ngrams(original_words, n)

        for i, (ngram, orig_ngram) in enumerate(zip(ngrams, original_ngrams)):
            positions = set(range(i, i + n))
            if positions & matched_positions:
                continue

            if ngram in TURKISH_MEDICINE_DICTIONARY:
                if is_medicine_context(ngram, text):
                    replacements.append((orig_ngram, TURKISH_MEDICINE_DICTIONARY[ngram]))
                    matched_positions.update(positions)
                    print(f"[MEDICINE-NGRAM] '{orig_ngram}' → '{TURKISH_MEDICINE_DICTIONARY[ngram][:40]}...'")

    for i, (word, orig_word) in enumerate(zip(words, original_words)):
        if i in matched_positions:
            continue
        if len(word) < 3:
            continue

        medicine_name, english_name = find_medicine_match(word)

        if medicine_name and english_name:
            if not is_medicine_context(medicine_name, text):
                print(f"[CONTEXT] '{orig_word}' → ilaç DEĞİL, takdir/günlük kullanım")
                continue

            replacements.append((orig_word, english_name))
            matched_positions.add(i)
            print(f"[MEDICINE] '{orig_word}' → '{medicine_name}' → '{english_name[:40]}...'")

    replacements.sort(key=lambda x: len(x[0]), reverse=True)

    for original, replacement in replacements:
        pattern = r'\b' + re.escape(original) + r'\b'
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    return result
