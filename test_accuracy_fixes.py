#!/usr/bin/env python3
"""Accuracy fix verification — tests all 6 fixes."""
import json
import requests
import sys

BASE = "http://localhost:8503"
PASSED = 0
FAILED = 0

def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS: {name}")
    else:
        FAILED += 1
        print(f"  FAIL: {name} — {detail}")

print("=" * 60)
print("ACCURACY FIX VERIFICATION")
print("=" * 60)

# --- Test 1: Search and check citation pipeline ---
print("\n--- Test 1: Citation pipeline (rerank_score, ordering, percentages) ---")
try:
    r = requests.post(f"{BASE}/api/search", json={
        "query": "what is LME approach for marine ecosystems",
        "k": 5,
        "response_language": "English"
    }, timeout=120)
    data = r.json()
    check("Search returned success", data.get("success") or data.get("status") == "success")
    
    cits = data.get("citations", [])
    check("Has citations", len(cits) > 0, f"got {len(cits)}")
    
    # F5: Check rerank_score is present in citations
    has_rerank = any(c.get("rerank_score") is not None for c in cits)
    check("F5: rerank_score flows through citations", has_rerank,
          "No citation has rerank_score — FlashRank may not be reranking")
    
    # F2: Check confidence percentages are descending (MCP no longer re-sorts)
    pcts = [c.get("confidence_percentage", 0) for c in cits]
    is_desc = all(pcts[i] >= pcts[i+1] for i in range(len(pcts)-1))
    check("F2: Confidence percentages descending (order preserved)", is_desc,
          f"percentages: {pcts}")
    
    # F1+F6: If rerank_score is present, the highest should map to the highest confidence
    if has_rerank:
        reranks = [c.get("rerank_score") for c in cits if c.get("rerank_score") is not None]
        top_cit = cits[0]
        top_rs = top_cit.get("rerank_score")
        if top_rs is not None and len(reranks) > 1:
            check("F1+F6: Top citation has highest rerank_score",
                  top_rs >= max(reranks) - 0.001,
                  f"top={top_rs}, max={max(reranks)}")
    
    # F3: No similarity_score should be > 1.0 (position fallback was producing 0.5-1.5)
    all_scores = []
    for c in cits:
        meta = c.get("metadata", {})
        ss = meta.get("similarity_score")
        if ss is not None:
            all_scores.append(ss)
    scores_ok = all(s <= 1.01 for s in all_scores) if all_scores else True
    check("F3: No similarity_score > 1.0 (position fallback fix)",
          scores_ok, f"scores: {all_scores}")
    
    # Print citation details
    print("\n  Citation details:")
    for i, c in enumerate(cits[:5]):
        pct = c.get("confidence_percentage", 0)
        src = str(c.get("source", "?"))[:40]
        pg = c.get("page", "?")
        rs = c.get("rerank_score")
        rs_str = f"{rs:.4f}" if rs else "None"
        print(f"    #{i+1} [{pct}%] {src} pg={pg} rerank={rs_str}")
        
except Exception as e:
    FAILED += 1
    print(f"  FAIL: Search request failed — {e}")

# --- Test 2: Answer language ---
print("\n--- Test 2: Answer language (should be English) ---")
try:
    r = requests.post(f"{BASE}/api/search", json={
        "query": "fetch me details from page 14",
        "k": 3,
        "response_language": "English"
    }, timeout=120)
    data = r.json()
    answer = data.get("answer", "")
    # Check it's not in Swedish (old bug)
    swedish_words = ["och", "för", "det", "som", "att", "med", "den"]
    first_100 = answer[:100].lower()
    swedish_count = sum(1 for w in swedish_words if f" {w} " in f" {first_100} ")
    check("Answer is in English (not Swedish)", swedish_count < 3,
          f"Found {swedish_count} Swedish words in first 100 chars")
except Exception as e:
    FAILED += 1
    print(f"  FAIL: Language test failed — {e}")

# --- Test 3: MCP health shows accuracy features ---
print("\n--- Test 3: MCP health shows accuracy features ---")
try:
    r = requests.get(f"{BASE}/health", timeout=10)
    data = r.json()
    feats = data.get("accuracy_features", {})
    check("Reranking enabled", feats.get("reranking") is True)
    check("Hybrid search enabled", feats.get("hybrid_search") is True)
except Exception as e:
    FAILED += 1
    print(f"  FAIL: Health check failed — {e}")

# --- Summary ---
print("\n" + "=" * 60)
total = PASSED + FAILED
print(f"RESULTS: {PASSED}/{total} passed, {FAILED} failed")
if FAILED == 0:
    print("ALL ACCURACY TESTS PASSED!")
else:
    print(f"WARNING: {FAILED} test(s) failed")
print("=" * 60)

sys.exit(0 if FAILED == 0 else 1)
