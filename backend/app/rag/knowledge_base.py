"""
Medical Knowledge Base Module
Tıbbi bilgi kaynaklarını yönetme ve yükleme
"""

import json
import os
from typing import List, Dict, Optional
from pathlib import Path

from app.rag.vector_store import VectorStore


class MedicalKnowledgeBase:
    """
    Tıbbi bilgi tabanı yöneticisi
    - JSON formatında tıbbi bilgileri yükler
    - Kategorize eder
    - Vector store'a aktarır
    """
    
    def __init__(self, vector_store: Optional[VectorStore] = None):
        """
        Args:
            vector_store: Kullanılacak vector store (None ise yeni oluşturulur)
        """
        self.vector_store = vector_store or VectorStore()
        self.data_dir = Path(__file__).parent.parent.parent / "data" / "medical_knowledge"
        self.categories = set()
    
    def load_from_json(self, file_path: str) -> int:
        """
        JSON dosyasından tıbbi bilgi yükle
        
        Expected format:
        [
            {
                "title": "Headache",
                "category": "symptoms",
                "content": "A headache is pain in any region of the head...",
                "source": "MedlinePlus",
                "keywords": ["head pain", "migraine", "tension headache"]
            }
        ]
        
        Returns:
            Yüklenen döküman sayısı
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        texts = []
        metadatas = []
        ids = []
        
        for i, item in enumerate(data):
            # Ana içerik
            text = self._format_document(item)
            texts.append(text)
            
            # Metadata
            metadata = {
                "title": item.get("title", ""),
                "category": item.get("category", "general"),
                "source": item.get("source", "unknown"),
                "keywords": item.get("keywords", [])
            }
            metadatas.append(metadata)
            self.categories.add(metadata["category"])
            
            # ID
            doc_id = item.get("id", f"{metadata['category']}_{i}")
            ids.append(doc_id)
        
        self.vector_store.add_documents(texts, metadatas, ids)
        return len(texts)
    
    def _format_document(self, item: Dict) -> str:
        """Dökümanı arama için optimize edilmiş formata çevir"""
        parts = []
        
        if item.get("title"):
            parts.append(f"Title: {item['title']}")
        
        if item.get("category"):
            parts.append(f"Category: {item['category']}")
        
        if item.get("content"):
            parts.append(f"Content: {item['content']}")
        
        if item.get("symptoms"):
            parts.append(f"Symptoms: {', '.join(item['symptoms'])}")
        
        if item.get("causes"):
            parts.append(f"Causes: {', '.join(item['causes'])}")
        
        if item.get("treatments"):
            parts.append(f"Treatments: {', '.join(item['treatments'])}")
        
        if item.get("when_to_see_doctor"):
            parts.append(f"When to see a doctor: {item['when_to_see_doctor']}")
        
        if item.get("keywords"):
            parts.append(f"Related terms: {', '.join(item['keywords'])}")
        
        return "\n".join(parts)
    
    def load_default_knowledge(self) -> int:
        """
        Varsayılan tıbbi bilgi tabanını yükle
        data/medical_knowledge/ klasöründeki tüm JSON dosyalarını yükler
        """
        if not self.data_dir.exists():
            print(f"⚠️  Veri klasörü bulunamadı: {self.data_dir}")
            return 0
        
        total_loaded = 0
        for json_file in self.data_dir.glob("*.json"):
            try:
                count = self.load_from_json(str(json_file))
                print(f"📚 {json_file.name}: {count} döküman yüklendi")
                total_loaded += count
            except Exception as e:
                print(f"❌ {json_file.name} yüklenemedi: {e}")
        
        return total_loaded
    
    def search(self, query: str, top_k: int = 5, category: Optional[str] = None) -> List[Dict]:
        """
        Bilgi tabanında arama yap
        
        Args:
            query: Arama sorgusu (İngilizce)
            top_k: Döndürülecek sonuç sayısı
            category: Belirli bir kategoride ara (symptoms, diseases, etc.)
        """
        results = self.vector_store.search(query, top_k=top_k * 2 if category else top_k)
        
        # Kategori filtresi
        if category:
            results = [r for r in results if r["metadata"].get("category") == category]
            results = results[:top_k]
        
        return results
    
    def get_context_for_query(self, query: str, max_tokens: int = 2500, search_results: Optional[List[Dict]] = None) -> str:
        """
        Sorgu için LLM'e verilecek context oluştur

        Args:
            query: Kullanıcı sorusu
            max_tokens: Yaklaşık maksimum token (karakter/4 hesabı)
            search_results: Önceden hesaplanmış arama sonuçları (double search önleme)
        """
        # Eğer önceden hesaplanmış sonuçlar verilmediyse, arama yap
        results = search_results if search_results is not None else self.search(query, top_k=5)

        if not results:
            return ""

        context_parts = []
        char_count = 0
        max_chars = max_tokens * 4  # Yaklaşık token hesabı

        for i, result in enumerate(results, 1):
            # Yapılandırılmış format - LLM'in kullanması kolay
            entry = f"\n[RELEVANT MEDICAL INFO #{i}]\n"
            entry += result['text']
            entry += "\n---"

            if char_count + len(entry) > max_chars:
                break

            context_parts.append(entry)
            char_count += len(entry)

        return "\n".join(context_parts)
    
    def save(self, path: Optional[str] = None) -> None:
        """Vector store'u kaydet"""
        save_path = path or str(self.data_dir / "vector_index")
        self.vector_store.save(save_path)
    
    def get_stats(self) -> Dict:
        """İstatistikleri döndür"""
        return {
            "total_documents": len(self.vector_store),
            "categories": list(self.categories),
            "vector_store": self.vector_store.get_stats()
        }


# Singleton instance
_knowledge_base = None

def get_knowledge_base() -> MedicalKnowledgeBase:
    """Singleton knowledge base instance döndür"""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = MedicalKnowledgeBase()
        _knowledge_base.load_default_knowledge()
    return _knowledge_base
