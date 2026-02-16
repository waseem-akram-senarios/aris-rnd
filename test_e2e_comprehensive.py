#!/usr/bin/env python3
"""Comprehensive E2E test suite — validates all MCP tools + accuracy fixes."""
import json, requests, sys, time

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

print("=" * 65)
print("COMPREHENSIVE E2E + ACCURACY TEST SUITE")
print("=" * 65)

# ═══════════════════════════════════════════════════════════════
# Section 1: Service Health
# ═══════════════════════════════════════════════════════════════
print("\n--- 1. Service Health ---")
for svc, port in [("MCP", 8503), ("Retrieval", 8502), ("Gateway", 8500), ("Ingestion", 8501)]:
    try:
        r = requests.get(f"http://localhost:{port}/health", timeout=10)
        d = r.json()
        check(f"{svc} healthy", d.get("status") == "healthy", d.get("status"))
    except Exception as e:
        FAILED += 1
        print(f"  FAIL: {svc} health — {e}")

# ═══════════════════════════════════════════════════════════════
# Section 2: MCP Server Info & Tools
# ═══════════════════════════════════════════════════════════════
print("\n--- 2. MCP Server Info ---")
try:
    r = requests.get(f"{BASE}/info", timeout=10)
    info = r.json()
    check("Server info returns OK", r.status_code == 200)
    tools = info.get("tools", {})
    # tools is a dict with tool_name: description
    if isinstance(tools, dict):
        tool_names = sorted(tools.keys())
    elif isinstance(tools, list):
        tool_names = sorted([t.get("name", "") for t in tools])
    else:
        tool_names = []
    check("Has 7 tools", len(tool_names) == 7, f"got {len(tool_names)}: {tool_names}")
    check("Tools are Intelycx-pattern tools",
          "search_knowledge_base" in tool_names and "ingest_document" in tool_names,
          str(tool_names))
except Exception as e:
    FAILED += 1
    print(f"  FAIL: Server info — {e}")

# ═══════════════════════════════════════════════════════════════
# Section 3: Document Management (CRUD)
# ═══════════════════════════════════════════════════════════════
print("\n--- 3. Document Management ---")
try:
    r = requests.get(f"{BASE}/api/documents", timeout=10)
    check("List documents returns 200", r.status_code == 200)
    docs = r.json()
    if isinstance(docs, dict):
        doc_list = docs.get("documents", [])
    else:
        doc_list = docs
    check("Documents list is non-empty", len(doc_list) > 0, f"got {len(doc_list)} docs")
    
    if doc_list:
        doc_id = doc_list[0].get("document_id") or doc_list[0].get("id")
        if doc_id:
            r2 = requests.get(f"{BASE}/api/documents/{doc_id}", timeout=10)
            check("Get single document", r2.status_code == 200)
except Exception as e:
    FAILED += 1
    print(f"  FAIL: Documents — {e}")

# ═══════════════════════════════════════════════════════════════
# Section 4: Index Management
# ═══════════════════════════════════════════════════════════════
print("\n--- 4. Index Management ---")
try:
    r = requests.get(f"{BASE}/api/indexes", timeout=10)
    check("List indexes returns 200", r.status_code == 200)
    indexes = r.json()
    if isinstance(indexes, dict):
        idx_list = indexes.get("indexes", [])
    else:
        idx_list = indexes
    check("Indexes list is non-empty", len(idx_list) > 0, f"got {len(idx_list)}")
except Exception as e:
    FAILED += 1
    print(f"  FAIL: Indexes — {e}")

# ═══════════════════════════════════════════════════════════════
# Section 5: System Stats
# ═══════════════════════════════════════════════════════════════
print("\n--- 5. System Stats ---")
try:
    r = requests.get(f"{BASE}/api/stats", timeout=10)
    check("Stats returns 200", r.status_code == 200)
    stats_resp = r.json()
    # Stats may be nested under "stats" key
    stats = stats_resp.get("stats", stats_resp)
    proc = stats.get("processing", stats)
    doc_count = proc.get("total_documents") or stats.get("total_documents")
    check("Stats has document count", doc_count is not None,
          f"keys={list(stats.keys())[:5]}")
except Exception as e:
    FAILED += 1
    print(f"  FAIL: Stats — {e}")

# ═══════════════════════════════════════════════════════════════
# Section 6: Search + Accuracy (core tests)
# ═══════════════════════════════════════════════════════════════
print("\n--- 6. Search & Accuracy ---")
try:
    r = requests.post(f"{BASE}/api/search", json={
        "query": "what is LME approach for marine ecosystems",
        "k": 5,
        "response_language": "English"
    }, timeout=120)
    data = r.json()
    check("Search returns success", data.get("success") or data.get("status") == "success")
    
    cits = data.get("citations", [])
    check("Has citations", len(cits) > 0, f"got {len(cits)}")
    
    # F5: rerank_score flows through
    has_rerank = any(c.get("rerank_score") is not None for c in cits)
    check("F5: rerank_score present in citations", has_rerank)
    
    # F2: Confidence percentages descending
    pcts = [c.get("confidence_percentage", 0) for c in cits]
    is_desc = all(pcts[j] >= pcts[j+1] for j in range(len(pcts)-1))
    check("F2: Confidence percentages descending", is_desc, str(pcts))
    
    # F1+F6: Top citation has highest rerank_score
    if has_rerank:
        reranks = [c.get("rerank_score") for c in cits if c.get("rerank_score") is not None]
        top_rs = cits[0].get("rerank_score")
        if top_rs is not None and len(reranks) > 1:
            check("F1+F6: Top citation has best rerank_score",
                  top_rs >= max(reranks) - 0.001,
                  f"top={top_rs:.4f}, max={max(reranks):.4f}")
    
    # F3: No similarity_score > 1.0
    all_scores = []
    for c in cits:
        meta = c.get("metadata", {})
        ss = meta.get("similarity_score")
        if ss is not None:
            all_scores.append(ss)
    scores_ok = all(s <= 1.01 for s in all_scores) if all_scores else True
    check("F3: No similarity_score > 1.0", scores_ok, str(all_scores))
    
    # Top citation should have high confidence
    if cits:
        top_pct = cits[0].get("confidence_percentage", 0)
        check("Top citation confidence >= 90%", top_pct >= 90, f"got {top_pct}%")
    
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
    print(f"  FAIL: Search — {e}")

# ═══════════════════════════════════════════════════════════════
# Section 7: Language correctness
# ═══════════════════════════════════════════════════════════════
print("\n--- 7. Language Correctness ---")
try:
    r = requests.post(f"{BASE}/api/search", json={
        "query": "fetch me details from page 14",
        "k": 3,
        "response_language": "English"
    }, timeout=120)
    data = r.json()
    answer = data.get("answer", "")
    swedish_words = ["och", "för", "det", "som", "att", "med", "den"]
    first_100 = answer[:100].lower()
    swedish_count = sum(1 for w in swedish_words if f" {w} " in f" {first_100} ")
    check("Answer is English (not Swedish)", swedish_count < 3,
          f"Found {swedish_count} Swedish words")
except Exception as e:
    FAILED += 1
    print(f"  FAIL: Language test — {e}")

# ═══════════════════════════════════════════════════════════════
# Section 8: Input Validation
# ═══════════════════════════════════════════════════════════════
print("\n--- 8. Input Validation ---")
try:
    r = requests.post(f"{BASE}/api/search", json={}, timeout=10)
    check("Empty search body returns 400", r.status_code == 400)
except Exception as e:
    FAILED += 1
    print(f"  FAIL: Validation — {e}")

# ═══════════════════════════════════════════════════════════════
# Section 9: UI Accessibility
# ═══════════════════════════════════════════════════════════════
print("\n--- 9. UI Accessibility ---")
try:
    r = requests.get("http://localhost:80/_stcore/health", timeout=10)
    check("Streamlit UI healthy", r.text.strip() == "ok")
except Exception as e:
    FAILED += 1
    print(f"  FAIL: UI — {e}")

# ═══════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
total = PASSED + FAILED
print(f"RESULTS: {PASSED}/{total} passed, {FAILED} failed")
if FAILED == 0:
    print("ALL E2E + ACCURACY TESTS PASSED!")
else:
    print(f"WARNING: {FAILED} test(s) failed")
print("=" * 65)

sys.exit(0 if FAILED == 0 else 1)
