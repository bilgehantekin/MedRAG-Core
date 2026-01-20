"""
RAG API Router
RAG tabanlı tıbbi chatbot endpoint'leri
"""

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from deep_translator import GoogleTranslator
from groq import Groq

# RAG modülleri
from app.rag.rag_chain import get_rag_chain
from app.rag.knowledge_base import get_knowledge_base

# İlaç isim işleme (main.py ile aynı gelişmiş versiyon)
from app.medicine_utils import mask_medicines, unmask_medicines, convert_english_medicines_to_turkish

# Sağlık filtresi - selamlaşma ve sağlık konusu tespiti için
from app.health_filter import is_greeting, is_health_related, get_greeting_type, count_health_signals, count_non_health_signals

# Hazır cevaplar
from app.prompts import get_greeting_response

# Domain kontrolü (main.py ile aynı tri-state logic)
from app.domain import check_health_domain_simple

router = APIRouter(prefix="/rag", tags=["RAG"])

# Groq client (çeviri için)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))

# Translator'lar
tr_to_en = GoogleTranslator(source='tr', target='en')
en_to_tr = GoogleTranslator(source='en', target='tr')


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
    """Türkçe'den İngilizce'ye çevir (ilaç maskeleri korunur)"""
    try:
        if not text or len(text.strip()) < 2:
            return text
        translated = tr_to_en.translate(text)
        print(f"[RAG TR→EN] {text[:50]}... → {translated[:50]}...")
        return translated
    except Exception as e:
        print(f"⚠️ Çeviri hatası (TR→EN): {e}")
        return text


def translate_to_turkish(text: str) -> str:
    """İngilizce metni Türkçe'ye çevirir - Google Translate (main.py ile aynı)"""
    try:
        if not text or len(text.strip()) < 2:
            return text
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

        # ============ 2. SAĞLIK DIŞI KONU KONTROLÜ (main.py ile aynı tri-state) ============
        # İlk soru (sağlık bağlamı yok) - tam sağlık kontrolü
        if not has_health_context:
            domain_result = check_health_domain_simple(user_message)
            print(f"[RAG] check_health_domain_simple: {domain_result}")

            if domain_result == "NO":
                return RAGChatResponse(
                    response="Merhaba! Ben sağlık odaklı bir asistanım. 🏥\n\nSadece sağlık, hastalık, semptom ve tedavi ile ilgili sorularınızda size yardımcı olabilirim. Sağlık dışı konularda maalesef yardımcı olamıyorum.\n\nSağlıkla ilgili bir sorunuz varsa, lütfen sorun!",
                    response_en="",
                    sources=[],
                    rag_used=False
                )
            elif domain_result == "UNCERTAIN":
                # Belirsiz durumda netleştirme sorusu sor (main.py ile aynı)
                return RAGChatResponse(
                    response="Merhaba! 😊 Mesajınızı tam anlayamadım.\n\nBen sağlık konularında yardımcı olan bir asistanım. Sağlık, semptom veya ilaçlarla ilgili bir sorunuz mu var?\n\nLütfen sorunuzu biraz daha açıklayabilir misiniz?",
                    response_en="",
                    sources=[],
                    rag_used=False
                )

        # ============ 2b. FOLLOW-UP'TA KONU DEĞİŞİMİ KONTROLÜ (main.py ile aynı) ============
        if has_health_context and not greeting_type:
            health_kw, health_pat, _, _ = count_health_signals(user_message)
            hard_nh, soft_nh, _, _ = count_non_health_signals(user_message)

            # Sağlık sinyali yok + hard non-health varsa -> konu değiştirme reddi
            if (health_kw + health_pat) == 0 and hard_nh > 0:
                print(f"[RAG] Follow-up'ta konu değişimi tespit edildi → Ret")
                return RAGChatResponse(
                    response="Anladım, konu değiştirmek istiyorsunuz. 😊\n\nAncak ben sadece sağlık konularında yardımcı olabiliyorum. Eğer sağlıkla ilgili başka bir sorunuz varsa, sormaktan çekinmeyin!\n\nÖnceki konuya devam etmek isterseniz de yanınızdayım.",
                    response_en="",
                    sources=[],
                    rag_used=False
                )

        # ============ 3. RAG İŞLEMİ ============
        rag_chain = get_rag_chain()

        # İlk sağlık sorusu mu yoksa follow-up mı?
        is_first_health_question = not has_health_context
        print(f"[RAG] İlk sağlık sorusu mu: {is_first_health_question}")

        # Global mask_map ve counter (history + current message için tek map)
        global_mask_map = {}
        mask_counter = 0

        # 3a. Chat history'yi hazırla (history'den başla, counter collision önleme)
        history_en = []
        for msg in request.history[-6:]:  # Son 6 mesaj
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
                # Assistant mesajı, sadece çevir
                content_en = translate_to_english(msg.content)
            history_en.append({"role": msg.role, "content": content_en})

        # 3b. Kullanıcı mesajındaki ilaçları maskele (LLM için)
        # Bunu search query'den önce yapıyoruz ki generic isimleri çıkarabilelim
        masked_message, global_mask_map, mask_counter = mask_medicines(
            user_message, start_counter=mask_counter, existing_mask_map=global_mask_map
        )
        print(f"[RAG MASK-MAP] {global_mask_map}")

        # 3c. Maskesiz sorguyu çevir + generic isimler ekle (KB search için)
        # Örn: "Calpol ilacı" → "Calpol paracetamol ilacı" → "Calpol paracetamol drug"
        search_query_tr = user_message
        if global_mask_map:
            # Generic isimleri sorguya ekle - brand/generic uyuşmazlığını azaltır
            generic_names = []
            for mapping in global_mask_map.values():
                en_name = mapping.get("en", "")
                # "paracetamol (Turkish brand: Calpol)" → "paracetamol"
                if "(" in en_name:
                    generic = en_name.split("(")[0].strip()
                else:
                    generic = en_name.strip()
                if generic and len(generic) > 2:
                    generic_names.append(generic)
            if generic_names:
                search_query_tr = f"{user_message} {' '.join(generic_names)}"
                print(f"[RAG Search Query] Enhanced with generic names: {search_query_tr}")

        search_query_en = translate_to_english(search_query_tr)

        # 3d. Maskelenmiş mesajı İngilizce'ye çevir (LLM için)
        llm_query_en = translate_to_english(masked_message)

        # RAG query - search_query ayrı geçilir (maskesiz)
        result = rag_chain.query(
            question=llm_query_en,  # LLM'e gönderilecek (maskeli)
            search_query=search_query_en,  # KB search için (maskesiz)
            chat_history=history_en,
            use_context=request.use_rag,
            is_first_health_question=is_first_health_question,
            mask_map=global_mask_map  # Token → ilaç adı eşleştirmesi
        )

        # 3d. Cevabı Türkçe'ye çevir
        response_tr = translate_to_turkish(result["answer"])
        response_en_raw = result["answer"]

        # 3e. ÖNCE LLM'in kendi eklediği İngilizce ilaç isimlerini Türkçe'ye çevir
        # format_style="tr_only": parantez içinde İngilizce isim KOYMUYORUZ
        # Aksi halde "Parasetamol (Calpol (paracetamol))" gibi çirkin çıktılar oluşuyor
        response_tr = convert_english_medicines_to_turkish(response_tr, format_style="tr_only")

        # 3f. SONRA maskeleri aç: MEDTOK0X → "Calpol"
        # format_style="tr_only": kullanıcının yazdığı Türkçe ismi koru
        if global_mask_map:
            response_tr = unmask_medicines(response_tr, global_mask_map, format_style="tr_only")
            # response_en için en_only kullan (drift önleme - saf İngilizce kalmalı)
            response_en_raw = unmask_medicines(response_en_raw, global_mask_map, format_style="en_only")

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
            response_en=response_en_raw,  # Saf İngilizce (drift önleme için)
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
        # Global instance'ları sıfırla
        from app.rag import knowledge_base as kb_module
        from app.rag import rag_chain as rag_chain_module

        kb_module._knowledge_base = None
        rag_chain_module._rag_chain = None  # RAG chain'i de sıfırla (stale KB referansı önleme)

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
