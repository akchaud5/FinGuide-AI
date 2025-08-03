# MCP Servers for Financial RAG System

This directory contains Model Context Protocol (MCP) servers that expose the RAG system's functionality as standardized tools.

## Available MCP Servers

### 1. Document Ingestion Server (`document_server.py`)
**Purpose**: Handle document processing and vector store management
**Tools**:
- `ingest_document` - Process and add a single document
- `ingest_directory` - Process all documents in a directory
- `refresh_index` - Rebuild the entire vector store
- `get_ingestion_stats` - Get processing statistics
- `validate_documents` - Validate document processing

### 2. Compliance Server (`compliance_server.py`)
**Purpose**: Provide compliance checking and risk assessment
**Tools**:
- `check_compliance` - Check query/text for compliance issues
- `validate_broker` - Validate if a broker is SEBI registered
- `get_penalty_info` - Get penalty information for violations
- `assess_risk_level` - Assess risk level of an activity
- `get_compliance_patterns` - Get all compliance patterns
- `bulk_compliance_check` - Check multiple texts in batch

### 3. RAG Query Server (`query_server.py`)
**Purpose**: Handle RAG queries and return structured responses
**Tools**:
- `query_rag` - Execute RAG query with compliance checking
- `search_documents` - Search documents without LLM processing
- `get_similar_queries` - Find similar historical queries
- `get_query_stats` - Get query usage statistics
- `explain_answer` - Get detailed explanation of answer generation
- `validate_rag_system` - Validate RAG system functionality

## Usage

### Starting the Servers

```bash
# Document Ingestion Server
python mcp_servers/document_server.py

# Compliance Server
python mcp_servers/compliance_server.py

# RAG Query Server
python mcp_servers/query_server.py
```

### Testing

```bash
# Test all servers
python mcp_servers/test_servers.py
```

### Configuration

Each server can be configured via environment variables:
- `MCP_PORT_DOCUMENT` - Port for document server (default: 8001)
- `MCP_PORT_COMPLIANCE` - Port for compliance server (default: 8002) 
- `MCP_PORT_QUERY` - Port for query server (default: 8003)

### Integration Examples

```python
# Using with Claude Desktop or other MCP clients
{
  "mcpServers": {
    "financial-rag-document": {
      "command": "python",
      "args": ["/path/to/rag_fin_advisor/mcp_servers/document_server.py"]
    },
    "financial-rag-compliance": {
      "command": "python", 
      "args": ["/path/to/rag_fin_advisor/mcp_servers/compliance_server.py"]
    },
    "financial-rag-query": {
      "command": "python",
      "args": ["/path/to/rag_fin_advisor/mcp_servers/query_server.py"]
    }
  }
}
```

## Architecture

The MCP servers provide a clean interface layer over the existing RAG system components:

```
MCP Clients (Claude Desktop, etc.)
        ↓
    MCP Servers
        ↓
Existing RAG Components
```

This design allows the RAG system to be used by any MCP-compatible client while maintaining the existing functionality for direct usage.

## Features

- **17 Total Tools** across all servers
- **Full Integration** with existing RAG components
- **Compliance Checking** with SEBI/RBI regulations
- **Document Processing** with vector store management
- **Structured Responses** with source citations
- **Risk Assessment** and penalty information
- **Query Analytics** and usage statistics