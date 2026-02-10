#!/usr/bin/env python3
"""
Comprehensive Citation Accuracy & Page Number Test Suite
Tests documents from docs/testing/ for:
  1. Source attribution accuracy (correct document cited)
  2. Page number accuracy
  3. Citation metadata completeness (document_id, page_confidence, etc.)
  4. Content relevance (snippet matches query intent)
"""

import json
import subprocess
import sys
import time
import os
from dataclasses import dataclass, field
from typing import Optional

# ─── Configuration ───────────────────────────────────────────────────────────
PEM_FILE = os.path.join(os.path.dirname(__file__), "..", "scripts", "ec2_wah_pk.pem")
SERVER_HOST = "44.221.84.58"
MCP_PORT = 8503

# Document registry: filename -> document_id (from ingestion)
DOCUMENTS = {
    "END_TO_END_TEST_FINAL_REPORT.md": "357fdedc-3a7d-429a-8402-b27777403418",
    "END_TO_END_TEST_RESULTS.md":      "c3a7092f-705a-4176-b96b-eedcb4afe96b",
    "END_TO_END_TEST_REPORT.txt":      "98ba3682-3726-4d05-b72d-2b4c0aacac73",
    "FINAL_TEST_REPORT.txt":           "d295cc39-06a1-415c-be25-6766827905ee",
    "FIXES_AND_TESTING_COMPLETE.txt":   "141d2c98-f0be-40cb-9bae-5a4f83b11caa",
    "RAG_OPTIONS_TEST_GUIDE.txt":       "d6d6b6e3-ab27-4327-b9a0-d08510156cab",
    "TESTING_GUIDE.txt":                "f72ff53a-239a-4774-8f60-8ac39ce9de34",
}

# Queries mapped to expected sources (filename substrings that SHOULD appear)
# and keywords that MUST appear in the retrieved content
TEST_QUERIES = [
    {
        "id": "Q1",
        "query": "What is the container status and port configuration for the application?",
        "expected_sources": ["END_TO_END_TEST_FINAL_REPORT", "END_TO_END_TEST_RESULTS", "FINAL_TEST_REPORT"],
        "expected_keywords": ["aris-rag-app", "80", "8501", "healthy"],
        "description": "Container & port info (multi-doc)"
    },
    {
        "id": "Q2",
        "query": "What parsers are available and what are their processing times?",
        "expected_sources": ["RAG_OPTIONS_TEST_GUIDE", "TESTING_GUIDE"],
        "expected_keywords": ["docling", "pymupdf"],
        "description": "Parser details (RAG Options Guide)"
    },
    {
        "id": "Q3",
        "query": "What are the chunking strategies Precise Balanced and Comprehensive and what chunk sizes do they use?",
        "expected_sources": ["RAG_OPTIONS_TEST_GUIDE"],
        "expected_keywords": ["precise", "balanced", "comprehensive", "chunk"],
        "description": "Chunking strategies (RAG Options Guide)"
    },
    {
        "id": "Q4",
        "query": "What fixes were applied for Docling no fallback when explicitly selected?",
        "expected_sources": ["FIXES_AND_TESTING_COMPLETE"],
        "expected_keywords": ["docling", "fallback", "parser_factory"],
        "description": "Docling fix details (Fixes doc)"
    },
    {
        "id": "Q5",
        "query": "What Nginx proxy_read_timeout and proxy_send_timeout settings were configured for Docling processing?",
        "expected_sources": ["FIXES_AND_TESTING_COMPLETE"],
        "expected_keywords": ["nginx", "1200", "timeout"],
        "description": "Nginx timeouts (Fixes doc)"
    },
    {
        "id": "Q6",
        "query": "What are the enhanced logging messages during Docling processing?",
        "expected_sources": ["END_TO_END_TEST_FINAL_REPORT", "END_TO_END_TEST_REPORT"],
        "expected_keywords": ["docling", "conversion", "markdown"],
        "description": "Enhanced logging messages"
    },
    {
        "id": "Q7",
        "query": "What embedding models are available and what are their dimensions?",
        "expected_sources": ["RAG_OPTIONS_TEST_GUIDE"],
        "expected_keywords": ["embedding", "1536", "3072"],
        "description": "Embedding models (RAG Options Guide)"
    },
    {
        "id": "Q8",
        "query": "How to monitor Docling processing on the server using SSH?",
        "expected_sources": ["TESTING_GUIDE", "END_TO_END_TEST_FINAL_REPORT"],
        "expected_keywords": ["ssh", "docker logs", "docling"],
        "description": "SSH monitoring (Testing Guide)"
    },
    {
        "id": "Q9",
        "query": "What are the test scenarios listed in the complete test matrix?",
        "expected_sources": ["RAG_OPTIONS_TEST_GUIDE"],
        "expected_keywords": ["scenario", "fast processing", "quality"],
        "description": "Test matrix scenarios"
    },
    {
        "id": "Q10",
        "query": "What components were tested for importability and what was the result?",
        "expected_sources": ["END_TO_END_TEST_FINAL_REPORT", "END_TO_END_TEST_RESULTS", "FINAL_TEST_REPORT"],
        "expected_keywords": ["parserfactory", "doclingparser", "documentprocessor", "import"],
        "description": "Component import tests"
    },
]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def ssh_cmd(cmd: str, timeout: int = 30) -> str:
    """Run a command on the remote server via SSH."""
    full_cmd = [
        "ssh", "-i", PEM_FILE,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        f"ec2-user@{SERVER_HOST}",
        cmd
    ]
    result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
    return result.stdout


def init_mcp_session() -> str:
    """Initialize an MCP session and return the session ID."""
    raw = ssh_cmd(
        f'curl -s -D- -X POST http://localhost:{MCP_PORT}/mcp '
        f'-H "Content-Type: application/json" '
        f'-H "Accept: application/json, text/event-stream" '
        f'-d \'{{"jsonrpc":"2.0","id":1,"method":"initialize","params":{{"protocolVersion":"2025-03-26","capabilities":{{}},"clientInfo":{{"name":"accuracy-test","version":"1.0"}}}}}}\'',
        timeout=15,
    )
    for line in raw.splitlines():
        if line.lower().startswith("mcp-session-id"):
            session_id = line.split(":", 1)[1].strip()
            # Send initialized notification
            ssh_cmd(
                f'curl -s -X POST http://localhost:{MCP_PORT}/mcp '
                f'-H "Content-Type: application/json" '
                f'-H "Accept: application/json, text/event-stream" '
                f'-H "Mcp-Session-Id: {session_id}" '
                f'-d \'{{"jsonrpc":"2.0","method":"notifications/initialized"}}\'',
                timeout=10,
            )
            return session_id
    raise RuntimeError(f"Could not obtain MCP session ID. Raw response:\n{raw[:500]}")


def mcp_query(session_id: str, query: str, k: int = 5) -> dict:
    """Execute a rag_quick_query via MCP and return parsed result."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 200,
        "method": "tools/call",
        "params": {
            "name": "rag_quick_query",
            "arguments": {"query": query, "k": k},
        },
    })
    raw = ssh_cmd(
        f"curl -s -X POST http://localhost:{MCP_PORT}/mcp "
        f"-H 'Content-Type: application/json' "
        f"-H 'Accept: application/json, text/event-stream' "
        f"-H 'Mcp-Session-Id: {session_id}' "
        f"-d '{payload}'",
        timeout=60,
    )
    # Parse SSE response
    for line in raw.splitlines():
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                text = data.get("result", {}).get("content", [{}])[0].get("text", "{}")
                return json.loads(text)
            except (json.JSONDecodeError, IndexError, KeyError):
                continue
    return {"error": "No parseable response", "raw": raw[:500]}


@dataclass
class TestResult:
    query_id: str
    description: str
    query: str
    passed: bool = True
    source_match: bool = True
    page_valid: bool = True
    has_document_id: bool = True
    has_page_confidence: bool = True
    has_extraction_method: bool = True
    keyword_hit_ratio: float = 0.0
    total_citations: int = 0
    matched_sources: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    citations_detail: list = field(default_factory=list)


# ─── Main Test Runner ────────────────────────────────────────────────────────

def run_tests():
    print("=" * 80)
    print("  CITATION ACCURACY & PAGE NUMBER TEST SUITE")
    print("  Documents: docs/testing/ (7 files)")
    print("=" * 80)
    print()

    # 1. Init MCP session
    print("[1/3] Initializing MCP session...", end=" ", flush=True)
    session_id = init_mcp_session()
    print(f"OK (session: {session_id[:12]}...)")
    print()

    # 2. Run queries
    print(f"[2/3] Running {len(TEST_QUERIES)} test queries...")
    print("-" * 80)
    results: list[TestResult] = []

    for tq in TEST_QUERIES:
        qid = tq["id"]
        query = tq["query"]
        expected_sources = tq["expected_sources"]
        expected_keywords = tq["expected_keywords"]
        desc = tq["description"]

        print(f"\n  {qid}: {desc}")
        print(f"       Query: {query[:70]}...")

        resp = mcp_query(session_id, query, k=5)
        tr = TestResult(query_id=qid, description=desc, query=query)

        if "error" in resp and resp.get("total_results", 1) == 0:
            tr.passed = False
            tr.source_match = False
            tr.issues.append(f"Query returned error/no results: {resp.get('error', 'unknown')}")
            results.append(tr)
            print(f"       FAIL: No results returned")
            continue

        citations = resp.get("citations", [])
        tr.total_citations = len(citations)

        if tr.total_citations == 0:
            tr.passed = False
            tr.source_match = False
            tr.issues.append("Zero citations returned")
            results.append(tr)
            print(f"       FAIL: Zero citations")
            continue

        # Evaluate each citation
        keyword_hits = set()
        source_matched = False

        for i, cit in enumerate(citations):
            source = cit.get("source", "")
            doc_id = cit.get("document_id")
            page = cit.get("page")
            page_conf = cit.get("page_confidence")
            page_ext_method = cit.get("page_extraction_method")
            content = cit.get("content", "").lower()
            snippet = cit.get("snippet", "").lower()
            combined_text = content + " " + snippet

            cit_detail = {
                "index": i + 1,
                "source": source,
                "document_id": doc_id,
                "page": page,
                "page_confidence": page_conf,
                "page_extraction_method": page_ext_method,
                "content_type": cit.get("content_type"),
                "source_confidence": cit.get("source_confidence"),
                "confidence": cit.get("confidence"),
            }
            tr.citations_detail.append(cit_detail)

            # Check source match
            for exp_src in expected_sources:
                if exp_src.lower() in source.lower():
                    source_matched = True
                    if source not in tr.matched_sources:
                        tr.matched_sources.append(source)
                    break

            # Check keywords in content/snippet
            for kw in expected_keywords:
                if kw.lower() in combined_text:
                    keyword_hits.add(kw.lower())

            # Validate page number (should be >= 1 for single-page docs)
            if page is None or page < 1:
                tr.page_valid = False
                tr.issues.append(f"Citation {i+1}: Invalid page number: {page}")

            # Validate document_id exists
            if not doc_id:
                tr.has_document_id = False
                tr.issues.append(f"Citation {i+1}: Missing document_id")

            # Validate page_confidence
            if page_conf is None:
                tr.has_page_confidence = False

            # Validate page_extraction_method
            if not page_ext_method or page_ext_method == "unknown":
                tr.has_extraction_method = False

        tr.source_match = source_matched
        if not source_matched:
            tr.issues.append(f"No citation matched expected sources: {expected_sources}")

        tr.keyword_hit_ratio = len(keyword_hits) / len(expected_keywords) if expected_keywords else 1.0
        if tr.keyword_hit_ratio < 0.5:
            tr.issues.append(
                f"Low keyword coverage: {len(keyword_hits)}/{len(expected_keywords)} "
                f"(missing: {set(kw.lower() for kw in expected_keywords) - keyword_hits})"
            )

        tr.passed = tr.source_match and tr.page_valid and tr.has_document_id and tr.keyword_hit_ratio >= 0.5
        status = "PASS" if tr.passed else "FAIL"
        print(f"       {status}: {tr.total_citations} citations, src_match={tr.source_match}, "
              f"page_ok={tr.page_valid}, kw={tr.keyword_hit_ratio:.0%}")

        results.append(tr)
        time.sleep(0.5)  # Small pause between queries

    # 3. Report
    print()
    print("=" * 80)
    print("  TEST RESULTS SUMMARY")
    print("=" * 80)

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    src_ok = sum(1 for r in results if r.source_match)
    page_ok = sum(1 for r in results if r.page_valid)
    docid_ok = sum(1 for r in results if r.has_document_id)
    pconf_ok = sum(1 for r in results if r.has_page_confidence)
    pext_ok = sum(1 for r in results if r.has_extraction_method)
    avg_kw = sum(r.keyword_hit_ratio for r in results) / total if total else 0

    print(f"""
  Overall Pass Rate:          {passed}/{total} ({passed/total*100:.0f}%)
  Source Attribution Accuracy: {src_ok}/{total} ({src_ok/total*100:.0f}%)
  Page Number Validity:        {page_ok}/{total} ({page_ok/total*100:.0f}%)
  Document ID Present:         {docid_ok}/{total} ({docid_ok/total*100:.0f}%)
  Page Confidence Present:     {pconf_ok}/{total} ({pconf_ok/total*100:.0f}%)
  Extraction Method Present:   {pext_ok}/{total} ({pext_ok/total*100:.0f}%)
  Avg Keyword Coverage:        {avg_kw:.0%}
""")

    print("-" * 80)
    print("  DETAILED PER-QUERY RESULTS")
    print("-" * 80)

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"\n  [{status}] {r.query_id}: {r.description}")
        print(f"    Query: {r.query[:70]}")
        print(f"    Citations: {r.total_citations} | Source Match: {r.source_match} | Page Valid: {r.page_valid}")
        print(f"    Keyword Coverage: {r.keyword_hit_ratio:.0%} | Has DocID: {r.has_document_id}")
        if r.matched_sources:
            print(f"    Matched Sources: {', '.join(r.matched_sources)}")
        if r.issues:
            for issue in r.issues:
                print(f"    ⚠ {issue}")
        if r.citations_detail:
            print(f"    Citations Detail:")
            for cd in r.citations_detail[:3]:  # Show top 3
                print(f"      #{cd['index']}: source={cd['source']}, page={cd['page']}, "
                      f"doc_id={str(cd['document_id'])[:12] if cd['document_id'] else 'None'}..., "
                      f"page_conf={cd['page_confidence']}, "
                      f"extraction={cd['page_extraction_method']}, "
                      f"content_type={cd['content_type']}")

    print()
    print("=" * 80)
    if passed == total:
        print("  ALL TESTS PASSED")
    else:
        print(f"  {total - passed} TEST(S) FAILED - see issues above")
    print("=" * 80)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(run_tests())
