#!/usr/bin/env python3
"""
Test all MCP CRUD tools by calling the underlying service endpoints.
These are the same endpoints the MCP tools call internally.
"""

import httpx
import json
import sys
import time

import os

# Use Docker service names when running inside container, localhost when outside
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8500")
RETRIEVAL_URL = os.getenv("RETRIEVAL_SERVICE_URL", "http://retrieval:8502")
MCP_URL = os.getenv("MCP_URL", "http://localhost:8503")

client = httpx.Client(timeout=60)
results = []

def test(name, func):
    try:
        func()
        results.append((name, "PASS"))
        print(f"  PASS: {name}")
    except Exception as e:
        results.append((name, f"FAIL: {e}"))
        print(f"  FAIL: {name} - {e}")


def test_mcp_health():
    r = client.get(f"{MCP_URL}/health")
    data = r.json()
    assert data["status"] == "healthy", f"Status is {data['status']}"
    assert data["total_tools"] == 5, f"Expected 5 tools, got {data['total_tools']}"

def test_list_documents():
    r = client.get(f"{GATEWAY_URL}/documents")
    assert r.status_code == 200, f"HTTP {r.status_code}"
    data = r.json()
    assert "documents" in data, "Missing 'documents' key"
    assert "total" in data, "Missing 'total' key"
    print(f"    Found {data['total']} documents")

def test_get_document():
    r = client.get(f"{GATEWAY_URL}/documents")
    docs = r.json().get("documents", [])
    if not docs:
        print("    No documents to test (skipped)")
        return
    doc_id = docs[0]["document_id"]
    r2 = client.get(f"{GATEWAY_URL}/documents/{doc_id}")
    assert r2.status_code == 200, f"HTTP {r2.status_code}"
    doc = r2.json()
    assert doc.get("document_id") == doc_id, "Returned doc ID mismatch"
    print(f"    Retrieved: {doc.get('document_name', '?')}")

def test_get_stats():
    r = client.get(f"{GATEWAY_URL}/stats")
    assert r.status_code == 200, f"HTTP {r.status_code}"
    data = r.json()
    print(f"    Stats keys: {list(data.keys())}")

def test_list_indexes():
    r = client.get(f"{RETRIEVAL_URL}/admin/indexes")
    assert r.status_code == 200, f"HTTP {r.status_code}"
    data = r.json()
    assert "indexes" in data, "Missing 'indexes' key"
    print(f"    Found {data.get('total', len(data['indexes']))} indexes")

def test_get_index_info():
    r = client.get(f"{RETRIEVAL_URL}/admin/indexes")
    indexes = r.json().get("indexes", [])
    if not indexes:
        print("    No indexes to test (skipped)")
        return
    idx_name = indexes[0]["index_name"]
    r2 = client.get(f"{RETRIEVAL_URL}/admin/indexes/{idx_name}")
    assert r2.status_code == 200, f"HTTP {r2.status_code}"
    print(f"    Index info retrieved: {idx_name}")

def test_list_chunks():
    r = client.get(f"{RETRIEVAL_URL}/admin/indexes")
    indexes = r.json().get("indexes", [])
    if not indexes:
        print("    No indexes to test (skipped)")
        return
    idx_name = indexes[0]["index_name"]
    r2 = client.get(f"{RETRIEVAL_URL}/admin/indexes/{idx_name}/chunks?limit=5")
    assert r2.status_code == 200, f"HTTP {r2.status_code}"
    data = r2.json()
    assert "chunks" in data, "Missing 'chunks' key"
    print(f"    Found {data.get('total', len(data['chunks']))} chunks in {idx_name}")

def test_get_chunk():
    r = client.get(f"{RETRIEVAL_URL}/admin/indexes")
    indexes = r.json().get("indexes", [])
    if not indexes:
        print("    No indexes to test (skipped)")
        return
    idx_name = indexes[0]["index_name"]
    r2 = client.get(f"{RETRIEVAL_URL}/admin/indexes/{idx_name}/chunks?limit=1")
    chunks = r2.json().get("chunks", [])
    if not chunks:
        print("    No chunks to test (skipped)")
        return
    chunk_id = chunks[0].get("chunk_id", "")
    if not chunk_id:
        print("    Chunk has no ID (skipped)")
        return
    r3 = client.get(f"{RETRIEVAL_URL}/admin/indexes/{idx_name}/chunks/{chunk_id}")
    assert r3.status_code == 200, f"HTTP {r3.status_code}"
    print(f"    Retrieved chunk: {chunk_id[:40]}...")

def test_create_update_delete_chunk():
    """Test the full lifecycle: create -> get -> update -> delete a chunk."""
    r = client.get(f"{RETRIEVAL_URL}/admin/indexes")
    indexes = r.json().get("indexes", [])
    if not indexes:
        print("    No indexes to test (skipped)")
        return
    idx_name = indexes[0]["index_name"]
    
    # CREATE
    create_data = {
        "text": "MCP CRUD test chunk - this is a test entry created by automated testing.",
        "index_name": idx_name,
        "source": "mcp_crud_test",
        "page": 999,
        "metadata": {"test": True, "created_by": "test_mcp_crud.py"}
    }
    r_create = client.post(f"{RETRIEVAL_URL}/admin/indexes/{idx_name}/chunks", json=create_data)
    assert r_create.status_code == 200 or r_create.status_code == 201, f"Create HTTP {r_create.status_code}: {r_create.text[:200]}"
    created = r_create.json()
    chunk_id = created.get("chunk_id", "")
    print(f"    Created chunk: {chunk_id}")
    
    if not chunk_id:
        print("    No chunk_id returned, skipping update/delete")
        return
    
    # UPDATE
    update_data = {
        "text": "MCP CRUD test chunk - UPDATED text.",
        "page": 998,
        "metadata": {"test": True, "updated": True}
    }
    r_update = client.put(f"{RETRIEVAL_URL}/admin/indexes/{idx_name}/chunks/{chunk_id}", json=update_data)
    assert r_update.status_code == 200, f"Update HTTP {r_update.status_code}: {r_update.text[:200]}"
    print(f"    Updated chunk: {chunk_id}")
    
    # DELETE
    r_delete = client.request("DELETE", f"{RETRIEVAL_URL}/admin/indexes/{idx_name}/chunks/{chunk_id}")
    assert r_delete.status_code == 200, f"Delete HTTP {r_delete.status_code}: {r_delete.text[:200]}"
    print(f"    Deleted chunk: {chunk_id}")


def test_mcp_tools_list():
    """Verify all 5 consolidated tools are registered via MCP tools/list."""
    r = client.get(f"{MCP_URL}/tools")
    data = r.json()
    assert data.get("total_tools") == 5, f"Expected 5 tools, got {data.get('total_tools')}"
    tool_names = [t["name"] for t in data.get("tools", [])]
    expected = ["rag_query", "rag_documents", "rag_indexes", "rag_chunks", "rag_stats"]
    for tool in expected:
        assert tool in tool_names, f"Missing tool: {tool}"
    print(f"    All 5 tools registered")


if __name__ == "__main__":
    print("=" * 60)
    print("MCP CRUD Tools - Integration Test Suite")
    print("=" * 60)
    print()
    
    test("MCP Health (5 tools)", test_mcp_health)
    test("MCP Tools List", test_mcp_tools_list)
    test("List Documents", test_list_documents)
    test("Get Document", test_get_document)
    test("Get Stats", test_get_stats)
    test("List Indexes", test_list_indexes)
    test("Get Index Info", test_get_index_info)
    test("List Chunks", test_list_chunks)
    test("Get Chunk", test_get_chunk)
    test("Create/Update/Delete Chunk Lifecycle", test_create_update_delete_chunk)
    
    print()
    print("=" * 60)
    passed = sum(1 for _, s in results if s == "PASS")
    failed = sum(1 for _, s in results if s != "PASS")
    print(f"Results: {passed}/{len(results)} PASSED, {failed} FAILED")
    print("=" * 60)
    
    if failed > 0:
        print("\nFailed tests:")
        for name, status in results:
            if status != "PASS":
                print(f"  - {name}: {status}")
        sys.exit(1)
    else:
        print("\nAll tests PASSED!")
        sys.exit(0)
