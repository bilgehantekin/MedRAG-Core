"""
Vector Store Module
FAISS ile vektör veritabanı yönetimi
"""

import faiss
import numpy as np
import json
import os
from typing import List, Dict, Tuple, Optional
from pathlib import Path

from app.rag.embeddings import get_embedding_model, EmbeddingModel


class VectorStore:
    """
    FAISS tabanlı vektör veritabanı
    Tıbbi dökümanları saklar ve semantic search yapar
    """
    
    def __init__(
        self, 
        embedding_model: Optional[EmbeddingModel] = None,
        index_path: Optional[str] = None
    ):
        """
        Args:
            embedding_model: Kullanılacak embedding model (None ise default)
            index_path: Kaydedilmiş index'i yüklemek için path
        """
        self.embedding_model = embedding_model or get_embedding_model()
        self.dimension = self.embedding_model.get_dimension()
        
        # FAISS index - L2 distance (Euclidean)
        self.index = faiss.IndexFlatL2(self.dimension)
        
        # Metadata storage - her vektörün karşılığı olan metin/bilgi
        self.documents: List[Dict] = []
        
        # Eğer kayıtlı index varsa yükle
        if index_path and os.path.exists(index_path):
            load_success = self.load(index_path)
            if load_success:
                print(f"✅ Vector store yüklendi: {len(self.documents)} döküman")
            else:
                # Eski/uyumsuz index - temiz başla, rebuild gerekiyor
                print("⚠️  Uyumsuz index atlandı - temiz başlatılıyor")
                self.index = faiss.IndexFlatL2(self.dimension)
                self.documents = []
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

        # Embedding oluştur ve normalize et (retrieval kalitesi için)
        embeddings = self.embedding_model.embed_texts(texts).astype('float32')
        embeddings = self._normalize(embeddings)

        # FAISS'e ekle
        self.index.add(embeddings)
        
        # Metadata sakla
        for i, text in enumerate(texts):
            doc = {
                "id": ids[i] if ids else f"doc_{len(self.documents)}",
                "text": text,
                "metadata": metadatas[i] if metadatas else {}
            }
            self.documents.append(doc)
        
        print(f"✅ {len(texts)} döküman eklendi. Toplam: {len(self.documents)}")
    
    def search(
        self, 
        query: str, 
        top_k: int = 5,
        score_threshold: Optional[float] = None
    ) -> List[Dict]:
        """
        Semantic search yap
        
        Args:
            query: Arama sorgusu
            top_k: Döndürülecek maksimum sonuç sayısı
            score_threshold: Bu değerin altındaki skorları filtrele (düşük = daha iyi)
            
        Returns:
            List of {text, metadata, score} dictionaries
        """
        if self.index.ntotal == 0:
            return []

        # Query embedding (normalize et - dokümanlarla aynı şekilde)
        query_embedding = self.embedding_model.embed_text(query)
        query_embedding = query_embedding.reshape(1, -1).astype('float32')
        query_embedding = self._normalize(query_embedding)

        # FAISS search
        distances, indices = self.index.search(query_embedding, min(top_k, self.index.ntotal))
        
        # Sonuçları formatla
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:  # FAISS bazen -1 döndürebilir
                continue
            
            if score_threshold is not None and dist > score_threshold:
                continue
            
            doc = self.documents[idx]
            results.append({
                "text": doc["text"],
                "metadata": doc["metadata"],
                "score": float(dist),  # Düşük = daha iyi (L2 distance)
                "id": doc["id"]
            })
        
        return results
    
    def save(self, path: str) -> None:
        """Index ve metadata'yı diske kaydet"""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # FAISS index kaydet
        faiss.write_index(self.index, str(path / "index.faiss"))

        # Metadata kaydet
        with open(path / "documents.json", "w", encoding="utf-8") as f:
            json.dump(self.documents, f, ensure_ascii=False, indent=2)

        # Index metadata kaydet (normalization flag dahil)
        index_metadata = {
            "normalized": True,
            "version": "2.0",
            "dimension": self.dimension,
            "model": self.embedding_model.model_name,
            "total_documents": len(self.documents)
        }
        with open(path / "index_metadata.json", "w", encoding="utf-8") as f:
            json.dump(index_metadata, f, ensure_ascii=False, indent=2)

        print(f"✅ Vector store kaydedildi: {path}")

    def load(self, path: str) -> bool:
        """
        Kaydedilmiş index ve metadata'yı yükle

        Returns:
            bool: True ise başarılı yükleme, False ise rebuild gerekiyor
        """
        path = Path(path)
        needs_rebuild = False

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
        else:
            # Eski format - metadata yok, muhtemelen normalize edilmemiş
            print("⚠️  index_metadata.json bulunamadı - eski format, rebuild önerilir")
            needs_rebuild = True

        if needs_rebuild:
            print("🔄 Eski index uyumsuz - rebuild gerekiyor!")
            return False

        # FAISS index yükle
        index_file = path / "index.faiss"
        if index_file.exists():
            self.index = faiss.read_index(str(index_file))

        # Metadata yükle
        docs_file = path / "documents.json"
        if docs_file.exists():
            with open(docs_file, "r", encoding="utf-8") as f:
                self.documents = json.load(f)

        return True
    
    def clear(self) -> None:
        """Tüm verileri temizle"""
        self.index = faiss.IndexFlatL2(self.dimension)
        self.documents = []
        print("✅ Vector store temizlendi")
    
    def __len__(self) -> int:
        return len(self.documents)
    
    def get_stats(self) -> Dict:
        """İstatistikleri döndür"""
        return {
            "total_documents": len(self.documents),
            "index_size": self.index.ntotal,
            "dimension": self.dimension,
            "model": self.embedding_model.model_name
        }
