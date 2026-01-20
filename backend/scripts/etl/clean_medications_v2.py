#!/usr/bin/env python3
"""
medications_openfda_clean.json temizleme scripti v2

Yapılan işlemler:
1. keywords_tr: Soru kalıplarını ("nedir", "ne işe yarar", vb.) çıkarır
2. typos_tr: 30'dan 10'a indirir (en faydalı varyasyonları tutar)
3. Gereksiz alanlar: source_urls, merged_count silinir
"""

import json
import random
from pathlib import Path

# Dosya yolları
INPUT_FILE = Path(__file__).parent.parent.parent / "data" / "medical_knowledge" / "medications_openfda_clean.json"
OUTPUT_FILE = INPUT_FILE  # Üzerine yaz
BACKUP_FILE = INPUT_FILE.with_suffix(".backup.json")

# Temizlenecek soru kalıpları (boşluklu ve bitişik versiyonlar)
SORU_KALIPLARI = [
    # Boşluklu versiyonlar
    " nedir",
    " ne işe yarar",
    " ne ise yarar",
    " ne ışe yarar",  # Türkçe noktalı i
    " kullanımı",
    " kullanimi",
    " yan etkileri",
    " yan etkıleri",
    " yan etcileri",
    " cullanımı",
    # Bitişik yazılmış versiyonlar (typos için)
    "nedir",
    "neişeyarar",
    "neiseyarar",
    "neışeyarar",  # Türkçe noktalı ı
    "kullanımı",
    "kullanimi",
    "yanetkileri",
    "yanetkıleri",
    "yanetcileri",
]

# Silinecek alanlar
SILINECEK_ALANLAR = ["source_urls", "merged_count"]

# typos_tr için maksimum sayı
MAX_TYPOS = 10


def contains_soru_kalibi(keyword: str) -> bool:
    """Keyword'ün soru kalıbı içerip içermediğini kontrol eder."""
    keyword_lower = keyword.lower()
    # Boşluksuz versiyonu da kontrol et (bitişik yazımlar için)
    keyword_no_space = keyword_lower.replace(" ", "")
    return any(kalip in keyword_lower or kalip in keyword_no_space for kalip in SORU_KALIPLARI)


def filter_keywords_tr(keywords: list) -> list:
    """Soru kalıplarını içeren keyword'leri filtreler."""
    return [kw for kw in keywords if not contains_soru_kalibi(kw)]


def prioritize_typos(typos: list, max_count: int = MAX_TYPOS) -> list:
    """
    typos_tr listesinden en faydalı olanları seçer.

    Öncelik:
    1. Boşluksuz/bitişik yazımlar (fluticasonepropionate)
    2. Karakter değişiklikleri (ph->f, c->k, s->z)
    3. Türkçe karakter hataları (ı->i, ş->s)
    """
    if len(typos) <= max_count:
        return typos

    # Öncelik skorları
    scored_typos = []
    for typo in typos:
        score = 0
        typo_lower = typo.lower()

        # Bitişik yazımlar yüksek öncelik
        if " " not in typo and "/" not in typo:
            score += 3

        # Yaygın Türkçe typo kalıpları
        if any(x in typo_lower for x in ["ph", "ks", "cks"]):  # ph->f tipi
            score += 2
        if any(x in typo for x in ["ı", "ş", "ğ", "ü", "ö", "ç"]):  # TR karakter varyasyonları
            score += 2

        # Soru kalıpları içerenlere düşük öncelik
        if contains_soru_kalibi(typo):
            score -= 5

        scored_typos.append((typo, score))

    # Skora göre sırala ve en yüksek skorluları al
    scored_typos.sort(key=lambda x: x[1], reverse=True)

    # İlk max_count tanesini al, soru kalıbı içerenleri hariç tut
    result = []
    for typo, score in scored_typos:
        if not contains_soru_kalibi(typo):
            result.append(typo)
        if len(result) >= max_count:
            break

    return result


def clean_record(record: dict) -> dict:
    """Tek bir kaydı temizler."""
    cleaned = record.copy()

    # 1. keywords_tr temizle
    if "keywords_tr" in cleaned:
        cleaned["keywords_tr"] = filter_keywords_tr(cleaned["keywords_tr"])

    # 2. typos_tr'yi azalt
    if "typos_tr" in cleaned:
        cleaned["typos_tr"] = prioritize_typos(cleaned["typos_tr"], MAX_TYPOS)

    # 3. Gereksiz alanları sil
    for alan in SILINECEK_ALANLAR:
        cleaned.pop(alan, None)

    return cleaned


def main():
    print(f"Dosya okunuyor: {INPUT_FILE}")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Toplam kayıt: {len(data)}")

    # İstatistikler - öncesi
    before_keywords = sum(len(r.get("keywords_tr", [])) for r in data)
    before_typos = sum(len(r.get("typos_tr", [])) for r in data)

    # Temizle
    cleaned_data = [clean_record(record) for record in data]

    # İstatistikler - sonrası
    after_keywords = sum(len(r.get("keywords_tr", [])) for r in cleaned_data)
    after_typos = sum(len(r.get("typos_tr", [])) for r in cleaned_data)

    # Yedek al
    print(f"Yedek alınıyor: {BACKUP_FILE}")
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Kaydet
    print(f"Temizlenmiş dosya kaydediliyor: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    # Özet
    print("\n" + "="*50)
    print("TEMİZLEME TAMAMLANDI")
    print("="*50)
    print(f"keywords_tr: {before_keywords} -> {after_keywords} (-%{100*(before_keywords-after_keywords)/before_keywords:.0f})")
    print(f"typos_tr: {before_typos} -> {after_typos} (-%{100*(before_typos-after_typos)/before_typos:.0f})")
    print(f"Silinen alanlar: {SILINECEK_ALANLAR}")
    print(f"\nYedek: {BACKUP_FILE}")


if __name__ == "__main__":
    main()
