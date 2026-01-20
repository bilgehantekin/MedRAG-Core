"""
Medical Chatbot - FastAPI Backend
Sağlık odaklı chatbot API'si - Groq + Translation Pipeline
TR → EN → LLM → EN → TR
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
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
from app.medicines import MEDICINE_BRANDS
from app.medicine_utils import detect_medicines, mask_medicines, unmask_medicines, convert_english_medicines_to_turkish
from app.domain import check_health_domain_simple

# Groq API ayarları
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

if not GROQ_API_KEY:
    print("⚠️  UYARI: GROQ_API_KEY ayarlanmamış! .env dosyasına ekleyin.")

groq_client = Groq(api_key=GROQ_API_KEY)

# Translator'lar
tr_to_en = GoogleTranslator(source='tr', target='en')
en_to_tr = GoogleTranslator(source='en', target='tr')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events - preload models at startup"""
    # Startup: preload X-ray model if not in demo mode
    try:
        from app.image.config import DEMO_MODE
        if not DEMO_MODE:
            print("🔄 Pre-loading X-ray analysis model at startup...")
            from app.image import inference
            if inference.load_model():
                print("✅ X-ray model pre-loaded successfully")
            else:
                print("⚠️ X-ray model failed to pre-load, will use DEMO mode")
        else:
            print("ℹ️ X-ray model in DEMO mode - skipping pre-load")
    except ImportError as e:
        print(f"⚠️ Image module not available: {e}")
    except Exception as e:
        print(f"⚠️ Error pre-loading model: {e}")

    yield  # Application runs here

    # Shutdown: cleanup if needed
    print("👋 Shutting down...")


app = FastAPI(
    title="Medical Chatbot API",
    description="Sağlık odaklı bilgilendirme chatbot'u - Groq + Translation + RAG",
    version="3.0.0",
    lifespan=lifespan
)

# RAG Router'ı dahil et (opsiyonel - RAG kuruluysa)
try:
    from app.rag.router import router as rag_router
    app.include_router(rag_router)
    print("✅ RAG router yüklendi - /rag/* endpoint'leri aktif")
except ImportError as e:
    print(f"⚠️ RAG router yüklenemedi (sentence-transformers/faiss kurulu değil): {e}")

# Image Analysis Router'ı dahil et (opsiyonel - torch kuruluysa)
try:
    from app.image.router import router as image_router
    app.include_router(image_router)
    print("✅ Image Analysis router yüklendi - /image/* endpoint'leri aktif")
except ImportError as e:
    print(f"⚠️ Image Analysis router yüklenemedi (torch/torchxrayvision kurulu değil): {e}")

# CORS ayarları
# NOT: Prod'da allow_origins'i whitelist'e çevirin veya allow_credentials=False yapın
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # "*" ile kullanıldığında False olmalı
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
    red_flags: List[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str
    history: List[Message] = Field(default_factory=list)
    detailed_response: bool = False
    symptom_context: Optional[SymptomContext] = None  # 3D modelden gelen yapısal bilgi


class ChatResponse(BaseModel):
    response: str
    response_en: Optional[str] = None  # İngilizce versiyon (drift önleme için frontend'in saklaması için)
    is_emergency: bool = False
    disclaimer: str = "⚠️ Bu bilgiler eğitim amaçlıdır, tıbbi tavsiye değildir. Acil durumlarda 112'yi arayın."

def translate_to_english(text: str) -> str:
    """Türkçe metni İngilizce'ye çevirir (ilaç maskeleri korunur)"""
    try:
        translated = tr_to_en.translate(text)
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
            max_tokens=3,   # Kısa yanıt (YES/NO/UNCERTAIN)
            stop=["\n"],    # Tek satır
        )
        
        result = response.choices[0].message.content.strip().upper()
        print(f"[CLASSIFIER] Sonuç: {result}")
        return result
        
    except Exception as e:
        print(f"[ERROR] Classifier hatası: {str(e)}")
        return "UNCERTAIN"  # Hata durumunda belirsiz





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
            hard_nh, soft_nh, _, _ = count_non_health_signals(user_message)
            
            # Sağlık sinyali varsa geçir
            if health_kw + health_pat > 0:
                pass  # Devam et
            # Follow-up'ta sadece HARD konu değişimini reddet
            elif hard_nh > 0:
                return ChatResponse(
                    response="Anladım, konu değiştirmek istiyorsunuz. 😊\n\nAncak ben sadece sağlık konularında yardımcı olabiliyorum. Eğer sağlıkla ilgili başka bir sorunuz varsa, sormaktan çekinmeyin!\n\nÖnceki konuya devam etmek isterseniz de yanınızdayım.",
                    is_emergency=False
                )
            # Soft non-health (fiyat/ne kadar/futbol) gördüysen bile follow-up'ta direkt reddetme
            else:
                pass  # Devam et
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
    
    # 4. Pipeline: TR → MASK → EN → LLM → TR → UNMASK → EN→TR
    # İlaç isimlerini maskele, çevir, LLM'den yanıt al, çevir, maskeleri aç, EN ilaçları TR'ye çevir

    # Global mask_map ve counter (history + current message için tek map)
    global_mask_map = {}
    mask_counter = 0

    # 4a. Geçmiş mesajları işle (history'den başla, counter collision önleme)
    messages_en = []
    for msg in request.history[-10:]:
        if msg.content_en:
            # Frontend'den gelen İngilizce versiyon var, direkt kullan (drift önleme)
            content_en = msg.content_en
        elif msg.role == "user":
            # User mesajı, maskele ve çevir (counter devam ettir)
            masked_hist, global_mask_map, mask_counter = mask_medicines(
                msg.content, start_counter=mask_counter, existing_mask_map=global_mask_map
            )
            content_en = translate_to_english(masked_hist)
        else:
            # Assistant mesajı ve content_en yok, çevir (eski mesajlar için backward compat)
            content_en = translate_to_english(msg.content)

        messages_en.append({"role": msg.role, "content": content_en})

    # 4b. Kullanıcı mesajındaki ilaçları maskele (counter kaldığı yerden devam)
    masked_message, global_mask_map, mask_counter = mask_medicines(
        user_message, start_counter=mask_counter, existing_mask_map=global_mask_map
    )
    print(f"[MASK-MAP] {global_mask_map}")

    # 4c. Maskelenmiş mesajı İngilizce'ye çevir
    user_message_en = translate_to_english(masked_message)

    # Kullanıcı mesajını ekle
    messages_en.append({"role": "user", "content": user_message_en})

    # 4d. İngilizce sistem prompt'u al (yapısal context ile)
    # has_health_context: True ise follow-up (kısa), False ise ilk sağlık sorusu (detaylı)
    system_prompt_en = get_english_system_prompt(
        detailed=request.detailed_response,
        has_history=has_health_context,
        symptom_context=request.symptom_context
    )

    # 4e. Groq'tan İngilizce yanıt al
    response_en_raw = call_groq(messages_en, system_prompt=system_prompt_en)

    # 4f. Yanıtı Türkçe'ye çevir
    response_tr = translate_to_turkish(response_en_raw)

    # 4g. ÖNCE LLM'in kendi eklediği İngilizce ilaç isimlerini Türkçe'ye çevir
    # (mask ile yakalanmayan "ibuprofen", "acetaminophen" gibi)
    # NOT: Bu unmask'ten ÖNCE yapılmalı, yoksa çift dönüşüm olur
    response_tr = convert_english_medicines_to_turkish(response_tr, format_style="tr_with_en")

    # 4h. SONRA maskeleri aç: MEDTOK0 → "Parol (paracetamol)"
    if global_mask_map:
        response_tr = unmask_medicines(response_tr, global_mask_map, format_style="tr_with_en")
        # response_en için en_only kullan (drift önleme - saf İngilizce kalmalı)
        response_en_raw = unmask_medicines(response_en_raw, global_mask_map, format_style="en_only")

    return ChatResponse(
        response=response_tr,
        response_en=response_en_raw,  # Saf İngilizce (drift önleme için)
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
