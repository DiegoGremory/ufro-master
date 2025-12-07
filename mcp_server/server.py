"""
MCP server with tools:
- identify_person
- ask_normativa
"""
import os
import asyncio
import json
import base64
import io
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import httpx

from orchestrator.pp1_client import ask_pp1
from orchestrator.pp2_client import verify_person
from db.mongo import init_motor, close_motor
from db.queries import save_trace
from datetime import datetime
import time


class MCPServer:
    """MCP Server implementation"""
    
    def __init__(self):
        self.tools = {
            "identify_person": self.identify_person,
            "ask_normativa": self.ask_normativa,
        }
    
    async def identify_person(
        self, 
        image_base64: str,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        MCP tool: Identify person using PP2 facial verification
        
        Args:
            image_base64: Base64 encoded image
            filename: Optional filename (defaults to image.jpg)
            
        Returns:
            Identification result with confidence score
        """
        try:
            # Decode base64 image
            image_bytes = base64.b64decode(image_base64)
            image_file = io.BytesIO(image_bytes)
            filename = filename or "image.jpg"
            
            # Call PP2 verification
            result = await verify_person(image_file, filename)
            
            return {
                "success": result.get("success", False),
                "verified": result.get("verified", False),
                "confidence": result.get("confidence", 0.0),
                "person_id": result.get("person_id"),
                "message": "Persona identificada exitosamente" if result.get("verified") else "Persona no identificada",
                "raw_response": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Error al identificar persona: {str(e)}"
            }
    
    async def ask_normativa(
        self, 
        query: str,
        provider: Optional[str] = None,
        k: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        MCP tool: Ask normative question using PP1 chatbot
        
        Args:
            query: Query string about normative regulations
            provider: LLM provider (deepseek or chatgpt)
            k: Top K results
            
        Returns:
            Answer from normative database
        """
        try:
            result = await ask_pp1(message=query, provider=provider, k=k)
            
            return {
                "success": result.get("success", False),
                "answer": result.get("answer", ""),
                "provider": result.get("provider", provider),
                "message": "Consulta respondida exitosamente" if result.get("success") else "Error al responder consulta",
                "raw_response": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Error al consultar normativa: {str(e)}"
            }
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle MCP request
        
        Args:
            request: MCP request object
            
        Returns:
            MCP response object
        """
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name in self.tools:
                try:
                    result = await self.tools[tool_name](**arguments)
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result, ensure_ascii=False, indent=2)
                                }
                            ]
                        }
                    }
                except Exception as e:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32603,
                            "message": f"Internal error: {str(e)}"
                        }
                    }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool '{tool_name}' not found"
                    }
                }
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "identify_person",
                            "description": "Identifica una persona usando verificación facial (PP2)",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "image_base64": {
                                        "type": "string",
                                        "description": "Imagen codificada en base64"
                                    },
                                    "filename": {
                                        "type": "string",
                                        "description": "Nombre del archivo (opcional)"
                                    }
                                },
                                "required": ["image_base64"]
                            }
                        },
                        {
                            "name": "ask_normativa",
                            "description": "Consulta sobre normativa universitaria usando chatbot (PP1)",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "Pregunta sobre normativa"
                                    },
                                    "provider": {
                                        "type": "string",
                                        "enum": ["deepseek", "chatgpt"],
                                        "description": "Proveedor LLM (opcional)"
                                    },
                                    "k": {
                                        "type": "integer",
                                        "description": "Top K resultados (opcional)"
                                    }
                                },
                                "required": ["query"]
                            }
                        }
                    ]
                }
            }
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": "Method not found"}
        }


# FastAPI app for MCP server
mcp_app = FastAPI(title="UFRO MCP Server", version="1.0.0")
server = MCPServer()


@mcp_app.on_event("startup")
async def startup_event():
    """Initialize MongoDB connection on startup"""
    await init_motor()


@mcp_app.on_event("shutdown")
async def shutdown_event():
    """Close MongoDB connection on shutdown"""
    await close_motor()


@mcp_app.post("/mcp")
async def mcp_endpoint(request: Dict[str, Any]):
    """MCP endpoint handler"""
    try:
        response = await server.handle_request(request)
        return JSONResponse(content=response)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("MCP_SERVER_PORT", "9000"))
    uvicorn.run(mcp_app, host="0.0.0.0", port=port)


