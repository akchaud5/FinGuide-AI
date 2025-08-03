#!/usr/bin/env python3
"""
MCP Server for Document Ingestion
Handles document processing and vector store management for the Financial RAG System
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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

from src.ingest_documents import DocumentProcessor
from data_processor import process_all_documents
from config import logger, RAW_DIR, INDEX_DIR


class DocumentIngestionServer:
    """MCP Server for document ingestion and processing"""
    
    def __init__(self):
        self.server = Server("financial-rag-document")
        self.processor = None
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup MCP server handlers"""
        
        async def handle_list_tools() -> List[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="ingest_document",
                    description="Process and ingest a single document into the vector store",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path to the document file to ingest"
                            },
                            "force_reprocess": {
                                "type": "boolean",
                                "description": "Force reprocessing even if already cached",
                                "default": False
                            }
                        },
                        "required": ["file_path"]
                    }
                ),
                Tool(
                    name="ingest_directory",
                    description="Process and ingest all documents in a directory",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "directory_path": {
                                "type": "string",
                                "description": "Path to directory containing documents"
                            },
                            "force_reprocess": {
                                "type": "boolean",
                                "description": "Force reprocessing even if already cached",
                                "default": False
                            },
                            "file_patterns": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "File patterns to match (e.g., ['*.pdf', '*.txt'])",
                                "default": ["*.pdf", "*.txt"]
                            }
                        },
                        "required": ["directory_path"]
                    }
                ),
                Tool(
                    name="refresh_index",
                    description="Rebuild the entire vector store from scratch",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "backup_existing": {
                                "type": "boolean",
                                "description": "Create backup of existing index",
                                "default": True
                            }
                        }
                    }
                ),
                Tool(
                    name="get_ingestion_stats",
                    description="Get document processing and vector store statistics",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="validate_documents",
                    description="Validate processed documents and check for issues",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "check_embeddings": {
                                "type": "boolean",
                                "description": "Check if embeddings are properly generated",
                                "default": True
                            }
                        }
                    }
                )
            ]
        
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            try:
                if name == "ingest_document":
                    return await self._ingest_document(arguments)
                elif name == "ingest_directory":
                    return await self._ingest_directory(arguments)
                elif name == "refresh_index":
                    return await self._refresh_index(arguments)
                elif name == "get_ingestion_stats":
                    return await self._get_ingestion_stats(arguments)
                elif name == "validate_documents":
                    return await self._validate_documents(arguments)
                else:
                    return [TextContent(
                        type="text",
                        text=f"Unknown tool: {name}"
                    )]
            except Exception as e:
                logger.error(f"Error in tool {name}: {e}")
                return [TextContent(
                    type="text",
                    text=f"Error executing {name}: {str(e)}"
                )]
        
        # Register the handlers
        self.server.request_handlers["tools/list"] = handle_list_tools
        self.server.request_handlers["tools/call"] = handle_call_tool
    
    async def _ingest_document(self, args: Dict[str, Any]) -> List[TextContent]:
        """Ingest a single document"""
        file_path = Path(args["file_path"])
        force_reprocess = args.get("force_reprocess", False)
        
        if not file_path.exists():
            return [TextContent(
                type="text",
                text=f"Error: File not found: {file_path}"
            )]
        
        # Initialize processor if needed
        if not self.processor:
            self.processor = DocumentProcessor()
        
        # Process document
        documents = self.processor.process_single_document(file_path)
        
        if documents:
            # Update vector store
            self.processor.create_vector_store(documents, update_existing=True)
            
            result = {
                "status": "success",
                "file": str(file_path),
                "chunks_created": len(documents),
                "message": f"Successfully ingested {file_path.name} with {len(documents)} chunks"
            }
        else:
            result = {
                "status": "failed",
                "file": str(file_path),
                "chunks_created": 0,
                "message": f"Failed to process {file_path.name}"
            }
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    async def _ingest_directory(self, args: Dict[str, Any]) -> List[TextContent]:
        """Ingest all documents in a directory"""
        directory_path = Path(args["directory_path"])
        force_reprocess = args.get("force_reprocess", False)
        file_patterns = args.get("file_patterns", ["*.pdf", "*.txt"])
        
        if not directory_path.exists():
            return [TextContent(
                type="text",
                text=f"Error: Directory not found: {directory_path}"
            )]
        
        # Find all matching files
        all_files = []
        for pattern in file_patterns:
            all_files.extend(directory_path.rglob(pattern))
        
        if not all_files:
            return [TextContent(
                type="text",
                text=f"No files found matching patterns {file_patterns} in {directory_path}"
            )]
        
        # Initialize processor if needed
        if not self.processor:
            self.processor = DocumentProcessor()
        
        # Process all files
        total_documents = []
        processed_files = 0
        failed_files = []
        
        for file_path in all_files:
            try:
                documents = self.processor.process_single_document(file_path)
                if documents:
                    total_documents.extend(documents)
                    processed_files += 1
                else:
                    failed_files.append(str(file_path))
            except Exception as e:
                failed_files.append(f"{file_path}: {str(e)}")
        
        # Update vector store if we have documents
        if total_documents:
            self.processor.create_vector_store(total_documents, update_existing=True)
        
        result = {
            "status": "completed",
            "directory": str(directory_path),
            "total_files_found": len(all_files),
            "files_processed": processed_files,
            "files_failed": len(failed_files),
            "total_chunks_created": len(total_documents),
            "failed_files": failed_files[:10],  # Show first 10 failures
            "message": f"Processed {processed_files}/{len(all_files)} files, created {len(total_documents)} chunks"
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    async def _refresh_index(self, args: Dict[str, Any]) -> List[TextContent]:
        """Rebuild the entire vector store"""
        backup_existing = args.get("backup_existing", True)
        
        # Backup existing index if requested
        if backup_existing and INDEX_DIR.exists():
            from datetime import datetime
            backup_dir = INDEX_DIR.parent / f"faiss_index_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            import shutil
            shutil.copytree(INDEX_DIR, backup_dir)
            logger.info(f"Created backup at {backup_dir}")
        
        # Process all documents
        try:
            stats = process_all_documents(force_reprocess=True)
            
            result = {
                "status": "success",
                "backup_created": backup_existing,
                "statistics": stats,
                "message": "Vector store successfully rebuilt"
            }
        except Exception as e:
            result = {
                "status": "failed",
                "error": str(e),
                "message": f"Failed to rebuild vector store: {str(e)}"
            }
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    async def _get_ingestion_stats(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get ingestion statistics"""
        # Initialize processor if needed
        if not self.processor:
            self.processor = DocumentProcessor()
        
        stats = self.processor.get_processing_stats()
        
        # Add vector store info if available
        if (INDEX_DIR / "metadata.json").exists():
            with open(INDEX_DIR / "metadata.json", 'r') as f:
                vector_store_metadata = json.load(f)
                stats["vector_store_metadata"] = vector_store_metadata
        
        return [TextContent(
            type="text",
            text=json.dumps(stats, indent=2)
        )]
    
    async def _validate_documents(self, args: Dict[str, Any]) -> List[TextContent]:
        """Validate processed documents"""
        check_embeddings = args.get("check_embeddings", True)
        
        validation_results = {
            "vector_store_exists": (INDEX_DIR / "index.faiss").exists(),
            "metadata_exists": (INDEX_DIR / "metadata.json").exists(),
            "issues": [],
            "recommendations": []
        }
        
        # Check if vector store exists
        if not validation_results["vector_store_exists"]:
            validation_results["issues"].append("Vector store not found")
            validation_results["recommendations"].append("Run refresh_index to create vector store")
        
        # Check metadata
        if not validation_results["metadata_exists"]:
            validation_results["issues"].append("Vector store metadata not found")
        else:
            with open(INDEX_DIR / "metadata.json", 'r') as f:
                metadata = json.load(f)
                validation_results["metadata"] = metadata
        
        # Check embeddings if requested
        if check_embeddings and validation_results["vector_store_exists"]:
            try:
                from src.rag_chain import FinancialRAGChain
                rag = FinancialRAGChain()
                # Try a simple query to test embeddings
                test_result = rag.vector_store.similarity_search("test", k=1)
                validation_results["embeddings_working"] = len(test_result) > 0
            except Exception as e:
                validation_results["embeddings_working"] = False
                validation_results["issues"].append(f"Embeddings test failed: {str(e)}")
        
        # Add overall status
        validation_results["status"] = "healthy" if not validation_results["issues"] else "issues_found"
        
        return [TextContent(
            type="text",
            text=json.dumps(validation_results, indent=2)
        )]

    async def run(self, transport_type: str = "stdio"):
        """Run the MCP server"""
        if transport_type == "stdio":
            from mcp import stdio_server
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="financial-rag-document",
                        server_version="1.0.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={}
                        )
                    )
                )


async def main():
    """Main entry point"""
    server = DocumentIngestionServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())