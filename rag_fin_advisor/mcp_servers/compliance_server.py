#!/usr/bin/env python3
"""
MCP Server for Compliance Checking
Provides compliance validation and risk assessment for financial activities
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

from src.compliance import ComplianceChecker, RiskLevel
from config import logger


class ComplianceServer:
    """MCP Server for compliance checking and risk assessment"""
    
    def __init__(self):
        self.server = Server("financial-rag-compliance")
        self.compliance_checker = ComplianceChecker()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup MCP server handlers"""
        
        async def handle_list_tools() -> List[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="check_compliance",
                    description="Check text or query for compliance issues and violations",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Text or query to check for compliance issues"
                            },
                            "check_type": {
                                "type": "string",
                                "enum": ["query", "response", "both"],
                                "description": "Type of compliance check to perform",
                                "default": "query"
                            },
                            "include_suggestions": {
                                "type": "boolean",
                                "description": "Include compliance suggestions and alternatives",
                                "default": True
                            }
                        },
                        "required": ["text"]
                    }
                ),
                Tool(
                    name="validate_broker",
                    description="Validate if a broker is SEBI registered",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "broker_name": {
                                "type": "string",
                                "description": "Name of the broker to validate"
                            },
                            "include_alternatives": {
                                "type": "boolean",
                                "description": "Include alternative registered brokers",
                                "default": False
                            }
                        },
                        "required": ["broker_name"]
                    }
                ),
                Tool(
                    name="get_penalty_info",
                    description="Get penalty information for specific violations",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "violation_type": {
                                "type": "string",
                                "enum": ["insider_trading", "market_manipulation", "front_running", "kyc_violation"],
                                "description": "Type of violation to get penalty info for"
                            },
                            "include_cases": {
                                "type": "boolean",
                                "description": "Include example cases and precedents",
                                "default": False
                            }
                        },
                        "required": ["violation_type"]
                    }
                ),
                Tool(
                    name="assess_risk_level",
                    description="Assess the risk level of a financial activity",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "activity": {
                                "type": "string",
                                "description": "Financial activity to assess"
                            },
                            "user_profile": {
                                "type": "object",
                                "properties": {
                                    "experience_level": {
                                        "type": "string",
                                        "enum": ["beginner", "intermediate", "advanced"]
                                    },
                                    "risk_tolerance": {
                                        "type": "string",
                                        "enum": ["low", "medium", "high"]
                                    },
                                    "investment_amount": {
                                        "type": "number",
                                        "description": "Investment amount in INR"
                                    }
                                },
                                "description": "User profile for personalized risk assessment"
                            },
                            "include_recommendations": {
                                "type": "boolean",
                                "description": "Include risk mitigation recommendations",
                                "default": True
                            }
                        },
                        "required": ["activity"]
                    }
                ),
                Tool(
                    name="get_compliance_patterns",
                    description="Get all compliance patterns and their risk levels",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "risk_level": {
                                "type": "string",
                                "enum": ["illegal", "high_risk", "medium_risk", "low_risk", "info"],
                                "description": "Filter by specific risk level"
                            },
                            "category": {
                                "type": "string",
                                "description": "Filter by category (e.g., 'trading', 'investment')"
                            }
                        }
                    }
                ),
                Tool(
                    name="bulk_compliance_check",
                    description="Check multiple texts for compliance issues in batch",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "texts": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Array of texts to check for compliance"
                            },
                            "return_summary": {
                                "type": "boolean",
                                "description": "Return summary statistics",
                                "default": True
                            }
                        },
                        "required": ["texts"]
                    }
                )
            ]
        
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            try:
                if name == "check_compliance":
                    return await self._check_compliance(arguments)
                elif name == "validate_broker":
                    return await self._validate_broker(arguments)
                elif name == "get_penalty_info":
                    return await self._get_penalty_info(arguments)
                elif name == "assess_risk_level":
                    return await self._assess_risk_level(arguments)
                elif name == "get_compliance_patterns":
                    return await self._get_compliance_patterns(arguments)
                elif name == "bulk_compliance_check":
                    return await self._bulk_compliance_check(arguments)
                else:
                    return [TextContent(
                        type="text",
                        text=f"Unknown tool: {name}"
                    )]
            except Exception as e:
                logger.error(f"Error in compliance tool {name}: {e}")
                return [TextContent(
                    type="text",
                    text=f"Error executing {name}: {str(e)}"
                )]
        
        # Register the handlers
        self.server.request_handlers["tools/list"] = handle_list_tools
        self.server.request_handlers["tools/call"] = handle_call_tool
    
    async def _check_compliance(self, args: Dict[str, Any]) -> List[TextContent]:
        """Check text for compliance issues"""
        text = args["text"]
        check_type = args.get("check_type", "query")
        include_suggestions = args.get("include_suggestions", True)
        
        result = {
            "text": text,
            "check_type": check_type,
            "warnings": [],
            "risk_level": "low_risk",
            "is_compliant": True
        }
        
        # Perform compliance checks
        if check_type in ["query", "both"]:
            query_warnings = self.compliance_checker.check_query(text)
            result["warnings"].extend(query_warnings)
        
        if check_type in ["response", "both"]:
            response_warnings = self.compliance_checker.check_response(text)
            result["warnings"].extend(response_warnings)
        
        # Determine overall risk level
        if result["warnings"]:
            risk_levels = [RiskLevel(w["category"]) for w in result["warnings"] if w["category"] in [r.value for r in RiskLevel]]
            if RiskLevel.ILLEGAL in risk_levels:
                result["risk_level"] = "illegal"
                result["is_compliant"] = False
            elif RiskLevel.HIGH_RISK in risk_levels:
                result["risk_level"] = "high_risk"
            elif RiskLevel.MEDIUM_RISK in risk_levels:
                result["risk_level"] = "medium_risk"
        
        # Add suggestions if requested
        if include_suggestions and result["warnings"]:
            result["suggestions"] = self._generate_compliance_suggestions(result["warnings"])
        
        # Add disclaimer
        result["disclaimer"] = self.compliance_checker.generate_disclaimer(RiskLevel(result["risk_level"]))
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    async def _validate_broker(self, args: Dict[str, Any]) -> List[TextContent]:
        """Validate broker registration"""
        broker_name = args["broker_name"]
        include_alternatives = args.get("include_alternatives", False)
        
        validation_result = self.compliance_checker.validate_broker_registration(broker_name)
        
        result = {
            "broker_name": broker_name,
            "validation": validation_result,
            "timestamp": json.dumps({"$date": "now"}),
        }
        
        if include_alternatives and not validation_result["is_registered"]:
            # Add some well-known registered brokers
            result["registered_alternatives"] = [
                "Zerodha", "Upstox", "Groww", "Angel One", "HDFC Securities",
                "ICICI Direct", "Kotak Securities", "Motilal Oswal", "5paisa"
            ]
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    async def _get_penalty_info(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get penalty information for violations"""
        violation_type = args["violation_type"]
        include_cases = args.get("include_cases", False)
        
        penalty_info = self.compliance_checker.get_penalty_info(violation_type)
        
        result = {
            "violation_type": violation_type,
            "penalties": penalty_info
        }
        
        # Add example cases if requested
        if include_cases:
            cases = {
                "insider_trading": [
                    {
                        "case": "Rajat Gupta case",
                        "penalty": "₹5 crores fine + criminal prosecution",
                        "year": "2013"
                    }
                ],
                "market_manipulation": [
                    {
                        "case": "Ketan Parekh case", 
                        "penalty": "₹1000 crores + criminal prosecution",
                        "year": "2001"
                    }
                ]
            }
            result["example_cases"] = cases.get(violation_type, [])
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    async def _assess_risk_level(self, args: Dict[str, Any]) -> List[TextContent]:
        """Assess risk level of an activity"""
        activity = args["activity"]
        user_profile = args.get("user_profile", {})
        include_recommendations = args.get("include_recommendations", True)
        
        # Get base risk level
        base_risk = self.compliance_checker.get_risk_level(activity)
        
        result = {
            "activity": activity,
            "base_risk_level": base_risk.value,
            "user_profile": user_profile,
            "final_risk_assessment": base_risk.value
        }
        
        # Adjust risk based on user profile
        if user_profile:
            experience = user_profile.get("experience_level", "beginner")
            risk_tolerance = user_profile.get("risk_tolerance", "low")
            amount = user_profile.get("investment_amount", 0)
            
            # Risk adjustment logic
            risk_adjustment = {
                "beginner": 1,  # Increase risk
                "intermediate": 0,  # No change
                "advanced": -1   # Decrease risk
            }
            
            tolerance_adjustment = {
                "low": 1,    # Increase risk perception
                "medium": 0, # No change
                "high": -1   # Decrease risk perception
            }
            
            # Simple scoring system
            risk_score = list(RiskLevel).index(base_risk)
            risk_score += risk_adjustment.get(experience, 0)
            risk_score += tolerance_adjustment.get(risk_tolerance, 0)
            
            # Large amounts increase risk
            if amount > 1000000:  # More than 10 lakh
                risk_score += 1
            
            # Clamp to valid range
            risk_score = max(0, min(len(RiskLevel) - 1, risk_score))
            final_risk = list(RiskLevel)[risk_score]
            
            result["final_risk_assessment"] = final_risk.value
            result["risk_factors"] = {
                "experience_adjustment": risk_adjustment.get(experience, 0),
                "tolerance_adjustment": tolerance_adjustment.get(risk_tolerance, 0),
                "amount_factor": amount > 1000000
            }
        
        # Add recommendations
        if include_recommendations:
            result["recommendations"] = self._generate_risk_recommendations(
                activity, RiskLevel(result["final_risk_assessment"]), user_profile
            )
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    async def _get_compliance_patterns(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get compliance patterns"""
        risk_level_filter = args.get("risk_level")
        category_filter = args.get("category")
        
        patterns = self.compliance_checker.patterns
        result = {"patterns": {}}
        
        for risk_level, pattern_list in patterns.items():
            if risk_level_filter and risk_level.value != risk_level_filter:
                continue
                
            filtered_patterns = []
            for pattern, warning in pattern_list:
                if category_filter and category_filter.lower() not in warning.lower():
                    continue
                filtered_patterns.append({
                    "pattern": pattern,
                    "warning": warning
                })
            
            if filtered_patterns:
                result["patterns"][risk_level.value] = filtered_patterns
        
        result["total_patterns"] = sum(len(p) for p in result["patterns"].values())
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
    
    async def _bulk_compliance_check(self, args: Dict[str, Any]) -> List[TextContent]:
        """Check multiple texts for compliance"""
        texts = args["texts"]
        return_summary = args.get("return_summary", True)
        
        results = []
        summary = {
            "total_texts": len(texts),
            "compliant_texts": 0,
            "non_compliant_texts": 0,
            "risk_level_counts": {},
            "common_violations": {}
        }
        
        for i, text in enumerate(texts):
            warnings = self.compliance_checker.check_query(text)
            is_compliant = len(warnings) == 0
            
            if is_compliant:
                summary["compliant_texts"] += 1
                risk_level = "compliant"
            else:
                summary["non_compliant_texts"] += 1
                # Get highest risk level
                risk_levels = [RiskLevel(w["category"]) for w in warnings if w["category"] in [r.value for r in RiskLevel]]
                if RiskLevel.ILLEGAL in risk_levels:
                    risk_level = "illegal"
                elif RiskLevel.HIGH_RISK in risk_levels:
                    risk_level = "high_risk"
                elif RiskLevel.MEDIUM_RISK in risk_levels:
                    risk_level = "medium_risk"
                else:
                    risk_level = "low_risk"
                
                # Count violation types
                for warning in warnings:
                    violation_category = warning["category"]
                    summary["common_violations"][violation_category] = summary["common_violations"].get(violation_category, 0) + 1
            
            summary["risk_level_counts"][risk_level] = summary["risk_level_counts"].get(risk_level, 0) + 1
            
            results.append({
                "index": i,
                "text": text[:100] + "..." if len(text) > 100 else text,
                "is_compliant": is_compliant,
                "risk_level": risk_level,
                "warnings_count": len(warnings),
                "warnings": warnings if not is_compliant else []
            })
        
        response = {
            "results": results
        }
        
        if return_summary:
            response["summary"] = summary
        
        return [TextContent(
            type="text",
            text=json.dumps(response, indent=2)
        )]
    
    def _generate_compliance_suggestions(self, warnings: List[Dict]) -> List[str]:
        """Generate compliance suggestions based on warnings"""
        suggestions = []
        
        for warning in warnings:
            category = warning["category"]
            if category == "illegal":
                suggestions.append("❌ This activity is illegal. Consider legal alternatives or consult a lawyer.")
            elif category == "high_risk":
                suggestions.append("⚠️ Consider starting with lower-risk investments. Educate yourself thoroughly first.")
            elif category == "medium_risk":
                suggestions.append("⚡ Ensure you understand the risks. Consider diversification.")
            else:
                suggestions.append("ℹ️ Follow all regulatory guidelines and consult a SEBI-registered advisor.")
        
        # Add general suggestions
        suggestions.append("📚 Always read official documents and regulatory guidelines")
        suggestions.append("👥 Consult with a SEBI-registered investment advisor")
        suggestions.append("🔍 Verify broker registration on SEBI website")
        
        return list(set(suggestions))  # Remove duplicates
    
    def _generate_risk_recommendations(self, activity: str, risk_level: RiskLevel, user_profile: Dict) -> List[str]:
        """Generate personalized risk recommendations"""
        recommendations = []
        
        experience = user_profile.get("experience_level", "beginner")
        
        if risk_level == RiskLevel.ILLEGAL:
            recommendations.append("🚫 Do not proceed with this activity as it's illegal")
            recommendations.append("⚖️ Consult a legal expert if you're unsure about compliance")
        elif risk_level == RiskLevel.HIGH_RISK:
            if experience == "beginner":
                recommendations.append("🎓 Gain more experience with safer investments first")
                recommendations.append("📖 Take a financial education course")
            recommendations.append("💰 Only invest money you can afford to lose")
            recommendations.append("📊 Start with small amounts to test strategies")
        elif risk_level == RiskLevel.MEDIUM_RISK:
            recommendations.append("🔄 Consider diversifying your investments")
            recommendations.append("📈 Monitor your investments regularly")
        
        # General recommendations
        recommendations.append("📋 Maintain proper records for tax purposes")
        recommendations.append("🎯 Define clear investment goals and risk tolerance")
        
        return recommendations

    async def run(self, transport_type: str = "stdio"):
        """Run the MCP server"""
        if transport_type == "stdio":
            from mcp import stdio_server
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="financial-rag-compliance",
                        server_version="1.0.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={}
                        )
                    )
                )


async def main():
    """Main entry point"""
    server = ComplianceServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())