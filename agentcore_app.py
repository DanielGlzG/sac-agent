import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore.runtime.context import RequestContext

from customer_service_agent import CustomerServiceOrchestrator


# Create AgentCore app instance
app = BedrockAgentCoreApp(debug=True)


def validate_agentcore_payload(payload: Dict[str, Any]) -> tuple[bool, Optional[str], Optional[str], Optional[Dict], Optional[str]]:
    """
    Validates AgentCore payload format for customer service agent
    
    Expected AgentCore payload:
    {
        "prompt": "Necesito ayuda con mi cuenta",
        "user_id": "247",
        "metadata": {...}  # optional
    }
    
    Returns:
        tuple: (is_valid, user_query, user_id, metadata, error_message)
    """
    try:
        # Extract required fields
        user_query = payload.get("prompt", "").strip()
        user_id = payload.get("user_id", "").strip()
        
        if not user_query:
            return False, None, None, None, "Campo 'prompt' es requerido y no puede estar vacío"
        
        if not user_id:
            return False, None, None, None, "Campo 'user_id' es requerido y no puede estar vacío"
        
        # Extract optional metadata
        metadata = payload.get("metadata", {})
        
        # Add AgentCore context to metadata
        metadata["source"] = "agentcore_runtime"
        metadata["service"] = "customer_service_agent"
        metadata["timestamp"] = datetime.now().isoformat()
        
        return True, user_query, user_id, metadata, None
        
    except Exception as e:
        return False, None, None, None, f"Error validando payload: {str(e)}"


@app.entrypoint
async def customer_service_agent(payload: Dict[str, Any], context: RequestContext) -> Dict[str, Any]:
    """
    AgentCore entrypoint for customer service agent processing
    
    Args:
        payload: Request payload with prompt, user_id, and optional metadata
        context: AgentCore request context with session management and memory
        
    Returns:
        Dict with success status, response, and execution details
    """
    start_time = datetime.now()
    session_id = context.session_id or f"agentcore_{start_time.strftime('%Y%m%d_%H%M%S_%f')}"
    
    try:
        # Validate payload format
        is_valid, user_query, user_id, metadata, error_message = validate_agentcore_payload(payload)
        
        if not is_valid:
            return {
                "success": False,
                "error": {
                    "message": error_message,
                    "session_id": session_id,
                    "timestamp": start_time.isoformat(),
                    "source": "agentcore_validation"
                }
            }
        
        # Add session info to metadata
        if metadata is None:
            metadata = {}
        metadata["session_id"] = session_id
        metadata["agentcore_context"] = True
        
        print(f"🚀 [AgentCore] Processing customer service query for user '{user_id}' in session '{session_id}'")
        print(f"📝 Query: {user_query}")
        
        # Create customer service orchestrator with AgentCore context
        # Ensure context has session_id
        if not hasattr(context, 'session_id') or not context.session_id:
            context.session_id = session_id
            
        orchestrator = CustomerServiceOrchestrator(context)
        
        # Process message using customer service agent
        response = orchestrator.chat(user_query, user_id)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Extract execution details from response for metadata
        tools_used = ["search_knowledge_base", "knowledge_assistant"] if "base de conocimientos" in response.lower() else []
        if "escalando a agente humano" in response.lower():
            tools_used.append("escalate_to_human")
        
        agents_involved = ["orchestrator"]
        if tools_used:
            agents_involved.extend(["knowledge_assistant"] if "knowledge_assistant" in tools_used else [])
        
        bedrock_queries = response.lower().count("bedrock") + response.lower().count("base de conocimientos")
        
        return {
            "success": True,
            "data": {
                "response": response,
                "session_info": {
                    "session_id": session_id,
                    "user_id": user_id,
                    "timestamp": end_time.isoformat()
                },
                "execution_details": {
                    "tools_used": tools_used,
                    "agents_involved": agents_involved,
                    "bedrock_queries": bedrock_queries,
                    "processing_time_seconds": processing_time,
                    "memory_context": bool(context and hasattr(context, 'memory')),
                    "conversation_history_available": True
                },
                "metadata": metadata
            }
        }
            
    except Exception as e:
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        error_msg = f"Error crítico en AgentCore customer service: {str(e)}"
        print(f"❌ {error_msg}")
        
        return {
            "success": False,
            "error": {
                "message": error_msg,
                "error_type": type(e).__name__,
                "session_id": session_id,
                "user_id": user_id if 'user_id' in locals() else None,
                "processing_time_seconds": processing_time,
                "timestamp": end_time.isoformat()
            }
        }


if __name__ == "__main__":
    print("🚀 Starting AgentCore Customer Service Agent...")
    app.run()