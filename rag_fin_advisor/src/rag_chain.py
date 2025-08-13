"""
RAG Chain module for Financial RAG System
Handles retrieval, LLM interaction, and response generation
"""

import os
import json
from typing import List, Dict, Optional
from datetime import datetime
import re

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.callbacks import StreamingStdOutCallbackHandler

from config import (
    INDEX_DIR, CACHE_DIR, OPENAI_API_KEY,
    MODEL_CONFIG, RETRIEVAL_CONFIG, COMPLIANCE_PATTERNS,
    logger
)
from .market_data import IndianMarketDataAPI

class FinancialRAGChain:
    """Main RAG chain for financial Q&A"""
    
    def __init__(self, streaming: bool = False, enable_market_data: bool = True):
        # Check API key
        if not OPENAI_API_KEY:
            raise ValueError("OpenAI API key not found. Set it in config/api_key.txt")
        
        # Initialize embeddings
        self.embeddings = HuggingFaceEmbeddings(
            model_name=MODEL_CONFIG["embedding_model"],
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        # Initialize LLM
        callbacks = [StreamingStdOutCallbackHandler()] if streaming else []
        self.llm = ChatOpenAI(
            model=MODEL_CONFIG["llm_model"],
            temperature=MODEL_CONFIG["temperature"],
            max_tokens=MODEL_CONFIG["max_tokens"],
            openai_api_key=OPENAI_API_KEY,
            streaming=streaming,
            callbacks=callbacks
        )
        
        # Initialize market data API
        self.market_data = IndianMarketDataAPI() if enable_market_data else None
        
        # Load vector store
        self.vector_store = self.load_vector_store()
        if not self.vector_store:
            raise ValueError("No vector store found. Run document processing first.")
        
        # Create QA chain
        self.qa_chain = self.create_qa_chain()
        
        # Query cache
        self.query_cache_file = CACHE_DIR / "query_cache.json"
        self.query_log_file = CACHE_DIR / "query_log.jsonl"
        
    def load_vector_store(self) -> Optional[FAISS]:
        """Load FAISS vector store"""
        try:
            if (INDEX_DIR / "index.faiss").exists():
                vector_store = FAISS.load_local(
                    str(INDEX_DIR),
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                logger.info("Vector store loaded successfully")
                return vector_store
            else:
                logger.error(f"No vector store found at {INDEX_DIR}")
                return None
        except Exception as e:
            logger.error(f"Error loading vector store: {e}")
            return None
    
    def create_qa_chain(self):
        """Create the QA chain with custom prompt"""
        prompt_template = """You are an expert Indian financial advisor specializing in SEBI regulations, RBI guidelines, and stock market compliance. You have deep knowledge of Indian securities laws and always provide accurate, practical advice.

Use the following context to answer the question. If the context doesn't contain enough information, provide general guidance based on standard Indian financial regulations.

Context:
{context}

Question: {question}

Instructions:
1. Provide a clear, direct answer to the question
2. Cite specific regulations, acts, or circulars when applicable (e.g., "As per SEBI (LODR) Regulations 2015...")
3. Include practical steps or requirements if relevant
4. Mention any important warnings or risks
5. If discussing procedures, provide step-by-step guidance
6. For compliance questions, mention penalties for violations
7. Always clarify if something is illegal, risky, or requires special permissions

Answer:"""
        
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"]
        )
        
        qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vector_store.as_retriever(
                search_type=RETRIEVAL_CONFIG["search_type"],
                search_kwargs={"k": RETRIEVAL_CONFIG["k"]}
            ),
            return_source_documents=True,
            chain_type_kwargs={
                "prompt": prompt,
                "verbose": False
            }
        )
        
        return qa_chain
    
    def check_compliance(self, query: str) -> List[Dict]:
        """Check query for compliance issues"""
        warnings = []
        query_lower = query.lower()
        
        for category, patterns in COMPLIANCE_PATTERNS.items():
            for pattern, warning in patterns:
                if re.search(pattern, query_lower):
                    warnings.append({
                        "category": category,
                        "pattern": pattern,
                        "warning": warning
                    })
        
        return warnings
    
    def extract_symbols_from_query(self, query: str) -> List[str]:
        """Extract stock symbols from query"""
        symbols = []
        query_upper = query.upper()
        
        # Common Indian stock symbols (basic extraction)
        common_symbols = [
            "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HDFC", "ITC", 
            "SBIN", "BHARTIARTL", "KOTAKBANK", "ASIANPAINT", "MARUTI", 
            "BAJFINANCE", "HCLTECH", "AXISBANK", "LT", "SUNPHARMA", "TITAN",
            "NIFTY", "SENSEX", "BANKNIFTY"
        ]
        
        for symbol in common_symbols:
            if symbol in query_upper:
                symbols.append(symbol)
                
        return symbols
    
    def needs_market_data(self, query: str) -> bool:
        """Check if query needs real-time market data"""
        market_keywords = [
            "price", "current", "latest", "today", "now", "real-time", "live",
            "market", "trading", "volume", "change", "gain", "loss", "index",
            "nifty", "sensex", "stock", "share", "equity"
        ]
        
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in market_keywords)
    
    async def get_market_context(self, query: str) -> Optional[Dict]:
        """Get market data context for the query"""
        if not self.market_data or not self.needs_market_data(query):
            return None
            
        try:
            context = {}
            symbols = self.extract_symbols_from_query(query)
            
            # Get market status
            market_status = await self.market_data.get_market_status()
            context["market_status"] = market_status
            
            # Get indices data
            indices = await self.market_data.get_market_indices()
            if indices:
                context["indices"] = indices
            
            # Get specific stock data if symbols found
            if symbols:
                stock_data = {}
                for symbol in symbols[:3]:  # Limit to 3 symbols
                    try:
                        data = await self.market_data.get_real_time_price(symbol)
                        if data:
                            stock_data[symbol] = {
                                "price": data.price,
                                "change": data.change,
                                "change_percent": data.change_percent,
                                "market_state": data.market_state
                            }
                    except Exception as e:
                        logger.warning(f"Failed to get data for {symbol}: {e}")
                        
                if stock_data:
                    context["stocks"] = stock_data
            
            # Get gainers/losers if query asks for market overview
            if any(word in query.lower() for word in ["gainer", "loser", "market", "overview"]):
                gainers_losers = await self.market_data.get_top_gainers_losers(5)
                if gainers_losers:
                    context["gainers_losers"] = gainers_losers
                    
            return context if context else None
            
        except Exception as e:
            logger.error(f"Error getting market context: {e}")
            return None
    
    def format_sources(self, source_documents) -> List[Dict]:
        """Format source documents for display"""
        sources = []
        seen = set()
        
        for doc in source_documents:
            source_name = doc.metadata.get("source", "Unknown")
            if source_name not in seen:
                seen.add(source_name)
                sources.append({
                    "name": source_name,
                    "regulator": doc.metadata.get("regulator", "Unknown"),
                    "doc_type": doc.metadata.get("doc_type", "Unknown"),
                    "chunk": doc.metadata.get("chunk_index", 0) + 1,
                    "total_chunks": doc.metadata.get("total_chunks", 0)
                })
        
        return sources
    
    def log_query(self, query: str, response: Dict):
        """Log query and response"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "response": response["answer"][:200] + "...",  # Log first 200 chars
            "warnings": len(response["warnings"]),
            "sources": len(response["sources"]),
            "model": MODEL_CONFIG["llm_model"]
        }
        
        # Append to log file
        with open(self.query_log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def answer(self, query: str, use_cache: bool = True) -> Dict:
        """Get answer for a query with market data integration"""
        # Check compliance
        warnings = self.check_compliance(query)
        
        # Check cache (but not for market data queries as they need fresh data)
        use_cache_for_query = use_cache and not self.needs_market_data(query)
        if use_cache_for_query and self.query_cache_file.exists():
            try:
                with open(self.query_cache_file, 'r') as f:
                    cache = json.load(f)
                    if query in cache:
                        logger.info("Using cached response")
                        cached_response = cache[query]
                        cached_response["warnings"] = warnings  # Update warnings
                        return cached_response
            except:
                pass
        
        try:
            # Get market data context if needed
            market_context = None
            if self.market_data and self.needs_market_data(query):
                logger.info("Fetching market data context...")
                import asyncio
                market_context = asyncio.run(self.get_market_context(query))
            
            # Enhance query with market data
            enhanced_query = query
            if market_context:
                market_info = self._format_market_context(market_context)
                enhanced_query = f"{query}\n\nCurrent Market Data:\n{market_info}"
            
            # Get answer from QA chain
            logger.info(f"Processing query: {query[:100]}...")
            result = self.qa_chain({"query": enhanced_query})
            
            # Format response
            response = {
                "answer": result["result"],
                "warnings": warnings,
                "sources": self.format_sources(result.get("source_documents", [])),
                "timestamp": datetime.now().isoformat()
            }
            
            # Add market data to response if available
            if market_context:
                response["market_data"] = market_context
                response["enhanced_with_market_data"] = True
            
            # Cache response (but not market data queries)
            if use_cache_for_query:
                try:
                    cache = {}
                    if self.query_cache_file.exists():
                        with open(self.query_cache_file, 'r') as f:
                            cache = json.load(f)
                    
                    cache[query] = response
                    
                    with open(self.query_cache_file, 'w') as f:
                        json.dump(cache, f, indent=2)
                except:
                    pass
            
            # Log query
            self.log_query(query, response)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            
            # Return error response
            error_response = {
                "answer": f"I encountered an error processing your query: {str(e)}. Please check if the OpenAI API key is valid and try again.",
                "warnings": warnings,
                "sources": [],
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
            return error_response
    
    def _format_market_context(self, market_context: Dict) -> str:
        """Format market context for LLM"""
        formatted = []
        
        # Market status
        if "market_status" in market_context:
            status = market_context["market_status"]
            formatted.append(f"Market Status: {status.get('market_state', 'unknown').upper()}")
            if status.get("current_time"):
                formatted.append(f"Current Time: {status['current_time']}")
        
        # Indices
        if "indices" in market_context:
            formatted.append("\nMajor Indices:")
            indices_data = market_context["indices"]
            if hasattr(indices_data, 'indices'):
                # Handle NormalizedIndices object
                for name, data in indices_data.indices.items():
                    change_sign = "+" if data["change"] >= 0 else ""
                    formatted.append(f"- {name}: ₹{data['price']:.2f} ({change_sign}{data['change_percent']:.2f}%)")
            elif isinstance(indices_data, dict) and "indices" in indices_data:
                # Handle dict format
                for name, data in indices_data["indices"].items():
                    change_sign = "+" if data["change"] >= 0 else ""
                    formatted.append(f"- {name}: ₹{data['price']:.2f} ({change_sign}{data['change_percent']:.2f}%)")
        
        # Individual stocks
        if "stocks" in market_context:
            formatted.append("\nStock Prices:")
            for symbol, data in market_context["stocks"].items():
                change_sign = "+" if data["change"] >= 0 else ""
                formatted.append(f"- {symbol}: ₹{data['price']:.2f} ({change_sign}{data['change_percent']:.2f}%)")
        
        # Gainers/Losers
        if "gainers_losers" in market_context:
            gl_data = market_context["gainers_losers"]
            if gl_data.get("top_gainers"):
                formatted.append("\nTop Gainers:")
                for stock in gl_data["top_gainers"][:3]:
                    formatted.append(f"- {stock['symbol']}: +{stock['change_percent']:.2f}%")
            
            if gl_data.get("top_losers"):
                formatted.append("\nTop Losers:")
                for stock in gl_data["top_losers"][:3]:
                    formatted.append(f"- {stock['symbol']}: {stock['change_percent']:.2f}%")
        
        return "\n".join(formatted)
    
    def get_similar_queries(self, query: str, k: int = 5) -> List[str]:
        """Get similar queries from history"""
        similar = []
        
        if not self.query_log_file.exists():
            return similar
        
        # Simple similarity based on common words
        query_words = set(query.lower().split())
        
        with open(self.query_log_file, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    logged_query = entry["query"]
                    logged_words = set(logged_query.lower().split())
                    
                    # Calculate similarity
                    common = len(query_words & logged_words)
                    if common > 2 and logged_query != query:
                        similar.append(logged_query)
                        
                    if len(similar) >= k:
                        break
                except:
                    continue
        
        return similar
    
    def get_statistics(self) -> Dict:
        """Get usage statistics"""
        stats = {
            "total_queries": 0,
            "unique_queries": set(),
            "models_used": {},
            "warnings_triggered": 0,
            "avg_sources": 0,
        }
        
        if not self.query_log_file.exists():
            return stats
        
        total_sources = 0
        
        with open(self.query_log_file, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    stats["total_queries"] += 1
                    stats["unique_queries"].add(entry["query"])
                    
                    model = entry.get("model", "unknown")
                    stats["models_used"][model] = stats["models_used"].get(model, 0) + 1
                    
                    stats["warnings_triggered"] += entry.get("warnings", 0)
                    total_sources += entry.get("sources", 0)
                except:
                    continue
        
        stats["unique_queries"] = len(stats["unique_queries"])
        if stats["total_queries"] > 0:
            stats["avg_sources"] = total_sources / stats["total_queries"]
        
        return stats

def main():
    """Main function for standalone execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Financial RAG Q&A System")
    parser.add_argument("--query", type=str, help="Ask a question")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--similar", type=str, help="Find similar queries")
    parser.add_argument("--no-cache", action="store_true", help="Don't use cache")
    parser.add_argument("--stream", action="store_true", help="Stream output")
    
    args = parser.parse_args()
    
    try:
        rag = FinancialRAGChain(streaming=args.stream)
    except Exception as e:
        print(f"❌ Error initializing RAG: {e}")
        return
    
    if args.stats:
        stats = rag.get_statistics()
        print("\n📊 RAG System Statistics:")
        print(f"Total queries: {stats['total_queries']}")
        print(f"Unique queries: {stats['unique_queries']}")
        print(f"Warnings triggered: {stats['warnings_triggered']}")
        print(f"Average sources per query: {stats['avg_sources']:.2f}")
        print("\nModels used:")
        for model, count in stats['models_used'].items():
            print(f"  {model}: {count}")
    
    elif args.similar:
        similar = rag.get_similar_queries(args.similar)
        if similar:
            print("\n📝 Similar queries:")
            for i, q in enumerate(similar, 1):
                print(f"{i}. {q}")
        else:
            print("No similar queries found")
    
    elif args.query:
        # Answer query
        response = rag.answer(args.query, use_cache=not args.no_cache)
        
        # Print warnings
        if response["warnings"]:
            print("\n⚠️ COMPLIANCE WARNINGS:")
            for warning in response["warnings"]:
                print(f"- {warning['warning']}")
            print()
        
        # Print answer
        print("📝 ANSWER:")
        print(response["answer"])
        
        # Print sources
        if response["sources"]:
            print("\n📚 SOURCES:")
            for source in response["sources"]:
                print(f"- {source['name']} ({source['regulator']} - {source['doc_type']})")
        
        print("\n" + "-"*50)
        print("Disclaimer: This is educational information based on regulations. Always consult a SEBI-registered investment advisor.")
    
    else:
        print("Use --query to ask a question, --stats for statistics, or --help for options")

if __name__ == "__main__":
    main()