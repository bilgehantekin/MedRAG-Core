#!/usr/bin/env python3
"""
RAG Evaluation Script

Evaluates the RAG system against a test set of Turkish medical questions.
Tests emergency detection, source retrieval, and response quality.

Usage:
    python -m scripts.evaluate_rag [--verbose] [--limit N]
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from functools import partial

# Force unbuffered output
print = partial(print, flush=True)

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.knowledge_base import MedicalKnowledgeBase
from app.rag.rag_chain import RAGChain


def load_test_set(path: Path) -> List[Dict]:
    """Load evaluation test set"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def evaluate_emergency_detection(
    rag_chain: RAGChain,
    test_cases: List[Dict],
    verbose: bool = False
) -> Dict:
    """
    Evaluate emergency detection accuracy

    Returns:
        {
            "total": int,
            "correct": int,
            "accuracy": float,
            "false_positives": List[Dict],
            "false_negatives": List[Dict]
        }
    """
    total = 0
    correct = 0
    false_positives = []
    false_negatives = []

    for test in test_cases:
        expected_emergency = test["expected_safety_level"] == "emergency"
        question = test["question_en"]

        # Get search results
        results = rag_chain.knowledge_base.search(question, top_k=5)
        emergency_check = rag_chain._check_emergency(results)
        detected_emergency = emergency_check["is_emergency"]

        total += 1

        if detected_emergency == expected_emergency:
            correct += 1
            if verbose:
                print(f"✅ {test['id']}: {'EMERGENCY' if expected_emergency else 'normal'} - {test['question_tr'][:40]}...")
        else:
            if detected_emergency and not expected_emergency:
                false_positives.append({
                    "id": test["id"],
                    "question": test["question_tr"],
                    "expected": test["expected_safety_level"],
                    "sources": [r["metadata"].get("title") for r in results[:3]]
                })
                if verbose:
                    print(f"❌ FP {test['id']}: Detected emergency but expected {test['expected_safety_level']}")
            else:
                false_negatives.append({
                    "id": test["id"],
                    "question": test["question_tr"],
                    "expected": test["expected_safety_level"],
                    "sources": [r["metadata"].get("title") for r in results[:3]]
                })
                if verbose:
                    print(f"❌ FN {test['id']}: Missed emergency - {test['question_tr'][:40]}...")

    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total > 0 else 0,
        "false_positives": false_positives,
        "false_negatives": false_negatives
    }


def evaluate_source_retrieval(
    rag_chain: RAGChain,
    test_cases: List[Dict],
    verbose: bool = False
) -> Dict:
    """
    Evaluate if relevant sources are retrieved

    Returns:
        {
            "total": int,
            "with_sources": int,
            "avg_source_count": float,
            "category_match": int
        }
    """
    total = 0
    with_sources = 0
    total_sources = 0
    category_match = 0

    for test in test_cases:
        question = test["question_en"]
        expected_category = test["category"]

        results = rag_chain.knowledge_base.search(question, top_k=5)

        total += 1

        if results:
            with_sources += 1
            total_sources += len(results)

            # Check if any result matches expected category
            categories = [r["metadata"].get("category", "") for r in results]
            if expected_category in categories or any(expected_category in c for c in categories):
                category_match += 1
                if verbose:
                    print(f"✅ {test['id']}: Found {len(results)} sources, category match")
            else:
                if verbose:
                    print(f"⚠️  {test['id']}: Found {len(results)} sources but no category match (expected: {expected_category}, got: {categories[:3]})")
        else:
            if verbose:
                print(f"❌ {test['id']}: No sources found")

    return {
        "total": total,
        "with_sources": with_sources,
        "avg_source_count": total_sources / total if total > 0 else 0,
        "category_match": category_match,
        "category_match_rate": category_match / total if total > 0 else 0
    }


def evaluate_source_urls(
    rag_chain: RAGChain,
    test_cases: List[Dict],
    verbose: bool = False
) -> Dict:
    """
    Evaluate source URL availability

    Returns:
        {
            "total_queries": int,
            "queries_with_urls": int,
            "url_coverage": float
        }
    """
    total = 0
    with_urls = 0

    for test in test_cases:
        question = test["question_en"]
        results = rag_chain.knowledge_base.search(question, top_k=5)

        total += 1

        urls = [r["metadata"].get("source_url", "") for r in results if r["metadata"].get("source_url")]
        if urls:
            with_urls += 1
            if verbose:
                print(f"✅ {test['id']}: {len(urls)} source URLs available")
        else:
            if verbose:
                print(f"⚠️  {test['id']}: No source URLs")

    return {
        "total_queries": total,
        "queries_with_urls": with_urls,
        "url_coverage": with_urls / total if total > 0 else 0
    }


def run_evaluation(
    test_set_path: Path,
    verbose: bool = False,
    limit: int = None
) -> Dict:
    """Run full evaluation suite"""

    print("=" * 60)
    print("RAG System Evaluation")
    print("=" * 60)

    # Load test set
    print("\n📁 Loading test set...")
    test_cases = load_test_set(test_set_path)
    if limit:
        test_cases = test_cases[:limit]
    print(f"   Loaded {len(test_cases)} test cases")

    # Initialize RAG
    print("\n🔧 Initializing RAG system...")
    kb = MedicalKnowledgeBase()
    kb.load_default_knowledge()
    rag = RAGChain(knowledge_base=kb)
    print(f"   Knowledge base: {len(kb.vector_store)} documents")

    # Run evaluations
    results = {}

    # 1. Emergency Detection
    print("\n" + "=" * 40)
    print("📊 Evaluation 1: Emergency Detection")
    print("=" * 40)
    emergency_results = evaluate_emergency_detection(rag, test_cases, verbose)
    results["emergency_detection"] = emergency_results
    print(f"\n   Accuracy: {emergency_results['accuracy']:.1%} ({emergency_results['correct']}/{emergency_results['total']})")
    print(f"   False Positives: {len(emergency_results['false_positives'])}")
    print(f"   False Negatives: {len(emergency_results['false_negatives'])}")

    if emergency_results['false_negatives']:
        print("\n   ⚠️  CRITICAL - Missed emergencies:")
        for fn in emergency_results['false_negatives'][:5]:
            print(f"      - {fn['id']}: {fn['question'][:50]}...")

    # 2. Source Retrieval
    print("\n" + "=" * 40)
    print("📊 Evaluation 2: Source Retrieval")
    print("=" * 40)
    retrieval_results = evaluate_source_retrieval(rag, test_cases, verbose)
    results["source_retrieval"] = retrieval_results
    print(f"\n   Queries with sources: {retrieval_results['with_sources']}/{retrieval_results['total']}")
    print(f"   Avg sources per query: {retrieval_results['avg_source_count']:.1f}")
    print(f"   Category match rate: {retrieval_results['category_match_rate']:.1%}")

    # 3. Source URLs
    print("\n" + "=" * 40)
    print("📊 Evaluation 3: Source URLs")
    print("=" * 40)
    url_results = evaluate_source_urls(rag, test_cases, verbose)
    results["source_urls"] = url_results
    print(f"\n   Queries with URLs: {url_results['queries_with_urls']}/{url_results['total_queries']}")
    print(f"   URL coverage: {url_results['url_coverage']:.1%}")

    # Summary
    print("\n" + "=" * 60)
    print("📋 EVALUATION SUMMARY")
    print("=" * 60)

    # Overall score
    emergency_score = emergency_results['accuracy'] * 100
    retrieval_score = retrieval_results['category_match_rate'] * 100
    url_score = url_results['url_coverage'] * 100

    overall = (emergency_score + retrieval_score + url_score) / 3

    print(f"\n   Emergency Detection:  {emergency_score:.0f}%")
    print(f"   Category Matching:    {retrieval_score:.0f}%")
    print(f"   Source URL Coverage:  {url_score:.0f}%")
    print(f"   ─────────────────────────────")
    print(f"   OVERALL SCORE:        {overall:.0f}%")

    # Recommendations
    print("\n📝 Recommendations:")
    if len(emergency_results['false_negatives']) > 0:
        print("   ⚠️  CRITICAL: Fix false negatives in emergency detection")
    if retrieval_results['category_match_rate'] < 0.7:
        print("   ⚠️  Improve semantic search relevance")
    if url_results['url_coverage'] < 0.8:
        print("   ℹ️  Add more source URLs to knowledge base")

    print("\n" + "=" * 60)

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Evaluate RAG system')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    parser.add_argument('--limit', '-n', type=int, help='Limit number of test cases')

    args = parser.parse_args()

    test_set_path = Path(__file__).parent.parent / "data" / "medical_knowledge" / "evaluation_test_set.json"

    if not test_set_path.exists():
        print(f"Error: Test set not found at {test_set_path}")
        return 1

    results = run_evaluation(test_set_path, verbose=args.verbose, limit=args.limit)

    return 0


if __name__ == '__main__':
    sys.exit(main())
