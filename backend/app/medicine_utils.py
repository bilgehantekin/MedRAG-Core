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
# NOT: "a" ve "e" çıkarıldı - "parola" → "parol" gibi false positive'leri önlemek için
TURKISH_SUFFIXES = [
    "lerden", "lardan", "lerde", "larda", "lerin", "ların", "lere", "lara",
    "lerle", "larla", "leri", "ları", "ler", "lar",
    "ından", "inden", "undan", "ünden", "ında", "inde", "unda", "ünde",
    "ının", "inin", "unun", "ünün", "ına", "ine", "una", "üne",
    "ıyla", "iyle", "uyla", "üyle", "ını", "ini", "unu", "ünü",
    "dan", "den", "tan", "ten",
    "da", "de", "ta", "te",
    "ya", "ye",  # "a" ve "e" çıkarıldı
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

    # Fuzzy matching - daha konservatif
    best_match = None
    best_distance = max_distance + 1

    for candidate in candidates:
        if len(candidate) < 4:
            continue

        for medicine in TURKISH_MEDICINE_DICTIONARY.keys():
            if len(medicine) < 4:
                continue

            distance = levenshtein_distance(candidate, medicine)

            # Daha sıkı kurallar:
            # 1. Kısa kelimeler (<=5): max 1 mesafe
            # 2. Orta kelimeler (6-7): max 1 mesafe (daha konservatif)
            # 3. Uzun kelimeler (>=8): max 2 mesafe
            min_len = min(len(medicine), len(candidate))
            if min_len <= 5:
                adjusted_max = 1
            elif min_len <= 7:
                adjusted_max = 1  # Önerin/aferin gibi durumları önle
            else:
                adjusted_max = max_distance

            # Ek kontrol: İlk 2 karakter eşleşmeli (typo genelde ortada/sonda olur)
            if distance > 0 and candidate[:2] != medicine[:2]:
                continue

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


# ============================================================
# MASK-BASED MEDICINE HANDLING (TR name preservation)
# ============================================================

def mask_medicines(
    text: str,
    start_counter: int = 0,
    existing_mask_map: Optional[dict] = None
) -> Tuple[str, dict, int]:
    """
    Metindeki ilaç isimlerini mask'ler ve mask_map döndürür.

    Bu fonksiyon, çeviri sırasında Türkçe ilaç isimlerini korumak için kullanılır.
    İlaç isimleri MEDTOK0X, MEDTOK1X gibi placeholder'larla değiştirilir.

    Token format: MEDTOK{n}X
    - Sabit 'X' suffix'i substring collision'ı önler (MEDTOK1X ≠ MEDTOK10X)
    - Alphanumeric format çeviri sırasında bozulmaz

    Args:
        text: Orijinal Türkçe metin
        start_counter: Mask sayacının başlangıç değeri (history collision önleme)
        existing_mask_map: Mevcut mask_map ile birleştirmek için (opsiyonel)

    Returns:
        tuple: (masked_text, mask_map, next_counter)
            - masked_text: İlaç isimleri mask'lenmiş metin
            - mask_map: {"MEDTOK0X": {"tr": "Parol", "en": "acetaminophen"}, ...}
            - next_counter: Bir sonraki çağrı için kullanılacak counter değeri
    """
    text_lower = text.lower()
    words = re.findall(r'\b[\wğüşıöçĞÜŞİÖÇ]+\b', text_lower, re.UNICODE)
    original_words = re.findall(r'\b[\wğüşıöçĞÜŞİÖÇ]+\b', text, re.UNICODE)
    result = text

    mask_map = dict(existing_mask_map) if existing_mask_map else {}
    replacements = []  # (original_text, mask_key, tr_name, en_name)
    matched_positions = set()
    mask_counter = start_counter

    # Multi-word ilaç isimleri (aferin forte, tylol hot)
    for n in [3, 2]:
        ngrams = generate_ngrams(words, n)
        original_ngrams = generate_ngrams(original_words, n)

        for i, (ngram, orig_ngram) in enumerate(zip(ngrams, original_ngrams)):
            positions = set(range(i, i + n))
            if positions & matched_positions:
                continue

            if ngram in TURKISH_MEDICINE_DICTIONARY:
                if is_medicine_context(ngram, text):
                    # Token format: MEDTOK{n}X - sabit suffix ile substring collision önleme
                    # MEDTOK1X artık MEDTOK10X içinde geçmez
                    mask_key = f"MEDTOK{mask_counter}X"
                    # tr_name: kullanıcının yazdığı formu koru (title() Türkçe'de sorunlu)
                    tr_name = orig_ngram  # Kullanıcının yazdığı hali
                    en_name = TURKISH_MEDICINE_DICTIONARY[ngram]
                    replacements.append((orig_ngram, mask_key, tr_name, en_name))
                    matched_positions.update(positions)
                    mask_counter += 1
                    print(f"[MASK-NGRAM] '{orig_ngram}' → {mask_key} ({tr_name} / {en_name[:30]}...)")

    # Tek kelime ilaç isimleri
    for i, (word, orig_word) in enumerate(zip(words, original_words)):
        if i in matched_positions:
            continue
        if len(word) < 3:
            continue

        medicine_name, english_name = find_medicine_match(word)

        if medicine_name and english_name:
            if not is_medicine_context(medicine_name, text):
                print(f"[MASK-CONTEXT] '{orig_word}' → ilaç DEĞİL, atlandı")
                continue

            # Token format: MEDTOK{n}X - sabit suffix ile substring collision önleme
            mask_key = f"MEDTOK{mask_counter}X"
            # tr_name: kullanıcının yazdığı formu koru (title() Türkçe'de sorunlu)
            tr_name = orig_word  # Kullanıcının yazdığı hali
            replacements.append((orig_word, mask_key, tr_name, english_name))
            matched_positions.add(i)
            mask_counter += 1
            print(f"[MASK] '{orig_word}' → {mask_key} ({tr_name} / {english_name[:30]}...)")

    # Uzun orijinal metinleri önce değiştir (overlap önleme)
    replacements.sort(key=lambda x: len(x[0]), reverse=True)

    for orig_text, mask_key, tr_name, en_name in replacements:
        pattern = r'\b' + re.escape(orig_text) + r'\b'
        result = re.sub(pattern, mask_key, result, flags=re.IGNORECASE)
        mask_map[mask_key] = {"tr": tr_name, "en": en_name}

    return result, mask_map, mask_counter


def unmask_medicines(text: str, mask_map: dict, format_style: str = "tr_with_en") -> str:
    """
    Mask'lenmiş metindeki placeholder'ları ilaç isimleriyle değiştirir.

    Args:
        text: Mask'lenmiş metin (MEDTOK0X, MEDTOK1X içeren)
        mask_map: mask_medicines()'den dönen map
        format_style: Çıktı formatı
            - "tr_with_en": "Parol (acetaminophen)" - varsayılan
            - "tr_only": "Parol"
            - "en_only": "acetaminophen"

    Returns:
        str: İlaç isimleri açılmış metin
    """
    result = text

    # Uzun token'ları önce aç (MEDTOK10X önce, MEDTOK1X sonra)
    # Bu substring collision'ı önler
    sorted_keys = sorted(mask_map.keys(), key=len, reverse=True)

    for mask_key in sorted_keys:
        names = mask_map[mask_key]
        tr_name = names["tr"]
        en_name = names["en"]

        if format_style == "tr_with_en":
            # En yaygın İngilizce jenerik adı al
            # "paracetamol (Turkish brand: Parol)" → "paracetamol"
            en_short = en_name.split("(")[0].strip()  # Parantez öncesi
            en_short = en_short.split(",")[0].strip()  # Virgül öncesi
            en_short = en_short.split("/")[0].strip()  # Slash öncesi
            replacement = f"{tr_name} ({en_short})"
        elif format_style == "tr_only":
            replacement = tr_name
        elif format_style == "en_only":
            replacement = en_name
        else:
            replacement = f"{tr_name} ({en_name.split(',')[0].strip()})"

        # Regex ile word boundary kullan (translator case değiştirirse de yakala)
        pattern = r'\b' + re.escape(mask_key) + r'\b'
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        print(f"[UNMASK] {mask_key} → '{replacement}'")

    return result


# ============================================================
# REVERSE EN→TR MAPPING (LLM-generated medicine names)
# ============================================================

def _inside_parentheses(text: str, idx: int) -> bool:
    """
    Verilen index'in parantez içinde olup olmadığını kontrol eder.

    Bu fonksiyon, nested parentheses sorununu önlemek için kullanılır.
    Örn: "paracetamol (acetaminophen)" → "paracetamol" dönüştürülürken
    "(acetaminophen)" içindeki "acetaminophen" atlanmalı.

    Args:
        text: Metin
        idx: Kontrol edilecek karakter index'i

    Returns:
        bool: True eğer index parantez içindeyse
    """
    # idx'e kadar olan kısımda son '(' ve ')' pozisyonlarını bul
    last_open = text.rfind("(", 0, idx)
    last_close = text.rfind(")", 0, idx)

    # Eğer son '(' varsa ve ')' yoksa veya '(' sonra geliyorsa → parantez içindeyiz
    return last_open > last_close


# İngilizce jenerik isimler → Türkçe jenerik isimler
# NOT: Marka isimleri değil, jenerik isimler kullanılıyor
# NOT: Kontrollü maddeler (alprazolam, diazepam vb.) çıkarıldı
ENGLISH_TO_TURKISH_MEDICINES = {
    # Ağrı kesiciler / Antipiretikler
    "paracetamol": "Parasetamol",
    "acetaminophen": "Parasetamol",  # ABD'de paracetamol = acetaminophen
    "ibuprofen": "İbuprofen",
    "naproxen": "Naproksen",
    "aspirin": "Aspirin",
    "diclofenac": "Diklofenak",

    # Antibiyotikler
    "amoxicillin": "Amoksisilin",
    "azithromycin": "Azitromisin",
    "ciprofloxacin": "Siprofloksasin",
    "metronidazole": "Metronidazol",
    "penicillin": "Penisilin",
    "doxycycline": "Doksisiklin",

    # Mide/Sindirim
    "omeprazole": "Omeprazol",
    "pantoprazole": "Pantoprazol",
    "ranitidine": "Ranitidin",
    "metoclopramide": "Metoklopramid",

    # Alerji / Antihistaminikler
    "cetirizine": "Setirizin",
    "loratadine": "Loratadin",
    "desloratadine": "Desloratadin",
    "fexofenadine": "Feksofenadin",
    "diphenhydramine": "Difenhidramin",

    # Soğuk algınlığı
    "pseudoephedrine": "Psödoefedrin",
    "dextromethorphan": "Dekstrometorfan",
    "guaifenesin": "Guaifenesin",

    # Diyabet
    "metformin": "Metformin",
    "insulin": "İnsülin",

    # Kardiyovasküler
    "atorvastatin": "Atorvastatin",
    "lisinopril": "Lisinopril",
    "amlodipine": "Amlodipin",
    "losartan": "Losartan",

    # Vitaminler / Takviyeler
    "vitamin d": "D Vitamini",
    "vitamin c": "C Vitamini",
    "vitamin b12": "B12 Vitamini",
    "folic acid": "Folik Asit",
    "iron": "Demir",
    "calcium": "Kalsiyum",
    "magnesium": "Magnezyum",
}


def convert_english_medicines_to_turkish(text: str, format_style: str = "tr_with_en") -> str:
    """
    LLM yanıtındaki İngilizce ilaç isimlerini Türkçe'ye dönüştürür.

    Bu fonksiyon, mask_medicines ile yakalanmayan (LLM'in kendi eklediği)
    İngilizce ilaç isimlerini Türkçe karşılıklarına çevirir.

    NOT: Parantez içindeki ilaç isimleri atlanır (nested parentheses önleme).

    Args:
        text: LLM yanıtı (Türkçe'ye çevrilmiş)
        format_style: Çıktı formatı
            - "tr_with_en": "Parasetamol (paracetamol)" - varsayılan
            - "tr_only": "Parasetamol"

    Returns:
        str: İngilizce ilaç isimleri Türkçe'ye çevrilmiş metin
    """
    result = text

    # Uzun isimlerden başla (acetaminophen > aspirin)
    sorted_medicines = sorted(ENGLISH_TO_TURKISH_MEDICINES.keys(), key=len, reverse=True)

    for en_name in sorted_medicines:
        tr_name = ENGLISH_TO_TURKISH_MEDICINES[en_name]

        # Case-insensitive arama
        pattern = r'\b' + re.escape(en_name) + r'\b'

        # Tüm eşleşmeleri bul
        matches = list(re.finditer(pattern, result, flags=re.IGNORECASE))

        if not matches:
            continue

        # Sondan başa işle (index kayması önleme)
        for match in reversed(matches):
            # Parantez içindeyse atla (nested parentheses önleme)
            if _inside_parentheses(result, match.start()):
                print(f"[EN→TR-SKIP] '{en_name}' parantez içinde, atlandı")
                continue

            if format_style == "tr_with_en":
                replacement = f"{tr_name} ({en_name})"
            else:
                replacement = tr_name

            # Bu spesifik eşleşmeyi değiştir
            result = result[:match.start()] + replacement + result[match.end():]
            print(f"[EN→TR] '{en_name}' → '{replacement}'")

    return result
