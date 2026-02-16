import httpx
import asyncio
import sys

GATEWAY_URL = "http://127.0.0.1:8500"
INDEX_TO_DELETE = "aris-doc-af9cae19-154e-4304-be46-4ae31262d045"

async def test_deletion():
    print(f"🚀 Testing synchronized deletion for index: {INDEX_TO_DELETE}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Check if index exists in documents list
        print("Checking documents in registry...")
        resp = await client.get(f"{GATEWAY_URL}/documents")
        docs = resp.json().get("documents", [])
        associated_docs = [d for d in docs if (d.get("text_index") or d.get("index_name")) == INDEX_TO_DELETE]
        
        if not associated_docs:
            print(f"⚠️ No documents found for index {INDEX_TO_DELETE}. Cannot test sync.")
            # Let's pick another one from the list if possible
            for d in docs:
                idx = d.get("text_index") or d.get("index_name")
                if idx and idx != "aris-rag-index":
                    print(f"💡 Suggestion: Try index '{idx}' instead.")
            return

        print(f"Found {len(associated_docs)} documents associated with {INDEX_TO_DELETE}.")

        # 2. Perform deletion
        print(f"Triggering DELETE /admin/indexes/{INDEX_TO_DELETE}...")
        try:
            del_resp = await client.delete(f"{GATEWAY_URL}/admin/indexes/{INDEX_TO_DELETE}")
            print(f"Response: {del_resp.status_code}")
            print(f"Body: {del_resp.text}")
            
            if del_resp.status_code == 200:
                print("✅ Deletion triggered successfully.")
            else:
                print("❌ Deletion failed.")
                return
        except Exception as e:
            print(f"❌ Error during request: {e}")
            return

        # 3. Verify registry cleanup
        print("Verifying registry cleanup...")
        # Wait a bit for async operations if any (though GatewayService.delete_index_synced is awaited)
        await asyncio.sleep(2)
        
        resp = await client.get(f"{GATEWAY_URL}/documents")
        docs = resp.json().get("documents", [])
        remaining_docs = [d for d in docs if (d.get("text_index") or d.get("index_name")) == INDEX_TO_DELETE]
        
        if not remaining_docs:
            print(f"✨ SUCCESS: All {len(associated_docs)} documents for {INDEX_TO_DELETE} were removed from registry.")
        else:
            print(f"❌ FAILURE: {len(remaining_docs)} documents still remain in registry for index {INDEX_TO_DELETE}.")
            for d in remaining_docs:
                print(f"  - {d.get('document_id')} ({d.get('document_name')})")

if __name__ == "__main__":
    asyncio.run(test_deletion())
