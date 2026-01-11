"""
Medical Chatbot - FastAPI Backend
Sağlık odaklı chatbot API'si - Groq + Translation Pipeline
TR → EN → LLM → EN → TR
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import os
from pathlib import Path
from dotenv import load_dotenv

# .env dosyasını backend dizininden yükle
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from groq import Groq
from deep_translator import GoogleTranslator

from app.health_filter import is_health_related, check_emergency_symptoms, is_non_health_topic, is_greeting, get_greeting_type, count_health_signals, count_non_health_signals
from app.prompts import get_system_prompt, format_response_prompt, get_greeting_response
from app.medicines import TURKISH_MEDICINE_DICTIONARY, MEDICINE_TYPOS, MEDICINE_BRANDS

# Groq API ayarları
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

if not GROQ_API_KEY:
    print("⚠️  UYARI: GROQ_API_KEY ayarlanmamış! .env dosyasına ekleyin.")

groq_client = Groq(api_key=GROQ_API_KEY)

# Translator'lar
tr_to_en = GoogleTranslator(source='tr', target='en')
en_to_tr = GoogleTranslator(source='en', target='tr')

app = FastAPI(
    title="Medical Chatbot API",
    description="Sağlık odaklı bilgilendirme chatbot'u - Groq + Translation",
    version="2.0.0"
)

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    role: str  # "user" veya "assistant"
    content: str
    content_en: Optional[str] = None  # İngilizce versiyon (drift önleme için)


class SymptomContext(BaseModel):
    """3D modelden gelen yapılandırılmış semptom bilgisi"""
    region: str  # örn: "left_shin"
    region_name_tr: str  # örn: "Sol Kaval Kemiği"
    region_name_en: str  # örn: "Left Shin (Tibia)"
    symptom: str  # örn: "pain"
    symptom_name_tr: str  # örn: "Ağrı"
    symptom_name_en: str  # örn: "Pain"
    severity_0_10: int
    onset: str  # örn: "2_3_days"
    trigger: Optional[str] = None  # örn: "after_running"
    red_flags: Optional[List[str]] = []


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Message]] = []
    detailed_response: Optional[bool] = False
    symptom_context: Optional[SymptomContext] = None  # 3D modelden gelen yapısal bilgi


class ChatResponse(BaseModel):
    response: str
    response_en: Optional[str] = None  # İngilizce versiyon (drift önleme için frontend'in saklaması için)
    is_emergency: bool = False
    disclaimer: str = "⚠️ Bu bilgiler eğitim amaçlıdır, tıbbi tavsiye değildir. Acil durumlarda 112'yi arayın."

# Çift anlamlı kelimeler - bağlam kontrolü gerektirenler
# NOT: TURKISH_MEDICINE_DICTIONARY ve MEDICINE_TYPOS artık medicines.py'den import ediliyor
# Bu kelimeler hem ilaç ismi hem de günlük dilde başka anlama gelebilir
AMBIGUOUS_MEDICINE_NAMES = {
    "aferin": {
        "non_medicine_contexts": [
            # Takdir ifadeleri - SADECE çok net takdir kalıpları
            # NOT: "aferin ya" gibi kısa kalıplar "aferin yan etkisi" ile çakışabilir
            # Bu yüzden kelime sınırı gerektiren kalıpları regex ile kontrol edeceğiz
            "aferin sana", "aferin size", "aferin ona", "aferin bana",
            "aferin çocuğum", "aferin kızım", "aferin oğlum",
            "aferin be",
            "bravo", "tebrik", "helal olsun",
        ],
        # Regex kalıpları - kelime sınırı gerektiren ifadeler
        # NOT: "aferin ya" sadece cümle sonunda takdir, aksi halde (aferin ya yan etkisi) ilaç olabilir
        "non_medicine_patterns": [
            r"\baferin\s+ya[!.?\s]*$",  # "aferin ya" sadece cümle sonunda
            r"\baferin\s+valla[!.?\s]*$",  # "aferin valla" sadece cümle sonunda
        ],
        "medicine_contexts": [
            # İlaç kullanım ifadeleri
            "alsam", "almalı", "alayım", "aldım", "alıyor", "almak", "alınır",
            "içsem", "içmeliyim", "içeyim", "içtim", "içiyor", "içmek", "içilir",
            "kullansam", "kullanmalı", "kullanayım", "kullandım", "kullanıyor", "kullanılır", "kullanmak",
            "mg", "tablet", "hap", "şurup", "doz", "günde", "saatte",
            "ağrı", "ateş", "baş", "kafa", "grip", "soğuk algınlığı",
            "reçete", "doktor", "eczane", "ilaç",
            "forte", "plus", "cold", "hot",
            # Soru kalıpları
            "neden", "niçin", "ne için", "ne zaman", "nasıl", "ne işe", "faydası",
            "etkisi", "yan etki", "yan etkisi", "zararlı", "faydalı", "işe yarar",
        ],
    },
    # Gelecekte eklenebilecek diğer çift anlamlı kelimeler
    # "parola" kelimesi zaten sözlükte yok, sadece "parol" var
}

def is_medicine_context(word: str, full_text: str) -> bool:
    """
    Kelimenin ilaç bağlamında mı yoksa günlük dilde mi kullanıldığını kontrol eder.
    
    Args:
        word: Kontrol edilecek kelime (örn: "aferin")
        full_text: Tam cümle/metin
        
    Returns:
        bool: İlaç bağlamındaysa True, değilse False
    """
    import re
    
    word_lower = word.lower()
    text_lower = full_text.lower()
    
    # Bu kelime çift anlamlı değilse, direkt ilaç olarak kabul et
    if word_lower not in AMBIGUOUS_MEDICINE_NAMES:
        return True
    
    context_info = AMBIGUOUS_MEDICINE_NAMES[word_lower]
    
    # Önce ilaç DIŞI bağlam kontrolü (daha spesifik)
    for non_med_phrase in context_info["non_medicine_contexts"]:
        if non_med_phrase in text_lower:
            return False
    
    # Regex pattern'ler ile non-medicine kontrolü (kelime sınırı için)
    if "non_medicine_patterns" in context_info:
        for pattern in context_info["non_medicine_patterns"]:
            if re.search(pattern, text_lower):
                return False
    
    # Sonra ilaç bağlamı kontrolü
    for med_keyword in context_info["medicine_contexts"]:
        if med_keyword in text_lower:
            return True
    
    # "Aferin!" tek başına veya cümle sonunda ünlem olarak kullanılıyorsa
    # muhtemelen takdir ifadesi
    # "aferin!" veya "aferin." veya sadece "aferin" (tek kelime)
    if re.match(r'^aferin[!.\s]*$', text_lower.strip()):
        return False
    
    # "aferin sana" gibi hemen ardından zamir geliyorsa takdir
    if re.search(r'\baferin\s+(sana|size|ona|bana|bize|onlara)\b', text_lower):
        return False
    
    # Belirsiz durumda - eğer cümle çok kısa VE ilaç ipucu yoksa takdir
    words_in_text = len(text_lower.split())
    
    # Kısa cümleler için ek kontrol - sağlık anahtar kelimeleri var mı?
    health_hints = ["ağrı", "agri", "ateş", "ates", "hasta", "ilaç", "ilac", 
                    "doktor", "eczane", "baş", "bas", "grip", "nezle"]
    has_health_hint = any(hint in text_lower for hint in health_hints)
    
    if words_in_text <= 3 and not has_health_hint:
        return False  # Kısa cümle ve sağlık ipucu yok = muhtemelen takdir
    
    # Varsayılan olarak ilaç kabul et (sağlık chatbot'u olduğu için)
    return True


# Türkçe hal ekleri - ilaç isimlerinden temizlenecek
TURKISH_SUFFIXES = [
    # Uzun ekler önce (greedy matching için)
    "lerden", "lardan", "lerde", "larda", "lerin", "ların", "lere", "lara",
    "lerle", "larla", "leri", "ları", "ler", "lar",
    # İyelik + hal ekleri
    "ından", "inden", "undan", "ünden", "ında", "inde", "unda", "ünde",
    "ının", "inin", "unun", "ünün", "ına", "ine", "una", "üne",
    "ıyla", "iyle", "uyla", "üyle", "ını", "ini", "unu", "ünü",
    # Hal ekleri
    "dan", "den", "tan", "ten",
    "da", "de", "ta", "te",
    "a", "e", "ya", "ye",
    "ı", "i", "u", "ü",
    # İyelik ekleri
    "ım", "im", "um", "üm",
    "ın", "in", "un", "ün",
    "sı", "si", "su", "sü",
    # Soru eki
    "mı", "mi", "mu", "mü",
]


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
            # Ekleme, silme veya değiştirme maliyeti
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def generate_suffix_candidates(word: str) -> list:
    """
    Kelime için kademeli ek kırpma adayları üretir.
    Sadece sözlükte/typo'da eşleşen adayları kabul eder.
    
    Args:
        word: Orijinal kelime
        
    Returns:
        list: [orijinal, 1_ek_kırpılmış, 2_ek_kırpılmış, ...]
    """
    word_lower = word.lower()
    candidates = [word_lower]
    
    # Kademeli olarak ekleri kırp
    current = word_lower
    for _ in range(3):  # Maksimum 3 kırpma denemesi
        for suffix in TURKISH_SUFFIXES:
            if current.endswith(suffix) and len(current) > len(suffix) + 2:
                stripped = current[:-len(suffix)]
                if stripped not in candidates:
                    candidates.append(stripped)
                current = stripped
                break
        else:
            break  # Hiçbir ek bulunamadı
    
    return candidates


def strip_turkish_suffix(word: str) -> str:
    """
    Türkçe ekleri kelimeden temizler.
    Kademeli aday sistemi kullanarak sadece sözlükte eşleşen kökü döndürür.
    """
    word_lower = word.lower()
    candidates = generate_suffix_candidates(word_lower)
    
    # Öncelik: sözlükte veya typo'da direkt eşleşen
    for candidate in candidates:
        if candidate in TURKISH_MEDICINE_DICTIONARY or candidate in MEDICINE_TYPOS:
            return candidate
    
    # Eşleşme yoksa en kısa mantıklı adayı döndür
    return candidates[-1] if len(candidates[-1]) >= 3 else word_lower


def find_medicine_match(word: str, max_distance: int = 2) -> tuple:
    """
    Verilen kelime için en yakın ilaç eşleşmesini bulur.
    
    Returns:
        tuple: (bulunan_ilaç_ismi, İngilizce_karşılık) veya (None, None)
    """
    word_lower = word.lower()
    
    # 1. Önce yanlış yazım sözlüğünü kontrol et
    if word_lower in MEDICINE_TYPOS:
        corrected = MEDICINE_TYPOS[word_lower]
        if corrected in TURKISH_MEDICINE_DICTIONARY:
            return (corrected, TURKISH_MEDICINE_DICTIONARY[corrected])
    
    # 2. Direkt eşleşme kontrolü
    if word_lower in TURKISH_MEDICINE_DICTIONARY:
        return (word_lower, TURKISH_MEDICINE_DICTIONARY[word_lower])
    
    # 3. Kademeli ek kırpma ile kontrol et
    candidates = generate_suffix_candidates(word_lower)
    for candidate in candidates[1:]:  # İlk aday zaten kontrol edildi
        if candidate in TURKISH_MEDICINE_DICTIONARY:
            return (candidate, TURKISH_MEDICINE_DICTIONARY[candidate])
        if candidate in MEDICINE_TYPOS:
            corrected = MEDICINE_TYPOS[candidate]
            if corrected in TURKISH_MEDICINE_DICTIONARY:
                return (corrected, TURKISH_MEDICINE_DICTIONARY[corrected])
    
    # 4. Fuzzy matching - benzer ilaç ismi bul
    best_match = None
    best_distance = max_distance + 1
    
    # Tüm adaylarla dene
    for candidate in candidates:
        # Çok kısa kelimeler için fuzzy matching yapma (yanlış pozitif önleme)
        # "sana" → "xanax" gibi durumları önler
        if len(candidate) < 4:
            continue
            
        for medicine in TURKISH_MEDICINE_DICTIONARY.keys():
            # Hem aday hem ilaç ismi yeterince uzun olmalı
            if len(medicine) < 4:
                continue
                
            distance = levenshtein_distance(candidate, medicine)
            
            # Kısa kelimeler için daha düşük tolerans
            # 4-5 karakter: max 1 edit
            # 6+ karakter: max 2 edit
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
    Domain gate için kullanılır.
    Multi-word ilaç isimlerini de yakalar (aferin forte, tylol hot, vb.)
    
    Args:
        text: Kontrol edilecek metin
        
    Returns:
        list: Bulunan ilaç isimleri [(türkçe_isim, ingilizce_karşılık), ...]
    """
    import re
    
    text_lower = text.lower()
    
    # Kelimeleri ayır
    words = re.findall(r'\b[\wğüşıöçĞÜŞİÖÇ]+\b', text_lower, re.UNICODE)
    found_medicines = []
    matched_positions = set()  # Eşleşen kelime indeksleri (çift eşleşme önleme)
    
    # 1. Önce multi-word (2-gram, 3-gram) kontrol et - en uzun eşleşme öncelikli
    for n in [3, 2]:  # 3-gram, sonra 2-gram
        ngrams = generate_ngrams(words, n)
        for i, ngram in enumerate(ngrams):
            # Bu pozisyonlar zaten eşleşti mi?
            positions = set(range(i, i + n))
            if positions & matched_positions:
                continue
            
            # Direkt sözlükte var mı?
            if ngram in TURKISH_MEDICINE_DICTIONARY:
                # Bağlam kontrolü
                if is_medicine_context(ngram, text):
                    found_medicines.append((ngram, TURKISH_MEDICINE_DICTIONARY[ngram]))
                    matched_positions.update(positions)
                    print(f"[MEDICINE-NGRAM] '{ngram}' bulundu")
    
    # 2. Tek kelimeler için kontrol (zaten eşleşmemiş olanlar)
    for i, word in enumerate(words):
        if i in matched_positions:
            continue
        if len(word) < 3:
            continue
            
        medicine_name, english_name = find_medicine_match(word)
        
        if medicine_name and english_name:
            # Bağlam kontrolü - çift anlamlı kelimeler için
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
    import re
    
    text_lower = text.lower()
    
    # Kelimeleri ayır
    words = re.findall(r'\b[\wğüşıöçĞÜŞİÖÇ]+\b', text_lower, re.UNICODE)
    original_words = re.findall(r'\b[\wğüşıöçĞÜŞİÖÇ]+\b', text, re.UNICODE)
    result = text
    
    replacements = []  # (orijinal, yeni) çiftleri
    matched_positions = set()  # Eşleşen kelime indeksleri
    
    # 1. Önce multi-word (2-gram, 3-gram) kontrol et
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
    
    # 2. Tek kelimeler için kontrol
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
    
    # Uzun kelimelerden kısa kelimelere doğru değiştir (overlapping önleme)
    replacements.sort(key=lambda x: len(x[0]), reverse=True)
    
    for original, replacement in replacements:
        # Case-insensitive değiştirme
        pattern = r'\b' + re.escape(original) + r'\b'
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result


def translate_to_english(text: str) -> str:
    """Türkçe metni İngilizce'ye çevirir"""
    try:
        # Önce ilaç isimlerini dönüştür
        preprocessed = preprocess_turkish_medicine_names(text)
        translated = tr_to_en.translate(preprocessed)
        print(f"[TR→EN] {text[:50]}... → {translated[:50]}...")
        return translated
    except Exception as e:
        print(f"[ERROR] Çeviri hatası (TR→EN): {e}")
        return text  # Hata durumunda orijinal metni döndür


def translate_to_turkish(text: str) -> str:
    """İngilizce metni Türkçe'ye çevirir"""
    try:
        translated = en_to_tr.translate(text)
        print(f"[EN→TR] {text[:50]}... → {translated[:50]}...")
        return translated
    except Exception as e:
        print(f"[ERROR] Çeviri hatası (EN→TR): {e}")
        return text


def call_groq(messages: list, system_prompt: str = None) -> str:
    """Groq API'sine istek gönderir (İngilizce)"""
    try:
        groq_messages = []
        
        if system_prompt:
            groq_messages.append({"role": "system", "content": system_prompt})
        
        for msg in messages:
            groq_messages.append({"role": msg["role"], "content": msg["content"]})
        
        print(f"[DEBUG] Groq'a istek gönderiliyor, model: {GROQ_MODEL}")
        
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=groq_messages,
            temperature=0.7,
            max_tokens=2048,
        )
        
        result = response.choices[0].message.content
        print(f"[DEBUG] Groq yanıtı: {result[:100]}...")
        return result
        
    except Exception as e:
        print(f"[ERROR] Groq hatası: {str(e)}")
        raise HTTPException(status_code=503, detail=f"LLM API hatası: {str(e)}")


def call_groq_classifier(messages: list, system_prompt: str) -> str:
    """
    Sınıflandırma için optimize edilmiş Groq çağrısı.
    - temperature=0 (deterministik)
    - max_tokens=3 (YES/NO/UNCERTAIN)
    - stop=["\n"] (tek satır yanıt)
    """
    try:
        groq_messages = [{"role": "system", "content": system_prompt}]
        
        for msg in messages:
            groq_messages.append({"role": msg["role"], "content": msg["content"]})
        
        print(f"[CLASSIFIER] Groq'a sınıflandırma isteği gönderiliyor")
        
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=groq_messages,
            temperature=0,  # Deterministik
            max_tokens=10,  # Kısa yanıt (YES/NO/UNCERTAIN)
            stop=["\n"],    # Tek satır
        )
        
        result = response.choices[0].message.content.strip().upper()
        print(f"[CLASSIFIER] Sonuç: {result}")
        return result
        
    except Exception as e:
        print(f"[ERROR] Classifier hatası: {str(e)}")
        return "UNCERTAIN"  # Hata durumunda belirsiz





def check_health_domain_simple(message: str) -> str:
    """
    Mesajın sağlıkla ilgili olup olmadığını kontrol eder.
    Hard/soft non-health ayrımı yapar.
    
    Returns:
        str: "YES" (sağlık), "NO" (sağlık dışı), "UNCERTAIN" (belirsiz)
    """
    # 1. İlaç tespiti - ilaç varsa direkt sağlık kabul et
    detected_meds = detect_medicines(message)
    if detected_meds:
        print(f"[DOMAIN] İlaç tespit edildi: {[m[0] for m in detected_meds]} → YES")
        return "YES"
    
    # 2. Keyword bazlı sağlık ve non-health skorlarını al
    health_kw, health_pat, _, _ = count_health_signals(message)
    hard_nh, soft_nh, hard_found, soft_found = count_non_health_signals(message)
    
    health_score = health_kw + health_pat
    
    print(f"[DOMAIN] Skor - Sağlık: {health_score}, Hard-NH: {hard_nh}, Soft-NH: {soft_nh}")
    
    # 3. Skor karşılaştırması
    # Sağlık sinyali varsa ve hard non-health'ten fazla veya eşitse → YES
    if health_score > 0 and health_score >= hard_nh:
        return "YES"
    
    # Hard non-health varsa ve sağlık sinyali yoksa → NO
    if hard_nh > 0 and health_score == 0:
        print(f"[DOMAIN] Hard non-health sinyal: {hard_found[:3]}")
        return "NO"
    
    # Soft non-health varsa ama sağlık sinyali yoksa → UNCERTAIN (LLM'e sor)
    # Hard non-health baskınsa → NO
    if hard_nh > health_score:
        return "NO"
    
    # 4. Belirsiz durumda LLM'e sor (İngilizce) - tri-state
    message_en = translate_to_english(message)
    
    check_messages = [{
        "role": "user", 
        "content": f"Is this message about MEDICAL/HEALTH topics?\n\nMessage: {message_en}"
    }]
    
    check_system = """You are a classifier for a medical chatbot. Determine if the message is about medical/health topics.

HEALTH TOPICS (answer YES):
- Symptoms, diseases, illnesses
- Medications, drugs, treatments  
- Body parts, body functions
- Doctors, hospitals, clinics
- Mental health, anxiety, depression
- Diet for health reasons
- Medical tests, diagnoses

NON-HEALTH TOPICS (answer NO):
- Recipes, cooking (unless for medical diet)
- Sports scores, games
- Technology, programming
- Weather, travel
- Movies, music, entertainment
- Politics, finance

Answer only one token: YES, NO, or UNCERTAIN.

If the message could POSSIBLY be about health (mentions body parts, feelings, medications even ambiguously) → YES
If clearly and definitely unrelated to health → NO  
If too short/vague to determine → UNCERTAIN

For a medical chatbot, false positives are less harmful than false negatives.
When in doubt, lean towards YES."""
    
    # Classifier fonksiyonunu kullan (temperature=0)
    result = call_groq_classifier(check_messages, system_prompt=check_system)
    
    if "YES" in result:
        return "YES"
    elif "NO" in result and "UNCERTAIN" not in result:
        return "NO"
    else:
        return "UNCERTAIN"


def get_english_system_prompt(detailed: bool = False, has_history: bool = False, symptom_context: SymptomContext = None) -> str:
    """İngilizce sistem prompt'u döndürür - ilk soru vs takip soruları için farklı
    
    Eğer symptom_context varsa, 3D modelden gelen yapısal bilgiyi prompt'a ekler.
    """
    
    # Yapısal context varsa, prompt'a ekle
    context_section = ""
    if symptom_context:
        context_section = f"""
=== STRUCTURED SYMPTOM DATA FROM 3D BODY MODEL ===
The user has selected the following through the interactive 3D human body interface:

BODY REGION: {symptom_context.region_name_en} ({symptom_context.region})
SYMPTOM TYPE: {symptom_context.symptom_name_en} ({symptom_context.symptom})
SEVERITY: {symptom_context.severity_0_10}/10
ONSET: {symptom_context.onset}
TRIGGER: {symptom_context.trigger or 'Not specified'}
RED FLAGS REPORTED: {', '.join(symptom_context.red_flags) if symptom_context.red_flags else 'None'}

Use this structured data to provide more accurate and targeted guidance.
Focus on the specific body region and symptom type.
If red flags are present, emphasize seeking immediate medical attention.
=================================================

"""
    
    if not has_history:
        # İLK SORU - Kapsamlı yanıt
        return context_section + """You are a medical health assistant. Your role is to provide health education and general guidance.

IMPORTANT: This is the user's FIRST question. Provide a COMPREHENSIVE response with this EXACT structure:

**Your concern:** [1-2 sentence acknowledgment and brief explanation]

**Possible Causes:**
• [Cause 1]
• [Cause 2]
• [Cause 3]
• [Cause 4]

**What You Can Do:**
• [Recommendation 1]
• [Recommendation 2]
• [Recommendation 3]
• [Recommendation 4]

**Questions for You:**
• [Question about duration]
• [Question about severity]
• [Question about other symptoms]

**⚠️ Warning Signs - See a Doctor If:**
• [Red flag 1]
• [Red flag 2]
• [Red flag 3]
• [Red flag 4]

FORMATTING RULES:
- ALWAYS use bullet points (•) for lists - NEVER write as paragraphs
- Use **bold** for section headers
- Keep each bullet point to 1-2 sentences max
- Be empathetic but concise
- Do NOT diagnose or prescribe
- You are NOT a doctor"""
    
    else:
        # TAKİP SORUSU - Odaklı yanıt
        return context_section + """You are a medical health assistant continuing a conversation.

IMPORTANT: This is a FOLLOW-UP question. Be CONCISE and FOCUSED.

**Response Format:**
- Start with a direct answer to their question
- Use bullet points when listing multiple items:
  • Point 1
  • Point 2
- Keep response to 3-5 bullet points or 2-3 short paragraphs
- Don't repeat information already given

**If they share new symptoms:**
• Acknowledge the new info briefly
• Adjust guidance if needed
• Mention if urgency changes

RULES:
- You are NOT a doctor
- Be concise - this is a follow-up, not a new consultation
- Use bullet points (•) for any lists
- Stay focused on their current question"""


@app.get("/")
async def root():
    return {"message": "Medical Chatbot API", "status": "active", "provider": "Groq + Translation"}


def has_health_context_in_history(history: list) -> bool:
    """
    History'de gerçek bir sağlık konusu var mı kontrol eder.
    Sadece selamlaşma/nasılsın gibi mesajlar varsa False döner.
    """
    if not history:
        return False
    
    for msg in history:
        if msg.role == "user":
            content = msg.content.lower()
            # Selamlaşma değilse ve sağlık keyword'ü içeriyorsa
            if not is_greeting(content) and is_health_related(content):
                return True
    
    return False


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Ana chat endpoint'i
    Pipeline: TR Soru → EN Çeviri → Groq LLM → TR Çeviri → Yanıt
    """
    user_message = request.message.strip()
    
    if not user_message:
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz")
    
    has_history = len(request.history) > 0
    # Sağlık konulu bir geçmiş var mı? (merhaba/nasılsın değil, gerçek sağlık sorusu)
    has_health_context = has_health_context_in_history(request.history)
    
    # Symptom context var mı? (3D modelden gelen yapısal bilgi)
    has_symptom_context = request.symptom_context is not None
    
    # 1. Selamlaşma kontrolü (Türkçe)
    # SADECE symptom_context YOKSA ve sağlık bağlamı YOKSA selamlaşma yanıtı ver
    greeting_type = get_greeting_type(user_message)
    if greeting_type and not has_health_context and not has_symptom_context:
        return ChatResponse(
            response=get_greeting_response(greeting_type),
            is_emergency=False
        )
    
    # 2. Acil durum kontrolü (Türkçe + Yapısal context)
    # Red flag'leri kontrol et (yapısal context'ten)
    if request.symptom_context and request.symptom_context.red_flags:
        critical_flags = ['loss_of_consciousness', 'difficulty_breathing', 'chest_pain', 'severe_bleeding']
        if any(flag in critical_flags for flag in request.symptom_context.red_flags):
            return ChatResponse(
                response=f"🚨 **ACİL DURUM UYARISI** 🚨\n\nBildirdiğiniz belirtiler ({request.symptom_context.region_name_tr} - {request.symptom_context.symptom_name_tr}) acil tıbbi müdahale gerektirebilir!\n\n**HEMEN 112'yi arayın veya en yakın acil servise gidin!**\n\n⚠️ Bu durumu ciddiye alın ve beklemeden profesyonel yardım alın.",
                is_emergency=True,
                disclaimer="🚨 ACİL DURUM - Hemen 112'yi arayın!"
            )
    
    is_emergency, emergency_response = check_emergency_symptoms(user_message)
    if is_emergency:
        return ChatResponse(
            response=emergency_response,
            is_emergency=True,
            disclaimer="🚨 ACİL DURUM - Hemen 112'yi arayın!"
        )
    
    # 3. Sağlık domain kontrolü
    # Eğer symptom_context varsa, otomatik olarak sağlık konusu kabul et
    # - İlk sağlık sorusu: tam sağlık kontrolü yap
    # - Follow-up'larda: sadece açıkça alakasız konuları reddet (kara delik, yemek tarifi vs.)
    #   "gelip geçici", "evet", "3 gündür" gibi kısa cevaplar kabul edilir
    has_symptom_context = request.symptom_context is not None
    
    if not is_greeting(user_message) and not has_symptom_context:
        if has_health_context:
            # Follow-up: sadece açıkça sağlık dışı konu değişikliğini reddet
            # Ama önce sağlık sinyali var mı kontrol et (örn: "dizim ağrıyor ama futbol")
            health_kw, health_pat, _, _ = count_health_signals(user_message)
            non_health_count, _ = count_non_health_signals(user_message)
            
            # Sağlık sinyali varsa geçir
            if health_kw + health_pat > 0:
                pass  # Devam et
            elif non_health_count > 0:
                return ChatResponse(
                    response="Anladım, konu değiştirmek istiyorsunuz. 😊\n\nAncak ben sadece sağlık konularında yardımcı olabiliyorum. Eğer sağlıkla ilgili başka bir sorunuz varsa, sormaktan çekinmeyin!\n\nÖnceki konuya devam etmek isterseniz de yanınızdayım.",
                    is_emergency=False
                )
        else:
            # İlk sağlık sorusu (veya sadece selamlaşma geçmişi var): tam sağlık kontrolü
            domain_result = check_health_domain_simple(user_message)
            
            if domain_result == "NO":
                return ChatResponse(
                    response="Merhaba! Ben sağlık odaklı bir asistanım. 🏥\n\nSadece sağlık, hastalık, semptom ve tedavi ile ilgili sorularınızda size yardımcı olabilirim. Sağlık dışı konularda maalesef yardımcı olamıyorum.\n\nSağlıkla ilgili bir sorunuz varsa, lütfen sorun!",
                    is_emergency=False
                )
            elif domain_result == "UNCERTAIN":
                # Belirsiz durumda netleştirme sorusu sor
                return ChatResponse(
                    response="Merhaba! 😊 Mesajınızı tam anlayamadım.\n\nBen sağlık konularında yardımcı olan bir asistanım. Sağlık, semptom veya ilaçlarla ilgili bir sorunuz mu var?\n\nLütfen sorunuzu biraz daha açıklayabilir misiniz?",
                    is_emergency=False
                )
    
    # 4. Pipeline: TR → EN → LLM → EN → TR
    
    # 4a. Kullanıcı mesajını İngilizce'ye çevir
    user_message_en = translate_to_english(user_message)
    
    # 4b. Geçmiş mesajları İngilizce'ye çevir (drift önleme ile)
    # Eğer content_en varsa direkt kullan, yoksa çevir
    messages_en = []
    for msg in request.history[-10:]:
        if msg.content_en:
            # Frontend'den gelen İngilizce versiyon var, direkt kullan (drift önleme)
            content_en = msg.content_en
        elif msg.role == "user":
            # User mesajı, çevir
            content_en = translate_to_english(msg.content)
        else:
            # Assistant mesajı ve content_en yok, çevir (eski mesajlar için backward compat)
            content_en = translate_to_english(msg.content)
        
        messages_en.append({"role": msg.role, "content": content_en})
    
    # Kullanıcı mesajını ekle
    messages_en.append({"role": "user", "content": user_message_en})
    
    # 4c. İngilizce sistem prompt'u al (yapısal context ile)
    # has_health_context: True ise follow-up (kısa), False ise ilk sağlık sorusu (detaylı)
    system_prompt_en = get_english_system_prompt(
        detailed=request.detailed_response, 
        has_history=has_health_context,
        symptom_context=request.symptom_context
    )
    
    # 4d. Groq'tan İngilizce yanıt al
    response_en = call_groq(messages_en, system_prompt=system_prompt_en)
    
    # 4e. Yanıtı Türkçe'ye çevir
    response_tr = translate_to_turkish(response_en)
    
    return ChatResponse(
        response=response_tr,
        response_en=response_en,  # Frontend'in saklaması için (drift önleme)
        is_emergency=False
    )


@app.get("/models")
async def list_models():
    return {
        "current_model": GROQ_MODEL,
        "available_models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-70b-versatile", 
            "mixtral-8x7b-32768"
        ],
        "provider": "Groq",
        "pipeline": "TR → EN → LLM → TR"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
