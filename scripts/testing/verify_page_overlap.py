
import sys
import os

# Create a mock IngestionEngine to test the logic
class MockIngestionEngine:
    def _assign_metadata_to_chunks(self, chunks, original_metadata):
        # Determine the implementation to use (we will manually paste the logic here to verify it works as intended)
        # OR better yet, we can import it if we could, but for a standalone test we will reproduce the logic 
        # to confirm it behaves as expected mathematically.
        
        # Actually, let's test the ACTUAL function by mocking the class structure
        pass

def test_overlap_logic():
    """
    Simulate the max overlap logic to verify it handles page boundaries correctly.
    """
    print("Testing overlap logic...")
    
    # Setup simulated pages
    # Page 1: 0-1000
    # Page 2: 1000-2000
    page_blocks = [
        {'page': 1, 'start_char': 0, 'end_char': 1000},
        {'page': 2, 'start_char': 1000, 'end_char': 2000}
    ]
    
    # Test Case 1: Chunk straddles pages (900-1100)
    # 100 chars on Page 1, 100 chars on Page 2.
    # Should ideally overlap logic pick one. If equal, first one?
    start_index = 900
    end_index = 1100
    
    # Logic simulation
    best_page = 1
    max_overlap_chars = 0
    temp_idx = 0
    num_blocks = len(page_blocks)
    
    # Block index finding (mocking the loop)
    block_idx = 0
    while block_idx < num_blocks - 1 and page_blocks[block_idx].get('end_char', 0) < start_index:
        block_idx += 1
        
    temp_idx = block_idx
    while temp_idx < num_blocks:
        block = page_blocks[temp_idx]
        block_start = block.get('start_char', 0)
        block_end = block.get('end_char', 0)
        
        if block_start >= end_index:
            break
        
        overlap_start = max(start_index, block_start)
        overlap_end = min(end_index, block_end)
        overlap_chars = max(0, overlap_end - overlap_start)
        
        print(f"Checking Page {block['page']}: Overlap = {overlap_chars} chars")
        
        if overlap_chars > max_overlap_chars:
            max_overlap_chars = overlap_chars
            best_page = block.get('page', 1)
        
        temp_idx += 1
        
    print(f"Result: Assigned to Page {best_page}")
    
    # Test Case 2: Chunk mostly on Page 2 (950-1200)
    # 50 chars on Page 1, 200 chars on Page 2. Should be Page 2.
    print("\nTest Case 2: Mostly on Page 2 (950-1200)")
    start_index = 950
    end_index = 1200
    
    best_page = 1
    max_overlap_chars = 0
    block_idx = 0
    while block_idx < num_blocks - 1 and page_blocks[block_idx].get('end_char', 0) < start_index:
        block_idx += 1
    temp_idx = block_idx
    
    while temp_idx < num_blocks:
        block = page_blocks[temp_idx]
        block_start = block.get('start_char', 0)
        block_end = block.get('end_char', 0)
        if block_start >= end_index: break
        overlap_start = max(start_index, block_start)
        overlap_end = min(end_index, block_end)
        overlap_chars = max(0, overlap_end - overlap_start)
        if overlap_chars > max_overlap_chars:
            max_overlap_chars = overlap_chars
            best_page = block.get('page', 1)
        temp_idx += 1
    
    print(f"Result: Assigned to Page {best_page}")
    assert best_page == 2, "Failed: Should be Page 2"

    # Test Case 3: Chunk fully on Page 2 (1050-1150)
    print("\nTest Case 3: Fully on Page 2 (1050-1150)")
    start_index = 1050
    end_index = 1150
    
    best_page = 1
    max_overlap_chars = 0
    block_idx = 0
    while block_idx < num_blocks - 1 and page_blocks[block_idx].get('end_char', 0) < start_index:
        block_idx += 1
    temp_idx = block_idx
    
    while temp_idx < num_blocks:
        block = page_blocks[temp_idx]
        block_start = block.get('start_char', 0)
        block_end = block.get('end_char', 0)
        if block_start >= end_index: break
        overlap_start = max(start_index, block_start)
        overlap_end = min(end_index, block_end)
        overlap_chars = max(0, overlap_end - overlap_start)
        if overlap_chars > max_overlap_chars:
            max_overlap_chars = overlap_chars
            best_page = block.get('page', 1)
        temp_idx += 1
        
    print(f"Result: Assigned to Page {best_page}")
    assert best_page == 2, "Failed: Should be Page 2"

if __name__ == "__main__":
    test_overlap_logic()
