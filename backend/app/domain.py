"""
Domain Check Module
Sağlık konusu tespiti için ortak modül
main.py ve router.py tarafından kullanılır
"""

import os
from functools import lru_cache
from groq import Groq
from deep_translator import GoogleTranslator

from app.health_filter import count_health_signals, count_non_health_signals
from app.medicine_utils import detect_medicines, preprocess_turkish_medicine_names


# ============ Lazy Init (startup crash önleme) ============

@lru_cache(maxsize=1)
def _get_groq_client() -> Groq:
    """Groq client'ı lazy olarak oluştur (import anında değil, ilk kullanımda)"""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        print("[DOMAIN] ⚠️ GROQ_API_KEY yok - classifier devre dışı")
    return Groq(api_key=api_key)


@lru_cache(maxsize=1)
def _get_translator() -> GoogleTranslator:
    """Translator'ı lazy olarak oluştur"""
    return GoogleTranslator(source='tr', target='en')


def _translate_for_classifier(text: str) -> str:
    """Domain kontrolü için basit çeviri"""
    try:
        if not text or len(text.strip()) < 2:
            return text
        preprocessed = preprocess_turkish_medicine_names(text)
        return _get_translator().translate(preprocessed)
    except Exception:
        return text


def _call_classifier(messages: list, system_prompt: str) -> str:
    """
    Groq classifier çağrısı (temperature=0, strict single token)

    Returns: "YES", "NO", or "UNCERTAIN"
    """
    # API key yoksa LLM'e sormadan YES'e yaslan (false negative daha kötü)
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        print("[DOMAIN] API key yok - belirsizde YES'e yaslanıyor")
        return "YES"

    try:
        response = _get_groq_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=0,
            max_tokens=3,  # Tek token için yeterli
            stop=["\n"]    # Açıklama sarkmalarını önle
        )
        raw = response.choices[0].message.content.strip().upper()

        # Güvenli parsing - startswith ile
        if raw.startswith("YES"):
            return "YES"
        if raw.startswith("NO"):
            return "NO"
        return "UNCERTAIN"

    except Exception as e:
        print(f"[DOMAIN] Classifier hatası: {e}")
        # Hata durumunda YES'e yaslan (false negative daha kötü)
        return "YES"


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
    message_en = _translate_for_classifier(message)

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

Answer only one word: YES, NO, or UNCERTAIN.

If the message could POSSIBLY be about health (mentions body parts, feelings, medications even ambiguously) → YES
If clearly and definitely unrelated to health → NO
If too short/vague to determine → UNCERTAIN

For a medical chatbot, false positives are less harmful than false negatives.
When in doubt, lean towards YES."""

    return _call_classifier(check_messages, system_prompt=check_system)
