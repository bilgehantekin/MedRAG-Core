#!/usr/bin/env python3
"""
RAG System Test Script
RAG sistemini test etmek için basit script
"""

import sys
import os

# Backend path'i ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_rag_system():
    print("=" * 60)
    print("🧪 RAG System Test")
    print("=" * 60)
    
    # 1. Embedding modeli test et
    print("\n📌 1. Embedding Modeli Test Ediliyor...")
    try:
        from app.rag.embeddings import get_embedding_model
        embed_model = get_embedding_model()
        
        test_text = "I have a headache and fever"
        embedding = embed_model.embed_text(test_text)
        
        print(f"   ✅ Model: {embed_model.model_name}")
        print(f"   ✅ Embedding boyutu: {len(embedding)}")
        print(f"   ✅ Test metin: '{test_text}'")
    except Exception as e:
        print(f"   ❌ Embedding hatası: {e}")
        return False
    
    # 2. Knowledge Base yükle
    print("\n📌 2. Knowledge Base Yükleniyor...")
    try:
        from app.rag.knowledge_base import MedicalKnowledgeBase
        kb = MedicalKnowledgeBase()
        count = kb.load_default_knowledge()
        
        stats = kb.get_stats()
        print(f"   ✅ Yüklenen döküman: {count}")
        print(f"   ✅ Kategoriler: {stats['categories']}")
    except Exception as e:
        print(f"   ❌ Knowledge base hatası: {e}")
        return False
    
    # 3. Semantic Search test et
    print("\n📌 3. Semantic Search Test Ediliyor...")
    try:
        test_queries = [
            "I have a headache",
            "chest pain and shortness of breath",
            "what is paracetamol used for"
        ]
        
        for query in test_queries:
            results = kb.search(query, top_k=2)
            print(f"\n   🔍 Query: '{query}'")
            for i, r in enumerate(results, 1):
                print(f"      {i}. {r['metadata'].get('title', 'N/A')} (score: {r['score']:.3f})")
    except Exception as e:
        print(f"   ❌ Search hatası: {e}")
        return False
    
    # 4. RAG Chain test et
    print("\n📌 4. RAG Chain Test Ediliyor...")
    try:
        from app.rag.rag_chain import RAGChain
        rag = RAGChain(knowledge_base=kb)
        
        question = "What should I do for a headache?"
        print(f"   🔍 Soru: '{question}'")
        
        result = rag.query(question, use_context=True)
        
        print(f"   ✅ RAG kullanıldı: {result['context_used']}")
        print(f"   ✅ Kaynak sayısı: {len(result['sources'])}")
        print(f"   ✅ Cevap (ilk 200 karakter): {result['answer'][:200]}...")
    except Exception as e:
        print(f"   ❌ RAG Chain hatası: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✅ Tüm testler başarılı!")
    print("=" * 60)
    
    print("\n📋 Kullanılabilir endpoint'ler:")
    print("   POST /rag/chat     - RAG tabanlı chat")
    print("   POST /rag/search   - Knowledge base arama")
    print("   GET  /rag/stats    - İstatistikler")
    print("   GET  /rag/health   - Sağlık kontrolü")
    print("   POST /rag/reload   - Knowledge base yeniden yükle")
    
    return True


if __name__ == "__main__":
    success = test_rag_system()
    sys.exit(0 if success else 1)
