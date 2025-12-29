#!/bin/bash
# CURL Commands to Test All ARIS RAG APIs
# Server: http://44.221.84.58:8500

BASE_URL="http://44.221.84.58:8500"
DOC_ID="a1064075-218c-4e7b-8cde-d54337b9c491"  # Working document with 47 chunks

echo "=========================================="
echo "ARIS RAG API - CURL TEST COMMANDS"
echo "=========================================="
echo ""

# ==========================================
# 1. API HEALTH CHECK
# ==========================================
echo "1. API Health Check"
echo "-------------------"
echo "curl -X GET \"$BASE_URL/docs\""
echo ""
curl -X GET "$BASE_URL/docs" -s -o /dev/null -w "Status: %{http_code}\n"
echo ""

# ==========================================
# 2. LIST ALL DOCUMENTS
# ==========================================
echo "2. List All Documents"
echo "---------------------"
echo "curl -X GET \"$BASE_URL/documents\""
echo ""
curl -X GET "$BASE_URL/documents" | jq '.'
echo ""

# ==========================================
# 3. GET SINGLE DOCUMENT METADATA
# ==========================================
echo "3. Get Single Document Metadata"
echo "--------------------------------"
echo "curl -X GET \"$BASE_URL/documents/$DOC_ID\""
echo ""
curl -X GET "$BASE_URL/documents/$DOC_ID" | jq '.'
echo ""

# ==========================================
# 4. QUERY WITH SEARCH_MODE (FIX #1)
# ==========================================
echo "4. Query with search_mode='hybrid'"
echo "-----------------------------------"
echo "curl -X POST \"$BASE_URL/query\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"question\": \"What is this document about?\", \"search_mode\": \"hybrid\", \"k\": 3}'"
echo ""
curl -X POST "$BASE_URL/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is this document about?",
    "search_mode": "hybrid",
    "k": 3
  }' | jq '.answer, .sources'
echo ""

# ==========================================
# 5. TEXT QUERY
# ==========================================
echo "5. Text Query"
echo "-------------"
echo "curl -X POST \"$BASE_URL/query/text\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"question\": \"Summarize the main points\", \"k\": 5}'"
echo ""
curl -X POST "$BASE_URL/query/text" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Summarize the main points",
    "k": 5
  }' | jq '.answer'
echo ""

# ==========================================
# 6. IMAGE QUERY (FIX #5)
# ==========================================
echo "6. Image Query"
echo "--------------"
echo "curl -X POST \"$BASE_URL/query/images\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"question\": \"Show me images with diagrams\", \"k\": 3}'"
echo ""
curl -X POST "$BASE_URL/query/images" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me images with diagrams",
    "k": 3
  }' | jq '.images | length'
echo ""

# ==========================================
# 7. GET STORAGE STATUS (FIX #3)
# ==========================================
echo "7. Get Storage Status"
echo "---------------------"
echo "curl -X GET \"$BASE_URL/documents/$DOC_ID/storage/status\""
echo ""
curl -X GET "$BASE_URL/documents/$DOC_ID/storage/status" | jq '.'
echo ""

# ==========================================
# 8. GET DOCUMENT ACCURACY (FIX #4)
# ==========================================
echo "8. Get Document Accuracy"
echo "------------------------"
echo "curl -X GET \"$BASE_URL/documents/$DOC_ID/accuracy\""
echo ""
curl -X GET "$BASE_URL/documents/$DOC_ID/accuracy" | jq '.'
echo ""

# ==========================================
# 9. GET ALL IMAGES
# ==========================================
echo "9. Get All Images"
echo "-----------------"
echo "curl -X GET \"$BASE_URL/documents/$DOC_ID/images\""
echo ""
curl -X GET "$BASE_URL/documents/$DOC_ID/images" | jq '.images | length'
echo ""

# ==========================================
# 10. GET IMAGES SUMMARY (FIX #8)
# ==========================================
echo "10. Get Images Summary"
echo "----------------------"
echo "curl -X GET \"$BASE_URL/documents/$DOC_ID/images-summary\""
echo ""
curl -X GET "$BASE_URL/documents/$DOC_ID/images-summary" | jq '.'
echo ""

# ==========================================
# 11. GET IMAGE BY NUMBER
# ==========================================
echo "11. Get Image by Number"
echo "-----------------------"
echo "curl -X GET \"$BASE_URL/documents/$DOC_ID/images/1\""
echo ""
curl -X GET "$BASE_URL/documents/$DOC_ID/images/1" | jq '.'
echo ""

# ==========================================
# 12. GET PAGE CONTENT (FIX #6)
# ==========================================
echo "12. Get Page Content"
echo "--------------------"
echo "curl -X GET \"$BASE_URL/documents/$DOC_ID/pages/1\""
echo ""
curl -X GET "$BASE_URL/documents/$DOC_ID/pages/1" | jq '.'
echo ""

# ==========================================
# 13. VERIFY ENDPOINT (FIX #7)
# ==========================================
echo "13. Verify Endpoint"
echo "-------------------"
echo "curl -X POST \"$BASE_URL/documents/$DOC_ID/verify\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"page_number\": 1}'"
echo ""
curl -X POST "$BASE_URL/documents/$DOC_ID/verify" \
  -H "Content-Type: application/json" \
  -d '{
    "page_number": 1
  }' | jq '.'
echo ""

# ==========================================
# 14. RE-STORE TEXT (FIX #9)
# ==========================================
echo "14. Re-store Text Content"
echo "-------------------------"
echo "curl -X POST \"$BASE_URL/documents/$DOC_ID/re-store/text\""
echo ""
curl -X POST "$BASE_URL/documents/$DOC_ID/re-store/text" | jq '.'
echo ""

echo "=========================================="
echo "ALL API TESTS COMPLETED"
echo "=========================================="
