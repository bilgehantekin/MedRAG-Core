"""
Medical Knowledge Base Module
Tıbbi bilgi kaynaklarını yönetme ve yükleme

Performance Optimizations:
- Category pre-filtering for faster search
- Retrieval result caching
- Profiling support
"""

import json
import unicodedata
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from app.rag.vector_store import VectorStore
from app.rag.performance import (
    RequestProfiler,
    get_retrieval_cache,
    predict_category
)

# Chunking constants
MAX_CHUNK_CHARS = 1500  # ~375 tokens (approx 4 chars/token)
CHUNK_OVERLAP_CHARS = 200  # Overlap between chunks
MAX_RELATED_TERMS = 30  # Limit keywords in document text

# OpenFDA 3-doküman formatı için hedef boyutlar
OPENFDA_TARGET_CHARS = 1000  # 900-1400 arası hedef
OPENFDA_MAX_CHARS = 1400
OPENFDA_MIN_CHARS = 300


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
        self.data_dir = Path(__file__).parent.parent.parent / "data" / "medical_knowledge"
        self.categories = set()
        self._loaded_files: set = set()  # Tekrarlı yükleme önleme
        self._tr_drug_allowlist: set = set()  # TR'de geçerli ilaç isimleri

        # Vector store - kaydedilmiş index varsa oradan yükle
        if vector_store:
            self.vector_store = vector_store
        else:
            index_dir = self.data_dir / "vector_index"
            if index_dir.exists():
                self.vector_store = VectorStore(index_path=str(index_dir))
            else:
                self.vector_store = VectorStore()

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

    def _smart_truncate(self, text: str, max_len: int, min_len: int = 0) -> str:
        """
        Metni akıllıca kırp - kelime/cümle sınırlarına dikkat et.
        Asla kelime ortasında kesme!

        Args:
            text: Kırpılacak metin
            max_len: Maksimum uzunluk
            min_len: Minimum uzunluk (bu kadar karakter kesin korunacak)
        """
        if not text or len(text) <= max_len:
            return text

        # min_len'e kadar korunacak, sonra kesim noktası arayacağız
        search_start = max(min_len, max_len - 100)  # Son 100 karakterde ara
        truncated = text[:max_len]

        # 1. Önce cümle sonu ara (. ! ?)
        for punct in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
            last_punct = truncated.rfind(punct, search_start)
            if last_punct > search_start:
                return truncated[:last_punct + 1].rstrip()

        # 2. Virgül veya noktalı virgül ara
        for punct in [', ', '; ', ',\n', ';\n']:
            last_punct = truncated.rfind(punct, search_start)
            if last_punct > search_start:
                return truncated[:last_punct + 1].rstrip()

        # 3. Son çare: boşluk (kelime sınırı) ara
        last_space = truncated.rfind(' ', search_start)
        if last_space > search_start:
            return truncated[:last_space].rstrip()

        # 4. Hiçbiri yoksa, en son boşluğu bul
        last_space = truncated.rfind(' ')
        if last_space > min_len:
            return truncated[:last_space].rstrip()

        # 5. Boşluk bile yoksa mecburen kes (nadir durum)
        return truncated.rstrip()

    def _smart_truncate_item(self, item: str, max_len: int) -> str:
        """Liste öğesi için akıllı truncate - kelime sınırında kes"""
        if not item or len(item) <= max_len:
            return item
        return self._smart_truncate(item, max_len, min_len=max_len // 2)

    def _clean_list_items(self, items: List, max_items: int = 10, max_item_len: int = 200) -> List[str]:
        """Liste öğelerini temizle ve kırp - akıllı truncate ile"""
        if not items:
            return []

        cleaned = []
        seen = set()

        for item in items[:max_items * 2]:
            if not isinstance(item, str):
                continue

            # Temel temizlik
            item = item.strip()
            if len(item) < 10:
                continue

            # Table satırlarını temizle
            if item.lower().startswith('table ') and len(item) > 100:
                # Sadece table başlığını al
                import re
                match = re.match(r'^(Table\s+\d+[:\s]*[^:]+)', item, re.IGNORECASE)
                if match:
                    item = match.group(1).strip()
                else:
                    continue  # Çok uzun table satırını atla

            # Akıllı truncate
            item = self._smart_truncate_item(item, max_item_len)

            # Duplicate kontrolü
            item_key = item.lower()[:50]
            if item_key in seen:
                continue
            seen.add(item_key)

            cleaned.append(item)
            if len(cleaned) >= max_items:
                break

        return cleaned

    def _create_openfda_overview(self, med: Dict) -> Dict:
        """OpenFDA ilaç kaydından overview dokümanı oluştur"""
        title = med.get('title', '')
        parent_id = med.get('id', '')

        parts = [f"# {title}"]

        # Drug class
        if med.get('drug_class'):
            parts.append(f"İlaç sınıfı: {med['drug_class']}")

        # Uses (max 6)
        uses = self._clean_list_items(med.get('uses', []), max_items=6, max_item_len=180)
        if uses:
            parts.append("\n## Ne İşe Yarar")
            for use in uses:
                parts.append(f"• {use}")

        # Content özeti (varsa ve uses yoksa)
        content = med.get('content', '')
        if content and not uses:
            content_short = self._smart_truncate(content, 300, 100)
            parts.append(f"\n{content_short}")

        # Önemli limitler (warnings'da "not indicated" veya "prn" geçiyorsa)
        warnings = med.get('warnings', [])
        if isinstance(warnings, list):
            limitations = []
            for w in warnings:
                if isinstance(w, str):
                    w_lower = w.lower()
                    if 'not indicated' in w_lower or 'not for' in w_lower or 'prn' in w_lower:
                        limitations.append(w)

            if limitations:
                parts.append("\n## Önemli Uyarı")
                for lim in limitations[:2]:
                    lim_short = self._smart_truncate_item(lim, 150)
                    parts.append(f"⚠️ {lim_short}")

        full_content = '\n'.join(parts)
        full_content = self._smart_truncate(full_content, OPENFDA_MAX_CHARS, OPENFDA_MIN_CHARS)

        return {
            'id': f"{parent_id}_overview",
            'parent_id': parent_id,
            'section': 'overview',
            'title': title,
            'title_tr': f"{title} - Genel Bilgi",
            'category': 'medications',
            'content': full_content,
            'keywords_en': med.get('keywords_en', []),
            'keywords_tr': med.get('keywords_tr', []) + ['nedir', 'ne işe yarar', 'kullanım alanları'],
            'typos_tr': med.get('typos_tr', []),
            'brand_examples_tr': med.get('brand_examples_tr', []),
            'source_name': med.get('source_name', 'openFDA'),
            'source_url': med.get('source_url', ''),
            'drug_class': med.get('drug_class', ''),
        }

    def _create_openfda_safety(self, med: Dict) -> Optional[Dict]:
        """OpenFDA ilaç kaydından safety dokümanı oluştur"""
        title = med.get('title', '')
        parent_id = med.get('id', '')

        parts = [f"# {title} - Güvenlik Bilgileri"]
        has_content = False

        # Warnings (max 8, boxed öncelikli)
        warnings = med.get('warnings', [])
        if isinstance(warnings, list) and warnings:
            has_content = True
            parts.append("\n## Uyarılar")

            # Boxed warning'ları öne al
            boxed = [w for w in warnings if isinstance(w, str) and ('boxed' in w.lower() or w.lower().startswith('warning:'))]
            other = [w for w in warnings if isinstance(w, str) and w not in boxed]

            sorted_warnings = boxed + other
            cleaned_warnings = self._clean_list_items(sorted_warnings, max_items=8, max_item_len=220)
            for w in cleaned_warnings:
                prefix = "⚠️ " if any(w in boxed for w in [w]) else "• "
                parts.append(f"{prefix}{w}")

        # Contraindications (max 6)
        contras = med.get('contraindications', [])
        if isinstance(contras, list):
            # "None" placeholder'larını filtrele
            contras = [c for c in contras if isinstance(c, str) and 'none' not in c.lower()[:10]]
            if contras:
                has_content = True
                parts.append("\n## Kimler Kullanmamalı")
                cleaned_contras = self._clean_list_items(contras, max_items=6, max_item_len=180)
                for c in cleaned_contras:
                    parts.append(f"❌ {c}")

        # Overdose warning
        overdose = med.get('overdose_warning', '')
        if isinstance(overdose, str) and overdose:
            has_content = True
            parts.append("\n## Doz Aşımı")
            overdose_short = self._smart_truncate_item(overdose, 200)
            parts.append(f"🚨 {overdose_short}")

        if not has_content:
            return None

        full_content = '\n'.join(parts)
        full_content = self._smart_truncate(full_content, OPENFDA_MAX_CHARS, OPENFDA_MIN_CHARS)

        return {
            'id': f"{parent_id}_safety",
            'parent_id': parent_id,
            'section': 'safety',
            'title': f"{title} - Güvenlik",
            'title_tr': f"{title} - Uyarılar ve Kontrendikasyonlar",
            'category': 'medications',
            'content': full_content,
            'keywords_en': med.get('keywords_en', []),
            'keywords_tr': med.get('keywords_tr', []) + ['uyarı', 'kontrendikasyon', 'kimler kullanamaz', 'tehlike'],
            'source_name': med.get('source_name', 'openFDA'),
            'source_url': med.get('source_url', ''),
        }

    def _create_openfda_how_to_use(self, med: Dict) -> Optional[Dict]:
        """OpenFDA ilaç kaydından how_to_use dokümanı oluştur"""
        title = med.get('title', '')
        parent_id = med.get('id', '')

        parts = [f"# {title} - Kullanım Bilgileri"]
        has_content = False

        # Dosage info
        dosage_info = med.get('dosage_info', {})
        if isinstance(dosage_info, dict) and dosage_info.get('note'):
            has_content = True
            parts.append("\n## Dozaj")
            note = dosage_info['note']
            note_short = self._smart_truncate_item(note, 220)
            parts.append(note_short)
            if dosage_info.get('disclaimer'):
                parts.append(f"\n⚠️ {dosage_info['disclaimer']}")

        # Drug interactions (max 8)
        interactions = med.get('drug_interactions', [])
        if isinstance(interactions, list) and interactions:
            has_content = True
            parts.append("\n## İlaç Etkileşimleri")
            cleaned_inter = self._clean_list_items(interactions, max_items=8, max_item_len=180)
            for inter in cleaned_inter:
                parts.append(f"• {inter}")

        # Side effects (max 10)
        side_effects = med.get('side_effects', [])
        if isinstance(side_effects, list) and side_effects:
            has_content = True
            parts.append("\n## Yan Etkiler")
            cleaned_se = self._clean_list_items(side_effects, max_items=10, max_item_len=150)
            for se in cleaned_se:
                parts.append(f"• {se}")

        if not has_content:
            return None

        full_content = '\n'.join(parts)
        full_content = self._smart_truncate(full_content, OPENFDA_MAX_CHARS, OPENFDA_MIN_CHARS)

        return {
            'id': f"{parent_id}_how_to_use",
            'parent_id': parent_id,
            'section': 'how_to_use',
            'title': f"{title} - Kullanım",
            'title_tr': f"{title} - Nasıl Kullanılır",
            'category': 'medications',
            'content': full_content,
            'keywords_en': med.get('keywords_en', []),
            'keywords_tr': med.get('keywords_tr', []) + ['nasıl kullanılır', 'doz', 'yan etki', 'etkileşim'],
            'source_name': med.get('source_name', 'openFDA'),
            'source_url': med.get('source_url', ''),
            'has_guardrail': bool(dosage_info and dosage_info.get('note')),
        }

    def _is_noise_medication(self, med: Dict) -> bool:
        """Gürültü ilaç kaydı mı kontrol et (WATER, diluent, vb.)"""
        import re

        title = med.get('title', '').upper().strip()

        # Title pattern kontrolü
        noise_patterns = [
            r'^WATER$', r'^STERILE\s+WATER', r'^SODIUM\s+CHLORIDE$',
            r'^SALINE$', r'^DEXTROSE$', r'^GLUCOSE$',
            r'^BACTERIOSTATIC\s+WATER', r'^DILUENT', r'^STERILE\s+DILUENT', r'^PLACEBO',
        ]
        for pattern in noise_patterns:
            if re.match(pattern, title, re.IGNORECASE):
                return True

        # Keywords kontrolü
        noise_keywords = {'sterile diluent', 'diluent for', 'sterile water for injection', 'placebo'}
        keywords = med.get('keywords_en', []) + med.get('keywords_tr', [])
        for kw in keywords:
            if isinstance(kw, str):
                kw_lower = kw.lower()
                for noise in noise_keywords:
                    if noise in kw_lower:
                        return True

        return False

    def _build_tr_allowlist_from_curated(self) -> None:
        """
        medications.json'dan TR'de bilinen ilaç isimlerinin allowlist'ini oluştur.
        Bu liste OpenFDA yüklemesinde filtre olarak kullanılacak.
        """
        curated_path = self.data_dir / "medications.json"
        if not curated_path.exists():
            print("ℹ️  medications.json bulunamadı, allowlist oluşturulamadı")
            return

        with open(curated_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        terms = set()
        for item in data:
            if not isinstance(item, dict):
                continue

            # Title ve title_tr
            for field in ["title", "title_tr"]:
                if item.get(field):
                    terms.add(self._normalize_text(item[field]))

            # Keywords ve brand examples
            keyword_fields = ["keywords_tr", "keywords_en", "brand_examples_tr"]
            for field in keyword_fields:
                for kw in (item.get(field) or []):
                    if isinstance(kw, str) and kw.strip():
                        terms.add(self._normalize_text(kw))

        # Yaygın jenerik ilaç isimleri (manuel seed)
        common_generics = [
            "acetaminophen", "paracetamol", "ibuprofen", "aspirin", "naproxen",
            "diclofenac", "metformin", "omeprazole", "pantoprazole", "lansoprazole",
            "amoxicillin", "azithromycin", "ciprofloxacin", "metronidazole",
            "atorvastatin", "simvastatin", "amlodipine", "lisinopril", "losartan",
            "metoprolol", "carvedilol", "furosemide", "hydrochlorothiazide",
            "gabapentin", "pregabalin", "sertraline", "fluoxetine", "escitalopram",
            "alprazolam", "lorazepam", "diazepam", "zolpidem",
            "levothyroxine", "prednisone", "prednisolone", "dexamethasone",
            "insulin", "metformin", "glimepiride", "sitagliptin",
            "salbutamol", "albuterol", "fluticasone", "montelukast",
            "cetirizine", "loratadine", "fexofenadine", "diphenhydramine",
            "ranitidine", "famotidine", "sucralfate",
            "warfarin", "clopidogrel", "enoxaparin", "rivaroxaban",
            "tramadol", "codeine", "morphine", "fentanyl",
            "sildenafil", "tadalafil",
        ]
        for g in common_generics:
            terms.add(self._normalize_text(g))

        self._tr_drug_allowlist = terms
        print(f"✅ TR ilaç allowlist oluşturuldu: {len(terms)} terim")

    def _is_in_tr_allowlist(self, med: Dict) -> bool:
        """OpenFDA ilacının TR allowlist'te olup olmadığını kontrol et"""
        if not self._tr_drug_allowlist:
            return True  # Allowlist yoksa hepsini kabul et

        # Title kontrolü
        title_norm = self._normalize_text(med.get("title", ""))
        if title_norm in self._tr_drug_allowlist:
            return True

        # Title'daki kelimeleri kontrol et (ACETAMINOPHEN AND CAFFEINE gibi)
        title_words = title_norm.split()
        for word in title_words:
            if len(word) >= 4 and word in self._tr_drug_allowlist:
                return True

        # Keywords kontrolü
        for kw in (med.get("keywords_tr") or []) + (med.get("keywords_en") or []):
            if isinstance(kw, str):
                kw_norm = self._normalize_text(kw)
                if kw_norm in self._tr_drug_allowlist:
                    return True
                # Keyword'deki kelimeleri de kontrol et
                for word in kw_norm.split():
                    if len(word) >= 4 and word in self._tr_drug_allowlist:
                        return True

        return False

    def load_openfda_medications(self, file_path: str) -> int:
        """
        OpenFDA medications_openfda_only_tr.json dosyasını yükle.
        Her ilaç için 3 doküman oluşturur: overview, safety, how_to_use

        Returns:
            Yüklenen döküman sayısı
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError(f"JSON root must be a list, got {type(data).__name__}")

        texts = []
        metadatas = []
        ids = []
        noise_count = 0
        allowlist_filtered = 0
        section_counts = {'overview': 0, 'safety': 0, 'how_to_use': 0}

        for med in data:
            if not isinstance(med, dict):
                continue

            # Gürültü filtresi
            if self._is_noise_medication(med):
                noise_count += 1
                continue

            # TR allowlist filtresi
            if not self._is_in_tr_allowlist(med):
                allowlist_filtered += 1
                continue

            # 3-doküman formatı oluştur
            docs_to_add = []

            # 1. Overview (her zaman)
            overview = self._create_openfda_overview(med)
            docs_to_add.append(overview)
            section_counts['overview'] += 1

            # 2. Safety (içerik varsa)
            safety = self._create_openfda_safety(med)
            if safety:
                docs_to_add.append(safety)
                section_counts['safety'] += 1

            # 3. How to use (içerik varsa)
            how_to_use = self._create_openfda_how_to_use(med)
            if how_to_use:
                docs_to_add.append(how_to_use)
                section_counts['how_to_use'] += 1

            # Dokümanları ekle
            for doc in docs_to_add:
                # OpenFDA için _format_document BYPASS - content zaten markdown formatında
                text = doc.get("content", "").strip()
                if not text:
                    continue

                # Tüm keyword'leri birleştir
                raw_keywords = []
                raw_keywords.extend(doc.get('keywords_en') or [])
                raw_keywords.extend(doc.get('keywords_tr') or [])
                raw_keywords.extend(doc.get('typos_tr') or [])
                all_keywords = self._normalize_keywords(raw_keywords)

                metadata = {
                    "title": doc.get("title", ""),
                    "title_tr": doc.get("title_tr", ""),
                    "category": doc.get("category", "medications"),
                    "source": doc.get("source_name", "openFDA"),
                    "source_url": doc.get("source_url", ""),
                    "keywords": all_keywords,
                    "section": doc.get("section", ""),
                    "parent_id": doc.get("parent_id", ""),
                    "drug_class": doc.get("drug_class", ""),
                    "has_guardrail": self._to_bool(doc.get("has_guardrail", False)),
                }
                self.categories.add(metadata["category"])

                texts.append(text)
                metadatas.append(metadata)
                ids.append(doc.get("id", ""))

        if texts:
            self.vector_store.add_documents(texts, metadatas, ids)

        print(f"  → Gürültü filtresi: {noise_count} kayıt elendi")
        print(f"  → TR allowlist filtresi: {allowlist_filtered} kayıt elendi")
        print(f"  → Section dağılımı: {section_counts}")

        return len(texts)

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
                "retrieved_date": item.get("retrieved_date", ""),
                # OpenFDA chunks için ek alanlar
                "section": item.get("section", ""),
                "parent_id": item.get("parent_id", ""),
                "has_guardrail": self._to_bool(item.get("has_guardrail", False)),
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
        """Dökümanı arama için optimize edilmiş formata çevir (v3.3+ schema + OpenFDA chunks)"""
        parts = []

        # === CHUNK BİLGİSİ (OpenFDA chunks için) ===
        if item.get("section"):
            section = item['section']
            # Section'ı human-readable hale getir (v2 3-doküman formatı)
            section_names = {
                # v2 format (3-doküman)
                'overview': 'Genel Bilgi',
                'safety': 'Güvenlik (Uyarılar/Kontrendikasyonlar)',
                'how_to_use': 'Kullanım (Doz/Yan Etki/Etkileşim)',
                # v1 format (backward compatibility)
                'main': 'Genel Bilgi',
                'uses': 'Kullanım Alanları',
                'warnings': 'Uyarılar',
                'contraindications': 'Kontrendikasyonlar',
                'interactions': 'İlaç Etkileşimleri',
                'side_effects': 'Yan Etkiler',
                'dosage': 'Dozaj Bilgisi'
            }
            readable_section = section_names.get(section, section)
            parts.append(f"Section: {readable_section}")

        # === TEMEL BİLGİLER ===
        if item.get("title"):
            title = item['title']
            if item.get("title_tr") and item['title_tr'] != title:
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
        - medications.json: İlaç verileri (el yapımı, kaliteli, TR)
        - medications_openfda_only_tr.json: OpenFDA ilaç verileri (3-doküman formatı dinamik oluşturulur)
        - symptoms_diseases_medlineplus_tr_enriched.json: MedlinePlus verileri (ETL + TR zenginleştirme)

        Atlanacak dosyalar:
        - symptoms_diseases.json: Eski el yapımı veri (enriched ile değiştirildi)
        - medications_openfda.json: Ham veri (clean versiyonu kullanılıyor)
        - medications_openfda_chunks.json: Eski chunk dosyası (artık dinamik oluşturuluyor)
        - *_medlineplus.json (enriched hariç): Ara dosyalar
        - *_clean_en.json: Ara dosyalar
        """
        # Eğer index zaten diskten yüklendiyse, JSON'lardan tekrar yükleme yapma
        existing_docs = len(self.vector_store.documents)
        if existing_docs > 0:
            print(f"ℹ️  Index zaten {existing_docs} döküman içeriyor, JSON yüklemesi atlanıyor")
            # Categories'i vector_store'dan rebuild et
            for doc in self.vector_store.documents:
                cat = doc.get("metadata", {}).get("category", "general")
                self.categories.add(cat)
            return existing_docs

        if not self.data_dir.exists():
            print(f"⚠️  Veri klasörü bulunamadı: {self.data_dir}")
            return 0

        total_loaded = 0

        # 1. Standart JSON dosyaları (normal yükleme)
        standard_files = [
            "emergency.json",
            "medications.json",
            "symptoms_diseases_medlineplus_tr_enriched.json",
        ]

        # Fallback: Eğer enriched dosya yoksa, orijinal curated dosyayı yükle
        enriched_file = self.data_dir / "symptoms_diseases_medlineplus_tr_enriched.json"
        if not enriched_file.exists():
            print("ℹ️  Enriched dosya bulunamadı, orijinal symptoms_diseases.json yüklenecek")
            standard_files.append("symptoms_diseases.json")

        for filename in standard_files:
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

        # TR ilaç allowlist'i oluştur (medications.json'dan)
        self._build_tr_allowlist_from_curated()

        # 2. OpenFDA medications - özel 3-doküman formatı ile yükle (TR allowlist ile filtrelenir)
        openfda_file = self.data_dir / "medications_openfda_only_tr.json"
        if openfda_file.exists():
            file_key = str(openfda_file.resolve())
            if file_key not in self._loaded_files:
                try:
                    print(f"📦 OpenFDA medications yükleniyor (3-doküman formatı)...")
                    count = self.load_openfda_medications(str(openfda_file))
                    self._loaded_files.add(file_key)
                    print(f"📚 medications_openfda_only_tr.json: {count} döküman yüklendi")
                    total_loaded += count
                except Exception as e:
                    print(f"❌ medications_openfda_only_tr.json yüklenemedi: {e}")
        else:
            print(f"⚠️  medications_openfda_only_tr.json: dosya bulunamadı, atlanıyor")

        # IVF index rebuild (>1000 dok varsa) ve kaydet
        if total_loaded > 0:
            rebuilt = self.vector_store.rebuild_index_if_needed()
            if rebuilt:
                print("💾 IVF index kaydediliyor...")
                self.save()

        return total_loaded
    
    def _keyword_search(self, query_terms: set, top_k: int = 10) -> List[Dict]:
        """
        O(#terms) keyword-based document retrieval using inverted index.
        Uses VectorStore's keyword_index for fast lookup instead of O(N) scan.
        """
        # Use VectorStore's fast inverted index lookup
        return self.vector_store.get_docs_by_keywords(query_terms, top_k=top_k)

    def search(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
        profiler: Optional[RequestProfiler] = None,
        use_cache: bool = True
    ) -> List[Dict]:
        """
        Hybrid search: Vector similarity + keyword retrieval

        Sentence-transformers may not understand brand names (e.g., "Calpol").
        We combine vector search with keyword-based retrieval to improve recall.

        Args:
            query: Arama sorgusu (İngilizce veya Türkçe)
            top_k: Döndürülecek sonuç sayısı
            category: Belirli bir kategoride ara (symptoms, diseases, etc.)
            profiler: Optional profiler for timing
            use_cache: Whether to use retrieval cache
        """
        # Check retrieval cache first
        cache_key = f"{query}:{top_k}:{category}"
        if use_cache:
            retrieval_cache = get_retrieval_cache()
            cached_results = retrieval_cache.get(cache_key)
            if cached_results is not None:
                if profiler:
                    profiler.add_timing("t_retrieve", 0.5)  # Cache hit
                return cached_results

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

        # Auto-detect category if not provided (pre-filtering optimization)
        search_category = category
        if not search_category:
            predicted = predict_category(query)
            if predicted:
                search_category = predicted
                if profiler:
                    print(f"  → Auto-detected category: {predicted}")

        # 1. Vector search with optional profiler
        fetch_k = max(top_k * 2, 10)
        if profiler:
            with profiler.time("t_retrieve"):
                vector_results = self.vector_store.search(
                    query, top_k=fetch_k, category=search_category, profiler=profiler
                )
        else:
            vector_results = self.vector_store.search(
                query, top_k=fetch_k, category=search_category
            )

        # 2. Keyword search - sadece ilaç adı gibi kısa sorgularda çalıştır (hız optimizasyonu)
        # "başım ağrıyor ne yapayım" gibi semptom sorularında keyword taraması atlanır
        keyword_results = []
        if meaningful_terms:
            tokens = list(meaningful_terms)
            # İlaç sorgusu gibi görünüyor mu? (kısa veya rakam içeriyor)
            looks_like_drug_query = (
                len(tokens) <= 3 or
                any(any(ch.isdigit() for ch in t) for t in tokens) or
                any(t in self._tr_drug_allowlist for t in tokens)
            )
            if looks_like_drug_query:
                if profiler:
                    with profiler.time("t_keyword"):
                        keyword_results = self._keyword_search(meaningful_terms, top_k=top_k)
                else:
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

        # Kategori filtresi (if explicit category was provided but not used in search)
        if category and category != search_category:
            merged = [r for r in merged if r["metadata"].get("category") == category]

        results = merged[:top_k]

        # Cache the results
        if use_cache:
            retrieval_cache = get_retrieval_cache()
            retrieval_cache.set(cache_key, results)

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
