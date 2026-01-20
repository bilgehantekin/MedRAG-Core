"""
Medical Knowledge Base Module
Tıbbi bilgi kaynaklarını yönetme ve yükleme
"""

import json
import unicodedata
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from app.rag.vector_store import VectorStore

# Chunking constants
MAX_CHUNK_CHARS = 1500  # ~375 tokens (approx 4 chars/token)
CHUNK_OVERLAP_CHARS = 200  # Overlap between chunks
MAX_RELATED_TERMS = 30  # Limit keywords in document text


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

    def _to_bool(self, v) -> bool:
        """
        Güvenli bool dönüşümü: string "false", int 0, None vb. doğru handle et
        """
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v != 0
        if isinstance(v, str):
            s = v.strip().lower()
            if s in {"true", "1", "yes", "y", "evet"}:
                return True
            if s in {"false", "0", "no", "n", "hayır", "hayir", ""}:
                return False
        return False

    def _normalize_text(self, text: str) -> str:
        """
        Türkçe-safe metin normalizasyonu: casefold + NFKC unicode normalize
        Bu, İ/i ve diğer unicode sorunlarını önler
        """
        # NFKC: Uyumluluk dönüşümü (kombine karakterleri birleştirir)
        normalized = unicodedata.normalize('NFKC', text)
        # casefold: lower() yerine - Türkçe İ→i, Almanca ß→ss vb. doğru handle eder
        return normalized.casefold().strip()

    def _normalize_keywords(self, raw_keywords: List) -> List[str]:
        """
        Keyword listesini normalize et: non-str filtrele, casefold/strip, dedupe, sırayı koru
        """
        out = []
        seen = set()
        for kw in raw_keywords:
            if not isinstance(kw, str):
                continue
            k = self._normalize_text(kw)
            if not k or k in seen:
                continue
            seen.add(k)
            out.append(k)
        return out
    
    def _chunk_text(self, text: str, doc_id: str) -> List[Tuple[str, str]]:
        """
        Uzun metni chunk'lara böl

        Args:
            text: Bölünecek metin
            doc_id: Parent doküman ID'si

        Returns:
            List of (chunk_text, chunk_id) tuples
        """
        if len(text) <= MAX_CHUNK_CHARS:
            return [(text, doc_id)]

        chunks = []
        start = 0
        chunk_num = 0

        while start < len(text):
            end = start + MAX_CHUNK_CHARS

            # Chunk sınırını cümle/paragraf sonuna denk getirmeye çalış
            if end < len(text):
                # Önce paragraf sonu ara
                newline_pos = text.rfind('\n', start + MAX_CHUNK_CHARS // 2, end)
                if newline_pos > start:
                    end = newline_pos + 1
                else:
                    # Cümle sonu ara
                    for sep in ['. ', '! ', '? ', '; ']:
                        sep_pos = text.rfind(sep, start + MAX_CHUNK_CHARS // 2, end)
                        if sep_pos > start:
                            end = sep_pos + len(sep)
                            break

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk_id = f"{doc_id}_chunk{chunk_num}" if chunk_num > 0 else doc_id
                chunks.append((chunk_text, chunk_id))
                chunk_num += 1

            # Overlap ile sonraki chunk'a geç
            start = end - CHUNK_OVERLAP_CHARS if end < len(text) else len(text)

        return chunks

    def load_from_json(self, file_path: str) -> int:
        """
        JSON dosyasından tıbbi bilgi yükle

        Features:
        - Uzun içerikleri chunk'lara böler
        - File prefix ile ID çakışmasını önler
        - Türkçe-safe keyword normalizasyonu

        Returns:
            Yüklenen döküman sayısı
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # JSON format validasyonu
        if not isinstance(data, list):
            raise ValueError(f"JSON root must be a list, got {type(data).__name__}")

        # File prefix for ID collision prevention
        file_name = Path(file_path).stem  # e.g., "emergency" from "emergency.json"

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

            # Metadata - yeni schema desteği (v3.3+)
            source = item.get("source_name") or item.get("source", "unknown")

            # Tüm keyword'leri birleştir (EN + TR + typos) + dedupe + normalize
            raw_keywords = []
            raw_keywords.extend(item.get("keywords") or [])
            raw_keywords.extend(item.get("keywords_en") or [])
            raw_keywords.extend(item.get("keywords_tr") or [])
            raw_keywords.extend(item.get("typos_tr") or [])
            all_keywords = self._normalize_keywords(raw_keywords)

            metadata = {
                "title": item.get("title", ""),
                "title_tr": item.get("title_tr", ""),
                "category": item.get("category", "general"),
                "source": source,
                "source_url": item.get("source_url", ""),
                "keywords": all_keywords,
                "jurisdiction": item.get("jurisdiction", "TR"),
                "safety_level": item.get("safety_level", "general"),
                "severity": item.get("severity", ""),
                "call_emergency": self._to_bool(item.get("call_emergency", False)),
                "emergency_number": item.get("emergency_number", ""),
                "drug_class": item.get("drug_class", ""),
                "retrieved_date": item.get("retrieved_date", "")
            }
            self.categories.add(metadata["category"])

            # ID with file prefix to prevent collision
            base_id = item.get("id")
            if not base_id:
                base_id = f"{file_name}_{metadata['category']}_{i}"

            # Chunk long documents
            chunks = self._chunk_text(text, base_id)

            for chunk_text, chunk_id in chunks:
                texts.append(chunk_text)
                # Chunk metadata includes parent info
                chunk_metadata = metadata.copy()
                if len(chunks) > 1:
                    chunk_metadata["parent_id"] = base_id
                    chunk_metadata["is_chunk"] = True
                metadatas.append(chunk_metadata)
                ids.append(chunk_id)

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

        if self._to_bool(item.get("call_emergency", False)):
            emergency_num = item.get("emergency_number") or "112"
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
        val = item.get("call_112_if")
        if isinstance(val, list) and val:
            parts.append(f"Call 112 if: {', '.join(str(x) for x in val)}")

        if item.get("fast_test"):
            val = item["fast_test"]
            if isinstance(val, dict):
                parts.append(f"FAST test: {' | '.join(f'{k}: {v}' for k, v in val.items())}")
            elif isinstance(val, list):
                parts.append(f"FAST test: {'; '.join(str(v) for v in val)}")
            else:
                parts.append(f"FAST test: {val}")

        if item.get("cpr_basics"):
            val = item["cpr_basics"]
            if isinstance(val, dict):
                parts.append(f"CPR basics: {' | '.join(f'{k}: {v}' for k, v in val.items())}")
            elif isinstance(val, list):
                parts.append(f"CPR basics: {'; '.join(str(v) for v in val)}")
            else:
                parts.append(f"CPR basics: {val}")

        if item.get("recovery_position"):
            val = item["recovery_position"]
            if isinstance(val, dict):
                parts.append(f"Recovery position: {' | '.join(f'{k}: {v}' for k, v in val.items())}")
            elif isinstance(val, list):
                parts.append(f"Recovery position: {'; '.join(str(v) for v in val)}")
            else:
                parts.append(f"Recovery position: {val}")

        val = item.get("common_triggers")
        if isinstance(val, list) and val:
            parts.append(f"Common triggers: {', '.join(str(x) for x in val)}")

        if item.get("asthma_source"):
            parts.append(f"Asthma source: {item['asthma_source']}")

        # === SEMPTOM/HASTALIK ALANLARI ===
        val = item.get("symptoms")
        if isinstance(val, list) and val:
            parts.append(f"Symptoms: {', '.join(str(x) for x in val)}")

        val = item.get("causes")
        if isinstance(val, list) and val:
            parts.append(f"Causes: {', '.join(str(x) for x in val)}")

        val = item.get("treatments")
        if isinstance(val, list) and val:
            parts.append(f"Treatments: {', '.join(str(x) for x in val)}")

        val = item.get("what_to_do")
        if isinstance(val, list) and val:
            parts.append(f"What to do: {', '.join(str(x) for x in val)}")

        val = item.get("do_not")
        if isinstance(val, list) and val:
            parts.append(f"Do not: {', '.join(str(x) for x in val)}")

        val = item.get("red_flags")
        if isinstance(val, list) and val:
            parts.append(f"Red flags (seek emergency): {', '.join(str(x) for x in val)}")

        if item.get("when_to_see_doctor"):
            parts.append(f"When to see a doctor: {item['when_to_see_doctor']}")

        if item.get("crisis_info"):
            parts.append(f"Crisis info: {item['crisis_info']}")

        # === İLAÇ ALANLARI ===
        if item.get("drug_class"):
            parts.append(f"Drug class: {item['drug_class']}")

        val = item.get("uses")
        if isinstance(val, list) and val:
            parts.append(f"Uses: {', '.join(str(x) for x in val)}")

        if item.get("dosage_info"):
            dosage = item["dosage_info"]
            if isinstance(dosage, dict):
                dosage_parts = [f"{k}: {v}" for k, v in dosage.items()]
                parts.append(f"Dosage: {'; '.join(dosage_parts)}")
            else:
                parts.append(f"Dosage: {dosage}")

        val = item.get("side_effects")
        if isinstance(val, list) and val:
            parts.append(f"Side effects: {', '.join(str(x) for x in val)}")

        val = item.get("contraindications")
        if isinstance(val, list) and val:
            parts.append(f"Contraindications: {', '.join(str(x) for x in val)}")

        val = item.get("warnings")
        if isinstance(val, list) and val:
            parts.append(f"Warnings: {', '.join(str(x) for x in val)}")

        val = item.get("drug_interactions")
        if isinstance(val, list) and val:
            parts.append(f"Drug interactions: {', '.join(str(x) for x in val)}")

        if item.get("overdose_warning"):
            parts.append(f"Overdose warning: {item['overdose_warning']}")

        if item.get("safety_disclaimer"):
            parts.append(f"Safety disclaimer: {item['safety_disclaimer']}")

        if item.get("emergency_use_note"):
            parts.append(f"Emergency use note: {item['emergency_use_note']}")

        if item.get("rebound_warning"):
            parts.append(f"Rebound warning: {item['rebound_warning']}")

        val = item.get("brand_examples_tr")
        if isinstance(val, list) and val:
            parts.append(f"Turkish brands (örnek): {', '.join(str(x) for x in val)}")

        # === KEYWORD'LER (arama kalitesi için) ===
        # `or []` ile null değerler handle edilir
        raw_keywords = []
        raw_keywords.extend(item.get("keywords") or [])
        raw_keywords.extend(item.get("keywords_en") or [])
        raw_keywords.extend(item.get("keywords_tr") or [])
        raw_keywords.extend(item.get("typos_tr") or [])
        normalized_keywords = self._normalize_keywords(raw_keywords)
        # Limit related terms to prevent embedding noise
        if normalized_keywords:
            limited_keywords = normalized_keywords[:MAX_RELATED_TERMS]
            parts.append(f"Related terms: {', '.join(limited_keywords)}")

        return "\n".join(parts)
    
    def load_default_knowledge(self) -> int:
        """
        Varsayılan tıbbi bilgi tabanını yükle

        Yükleme stratejisi:
        - emergency.json: Acil durum verileri (el yapımı, kaliteli)
        - medications.json: İlaç verileri (el yapımı, kaliteli)
        - symptoms_diseases_medlineplus_tr_enriched.json: MedlinePlus verileri (ETL + TR zenginleştirme)

        Atlanacak dosyalar:
        - symptoms_diseases.json: Eski el yapımı veri (enriched ile değiştirildi)
        - *_medlineplus.json (enriched hariç): Ara dosyalar
        - *_clean_en.json: Ara dosyalar
        """
        if not self.data_dir.exists():
            print(f"⚠️  Veri klasörü bulunamadı: {self.data_dir}")
            return 0

        # Yüklenecek dosyalar (öncelik sırasına göre)
        files_to_load = [
            "emergency.json",
            "medications.json",
            "symptoms_diseases_medlineplus_tr_enriched.json",
        ]

        # Fallback: Eğer enriched dosya yoksa, orijinal curated dosyayı yükle
        enriched_file = self.data_dir / "symptoms_diseases_medlineplus_tr_enriched.json"
        if not enriched_file.exists():
            print("ℹ️  Enriched dosya bulunamadı, orijinal symptoms_diseases.json yüklenecek")
            files_to_load.append("symptoms_diseases.json")

        total_loaded = 0
        for filename in files_to_load:
            json_file = self.data_dir / filename

            if not json_file.exists():
                print(f"⚠️  {filename}: dosya bulunamadı, atlanıyor")
                continue

            # Tekrarlı yükleme kontrolü
            file_key = str(json_file.resolve())
            if file_key in self._loaded_files:
                print(f"ℹ️  {filename}: zaten yüklendi, atlanıyor")
                continue

            try:
                count = self.load_from_json(str(json_file))
                self._loaded_files.add(file_key)
                print(f"📚 {filename}: {count} döküman yüklendi")
                total_loaded += count
            except Exception as e:
                print(f"❌ {filename} yüklenemedi: {e}")

        return total_loaded
    
    def _keyword_search(self, query_terms: set, top_k: int = 10) -> List[Dict]:
        """
        Keyword-based document retrieval from stored metadata.
        Finds documents where query terms match stored keywords.
        """
        matches = []

        # Search through all stored documents
        for doc in self.vector_store.documents:
            metadata = doc.get("metadata", {})
            keywords = metadata.get("keywords", [])

            if not keywords:
                continue

            # Normalize keywords
            keywords_normalized = set()
            for kw in keywords:
                if isinstance(kw, str):
                    keywords_normalized.add(self._normalize_text(kw))

            # Check for matches
            match_score = 0
            for qt in query_terms:
                if qt in keywords_normalized:
                    match_score += 2  # Exact match
                else:
                    for kw in keywords_normalized:
                        if qt in kw:
                            match_score += 1
                            break

            if match_score > 0:
                matches.append({
                    "text": doc.get("text", ""),
                    "metadata": metadata,
                    "score": 0.5 - (match_score * 0.1),  # Convert to distance-like score (lower is better)
                    "keyword_matched": True,
                    "id": doc.get("id", "")
                })

        # Sort by match score and return top_k
        matches.sort(key=lambda x: x["score"])
        return matches[:top_k]

    def search(self, query: str, top_k: int = 5, category: Optional[str] = None) -> List[Dict]:
        """
        Hybrid search: Vector similarity + keyword retrieval

        Sentence-transformers may not understand brand names (e.g., "Calpol").
        We combine vector search with keyword-based retrieval to improve recall.

        Args:
            query: Arama sorgusu (İngilizce veya Türkçe)
            top_k: Döndürülecek sonuç sayısı
            category: Belirli bir kategoride ara (symptoms, diseases, etc.)
        """
        # Normalize query for keyword matching
        query_normalized = self._normalize_text(query)
        query_terms = set(query_normalized.split())
        # Filter out common stop words (Turkish + English)
        # "drug/drugs" is too generic - matches "Drugs and Young People" etc.
        stop_words = {"bir", "bu", "ile", "için", "ve", "de", "da", "ne", "nasıl",
                      "hakkında", "bilgi", "nedir", "the", "a", "an", "is", "what",
                      "how", "about", "ilacı", "ilaç", "alabilir", "miyim", "var",
                      "drug", "drugs", "medicine", "medication", "can", "you", "give",
                      "information", "tell", "me"}
        meaningful_terms = {t for t in query_terms if t not in stop_words and len(t) >= 3}

        # 1. Vector search
        fetch_k = max(top_k * 2, 10)
        vector_results = self.vector_store.search(query, top_k=fetch_k)

        # 2. Keyword search (if we have meaningful terms)
        keyword_results = []
        if meaningful_terms:
            keyword_results = self._keyword_search(meaningful_terms, top_k=top_k)

        # 3. Merge results, prioritizing keyword matches
        # doc_id ile dedupe - text[:200] chunking sonrası hatalı olabilir
        seen_ids = set()
        merged = []

        # Add keyword matches first (they're more relevant for brand name queries)
        for r in keyword_results:
            doc_id = r.get("id", "")
            if not doc_id:
                # Fallback: text hash kullan
                doc_id = hash(r["text"][:500])
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                merged.append(r)

        # Add vector results
        for r in vector_results:
            doc_id = r.get("id", "")
            if not doc_id:
                doc_id = hash(r["text"][:500])
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                merged.append(r)

        # Sort by score
        merged.sort(key=lambda x: x.get("score", float("inf")))

        # Kategori filtresi
        if category:
            merged = [r for r in merged if r["metadata"].get("category") == category]

        return merged[:top_k]
    
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
