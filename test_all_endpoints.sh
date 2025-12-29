#!/bin/bash
# Comprehensive API Endpoint Testing Script

BASE_URL="http://44.221.84.58:8500"
PASSED=0
FAILED=0

echo "=========================================="
echo "TESTING ALL API ENDPOINTS"
echo "=========================================="
echo ""

# Function to test endpoint
test_endpoint() {
    local name="$1"
    local url="$2"
    local method="${3:-GET}"
    local data="$4"
    
    echo -n "Testing $name... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$url")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" -H "Content-Type: application/json" -d "$data" "$url")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
        echo "✅ PASS (HTTP $http_code)"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo "❌ FAIL (HTTP $http_code)"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

echo "=== CORE ENDPOINTS ==="
test_endpoint "Health Check" "$BASE_URL/health"
test_endpoint "List Documents" "$BASE_URL/documents"
test_endpoint "Root" "$BASE_URL/"

echo ""
echo "=== FOCUSED API ENDPOINTS ==="
test_endpoint "System Status" "$BASE_URL/v1/status"
test_endpoint "Document Library" "$BASE_URL/v1/library"
test_endpoint "All Config" "$BASE_URL/v1/config"
test_endpoint "Model Config" "$BASE_URL/v1/config?section=model"
test_endpoint "Parser Config" "$BASE_URL/v1/config?section=parser"
test_endpoint "Chunking Config" "$BASE_URL/v1/config?section=chunking"
test_endpoint "Vector Store Config" "$BASE_URL/v1/config?section=vectorstore"
test_endpoint "Retrieval Config" "$BASE_URL/v1/config?section=retrieval"
test_endpoint "System Metrics" "$BASE_URL/v1/metrics"

echo ""
echo "=== LEGACY ENDPOINTS (Should still work) ==="
test_endpoint "Query Text" "$BASE_URL/query/text" "POST" '{"question":"test","k":5}'
test_endpoint "Query Images" "$BASE_URL/query/images" "POST" '{"question":"test","k":5}'

echo ""
echo "=========================================="
echo "TEST SUMMARY"
echo "=========================================="
echo "✅ Passed: $PASSED"
echo "❌ Failed: $FAILED"
echo "Total: $((PASSED + FAILED))"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "🎉 ALL TESTS PASSED!"
    exit 0
else
    echo "⚠️  Some tests failed"
    exit 1
fi
