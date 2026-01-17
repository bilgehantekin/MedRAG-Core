"""
RAG API Router
RAG tabanlı tıbbi chatbot endpoint'leri
"""

import os
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from deep_translator import GoogleTranslator
from groq import Groq

# RAG modülleri
from app.rag.rag_chain import RAGChain, get_rag_chain
from app.rag.knowledge_base import MedicalKnowledgeBase, get_knowledge_base
from app.rag.vector_store import VectorStore

# İlaç sözlüğü
from app.medicines import TURKISH_MEDICINE_DICTIONARY, MEDICINE_TYPOS

# Sağlık filtresi - selamlaşma ve sağlık konusu tespiti için
from app.health_filter import is_greeting, is_health_related, get_greeting_type

# Hazır cevaplar
from app.prompts import get_greeting_response

router = APIRouter(prefix="/rag", tags=["RAG"])

# Groq client (çeviri için)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))

# Translator'lar (yedek olarak Google Translate)
tr_to_en = GoogleTranslator(source='tr', target='en')
en_to_tr = GoogleTranslator(source='en', target='tr')

# Türkçe hal ekleri
TURKISH_SUFFIXES = [
    "lerden", "lardan", "lerde", "larda", "lerin", "ların", "lere", "lara",
    "lerle", "larla", "leri", "ları", "ler", "lar",
    "ından", "inden", "undan", "ünden", "ında", "inde", "unda", "ünde",
    "ının", "inin", "unun", "ünün", "ına", "ine", "una", "üne",
    "ıyla", "iyle", "uyla", "üyle", "ını", "ini", "unu", "ünü",
    "dan", "den", "tan", "ten", "da", "de", "ta", "te",
    "a", "e", "ya", "ye", "ı", "i", "u", "ü",
    "ım", "im", "um", "üm", "ın", "in", "un", "ün",
    "sı", "si", "su", "sü", "mı", "mi", "mu", "mü",
]


def strip_turkish_suffix(word: str) -> str:
    """Türkçe ekleri kelimeden temizler"""
    word_lower = word.lower()
    for suffix in TURKISH_SUFFIXES:
        if word_lower.endswith(suffix) and len(word_lower) > len(suffix) + 2:
            stripped = word_lower[:-len(suffix)]
            if stripped in TURKISH_MEDICINE_DICTIONARY or stripped in MEDICINE_TYPOS:
                return stripped
    return word_lower


def preprocess_medicine_names(text: str) -> str:
    """
    Türkçe ilaç isimlerini İngilizce karşılıklarına çevirir.
    Çeviriden ÖNCE çalıştırılır.
    """
    words = re.findall(r'\b[\wğüşıöçĞÜŞİÖÇ]+\b', text, re.UNICODE)
    result = text

    for word in words:
        if len(word) < 3:
            continue

        word_lower = word.lower()
        stripped = strip_turkish_suffix(word_lower)

        # Direkt eşleşme
        if stripped in TURKISH_MEDICINE_DICTIONARY:
            english = TURKISH_MEDICINE_DICTIONARY[stripped]
            pattern = r'\b' + re.escape(word) + r'\b'
            result = re.sub(pattern, english, result, flags=re.IGNORECASE)
            print(f"[RAG-MEDICINE] '{word}' → '{english[:40]}...'")
        # Yanlış yazım düzeltme
        elif stripped in MEDICINE_TYPOS:
            corrected = MEDICINE_TYPOS[stripped]
            if corrected in TURKISH_MEDICINE_DICTIONARY:
                english = TURKISH_MEDICINE_DICTIONARY[corrected]
                pattern = r'\b' + re.escape(word) + r'\b'
                result = re.sub(pattern, english, result, flags=re.IGNORECASE)
                print(f"[RAG-MEDICINE] '{word}' → '{corrected}' → '{english[:40]}...'")

    return result


# ============ Request/Response Models ============

class RAGMessage(BaseModel):
    role: str
    content: str
    content_en: Optional[str] = None


class RAGChatRequest(BaseModel):
    """RAG chatbot isteği"""
    message: str
    history: List[RAGMessage] = Field(default_factory=list)
    use_rag: bool = True  # RAG kullanılsın mı? False = normal LLM
    max_sources: int = 5  # Maksimum kaynak sayısı


class RAGSource(BaseModel):
    """RAG kaynak bilgisi"""
    title: str
    source: str
    category: str
    relevance_score: float


class RAGChatResponse(BaseModel):
    """RAG chatbot yanıtı"""
    response: str  # Türkçe yanıt
    response_en: Optional[str] = None  # İngilizce yanıt
    sources: List[RAGSource] = Field(default_factory=list)  # Kullanılan kaynaklar
    rag_used: bool = False  # RAG kullanıldı mı?
    disclaimer: str = "⚠️ Bu bilgiler eğitim amaçlıdır, tıbbi tavsiye değildir. Acil durumlarda 112'yi arayın."


class SearchRequest(BaseModel):
    """Knowledge base arama isteği"""
    query: str
    top_k: int = 5
    category: Optional[str] = None  # symptoms, diseases, treatments, etc.


class SearchResult(BaseModel):
    """Arama sonucu"""
    text: str
    title: str
    source: str
    category: str
    score: float


class KnowledgeBaseStats(BaseModel):
    """Knowledge base istatistikleri"""
    total_documents: int
    categories: List[str]
    embedding_model: str
    embedding_dimension: int


# ============ Helper Functions ============

def translate_to_english(text: str) -> str:
    """Türkçe'den İngilizce'ye çevir (ilaç isimleri ön işleme ile)"""
    try:
        if not text or len(text.strip()) < 2:
            return text
        # Önce ilaç isimlerini İngilizce'ye çevir
        preprocessed = preprocess_medicine_names(text)
        translated = tr_to_en.translate(preprocessed)
        print(f"[RAG TR→EN] {text[:50]}... → {translated[:50]}...")
        return translated
    except Exception as e:
        print(f"⚠️ Çeviri hatası (TR→EN): {e}")
        return text


def translate_to_turkish_with_llm(text: str) -> str:
    """LLM ile yüksek kaliteli Türkçe çeviri"""
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": """You are a professional translator. Translate the following English medical text to Turkish.

RULES:
- Use natural, fluent Turkish
- Keep medical terms accurate but understandable
- Preserve all formatting (bullet points, headers with **)
- Do NOT add any extra text or explanations
- Output ONLY the Turkish translation"""
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            temperature=0.3,
            max_tokens=2048
        )
        translated = response.choices[0].message.content
        print(f"[RAG LLM EN→TR] Çeviri tamamlandı ({len(text)} → {len(translated)} karakter)")
        return translated
    except Exception as e:
        print(f"[ERROR] LLM çeviri hatası: {e}")
        return None


def translate_to_turkish(text: str) -> str:
    """İngilizce metni Türkçe'ye çevirir - önce LLM, başarısızsa Google Translate"""
    try:
        if not text or len(text.strip()) < 2:
            return text

        # Önce LLM ile çevir (yüksek kalite)
        llm_translation = translate_to_turkish_with_llm(text)
        if llm_translation:
            return llm_translation

        # LLM başarısız olursa Google Translate kullan
        print(f"[RAG EN→TR] LLM başarısız, Google Translate deneniyor...")
        translated = en_to_tr.translate(text)
        print(f"[RAG EN→TR] {text[:50]}... → {translated[:50]}...")
        return translated

    except Exception as e:
        print(f"[ERROR] RAG Çeviri hatası (EN→TR): {e}")
        return text


# ============ Helper Functions ============

def generate_contextual_greeting(greeting_type: str, history: list) -> str:
    """
    Sağlık bağlamında selamlaşma mesajlarına bağlamsal cevap üretir.
    RAG kullanmadan, sadece LLM ile chat history'ye bakarak cevap verir.
    """
    try:
        # Chat history'den son sağlık konusunu bul
        health_topic = ""
        for msg in reversed(history):
            if msg.role == "user" and is_health_related(msg.content):
                health_topic = msg.content[:100]
                break

        # Greeting türüne göre prompt
        greeting_prompts = {
            'thanks': f"""Kullanıcı teşekkür etti. Sağlık konusu: "{health_topic}"

Kısa ve sıcak bir Türkçe cevap ver:
- Rica ederim de
- İyileşmesi için iyi dileklerini belirt
- Başka sorusu olursa yardımcı olacağını söyle
- 2-3 cümle yeterli""",

            'bye': f"""Kullanıcı vedalaşıyor. Sağlık konusu: "{health_topic}"

Kısa ve sıcak bir Türkçe veda cevabı ver:
- Hoşça kal de
- Sağlıklı günler dile
- 1-2 cümle yeterli""",

            'howru': f"""Kullanıcı nasılsın diye sordu.

Kısa bir Türkçe cevap ver:
- İyi olduğunu söyle
- Ona nasıl yardımcı olabileceğini sor
- 1-2 cümle yeterli""",

            'hello': f"""Kullanıcı merhaba dedi.

Kısa bir Türkçe selamlama cevabı ver:
- Merhaba de
- Nasıl yardımcı olabileceğini sor
- 1-2 cümle yeterli"""
        }

        prompt = greeting_prompts.get(greeting_type, greeting_prompts['hello'])

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Sen yardımsever bir sağlık asistanısın. Türkçe cevap ver."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=200
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"[ERROR] Bağlamsal selamlama hatası: {e}")
        # Hata durumunda hazır cevap döndür
        return get_greeting_response(greeting_type)


def has_health_context_in_history(history: list) -> bool:
    """
    History'de gerçek bir sağlık konusu var mı kontrol eder.
    Sadece selamlaşma/nasılsın gibi mesajlar varsa False döner.
    Normal chat ile aynı mantık.
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


# ============ Endpoints ============

@router.post("/chat", response_model=RAGChatResponse)
async def rag_chat(request: RAGChatRequest):
    """
    RAG tabanlı tıbbi chatbot

    Pipeline:
    1. Kullanıcı mesajı (TR) → İngilizce'ye çevir
    2. Knowledge base'de semantic search
    3. Bulunan context + soru → LLM
    4. Cevap (EN) → Türkçe'ye çevir

    Returns:
        RAGChatResponse: Zenginleştirilmiş yanıt + kaynaklar
    """
    try:
        user_message = request.message.strip()
        has_health_context = has_health_context_in_history(request.history)

        # Debug log
        print(f"[RAG] Mesaj: '{user_message}', has_health_context: {has_health_context}")

        # ============ 1. SELAMLAŞMA KONTROLÜ ============
        greeting_type = get_greeting_type(user_message)
        print(f"[RAG] greeting_type: {greeting_type}")

        # Selamlaşma mesajları: RAG KULLANMA, sadece LLM ile cevapla
        if greeting_type:
            # Sağlık bağlamı yoksa → hazır cevap
            if not has_health_context:
                print(f"[RAG] Selamlaşma (bağlamsız): {greeting_type} → Hazır cevap")
                return RAGChatResponse(
                    response=get_greeting_response(greeting_type),
                    response_en="",
                    sources=[],
                    rag_used=False
                )
            # Sağlık bağlamı varsa → LLM ile bağlamsal cevap (RAG olmadan)
            else:
                print(f"[RAG] Selamlaşma (bağlamlı): {greeting_type} → LLM ile cevapla (RAG yok)")
                contextual_response = generate_contextual_greeting(greeting_type, request.history)
                return RAGChatResponse(
                    response=contextual_response,
                    response_en="",
                    sources=[],
                    rag_used=False
                )

        # ============ 2. SAĞLIK DIŞI KONU KONTROLÜ ============
        # İlk soru (sağlık bağlamı yok) ve sağlıkla ilgili değilse → hazır ret cevabı
        is_health = is_health_related(user_message)
        print(f"[RAG] is_health_related: {is_health}")

        if not has_health_context and not is_health:
            print(f"[RAG] Sağlık dışı konu tespit edildi → Hazır ret cevabı dönüyor")
            return RAGChatResponse(
                response="Merhaba! Ben sağlık odaklı bir asistanım. 🏥\n\nSadece sağlık, hastalık, semptom ve tedavi ile ilgili sorularınızda size yardımcı olabilirim. Sağlık dışı konularda maalesef yardımcı olamıyorum.\n\nSağlıkla ilgili bir sorunuz varsa, lütfen sorun!",
                response_en="",
                sources=[],
                rag_used=False
            )

        # ============ 3. RAG İŞLEMİ ============
        rag_chain = get_rag_chain()

        # İlk sağlık sorusu mu yoksa follow-up mı?
        is_first_health_question = not has_health_context
        print(f"[RAG] İlk sağlık sorusu mu: {is_first_health_question}")

        # Mesajı İngilizce'ye çevir
        message_en = translate_to_english(user_message)

        # Chat history'yi hazırla
        history_en = []
        for msg in request.history[-6:]:  # Son 6 mesaj
            if msg.content_en:
                history_en.append({"role": msg.role, "content": msg.content_en})
            else:
                content_en = translate_to_english(msg.content) if msg.role == "user" else msg.content
                history_en.append({"role": msg.role, "content": content_en})

        # RAG query - is_first_health_question'ı geç
        result = rag_chain.query(
            question=message_en,
            chat_history=history_en,
            use_context=request.use_rag,
            is_first_health_question=is_first_health_question
        )
        
        # Cevabı Türkçe'ye çevir
        response_tr = translate_to_turkish(result["answer"])
        
        # Kaynakları formatla
        sources = [
            RAGSource(
                title=s.get("title", "Unknown"),
                source=s.get("source", "Medical Database"),
                category=s.get("category", "general"),
                relevance_score=round(1 / (1 + s.get("score", 1)), 3)  # Distance → similarity
            )
            for s in result.get("sources", [])[:request.max_sources]
        ]
        
        return RAGChatResponse(
            response=response_tr,
            response_en=result["answer"],
            sources=sources,
            rag_used=result.get("context_used", False)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG error: {str(e)}")


@router.post("/search", response_model=List[SearchResult])
async def search_knowledge_base(request: SearchRequest):
    """
    Knowledge base'de arama yap
    
    Debug ve test için kullanışlı endpoint.
    Hangi dökümanların bulunduğunu gösterir.
    """
    try:
        kb = get_knowledge_base()
        
        # Sorguyu İngilizce'ye çevir
        query_en = translate_to_english(request.query)
        
        # Arama yap
        results = kb.search(query_en, top_k=request.top_k, category=request.category)
        
        return [
            SearchResult(
                text=r["text"][:500] + "..." if len(r["text"]) > 500 else r["text"],
                title=r["metadata"].get("title", "Unknown"),
                source=r["metadata"].get("source", "Medical Database"),
                category=r["metadata"].get("category", "general"),
                score=round(r["score"], 4)
            )
            for r in results
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@router.get("/stats", response_model=KnowledgeBaseStats)
async def get_stats():
    """
    Knowledge base istatistiklerini döndür
    """
    try:
        kb = get_knowledge_base()
        stats = kb.get_stats()
        
        return KnowledgeBaseStats(
            total_documents=stats["total_documents"],
            categories=stats["categories"],
            embedding_model=stats["vector_store"]["model"],
            embedding_dimension=stats["vector_store"]["dimension"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats error: {str(e)}")


@router.post("/reload")
async def reload_knowledge_base():
    """
    Knowledge base'i yeniden yükle
    
    Yeni dökümanlar ekledikten sonra kullanın.
    """
    try:
        # Global instance'ı sıfırla
        from app.rag import knowledge_base as kb_module
        kb_module._knowledge_base = None
        
        # Yeniden yükle
        kb = get_knowledge_base()
        stats = kb.get_stats()
        
        return {
            "status": "success",
            "message": "Knowledge base reloaded",
            "documents": stats["total_documents"],
            "categories": stats["categories"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reload error: {str(e)}")


@router.get("/health")
async def rag_health_check():
    """
    RAG sistem sağlık kontrolü
    """
    try:
        kb = get_knowledge_base()
        stats = kb.get_stats()
        
        return {
            "status": "healthy",
            "knowledge_base": {
                "loaded": True,
                "documents": stats["total_documents"]
            },
            "embedding_model": stats["vector_store"]["model"],
            "ready": stats["total_documents"] > 0
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "ready": False
        }
