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
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

from groq import Groq
from deep_translator import GoogleTranslator

from app.health_filter import is_health_related, check_emergency_symptoms, is_non_health_topic, is_greeting, get_greeting_type
from app.prompts import get_system_prompt, format_response_prompt, get_greeting_response

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
    is_emergency: bool = False
    disclaimer: str = "⚠️ Bu bilgiler eğitim amaçlıdır, tıbbi tavsiye değildir. Acil durumlarda 112'yi arayın."


def translate_to_english(text: str) -> str:
    """Türkçe metni İngilizce'ye çevirir"""
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





def check_health_domain_simple(message: str) -> bool:
    """Mesajın sağlıkla ilgili olup olmadığını basit kontrol eder"""
    # Önce sağlık DIŞI keyword kontrolü
    if is_non_health_topic(message):
        return False
    
    # Keyword bazlı sağlık kontrolü
    if is_health_related(message):
        return True
    
    # Belirsiz durumda LLM'e sor (İngilizce)
    message_en = translate_to_english(message)
    
    check_messages = [{
        "role": "user", 
        "content": f"Is this message about MEDICAL/HEALTH topics? Answer only YES or NO.\n\nMessage: {message_en}"
    }]
    
    check_system = """You are a classifier. Determine if the message is about medical/health topics.

HEALTH TOPICS (YES): diseases, symptoms, medications, treatments, body functions, doctors, hospitals, mental health

NON-HEALTH TOPICS (NO): recipes, sports, technology, weather, movies, travel, politics, general chat

Answer only YES or NO. If unsure, answer NO."""
    
    try:
        result = call_groq(check_messages, system_prompt=check_system)
        return "YES" in result.upper() and "NO" not in result.upper()
    except:
        return False


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
    
    # 1. Selamlaşma kontrolü (Türkçe)
    greeting_type = get_greeting_type(user_message)
    if greeting_type and not has_health_context:
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
            if is_non_health_topic(user_message):
                return ChatResponse(
                    response="Anladım, konu değiştirmek istiyorsunuz. 😊\n\nAncak ben sadece sağlık konularında yardımcı olabiliyorum. Eğer sağlıkla ilgili başka bir sorunuz varsa, sormaktan çekinmeyin!\n\nÖnceki konuya devam etmek isterseniz de yanınızdayım.",
                    is_emergency=False
                )
        else:
            # İlk sağlık sorusu (veya sadece selamlaşma geçmişi var): tam sağlık kontrolü
            is_health = check_health_domain_simple(user_message)
            if not is_health:
                return ChatResponse(
                    response="Merhaba! Ben sağlık odaklı bir asistanım. 🏥\n\nSadece sağlık, hastalık, semptom ve tedavi ile ilgili sorularınızda size yardımcı olabilirim. Sağlık dışı konularda maalesef yardımcı olamıyorum.\n\nSağlıkla ilgili bir sorunuz varsa, lütfen sorun!",
                    is_emergency=False
                )
    
    # 4. Pipeline: TR → EN → LLM → EN → TR
    
    # 4a. Kullanıcı mesajını İngilizce'ye çevir
    user_message_en = translate_to_english(user_message)
    
    # 4b. Geçmiş mesajları İngilizce'ye çevir
    messages_en = []
    for msg in request.history[-10:]:
        content_en = translate_to_english(msg.content) if msg.role == "user" else msg.content
        # Assistant mesajları zaten İngilizce'den çevrilmiş, tekrar çevirmeye gerek yok
        # Ama basitlik için hepsini çevirelim
        if msg.role == "assistant":
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
