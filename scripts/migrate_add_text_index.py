#!/usr/bin/env python3
"""
Migration Script: Add text_index field to all documents in registry

PROBLEM:
- 51 out of 95 documents (54%) are missing the 'text_index' field
- This causes "RAG is not identifying the document, no information fetched" errors
- Affects all parsers (Docling, PyMuPDF, OCRmyPDF, etc.)

SOLUTION:
- For OpenSearch documents: Set text_index = aris-doc-{document_id}
- For FAISS documents: Set text_index = "faiss" (or skip, as FAISS doesn't use per-doc indexes)
- Update document_index_map.json to include all documents

USAGE:
    python3 scripts/migrate_add_text_index.py [--dry-run]
"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.document_registry import DocumentRegistry
from shared.config.settings import ARISConfig

def migrate_text_index(dry_run=False):
    """Add text_index field to all documents missing it."""
    
    print("=" * 80)
    print("MIGRATION: Add text_index to Document Registry")
    print("=" * 80)
    
    # Load registry
    registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
    print(f"\n📁 Loading registry from: {registry_path}")
    
    if not os.path.exists(registry_path):
        print(f"❌ Registry file not found: {registry_path}")
        return False
    
    with open(registry_path, 'r') as f:
        registry_data = json.load(f)
    
    total_docs = len(registry_data)
    print(f"📊 Total documents: {total_docs}")
    
    # Count documents with/without text_index
    docs_with_index = []
    docs_without_index = []
    
    for doc_id, doc_meta in registry_data.items():
        if doc_meta.get('text_index'):
            docs_with_index.append((doc_id, doc_meta))
        else:
            docs_without_index.append((doc_id, doc_meta))
    
    print(f"✅ Documents WITH text_index: {len(docs_with_index)}")
    print(f"❌ Documents WITHOUT text_index: {len(docs_without_index)}")
    
    if not docs_without_index:
        print("\n✨ All documents already have text_index field. No migration needed!")
        return True
    
    # Load document_index_map
    document_index_map_path = os.path.join(ARISConfig.VECTORSTORE_PATH, "document_index_map.json")
    document_index_map = {}
    
    if os.path.exists(document_index_map_path):
        with open(document_index_map_path, 'r') as f:
            document_index_map = json.load(f)
        print(f"\n📋 Loaded {len(document_index_map)} entries from document_index_map.json")
    else:
        print(f"\n⚠️  document_index_map.json not found, will create it")
    
    # Migrate documents
    print(f"\n🔧 Migrating {len(docs_without_index)} documents...")
    print("-" * 80)
    
    updated_count = 0
    skipped_count = 0
    
    for doc_id, doc_meta in docs_without_index:
        doc_name = doc_meta.get('document_name', 'Unknown')
        vector_store_type = doc_meta.get('vector_store_type', 'unknown')
        
        # Fix unknown vector_store_type (assume FAISS for old documents)
        if vector_store_type == 'unknown' or not vector_store_type:
            vector_store_type = 'faiss'  # System is using FAISS
            if not dry_run:
                doc_meta['vector_store_type'] = 'faiss'
        
        # Determine text_index based on vector store type
        if vector_store_type.lower() == 'opensearch':
            # For OpenSearch, use per-document index
            text_index = f"aris-doc-{doc_id}"
            
            # Also add to document_index_map
            if doc_name and doc_name != 'Unknown':
                document_index_map[doc_name] = text_index
            
            if not dry_run:
                doc_meta['text_index'] = text_index
            
            print(f"  ✅ {doc_name[:50]:<50} | {doc_id[:8]}... | OpenSearch → {text_index}")
            updated_count += 1
            
        elif vector_store_type.lower() == 'faiss':
            # For FAISS, we don't use per-document indexes
            # But we can still add the document to the map for consistency
            if doc_name and doc_name != 'Unknown':
                # FAISS uses a single shared index, but we can still track the document
                # Use "faiss-shared" as a placeholder
                text_index = "faiss-shared"
                document_index_map[doc_name] = text_index
                
                if not dry_run:
                    doc_meta['text_index'] = text_index
                
                print(f"  ℹ️  {doc_name[:50]:<50} | {doc_id[:8]}... | FAISS → {text_index}")
                updated_count += 1
            else:
                print(f"  ⚠️  {doc_name[:50]:<50} | {doc_id[:8]}... | FAISS (no name, skipped)")
                skipped_count += 1
        else:
            print(f"  ⚠️  {doc_name[:50]:<50} | {doc_id[:8]}... | Unknown store type: {vector_store_type}")
            skipped_count += 1
    
    print("-" * 80)
    print(f"\n📊 Migration Summary:")
    print(f"   Updated: {updated_count}")
    print(f"   Skipped: {skipped_count}")
    print(f"   Total: {len(docs_without_index)}")
    
    if dry_run:
        print("\n🔍 DRY RUN MODE - No changes were made")
        print("   Run without --dry-run to apply changes")
        return True
    
    # Save updated registry
    print(f"\n💾 Saving updated registry to: {registry_path}")
    backup_path = registry_path + ".backup"
    
    # Create backup
    print(f"   Creating backup: {backup_path}")
    with open(backup_path, 'w') as f:
        json.dump(registry_data, f, indent=2)
    
    # Save updated registry
    with open(registry_path, 'w') as f:
        json.dump(registry_data, f, indent=2)
    
    print(f"   ✅ Registry saved ({total_docs} documents)")
    
    # Save updated document_index_map
    print(f"\n💾 Saving updated document_index_map to: {document_index_map_path}")
    os.makedirs(os.path.dirname(document_index_map_path), exist_ok=True)
    
    with open(document_index_map_path, 'w') as f:
        json.dump(document_index_map, f, indent=2)
    
    print(f"   ✅ document_index_map saved ({len(document_index_map)} entries)")
    
    print("\n" + "=" * 80)
    print("✨ MIGRATION COMPLETE!")
    print("=" * 80)
    print(f"\n📋 Summary:")
    print(f"   - {updated_count} documents updated with text_index field")
    print(f"   - {skipped_count} documents skipped")
    print(f"   - Backup created: {backup_path}")
    print(f"   - document_index_map updated with {len(document_index_map)} entries")
    print("\n🔄 Next Steps:")
    print("   1. Restart retrieval service to load updated mappings")
    print("   2. Test queries on previously failing documents")
    print("   3. If issues persist, check logs for specific document IDs")
    
    return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate document registry to add text_index field")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without making changes")
    args = parser.parse_args()
    
    try:
        success = migrate_text_index(dry_run=args.dry_run)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Migration failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

