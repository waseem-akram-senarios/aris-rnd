# All UI Parameters Available in API

**Date:** December 26, 2025  
**Feature:** Complete UI-API parameter synchronization

---

## 🎯 **ALL UI PARAMETERS NOW IN API**

Your query endpoint now exposes **ALL UI parameters** as both query parameters and request body options!

---

## 📋 **COMPLETE PARAMETER LIST**

### **Query Parameters (URL)**
All parameters can be passed in the URL and will override request body values:

```
POST /query?parameter=value
```

| Parameter | Type | Range | Default | Description |
|-----------|------|-------|---------|-------------|
| `type` | string | text, image | text | Query type |
| `document_id` | string | - | null | Filter to specific document |
| `focus` | string | all, important, summary, specific | all | Query focus |
| `k` | integer | 1-50 | 6 | Number of chunks to retrieve |
| `use_mmr` | boolean | true, false | true | Use Maximum Marginal Relevance |
| `search_mode` | string | semantic, keyword, hybrid | hybrid | Search mode |
| `temperature` | float | 0.0-2.0 | 0.0 | LLM temperature |
| `max_tokens` | integer | 1-4000 | 1200 | Max response tokens |
| `use_agentic_rag` | boolean | true, false | false | Use Agentic RAG |
| `semantic_weight` | float | 0.0-1.0 | 0.7 | Semantic weight in hybrid |

### **Request Body (JSON)**
All parameters can also be sent in the request body:

```json
{
  "question": "Your question here",
  "k": 12,
  "use_mmr": true,
  "search_mode": "hybrid",
  "temperature": 0.0,
  "max_tokens": 1200,
  "use_agentic_rag": false,
  "semantic_weight": 0.7,
  "document_id": "abc123"
}
```

---

## 🎨 **UI TO API MAPPING**

### **1. Number of Chunks (k)**

**UI:** Slider or input field (1-50)

**API:**
```bash
# Query parameter
POST /query?k=20

# Request body
{"question": "...", "k": 20}
```

**Use in UI:**
```python
k = st.slider("Number of chunks", 1, 50, 12)
response = requests.post(f"{API_BASE}/query?k={k}", json={"question": question})
```

---

### **2. Use MMR (Maximum Marginal Relevance)**

**UI:** Checkbox or toggle

**API:**
```bash
# Query parameter
POST /query?use_mmr=true

# Request body
{"question": "...", "use_mmr": true}
```

**Use in UI:**
```python
use_mmr = st.checkbox("Use MMR for diversity", value=True)
response = requests.post(f"{API_BASE}/query?use_mmr={str(use_mmr).lower()}", json={"question": question})
```

---

### **3. Search Mode**

**UI:** Dropdown (Semantic, Keyword, Hybrid)

**API:**
```bash
# Query parameter
POST /query?search_mode=hybrid

# Request body
{"question": "...", "search_mode": "hybrid"}
```

**Use in UI:**
```python
search_mode = st.selectbox("Search Mode", ["semantic", "keyword", "hybrid"], index=2)
response = requests.post(f"{API_BASE}/query?search_mode={search_mode}", json={"question": question})
```

---

### **4. Temperature**

**UI:** Slider (0.0-2.0)

**API:**
```bash
# Query parameter
POST /query?temperature=0.5

# Request body
{"question": "...", "temperature": 0.5}
```

**Use in UI:**
```python
temperature = st.slider("Temperature", 0.0, 2.0, 0.0, 0.1)
response = requests.post(f"{API_BASE}/query?temperature={temperature}", json={"question": question})
```

---

### **5. Max Tokens**

**UI:** Slider or input (1-4000)

**API:**
```bash
# Query parameter
POST /query?max_tokens=1500

# Request body
{"question": "...", "max_tokens": 1500}
```

**Use in UI:**
```python
max_tokens = st.slider("Max Tokens", 100, 4000, 1200, 100)
response = requests.post(f"{API_BASE}/query?max_tokens={max_tokens}", json={"question": question})
```

---

### **6. Agentic RAG**

**UI:** Checkbox or toggle

**API:**
```bash
# Query parameter
POST /query?use_agentic_rag=true

# Request body
{"question": "...", "use_agentic_rag": true}
```

**Use in UI:**
```python
use_agentic = st.checkbox("Use Agentic RAG", value=False)
response = requests.post(f"{API_BASE}/query?use_agentic_rag={str(use_agentic).lower()}", json={"question": question})
```

---

### **7. Semantic Weight (Hybrid Search)**

**UI:** Slider (0.0-1.0)

**API:**
```bash
# Query parameter
POST /query?semantic_weight=0.8

# Request body
{"question": "...", "semantic_weight": 0.8}
```

**Use in UI:**
```python
semantic_weight = st.slider("Semantic Weight", 0.0, 1.0, 0.7, 0.1)
response = requests.post(f"{API_BASE}/query?semantic_weight={semantic_weight}", json={"question": question})
```

---

### **8. Query Focus**

**UI:** Dropdown (All, Important, Summary, Specific)

**API:**
```bash
# Query parameter
POST /query?focus=important

# Request body
# Focus is only available as query parameter
```

**Use in UI:**
```python
focus = st.selectbox("Focus", ["all", "important", "summary", "specific"], index=1)
response = requests.post(f"{API_BASE}/query?focus={focus}", json={"question": question})
```

---

### **9. Document Filter**

**UI:** Dropdown of document names

**API:**
```bash
# Query parameter
POST /query?document_id=abc123

# Request body
{"question": "...", "document_id": "abc123"}
```

**Use in UI:**
```python
doc_id = st.selectbox("Filter by document", document_ids)
response = requests.post(f"{API_BASE}/query?document_id={doc_id}", json={"question": question})
```

---

### **10. Query Type**

**UI:** Radio buttons or tabs (Text, Image)

**API:**
```bash
# Query parameter
POST /query?type=text
POST /query?type=image

# Request body
# Type is only available as query parameter
```

**Use in UI:**
```python
query_type = st.radio("Query Type", ["text", "image"])
response = requests.post(f"{API_BASE}/query?type={query_type}", json={"question": question})
```

---

## 🚀 **COMPLETE UI EXAMPLE**

```python
import streamlit as st
import requests

API_BASE = "http://44.221.84.58:8500"

st.title("ARIS RAG Query")

# Question input
question = st.text_area("Enter your question")

# All UI parameters
col1, col2 = st.columns(2)

with col1:
    query_type = st.radio("Query Type", ["text", "image"])
    focus = st.selectbox("Focus", ["all", "important", "summary", "specific"], index=1)
    k = st.slider("Number of chunks", 1, 50, 12)
    use_mmr = st.checkbox("Use MMR", value=True)
    search_mode = st.selectbox("Search Mode", ["semantic", "keyword", "hybrid"], index=2)

with col2:
    temperature = st.slider("Temperature", 0.0, 2.0, 0.0, 0.1)
    max_tokens = st.slider("Max Tokens", 100, 4000, 1200, 100)
    use_agentic = st.checkbox("Use Agentic RAG", value=False)
    semantic_weight = st.slider("Semantic Weight", 0.0, 1.0, 0.7, 0.1)

# Document filter (optional)
documents = requests.get(f"{API_BASE}/documents").json()
doc_names = ["All"] + [doc["document_name"] for doc in documents.get("documents", [])]
selected_doc = st.selectbox("Filter by document", doc_names)
doc_id = None if selected_doc == "All" else documents["documents"][doc_names.index(selected_doc) - 1]["document_id"]

if st.button("Query"):
    # Build query URL with all parameters
    params = {
        "type": query_type,
        "focus": focus,
        "k": k,
        "use_mmr": str(use_mmr).lower(),
        "search_mode": search_mode,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "use_agentic_rag": str(use_agentic).lower(),
        "semantic_weight": semantic_weight
    }
    
    if doc_id:
        params["document_id"] = doc_id
    
    # Build URL
    url = f"{API_BASE}/query?" + "&".join([f"{k}={v}" for k, v in params.items()])
    
    # Make request
    response = requests.post(url, json={"question": question})
    
    if response.status_code == 200:
        result = response.json()
        st.success("Answer:")
        st.write(result["answer"])
        
        st.info(f"Used {result['num_chunks_used']} chunks")
        st.info(f"Response time: {result['response_time']:.2f}s")
        
        with st.expander("Citations"):
            for citation in result["citations"]:
                st.write(f"**{citation['source']}** (Page {citation.get('page', 'N/A')})")
                st.write(citation["snippet"])
    else:
        st.error(f"Error: {response.json()}")
```

---

## 📊 **PARAMETER PRIORITY**

When the same parameter is provided in both URL and body:

**URL parameters override body parameters**

Example:
```bash
POST /query?k=20&temperature=0.5
Body: {"question": "...", "k": 10, "temperature": 0.0}

# Actual values used:
# k = 20 (from URL)
# temperature = 0.5 (from URL)
```

---

## 🧪 **TESTING EXAMPLES**

### **Example 1: All parameters in URL**
```bash
curl -X POST "http://44.221.84.58:8500/query?k=20&use_mmr=true&search_mode=hybrid&temperature=0.5&max_tokens=1500&focus=important" \
  -H "Content-Type: application/json" \
  -d '{"question":"What are the key points?"}'
```

### **Example 2: Mix of URL and body**
```bash
curl -X POST "http://44.221.84.58:8500/query?focus=important&search_mode=hybrid" \
  -H "Content-Type: application/json" \
  -d '{
    "question":"What are the specifications?",
    "k":15,
    "use_mmr":true,
    "temperature":0.3
  }'
```

### **Example 3: Document-specific with Agentic RAG**
```bash
curl -X POST "http://44.221.84.58:8500/query?document_id=abc123&use_agentic_rag=true&k=25" \
  -H "Content-Type: application/json" \
  -d '{"question":"Summarize this document"}'
```

### **Example 4: Image query with parameters**
```bash
curl -X POST "http://44.221.84.58:8500/query?type=image&k=10&focus=important" \
  -H "Content-Type: application/json" \
  -d '{"question":"Find all charts and diagrams"}'
```

---

## ✅ **SUMMARY**

**All 10 UI parameters are now available in the API:**

1. ✅ `k` - Number of chunks (1-50)
2. ✅ `use_mmr` - Maximum Marginal Relevance
3. ✅ `search_mode` - Semantic/Keyword/Hybrid
4. ✅ `temperature` - LLM temperature (0.0-2.0)
5. ✅ `max_tokens` - Max response tokens (1-4000)
6. ✅ `use_agentic_rag` - Agentic RAG mode
7. ✅ `semantic_weight` - Hybrid search weight (0.0-1.0)
8. ✅ `focus` - Query focus (all/important/summary/specific)
9. ✅ `document_id` - Document filter
10. ✅ `type` - Query type (text/image)

**Available as:**
- ✅ Query parameters (URL)
- ✅ Request body (JSON)
- ✅ URL overrides body

**Synced with UI:** ✅ Perfect 1:1 mapping

---

## 🔗 **TEST IT NOW**

**Swagger UI:** http://44.221.84.58:8500/docs

Go to the `/query` endpoint and see all parameters available!

---

**Your API now has complete parity with your UI! 🎉**
