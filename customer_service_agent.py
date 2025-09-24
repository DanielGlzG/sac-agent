"""
Agente de Servicio al Cliente con Strands Agents
==============================================

Este módulo implementa un sistema completo de servicio al cliente usando
el patrón multi-agente de Strands Agents. Incluye agentes especializados
para diferentes aspectos del servicio al cliente.

Autor: Implementación basada en Strands Agents Framework
Fecha: 2025
"""

import os
import logging
import boto3
from datetime import datetime
from typing import Dict, List, Optional, Any
from strands import Agent, tool
from strands.models.ollama import OllamaModel
from strands.models.bedrock import BedrockModel
from strands.models.openai import OpenAIModel
from strands.models.anthropic import AnthropicModel
from strands_tools import http_request, file_read, file_write
from botocore.client import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Import prompts
from prompts import SYSTEM_PROMPT_SERVICE_AGENT, SYSTEM_PROMPT_KNOWLEDGE_ASSISTANT, SYSTEM_PROMPT_SERVICE_AGENT_V2

# Import AgentCore context for memory management
try:
    from bedrock_agentcore.runtime.context import RequestContext
    from bedrock_agentcore.memory import MemoryClient
    from strands_tools.agent_core_memory import AgentCoreMemoryToolProvider
except ImportError:
    # Fallback for testing without AgentCore
    RequestContext = None
    MemoryClient = None
    AgentCoreMemoryToolProvider = None

load_dotenv()

# Configuración de logging estructurado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)

# Logger principal del agente
logger = logging.getLogger("CustomerService")

# Loggers específicos para cada componente
orchestrator_logger = logging.getLogger("CustomerService.Orchestrator")
knowledge_logger = logging.getLogger("CustomerService.Knowledge")
tools_logger = logging.getLogger("CustomerService.Tools")
memory_logger = logging.getLogger("CustomerService.Memory")

# Silenciar logs verbosos de librerías externas
logging.getLogger("strands").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("strands.telemetry.metrics").setLevel(logging.ERROR)

# Configuración del modelo
OLLAMA_CONFIG = {
    "model_id": "gpt-oss:latest",
    "host": "http://localhost:11434",
    "max_tokens": 2048,
    "temperature": 0.7,
    "top_p": 0.9,
}

BEDROCK_CONFIG = {
    "model_id": "anthropic.claude-3-sonnet-20240229-v1:0",
    "region": "us-east-1",
    "connect_timeout": 120,
    "read_timeout": 120,
    "max_attempts": 3
}

OPENAI_CONFIG = {
    "client_args": {
        "api_key": os.getenv("OPENAI_API_KEY"),
    },
    "model_id": "gpt-4o-mini",
    "params": {
        "max_tokens": 1000,
        "temperature": 0.7,
    }
}

# Configuración de AWS Bedrock
AWS_CONFIG = {
    "region": "us-west-2",  # Cambiar según tu región preferida
    "model_id": "anthropic.claude-3-sonnet-20240229-v1:0",  # Solo para referencia, no se usa
    "connect_timeout": 120,
    "read_timeout": 120,
    "max_attempts": 3
}

# ID de la Knowledge Base (debe ser configurado para tu KB específica)
KNOWLEDGE_BASE_ID = os.getenv("KNOWLEDGE_BASE_ID")  # Reemplaza con tu Knowledge Base ID real

# Configuración de AgentCore Memory
# Verificar que las variables de entorno estén configuradas
_memory_id = os.getenv("AGENTCORE_MEMORY_ID")
_region = os.getenv("AWS_REGION")
_user_pref_strategy = os.getenv("MEMORY_STRATEGY_USER_PREFERENCES")
_summaries_strategy = os.getenv("MEMORY_STRATEGY_SUMMARIES")
_semantic_strategy = os.getenv("MEMORY_STRATEGY_SEMANTIC")



MEMORY_CONFIG = {
    "memory_id": _memory_id,
    "region": _region,
    "actor_id_prefix": "customer_",  # Prefijo para identificar usuarios
    "namespaces": {
        "user_preferences": f"/strategies/{_user_pref_strategy}/actors/{{actor_id}}",
        "conversation_summaries": f"/strategies/{_summaries_strategy}/actors/{{actor_id}}/sessions/{{session_id}}",
        "semantic_memory": f"/strategies/{_semantic_strategy}/actors/{{actor_id}}"
    }
}

class BedrockKnowledgeBaseClient:
    """Cliente para interactuar con AWS Bedrock Knowledge Base (solo para recuperación)."""
    
    def __init__(self, region: str = None, knowledge_base_id: str = None):
        self.region = region or AWS_CONFIG["region"]
        self.knowledge_base_id = knowledge_base_id or KNOWLEDGE_BASE_ID
        
        # Configuración de cliente boto3
        bedrock_config = Config(
            connect_timeout=AWS_CONFIG["connect_timeout"],
            read_timeout=AWS_CONFIG["read_timeout"],
            retries={'max_attempts': AWS_CONFIG["max_attempts"]}
        )
        
        try:
            # Cliente para operaciones de runtime (consultas)
            self.bedrock_agent_runtime = boto3.client(
                "bedrock-agent-runtime",
                region_name=self.region,
                config=bedrock_config
            )
            
            
            logger.info(f"✅ Cliente Bedrock inicializado para región: {self.region}")
            
        except Exception as e:
            logger.error(f"❌ Error inicializando cliente Bedrock: {e}")
            raise
    
    def retrieve(self, query: str, max_results: int = 20, min_score: float = 0.1) -> Dict[str, Any]:
        """
        Recupera información relevante de la Knowledge Base sin generar respuesta.
        
        Args:
            query: Consulta a realizar
            max_results: Número máximo de resultados
            min_score: Puntuación mínima de relevancia
            
        Returns:
            Diccionario con los resultados de la búsqueda
        """
        try:
            logger.info(f"🔍 BEDROCK RETRIEVE: '{query}' (max={max_results}, min_score={min_score})")
            
            response = self.bedrock_agent_runtime.retrieve(
                knowledgeBaseId=self.knowledge_base_id,
                retrievalQuery={
                    'text': query
                },
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': max_results,
                    }
                }
            )
            
            # Procesar y filtrar resultados por score
            results = []
            for result in response.get('retrievalResults', []):
                score = result.get('score', 0.0)
                if score >= min_score:
                    results.append({
                        'content': result.get('content', {}).get('text', ''),
                        'score': score,
                        'location': result.get('location', {}),
                        'metadata': result.get('metadata', {})
                    })
            
            # Ordenar por score descendente
            results.sort(key=lambda x: x['score'], reverse=True)
            
            logger.info(f"📊 BEDROCK RETRIEVE RESULTS: {len(results)} resultados encontrados")
            
            return {
                'results': results,
                'total_results': len(results),
                'query': query,
                'knowledge_base_id': self.knowledge_base_id
            }
            
        except ClientError as e:
            logger.error(f"❌ Error en Bedrock retrieve: {e}")
            return {
                'results': [],
                'total_results': 0,
                'query': query,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"❌ Error inesperado en retrieve: {e}")
            return {
                'results': [],
                'total_results': 0,
                'query': query,
                'error': str(e)
            }

# Instancia global del cliente Bedrock
bedrock_client = BedrockKnowledgeBaseClient()

class AgentCoreMemoryManager:
    """Gestor de memoria para AgentCore con estrategias de corto y largo plazo."""
    
    def __init__(self, memory_id: str = None, region: str = None):
        self.memory_id = memory_id or MEMORY_CONFIG["memory_id"]
        self.region = region or MEMORY_CONFIG["region"]
        self.actor_id_prefix = MEMORY_CONFIG["actor_id_prefix"]
        self.namespaces = MEMORY_CONFIG["namespaces"]
        
        # Inicializar cliente de memoria si está disponible
        if MemoryClient:
            try:
                self.memory_client = MemoryClient(region_name=self.region)
                memory_logger.info(f"🧠 AgentCore Memory initialized | Memory ID: {self.memory_id} | Region: {self.region}")
            except Exception as e:
                memory_logger.error(f"🧠 Failed to initialize AgentCore Memory: {e}")
                self.memory_client = None
        else:
            self.memory_client = None
            memory_logger.warning("🧠 AgentCore Memory not available (import failed)")
    
    def format_actor_id(self, user_id: str) -> str:
        """Formato consistente para actor_id."""
        return f"{self.actor_id_prefix}{user_id}"
    
    def create_event(self, actor_id: str, session_id: str, user_message: str, agent_response: str) -> bool:
        """
        Guarda un evento (turno de conversación) en memoria de corto plazo.
        
        Args:
            actor_id: ID del actor (usuario)
            session_id: ID de la sesión de conversación
            user_message: Mensaje del usuario
            agent_response: Respuesta del agente
            
        Returns:
            bool: True si se guardó exitosamente
        """
        if not self.memory_client:
            memory_logger.warning("🧠 Cannot create event - Memory client not available")
            return False
        
        try:
            formatted_actor_id = self.format_actor_id(actor_id)
            memory_logger.info(f"🔍 CREATE EVENT: actor_id={actor_id} -> formatted={formatted_actor_id}")
            
            # Crear evento con mensajes del turno
            self.memory_client.create_event(
                memory_id=self.memory_id,
                actor_id=formatted_actor_id,
                session_id=session_id,
                messages=[
                    (user_message, "USER"),
                    (agent_response, "ASSISTANT")
                ]
            )
            
            memory_logger.info(f"🧠 Event created | Actor: {formatted_actor_id} | Session: {session_id}")
            return True
            
        except Exception as e:
            memory_logger.error(f"🧠 Failed to create event: {e}")
            return False
    
    def retrieve_memories(self, actor_id: str, session_id: str = None, namespace_type: str = "user_preferences") -> Dict[str, Any]:
        """
        Recupera memorias de largo plazo usando las estrategias configuradas.
        
        Args:
            actor_id: ID del actor (usuario)
            session_id: ID de sesión (opcional, para summaries)
            namespace_type: Tipo de namespace ("user_preferences", "conversation_summaries", "semantic_memory")
            
        Returns:
            Dict con las memorias recuperadas
        """
        if not self.memory_client:
            memory_logger.warning("🧠 Cannot retrieve memories - Memory client not available")
            return {"memories": [], "total": 0}
        
        try:
            formatted_actor_id = self.format_actor_id(actor_id)
            
            # Obtener el namespace template directamente
            namespace_template = self.namespaces.get(namespace_type)
            if not namespace_template:
                memory_logger.error(f"🧠 Namespace template not found for: {namespace_type}")
                return {"memories": [], "total": 0}
            
            # Construir namespace reemplazando las variables
            if namespace_type == "conversation_summaries" and session_id:
                namespace = namespace_template.format(actor_id=formatted_actor_id, session_id=session_id)
            else:
                namespace = namespace_template.format(actor_id=formatted_actor_id)
            
            # Recuperar memorias del namespace específico
            response = self.memory_client.retrieve_memories(
                memory_id=self.memory_id,
                query="user information",  # Query genérica para obtener memorias del namespace
                namespace=namespace
            )
            
            # La respuesta puede ser una lista directa o un dict con 'memories'
            if isinstance(response, list):
                memories = response
            else:
                memories = response.get("memories", [])
            
            memory_logger.info(f"🧠 Memories retrieved | Actor: {formatted_actor_id} | Namespace: {namespace} | Count: {len(memories)}")
            
            return {
                "memories": memories,
                "total": len(memories),
                "namespace": namespace,
                "actor_id": formatted_actor_id
            }
            
        except Exception as e:
            memory_logger.error(f"🧠 Failed to retrieve memories: {e}")
            return {"memories": [], "total": 0, "error": str(e)}
    
    def get_user_context(self, actor_id: str, session_id: str) -> str:
        """
        Construye contexto del usuario combinando diferentes tipos de memoria.
        
        Args:
            actor_id: ID del actor (usuario)
            session_id: ID de sesión
            
        Returns:
            str: Contexto formateado para el agente
        """
        context_parts = []
        
        try:
            # Recuperar preferencias del usuario
            user_prefs = self.retrieve_memories(actor_id, namespace_type="user_preferences")
            memory_logger.info(f"🧠 USER CONTEXT: Retrieved user preferences - {user_prefs['total']} items")
            
            if user_prefs["memories"]:
                context_parts.append("👤 **Información del usuario:**")
                for memory in user_prefs["memories"][:3]:  # Máximo 3 preferencias
                    content = memory.get('content', '') if isinstance(memory, dict) else str(memory)
                    if content:
                        context_parts.append(f"- {content}")
            
            # Recuperar resúmenes de conversaciones anteriores (solo si hay session_id)
            if session_id:
                summaries = self.retrieve_memories(actor_id, session_id, "conversation_summaries")
                memory_logger.info(f"🧠 USER CONTEXT: Retrieved conversation summaries - {summaries['total']} items")
                
                if summaries["memories"]:
                    context_parts.append("\n📝 **Conversaciones anteriores:**")
                    for memory in summaries["memories"][:2]:  # Máximo 2 resúmenes
                        content = memory.get('content', '') if isinstance(memory, dict) else str(memory)
                        if content:
                            context_parts.append(f"- {content}")
            
            # Recuperar memoria semántica
            semantic = self.retrieve_memories(actor_id, namespace_type="semantic_memory")
            memory_logger.info(f"🧠 USER CONTEXT: Retrieved semantic memory - {semantic['total']} items")
            
            if semantic["memories"]:
                context_parts.append("\n🧠 **Contexto relacionado:**")
                for memory in semantic["memories"][:2]:  # Máximo 2 elementos semánticos
                    content = memory.get('content', '') if isinstance(memory, dict) else str(memory)
                    if content:
                        context_parts.append(f"- {content}")
            
            final_context = "\n".join(context_parts) + "\n\n" if context_parts else ""
            memory_logger.info(f"🧠 USER CONTEXT: Built context with {len(context_parts)} parts | Length: {len(final_context)} chars")
            
            return final_context
            
        except Exception as e:
            memory_logger.error(f"🧠 USER CONTEXT ERROR: {e}")
            return ""

# Instancia global del gestor de memoria
memory_manager = AgentCoreMemoryManager()

def create_model_ollama():
    """Crea y retorna una instancia del modelo configurado."""
    return OllamaModel(**OLLAMA_CONFIG)

def create_model_bedrock():
    """Crea y retorna una instancia del modelo configurado."""
    return BedrockModel(**BEDROCK_CONFIG)

def create_model_openai():
    """Crea y retorna una instancia del modelo configurado."""
    return OpenAIModel(client_args={
        "api_key": os.getenv("OPENAI_API_KEY"),
    },
    model_id="gpt-4o-mini",
    params={
        "max_tokens": 1000,
        "temperature": 0.7,
    })

def create_model_anthropic():
    """Crea y retorna una instancia del modelo configurado."""
    return AnthropicModel(**ANTHROPIC_CONFIG)

# ==========================================
# HERRAMIENTAS PERSONALIZADAS
# ==========================================

@tool
def get_current_time() -> str:
    """
    Obtiene la fecha y hora actual.
    
    Returns:
        str: Fecha y hora actual en formato legible
    """
    tools_logger.info(f"🔧 TOOL INPUT: get_current_time | Params: none")
    tools_logger.info(f"🔧 TOOL PROCESSING: get_current_time | Action: Getting current system time")
    result = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tools_logger.info(f"🔧 TOOL OUTPUT: get_current_time | Result: {result}")
    return result

@tool
def search_knowledge_base(query: str) -> str:
    """
    Busca información en la base de conocimientos de AWS Bedrock.
    
    Args:
        query: Consulta de búsqueda
        
    Returns:
        str: Información relevante encontrada
    """
    tools_logger.info(f"🔧 TOOL INPUT: search_knowledge_base | Params: query='{query}'")
    
    try:
        tools_logger.info(f"🔧 TOOL PROCESSING: search_knowledge_base | Action: Calling Bedrock Knowledge Base retrieve")
        
        # Búsqueda en Bedrock Knowledge Base

        results = bedrock_client.retrieve(query, max_results=15, min_score=0.25)
        
        if results.get('error'):
            tools_logger.error(f"🔧 TOOL ERROR: search_knowledge_base | Bedrock error: {results['error']}")
        
        if not results['results']:
            tools_logger.info(f"🔧 TOOL PROCESSING: search_knowledge_base | Action: No results found in Bedrock, falling back")
        
        # Formatear resultados de Bedrock
        formatted_results = []
        total_results = len(results['results'])
        
        # Tomar los mejores resultados (máximo 3 para no sobrecargar)
        top_results = results['results'][:3]
        
        tools_logger.info(f"🔧 TOOL PROCESSING: search_knowledge_base | Action: Formatting {len(top_results)} top results from {total_results} total")
        
        for i, result in enumerate(top_results, 1):
            score = result['score']
            content = result['content']
            
            # Limitar longitud del contenido
            content_preview = content[:800] + "..." if len(content) > 800 else content
            
            formatted_results.append(
                f"📄 **Resultado {i}** (relevancia: {score:.2f})\n{content_preview}"
            )
        
        formatted_response = f"🔍 **Información encontrada en la base de conocimientos:**\n\n"
        formatted_response += f"📊 **{total_results} resultados** para: \"{query}\"\n\n"
        formatted_response += "\n\n".join(formatted_results)
        
        if total_results > 3:
            formatted_response += f"\n\n💡 *Se encontraron {total_results - 3} resultados adicionales. Puedes hacer una consulta más específica para obtener información más precisa.*"
        
        tools_logger.info(f"🔧 TOOL OUTPUT: search_knowledge_base | Result: Found {total_results} results from Bedrock | Response length: {len(formatted_response)} chars")
        return formatted_response
        
    except Exception as e:
        tools_logger.error(f"🔧 TOOL ERROR: search_knowledge_base | Exception: {e}")

@tool
def escalate_to_human(reason: str, customer_info: str = "") -> str:
    """
    Escala la conversación a un agente humano.
    
    Args:
        reason: Motivo de la escalación
        customer_info: Información adicional del cliente
        
    Returns:
        str: Confirmación de escalación
    """
    tools_logger.info(f"🔧 TOOL INPUT: escalate_to_human | Params: reason='{reason}', customer_info='{customer_info[:100]}...' ")
    
    escalation_id = datetime.now().strftime("%Y%m%d%H%M%S")
    
    tools_logger.info(f"🔧 TOOL PROCESSING: escalate_to_human | Action: Creating escalation with ID {escalation_id}")
    
    # En producción, esto activaría el sistema de routing humano
    # Aquí se haría la llamada al sistema de tickets/escalación
    tools_logger.info(f"🔧 TOOL PROCESSING: escalate_to_human | Action: Would trigger human routing system (simulated)")
    
    escalation_response = f"""🚀 **Escalando a agente humano**

    🆔 **ID de Escalación**: {escalation_id}
    📝 **Motivo**: {reason}
    ⏱️ **Tiempo estimado de espera**: 3-5 minutos

    Un agente humano se conectará contigo pronto. Mientras tanto:
    - Mantén esta ventana abierta
    - Ten a la mano cualquier información relevante
    - Si necesitas cerrar, puedes retomar la conversación citando el ID: {escalation_id}

    🎧 También puedes llamar directamente al +1-234-567-8900"""
    
    tools_logger.info(f"🔧 TOOL OUTPUT: escalate_to_human | Result: Escalation created with ID {escalation_id} | Response length: {len(escalation_response)} chars")
    
    return escalation_response


# ==========================================
# AGENTES ESPECIALIZADOS
# ==========================================

@tool
def knowledge_assistant(query: str) -> str:
    """
    Asistente especializado en consultas generales y FAQ.
    
    Args:
        query: Consulta sobre información general de la empresa
        
    Returns:
        str: Respuesta basada en la base de conocimientos
    """
    knowledge_logger.info(f"🤖 AGENT INPUT: knowledge_assistant | Message: '{query}'")
    
    try:
        knowledge_logger.info(f"🤖 AGENT PROCESSING: knowledge_assistant | Decision: Creating specialized knowledge agent")
        
        agent = Agent(
            model=create_model_openai(),
            system_prompt=SYSTEM_PROMPT_KNOWLEDGE_ASSISTANT,
            tools=[search_knowledge_base, get_current_time]
        )
        
        knowledge_logger.info(f"🤖 AGENT PROCESSING: knowledge_assistant | Decision: Executing query with knowledge base tools")
        
        response = agent(f"Responde esta consulta usando la base de conocimientos: {query}")
        
        knowledge_logger.info(f"🤖 AGENT OUTPUT: knowledge_assistant | Response: Length={len(str(response))} chars, Preview='{str(response)[:100]}...'")
        return str(response)
        
    except Exception as e:
        knowledge_logger.error(f"🤖 AGENT ERROR: knowledge_assistant | Exception: {e}")
        error_response = f"❌ Error al procesar tu consulta. Por favor contacta a soporte: {str(e)}"
        knowledge_logger.info(f"🤖 AGENT OUTPUT: knowledge_assistant | Response: Error response due to exception")
        return error_response


# ==========================================
# AGENTE PRINCIPAL (ORCHESTRATOR)
# ==========================================

class CustomerServiceOrchestrator:
    """Agente principal que coordina todos los asistentes especializados con AgentCore Memory."""
    
    def __init__(self, context: Optional['RequestContext'] = None):
        self.model = create_model_openai()
        self.context = context
        self.session_id = context.session_id if context else f"local_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Configurar memoria nativa de AgentCore si está disponible
        if AgentCoreMemoryToolProvider and MEMORY_CONFIG["memory_id"]:
            try:
                # Crear provider de memoria usando el namespace de preferencias
                namespace = MEMORY_CONFIG["namespaces"]["user_preferences"]
                
                self.memory_provider = AgentCoreMemoryToolProvider(
                    memory_id=MEMORY_CONFIG["memory_id"],
                    actor_id=f"customer_agent_{self.session_id}",  # Actor ID único por sesión
                    session_id=self.session_id,
                    namespace=namespace,  # Namespace ya configurado desde .env
                    region=MEMORY_CONFIG["region"]
                )
                memory_logger.info(f"🧠 ORCHESTRATOR INIT: AgentCore Memory provider enabled | Session: {self.session_id}")
            except Exception as e:
                memory_logger.error(f"🧠 ORCHESTRATOR INIT: Failed to setup memory provider: {e}")
                self.memory_provider = None
        else:
            self.memory_provider = None
            memory_logger.info(f"🧠 ORCHESTRATOR INIT: AgentCore Memory provider disabled | Session: {self.session_id}")
        
        # Prompt del sistema optimizado para servicio al cliente con Bedrock y memoria
        self.system_prompt = SYSTEM_PROMPT_SERVICE_AGENT_V2

        # Crear el agente principal con herramientas (incluyendo memoria si está disponible)
        tools = [knowledge_assistant]
        if self.memory_provider and hasattr(self.memory_provider, 'tools'):
            tools.extend(self.memory_provider.tools)
            
        self.orchestrator = Agent(
            model=self.model,
            system_prompt=self.system_prompt,
            tools=tools
        )
        
        memory_tools_count = len(self.memory_provider.tools) if self.memory_provider and hasattr(self.memory_provider, 'tools') else 0
        memory_logger.info(f"🧠 ORCHESTRATOR INIT: Agent created | Total tools: {len(tools)} | Memory tools: {memory_tools_count} | Provider: {'✅' if self.memory_provider else '❌'}")
    
    def chat(self, message: str, user_id: str = None) -> str:
        """
        Procesa un mensaje del cliente y retorna la respuesta apropiada usando AgentCore Memory.
        
        Args:
            message: Mensaje del cliente
            user_id: ID del usuario para contexto personalizado
            
        Returns:
            str: Respuesta del agente de servicio al cliente
        """
        orchestrator_logger.info(f"🎯 ORCHESTRATOR INPUT: '{message}' | User: {user_id} | Session: {self.session_id}")
        
        try:
            # Obtener contexto del usuario desde AgentCore Memory
            user_context = ""
            if user_id and self.session_id:
                user_context = memory_manager.get_user_context(user_id, self.session_id)
            
            # Recuperar historial de conversación local (para compatibilidad)
            conversation_history = self._get_conversation_history()
            
            # Construir contexto completo del mensaje incluyendo memoria de largo plazo
            contextualized_message = self._build_contextualized_message(message, user_id, conversation_history, user_context)
            
            # Procesar mensaje con el orchestrator (que ahora tiene herramientas de memoria)
            response = self.orchestrator(contextualized_message)
            
            # Guardar interacción en memoria local (para compatibilidad)
            self._save_interaction(message, str(response), user_id)
            
            # Guardar evento en AgentCore Memory (short-term -> long-term extraction)
            if user_id and self.session_id:
                memory_logger.info(f"🔍 SAVING EVENT: user_id={user_id}, session={self.session_id}")
                memory_logger.info(f"🔍 USER MESSAGE: {message}")
                memory_logger.info(f"🔍 AGENT RESPONSE: {str(response)[:200]}...")
                # Usar user_id directamente (el método create_event formatea internamente)
                memory_manager.create_event(user_id, self.session_id, message, str(response))
            
            orchestrator_logger.info(f"🎯 ORCHESTRATOR OUTPUT: Length: {len(str(response))} chars | Preview: {str(response)[:100]}...")
            return str(response)
            
        except Exception as e:
            logger.error(f"Error en chat: {e}")
            error_response = f"""❌ **Error del sistema**

            Disculpa, he encontrado un problema técnico. 

            🔧 **Opciones disponibles:**
            1. Intenta reformular tu consulta
            2. Contacta directamente: +1-234-567-8900
            3. Email: soporte@empresa.com

            **Error**: {str(e)}"""
            return error_response
    
    def _get_conversation_history(self) -> List[Dict[str, Any]]:
        """Recupera el historial de conversación desde AgentCore Memory."""
        if not self.context or not hasattr(self.context, 'memory'):
            memory_logger.info("🧠 MEMORY: No context available, starting fresh conversation")
            return []
        
        try:
            history = self.context.memory.get('conversation_history', [])
            memory_logger.info(f"🧠 MEMORY GET: Retrieved {len(history)} previous interactions")
            return history
        except Exception as e:
            memory_logger.error(f"🧠 MEMORY ERROR: Failed to retrieve history - {e}")
            return []
    
    def _save_interaction(self, user_message: str, agent_response: str, user_id: str = None):
        """Guarda la interacción actual en AgentCore Memory."""
        if not self.context or not hasattr(self.context, 'memory'):
            memory_logger.warning("🧠 MEMORY: No context available, cannot save interaction")
            return
        
        try:
            # Obtener historial actual
            history = self._get_conversation_history()
            
            # Añadir nueva interacción
            new_interaction = {
                'timestamp': datetime.now().isoformat(),
                'user_id': user_id,
                'user_message': user_message,
                'agent_response': agent_response,
                'session_id': self.session_id
            }
            
            history.append(new_interaction)
            
            # Limitar historial a las últimas 10 interacciones para evitar overflow
            if len(history) > 10:
                history = history[-10:]
            
            # Guardar en memoria
            self.context.memory.set('conversation_history', history)
            
            memory_logger.info(f"🧠 MEMORY SET: Saved interaction | Total history: {len(history)} items")
            
        except Exception as e:
            memory_logger.error(f"🧠 MEMORY ERROR: Failed to save interaction - {e}")
    
    def _build_contextualized_message(self, message: str, user_id: str = None, history: List[Dict] = None, user_context: str = "") -> str:
        """Construye un mensaje contextualizado con historial de conversación y memoria de largo plazo."""
        context_parts = []
        
        # Añadir contexto de memoria de largo plazo si está disponible
        if user_context:
            context_parts.append("🧠 **Memoria de largo plazo del usuario:**")
            context_parts.append(user_context)
        
        # Añadir historial de sesión reciente si existe
        if history:
            # Añadir resumen del historial reciente (hasta 3 interacciones anteriores)
            recent_history = history[-3:] if len(history) > 3 else history
            
            if recent_history:
                context_parts.append("📝 **Contexto de conversación actual:**")
                for i, interaction in enumerate(recent_history, 1):
                    context_parts.append(f"Interacción {i}:")
                    context_parts.append(f"Usuario: {interaction.get('user_message', 'N/A')}")
                    context_parts.append(f"Agente: {interaction.get('agent_response', 'N/A')[:100]}...")
                    context_parts.append("")
        
        # Añadir mensaje actual (sin incluir user_id para evitar propagación)
        context_parts.append("💬 **Mensaje actual:**")
        context_parts.append(message)
        
        contextualized_message = "\n".join(context_parts)
        
        has_long_term = bool(user_context)
        has_history = bool(history)
        memory_logger.info(f"🧠 CONTEXT: Built contextualized message | Long-term: {has_long_term} | History: {len(history) if history else 0} items")
        
        return contextualized_message

def main():
    """Función principal para probar el agente de servicio al cliente."""
    
    print("🤖 " + "="*60)
    print("   AGENTE DE SERVICIO AL CLIENTE - STRANDS AGENTS")
    print("="*60)
    print("💡 Escribe 'exit' para salir del chat")
    print("💡 Escribe 'help' para ver comandos disponibles")
    print("-"*60)
    
    # Crear instancia del orchestrator (sin context para testing local)
    agent = CustomerServiceOrchestrator()
    
    # Mensaje de bienvenida
    welcome_message = """¡Hola! 👋 Soy tu asistente de servicio al cliente con acceso a información actualizada.

    🎯 **¿En qué puedo ayudarte hoy?**

    Puedo asistirte con:
    📚 Información general y FAQ (desde base de conocimientos empresarial)
    🔧 Problemas técnicos y soporte especializado
    💼 Consultas sobre productos y ventas  
    📦 Estado de órdenes y envíos
    ☁️ Consultas avanzadas en documentación técnica
    🚀 Y mucho más...

    ✨ **Conectado a AWS Bedrock Knowledge Base** para información más precisa y actualizada.

    Solo describe tu consulta y te conectaré con el asistente especializado apropiado."""
    
    print(f"\n🤖 {welcome_message}\n")
    
    # Loop principal del chat
    while True:
        try:
            # Obtener input del usuario
            user_input = input("👤 Tú: ").strip()
            
            # Comandos especiales
            if user_input.lower() == 'exit':
                print("\n👋 ¡Gracias por usar nuestro servicio! Que tengas un excelente día.")
                break
            elif user_input.lower() == 'help':
                print("""
                🆘 **Comandos disponibles:**
                - 'exit': Salir del chat
                - 'help': Mostrar esta ayuda
                - Cualquier otra consulta será procesada por el agente

                📞 **Contacto directo:**
                - Teléfono: +1-234-567-8900
                - Email: soporte@empresa.com
                """)
                continue
            elif not user_input:
                continue
            
            # Procesar mensaje con el agente (con user_id de prueba para testing local)
            response = agent.chat(user_input, user_id="local_test_user")
            print(f"\n🤖 {response}\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 Conversación interrumpida. ¡Hasta la próxima!")
            break
        except Exception as e:
            print(f"\n❌ Error inesperado: {e}")
            print("🔧 Por favor intenta de nuevo o contacta a soporte técnico.\n")

if __name__ == "__main__":
    main()

