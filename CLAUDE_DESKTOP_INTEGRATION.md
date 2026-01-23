# 🖥️ **Claude Desktop MCP Integration Guide**

This guide shows you how to integrate your **accuracy-optimized ARIS RAG MCP server** with Claude Desktop.

---

## 📋 **Prerequisites**

1. **Claude Desktop installed** (version with MCP support)
2. **Your ARIS RAG MCP server running** at `http://44.221.84.58:8503/sse`
3. **Network access** to your server from Claude Desktop

---

## ⚙️ **Step 1: Configure Claude Desktop**

### **Location of MCP Configuration File:**

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

### **Create/Edit the Configuration File:**

If the file doesn't exist, create it. Add this configuration:

```json
{
  "mcpServers": {
    "aris-rag": {
      "command": "uvx",
      "args": ["mcp-server-sse", "--url", "http://44.221.84.58:8503/mcp"],
      "env": {}
    }
  }
}
```

**Alternative using npx:**
```json
{
  "mcpServers": {
    "aris-rag": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sse", "--url", "http://44.221.84.58:8503/mcp"],
      "env": {}
    }
  }
}
```

> **Note:** The MCP endpoint is at `/mcp`. The `/sse` endpoint redirects to `/mcp` for backwards compatibility.

---

## 🔧 **Step 2: Alternative MCP Client Setup**

If Claude Desktop MCP setup is complex, you can also use:

### **Option A: MCP CLI Client**
```bash
# Install MCP CLI
npm install -g @modelcontextprotocol/cli

# Test connection
mcp-cli connect sse --url http://44.221.84.58:8503/sse
```

### **Option B: Direct HTTP Testing**
```bash
# Test health endpoint
curl -s 'http://44.221.84.58:8503/health' | python3 -m json.tool

# Test MCP endpoint
curl -X POST "http://44.221.84.58:8503/mcp" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
  }'
```

---

## 🧪 **Step 3: Test the Integration**

### **Restart Claude Desktop**
After adding the configuration:
1. **Close Claude Desktop completely**
2. **Reopen Claude Desktop**
3. **Check if MCP tools are available**

### **Verify Tools Are Loaded**
In Claude Desktop, you should now see:
- `rag_ingest` - Add documents to RAG system
- `rag_search` - Query documents with accuracy features

---

## 💬 **Step 4: Using ARIS RAG in Claude Conversations**

### **Example 1: Ingest a Document**
```
Please help me add this maintenance manual to the RAG system:

[Use the rag_ingest tool with:]
- Content: "Monthly maintenance includes oil changes, filter replacement, and belt inspection..."
- Metadata: {"domain": "maintenance", "language": "en", "source": "manual.pdf"}
```

### **Example 2: Search for Information**
```
What are the maintenance procedures for the Model X machine?

[This will use rag_search with Agentic RAG to:]
- Decompose the question
- Search across all indexed documents
- Return relevant chunks with confidence scores
```

### **Example 3: Complex Multi-Part Questions**
```
Compare the safety procedures in the maintenance manual with the troubleshooting guide, and tell me what precautions I should take when working on hydraulic systems.

[This will trigger Agentic RAG to:]
- Break down into sub-queries
- Search multiple document types
- Synthesize comprehensive answers
```

---

## 🎯 **Accuracy Features Available in Claude**

When using your MCP server through Claude, you get:

### **Search Capabilities:**
- **Hybrid Search:** Combines semantic and keyword matching
- **Agentic RAG:** Automatically decomposes complex questions
- **Confidence Scores:** Each result shows relevance (0-100%)
- **Metadata Filtering:** Search by domain, language, source
- **Cross-Language Support:** Auto-translation for non-English queries

### **Ingestion Features:**
- **Multi-Format Support:** PDF, DOCX, TXT, S3 URIs
- **Smart Parsing:** Docling parser for maximum accuracy
- **Metadata Enrichment:** Automatic language detection
- **Chunk Optimization:** Token-aware splitting (512/128)

---

## 🔍 **Step 5: Verify Integration Success**

### **Test Commands in Claude:**

1. **Check Available Tools:**
   ```
   What MCP tools do you have access to?
   ```
   *Should show: rag_ingest, rag_search*

2. **Test Document Ingestion:**
   ```
   Please ingest this test document: "This is a test about machine safety procedures. Always wear protective gear when operating machinery."

   Use metadata: {"domain": "safety", "language": "en"}
   ```

3. **Test Search Functionality:**
   ```
   Search for information about machine safety procedures.
   ```

4. **Test Complex Questions:**
   ```
   What are the steps for maintaining industrial machinery and what safety precautions should be followed?
   ```

---

## 🚨 **Troubleshooting**

### **Issue: "MCP server not connecting"**

**Check:**
```bash
# Test health endpoint
curl -s 'http://44.221.84.58:8503/health'

# Test MCP endpoint
curl -s 'http://44.221.84.58:8503/mcp' -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

**Solutions:**
1. **Firewall:** Ensure port 8503 is accessible
2. **Network:** Check if Claude Desktop can reach your server
3. **Server Status:** Verify Docker container is running

### **Issue: "Tools not appearing in Claude"**

**Check:**
1. **Configuration File:** Verify JSON syntax is correct
2. **File Location:** Ensure config file is in the right directory
3. **Restart:** Completely close and reopen Claude Desktop
4. **Logs:** Check Claude Desktop logs for MCP errors

### **Issue: "Search returns no results"**

**Check:**
1. **Documents Indexed:** Verify documents are ingested
2. **Query Format:** Use clear, specific questions
3. **Filters:** Check if metadata filters are too restrictive

### **Issue: "Slow responses"**

**Check:**
1. **Network Latency:** Test ping to your server
2. **Server Load:** Check Docker container resources
3. **Query Complexity:** Complex queries take longer (expected)

---

## 🔧 **Advanced Configuration**

### **Multiple MCP Servers:**
```json
{
  "mcpServers": {
    "aris-rag": {
      "command": "uvx",
      "args": ["mcp-server-sse", "--url", "http://44.221.84.58:8503/sse"],
      "env": {}
    },
    "another-server": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sse", "--url", "https://another-server.com/sse"],
      "env": {}
    }
  }
}
```

### **Custom Environment Variables:**
```json
{
  "mcpServers": {
    "aris-rag": {
      "command": "uvx",
      "args": ["mcp-server-sse", "--url", "http://44.221.84.58:8503/sse"],
      "env": {
        "MCP_TIMEOUT": "30000",
        "MCP_MAX_RETRIES": "3"
      }
    }
  }
}
```

---

## 📊 **Performance Expectations**

### **Response Times:**
- **Simple queries:** 2-5 seconds
- **Complex Agentic RAG:** 5-15 seconds
- **Document ingestion:** 10-30 seconds (depends on size)

### **Accuracy Features:**
- **Confidence Scores:** 70-95% for good matches
- **Agentic Decomposition:** 3-5 sub-queries for complex questions
- **Reranking:** Top results improved by 20-30%

---

## 🎯 **Usage Examples**

### **Technical Documentation:**
```
"Find all references to error code ERR-5042 in the troubleshooting documents and explain the solution steps."
```

### **Multi-Document Analysis:**
```
"Compare the maintenance procedures in the operator manual with the service guide, highlighting any differences in safety requirements."
```

### **Specific Queries:**
```
"What are the torque specifications for bolts in the hydraulic system? Include the page numbers from the service manual."
```

### **Cross-Language Queries:**
```
"¿Cuáles son los procedimientos de mantenimiento para la máquina Modelo X?"
(Auto-translates to English for search, returns results in Spanish context)
```

---

## 🚀 **Next Steps**

1. **Configure Claude Desktop** with the MCP settings above
2. **Restart Claude Desktop** to load the configuration
3. **Test basic functionality** with simple queries
4. **Try advanced features** like Agentic RAG with complex questions
5. **Monitor performance** and accuracy metrics

---

## 📞 **Support**

If you encounter issues:

1. **Check server status:** `http://44.221.84.58:8500/health`
2. **Test MCP endpoint:** `http://44.221.84.58:8503/sse`
3. **Review logs:** Check Docker container logs
4. **Verify configuration:** Ensure JSON syntax is valid

**Your ARIS RAG MCP server is ready to enhance Claude Desktop with enterprise-grade document search and AI-powered answers!** 🎉

---

*Integration Guide Version: 1.0*  
*Server: http://44.221.84.58:8503/sse*  
*Last Updated: January 23, 2026*
