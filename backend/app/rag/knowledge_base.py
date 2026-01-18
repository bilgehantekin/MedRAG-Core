"""
Medical Knowledge Base Module
Tıbbi bilgi kaynaklarını yönetme ve yükleme
"""

import json
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
        self._loaded_files: set = set()  # Tekrarlı yükleme önleme
    
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

        # JSON format validasyonu
        if not isinstance(data, list):
            raise ValueError(f"JSON root must be a list, got {type(data).__name__}")

        texts = []
        metadatas = []
        ids = []

        for i, item in enumerate(data):
            # Item validasyonu
            if not isinstance(item, dict):
                print(f"⚠️  Skipping item {i}: expected dict, got {type(item).__name__}")
                continue
            # Ana içerik
            text = self._format_document(item)
            texts.append(text)
            
            # Metadata - yeni schema desteği (v3.3+)
            # source_name (yeni) veya source (eski) - backward compatible
            source = item.get("source_name") or item.get("source", "unknown")

            # Tüm keyword'leri birleştir (EN + TR + typos) + dedupe + normalize
            raw_keywords = []
            raw_keywords.extend(item.get("keywords", []))  # Eski format
            raw_keywords.extend(item.get("keywords_en", []))
            raw_keywords.extend(item.get("keywords_tr", []))
            raw_keywords.extend(item.get("typos_tr", []))
            # Normalize: lower + strip, sonra dedupe
            all_keywords = list({kw.lower().strip() for kw in raw_keywords if kw})

            metadata = {
                "title": item.get("title", ""),
                "title_tr": item.get("title_tr", ""),
                "category": item.get("category", "general"),
                "source": source,
                "source_url": item.get("source_url", ""),
                "keywords": all_keywords,
                "jurisdiction": item.get("jurisdiction", "TR"),
                "safety_level": item.get("safety_level", "general"),
                # Ek metadata alanları (v3.3+)
                "severity": item.get("severity", ""),
                "call_emergency": item.get("call_emergency", False),
                "emergency_number": item.get("emergency_number", ""),
                "drug_class": item.get("drug_class", ""),
                "retrieved_date": item.get("retrieved_date", "")
            }
            metadatas.append(metadata)
            self.categories.add(metadata["category"])
            
            # ID
            doc_id = item.get("id", f"{metadata['category']}_{i}")
            ids.append(doc_id)
        
        self.vector_store.add_documents(texts, metadatas, ids)
        return len(texts)
    
    def _format_document(self, item: Dict) -> str:
        """Dökümanı arama için optimize edilmiş formata çevir (v3.3+ schema)"""
        parts = []

        # === TEMEL BİLGİLER ===
        if item.get("title"):
            title = item['title']
            if item.get("title_tr"):
                title += f" / {item['title_tr']}"
            parts.append(f"Title: {title}")

        if item.get("category"):
            parts.append(f"Category: {item['category']}")

        if item.get("content"):
            parts.append(f"Content: {item['content']}")

        # === ACİL DURUM ALANLARI ===
        if item.get("severity"):
            parts.append(f"Severity: {item['severity']}")

        if item.get("call_emergency"):
            emergency_num = item.get("emergency_number", "112")
            parts.append(f"EMERGENCY: Call {emergency_num} immediately")

        if item.get("time_critical"):
            parts.append(f"Time critical: {item['time_critical']}")

        # Acil durum özel notları
        if item.get("aspirin_safety_note"):
            parts.append(f"Aspirin safety: {item['aspirin_safety_note']}")

        if item.get("shock_warning"):
            parts.append(f"Shock warning: {item['shock_warning']}")

        if item.get("asthma_note"):
            parts.append(f"Asthma guidance: {item['asthma_note']}")

        if item.get("epipen_note"):
            parts.append(f"EpiPen guidance: {item['epipen_note']}")

        if item.get("after_seizure"):
            parts.append(f"After seizure: {item['after_seizure']}")

        if item.get("bring_to_hospital"):
            parts.append(f"Bring to hospital: {item['bring_to_hospital']}")

        # Ek acil durum alanları
        if item.get("call_112_if"):
            parts.append(f"Call 112 if: {', '.join(item['call_112_if'])}")

        if item.get("fast_test"):
            parts.append(f"FAST test: {item['fast_test']}")

        if item.get("cpr_basics"):
            parts.append(f"CPR basics: {item['cpr_basics']}")

        if item.get("recovery_position"):
            parts.append(f"Recovery position: {item['recovery_position']}")

        if item.get("common_triggers"):
            parts.append(f"Common triggers: {', '.join(item['common_triggers'])}")

        if item.get("asthma_source"):
            parts.append(f"Asthma source: {item['asthma_source']}")

        # === SEMPTOM/HASTALIK ALANLARI ===
        if item.get("symptoms"):
            parts.append(f"Symptoms: {', '.join(item['symptoms'])}")

        if item.get("causes"):
            parts.append(f"Causes: {', '.join(item['causes'])}")

        if item.get("treatments"):
            parts.append(f"Treatments: {', '.join(item['treatments'])}")

        if item.get("what_to_do"):
            parts.append(f"What to do: {', '.join(item['what_to_do'])}")

        if item.get("do_not"):
            parts.append(f"Do not: {', '.join(item['do_not'])}")

        if item.get("red_flags"):
            parts.append(f"Red flags (seek emergency): {', '.join(item['red_flags'])}")

        if item.get("when_to_see_doctor"):
            parts.append(f"When to see a doctor: {item['when_to_see_doctor']}")

        if item.get("crisis_info"):
            parts.append(f"Crisis info: {item['crisis_info']}")

        # === İLAÇ ALANLARI ===
        if item.get("drug_class"):
            parts.append(f"Drug class: {item['drug_class']}")

        if item.get("uses"):
            parts.append(f"Uses: {', '.join(item['uses'])}")

        if item.get("dosage_info"):
            dosage = item["dosage_info"]
            if isinstance(dosage, dict):
                dosage_parts = [f"{k}: {v}" for k, v in dosage.items()]
                parts.append(f"Dosage: {'; '.join(dosage_parts)}")
            else:
                parts.append(f"Dosage: {dosage}")

        if item.get("side_effects"):
            parts.append(f"Side effects: {', '.join(item['side_effects'])}")

        if item.get("contraindications"):
            parts.append(f"Contraindications: {', '.join(item['contraindications'])}")

        if item.get("warnings"):
            parts.append(f"Warnings: {', '.join(item['warnings'])}")

        if item.get("drug_interactions"):
            parts.append(f"Drug interactions: {', '.join(item['drug_interactions'])}")

        if item.get("overdose_warning"):
            parts.append(f"Overdose warning: {item['overdose_warning']}")

        if item.get("safety_disclaimer"):
            parts.append(f"Safety disclaimer: {item['safety_disclaimer']}")

        if item.get("emergency_use_note"):
            parts.append(f"Emergency use note: {item['emergency_use_note']}")

        if item.get("rebound_warning"):
            parts.append(f"Rebound warning: {item['rebound_warning']}")

        if item.get("brand_examples_tr"):
            parts.append(f"Turkish brands (örnek): {', '.join(item['brand_examples_tr'])}")

        # === KEYWORD'LER (arama kalitesi için) ===
        all_keywords = []
        all_keywords.extend(item.get("keywords", []))
        all_keywords.extend(item.get("keywords_en", []))
        all_keywords.extend(item.get("keywords_tr", []))
        all_keywords.extend(item.get("typos_tr", []))
        if all_keywords:
            parts.append(f"Related terms: {', '.join(all_keywords)}")

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
            # Tekrarlı yükleme kontrolü
            file_key = str(json_file.resolve())
            if file_key in self._loaded_files:
                print(f"ℹ️  {json_file.name}: zaten yüklendi, atlanıyor")
                continue

            try:
                count = self.load_from_json(str(json_file))
                self._loaded_files.add(file_key)
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
