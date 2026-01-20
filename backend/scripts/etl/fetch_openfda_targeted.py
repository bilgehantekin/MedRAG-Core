#!/usr/bin/env python3
"""
OpenFDA Targeted ETL Script
============================

TURKISH_MEDICINE_DICTIONARY'deki canonical isimlere göre
hedefli OpenFDA verisi çeker.

Özellikler:
- Sadece sözlükteki etken maddeler için veri çeker
- Temiz, kısa ve RAG-optimize edilmiş JSON çıktısı
- Gereksiz alanları kırpar, gürültüyü temizler
- Match olmayan isimleri loglar

Kullanım:
    python fetch_openfda_targeted.py [--dry-run] [--verbose]
"""

import json
import re
import hashlib
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from urllib.parse import quote
import urllib.request
import urllib.error
import ssl

# =============================================================================
# KONFIGÜRASYON
# =============================================================================

# Dosya yolları
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent.parent / "data" / "medical_knowledge"
OUTPUT_FILE = DATA_DIR / "medications_openfda_only_tr.json"
LOG_FILE = SCRIPT_DIR / "openfda_fetch.log"

# OpenFDA API
OPENFDA_BASE_URL = "https://api.fda.gov/drug/label.json"
API_RATE_LIMIT_DELAY = 0.3  # saniye (rate limit: 240/dakika)

# Temizlik limitleri
# NOT: Truncation kapalı - full veri çekiliyor, chunking knowledge_base.py'de yapılıyor
MAX_TYPOS = 10

# Gürültü filtreleri - bunlar atlanacak
NOISE_TERMS = {
    "water", "sterile water", "diluent", "placebo",
    "sodium chloride", "dextrose", "lactose",
    "for injection", "for infusion",
}

# Kombinasyon mapping (bazı canonical isimler OpenFDA'da farklı)
CANONICAL_MAPPING = {
    # Kombinasyonlar için arama terimleri
    "paracetamol": ["acetaminophen", "paracetamol"],
    "paracetamol-caffeine": ["acetaminophen caffeine", "paracetamol caffeine"],
    "paracetamol-combination": ["acetaminophen"],
    "paracetamol-phenylephrine-chlorpheniramine": ["acetaminophen phenylephrine chlorpheniramine"],
    "paracetamol-pseudoephedrine": ["acetaminophen pseudoephedrine"],
    "amoxicillin-clavulanate": ["amoxicillin clavulanate", "amoxicillin and clavulanate"],
    "ampicillin-sulbactam": ["ampicillin sulbactam", "ampicillin and sulbactam"],
    "fluticasone-salmeterol": ["fluticasone salmeterol", "fluticasone and salmeterol"],
    "budesonide-formoterol": ["budesonide formoterol", "budesonide and formoterol"],
    "betamethasone-clotrimazole": ["betamethasone clotrimazole"],
    "alverine-simethicone": ["alverine simethicone"],
    "alginate-antacid": ["sodium alginate"],
    "calcium-carbonate-antacid": ["calcium carbonate"],
    "aluminum-magnesium-antacid": ["aluminum hydroxide magnesium"],
    "fusidic-acid": ["fusidic acid"],
    "ivy-leaf-extract": ["ivy leaf", "hedera helix"],
    "insulin-glargine": ["insulin glargine"],
    "b-vitamins": ["vitamin b", "thiamine riboflavin"],
    "b-complex": ["vitamin b complex", "b complex"],
    "multivitamin": ["multivitamin"],
    "multivitamin-ginseng": ["multivitamin ginseng", "ginseng"],
    "prenatal-vitamins": ["prenatal vitamin", "prenatal"],
}

# =============================================================================
# LOGGER AYARLARI
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# SÖZLÜK IMPORT
# =============================================================================

def get_canonical_names() -> dict:
    """
    TURKISH_MEDICINE_DICTIONARY'den canonical isimleri ve marka eşleşmelerini çıkarır.

    Returns:
        dict: {canonical_name: [brand1, brand2, ...]}
    """
    import sys
    sys.path.insert(0, str(SCRIPT_DIR.parent.parent / "app"))
    from medicines import TURKISH_MEDICINE_DICTIONARY

    # Canonical -> brands mapping
    canonical_to_brands = {}
    for brand, canonical in TURKISH_MEDICINE_DICTIONARY.items():
        if canonical not in canonical_to_brands:
            canonical_to_brands[canonical] = []
        canonical_to_brands[canonical].append(brand)

    return canonical_to_brands

# =============================================================================
# OPENFDA API
# =============================================================================

def fetch_openfda(query: str, limit: int = 5) -> Optional[dict]:
    """
    OpenFDA API'den veri çeker.

    Args:
        query: Arama sorgusu
        limit: Maksimum sonuç sayısı

    Returns:
        API yanıtı (JSON) veya None
    """
    # URL encode
    encoded_query = quote(query, safe=':()"')
    url = f"{OPENFDA_BASE_URL}?search={encoded_query}&limit={limit}"

    # SSL context (macOS için)
    ctx = ssl.create_default_context()

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'MedicalChatbot/1.0'})
        with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # Sonuç yok
        logger.warning(f"HTTP Error {e.code} for query: {query[:50]}...")
        return None
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return None


def search_canonical(canonical: str) -> Optional[dict]:
    """
    Canonical isim için OpenFDA'da arama yapar.

    Önce generic_name, sonra substance_name, gerekirse brand_name'de arar.
    """
    # Mapping varsa kullan
    search_terms = CANONICAL_MAPPING.get(canonical, [canonical])

    # Tire/dash'leri boşluğa çevir
    if canonical not in CANONICAL_MAPPING:
        search_terms = [canonical.replace("-", " ")]

    for term in search_terms:
        # 1. generic_name ile ara
        query = f'openfda.generic_name:"{term}"'
        result = fetch_openfda(query, limit=3)
        if result and result.get("results"):
            return result

        time.sleep(API_RATE_LIMIT_DELAY)

        # 2. substance_name ile ara
        query = f'openfda.substance_name:"{term}"'
        result = fetch_openfda(query, limit=3)
        if result and result.get("results"):
            return result

        time.sleep(API_RATE_LIMIT_DELAY)

        # 3. Genel arama (indications_and_usage + active_ingredient)
        query = f'"{term}"'
        result = fetch_openfda(query, limit=2)
        if result and result.get("results"):
            return result

        time.sleep(API_RATE_LIMIT_DELAY)

    return None

# =============================================================================
# TEMİZLİK FONKSİYONLARI
# =============================================================================

def clean_text(text: str) -> str:
    """
    Metni temizler (truncation yok - full veri).
    """
    if not text:
        return ""

    # None, N/A gibi placeholder'ları temizle
    if text.lower() in ["none", "n/a", "not applicable", "not available", ""]:
        return ""

    # Tablo satırlarını kaldır
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        # Tablo göstergelerini atla
        if any(x in line.lower() for x in ["table ", "figure ", "| ", " | "]):
            continue
        # Çok kısa satırları atla
        if len(line.strip()) < 5:
            continue
        clean_lines.append(line.strip())

    text = " ".join(clean_lines)

    # Çoklu boşlukları temizle
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def clean_list(items: list) -> list:
    """
    Liste öğelerini temizler ve dedupe eder (truncation yok - full veri).
    """
    if not items:
        return []

    seen_hashes = set()
    cleaned = []

    for item in items:
        if not item or not isinstance(item, str):
            continue

        # Temizle
        item = clean_text(item)
        if not item:
            continue

        # Placeholder kontrolü
        if item.lower() in ["none", "n/a", "not applicable"]:
            continue

        # Tablo kontrolü
        if "table" in item.lower()[:20]:
            continue

        # Dedupe (ilk 50 karakter hash)
        item_hash = hashlib.md5(item[:50].lower().encode()).hexdigest()
        if item_hash in seen_hashes:
            continue
        seen_hashes.add(item_hash)

        cleaned.append(item)

    return cleaned


def is_noise_record(record: dict) -> bool:
    """
    Gürültü kaydı mı kontrol eder (WATER, DILUENT vb.).
    """
    # Title kontrolü
    title = record.get("title", "").lower()
    if any(noise in title for noise in NOISE_TERMS):
        return True

    # openfda boş mu?
    openfda = record.get("openfda", {})
    if not openfda:
        # İçerik de çok generic mi?
        content = record.get("content", "").lower()
        if len(content) < 100 or "diluent" in content or "vehicle" in content:
            return True

    return False

# =============================================================================
# KAYIT DÖNÜŞTÜRME
# =============================================================================

def transform_record(
    raw_result: dict,
    canonical: str,
    brands: list
) -> Optional[dict]:
    """
    OpenFDA ham kaydını temiz formata dönüştürür.
    """
    openfda = raw_result.get("openfda", {})

    # Title
    generic_names = openfda.get("generic_name", [])
    brand_names = openfda.get("brand_name", [])
    title = generic_names[0] if generic_names else (brand_names[0] if brand_names else canonical)
    title = title.upper()

    # Drug class
    drug_class = ""
    pharm_classes = openfda.get("pharm_class_epc", [])
    if pharm_classes:
        drug_class = pharm_classes[0]

    # Content (indications) - full, no truncation
    content = ""
    indications = raw_result.get("indications_and_usage", [])
    if indications:
        content = clean_text(indications[0])

    # Gürültü kontrolü
    temp_record = {"title": title, "content": content, "openfda": openfda}
    if is_noise_record(temp_record):
        return None

    # Warnings - full, no truncation
    warnings = []
    if raw_result.get("boxed_warning"):
        warnings.extend(raw_result["boxed_warning"])
    if raw_result.get("warnings"):
        warnings.extend(raw_result["warnings"])
    if raw_result.get("warnings_and_cautions"):
        warnings.extend(raw_result["warnings_and_cautions"])
    warnings = clean_list(warnings)

    # Contraindications - full
    contraindications = clean_list(raw_result.get("contraindications", []))

    # Drug interactions - full
    interactions = clean_list(raw_result.get("drug_interactions", []))

    # Side effects - full
    side_effects = clean_list(raw_result.get("adverse_reactions", []))

    # Dosage - full
    dosage_info = {}
    dosage = raw_result.get("dosage_and_administration", [])
    if dosage:
        dosage_info = {
            "note": clean_text(dosage[0]),
            "disclaimer": "Doz bilgisi genel bilgilendirme amaçlıdır. Kişisel doz ayarlaması için mutlaka doktorunuza danışın."
        }

    # Overdose - full
    overdose = ""
    if raw_result.get("overdosage"):
        overdose = clean_text(raw_result["overdosage"][0])

    # Keywords
    keywords_en = [canonical]
    if generic_names:
        keywords_en.extend([g.lower() for g in generic_names[:2]])
    keywords_en = list(set(keywords_en))[:5]

    # TR keywords (marka isimleri)
    keywords_tr = [canonical]
    keywords_tr.extend(brands[:5])
    keywords_tr = list(set(keywords_tr))

    # Typos (basit varyasyonlar)
    typos_tr = generate_typos(canonical, brands)

    # ID
    slug = re.sub(r'[^a-z0-9]+', '_', canonical.lower())
    record_id = f"{slug}_001"

    return {
        "id": record_id,
        "title": title,
        "title_tr": title,
        "canonical_name": canonical,
        "category": "medications",
        "drug_class": drug_class,
        "source_name": "openFDA (Drug Label)",
        "source_url": "https://open.fda.gov/apis/drug/label/",
        "retrieved_date": datetime.now().strftime("%Y-%m-%d"),
        "content": content,
        "warnings": warnings,
        "contraindications": contraindications,
        "drug_interactions": interactions,
        "side_effects": side_effects,
        "dosage_info": dosage_info,
        "overdose_warning": overdose,
        "keywords_en": keywords_en,
        "keywords_tr": keywords_tr,
        "typos_tr": typos_tr,
        "brand_examples_tr": [b.upper() for b in brands[:3]],
        "safety_disclaimer": "Bu bilgiler ABD FDA verilerine dayanmaktadır ve yalnızca genel bilgilendirme amaçlıdır. Türkiye'deki kullanım koşulları farklılık gösterebilir. İlaç kullanmadan önce mutlaka doktorunuza veya eczacınıza danışın.",
        "jurisdiction": "TR",
        "safety_level": "medication",
        "source_jurisdiction": "US"
    }


def generate_typos(canonical: str, brands: list) -> list:
    """
    Basit typo varyasyonları oluşturur.
    """
    typos = set()

    # Canonical varyasyonları
    base = canonical.replace("-", "")
    typos.add(base)  # Bitişik

    # ph/f, c/k, s/z değişimleri
    variants = [
        (canonical.replace("ph", "f"), canonical.replace("f", "ph")),
        (canonical.replace("c", "k"), canonical.replace("k", "c")),
        (canonical.replace("s", "z"), canonical.replace("z", "s")),
    ]
    for v1, v2 in variants:
        if v1 != canonical:
            typos.add(v1)
        if v2 != canonical:
            typos.add(v2)

    # Brand varyasyonları
    for brand in brands[:3]:
        typos.add(brand.replace(" ", ""))  # Bitişik
        # Yaygın typo'lar
        if "x" in brand:
            typos.add(brand.replace("x", "ks"))
        if "c" in brand:
            typos.add(brand.replace("c", "k"))

    # Limitle
    return list(typos)[:MAX_TYPOS]

# =============================================================================
# ANA ETL FONKSİYONU
# =============================================================================

def run_etl(dry_run: bool = False, verbose: bool = False) -> dict:
    """
    Ana ETL fonksiyonu.

    Returns:
        İstatistikler dict'i
    """
    logger.info("=" * 60)
    logger.info("OpenFDA Targeted ETL Started")
    logger.info("=" * 60)

    # Canonical isimleri al
    canonical_to_brands = get_canonical_names()
    total_canonicals = len(canonical_to_brands)
    logger.info(f"Toplam canonical isim: {total_canonicals}")

    # Sonuçlar
    records = []
    matched = []
    not_matched = []
    skipped_noise = []

    for i, (canonical, brands) in enumerate(sorted(canonical_to_brands.items()), 1):
        logger.info(f"[{i}/{total_canonicals}] Araniyor: {canonical}")

        if dry_run:
            logger.info(f"  (dry-run) Brands: {brands}")
            continue

        # OpenFDA'da ara
        result = search_canonical(canonical)

        if not result or not result.get("results"):
            not_matched.append(canonical)
            logger.warning(f"  ✗ Bulunamadı: {canonical}")
            continue

        # İlk sonucu al ve dönüştür
        raw = result["results"][0]
        record = transform_record(raw, canonical, brands)

        if record is None:
            skipped_noise.append(canonical)
            logger.info(f"  ⊘ Gürültü olarak atlandı: {canonical}")
            continue

        records.append(record)
        matched.append(canonical)

        if verbose:
            logger.info(f"  ✓ Eşleşti: {record['title']}")
        else:
            logger.info(f"  ✓ Eşleşti")

    # Kaydet
    if not dry_run and records:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        logger.info(f"\nKaydedildi: {OUTPUT_FILE}")

    # İstatistikler
    stats = {
        "total_canonicals": total_canonicals,
        "matched": len(matched),
        "not_matched": len(not_matched),
        "skipped_noise": len(skipped_noise),
        "output_records": len(records),
        "not_matched_list": not_matched,
        "skipped_noise_list": skipped_noise,
    }

    # Özet log
    logger.info("\n" + "=" * 60)
    logger.info("ETL TAMAMLANDI")
    logger.info("=" * 60)
    logger.info(f"Toplam canonical: {total_canonicals}")
    logger.info(f"Eşleşen: {len(matched)} ({100*len(matched)/total_canonicals:.1f}%)")
    logger.info(f"Bulunamayan: {len(not_matched)}")
    logger.info(f"Gürültü olarak atlanan: {len(skipped_noise)}")
    logger.info(f"Çıktı kayıt sayısı: {len(records)}")

    if not_matched:
        logger.info("\nBulunamayan canonical isimler:")
        for name in sorted(not_matched):
            logger.info(f"  - {name}")

    if skipped_noise:
        logger.info("\nGürültü olarak atlanan:")
        for name in sorted(skipped_noise):
            logger.info(f"  - {name}")

    return stats

# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="OpenFDA'dan TURKISH_MEDICINE_DICTIONARY için hedefli veri çeker"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="API çağrısı yapmadan sadece canonical isimleri listele"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Detaylı çıktı"
    )

    args = parser.parse_args()

    stats = run_etl(dry_run=args.dry_run, verbose=args.verbose)

    # JSON olarak da kaydet (istatistikler)
    stats_file = SCRIPT_DIR / "openfda_fetch_stats.json"
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"\nİstatistikler: {stats_file}")


if __name__ == "__main__":
    main()
