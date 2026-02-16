import httpx
import time
import sys
import os

GATEWAY_URL = "http://127.0.0.1:8500"

async def verify_sync():
    print("🚀 Starting Sync CRUD Verification...")

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. List current documents
        print("\n--- 1. Listing current documents ---")
        try:
            resp = await client.get(f"{GATEWAY_URL}/documents")
            resp.raise_for_status()
            docs = resp.json().get("documents", [])
            print(f"Found {len(docs)} documents.")
        except Exception as e:
            print(f"❌ Failed to list documents: {e}")
            return

        # 2. Test Document Deletion Sync
        print("\n--- 2. Testing Document Deletion Sync ---")
        # We need a document that likely has a dedicated index
        # For testing, we'll try to find one or just use a dummy id if we were creating one
        # Since I don't want to upload a real doc in a quick test, let's look for one with index_name starting with aris-doc-
        test_doc = None
        for doc in docs:
            idx = doc.get("text_index") or doc.get("index_name")
            if idx and idx.startswith("aris-doc-"):
                test_doc = doc
                break
        
        if test_doc:
            doc_id = test_doc['document_id']
            index_name = test_doc.get("text_index") or test_doc.get("index_name")
            print(f"Found test document {doc_id} with dedicated index {index_name}")
            
            # Verify index exists in Retrieval service
            retrieval_url = "http://127.0.0.1:8502"
            try:
                idx_resp = await client.get(f"{retrieval_url}/admin/indexes/{index_name}")
                if idx_resp.status_code == 200:
                    print(f"✅ Index {index_name} verified in Retrieval Service.")
                else:
                    print(f"⚠️ Index {index_name} not found in Retrieval Service, but it's in registry. Proceeding...")
            except Exception as e:
                print(f"⚠️ Could not reach Retrieval Service: {e}")

            # Delete document via Gateway
            print(f"Deleting document {doc_id} via Gateway...")
            del_resp = await client.delete(f"{GATEWAY_URL}/documents/{doc_id}")
            if del_resp.status_code == 200:
                print(f"✅ Gateway reported success: {del_resp.json()}")
                
                # Check if index is gone
                print(f"Verifying index {index_name} is deleted...")
                try:
                    idx_resp = await client.get(f"{retrieval_url}/admin/indexes/{index_name}")
                    if idx_resp.status_code == 404:
                        print(f"✅ Verified: Dedicated index {index_name} was automatically deleted.")
                    else:
                        print(f"❌ Failure: Index {index_name} still exists (Status: {idx_resp.status_code}).")
                except Exception as e:
                    print(f"⚠️ Verification error: {e}")
            else:
                print(f"❌ Deletion failed: {del_resp.text}")
        else:
            print("ℹ️ No document with dedicated index found. Skipping Document Deletion Sync test.")

        # 3. Test Index Deletion Sync
        print("\n--- 3. Testing Index Deletion Sync ---")
        # We'll try to find any index that has documents in the registry
        try:
            resp = await client.get(f"{GATEWAY_URL}/documents")
            docs = resp.json().get("documents", [])
            target_index = None
            for doc in docs:
                idx = doc.get("text_index") or doc.get("index_name")
                if idx:
                    target_index = idx
                    break
            
            if target_index:
                print(f"Testing deletion of index '{target_index}' and registry sync.")
                # Delete index via Gateway's new endpoint
                del_resp = await client.delete(f"{GATEWAY_URL}/admin/indexes/{target_index}")
                if del_resp.status_code == 200:
                    result = del_resp.json()
                    print(f"✅ Gateway reported success: {result}")
                    print(f"Documents removed from registry: {result.get('documents_removed_from_registry', 0)}")
                    
                    # Verify registry is cleaned up
                    resp = await client.get(f"{GATEWAY_URL}/documents")
                    current_docs = resp.json().get("documents", [])
                    still_present = any((d.get("text_index") or d.get("index_name")) == target_index for d in current_docs)
                    if not still_present:
                        print(f"✅ Verified: Registry is clean of documents associated with {target_index}.")
                    else:
                        print(f"❌ Failure: Documents associated with {target_index} still in registry.")
                else:
                    print(f"❌ Index deletion failed: {del_resp.text}")
            else:
                print("ℹ️ No indexes found to test deletion. Skipping.")
        except Exception as e:
            print(f"❌ Error during index sync test: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(verify_sync())
