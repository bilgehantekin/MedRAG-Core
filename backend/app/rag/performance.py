"""
Performance Optimization Module
Profiling, Caching, and Performance Utilities
"""

import time
import hashlib
from typing import Dict, List, Optional, Any, Callable
from functools import lru_cache
from collections import OrderedDict
import threading


class TimingContext:
    """Context manager for timing code blocks"""

    def __init__(self, name: str, timings: Dict[str, float]):
        self.name = name
        self.timings = timings
        self.start = None

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        elapsed = (time.perf_counter() - self.start) * 1000  # ms
        self.timings[self.name] = elapsed


class RequestProfiler:
    """
    Request-level profiler for tracking execution time of each pipeline stage.

    Usage:
        profiler = RequestProfiler()
        with profiler.time("embedding"):
            # embedding code
        with profiler.time("search"):
            # search code
        print(profiler.report())
    """

    def __init__(self):
        self.timings: Dict[str, float] = {}
        self.start_time = time.perf_counter()

    def time(self, stage: str) -> TimingContext:
        """Create a timing context for a stage"""
        return TimingContext(stage, self.timings)

    def add_timing(self, stage: str, elapsed_ms: float):
        """Manually add a timing"""
        self.timings[stage] = elapsed_ms

    def total_time(self) -> float:
        """Get total elapsed time in ms"""
        return (time.perf_counter() - self.start_time) * 1000

    def report(self) -> Dict[str, Any]:
        """Generate timing report"""
        total = self.total_time()
        report = {
            "timings_ms": self.timings.copy(),
            "total_ms": round(total, 2),
            "breakdown_pct": {}
        }

        # Calculate percentages
        for stage, ms in self.timings.items():
            report["breakdown_pct"][stage] = round((ms / total) * 100, 1) if total > 0 else 0

        return report

    def log_summary(self, prefix: str = "[PERF]"):
        """Print a concise timing summary"""
        total = self.total_time()
        parts = [f"{prefix} TOTAL={total:.0f}ms"]

        # Sort by time (descending)
        sorted_timings = sorted(self.timings.items(), key=lambda x: x[1], reverse=True)
        for stage, ms in sorted_timings:
            pct = (ms / total) * 100 if total > 0 else 0
            parts.append(f"{stage}={ms:.0f}ms({pct:.0f}%)")

        print(" | ".join(parts))


class LRUCache:
    """
    Thread-safe LRU Cache with TTL support.

    Used for caching:
    - Query embeddings (same query = same embedding)
    - Retrieval results (same query = same top-k results)
    """

    def __init__(self, maxsize: int = 500, ttl_seconds: float = 300):
        """
        Args:
            maxsize: Maximum number of items in cache
            ttl_seconds: Time-to-live for cache entries (default 5 minutes)
        """
        self.maxsize = maxsize
        self.ttl = ttl_seconds
        self.cache: OrderedDict = OrderedDict()
        self.timestamps: Dict[str, float] = {}
        self.lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def _make_key(self, key: Any) -> str:
        """Create a hashable key from input"""
        if isinstance(key, str):
            return hashlib.md5(key.encode()).hexdigest()
        elif isinstance(key, (list, tuple)):
            return hashlib.md5(str(key).encode()).hexdigest()
        else:
            return hashlib.md5(str(key).encode()).hexdigest()

    def get(self, key: Any) -> Optional[Any]:
        """Get item from cache"""
        hash_key = self._make_key(key)

        with self.lock:
            if hash_key not in self.cache:
                self.misses += 1
                return None

            # Check TTL
            if time.time() - self.timestamps[hash_key] > self.ttl:
                del self.cache[hash_key]
                del self.timestamps[hash_key]
                self.misses += 1
                return None

            # Move to end (most recently used)
            self.cache.move_to_end(hash_key)
            self.hits += 1
            return self.cache[hash_key]

    def set(self, key: Any, value: Any):
        """Set item in cache"""
        hash_key = self._make_key(key)

        with self.lock:
            if hash_key in self.cache:
                self.cache.move_to_end(hash_key)
            else:
                if len(self.cache) >= self.maxsize:
                    # Remove oldest item
                    oldest_key = next(iter(self.cache))
                    del self.cache[oldest_key]
                    del self.timestamps[oldest_key]

            self.cache[hash_key] = value
            self.timestamps[hash_key] = time.time()

    def clear(self):
        """Clear all cache entries"""
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()
            self.hits = 0
            self.misses = 0

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "size": len(self.cache),
            "maxsize": self.maxsize,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_pct": round(hit_rate, 1)
        }


# Global cache instances
_embedding_cache: Optional[LRUCache] = None
_retrieval_cache: Optional[LRUCache] = None


def get_embedding_cache() -> LRUCache:
    """Get singleton embedding cache"""
    global _embedding_cache
    if _embedding_cache is None:
        _embedding_cache = LRUCache(maxsize=1000, ttl_seconds=600)  # 10 min TTL
    return _embedding_cache


def get_retrieval_cache() -> LRUCache:
    """Get singleton retrieval cache"""
    global _retrieval_cache
    if _retrieval_cache is None:
        _retrieval_cache = LRUCache(maxsize=500, ttl_seconds=300)  # 5 min TTL
    return _retrieval_cache


def clear_all_caches():
    """Clear all performance caches"""
    if _embedding_cache:
        _embedding_cache.clear()
    if _retrieval_cache:
        _retrieval_cache.clear()
    print("✅ All caches cleared")


def get_cache_stats() -> Dict[str, Any]:
    """Get statistics for all caches"""
    return {
        "embedding_cache": get_embedding_cache().stats(),
        "retrieval_cache": get_retrieval_cache().stats()
    }


# Category classification for pre-filtering
CATEGORY_KEYWORDS = {
    "medications": {
        "tr": ["ilaç", "tablet", "hap", "şurup", "kapsül", "doz", "kullanım", "yan etki",
               "etkileşim", "prospektüs", "reçete", "mg", "ml", "günde"],
        "en": ["drug", "medicine", "medication", "tablet", "pill", "dosage", "dose",
               "side effect", "interaction", "prescription"]
    },
    "symptoms": {
        "tr": ["ağrı", "acı", "şiş", "şişlik", "kaşıntı", "kızarıklık", "ateş", "bulantı",
               "kusma", "baş dönmesi", "halsizlik", "yorgunluk", "uykusuzluk"],
        "en": ["pain", "ache", "swelling", "itching", "rash", "fever", "nausea",
               "vomiting", "dizziness", "fatigue", "weakness", "insomnia"]
    },
    "diseases": {
        "tr": ["hastalık", "sendrom", "rahatsızlık", "enfeksiyon", "virüs", "bakteri",
               "kanser", "diyabet", "tansiyon", "kalp", "astım"],
        "en": ["disease", "syndrome", "disorder", "infection", "virus", "bacteria",
               "cancer", "diabetes", "hypertension", "heart", "asthma"]
    },
    "emergency": {
        "tr": ["acil", "kalp krizi", "felç", "nöbet", "bayılma", "kaza", "zehirlenme",
               "nefes alamıyorum", "göğüs ağrısı", "kanaması durmuyor"],
        "en": ["emergency", "heart attack", "stroke", "seizure", "faint", "unconscious",
               "poisoning", "cannot breathe", "chest pain", "severe bleeding"]
    },
    "mental_health": {
        "tr": ["depresyon", "anksiyete", "kaygı", "panik", "stres", "intihar", "psikoloji",
               "ruh sağlığı", "terapi", "psikiyatri"],
        "en": ["depression", "anxiety", "panic", "stress", "suicide", "psychology",
               "mental health", "therapy", "psychiatry"]
    }
}


def predict_category(query: str) -> Optional[str]:
    """
    Predict the most likely category for a query.
    Returns None if no strong signal (use all categories).

    This enables pre-filtering to reduce search space.
    """
    query_lower = query.lower()
    scores = {}

    for category, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        all_keywords = keywords.get("tr", []) + keywords.get("en", [])

        for kw in all_keywords:
            if kw in query_lower:
                # Longer keywords get higher scores
                score += len(kw.split())

        if score > 0:
            scores[category] = score

    if not scores:
        return None

    # Return category with highest score (if significant)
    best_category = max(scores, key=scores.get)

    # Only return if score is meaningful (at least 2 points)
    if scores[best_category] >= 2:
        return best_category

    return None
