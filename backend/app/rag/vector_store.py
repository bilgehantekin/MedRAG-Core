"""
Vector Store Module
FAISS ile vektör veritabanı yönetimi

Performance Optimizations:
- IVF index for faster search on large datasets
- Embedding cache to avoid re-computing same queries
- Pre-filtering support for category-based search
"""

import faiss
import numpy as np
import json
import os
import time
from collections import defaultdict
from typing import List, Dict, Optional, Tuple, Set
from pathlib import Path

from app.rag.embeddings import get_embedding_model, EmbeddingModel
from app.rag.performance import get_embedding_cache, RequestProfiler

# Index type thresholds
IVF_THRESHOLD = 1000  # Use IVF index if documents > 1000
HNSW_THRESHOLD = 5000  # Use HNSW index if documents > 5000


class VectorStore:
    """
    FAISS tabanlı vektör veritabanı
    Tıbbi dökümanları saklar ve semantic search yapar
    """
    
    def __init__(
        self,
        embedding_model: Optional[EmbeddingModel] = None,
        index_path: Optional[str] = None,
        use_ivf: bool = True,  # Enable IVF for faster search
        nprobe: int = 10  # Number of clusters to search (higher = more accurate, slower)
    ):
        """
        Args:
            embedding_model: Kullanılacak embedding model (None ise default)
            index_path: Kaydedilmiş index'i yüklemek için path
            use_ivf: Use IVF index for faster search (recommended for >1000 docs)
            nprobe: Number of clusters to search for IVF (default 10)
        """
        self.embedding_model = embedding_model or get_embedding_model()
        self.dimension = self.embedding_model.get_dimension()
        self.use_ivf = use_ivf
        self.nprobe = nprobe
        self.index_type = "flat"  # Will be updated based on doc count

        # FAISS index - start with FlatL2, upgrade to IVF after documents are added
        self.index = faiss.IndexFlatL2(self.dimension)

        # Metadata storage - her vektörün karşılığı olan metin/bilgi
        self.documents: List[Dict] = []

        # Category index for pre-filtering (category -> document indices)
        self.category_index: Dict[str, List[int]] = {}

        # Inverted keyword index for O(1) keyword lookup (keyword -> document indices)
        self.keyword_index: Dict[str, List[int]] = defaultdict(list)

        # Embedding cache reference
        self._embedding_cache = get_embedding_cache()

        # Eğer kayıtlı index varsa yükle
        if index_path:
            if os.path.isdir(index_path):
                load_success = self.load(index_path)
                if load_success:
                    print(f"✅ Vector store yüklendi: {len(self.documents)} döküman (index_type: {self.index_type})")
                else:
                    # Eski/uyumsuz index - temiz başla, rebuild gerekiyor
                    print("⚠️  Uyumsuz index atlandı - temiz başlatılıyor")
                    self.index = faiss.IndexFlatL2(self.dimension)
                    self.documents = []
            else:
                print(f"⚠️  index_path klasör değil: {index_path} (skip load)")
                print(f"✅ Yeni vector store oluşturuldu (dim: {self.dimension})")
        else:
            print(f"✅ Yeni vector store oluşturuldu (dim: {self.dimension})")

    def _normalize(self, x: np.ndarray) -> np.ndarray:
        """
        Vektörleri unit normalize eder.
        L2 distance ile normalize edilmiş vektörler kullanmak,
        cosine similarity ile eşdeğer sonuçlar verir ve retrieval kalitesini artırır.
        """
        norms = np.linalg.norm(x, axis=1, keepdims=True)
        norms = np.clip(norms, 1e-12, None)  # Sıfıra bölmeyi önle
        return x / norms
    
    def add_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None
    ) -> None:
        """
        Dökümanları vector store'a ekle

        Args:
            texts: Eklenecek metinler
            metadatas: Her metin için metadata (source, category, etc.)
            ids: Her metin için unique ID
        """
        if not texts:
            return

        # Uzunluk validasyonu
        if metadatas is not None and len(metadatas) != len(texts):
            raise ValueError(f"metadatas length ({len(metadatas)}) must match texts length ({len(texts)})")
        if ids is not None and len(ids) != len(texts):
            raise ValueError(f"ids length ({len(ids)}) must match texts length ({len(texts)})")

        # Embedding oluştur ve normalize et (retrieval kalitesi için)
        embeddings = np.asarray(self.embedding_model.embed_texts(texts), dtype="float32")
        embeddings = np.atleast_2d(embeddings)  # 1D gelirse 2D yap
        embeddings = self._normalize(embeddings)

        # Track starting index for category mapping
        start_idx = len(self.documents)

        # FAISS'e ekle
        self.index.add(embeddings)

        # Metadata sakla + category index'i güncelle + keyword index'i güncelle
        for i, text in enumerate(texts):
            doc_idx = start_idx + i
            doc = {
                "id": ids[i] if ids else f"doc_{doc_idx}",
                "text": text,
                "metadata": metadatas[i] if metadatas else {}
            }
            self.documents.append(doc)

            # Update category index for pre-filtering
            category = doc["metadata"].get("category", "general")
            if category not in self.category_index:
                self.category_index[category] = []
            self.category_index[category].append(doc_idx)

            # Update keyword index for O(1) keyword lookup
            keywords = doc["metadata"].get("keywords", [])
            if keywords:
                seen_kw = set()
                for kw in keywords:
                    if isinstance(kw, str):
                        k = kw.casefold().strip()
                        if k and k not in seen_kw:
                            self.keyword_index[k].append(doc_idx)
                            seen_kw.add(k)

        print(f"✅ {len(texts)} döküman eklendi. Toplam: {len(self.documents)}")

    def rebuild_index_if_needed(self) -> bool:
        """
        Rebuild index with IVF if document count exceeds threshold.
        Call this after bulk loading is complete.

        Returns:
            True if index was rebuilt, False otherwise
        """
        doc_count = len(self.documents)

        # Only rebuild if we have enough documents and using FlatL2
        if not self.use_ivf or doc_count < IVF_THRESHOLD:
            return False

        if self.index_type == "ivf":
            return False  # Already IVF

        print(f"🔄 Rebuilding index to IVF (doc_count={doc_count})...")
        start = time.perf_counter()

        # Get all embeddings from current index
        all_embeddings = np.zeros((doc_count, self.dimension), dtype="float32")
        for i in range(doc_count):
            # Reconstruct embedding from flat index
            all_embeddings[i] = self.index.reconstruct(i)

        # Create IVF index
        # nlist: number of clusters (sqrt(n) is a good heuristic)
        nlist = min(int(np.sqrt(doc_count)), 100)  # Cap at 100 clusters

        quantizer = faiss.IndexFlatL2(self.dimension)
        ivf_index = faiss.IndexIVFFlat(quantizer, self.dimension, nlist)

        # Train the index
        ivf_index.train(all_embeddings)

        # Add vectors
        ivf_index.add(all_embeddings)

        # Set nprobe (number of clusters to search)
        ivf_index.nprobe = self.nprobe

        # Replace index
        self.index = ivf_index
        self.index_type = "ivf"

        elapsed = (time.perf_counter() - start) * 1000
        print(f"✅ IVF index rebuilt: nlist={nlist}, nprobe={self.nprobe}, time={elapsed:.0f}ms")

        return True
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: Optional[float] = None,
        category: Optional[str] = None,
        profiler: Optional[RequestProfiler] = None
    ) -> List[Dict]:
        """
        Semantic search yap

        Args:
            query: Arama sorgusu
            top_k: Döndürülecek maksimum sonuç sayısı
            score_threshold: Bu değerin altındaki skorları filtrele (düşük = daha iyi)
            category: Filter by category (pre-filtering optimization)
            profiler: Optional profiler for timing

        Returns:
            List of {text, metadata, score} dictionaries
        """
        if self.index.ntotal == 0:
            return []

        # Try to get embedding from cache first
        cached_embedding = self._embedding_cache.get(query)

        if cached_embedding is not None:
            query_embedding = cached_embedding
            if profiler:
                profiler.add_timing("t_embed", 0.1)  # Cache hit
        else:
            # Query embedding (normalize et - dokümanlarla aynı şekilde)
            if profiler:
                with profiler.time("t_embed"):
                    query_embedding = self.embedding_model.embed_text(query)
                    query_embedding = query_embedding.reshape(1, -1).astype('float32')
                    query_embedding = self._normalize(query_embedding)
            else:
                query_embedding = self.embedding_model.embed_text(query)
                query_embedding = query_embedding.reshape(1, -1).astype('float32')
                query_embedding = self._normalize(query_embedding)

            # Cache the embedding
            self._embedding_cache.set(query, query_embedding)

        # FAISS search
        if profiler:
            with profiler.time("t_faiss"):
                distances, indices = self.index.search(query_embedding, min(top_k * 2, self.index.ntotal))
        else:
            distances, indices = self.index.search(query_embedding, min(top_k * 2, self.index.ntotal))

        # Sonuçları formatla (with optional category filtering)
        results = []
        category_filter_indices = None
        if category and category in self.category_index:
            category_filter_indices = set(self.category_index[category])

        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:  # FAISS bazen -1 döndürebilir
                continue

            if score_threshold is not None and dist > score_threshold:
                continue

            # Category pre-filtering
            if category_filter_indices is not None and idx not in category_filter_indices:
                continue

            doc = self.documents[idx]
            results.append({
                "text": doc["text"],
                "metadata": doc["metadata"],
                "score": float(dist),  # Düşük = daha iyi (L2 distance)
                "id": doc["id"]
            })

            if len(results) >= top_k:
                break

        return results

    def search_by_category(
        self,
        query: str,
        categories: List[str],
        top_k: int = 5,
        profiler: Optional[RequestProfiler] = None
    ) -> List[Dict]:
        """
        Search within specific categories only.
        More efficient than post-filtering for targeted queries.

        Args:
            query: Search query
            categories: List of categories to search in
            top_k: Maximum results
            profiler: Optional profiler

        Returns:
            List of search results
        """
        if not categories:
            return self.search(query, top_k=top_k, profiler=profiler)

        # Get all document indices for requested categories
        target_indices = set()
        for cat in categories:
            if cat in self.category_index:
                target_indices.update(self.category_index[cat])

        if not target_indices:
            return []

        # Perform search with larger k to account for filtering
        results = self.search(query, top_k=top_k * 3, profiler=profiler)

        # Filter to only include target categories
        filtered = [r for r in results if r["metadata"].get("category") in categories]

        return filtered[:top_k]
    
    def save(self, path: str) -> None:
        """Index ve metadata'yı diske kaydet"""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # FAISS index kaydet
        faiss.write_index(self.index, str(path / "index.faiss"))

        # Metadata kaydet
        with open(path / "documents.json", "w", encoding="utf-8") as f:
            json.dump(self.documents, f, ensure_ascii=False, indent=2)

        # Category index kaydet (for pre-filtering)
        with open(path / "category_index.json", "w", encoding="utf-8") as f:
            json.dump(self.category_index, f, ensure_ascii=False, indent=2)

        # Keyword index kaydet (for O(1) keyword lookup)
        with open(path / "keyword_index.json", "w", encoding="utf-8") as f:
            json.dump(dict(self.keyword_index), f, ensure_ascii=False, indent=2)

        # Index metadata kaydet (normalization flag dahil)
        index_metadata = {
            "normalized": True,
            "version": "3.0",  # Updated version for IVF support
            "dimension": self.dimension,
            "model": self.embedding_model.model_name,
            "total_documents": len(self.documents),
            "index_type": self.index_type,
            "nprobe": self.nprobe if self.index_type == "ivf" else None,
            "categories": list(self.category_index.keys())
        }
        with open(path / "index_metadata.json", "w", encoding="utf-8") as f:
            json.dump(index_metadata, f, ensure_ascii=False, indent=2)

        print(f"✅ Vector store kaydedildi: {path} (index_type: {self.index_type})")

    def load(self, path: str) -> bool:
        """
        Kaydedilmiş index ve metadata'yı yükle

        Returns:
            bool: True ise başarılı yükleme, False ise rebuild gerekiyor
        """
        path = Path(path)
        needs_rebuild = False
        index_metadata = {}

        # Index metadata kontrol et
        metadata_file = path / "index_metadata.json"
        if metadata_file.exists():
            with open(metadata_file, "r", encoding="utf-8") as f:
                index_metadata = json.load(f)

            # Normalization kontrolü
            if not index_metadata.get("normalized", False):
                print("⚠️  Eski index normalize edilmemiş! Rebuild gerekiyor.")
                needs_rebuild = True

            # Model uyumluluk kontrolü
            saved_model = index_metadata.get("model", "")
            if saved_model and saved_model != self.embedding_model.model_name:
                print(f"⚠️  Model uyumsuzluğu! Kayıtlı: {saved_model}, Şimdiki: {self.embedding_model.model_name}")
                needs_rebuild = True

            # Dimension uyumluluk kontrolü (metadata'dan)
            saved_dim = index_metadata.get("dimension")
            if saved_dim and int(saved_dim) != int(self.dimension):
                print(f"⚠️  Dimension uyumsuzluğu! Kayıtlı: {saved_dim}, Şimdiki: {self.dimension}")
                needs_rebuild = True
        else:
            # Eski format - metadata yok, muhtemelen normalize edilmemiş
            print("⚠️  index_metadata.json bulunamadı - eski format, rebuild önerilir")
            needs_rebuild = True

        if needs_rebuild:
            print("🔄 Eski index uyumsuz - rebuild gerekiyor!")
            return False

        # Dosya varlık kontrolü
        index_file = path / "index.faiss"
        docs_file = path / "documents.json"

        if not index_file.exists() or not docs_file.exists():
            print("⚠️  index.faiss veya documents.json eksik - rebuild gerekiyor")
            return False

        # Atomic load: önce temp'e yükle, validasyon geçerse commit et
        tmp_index = faiss.read_index(str(index_file))

        with open(docs_file, "r", encoding="utf-8") as f:
            tmp_docs = json.load(f)

        # Yükleme sonrası uyumluluk kontrolleri
        # Index dimension kontrolü
        if getattr(tmp_index, "d", None) != self.dimension:
            print(f"⚠️  Index dimension uyumsuz! index.d={tmp_index.d}, beklenen={self.dimension}")
            return False

        # Index-document sayısı uyumu
        if tmp_index.ntotal != len(tmp_docs):
            print(f"⚠️  Index/doc count uyumsuz! ntotal={tmp_index.ntotal}, docs={len(tmp_docs)}")
            return False

        # Tüm validasyonlar geçti - commit et
        self.index = tmp_index
        self.documents = tmp_docs

        # Load index type info
        self.index_type = index_metadata.get("index_type", "flat")
        if self.index_type == "ivf" and hasattr(tmp_index, "nprobe"):
            tmp_index.nprobe = index_metadata.get("nprobe", self.nprobe)

        # Load category index if available
        category_file = path / "category_index.json"
        if category_file.exists():
            with open(category_file, "r", encoding="utf-8") as f:
                self.category_index = json.load(f)
            print(f"  → Category index yüklendi: {list(self.category_index.keys())}")
        else:
            # Rebuild category index from documents
            print("  → Category index bulunamadı, yeniden oluşturuluyor...")
            self._rebuild_category_index()

        # Load keyword index if available
        keyword_file = path / "keyword_index.json"
        if keyword_file.exists():
            with open(keyword_file, "r", encoding="utf-8") as f:
                loaded_kw = json.load(f)
                self.keyword_index = defaultdict(list, loaded_kw)
            print(f"  → Keyword index yüklendi: {len(self.keyword_index)} keyword")
        else:
            # Rebuild keyword index from documents
            print("  → Keyword index bulunamadı, yeniden oluşturuluyor...")
            self._rebuild_keyword_index()

        return True

    def _rebuild_category_index(self):
        """Rebuild category index from documents"""
        self.category_index = {}
        for idx, doc in enumerate(self.documents):
            category = doc.get("metadata", {}).get("category", "general")
            if category not in self.category_index:
                self.category_index[category] = []
            self.category_index[category].append(idx)

    def _rebuild_keyword_index(self):
        """Rebuild keyword index from documents"""
        self.keyword_index = defaultdict(list)
        for idx, doc in enumerate(self.documents):
            keywords = doc.get("metadata", {}).get("keywords", [])
            if keywords:
                seen_kw = set()
                for kw in keywords:
                    if isinstance(kw, str):
                        k = kw.casefold().strip()
                        if k and k not in seen_kw:
                            self.keyword_index[k].append(idx)
                            seen_kw.add(k)

    def get_docs_by_keywords(self, query_terms: Set[str], top_k: int = 10) -> List[Dict]:
        """
        O(#terms) keyword-based document retrieval using inverted index.

        Args:
            query_terms: Set of normalized query terms to search for
            top_k: Maximum results to return

        Returns:
            List of matching documents with scores
        """
        if not query_terms or not self.keyword_index:
            return []

        # Collect candidate document indices with match scores
        doc_scores: Dict[int, int] = defaultdict(int)

        for term in query_terms:
            term_lower = term.casefold().strip()

            # Exact match
            if term_lower in self.keyword_index:
                for doc_idx in self.keyword_index[term_lower]:
                    doc_scores[doc_idx] += 2  # Exact match bonus

            # Partial match (term içeren keyword'ler)
            for kw, doc_indices in self.keyword_index.items():
                if term_lower in kw and kw != term_lower:
                    for doc_idx in doc_indices:
                        doc_scores[doc_idx] += 1  # Partial match

        if not doc_scores:
            return []

        # Sort by score (descending) and convert to results
        sorted_docs = sorted(doc_scores.items(), key=lambda x: -x[1])

        results = []
        for doc_idx, score in sorted_docs[:top_k]:
            doc = self.documents[doc_idx]
            results.append({
                "text": doc["text"],
                "metadata": doc["metadata"],
                "score": max(0.01, 0.5 - (score * 0.05)),  # Distance-like score (lower=better), clamped to prevent div-by-zero
                "keyword_matched": True,
                "id": doc["id"]
            })

        return results
    
    def clear(self) -> None:
        """Tüm verileri temizle"""
        self.index = faiss.IndexFlatL2(self.dimension)
        self.documents = []
        print("✅ Vector store temizlendi")
    
    def __len__(self) -> int:
        return len(self.documents)
    
    def get_stats(self) -> Dict:
        """İstatistikleri döndür"""
        stats = {
            "total_documents": len(self.documents),
            "index_size": self.index.ntotal,
            "dimension": self.dimension,
            "model": self.embedding_model.model_name,
            "index_type": self.index_type,
            "categories": list(self.category_index.keys()),
            "category_counts": {k: len(v) for k, v in self.category_index.items()}
        }

        # Add IVF-specific stats
        if self.index_type == "ivf" and hasattr(self.index, "nprobe"):
            stats["nprobe"] = self.index.nprobe
            stats["nlist"] = getattr(self.index, "nlist", None)

        # Add cache stats
        stats["embedding_cache"] = self._embedding_cache.stats()

        # Add keyword index stats
        stats["keyword_index_size"] = len(self.keyword_index)

        return stats
