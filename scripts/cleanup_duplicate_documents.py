#!/usr/bin/env python3
"""
Cleanup script to remove duplicate documents from the system.
Keeps only the most recent (or best quality) version of each document.
"""

import os
import sys
import json
import requests
from collections import defaultdict
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://44.221.84.58:8500"

def get_all_documents():
    """Get all documents from the server"""
    response = requests.get(f"{BASE_URL}/documents", timeout=30)
    response.raise_for_status()
    data = response.json()
    return data.get('documents', data) if isinstance(data, dict) else data

def delete_document(doc_id):
    """Delete a document by ID"""
    try:
        response = requests.delete(f"{BASE_URL}/documents/{doc_id}", timeout=60)
        return response.status_code in (200, 204)
    except Exception as e:
        print(f"    ⚠️ Error deleting {doc_id}: {e}")
        return False

def choose_best_version(versions):
    """
    Choose the best version to keep based on:
    1. Highest chunks_created
    2. Most recent upload date
    3. Best parser (docling > pymupdf > ocrmypdf)
    """
    parser_priority = {'docling': 3, 'pymupdf': 2, 'ocrmypdf': 1, 'textract': 0}
    
    def score_doc(doc):
        chunks = doc.get('chunks_created', 0) or 0
        parser = doc.get('parser_used', '').lower()
        parser_score = parser_priority.get(parser, 0)
        
        # Parse date
        date_str = doc.get('updated_at') or doc.get('created_at') or ''
        try:
            if date_str:
                date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                date_score = date.timestamp()
            else:
                date_score = 0
        except:
            date_score = 0
        
        return (chunks, parser_score, date_score)
    
    # Sort by score (highest first)
    sorted_versions = sorted(versions, key=score_doc, reverse=True)
    return sorted_versions[0]

def main():
    print("=" * 80)
    print("🧹 DUPLICATE DOCUMENT CLEANUP")
    print("=" * 80)
    print(f"Server: {BASE_URL}")
    print()
    
    # Get all documents
    print("📋 Fetching all documents...")
    documents = get_all_documents()
    print(f"   Total documents: {len(documents)}")
    
    # Group by filename
    docs_by_name = defaultdict(list)
    for doc in documents:
        name = doc.get('document_name', 'Unknown')
        docs_by_name[name].append(doc)
    
    # Find duplicates
    duplicates = {name: versions for name, versions in docs_by_name.items() if len(versions) > 1}
    
    if not duplicates:
        print("\n✅ No duplicate documents found!")
        return
    
    print(f"\n⚠️ Found {len(duplicates)} documents with duplicates:")
    
    total_to_delete = 0
    for name, versions in duplicates.items():
        print(f"  - {name}: {len(versions)} copies")
        total_to_delete += len(versions) - 1  # Keep one
    
    print(f"\n📊 Will delete {total_to_delete} duplicate documents")
    
    # Ask for confirmation
    confirm = input("\n❓ Proceed with cleanup? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Cleanup cancelled")
        return
    
    print("\n🗑️ Starting cleanup...")
    deleted_count = 0
    kept_count = 0
    
    for name, versions in duplicates.items():
        print(f"\n📄 Processing: {name}")
        
        # Choose best version to keep
        best = choose_best_version(versions)
        best_id = best.get('document_id')
        best_chunks = best.get('chunks_created', 0)
        best_parser = best.get('parser_used', 'unknown')
        
        print(f"   ✅ Keeping: {best_id} ({best_parser}, {best_chunks} chunks)")
        kept_count += 1
        
        # Delete others
        for doc in versions:
            doc_id = doc.get('document_id')
            if doc_id != best_id:
                parser = doc.get('parser_used', 'unknown')
                chunks = doc.get('chunks_created', 0)
                print(f"   🗑️ Deleting: {doc_id} ({parser}, {chunks} chunks)...", end=" ")
                
                if delete_document(doc_id):
                    print("✅")
                    deleted_count += 1
                else:
                    print("❌")
    
    print("\n" + "=" * 80)
    print("📊 CLEANUP SUMMARY")
    print("=" * 80)
    print(f"   Documents kept: {kept_count}")
    print(f"   Documents deleted: {deleted_count}")
    print(f"   Remaining unique documents: {len(documents) - deleted_count}")
    print("\n✅ Cleanup complete!")

if __name__ == "__main__":
    main()

