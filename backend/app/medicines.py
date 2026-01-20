"""
Türkçe İlaç Sözlüğü
Tek kaynak - hem health_filter hem main.py tarafından kullanılır

v2.0 - Ocak 2026
- Canonical generic isimler (kısa, temiz)
- Yüksek riskli ilaç seti (kontrollü maddeler)
- Eksik kritik ilaçlar eklendi
- Normalizasyon ve eşleştirme yardımcı fonksiyonları
"""

import re
import unicodedata
from typing import Optional, Tuple, Set

# =============================================================================
# ANA SÖZLÜK: Türkçe marka → Canonical generic isim
# =============================================================================
# NOT: Value'lar SADECE generic isim olmalı (kısa, temiz).
# Marka bilgisi, açıklama vs. ayrı bir sözlükte tutulabilir.

TURKISH_MEDICINE_DICTIONARY = {
    # =========================================================================
    # AĞRI KESİCİLER / ATEŞ DÜŞÜRÜCÜLER
    # =========================================================================

    # Parasetamol bazlı
    "parol": "paracetamol",
    "tylol": "paracetamol",
    "minoset": "paracetamol",
    "vermidon": "paracetamol",
    "calpol": "paracetamol",
    "parasedamol": "paracetamol",
    "parasetamol": "paracetamol",
    "panadol": "paracetamol",

    # Parasetamol kombinasyonları
    "aferin": "paracetamol-caffeine",
    "aferin forte": "paracetamol-caffeine",
    "gripin": "paracetamol-phenylephrine-chlorpheniramine",
    "tylol hot": "paracetamol-combination",
    "theraflu": "paracetamol-combination",
    "fervex": "paracetamol-combination",
    "coldrex": "paracetamol-combination",
    "deflu": "paracetamol-pseudoephedrine",

    # NSAIDs - İbuprofen
    "nurofen": "ibuprofen",
    "pedifen": "ibuprofen",
    "brufen": "ibuprofen",
    "dolven": "ibuprofen",  # EKLENDI - çocuk şurubu yaygın

    # NSAIDs - Naproksen
    "apranax": "naproxen",
    "naprosyn": "naproxen",
    "opraks": "naproxen",

    # NSAIDs - Diklofenak
    "voltaren": "diclofenac",
    "dikloron": "diclofenac",
    "diclomec": "diclofenac",
    "cataflam": "diclofenac",  # EKLENDI - diclofenac potassium

    # NSAIDs - Diğer
    "majezik": "flurbiprofen",
    "arveles": "dexketoprofen",
    "dexofen": "dexketoprofen",

    # Metamizol (TR'de çok yaygın)
    "novalgin": "metamizole",  # EKLENDI - kritik
    "novaljin": "metamizole",  # Typo varyasyonu

    # Aspirin
    "aspirin": "aspirin",
    "disprin": "aspirin",
    "ecopirin": "aspirin",
    "coraspin": "aspirin",  # Düşük doz
    "kardegic": "aspirin",  # Düşük doz

    # =========================================================================
    # ANTİBİYOTİKLER
    # =========================================================================

    # Penisilin grubu
    "augmentin": "amoxicillin-clavulanate",
    "amoklavin": "amoxicillin-clavulanate",
    "klamoks": "amoxicillin-clavulanate",
    "amoksisilin": "amoxicillin",
    "duocid": "ampicillin-sulbactam",

    # Florokinolon grubu
    "cipro": "ciprofloxacin",
    "ciproxin": "ciprofloxacin",
    "siprofloksasin": "ciprofloxacin",

    # Makrolid grubu
    "klacid": "clarithromycin",
    "macrol": "clarithromycin",
    "azitromisin": "azithromycin",
    "zitromax": "azithromycin",
    "azro": "azithromycin",

    # Sefalosporin grubu
    "iesef": "cefixime",
    "cefaks": "cefuroxime",
    "cefixime": "cefixime",
    "sefuroksim": "cefuroxime",
    "suprax": "cefixime",

    # =========================================================================
    # MİDE İLAÇLARI
    # =========================================================================

    # PPI (Proton Pompa İnhibitörleri)
    "nexium": "esomeprazole",
    "lansor": "lansoprazole",
    "controloc": "pantoprazole",
    "pantpas": "pantoprazole",
    "losec": "omeprazole",

    # Antasitler
    "gaviscon": "alginate-antacid",
    "rennie": "calcium-carbonate-antacid",
    "talcid": "hydrotalcite",
    "maalox": "aluminum-magnesium-antacid",

    # Antiemetik / Prokinetik
    "motilium": "domperidone",
    "metpamid": "metoclopramide",

    # =========================================================================
    # SPAZMOLİTİKLER / IBS
    # =========================================================================
    "buscopan": "hyoscine",
    "spazmol": "hyoscine",
    "duspatalin": "mebeverine",  # EKLENDI - IBS için çok yaygın
    "meteospasmyl": "alverine-simethicone",  # EKLENDI

    # =========================================================================
    # ALERJİ İLAÇLARI (Antihistaminikler)
    # =========================================================================
    "zyrtec": "cetirizine",
    "cetrin": "cetirizine",
    "allerset": "cetirizine",
    "setrizin": "cetirizine",
    "histazin": "cetirizine",
    "aerius": "desloratadine",
    "desloratadin": "desloratadine",
    "xyzal": "levocetirizine",
    "loratadin": "loratadine",
    "telfast": "fexofenadine",  # EKLENDI - çok yaygın
    "avil": "pheniramine",

    # =========================================================================
    # BURUN / ÖKSÜRÜK İLAÇLARI
    # =========================================================================

    # Burun sprayleri
    "otrivin": "xylometazoline",
    "iliadin": "oxymetazoline",

    # Öksürük / Mukolitik
    "prospan": "ivy-leaf-extract",
    "mucosolvan": "ambroxol",
    "bromeks": "bromhexine",
    "tusso": "dextromethorphan",
    "sudafed": "pseudoephedrine",
    "sinecod": "butamirate",

    # =========================================================================
    # KAS GEVŞETİCİLER
    # =========================================================================
    "muscoril": "thiocolchicoside",
    "myoril": "thiocolchicoside",
    "sirdalud": "tizanidine",
    "tizanidin": "tizanidine",

    # =========================================================================
    # TİROİD İLAÇLARI (kritik, çok yaygın)
    # =========================================================================
    "euthyrox": "levothyroxine",  # EKLENDI - kritik
    "levotiron": "levothyroxine",  # EKLENDI - kritik
    "tefor": "levothyroxine",  # EKLENDI

    # =========================================================================
    # ASTIM / KOAH İLAÇLARI
    # =========================================================================
    "ventolin": "salbutamol",
    "seretide": "fluticasone-salmeterol",
    "symbicort": "budesonide-formoterol",
    "singulair": "montelukast",  # EKLENDI - çok yaygın
    "flixotide": "fluticasone",  # EKLENDI
    "pulmicort": "budesonide",  # EKLENDI

    # =========================================================================
    # TANSİYON İLAÇLARI
    # =========================================================================
    "beloc": "metoprolol",
    "concor": "bisoprolol",
    "norvasc": "amlodipine",
    "amlodipin": "amlodipine",

    # =========================================================================
    # KOLESTEROL İLAÇLARI
    # =========================================================================
    "lipitor": "atorvastatin",
    "crestor": "rosuvastatin",
    "atorvastatin": "atorvastatin",

    # =========================================================================
    # DİYABET İLAÇLARI (son yıllarda çok soruluyor)
    # =========================================================================
    "metformin": "metformin",
    "glucophage": "metformin",
    "diamicron": "gliclazide",

    # GLP-1 agonistleri / SGLT2 inhibitörleri (EKLENDI - çok popüler)
    "ozempic": "semaglutide",  # EKLENDI - çok soruluyor
    "wegovy": "semaglutide",  # EKLENDI - obezite
    "jardiance": "empagliflozin",  # EKLENDI
    "forxiga": "dapagliflozin",  # EKLENDI
    "januvia": "sitagliptin",  # EKLENDI
    "lantus": "insulin-glargine",  # EKLENDI

    # =========================================================================
    # KAN SULANDIRICILAR
    # =========================================================================
    "coumadin": "warfarin",
    "plavix": "clopidogrel",

    # Modern DOAC'lar (EKLENDI - çok kritik)
    "eliquis": "apixaban",  # EKLENDI
    "xarelto": "rivaroxaban",  # EKLENDI
    "pradaxa": "dabigatran",  # EKLENDI

    # =========================================================================
    # PSİKİYATRİK İLAÇLAR
    # =========================================================================
    # NOT: Kontrollü maddeler HIGH_RISK_DRUGS setinde de işaretli

    # Antidepresanlar (SSRI/SNRI)
    "lexapro": "escitalopram",
    "cipralex": "escitalopram",
    "prozac": "fluoxetine",
    "lustral": "sertraline",

    # Anksiyolitikler (KONTROLLÜ)
    "xanax": "alprazolam",

    # =========================================================================
    # CİLT KREMLERİ
    # =========================================================================
    "fucidin": "fusidic-acid",
    "bactroban": "mupirocin",
    "triderm": "betamethasone-clotrimazole",
    "advantan": "methylprednisolone",
    "bepanthen": "dexpanthenol",

    # =========================================================================
    # VİTAMİNLER (düşük öncelik ama yaygın soru)
    # =========================================================================
    "supradyn": "multivitamin",
    "centrum": "multivitamin",
    "pharmaton": "multivitamin-ginseng",
    "berocca": "b-vitamins",
    "elevit": "prenatal-vitamins",
    "bemiks": "b-complex",
    "benexol": "b-vitamins",
}


# =============================================================================
# YÜKSEK RİSKLİ İLAÇLAR (Kontrollü maddeler, bağımlılık potansiyeli)
# =============================================================================
# Bu ilaçlar tanındığında bot:
# - Doz/kullanım talimatı vermemeli
# - Doktor/eczacı yönlendirmesi yapmalı
# - Bağımlılık/risk uyarısı göstermeli

HIGH_RISK_DRUGS: Set[str] = {
    # Benzodiazepinler
    "alprazolam",
    "diazepam",
    "lorazepam",
    "clonazepam",

    # Opioidler
    "tramadol",
    "codeine",
    "morphine",
    "fentanyl",
    "oxycodone",

    # Z-ilaçları (uyku)
    "zolpidem",
    "zopiclone",

    # Diğer kontrollü
    "methylphenidate",  # Ritalin
    "pregabalin",  # Lyrica - kontrollü madde
    "gabapentin",  # Bazı ülkelerde kontrollü
}

# Yüksek riskli marka isimleri (hızlı lookup için)
HIGH_RISK_BRANDS: Set[str] = {
    "xanax", "rivotril", "diazem", "ativan",  # Benzodiazepinler
    "tramal", "contramal", "tramadol",  # Tramadol
    "ritalin", "concerta",  # ADHD
    "lyrica", "pregabalin",  # Pregabalin
    "imovane", "stilnox",  # Z-ilaçları
}


# =============================================================================
# YAZIM HATALARI SÖZLÜĞÜ
# =============================================================================
# Yaygın yanlış yazımlar → doğru marka ismi
# NOT: Cyrillic ve garip karakterler temizlendi

MEDICINE_TYPOS = {
    # Parol varyasyonları
    "paroll": "parol",
    "parool": "parol",
    "paral": "parol",
    "parole": "parol",
    "porol": "parol",
    "prol": "parol",

    # Aferin varyasyonları
    "afeirin": "aferin",
    "afferin": "aferin",
    "afren": "aferin",
    "aferin": "aferin",
    "afirin": "aferin",
    "eferin": "aferin",
    "aferrin": "aferin",

    # Tylol varyasyonları
    "tilol": "tylol",
    "tyloll": "tylol",
    "taylol": "tylol",
    "tiloll": "tylol",

    # Apranax varyasyonları
    "apranaks": "apranax",
    "apranaksi": "apranax",
    "apranx": "apranax",
    "apranak": "apranax",
    "aprenax": "apranax",
    "apranex": "apranax",

    # Nurofen varyasyonları
    "norofen": "nurofen",
    "nurafen": "nurofen",
    "nuroffen": "nurofen",
    "neurofen": "nurofen",

    # Majezik varyasyonları
    "macezik": "majezik",
    "majezic": "majezik",
    "mecezik": "majezik",

    # Augmentin varyasyonları
    "ogmentin": "augmentin",
    "agmentin": "augmentin",
    "augmantin": "augmentin",
    "augmanten": "augmentin",
    "ogmanten": "augmentin",

    # Gripin varyasyonları
    "giripin": "gripin",
    "gribin": "gripin",

    # Arveles varyasyonları
    "arvales": "arveles",
    "arvelez": "arveles",
    "arweles": "arveles",

    # Voltaren varyasyonları
    "woltaren": "voltaren",
    "voltaran": "voltaren",
    "valtaren": "voltaren",

    # Aspirin varyasyonları
    "asprin": "aspirin",

    # Novalgin varyasyonları (EKLENDI)
    "novaljin": "novalgin",
    "novalcin": "novalgin",
    "novalgın": "novalgin",

    # Euthyrox varyasyonları (EKLENDI)
    "euthrox": "euthyrox",
    "euthirox": "euthyrox",
    "eutirox": "euthyrox",

    # Ozempic varyasyonları (EKLENDI)
    "ozempik": "ozempic",
    "ozempıc": "ozempic",

    # Xarelto varyasyonları (EKLENDI)
    "ksarelto": "xarelto",
    "zarelto": "xarelto",
}


# =============================================================================
# İLAÇ MARKA İSİMLERİ SETİ (hızlı lookup için)
# =============================================================================
MEDICINE_BRANDS: Set[str] = set(TURKISH_MEDICINE_DICTIONARY.keys())


# =============================================================================
# NORMALİZASYON VE EŞLEŞTİRME FONKSİYONLARI
# =============================================================================

def normalize_text(text: str) -> str:
    """
    Metin normalizasyonu - eşleştirmeden önce kullanılmalı

    - Unicode NFKC normalizasyonu (Cyrillic → Latin vb.)
    - Küçük harfe çevirme (casefold)
    - Türkçe karakterleri koruma
    - Noktalama temizliği
    """
    if not text:
        return ""

    # Unicode normalizasyonu (NFKC - en agresif)
    text = unicodedata.normalize("NFKC", text)

    # Casefold (lowercase'den daha agresif, uluslararası karakterler için)
    text = text.casefold()

    # Türkçe özel karakterleri koru ama normalize et
    # ı → i dönüşümü casefold ile olmuyor, manuel yapabiliriz
    # Ama bu ilaç isimlerinde genelde sorun değil

    # Sadece alfanumerik ve boşluk kalsın
    text = re.sub(r'[^\w\s-]', '', text)

    # Çoklu boşlukları tekile indir
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def find_medicine_in_text(text: str) -> list[Tuple[str, str, int, int]]:
    """
    Metinde ilaç isimlerini bul (longest-first matching)

    Returns:
        List of (brand_name, generic_name, start_pos, end_pos)
    """
    if not text:
        return []

    normalized = normalize_text(text)
    found = []

    # 1. Önce typo'ları düzelt
    for typo, correct in MEDICINE_TYPOS.items():
        typo_norm = normalize_text(typo)
        if typo_norm in normalized:
            # Kelime sınırı kontrolü ile değiştir
            pattern = r'\b' + re.escape(typo_norm) + r'\b'
            normalized = re.sub(pattern, normalize_text(correct), normalized)

    # 2. Sözlüğü uzunluğa göre sırala (longest-first)
    sorted_brands = sorted(TURKISH_MEDICINE_DICTIONARY.keys(),
                          key=lambda x: len(x), reverse=True)

    # 3. Her markayı ara (kelime sınırı ile)
    used_positions = set()  # Overlap önleme

    for brand in sorted_brands:
        brand_norm = normalize_text(brand)
        if not brand_norm:
            continue

        # Kelime sınırı ile ara
        pattern = r'\b' + re.escape(brand_norm) + r'\b'

        for match in re.finditer(pattern, normalized):
            start, end = match.start(), match.end()

            # Bu pozisyon daha önce kullanıldı mı?
            if any(start < used_end and end > used_start
                   for used_start, used_end in used_positions):
                continue

            generic = TURKISH_MEDICINE_DICTIONARY[brand]
            found.append((brand, generic, start, end))
            used_positions.add((start, end))

    # Pozisyona göre sırala
    found.sort(key=lambda x: x[2])

    return found


def get_generic_name(brand: str) -> Optional[str]:
    """
    Marka isminden generic isim al (normalizasyonlu)
    """
    if not brand:
        return None

    normalized = normalize_text(brand)

    # Önce typo kontrolü
    if normalized in {normalize_text(t) for t in MEDICINE_TYPOS}:
        for typo, correct in MEDICINE_TYPOS.items():
            if normalize_text(typo) == normalized:
                normalized = normalize_text(correct)
                break

    # Sözlükte ara
    for brand_key, generic in TURKISH_MEDICINE_DICTIONARY.items():
        if normalize_text(brand_key) == normalized:
            return generic

    return None


def is_high_risk_drug(name: str) -> bool:
    """
    İlaç yüksek riskli mi kontrol et (marka veya generic)
    """
    if not name:
        return False

    normalized = normalize_text(name)

    # Marka kontrolü
    if normalized in {normalize_text(b) for b in HIGH_RISK_BRANDS}:
        return True

    # Generic kontrolü
    generic = get_generic_name(name)
    if generic and generic in HIGH_RISK_DRUGS:
        return True

    # Direkt generic isim mi?
    if normalized in {normalize_text(g) for g in HIGH_RISK_DRUGS}:
        return True

    return False


def replace_medicines_in_text(text: str) -> str:
    """
    Metindeki tüm ilaç marka isimlerini generic isimlerle değiştir
    (LLM'e göndermeden önce kullanılabilir)
    """
    if not text:
        return text

    result = text
    found = find_medicine_in_text(text)

    # Sondan başa doğru değiştir (pozisyon kayması önleme)
    for brand, generic, start, end in reversed(found):
        # Orijinal metinde karşılık gelen kısmı bul
        # (case-insensitive replacement)
        pattern = re.compile(re.escape(brand), re.IGNORECASE)
        result = pattern.sub(generic, result, count=1)

    return result


# =============================================================================
# MARKA BİLGİLERİ (UI için - isteğe bağlı)
# =============================================================================
# Eğer UI'da marka bilgisi göstermek isterseniz bu sözlüğü kullanın

BRAND_INFO = {
    "parol": {"tr_name": "Parol", "company": "Atabay", "form": "tablet/şurup"},
    "nurofen": {"tr_name": "Nurofen", "company": "Reckitt", "form": "tablet/şurup"},
    "majezik": {"tr_name": "Majezik", "company": "Sanofi", "form": "tablet"},
    "arveles": {"tr_name": "Arveles", "company": "Deva", "form": "tablet/ampul"},
    # ... diğerleri gerektiğinde eklenebilir
}
