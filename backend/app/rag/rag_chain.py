"""
RAG Chain Module
Retrieval-Augmented Generation pipeline
"""

import os
from typing import Optional, List, Dict
from groq import Groq
from dotenv import load_dotenv
from pathlib import Path

from app.rag.knowledge_base import MedicalKnowledgeBase, get_knowledge_base

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
    
    def query(
        self,
        question: str,
        chat_history: Optional[List[Dict]] = None,
        use_context: bool = True,
        max_context_tokens: int = 2500,
        is_first_health_question: bool = True
    ) -> Dict:
        """
        RAG query yap

        Args:
            question: Kullanıcı sorusu (İngilizce)
            chat_history: Önceki mesajlar
            use_context: Context kullanılsın mı (False = normal LLM)
            max_context_tokens: Context için maksimum token
            is_first_health_question: İlk sağlık sorusu mu? (True = detaylı, False = kısa)

        Returns:
            {
                "answer": str,
                "sources": List[Dict],
                "context_used": bool
            }
        """
        sources = []
        context = ""

        # Context al (RAG)
        if use_context:
            search_results = self.knowledge_base.search(question, top_k=5)
            sources = [
                {
                    "title": r["metadata"].get("title", "Unknown"),
                    "source": r["metadata"].get("source", "Medical Database"),
                    "score": r["score"],
                    "category": r["metadata"].get("category", "general")
                }
                for r in search_results
            ]
            # search_results'ı geç, double search önleme
            context = self.knowledge_base.get_context_for_query(question, max_context_tokens, search_results=search_results)

        # Mesajları hazırla
        messages = []

        # İlk sağlık sorusu mu follow-up mı? (router'dan gelen değeri kullan)
        is_followup = not is_first_health_question
        print(f"[RAG Chain] is_followup={is_followup}, is_first_health_question={is_first_health_question}")

        # System prompt
        if context:
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
        
        # LLM çağrısı
        try:
            response = self.groq_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,  # Normal chat ile aynı
                max_tokens=2048   # Normal chat ile aynı - daha uzun yanıtlar için
            )
            answer = response.choices[0].message.content
        except Exception as e:
            answer = f"Error generating response: {str(e)}"
        
        return {
            "answer": answer,
            "sources": sources,
            "context_used": bool(context),
            "model": self.model
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
