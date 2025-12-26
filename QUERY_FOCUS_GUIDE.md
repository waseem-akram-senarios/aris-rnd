# Query with Focus on Important Parts - API Guide

**Date:** December 26, 2025  
**Feature:** Enhanced query endpoint with importance/focus parameter

---

## 🎯 **NEW FEATURE: FOCUS PARAMETER**

Your query endpoint now supports a `focus` parameter to target the most important parts of documents!

---

## 📋 **QUERY ENDPOINT**

```
POST /query?type=text&document_id=xxx&focus=important
```

### **Parameters:**

1. **`type`** - Query type
   - `text` (default) - Query text chunks
   - `image` - Query images with OCR

2. **`document_id`** - Filter to specific document (optional)

3. **`focus`** - What to focus on (NEW!)
   - `all` (default) - Query all content
   - `important` - Focus on most important/relevant parts
   - `summary` - Get summary of document key points
   - `specific` - Precise answer from most relevant section

---

## 🎯 **FOCUS OPTIONS EXPLAINED**

### **1. `focus=all` (Default)**
Standard query - retrieves k chunks as specified

**Use when:**
- You want comprehensive coverage
- You need all relevant information
- Standard RAG query

**Example:**
```bash
curl -X POST "http://44.221.84.58:8500/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the specifications?",
    "k": 12
  }'
```

### **2. `focus=important` ⭐ RECOMMENDED**
Focuses on most important/relevant parts

**What it does:**
- Retrieves 2x more chunks (up to 25)
- Uses MMR for diversity (reduces redundancy)
- Uses hybrid search (semantic + keyword)
- Returns most relevant information

**Use when:**
- You want the most important information
- You need key points and critical details
- You want to avoid less relevant content

**Example:**
```bash
curl -X POST "http://44.221.84.58:8500/query?focus=important" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the key safety requirements?",
    "k": 12
  }'
```

**Result:** Retrieves 24 chunks (12 * 2), uses MMR to select most diverse and important ones

### **3. `focus=summary`**
Get a comprehensive summary

**What it does:**
- Retrieves 20 chunks for broad coverage
- Uses MMR for diverse information
- Uses hybrid search
- Automatically adds "Provide a comprehensive summary" to your question

**Use when:**
- You want an overview of the document
- You need a summary of key points
- You want to understand the main topics

**Example:**
```bash
curl -X POST "http://44.221.84.58:8500/query?focus=summary" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is this document about?",
    "k": 12
  }'
```

**Result:** Retrieves 20 chunks, asks for comprehensive summary

### **4. `focus=specific`**
Get a precise, specific answer

**What it does:**
- Retrieves only 6 most relevant chunks
- Uses semantic search only (no keyword)
- No MMR (most relevant, not diverse)
- Focused, precise answer

**Use when:**
- You need a specific fact or detail
- You want a concise answer
- You don't need comprehensive coverage

**Example:**
```bash
curl -X POST "http://44.221.84.58:8500/query?focus=specific" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the maximum temperature?",
    "k": 12
  }'
```

**Result:** Retrieves only 6 most relevant chunks, precise answer

---

## 🎨 **UI INTEGRATION**

### **Add to Your Streamlit UI:**

```python
# Query Focus Selector
focus_option = st.selectbox(
    "🎯 Query Focus",
    options=["all", "important", "summary", "specific"],
    index=1,  # Default to "important"
    help="""
    - All: Standard query
    - Important: Focus on most important parts (recommended)
    - Summary: Get document summary
    - Specific: Precise answer to specific question
    """
)

# Make API call with focus parameter
response = requests.post(
    f"{API_BASE}/query?focus={focus_option}",
    json={
        "question": question,
        "k": num_chunks
    }
)
```

### **UI Labels:**

```python
focus_labels = {
    "all": "📄 All Content - Comprehensive search",
    "important": "⭐ Important Parts - Most relevant information (Recommended)",
    "summary": "📝 Summary - Overview of key points",
    "specific": "🎯 Specific Answer - Precise and focused"
}
```

---

## 📊 **COMPARISON TABLE**

| Focus | Chunks Retrieved | Search Mode | MMR | Best For |
|-------|-----------------|-------------|-----|----------|
| `all` | k (as specified) | User's choice | User's choice | Standard queries |
| `important` | k * 2 (max 25) | Hybrid | Yes | Most important info ⭐ |
| `summary` | 20 | Hybrid | Yes | Document overview |
| `specific` | 6 (max) | Semantic | No | Precise answers |

---

## 🚀 **COMPLETE EXAMPLES**

### **Example 1: Query Important Parts of Specific Document**
```bash
curl -X POST "http://44.221.84.58:8500/query?document_id=abc123&focus=important" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the main specifications?",
    "k": 10
  }'
```

**What happens:**
- Filters to document `abc123`
- Retrieves 20 chunks (10 * 2)
- Uses hybrid search + MMR
- Returns most important specifications

### **Example 2: Get Document Summary**
```bash
curl -X POST "http://44.221.84.58:8500/query?focus=summary" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is this document about?",
    "k": 12
  }'
```

**What happens:**
- Retrieves 20 diverse chunks
- Question becomes: "Provide a comprehensive summary: What is this document about?"
- Returns comprehensive overview

### **Example 3: Specific Fact Lookup**
```bash
curl -X POST "http://44.221.84.58:8500/query?focus=specific" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the warranty period?",
    "k": 12
  }'
```

**What happens:**
- Retrieves only 6 most relevant chunks
- Semantic search for precision
- Returns specific answer

### **Example 4: Important Parts with Images**
```bash
curl -X POST "http://44.221.84.58:8500/query?type=image&focus=important" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Find important diagrams",
    "k": 10
  }'
```

**What happens:**
- Queries images
- Retrieves 20 images (10 * 2)
- Returns most important/relevant images

---

## 💡 **BEST PRACTICES**

### **When to Use Each Focus:**

1. **Use `important`** (⭐ Recommended)
   - Default choice for most queries
   - When you want key information without noise
   - When document is long and you need highlights

2. **Use `summary`**
   - First time reading a document
   - When you need an overview
   - When preparing a brief

3. **Use `specific`**
   - Looking for a specific fact
   - Need a yes/no answer
   - Want concise response

4. **Use `all`**
   - Need comprehensive coverage
   - Researching thoroughly
   - When you have specific retrieval settings

---

## 🔗 **API ENDPOINT**

**Base URL:** http://44.221.84.58:8500

**Swagger UI:** http://44.221.84.58:8500/docs

**Endpoint:** `POST /query`

**Full URL with all parameters:**
```
POST /query?type=text&document_id=xxx&focus=important
```

---

## ✅ **SUMMARY**

**New Parameter Added:** `focus`

**Options:**
- `all` - Standard query
- `important` ⭐ - Most important parts (recommended)
- `summary` - Document overview
- `specific` - Precise answer

**Synced with UI:** Add dropdown in Streamlit to let users choose focus

**Deployed:** ✅ Live on server

**Test it now:** http://44.221.84.58:8500/docs

---

**Your API now intelligently focuses on the most important parts of documents! 🎯**
