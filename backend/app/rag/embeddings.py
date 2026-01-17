"""
Embedding Module
Metin verilerini vektörlere dönüştürme
"""

from sentence_transformers import SentenceTransformer
from typing import List, Union
import numpy as np


class EmbeddingModel:
    """
    Sentence Transformers ile metin embedding
    İngilizce tıbbi metinler için optimize edilmiş
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Args:
            model_name: Kullanılacak model. Seçenekler:
                - "all-MiniLM-L6-v2": Hızlı, genel amaçlı (384 dim)
                - "all-mpnet-base-v2": Daha kaliteli, yavaş (768 dim)
                - "pritamdeka/S-PubMedBert-MS-MARCO": Tıbbi metinler için
        """
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        print(f"✅ Embedding model yüklendi: {model_name} (dim: {self.dimension})")
    
    def embed_text(self, text: str) -> np.ndarray:
        """Tek bir metni vektöre dönüştür"""
        return self.model.encode(text, convert_to_numpy=True)
    
    def embed_texts(self, texts: List[str], batch_size: int = 32, show_progress: bool = True) -> np.ndarray:
        """Birden fazla metni vektörlere dönüştür"""
        return self.model.encode(
            texts, 
            batch_size=batch_size, 
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )
    
    def get_dimension(self) -> int:
        """Embedding boyutunu döndür"""
        return self.dimension


# Singleton instance - lazy loading
_embedding_model = None

def get_embedding_model(model_name: str = "all-MiniLM-L6-v2") -> EmbeddingModel:
    """Singleton embedding model instance döndür"""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = EmbeddingModel(model_name)
    return _embedding_model
