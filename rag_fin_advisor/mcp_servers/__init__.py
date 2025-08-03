"""
MCP Servers package for Financial RAG System

This package contains Model Context Protocol (MCP) servers that expose
the RAG system's functionality as standardized tools.
"""

__version__ = "1.0.0"
__author__ = "Financial RAG Team"

# Import main server classes for easy access
from .document_server import DocumentIngestionServer
from .compliance_server import ComplianceServer
from .query_server import RAGQueryServer

__all__ = [
    "DocumentIngestionServer",
    "ComplianceServer", 
    "RAGQueryServer"
]