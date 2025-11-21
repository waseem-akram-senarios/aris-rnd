#!/usr/bin/env python3
"""
Script to extract detailed information from documents in the RAG system.
"""
import os
import sys
from rag_system import RAGSystem
from ingestion.document_processor import DocumentProcessor

def extract_detailed_info(pdf_path, output_file=None):
    """Extract detailed information from a PDF document."""
    
    # Initialize RAG system
    rag = RAGSystem(use_cerebras=False)
    processor = DocumentProcessor(rag)
    
    print(f"Processing: {pdf_path}")
    print("=" * 70)
    print()
    
    # Process document
    with open(pdf_path, 'rb') as f:
        content = f.read()
    
    result = processor.process_document(
        file_path=pdf_path,
        file_content=content,
        file_name=os.path.basename(pdf_path),
        parser_preference='pymupdf'
    )
    
    if result.status != 'success':
        print(f"❌ Processing failed: {result.error}")
        return
    
    print(f"✅ Document processed: {result.chunks_created} chunks, {result.tokens_extracted:,} tokens")
    print(f"   Parser used: {result.parser_used}")
    print()
    
    # Comprehensive questions for detailed extraction
    questions = {
        "Document Overview": [
            "What is the complete title and purpose of this document?",
            "What is the document version, revision, or date?",
            "Who is the intended audience or application for this document?"
        ],
        "Materials & Components": [
            "List all materials specified with their exact specifications, grades, and standards",
            "What are all component parts and their materials?",
            "What are the material properties and certifications required?"
        ],
        "Dimensions & Tolerances": [
            "Provide all dimensions with their exact values and tolerances",
            "What are the wall thicknesses, clearances, and spacing requirements?",
            "What are the mounting hole specifications and positions?"
        ],
        "Manufacturing & Processes": [
            "What is the complete manufacturing process?",
            "What are all finishing requirements and surface specifications?",
            "What are the post-molding operations and assembly steps?"
        ],
        "Quality & Testing": [
            "What are all quality assurance procedures?",
            "What testing requirements and acceptance criteria are specified?",
            "What inspection requirements and sampling plans are defined?"
        ],
        "Performance & Environmental": [
            "What are all environmental specifications (temperature, humidity, etc.)?",
            "What are the performance requirements and ratings?",
            "What are the operating conditions and limitations?"
        ],
        "Design & Features": [
            "What are all design features and technical specifications?",
            "What are the assembly requirements and procedures?",
            "What are the interface requirements and compatibility specifications?"
        ],
        "Standards & Compliance": [
            "What standards, certifications, or regulations are referenced?",
            "What compliance requirements are specified?",
            "What are the marking, labeling, or documentation requirements?"
        ]
    }
    
    output_lines = []
    output_lines.append("=" * 70)
    output_lines.append("DETAILED DOCUMENT INFORMATION EXTRACTION")
    output_lines.append("=" * 70)
    output_lines.append(f"Document: {os.path.basename(pdf_path)}")
    output_lines.append(f"Parser: {result.parser_used}")
    output_lines.append(f"Chunks: {result.chunks_created}")
    output_lines.append(f"Tokens: {result.tokens_extracted:,}")
    output_lines.append("=" * 70)
    output_lines.append("")
    
    # Query each category
    for category, category_questions in questions.items():
        output_lines.append("")
        output_lines.append("=" * 70)
        output_lines.append(f"CATEGORY: {category}")
        output_lines.append("=" * 70)
        output_lines.append("")
        
        for i, question in enumerate(category_questions, 1):
            print(f"Querying: {category} - Question {i}/{len(category_questions)}")
            
            query_result = rag.query_with_rag(question, k=4)
            
            output_lines.append(f"Q{i}: {question}")
            output_lines.append("-" * 70)
            output_lines.append(f"Answer:")
            output_lines.append(query_result['answer'])
            output_lines.append("")
            
            if query_result.get('sources'):
                output_lines.append(f"Sources: {', '.join(set(query_result['sources']))}")
                output_lines.append("")
            
            # Add context chunks
            if 'context_chunks' in query_result and query_result['context_chunks']:
                output_lines.append("Relevant Context:")
                for j, chunk in enumerate(query_result['context_chunks'][:3], 1):
                    output_lines.append(f"  [{j}] {chunk[:200]}...")
                output_lines.append("")
            
            output_lines.append("=" * 70)
            output_lines.append("")
    
    # Get document statistics
    stats = rag.get_stats()
    output_lines.append("")
    output_lines.append("=" * 70)
    output_lines.append("DOCUMENT STATISTICS")
    output_lines.append("=" * 70)
    output_lines.append(f"Total Documents: {stats['total_documents']}")
    output_lines.append(f"Total Chunks: {stats['total_chunks']}")
    output_lines.append(f"Total Tokens: {stats['total_tokens']:,}")
    output_lines.append(f"Estimated Embedding Cost: ${stats['estimated_embedding_cost_usd']:.6f}")
    output_lines.append("=" * 70)
    
    # Output results
    output_text = "\n".join(output_lines)
    print("\n" + output_text)
    
    # Save to file if requested
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_text)
        print(f"\n✅ Detailed information saved to: {output_file}")
    
    return output_text

if __name__ == "__main__":
    # Find X-90 document
    pdf_files = [f for f in os.listdir('.') if f.endswith('.pdf')]
    x90_files = [f for f in pdf_files if 'x90' in f.lower()]
    
    if x90_files:
        pdf_path = x90_files[0]
    elif pdf_files:
        pdf_path = pdf_files[0]
        print(f"⚠️  X-90 document not found, using: {pdf_path}")
    else:
        print("❌ No PDF files found")
        sys.exit(1)
    
    output_file = f"{os.path.splitext(pdf_path)[0]}_detailed_info.txt"
    extract_detailed_info(pdf_path, output_file)


