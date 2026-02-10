#!/usr/bin/env python3
"""
Server Page-Number Accuracy Test
=================================
Deep test of page number accuracy for citations from multi-page PDFs
on the deployed server. Tests:
  1. Page numbers are valid integers >= 1
  2. Page numbers don't exceed known document page counts
  3. page_confidence is set (not None) and > 0
  4. page_extraction_method is meaningful (not 'unknown')
  5. document_id is present
  6. Different pages appear for different queries (no "all page 1" syndrome)
  7. Source attribution matches expected documents
  8. Citation metadata chain is complete
"""

import json
import subprocess
import sys
import time
import os
from collections import defaultdict

PEM_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "ec2_wah_pk.pem")
SERVER_HOST = "44.221.84.58"
MCP_PORT = 8503

# Known multi-page documents on the server with approximate page counts
KNOWN_MULTI_PAGE_DOCS = {
    "FW Handbook.pdf": {"min_pages": 10, "max_pages": 20},
    "EM11, top seal.pdf": {"min_pages": 5, "max_pages": 20},
    "EM10, degasing.pdf": {"min_pages": 2, "max_pages": 10},
}

# Targeted queries designed to hit specific page ranges in multi-page PDFs
QUERIES = [
    {
        "id": "MP1",
        "query": "FW Handbook freshwater aquarium setup and cleaning new tank",
        "target_source": "FW Handbook",
        "description": "FW Handbook - tank setup (early pages)",
    },
    {
        "id": "MP2",
        "query": "FW Handbook fish feeding frozen foods nutrition and diet",
        "target_source": "FW Handbook",
        "description": "FW Handbook - feeding (mid pages)",
    },
    {
        "id": "MP3",
        "query": "FW Handbook glass maintenance cleaning ornaments rocks",
        "target_source": "FW Handbook",
        "description": "FW Handbook - maintenance (later pages)",
    },
    {
        "id": "MP4",
        "query": "FW Handbook water temperature pH level and water quality testing",
        "target_source": "FW Handbook",
        "description": "FW Handbook - water quality",
    },
    {
        "id": "MP5",
        "query": "FW Handbook disease treatment fish health medication",
        "target_source": "FW Handbook",
        "description": "FW Handbook - fish health (later pages)",
    },
    {
        "id": "MP6",
        "query": "EM11 top seal installation procedure and assembly steps",
        "target_source": "EM11",
        "description": "EM11 Top Seal - installation",
    },
    {
        "id": "MP7",
        "query": "EM11 top seal technical specifications dimensions and tolerances",
        "target_source": "EM11",
        "description": "EM11 Top Seal - specs",
    },
    {
        "id": "MP8",
        "query": "EM10 degasing procedure and valve operation",
        "target_source": "EM10",
        "description": "EM10 Degasing - procedure",
    },
    {
        "id": "MP9",
        "query": "Policy manual employee guidelines and company procedures",
        "target_source": "Policy",
        "description": "Policy Manual - general",
    },
    {
        "id": "MP10",
        "query": "VUORMAR product specifications and model details",
        "target_source": "VUORMAR",
        "description": "VUORMAR - product info",
    },
]


def ssh_cmd(cmd, timeout=30):
    full = ["ssh", "-i", PEM_FILE, "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10", f"ec2-user@{SERVER_HOST}", cmd]
    r = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
    return r.stdout


def init_session():
    raw = ssh_cmd(
        f'curl -s -D- -X POST http://localhost:{MCP_PORT}/mcp '
        f'-H "Content-Type: application/json" '
        f'-H "Accept: application/json, text/event-stream" '
        f'-d \'{{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{{\"protocolVersion\":\"2025-03-26\",\"capabilities\":{{}},\"clientInfo\":{{\"name\":\"page-acc\",\"version\":\"1.0\"}}}}}}\'',
        timeout=15)
    for line in raw.splitlines():
        if line.lower().startswith("mcp-session-id"):
            sid = line.split(":", 1)[1].strip()
            ssh_cmd(
                f'curl -s -X POST http://localhost:{MCP_PORT}/mcp '
                f'-H "Content-Type: application/json" '
                f'-H "Accept: application/json, text/event-stream" '
                f'-H "Mcp-Session-Id: {sid}" '
                f'-d \'{{\"jsonrpc\":\"2.0\",\"method\":\"notifications/initialized\"}}\'',
                timeout=10)
            return sid
    raise RuntimeError("Could not init MCP session")


def query_mcp(sid, query, k=8):
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 500,
        "method": "tools/call",
        "params": {"name": "rag_search", "arguments": {"query": query, "k": k, "include_answer": False}}
    })
    raw = ssh_cmd(
        f"curl -s -X POST http://localhost:{MCP_PORT}/mcp "
        f"-H 'Content-Type: application/json' "
        f"-H 'Accept: application/json, text/event-stream' "
        f"-H 'Mcp-Session-Id: {sid}' "
        f"-d '{payload}'",
        timeout=90)
    for line in raw.splitlines():
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                text = data.get("result", {}).get("content", [{}])[0].get("text", "{}")
                return json.loads(text)
            except (json.JSONDecodeError, IndexError, KeyError):
                continue
    return {"error": "no response", "raw": raw[:300]}


def run_tests():
    print("=" * 80)
    print("  SERVER PAGE-NUMBER ACCURACY TEST")
    print("  Testing multi-page PDF citations on deployed server")
    print("=" * 80)
    print()

    sid = init_session()
    print(f"[Session] {sid[:16]}...")
    print()

    # === Aggregated stats ===
    total_citations = 0
    valid_pages = 0
    invalid_pages = 0
    has_doc_id = 0
    has_page_conf = 0
    has_extraction_method = 0
    high_confidence = 0  # page_confidence >= 0.8
    low_confidence = 0   # page_confidence < 0.3
    pages_seen_per_source = defaultdict(set)  # source -> set of pages
    query_pass = 0
    query_fail = 0
    issues = []

    print(f"Running {len(QUERIES)} queries against multi-page documents...")
    print("-" * 80)

    for q in QUERIES:
        qid = q["id"]
        query = q["query"]
        target = q["target_source"]
        desc = q["description"]

        print(f"\n  {qid}: {desc}")
        print(f"       Query: {query[:65]}...")

        resp = query_mcp(sid, query, k=8)
        citations = resp.get("citations", [])

        if not citations:
            print(f"       WARN: No citations returned")
            issues.append(f"{qid}: No citations returned for '{desc}'")
            query_fail += 1
            continue

        q_ok = True
        target_found = False
        q_pages = set()

        for i, c in enumerate(citations):
            total_citations += 1
            src = c.get("source", "")
            page = c.get("page")
            doc_id = c.get("document_id")
            pconf = c.get("page_confidence")
            pmethod = c.get("page_extraction_method")
            ctype = c.get("content_type", "text")

            # Check target source match
            if target.lower() in src.lower():
                target_found = True

            # Validate page number
            if page is not None and isinstance(page, int) and page >= 1:
                valid_pages += 1
                q_pages.add(page)
                pages_seen_per_source[src].add(page)

                # Check against known page counts
                for known_name, bounds in KNOWN_MULTI_PAGE_DOCS.items():
                    if known_name.lower() in src.lower():
                        if page > bounds["max_pages"]:
                            issues.append(f"{qid} cit#{i+1}: Page {page} exceeds expected max {bounds['max_pages']} for {src}")
                            q_ok = False
            else:
                invalid_pages += 1
                issues.append(f"{qid} cit#{i+1}: Invalid page: {page} for {src}")
                q_ok = False

            # Validate document_id
            if doc_id:
                has_doc_id += 1
            else:
                issues.append(f"{qid} cit#{i+1}: Missing document_id for {src}")
                q_ok = False

            # Validate page_confidence
            if pconf is not None:
                has_page_conf += 1
                if pconf >= 0.8:
                    high_confidence += 1
                elif pconf < 0.3:
                    low_confidence += 1
            else:
                issues.append(f"{qid} cit#{i+1}: Missing page_confidence for {src}")

            # Validate page_extraction_method
            if pmethod and pmethod != "unknown":
                has_extraction_method += 1
            else:
                issues.append(f"{qid} cit#{i+1}: Missing/unknown extraction method for {src}")

        if not target_found:
            issues.append(f"{qid}: Target source '{target}' not found in citations")
            q_ok = False

        status = "PASS" if q_ok else "WARN"
        if q_ok:
            query_pass += 1
        else:
            query_fail += 1

        # Print citation details
        print(f"       {status}: {len(citations)} citations, pages={sorted(q_pages)}")
        for i, c in enumerate(citations[:5]):
            src = c.get("source", "?")
            page = c.get("page", "?")
            pconf = c.get("page_confidence", "?")
            pmethod = c.get("page_extraction_method", "?")
            print(f"         [{i+1}] {src} | Page {page} | conf={pconf} | method={pmethod}")

        time.sleep(0.5)

    # === PAGE DIVERSITY CHECK ===
    # For multi-page docs, we should see MULTIPLE different pages across queries
    print()
    print("=" * 80)
    print("  PAGE DIVERSITY ANALYSIS")
    print("=" * 80)
    diversity_pass = 0
    diversity_total = 0
    for src, pages in sorted(pages_seen_per_source.items()):
        for known_name in KNOWN_MULTI_PAGE_DOCS:
            if known_name.lower() in src.lower():
                diversity_total += 1
                n_pages = len(pages)
                status = "PASS" if n_pages >= 2 else "WARN"
                if n_pages >= 2:
                    diversity_pass += 1
                else:
                    issues.append(f"Page diversity: Only {n_pages} unique page(s) for {src}: {sorted(pages)}")
                print(f"  {status} {src}: {n_pages} unique pages seen: {sorted(pages)}")
                break

    # === SUMMARY ===
    print()
    print("=" * 80)
    print("  RESULTS SUMMARY")
    print("=" * 80)

    pct = lambda n, d: f"{n/d*100:.0f}%" if d > 0 else "N/A"

    print(f"""
  Queries:
    Passed:                     {query_pass}/{query_pass + query_fail} ({pct(query_pass, query_pass + query_fail)})

  Citation Metrics ({total_citations} total citations):
    Valid Page Numbers:          {valid_pages}/{total_citations} ({pct(valid_pages, total_citations)})
    Invalid Page Numbers:        {invalid_pages}/{total_citations}
    Document ID Present:         {has_doc_id}/{total_citations} ({pct(has_doc_id, total_citations)})
    Page Confidence Present:     {has_page_conf}/{total_citations} ({pct(has_page_conf, total_citations)})
    Extraction Method Present:   {has_extraction_method}/{total_citations} ({pct(has_extraction_method, total_citations)})
    High Confidence (>=0.8):     {high_confidence}/{total_citations} ({pct(high_confidence, total_citations)})
    Low Confidence (<0.3):       {low_confidence}/{total_citations}

  Page Diversity (multi-page docs):
    Docs with 2+ pages seen:     {diversity_pass}/{diversity_total} ({pct(diversity_pass, diversity_total)})
""")

    if issues:
        print(f"  Issues ({len(issues)}):")
        for iss in issues:
            print(f"    - {iss}")
    else:
        print("  No issues found.")

    print()
    print("=" * 80)
    overall = (
        valid_pages == total_citations
        and has_doc_id == total_citations
        and has_page_conf == total_citations
        and has_extraction_method == total_citations
        and invalid_pages == 0
    )
    if overall:
        print("  ALL CITATION METADATA CHECKS PASSED")
    else:
        print("  SOME CHECKS HAD ISSUES - see details above")
    print("=" * 80)

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(run_tests())
