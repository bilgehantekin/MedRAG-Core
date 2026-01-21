"""
RAG Chain Module
Retrieval-Augmented Generation pipeline

Performance Optimizations:
- Request-level profiling for timing breakdown
- Streaming support for faster perceived response
"""

import os
from typing import Optional, List, Dict, Generator
from groq import Groq
from dotenv import load_dotenv
from pathlib import Path

from app.rag.knowledge_base import MedicalKnowledgeBase, get_knowledge_base
from app.rag.performance import RequestProfiler

# .env yükle
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class RAGChain:
    """
    RAG Pipeline
    1. Kullanıcı sorusu al
    2. Knowledge base'de semantic search yap
    3. Bulunan context ile LLM'e sor
    4. Zenginleştirilmiş cevap döndür
    """

    def __init__(
        self,
        knowledge_base: Optional[MedicalKnowledgeBase] = None,
        model: str = "llama-3.3-70b-versatile"
    ):
        self.knowledge_base = knowledge_base or get_knowledge_base()
        self.model = model
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))

        print(f"✅ RAG Chain başlatıldı (model: {model})")

    # Score thresholds for emergency detection
    # NOTE: Score is L2 DISTANCE - LOWER is BETTER (closer match)
    # IMPORTANT: keyword_matched results have artificial scores, ignore them for emergency
    EMERGENCY_SCORE_STRICT = 0.35  # Only real semantic match triggers emergency
    EMERGENCY_SCORE_WARN = 0.7     # Decent match → cautious mention

    def _check_emergency(self, search_results: List[Dict]) -> Dict:
        """
        Arama sonuçlarında acil durum olup olmadığını kontrol et

        IMPORTANT:
        - Score is L2 distance - LOWER score = BETTER match
        - keyword_matched results have ARTIFICIAL scores (keyword boost)
          → emergency tespitinde GÖZ ARDI EDİLMELİ
        - Sadece gerçek semantik benzerlik emergency tetiklemeli

        Emergency tetikleme kuralları (False Positive azaltmak için):
        1. Top-1 emergency + score <= 0.35 + keyword_matched DEĞİL → Kesin emergency
        2. Top-2'de emergency + score <= 0.7 + keyword_matched DEĞİL → Emergency
        3. Emergency var ama keyword_matched VEYA score > 0.7 → Sadece bilgilendirme (acil değil)

        Returns:
            {
                "is_emergency": bool,
                "is_cautious_warning": bool,  # Emergency içerik var ama tetiklenmedi
                "emergency_number": str (varsayılan "112"),
                "emergency_sources": List[Dict]
            }
        """
        emergency_sources = []
        emergency_number = "112"

        # Track semantic-only emergency matches (not keyword boosted)
        semantic_emergency_top1 = None
        semantic_emergency_top2 = None

        for i, result in enumerate(search_results):
            metadata = result.get("metadata", {})
            safety_level = metadata.get("safety_level", "general")
            call_emergency = metadata.get("call_emergency", False)
            score = result.get("score", float("inf"))
            is_keyword_matched = result.get("keyword_matched", False)

            if safety_level == "emergency" or call_emergency:
                emergency_sources.append({
                    "title": metadata.get("title", ""),
                    "title_tr": metadata.get("title_tr", ""),
                    "source_url": metadata.get("source_url", ""),
                    "score": score,
                    "rank": i + 1,
                    "keyword_matched": is_keyword_matched
                })
                if metadata.get("emergency_number"):
                    emergency_number = metadata["emergency_number"]

                # Track semantic-only matches for top positions
                if not is_keyword_matched:
                    if i == 0 and semantic_emergency_top1 is None:
                        semantic_emergency_top1 = {"score": score, "title": metadata.get("title", "")}
                    elif i <= 1 and semantic_emergency_top2 is None:
                        semantic_emergency_top2 = {"score": score, "title": metadata.get("title", "")}

        # Determine emergency level
        is_emergency = False
        is_cautious_warning = False

        if emergency_sources:
            # Rule 1: Top-1 semantic emergency with very good score
            if semantic_emergency_top1 and semantic_emergency_top1["score"] <= self.EMERGENCY_SCORE_STRICT:
                is_emergency = True
                print(f"🚨 Emergency Rule 1: Top-1 semantic match '{semantic_emergency_top1['title']}' score={semantic_emergency_top1['score']:.3f}")

            # Rule 2: Top-2 semantic emergency with good score
            elif semantic_emergency_top2 and semantic_emergency_top2["score"] <= self.EMERGENCY_SCORE_WARN:
                is_emergency = True
                print(f"🚨 Emergency Rule 2: Top-2 semantic match '{semantic_emergency_top2['title']}' score={semantic_emergency_top2['score']:.3f}")

            # Rule 3: Emergency content exists but not strong enough match
            else:
                is_cautious_warning = True
                print(f"⚠️ Emergency content found but not triggered (keyword_matched or weak score)")

        return {
            "is_emergency": is_emergency,
            "is_cautious_warning": is_cautious_warning,
            "emergency_number": emergency_number,
            "emergency_sources": emergency_sources
        }

    # Score threshold for sensitive content detection
    SENSITIVE_SCORE_THRESHOLD = 0.8  # Only consider results with score < 0.8 (lower is better)

    def _check_sensitive(self, search_results: List[Dict]) -> Dict:
        """
        Hassas içerik (mental health) kontrolü

        Sadece TOP-2 sonuçları ve düşük skorlu (iyi eşleşme) sonuçları kontrol eder.
        Bu, "drug" gibi genel kelimelerin yanlışlıkla sensitive mode tetiklemesini önler.

        Returns:
            {
                "is_sensitive": bool,
                "is_crisis": bool,  # Self-harm, suicide gibi kriz durumu
                "sensitive_sources": List[Dict]
            }
        """
        sensitive_sources = []
        is_crisis = False

        crisis_keywords = {"suicide", "self-harm", "intihar", "kendine zarar"}

        # Only check top-2 results OR results with good scores
        for i, result in enumerate(search_results):
            score = result.get("score", float("inf"))

            # Skip results that are:
            # - Not in top-2 AND
            # - Have poor scores (high distance)
            if i >= 2 and score > self.SENSITIVE_SCORE_THRESHOLD:
                continue

            metadata = result.get("metadata", {})
            safety_level = metadata.get("safety_level", "general")
            category = metadata.get("category", "")
            title = metadata.get("title", "").lower()
            title_tr = metadata.get("title_tr", "").lower()

            if safety_level == "sensitive" or category == "mental_health":
                sensitive_sources.append({
                    "title": metadata.get("title", ""),
                    "title_tr": metadata.get("title_tr", ""),
                    "score": score
                })

                # Check for crisis content
                for kw in crisis_keywords:
                    if kw in title or kw in title_tr:
                        is_crisis = True
                        break

        return {
            "is_sensitive": len(sensitive_sources) > 0,
            "is_crisis": is_crisis,
            "sensitive_sources": sensitive_sources
        }
    
    def get_rag_system_prompt(self, context: str, is_followup: bool = False) -> str:
        """RAG için sistem prompt'u oluştur - main.py ile aynı format"""

        if not is_followup:
            # İLK SORU - Kapsamlı yanıt (main.py ile aynı)
            return f"""You are a medical health assistant. Your role is to provide health education and general guidance.

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
- You are NOT a doctor
- Use the reference information below to inform your response, but DO NOT copy text verbatim
- Write in plain, conversational language

=== REFERENCE INFORMATION (use to enhance your response) ===
{context}
==============================================================="""
        else:
            # TAKİP SORUSU - Odaklı yanıt (main.py ile aynı format)
            return f"""You are a medical health assistant continuing a conversation.

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
- Stay focused on their current question
- Use the reference information to inform your response, but DO NOT copy text verbatim

=== REFERENCE INFORMATION ===
{context}
============================"""

    def get_emergency_system_prompt(self, context: str, emergency_number: str = "112") -> str:
        """Acil durum için özel sistem prompt'u"""
        return f"""⚠️ **BU BİR ACİL DURUM OLABİLİR** ⚠️

You are a medical emergency assistant. The user's query matches emergency medical content.

**YOUR FIRST PRIORITY**: If this appears to be a life-threatening situation, IMMEDIATELY advise calling emergency services.

**RESPONSE FORMAT** (use this EXACT structure):

🚨 **ACİL DURUM UYARISI / EMERGENCY WARNING**
• **Hemen {emergency_number}'yi arayın / Call {emergency_number} immediately** if:
  - [List specific emergency signs from context]

**While Waiting for Help:**
• [First aid step 1]
• [First aid step 2]
• [First aid step 3]

**Do NOT:**
• [What not to do 1]
• [What not to do 2]

**⚠️ Important:**
This is general guidance only. Always call {emergency_number} if unsure.

RULES:
- ALWAYS start with emergency number ({emergency_number}) advice
- Use bullet points (•) for all lists
- Keep instructions clear and actionable
- Include Turkish translations where helpful
- You are NOT a replacement for emergency services
- Use the reference information below, but prioritize safety

=== EMERGENCY REFERENCE INFORMATION ===
{context}
======================================"""

    def get_crisis_system_prompt(self, context: str) -> str:
        """Mental health krizi için özel sistem prompt'u (self-harm, suicide)"""
        return f"""🤝 **HASSAS KONU - EMPATİ VE GÜVENLİK ÖNCELİKLİ**

You are a compassionate mental health support assistant. The user may be experiencing difficult emotions or thoughts.

**YOUR FIRST PRIORITY**: Show empathy and provide crisis resources immediately.

**RESPONSE FORMAT**:

💙 **Sizi duyuyorum / I hear you**
[1-2 empathetic sentences acknowledging their feelings without judgment]

📞 **Acil Yardım / Emergency Support**
• **Acil Durum: 112** (7/24)
• **Alo 183**: Aile ve Sosyal Hizmetler danışma hattı
• En yakın acil servise veya ruh sağlığı merkezine başvurun
• Yalnız değilsiniz - destek almak güç göstergesidir

**What might help right now:**
• [Grounding technique or coping suggestion]
• [Encourage talking to someone they trust]
• [Mention professional help is available - psychiatrist, psychologist, ÇÖZÜM merkezi]

**⚠️ Important:**
• If you're in immediate danger, please call 112 immediately
• These feelings are real, but they can change with support
• You deserve help and compassion

RULES:
- Lead with empathy, not medical information
- ALWAYS provide crisis hotline numbers prominently
- Never dismiss or minimize their feelings
- Use gentle, supportive language
- You are NOT a replacement for professional mental health care
- Do NOT provide specific medical advice for mental health conditions

=== REFERENCE INFORMATION ===
{context}
============================"""

    def get_sensitive_system_prompt(self, context: str, is_followup: bool = False) -> str:
        """Hassas konular (mental health) için özel sistem prompt'u"""
        return f"""You are a supportive health assistant discussing a sensitive topic.

**Important Guidelines:**
- Be empathetic and non-judgmental
- Acknowledge their feelings before providing information
- Encourage professional help when appropriate
- Include crisis resources if relevant

**Response Format:**
- Start with empathetic acknowledgment
- Provide helpful information from context
- Suggest next steps (professional help, self-care)
- Mention: "Bu bilgi profesyonel yardım yerine geçmez"

RULES:
- Do NOT diagnose mental health conditions
- Encourage seeking professional support
- Be sensitive with language
- For emergencies, direct to 112 (acil) or nearest emergency room

=== REFERENCE INFORMATION ===
{context}
============================"""

    def query(
        self,
        question: str,
        chat_history: Optional[List[Dict]] = None,
        use_context: bool = True,
        max_context_tokens: int = 2500,
        is_first_health_question: bool = True,
        search_query: Optional[str] = None,
        mask_map: Optional[Dict] = None,
        enable_profiling: bool = True
    ) -> Dict:
        """
        RAG query yap

        Args:
            question: LLM'e gönderilecek soru (İngilizce, maskeli olabilir)
            chat_history: Önceki mesajlar
            use_context: Context kullanılsın mı (False = normal LLM)
            max_context_tokens: Context için maksimum token
            is_first_health_question: İlk sağlık sorusu mu? (True = detaylı, False = kısa)
            search_query: Knowledge base araması için soru (maskesiz). None ise question kullanılır.
            mask_map: İlaç maskeleme haritası (örn: {'MEDTOK0X': {'tr': 'Calpol', 'en': 'paracetamol'}})
            enable_profiling: Enable timing profiler (default True)

        Returns:
            {
                "answer": str,
                "sources": List[Dict],
                "source_urls": List[str],
                "context_used": bool,
                "is_emergency": bool,
                "is_crisis": bool,
                "is_sensitive": bool,
                "timings": Dict  # Performance timing breakdown
            }
        """
        # Initialize profiler
        profiler = RequestProfiler() if enable_profiling else None

        sources = []
        source_urls = []
        context = ""
        is_emergency = False
        is_cautious_warning = False
        is_crisis = False
        is_sensitive = False
        emergency_number = "112"

        # Context al (RAG)
        if use_context:
            # search_query belirtilmişse kullan (maskesiz sorgu), yoksa question kullan
            kb_query = search_query if search_query else question
            search_results = self.knowledge_base.search(kb_query, top_k=5, profiler=profiler)

            # Acil durum kontrolü (geliştirilmiş - score threshold)
            emergency_check = self._check_emergency(search_results)
            is_emergency = emergency_check["is_emergency"]
            is_cautious_warning = emergency_check["is_cautious_warning"]
            emergency_number = emergency_check["emergency_number"]

            # Hassas içerik kontrolü (mental health, crisis)
            sensitive_check = self._check_sensitive(search_results)
            is_sensitive = sensitive_check["is_sensitive"]
            is_crisis = sensitive_check["is_crisis"]

            if is_emergency:
                print(f"🚨 [RAG Chain] EMERGENCY detected! Sources: {len(emergency_check['emergency_sources'])}")
            elif is_cautious_warning:
                print(f"⚠️  [RAG Chain] Cautious warning (low score emergency)")
            if is_crisis:
                print(f"💙 [RAG Chain] CRISIS content detected (mental health)")
            elif is_sensitive:
                print(f"🤝 [RAG Chain] Sensitive content detected")

            # Kaynakları hazırla (source_url dahil)
            sources = [
                {
                    "title": r["metadata"].get("title", "Unknown"),
                    "title_tr": r["metadata"].get("title_tr", ""),
                    "source": r["metadata"].get("source", "Medical Database"),
                    "source_url": r["metadata"].get("source_url", ""),
                    "score": r["score"],
                    "category": r["metadata"].get("category", "general"),
                    "safety_level": r["metadata"].get("safety_level", "general")
                }
                for r in search_results
            ]

            # Benzersiz source URL'leri çıkar (boş olmayanlar)
            seen_urls = set()
            for s in sources:
                url = s.get("source_url", "")
                if url and url not in seen_urls:
                    source_urls.append(url)
                    seen_urls.add(url)

            # search_results'ı geç, double search önleme
            # kb_query kullan (maskesiz) - tutarlılık ve debug için
            context = self.knowledge_base.get_context_for_query(kb_query, max_context_tokens, search_results=search_results)

            # Add mask_map hints to context so LLM knows what tokens mean
            if mask_map and context:
                token_hints = []
                for token, mapping in mask_map.items():
                    # Extract English generic name and Turkish brand
                    en_name = mapping.get("en", "")
                    tr_name = mapping.get("tr", "")
                    # Extract just the generic name (before parenthesis)
                    if "(" in en_name:
                        generic = en_name.split("(")[0].strip()
                    else:
                        generic = en_name.strip()
                    # e.g., "MEDTOK0X is a brand name; the generic medication is: paracetamol"
                    token_hints.append(f"{token} is a Turkish brand mention ({tr_name}); generic medication: {generic}")

                if token_hints:
                    hint_section = "\n=== MEDICATION TOKEN MAPPING ===\n"
                    hint_section += "The user's question contains masked medication brand names. Here's what they mean:\n"
                    hint_section += "\n".join(f"• {h}" for h in token_hints)
                    hint_section += "\n\n**CRITICAL**: These tokens represent REAL medications. "
                    hint_section += "Search for the GENERIC name (e.g., 'paracetamol') in the reference information below. "
                    hint_section += "The reference info contains details about the generic medication - use that to answer.\n"
                    hint_section += "================================\n"
                    context = hint_section + context

        # Mesajları hazırla
        messages = []

        # İlk sağlık sorusu mu follow-up mı?
        is_followup = not is_first_health_question

        # Determine response mode and temperature
        response_mode = "normal"
        temperature = 0.7  # Default

        if is_emergency:
            response_mode = "emergency"
            temperature = 0.3  # Lower for safety-critical responses
        elif is_crisis:
            response_mode = "crisis"
            temperature = 0.3  # Lower for sensitive crisis responses
        elif is_sensitive:
            response_mode = "sensitive"
            temperature = 0.5  # Moderate for empathetic responses

        print(f"[RAG Chain] mode={response_mode}, temp={temperature}, is_followup={is_followup}")

        # System prompt based on response mode
        if context:
            if response_mode == "emergency":
                messages.append({
                    "role": "system",
                    "content": self.get_emergency_system_prompt(context, emergency_number)
                })
            elif response_mode == "crisis":
                messages.append({
                    "role": "system",
                    "content": self.get_crisis_system_prompt(context)
                })
            elif response_mode == "sensitive":
                messages.append({
                    "role": "system",
                    "content": self.get_sensitive_system_prompt(context, is_followup=is_followup)
                })
            else:
                messages.append({
                    "role": "system",
                    "content": self.get_rag_system_prompt(context, is_followup=is_followup)
                })
        else:
            messages.append({
                "role": "system",
                "content": """You are a medical assistant. Use SHORT, SIMPLE sentences.
Be helpful but concise. Do NOT diagnose. Recommend seeing a doctor for proper care."""
            })
        
        # Chat history
        if chat_history:
            for msg in chat_history[-6:]:  # Son 6 mesaj
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        # Kullanıcı sorusu
        messages.append({
            "role": "user",
            "content": question
        })
        
        # LLM çağrısı - dynamic temperature based on content type
        try:
            if profiler:
                with profiler.time("t_llm"):
                    response = self.groq_client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=temperature,  # Dynamic: 0.3 for emergency/crisis, 0.5 for sensitive, 0.7 for normal
                        max_tokens=2048
                    )
            else:
                response = self.groq_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=2048
                )
            answer = response.choices[0].message.content
        except Exception as e:
            answer = f"Error generating response: {str(e)}"

        # Log profiling summary
        timings = {}
        if profiler:
            profiler.log_summary("[RAG PERF]")
            timings = profiler.report()

        return {
            "answer": answer,
            "sources": sources,
            "source_urls": source_urls[:3],
            "context_used": bool(context),
            "is_emergency": is_emergency,
            "is_cautious_warning": is_cautious_warning,
            "is_crisis": is_crisis,
            "is_sensitive": is_sensitive,
            "emergency_number": emergency_number if is_emergency else None,
            "response_mode": response_mode,
            "temperature": temperature,
            "model": self.model,
            "timings": timings  # Performance breakdown
        }
    
    def query_with_translation(
        self,
        question_tr: str,
        question_en: str,
        chat_history: Optional[List[Dict]] = None,
        translate_func=None
    ) -> Dict:
        """
        Çeviri pipeline'ı ile RAG query
        
        Args:
            question_tr: Türkçe soru (logging için)
            question_en: İngilizce soru (RAG için)
            chat_history: Mesaj geçmişi
            translate_func: EN->TR çeviri fonksiyonu
        """
        # RAG query (İngilizce)
        result = self.query(question_en, chat_history)
        
        # Cevabı Türkçe'ye çevir
        if translate_func and result["answer"]:
            try:
                result["answer_tr"] = translate_func(result["answer"])
            except Exception as e:
                result["answer_tr"] = result["answer"]
                result["translation_error"] = str(e)
        
        result["question_tr"] = question_tr
        result["question_en"] = question_en
        
        return result


# Singleton
_rag_chain = None

def get_rag_chain() -> RAGChain:
    """Singleton RAG chain instance döndür"""
    global _rag_chain
    if _rag_chain is None:
        _rag_chain = RAGChain()
    return _rag_chain
