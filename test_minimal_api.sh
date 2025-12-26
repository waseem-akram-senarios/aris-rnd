#!/bin/bash
# Comprehensive test for minimal API (10 endpoints)

BASE_URL="http://44.221.84.58:8500"
PASSED=0
FAILED=0

echo "=========================================="
echo "TESTING MINIMAL API (10 ENDPOINTS)"
echo "=========================================="
echo ""

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
        echo "   Response: $(echo "$body" | head -c 100)"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

echo "=== CORE ENDPOINTS (5) ==="
test_endpoint "Root" "$BASE_URL/"
test_endpoint "Health Check" "$BASE_URL/health"
test_endpoint "List Documents" "$BASE_URL/documents"

echo ""
echo "=== SETTINGS & INFO (5) ==="
test_endpoint "System Status" "$BASE_URL/v1/status"
test_endpoint "Document Library" "$BASE_URL/v1/library"
test_endpoint "All Config" "$BASE_URL/v1/config"
test_endpoint "Model Config" "$BASE_URL/v1/config?section=model"
test_endpoint "Parser Config" "$BASE_URL/v1/config?section=parser"
test_endpoint "System Metrics" "$BASE_URL/v1/metrics"

echo ""
echo "=== QUERY ENDPOINT WITH FOCUS (4 variations) ==="
test_endpoint "Query - Default" "$BASE_URL/query" "POST" '{"question":"test","k":5}'
test_endpoint "Query - Important Focus" "$BASE_URL/query?focus=important" "POST" '{"question":"test","k":5}'
test_endpoint "Query - Summary Focus" "$BASE_URL/query?focus=summary" "POST" '{"question":"test","k":5}'
test_endpoint "Query - Specific Focus" "$BASE_URL/query?focus=specific" "POST" '{"question":"test","k":5}'

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
