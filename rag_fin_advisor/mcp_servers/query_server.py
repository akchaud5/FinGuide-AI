#!/usr/bin/env python3
"""
MCP Server for RAG Queries
Handles RAG queries and returns structured responses with compliance checking
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp.server import InitializationOptions, NotificationOptions, Server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    LoggingLevel
)
import mcp

from src.rag_chain import FinancialRAGChain
from src.compliance import ComplianceChecker
from config import logger, CACHE_DIR


class RAGQueryServer:
    """MCP Server for RAG queries and document search"""
    
    def __init__(self):
        self.server = Server("financial-rag-query")
        self.rag_chain = None
        self.compliance_checker = ComplianceChecker()
        self.setup_handlers()
    
    def _initialize_rag(self):
        """Initialize RAG chain if not already done"""
        if not self.rag_chain:
            try:
                self.rag_chain = FinancialRAGChain()
                logger.info("RAG chain initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize RAG chain: {e}")
                raise
    
    def setup_handlers(self):
        """Setup MCP server handlers"""
        
        async def handle_list_tools() -> List[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="query_rag",
                    description="Execute a RAG query with compliance checking and structured response",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The query to ask the RAG system"
                            },
                            "include_compliance_check": {
                                "type": "boolean",
                                "description": "Include compliance checking in the response",
                                "default": True
                            },
                            "max_sources": {
                                "type": "integer",
                                "description": "Maximum number of source documents to return",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 20
                            },
                            "use_cache": {
                                "type": "boolean",
                                "description": "Use cached responses if available",
                                "default": True
                            },
                            "response_format": {
                                "type": "string",
                                "enum": ["structured", "markdown", "plain"],
                                "description": "Format for the response",
                                "default": "structured"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="search_documents",
                    description="Search documents without LLM processing (raw retrieval)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query for document retrieval"
                            },
                            "k": {
                                "type": "integer",
                                "description": "Number of documents to retrieve",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 50
                            },
                            "search_type": {
                                "type": "string",
                                "enum": ["similarity", "mmr"],
                                "description": "Type of search to perform",
                                "default": "similarity"
                            },
                            "include_content": {
                                "type": "boolean",
                                "description": "Include document content in results",
                                "default": False
                            },
                            "filter_by_regulator": {
                                "type": "string",
                                "description": "Filter results by regulator (SEBI, RBI, etc.)"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="get_similar_queries",
                    description="Find similar queries from search history",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Query to find similar matches for"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of similar queries to return",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 20
                            },
                            "include_responses": {
                                "type": "boolean",
                                "description": "Include response previews",
                                "default": False
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="get_query_stats",
                    description="Get query usage statistics and analytics",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "time_period": {
                                "type": "string",
                                "enum": ["today", "week", "month", "all"],
                                "description": "Time period for statistics",
                                "default": "all"
                            },
                            "include_trends": {
                                "type": "boolean",
                                "description": "Include trending topics and patterns",
                                "default": True
                            }
                        }
                    }
                ),
                Tool(
                    name="explain_answer",
                    description="Get detailed explanation of how an answer was generated",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The original query"
                            },
                            "include_retrieval_details": {
                                "type": "boolean",
                                "description": "Include details about document retrieval",
                                "default": True
                            },
                            "include_prompt_details": {
                                "type": "boolean",
                                "description": "Include details about prompt construction",
                                "default": False
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="validate_rag_system",
                    description="Validate that the RAG system is working correctly",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "run_test_queries": {
                                "type": "boolean",
                                "description": "Run test queries to validate functionality",
                                "default": True
                            },
                            "check_embeddings": {
                                "type": "boolean",
                                "description": "Check if embeddings are working",
                                "default": True
                            }
                        }
                    }
                )
            ]
        
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            try:
                if name == "query_rag":
                    return await self._query_rag(arguments)
                elif name == "search_documents":
                    return await self._search_documents(arguments)
                elif name == "get_similar_queries":
                    return await self._get_similar_queries(arguments)
                elif name == "get_query_stats":
                    return await self._get_query_stats(arguments)
                elif name == "explain_answer":
                    return await self._explain_answer(arguments)
                elif name == "validate_rag_system":
                    return await self._validate_rag_system(arguments)
                else:
                    return [TextContent(
                        type="text",
                        text=f"Unknown tool: {name}"
                    )]
            except Exception as e:
                logger.error(f"Error in RAG tool {name}: {e}")
                return [TextContent(
                    type="text",
                    text=f"Error executing {name}: {str(e)}"
                )]
        
        # Register the handlers
        self.server.request_handlers["tools/list"] = handle_list_tools
        self.server.request_handlers["tools/call"] = handle_call_tool
    
    async def _query_rag(self, args: Dict[str, Any]) -> List[TextContent]:
        """Execute RAG query"""
        query = args["query"]
        include_compliance_check = args.get("include_compliance_check", True)
        max_sources = args.get("max_sources", 5)
        use_cache = args.get("use_cache", True)
        response_format = args.get("response_format", "structured")
        
        # Initialize RAG if needed
        self._initialize_rag()
        
        # Execute query
        response = self.rag_chain.answer(query, use_cache=use_cache)
        
        # Structure the response
        result = {
            "query": query,
            "answer": response["answer"],
            "timestamp": response["timestamp"],
            "sources": response.get("sources", [])[:max_sources],
            "compliance": {
                "warnings": response.get("warnings", []),
                "compliance_check_performed": include_compliance_check
            }
        }
        
        # Add additional compliance check if requested
        if include_compliance_check:
            query_compliance = self.compliance_checker.check_query(query)
            response_compliance = self.compliance_checker.check_response(response["answer"])
            
            result["compliance"]["query_warnings"] = query_compliance
            result["compliance"]["response_warnings"] = response_compliance
            result["compliance"]["total_warnings"] = len(query_compliance) + len(response_compliance) + len(response.get("warnings", []))
        
        # Add metadata
        result["metadata"] = {
            "response_format": response_format,
            "processing_time_ms": None,  # Could add timing if needed
            "model_used": "gpt-3.5-turbo",  # From config
            "cache_hit": use_cache and query in (self.rag_chain.query_cache_file.exists() if hasattr(self.rag_chain, 'query_cache_file') else False)
        }
        
        # Format based on requested format
        if response_format == "markdown":
            formatted_response = self._format_as_markdown(result)
        elif response_format == "plain":
            formatted_response = result["answer"]
        else:
            formatted_response = json.dumps(result, indent=2)
        
        return [TextContent(
            type="text",
            text=formatted_response
        )]
    
    async def _search_documents(self, args: Dict[str, Any]) -> List[TextContent]:
        """Search documents without LLM processing"""
        query = args["query"]
        k = args.get("k", 5)
        search_type = args.get("search_type", "similarity")
        include_content = args.get("include_content", False)
        filter_by_regulator = args.get("filter_by_regulator")
        
        # Initialize RAG if needed
        self._initialize_rag()
        
        # Perform search
        if search_type == "mmr":
            documents = self.rag_chain.vector_store.max_marginal_relevance_search(query, k=k)
        else:
            documents = self.rag_chain.vector_store.similarity_search(query, k=k)
        
        # Filter by regulator if specified
        if filter_by_regulator:
            documents = [doc for doc in documents if doc.metadata.get("regulator", "").lower() == filter_by_regulator.lower()]
        
        # Format results
        results = []
        for i, doc in enumerate(documents):
            result = {
                "index": i,
                "metadata": doc.metadata,
                "relevance_score": None,  # FAISS doesn't return scores by default
            }
            
            if include_content:
                result["content"] = doc.page_content[:500] + "..." if len(doc.page_content) > 500 else doc.page_content
            else:
                result["content_preview"] = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
            
            results.append(result)
        
        response = {
            "query": query,
            "search_type": search_type,
            "total_results": len(results),
            "filter_applied": filter_by_regulator,
            "results": results
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(response, indent=2)
        )]
    
    async def _get_similar_queries(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get similar queries from history"""
        query = args["query"]
        limit = args.get("limit", 5)
        include_responses = args.get("include_responses", False)
        
        # Initialize RAG if needed
        self._initialize_rag()
        
        # Get similar queries
        similar_queries = self.rag_chain.get_similar_queries(query, k=limit)
        
        results = []
        for similar_query in similar_queries:
            result = {
                "query": similar_query,
                "similarity_reason": "common_words",  # Could be enhanced with actual similarity scoring
            }
            
            if include_responses:
                # Try to get cached response
                try:
                    if hasattr(self.rag_chain, 'query_cache_file') and self.rag_chain.query_cache_file.exists():
                        with open(self.rag_chain.query_cache_file, 'r') as f:
                            cache = json.load(f)
                            if similar_query in cache:
                                result["response_preview"] = cache[similar_query]["answer"][:200] + "..."
                except:
                    pass
            
            results.append(result)
        
        response = {
            "original_query": query,
            "similar_queries": results,
            "total_found": len(results)
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(response, indent=2)
        )]
    
    async def _get_query_stats(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get query statistics"""
        time_period = args.get("time_period", "all")
        include_trends = args.get("include_trends", True)
        
        # Initialize RAG if needed
        self._initialize_rag()
        
        # Get statistics
        stats = self.rag_chain.get_statistics()
        
        # Add time period filtering if log file exists
        if hasattr(self.rag_chain, 'query_log_file') and self.rag_chain.query_log_file.exists():
            # Could add time-based filtering here
            pass
        
        result = {
            "time_period": time_period,
            "statistics": stats,
            "generated_at": datetime.now().isoformat()
        }
        
        if include_trends:
            # Add basic trend analysis
            result["trends"] = {
                "most_active_day": "Unknown",  # Could analyze log timestamps
                "common_query_types": [],      # Could categorize queries
                "peak_usage_hours": []         # Could analyze usage patterns
            }
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    async def _explain_answer(self, args: Dict[str, Any]) -> List[TextContent]:
        """Explain how an answer was generated"""
        query = args["query"]
        include_retrieval_details = args.get("include_retrieval_details", True)
        include_prompt_details = args.get("include_prompt_details", False)
        
        # Initialize RAG if needed
        self._initialize_rag()
        
        explanation = {
            "query": query,
            "process_steps": [
                "1. Query preprocessing and compliance checking",
                "2. Vector similarity search in document database",
                "3. Document retrieval and ranking",
                "4. Context construction from retrieved documents",
                "5. LLM query with constructed prompt",
                "6. Response post-processing and compliance validation"
            ]
        }
        
        if include_retrieval_details:
            # Get retrieval details
            documents = self.rag_chain.vector_store.similarity_search(query, k=5)
            explanation["retrieval_details"] = {
                "documents_found": len(documents),
                "retrieval_method": "FAISS similarity search",
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "top_sources": [doc.metadata.get("source", "Unknown") for doc in documents[:3]]
            }
        
        if include_prompt_details:
            explanation["prompt_details"] = {
                "prompt_template": "Financial advisor prompt with context injection",
                "context_length": "Varies based on retrieved documents",
                "model_parameters": {
                    "temperature": 0.1,
                    "max_tokens": 1000
                }
            }
        
        return [TextContent(
            type="text",
            text=json.dumps(explanation, indent=2)
        )]
    
    async def _validate_rag_system(self, args: Dict[str, Any]) -> List[TextContent]:
        """Validate RAG system functionality"""
        run_test_queries = args.get("run_test_queries", True)
        check_embeddings = args.get("check_embeddings", True)
        
        validation_results = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "checks": {}
        }
        
        try:
            # Initialize RAG
            self._initialize_rag()
            validation_results["checks"]["rag_initialization"] = {"status": "pass", "message": "RAG chain initialized successfully"}
        except Exception as e:
            validation_results["checks"]["rag_initialization"] = {"status": "fail", "message": f"Failed to initialize: {str(e)}"}
            validation_results["overall_status"] = "failed"
            
            return [TextContent(
                type="text",
                text=json.dumps(validation_results, indent=2)
            )]
        
        # Check vector store
        try:
            test_search = self.rag_chain.vector_store.similarity_search("test", k=1)
            validation_results["checks"]["vector_store"] = {
                "status": "pass",
                "message": f"Vector store accessible, returned {len(test_search)} results"
            }
        except Exception as e:
            validation_results["checks"]["vector_store"] = {"status": "fail", "message": f"Vector store error: {str(e)}"}
            validation_results["overall_status"] = "degraded"
        
        # Test embeddings if requested
        if check_embeddings:
            try:
                # Try to generate embeddings
                test_embedding = self.rag_chain.embeddings.embed_query("test query")
                validation_results["checks"]["embeddings"] = {
                    "status": "pass",
                    "message": f"Embeddings working, dimension: {len(test_embedding)}"
                }
            except Exception as e:
                validation_results["checks"]["embeddings"] = {"status": "fail", "message": f"Embeddings error: {str(e)}"}
                validation_results["overall_status"] = "degraded"
        
        # Run test queries if requested
        if run_test_queries:
            test_queries = [
                "What is SEBI?",
                "How to open demat account?"
            ]
            
            test_results = []
            for test_query in test_queries:
                try:
                    response = self.rag_chain.answer(test_query, use_cache=False)
                    test_results.append({
                        "query": test_query,
                        "status": "pass",
                        "response_length": len(response["answer"]),
                        "sources_found": len(response.get("sources", []))
                    })
                except Exception as e:
                    test_results.append({
                        "query": test_query,
                        "status": "fail",
                        "error": str(e)
                    })
                    validation_results["overall_status"] = "degraded"
            
            validation_results["checks"]["test_queries"] = {
                "status": "pass" if all(r["status"] == "pass" for r in test_results) else "fail",
                "results": test_results
            }
        
        return [TextContent(
            type="text",
            text=json.dumps(validation_results, indent=2)
        )]
    
    def _format_as_markdown(self, result: Dict) -> str:
        """Format response as markdown"""
        md = f"# Query Response\n\n"
        md += f"**Query:** {result['query']}\n\n"
        
        # Compliance warnings
        if result["compliance"]["warnings"]:
            md += f"## ⚠️ Compliance Warnings\n\n"
            for warning in result["compliance"]["warnings"]:
                if isinstance(warning, dict):
                    md += f"- {warning.get('warning', str(warning))}\n"
                else:
                    md += f"- {warning}\n"
            md += "\n"
        
        # Answer
        md += f"## Answer\n\n{result['answer']}\n\n"
        
        # Sources
        if result["sources"]:
            md += f"## Sources\n\n"
            for i, source in enumerate(result["sources"], 1):
                if isinstance(source, dict):
                    md += f"{i}. {source.get('name', 'Unknown')} ({source.get('regulator', 'Unknown')})\n"
                else:
                    md += f"{i}. {source}\n"
        
        return md

    async def run(self, transport_type: str = "stdio"):
        """Run the MCP server"""
        if transport_type == "stdio":
            from mcp import stdio_server
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="financial-rag-query",
                        server_version="1.0.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={}
                        )
                    )
                )


async def main():
    """Main entry point"""
    server = RAGQueryServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())