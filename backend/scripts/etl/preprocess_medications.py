"""
OpenFDA Medications Preprocessing Pipeline v2
Max kalite + hız için:
- Gürültü filtresi (WATER, sterile diluent, vb.)
- Kalite filtresi (2+ sinyal)
- Normalizasyon (metin temizliği)
- Table satırları temizleme
- Dedup/Grouping (aynı generic name birleştirme)
- Brand/synonym/typo genişletme
- Doz guardrail'i
- 3-doküman formatı: overview, safety, how_to_use
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from dataclasses import dataclass, field

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "medical_knowledge"
INPUT_FILE = DATA_DIR / "medications_openfda.json"
OUTPUT_FILE = DATA_DIR / "medications_openfda_clean.json"
OUTPUT_CHUNKS_FILE = DATA_DIR / "medications_openfda_chunks.json"

# Chunk size hedefi
MIN_CHUNK_CHARS = 300
TARGET_CHUNK_CHARS = 1000  # 900-1400 arası hedef
MAX_CHUNK_CHARS = 1400


@dataclass
class QualityMetrics:
    """Kalite metrikleri"""
    total_input: int = 0
    filtered_noise: int = 0
    filtered_low_quality: int = 0
    filtered_placeholder: int = 0
    merged_duplicates: int = 0
    final_docs: int = 0
    final_chunks: int = 0


# ============================================
# 0) GÜRÜLTÜ FİLTRESİ
# ============================================

# Gürültü kayıtları tespit için pattern'ler
NOISE_TITLE_PATTERNS = [
    r'^WATER$',
    r'^STERILE\s+WATER',
    r'^SODIUM\s+CHLORIDE$',
    r'^SALINE$',
    r'^DEXTROSE$',
    r'^GLUCOSE$',
    r'^BACTERIOSTATIC\s+WATER',
    r'^DILUENT',
    r'^STERILE\s+DILUENT',
    r'^PLACEBO',
]

NOISE_KEYWORDS = {
    'sterile diluent',
    'diluent for',
    'sterile water for injection',
    'bacteriostatic water',
    'normal saline',
    'placebo',
}


def is_noise_record(med: Dict) -> bool:
    """Gürültü kaydı mı kontrol et (WATER, diluent, vb.)"""
    title = med.get('title', '').upper().strip()

    # Title pattern kontrolü
    for pattern in NOISE_TITLE_PATTERNS:
        if re.match(pattern, title, re.IGNORECASE):
            return True

    # Keywords kontrolü
    keywords = med.get('keywords_en', []) + med.get('keywords_tr', [])
    for kw in keywords:
        kw_lower = kw.lower()
        for noise in NOISE_KEYWORDS:
            if noise in kw_lower:
                return True

    # Content kontrolü - çok genel içerik
    content = med.get('content', '').lower()
    if 'sterile diluent' in content or 'diluent for' in content:
        return True

    # Drug class yoksa ve title çok genel
    if not med.get('drug_class') and len(title) <= 10:
        # Çok basit isim + drug class yok = muhtemelen gürültü
        simple_names = {'WATER', 'SALINE', 'DEXTROSE', 'GLUCOSE', 'SODIUM', 'POTASSIUM'}
        if title in simple_names:
            return True

    return False


def filter_noise(data: List[Dict]) -> Tuple[List[Dict], int]:
    """Gürültü kayıtlarını filtrele"""
    filtered = []
    noise_count = 0

    for med in data:
        if is_noise_record(med):
            noise_count += 1
            continue
        filtered.append(med)

    return filtered, noise_count


# ============================================
# 1) KALİTE FİLTRESİ
# ============================================

def count_quality_signals(med: Dict) -> int:
    """Bir kayıttaki kalite sinyallerini say"""
    score = 0

    # uses kontrolü
    if med.get('uses') and len(med['uses']) > 0:
        score += 1

    # warnings kontrolü
    if med.get('warnings') and len(med['warnings']) > 0:
        score += 1

    # contraindications kontrolü (placeholder değilse)
    contras = med.get('contraindications', [])
    if contras and not all('none' in str(c).lower() for c in contras):
        score += 1

    # drug_interactions kontrolü
    if med.get('drug_interactions') and len(med['drug_interactions']) > 0:
        score += 1

    # dosage_info kontrolü
    if med.get('dosage_info') and med['dosage_info'].get('note'):
        score += 1

    # side_effects kontrolü
    if med.get('side_effects') and len(med['side_effects']) > 0:
        score += 1

    return score


def is_placeholder_content(med: Dict) -> bool:
    """Placeholder/çöp içerik mi kontrol et"""
    content = med.get('content', '')
    title = med.get('title', '')

    # Çok kısa ve anlamsız
    if len(content) < 30:
        return True

    # Sadece "X is a medication" tarzı
    if re.match(r'^[\w\s]+ is a medication\.?$', content, re.IGNORECASE):
        return True

    # Title çok kısa veya garip
    if len(title) < 3:
        return True

    return False


def quality_filter(data: List[Dict], min_signals: int = 2) -> Tuple[List[Dict], int, int]:
    """Kalite filtresini uygula"""
    low_quality_count = 0
    placeholder_count = 0
    filtered = []

    for med in data:
        signals = count_quality_signals(med)

        if signals < min_signals:
            low_quality_count += 1
            continue

        if is_placeholder_content(med):
            placeholder_count += 1
            continue

        filtered.append(med)

    return filtered, low_quality_count, placeholder_count


# ============================================
# 2) NORMALİZASYON + TABLE TEMİZLİĞİ
# ============================================

def clean_text(text: str) -> str:
    """Metin temizliği"""
    if not text:
        return ""

    # HTML/escape temizliği
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)

    # Çoklu boşluk temizliği
    text = re.sub(r'\s+', ' ', text)

    # Başta/sondaki boşluklar
    text = text.strip()

    return text


def clean_table_lines(text: str) -> str:
    """Table içeren uzun satırları temizle veya özetle"""
    if not text:
        return ""

    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        line = line.strip()

        # Table satırı tespiti
        if re.match(r'^Table\s+\d+', line, re.IGNORECASE):
            # Table referansını koru ama uzun içeriği kırp
            if len(line) > 100:
                # Sadece table başlığını al
                match = re.match(r'^(Table\s+\d+[:\s]*[^:]+)', line, re.IGNORECASE)
                if match:
                    line = match.group(1) + " (detaylar için tam etikete bakın)"
                else:
                    line = line[:100] + "..."
            cleaned_lines.append(line)

        # Çok uzun tek satır (genelde tablo verisi)
        elif len(line) > 200 and ('|' in line or '\t' in line or line.count(' ') > 20):
            # Bu muhtemelen bir tablo satırı, özetle
            cleaned_lines.append(line[:150] + "...")

        else:
            cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def clean_list_items(items: List[str], max_items: int = 10, max_item_length: int = 250) -> List[str]:
    """Liste öğelerini temizle"""
    if not items:
        return []

    cleaned = []
    seen = set()

    for item in items[:max_items * 2]:  # Fazladan al, temizledikten sonra kırp
        item = clean_text(item)
        item = clean_table_lines(item)

        # Çok kısa veya boş
        if len(item) < 10:
            continue

        # Çok uzun olanları kırp
        if len(item) > max_item_length:
            item = item[:max_item_length] + "..."

        # Duplicate kontrolü (normalize edilmiş)
        item_normalized = item.lower().strip()[:50]  # İlk 50 karakter ile kontrol
        if item_normalized in seen:
            continue
        seen.add(item_normalized)

        cleaned.append(item)

        if len(cleaned) >= max_items:
            break

    return cleaned


def normalize_medication(med: Dict) -> Dict:
    """Tek bir ilaç kaydını normalize et"""
    normalized = med.copy()

    # Title temizliği
    normalized['title'] = clean_text(med.get('title', '')).upper()
    normalized['title_tr'] = normalized['title']  # İlaç isimleri genelde aynı

    # Content temizliği
    content = clean_text(med.get('content', ''))
    content = clean_table_lines(content)
    normalized['content'] = content

    # Liste alanları temizliği - farklı limitlerle
    normalized['uses'] = clean_list_items(med.get('uses', []), max_items=6, max_item_length=200)
    normalized['warnings'] = clean_list_items(med.get('warnings', []), max_items=8, max_item_length=250)
    normalized['contraindications'] = clean_list_items(med.get('contraindications', []), max_items=6, max_item_length=200)
    normalized['drug_interactions'] = clean_list_items(med.get('drug_interactions', []), max_items=8, max_item_length=200)
    normalized['side_effects'] = clean_list_items(med.get('side_effects', []), max_items=10, max_item_length=150)

    # Dosage info temizliği
    if normalized.get('dosage_info'):
        note = normalized['dosage_info'].get('note', '')
        note = clean_text(note)
        note = clean_table_lines(note)
        if len(note) > 300:
            note = note[:300] + "..."
        normalized['dosage_info']['note'] = note

    # Overdose warning temizliği
    overdose = clean_text(med.get('overdose_warning', ''))
    if len(overdose) > 200:
        overdose = overdose[:200] + "..."
    normalized['overdose_warning'] = overdose

    return normalized


# ============================================
# 3) DEDUP / GROUPING
# ============================================

def extract_canonical_name(med: Dict) -> str:
    """İlaç için canonical (birleştirme) anahtarı üret"""
    title = med.get('title', '').upper().strip()

    # Özel karakterleri temizle
    title = re.sub(r'[^A-Z0-9\s]', '', title)

    # Çoklu boşlukları tek boşluğa
    title = re.sub(r'\s+', ' ', title).strip()

    # Bazı yaygın suffix'leri kaldır
    suffixes_to_remove = [
        r'\s+TABLETS?$',
        r'\s+CAPSULES?$',
        r'\s+INJECTION$',
        r'\s+SOLUTION$',
        r'\s+ORAL$',
        r'\s+EXTENDED RELEASE$',
        r'\s+ER$',
        r'\s+XR$',
        r'\s+SR$',
        r'\s+CR$',
        r'\s+HCL$',
        r'\s+HYDROCHLORIDE$',
        r'\s+\d+\s*MG$',
        r'\s+\d+\s*ML$',
    ]

    for suffix in suffixes_to_remove:
        title = re.sub(suffix, '', title, flags=re.IGNORECASE)

    return title.strip()


def merge_medications(meds: List[Dict]) -> Dict:
    """Aynı canonical name'e sahip ilaçları birleştir"""
    if len(meds) == 1:
        return meds[0]

    # En kaliteli kaydı ana kayıt olarak seç
    meds_sorted = sorted(meds, key=lambda m: count_quality_signals(m), reverse=True)
    master = meds_sorted[0].copy()

    # Liste alanlarını birleştir
    list_fields = ['uses', 'warnings', 'contraindications', 'drug_interactions', 'side_effects']

    for field_name in list_fields:
        all_items = set()
        for med in meds:
            for item in med.get(field_name, []):
                # Normalize edip ekle
                normalized = item.strip().lower()[:50]
                if len(normalized) > 10:  # Çok kısa olanları atla
                    all_items.add(item)

        master[field_name] = list(all_items)[:12]  # Max 12 madde

    # Keywords birleştir
    all_keywords_en = set()
    all_keywords_tr = set()
    all_typos_tr = set()

    for med in meds:
        all_keywords_en.update(med.get('keywords_en', []))
        all_keywords_tr.update(med.get('keywords_tr', []))
        all_typos_tr.update(med.get('typos_tr', []))

    master['keywords_en'] = list(all_keywords_en)
    master['keywords_tr'] = list(all_keywords_tr)
    master['typos_tr'] = list(all_typos_tr)

    # Source URLs birleştir
    source_urls = set()
    for med in meds:
        if med.get('source_url'):
            source_urls.add(med['source_url'])
    master['source_urls'] = list(source_urls)

    # Merge count
    master['merged_count'] = len(meds)

    return master


def deduplicate_medications(data: List[Dict]) -> Tuple[List[Dict], int]:
    """Aynı ilaçları birleştir"""
    # Canonical name'e göre grupla
    groups = defaultdict(list)

    for med in data:
        canonical = extract_canonical_name(med)
        groups[canonical].append(med)

    # Her grubu birleştir
    merged = []
    total_merged = 0

    for canonical, meds in groups.items():
        if len(meds) > 1:
            total_merged += len(meds) - 1

        merged_med = merge_medications(meds)
        merged.append(merged_med)

    return merged, total_merged


# ============================================
# 4) BRAND / SYNONYM / TYPO GENİŞLETME
# ============================================

# Türkiye'de bilinen bazı ilaç markaları (örnek - genişletilebilir)
TR_BRAND_MAP = {
    'ACETAMINOPHEN': ['PAROL', 'TYLOL', 'MINOSET', 'CALPOL', 'TAMOL'],
    'IBUPROFEN': ['ADVIL', 'DOLGIT', 'NUROFEN', 'BRUFEN'],
    'ASPIRIN': ['ASPIRIN', 'DISPRIL', 'CORASPIN'],
    'OMEPRAZOLE': ['LOSEC', 'OMEPROL', 'PRILOSEC'],
    'METFORMIN': ['GLUCOPHAGE', 'GLUKOFEN', 'DIAFORMIN'],
    'AMOXICILLIN': ['AMOKLAVIN', 'AUGMENTIN', 'KLAVUNAT'],
    'PARACETAMOL': ['PAROL', 'TYLOL', 'MINOSET', 'CALPOL'],
    'DICLOFENAC': ['VOLTAREN', 'DIKLORON', 'CATAFLAM'],
    'NAPROXEN': ['APRANAX', 'NAPROSYN', 'ALEVE'],
    'PANTOPRAZOLE': ['PANTPAS', 'PROTONIX', 'PANTOZOL'],
    'ATORVASTATIN': ['LIPITOR', 'ATOR'],
    'METOPROLOL': ['BELOC', 'LOPRESSOR'],
    'AMLODIPINE': ['NORVASC', 'AMLODIPIN'],
    'LISINOPRIL': ['ZESTRIL', 'PRINIVIL'],
    'GABAPENTIN': ['NEURONTIN', 'GABATEVA'],
}

# Türkçe karakter dönüşümleri
TR_CHAR_MAP = {
    'ğ': 'g', 'ü': 'u', 'ş': 's', 'ı': 'i', 'ö': 'o', 'ç': 'c',
    'Ğ': 'G', 'Ü': 'U', 'Ş': 'S', 'İ': 'I', 'Ö': 'O', 'Ç': 'C'
}


def generate_typos(word: str) -> List[str]:
    """Yaygın yazım hatalarını üret"""
    typos = set()
    word_lower = word.lower()

    # Türkçe karakter düşürme
    no_tr = word_lower
    for tr_char, ascii_char in TR_CHAR_MAP.items():
        no_tr = no_tr.replace(tr_char, ascii_char)
    if no_tr != word_lower:
        typos.add(no_tr)

    # Bitişik yazma
    typos.add(word_lower.replace(' ', ''))

    # Yaygın değişimler
    replacements = [
        ('ph', 'f'), ('f', 'ph'),
        ('c', 'k'), ('k', 'c'),
        ('z', 's'), ('s', 'z'),
    ]
    for old, new in replacements:
        if old in word_lower:
            typos.add(word_lower.replace(old, new))

    return list(typos)


def expand_keywords(med: Dict) -> Dict:
    """Keyword/brand/typo alanlarını genişlet"""
    expanded = med.copy()
    title = med.get('title', '').upper()

    # Keywords EN genişlet
    keywords_en = set(med.get('keywords_en', []))
    keywords_en.add(title.lower())

    # Drug class ekle
    if med.get('drug_class'):
        keywords_en.add(med['drug_class'].lower())

    expanded['keywords_en'] = list(keywords_en)

    # Keywords TR genişlet
    keywords_tr = set(med.get('keywords_tr', []))
    keywords_tr.add(title.lower())

    # TR brand ekle
    for generic, brands in TR_BRAND_MAP.items():
        if generic in title:
            for brand in brands:
                keywords_tr.add(brand.lower())

    # Yaygın TR arama terimleri
    keywords_tr.add(f"{title.lower()} ne işe yarar")
    keywords_tr.add(f"{title.lower()} yan etkileri")
    keywords_tr.add(f"{title.lower()} kullanımı")
    keywords_tr.add(f"{title.lower()} nedir")

    expanded['keywords_tr'] = list(keywords_tr)

    # Typos genişlet
    typos_tr = set(med.get('typos_tr', []))
    for kw in keywords_tr:
        typos_tr.update(generate_typos(kw))

    expanded['typos_tr'] = list(typos_tr)[:30]  # Max 30

    # Brand examples TR
    brand_examples = []
    for generic, brands in TR_BRAND_MAP.items():
        if generic in title:
            brand_examples.extend(brands)
    expanded['brand_examples_tr'] = brand_examples

    return expanded


# ============================================
# 5) DOZ GUARDRAİL'İ
# ============================================

DOSAGE_DISCLAIMER = (
    "Doz bilgisi genel bilgilendirme amaçlıdır. "
    "Kişisel doz ayarlaması için mutlaka doktorunuza danışın."
)


def apply_dosage_guardrail(med: Dict) -> Dict:
    """Doz bilgisini güvenli hale getir"""
    guarded = med.copy()

    # Dosage info varsa, güvenli nota dönüştür
    if guarded.get('dosage_info') and guarded['dosage_info'].get('note'):
        original_note = guarded['dosage_info']['note']

        # Spesifik mg/kg gibi değerleri kaldır veya genelleştir
        safe_note = re.sub(
            r'\d+\s*(mg|ml|mcg|µg)/kg',
            'doz (doktora danışın)',
            original_note,
            flags=re.IGNORECASE
        )

        # Çok uzunsa kısalt
        if len(safe_note) > 250:
            safe_note = safe_note[:250] + "..."

        guarded['dosage_info'] = {
            'note': safe_note,
            'disclaimer': DOSAGE_DISCLAIMER
        }

    # Safety disclaimer ekle
    guarded['safety_disclaimer'] = (
        "Bu bilgiler ABD FDA verilerine dayanmaktadır ve yalnızca genel bilgilendirme amaçlıdır. "
        "Türkiye'deki kullanım koşulları farklılık gösterebilir. "
        "İlaç kullanmadan önce mutlaka doktorunuza veya eczacınıza danışın."
    )

    return guarded


# ============================================
# 6) 3-DOKÜMAN FORMATI (overview, safety, how_to_use)
# ============================================

def truncate_to_target(text: str, target: int = TARGET_CHUNK_CHARS, max_len: int = MAX_CHUNK_CHARS) -> str:
    """Metni hedef uzunluğa kırp"""
    if len(text) <= max_len:
        return text

    # Cümle sonunda bitirmeye çalış
    truncated = text[:max_len]
    last_period = truncated.rfind('.')
    last_newline = truncated.rfind('\n')

    cut_point = max(last_period, last_newline)
    if cut_point > target // 2:
        return truncated[:cut_point + 1]

    return truncated + "..."


def create_overview_chunk(med: Dict) -> Dict:
    """
    Overview chunk: title, drug_class, uses (4-6 madde), önemli limitler
    """
    parent_id = med.get('id', '')
    title = med.get('title', '')

    parts = []

    # Title ve drug class
    parts.append(f"# {title}")
    if med.get('drug_class'):
        parts.append(f"İlaç sınıfı: {med['drug_class']}")

    # Uses (max 6)
    uses = med.get('uses', [])[:6]
    if uses:
        parts.append("\n## Ne İşe Yarar")
        for use in uses:
            # Kısa tut
            use_short = use[:150] + "..." if len(use) > 150 else use
            parts.append(f"• {use_short}")

    # Content özeti (varsa ve uses yoksa)
    content = med.get('content', '')
    if content and not uses:
        content_short = content[:300] + "..." if len(content) > 300 else content
        parts.append(f"\n{content_short}")

    # Önemli limitler (varsa warnings'da "not indicated" veya "prn" geçiyorsa)
    warnings = med.get('warnings', [])
    limitations = []
    for w in warnings:
        w_lower = w.lower()
        if 'not indicated' in w_lower or 'not for' in w_lower or 'prn' in w_lower or 'limitation' in w_lower:
            limitations.append(w)

    if limitations:
        parts.append("\n## Önemli Uyarı")
        for lim in limitations[:2]:
            lim_short = lim[:120] + "..." if len(lim) > 120 else lim
            parts.append(f"⚠️ {lim_short}")

    full_content = '\n'.join(parts)
    full_content = truncate_to_target(full_content)

    return {
        'id': f"{parent_id}_overview",
        'parent_id': parent_id,
        'section': 'overview',
        'title': title,
        'title_tr': f"{title} - Genel Bilgi",
        'category': 'medications',
        'content': full_content,
        'keywords_en': med.get('keywords_en', []),
        'keywords_tr': med.get('keywords_tr', []) + ['nedir', 'ne işe yarar', 'kullanım alanları'],
        'typos_tr': med.get('typos_tr', []),
        'brand_examples_tr': med.get('brand_examples_tr', []),
        'source_name': med.get('source_name', ''),
        'source_url': med.get('source_url', ''),
        'drug_class': med.get('drug_class', ''),
    }


def create_safety_chunk(med: Dict) -> Optional[Dict]:
    """
    Safety chunk: warnings (boxed dahil), contraindications, overdose_warning
    """
    parent_id = med.get('id', '')
    title = med.get('title', '')

    parts = []
    has_content = False

    parts.append(f"# {title} - Güvenlik Bilgileri")

    # Warnings (max 8, boxed öncelikli)
    warnings = med.get('warnings', [])
    if warnings:
        has_content = True
        parts.append("\n## Uyarılar")

        # Boxed warning'ları öne al
        boxed = [w for w in warnings if 'boxed' in w.lower() or 'warning:' in w.lower()[:15]]
        other = [w for w in warnings if w not in boxed]

        sorted_warnings = boxed + other
        for w in sorted_warnings[:8]:
            w_short = w[:200] + "..." if len(w) > 200 else w
            prefix = "⚠️ " if w in boxed else "• "
            parts.append(f"{prefix}{w_short}")

    # Contraindications (max 6)
    contras = med.get('contraindications', [])
    # "None" placeholder'larını filtrele
    contras = [c for c in contras if 'none' not in c.lower()[:10]]
    if contras:
        has_content = True
        parts.append("\n## Kimler Kullanmamalı")
        for c in contras[:6]:
            c_short = c[:150] + "..." if len(c) > 150 else c
            parts.append(f"❌ {c_short}")

    # Overdose warning
    overdose = med.get('overdose_warning', '')
    if overdose:
        has_content = True
        parts.append("\n## Doz Aşımı")
        overdose_short = overdose[:180] + "..." if len(overdose) > 180 else overdose
        parts.append(f"🚨 {overdose_short}")

    if not has_content:
        return None

    full_content = '\n'.join(parts)
    full_content = truncate_to_target(full_content)

    return {
        'id': f"{parent_id}_safety",
        'parent_id': parent_id,
        'section': 'safety',
        'title': f"{title} - Güvenlik",
        'title_tr': f"{title} - Uyarılar ve Kontrendikasyonlar",
        'category': 'medications',
        'content': full_content,
        'keywords_en': med.get('keywords_en', []),
        'keywords_tr': med.get('keywords_tr', []) + ['uyarı', 'kontrendikasyon', 'kimler kullanamaz', 'yan etki'],
        'source_name': med.get('source_name', ''),
        'source_url': med.get('source_url', ''),
    }


def create_how_to_use_chunk(med: Dict) -> Optional[Dict]:
    """
    How-to-use chunk: dosage_info, drug_interactions, side_effects
    """
    parent_id = med.get('id', '')
    title = med.get('title', '')

    parts = []
    has_content = False

    parts.append(f"# {title} - Kullanım Bilgileri")

    # Dosage info
    dosage_info = med.get('dosage_info', {})
    if dosage_info and dosage_info.get('note'):
        has_content = True
        parts.append("\n## Dozaj")
        note = dosage_info['note']
        note_short = note[:200] + "..." if len(note) > 200 else note
        parts.append(note_short)
        if dosage_info.get('disclaimer'):
            parts.append(f"\n⚠️ {dosage_info['disclaimer']}")

    # Drug interactions (max 8)
    interactions = med.get('drug_interactions', [])
    if interactions:
        has_content = True
        parts.append("\n## İlaç Etkileşimleri")
        for inter in interactions[:8]:
            inter_short = inter[:150] + "..." if len(inter) > 150 else inter
            parts.append(f"• {inter_short}")

    # Side effects (max 10)
    side_effects = med.get('side_effects', [])
    if side_effects:
        has_content = True
        parts.append("\n## Yan Etkiler")
        for se in side_effects[:10]:
            se_short = se[:120] + "..." if len(se) > 120 else se
            parts.append(f"• {se_short}")

    if not has_content:
        return None

    full_content = '\n'.join(parts)
    full_content = truncate_to_target(full_content)

    # Guardrail flag - doz bilgisi varsa
    has_guardrail = bool(dosage_info and dosage_info.get('note'))

    return {
        'id': f"{parent_id}_how_to_use",
        'parent_id': parent_id,
        'section': 'how_to_use',
        'title': f"{title} - Kullanım",
        'title_tr': f"{title} - Nasıl Kullanılır",
        'category': 'medications',
        'content': full_content,
        'keywords_en': med.get('keywords_en', []),
        'keywords_tr': med.get('keywords_tr', []) + ['nasıl kullanılır', 'doz', 'yan etki', 'etkileşim'],
        'source_name': med.get('source_name', ''),
        'source_url': med.get('source_url', ''),
        'has_guardrail': has_guardrail,
    }


def create_chunks(med: Dict) -> List[Dict]:
    """İlaç kaydını 3-doküman formatında chunk'lara ayır"""
    chunks = []

    # 1. Overview (her zaman oluştur)
    overview = create_overview_chunk(med)
    chunks.append(overview)

    # 2. Safety (içerik varsa)
    safety = create_safety_chunk(med)
    if safety:
        chunks.append(safety)

    # 3. How to use (içerik varsa)
    how_to_use = create_how_to_use_chunk(med)
    if how_to_use:
        chunks.append(how_to_use)

    return chunks


# ============================================
# ANA PIPELINE
# ============================================

def run_preprocessing_pipeline(input_path: Path = INPUT_FILE,
                                output_path: Path = OUTPUT_FILE,
                                chunks_path: Path = OUTPUT_CHUNKS_FILE) -> QualityMetrics:
    """Tam preprocessing pipeline'ını çalıştır"""

    print("=" * 60)
    print("OpenFDA Medications Preprocessing Pipeline v2")
    print("(3-doküman formatı: overview, safety, how_to_use)")
    print("=" * 60)

    # 1. Veri yükle
    print("\n[1/7] Veri yükleniyor...")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    metrics = QualityMetrics(total_input=len(data))
    print(f"  → {len(data)} kayıt yüklendi")

    # 2. Gürültü filtresi
    print("\n[2/7] Gürültü filtresi uygulanıyor...")
    filtered_noise, noise_count = filter_noise(data)
    metrics.filtered_noise = noise_count
    print(f"  → {noise_count} gürültü kayıt elendi (WATER, diluent, vb.)")
    print(f"  → {len(filtered_noise)} kayıt kaldı")

    # 3. Kalite filtresi
    print("\n[3/7] Kalite filtresi uygulanıyor...")
    filtered, low_q, placeholder = quality_filter(filtered_noise, min_signals=2)
    metrics.filtered_low_quality = low_q
    metrics.filtered_placeholder = placeholder
    print(f"  → {low_q} düşük kaliteli kayıt elendi")
    print(f"  → {placeholder} placeholder kayıt elendi")
    print(f"  → {len(filtered)} kayıt kaldı")

    # 4. Normalizasyon
    print("\n[4/7] Normalizasyon yapılıyor...")
    normalized = [normalize_medication(med) for med in filtered]
    print(f"  → {len(normalized)} kayıt normalize edildi (table satırları temizlendi)")

    # 5. Deduplication
    print("\n[5/7] Deduplication yapılıyor...")
    deduplicated, merged_count = deduplicate_medications(normalized)
    metrics.merged_duplicates = merged_count
    print(f"  → {merged_count} duplicate kayıt birleştirildi")
    print(f"  → {len(deduplicated)} benzersiz ilaç kaldı")

    # 6. Keyword/Brand/Typo genişletme
    print("\n[6/7] Keyword/Brand/Typo genişletiliyor...")
    expanded = [expand_keywords(med) for med in deduplicated]
    print(f"  → {len(expanded)} kayıt genişletildi")

    # 7. Dosage guardrail
    print("\n[7/7] Dosage guardrail uygulanıyor...")
    guarded = [apply_dosage_guardrail(med) for med in expanded]
    metrics.final_docs = len(guarded)
    print(f"  → {len(guarded)} kayıt güvenli hale getirildi")

    # Kaydet (master docs)
    print(f"\n→ Master docs kaydediliyor: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(guarded, f, ensure_ascii=False, indent=2)

    # Chunking (3-doküman formatı)
    print("\n[BONUS] 3-doküman formatında chunking yapılıyor...")
    all_chunks = []
    for med in guarded:
        chunks = create_chunks(med)
        all_chunks.extend(chunks)
    metrics.final_chunks = len(all_chunks)

    # Chunk istatistikleri
    chunk_lengths = [len(c['content']) for c in all_chunks]
    avg_len = sum(chunk_lengths) / len(chunk_lengths) if chunk_lengths else 0
    min_len = min(chunk_lengths) if chunk_lengths else 0
    max_len = max(chunk_lengths) if chunk_lengths else 0

    print(f"  → {len(all_chunks)} chunk oluşturuldu")
    print(f"  → Chunk uzunluğu: min={min_len}, avg={avg_len:.0f}, max={max_len}")

    # Section dağılımı
    section_counts = defaultdict(int)
    for c in all_chunks:
        section_counts[c.get('section', 'unknown')] += 1
    print(f"  → Section dağılımı: {dict(section_counts)}")

    # Kaydet (chunks)
    print(f"\n→ Chunks kaydediliyor: {chunks_path}")
    with open(chunks_path, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    # Özet
    print("\n" + "=" * 60)
    print("ÖZET")
    print("=" * 60)
    print(f"Girdi kayıt sayısı:      {metrics.total_input}")
    print(f"Gürültü elenen:          {metrics.filtered_noise}")
    print(f"Düşük kalite elenen:     {metrics.filtered_low_quality}")
    print(f"Placeholder elenen:      {metrics.filtered_placeholder}")
    print(f"Birleştirilen duplicate: {metrics.merged_duplicates}")
    print(f"Final master doc:        {metrics.final_docs}")
    print(f"Final chunk sayısı:      {metrics.final_chunks}")
    print(f"Avg chunk/doc:           {metrics.final_chunks / metrics.final_docs:.1f}")
    print("=" * 60)

    return metrics


if __name__ == "__main__":
    metrics = run_preprocessing_pipeline()
