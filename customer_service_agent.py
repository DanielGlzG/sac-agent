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
    "region": "us-east-1",  # Cambiar según tu región preferida
    "model_id": "anthropic.claude-3-sonnet-20240229-v1:0",  # Solo para referencia, no se usa
    "connect_timeout": 120,
    "read_timeout": 120,
    "max_attempts": 3
}

# ID de la Knowledge Base (debe ser configurado para tu KB específica)
KNOWLEDGE_BASE_ID = os.getenv("KNOWLEDGE_BASE_ID")  # Reemplaza con tu Knowledge Base ID real

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
            
            # Cliente para operaciones de administración
            self.bedrock_agent = boto3.client(
                "bedrock-agent",
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

def create_model_ollama():
    """Crea y retorna una instancia del modelo configurado."""
    return OllamaModel(**OLLAMA_CONFIG)

def create_model_bedrock():
    """Crea y retorna una instancia del modelo configurado."""
    return BedrockModel(**BEDROCK_CONFIG)

print(os.getenv("OPENAI_API_KEY"))
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
    tools_logger.info("🕒 TOOL CALLED: get_current_time")
    result = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tools_logger.info(f"🕒 TOOL RESULT: {result}")
    return result

@tool
def search_knowledge_base(query: str, max_results: int = 15, min_score: float = 0.1) -> str:
    """
    Busca información en la base de conocimientos de AWS Bedrock.
    
    Args:
        query: Consulta de búsqueda
        max_results: Número máximo de resultados
        min_score: Puntuación mínima de relevancia
        
    Returns:
        str: Información relevante encontrada
    """
    tools_logger.info(f"🔍 TOOL CALLED: search_knowledge_base | Query: '{query}'")
    
    try:
        # Búsqueda en Bedrock Knowledge Base
        results = bedrock_client.retrieve(query, max_results, min_score)
        
        if results.get('error'):
            tools_logger.error(f"🔍 BEDROCK ERROR: {results['error']}")
            # Fallback a base de conocimientos local
        
        if not results['results']:
            tools_logger.info("🔍 BEDROCK RESULT: No se encontraron resultados en Bedrock")
            # Fallback a base de conocimientos local
        
        # Formatear resultados de Bedrock
        formatted_results = []
        total_results = len(results['results'])
        
        # Tomar los mejores resultados (máximo 3 para no sobrecargar)
        top_results = results['results'][:3]
        
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
        
        tools_logger.info(f"🔍 TOOL RESULT: Found {total_results} results from Bedrock | Showing top {len(top_results)}")
        return formatted_response
        
    except Exception as e:
        tools_logger.error(f"🔍 TOOL ERROR: {e}")
        # Fallback a base de conocimientos local en caso de error
        return search_local_knowledge_base(query)

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
    tools_logger.info(f"🚀 TOOL CALLED: escalate_to_human | Reason: {reason}")
    
    escalation_id = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # En producción, esto activaría el sistema de routing humano
    tools_logger.info(f"🚀 TOOL RESULT: Escalation created | ID: {escalation_id}")
    
    return f"""🚀 **Escalando a agente humano**

    🆔 **ID de Escalación**: {escalation_id}
    📝 **Motivo**: {reason}
    ⏱️ **Tiempo estimado de espera**: 3-5 minutos

    Un agente humano se conectará contigo pronto. Mientras tanto:
    - Mantén esta ventana abierta
    - Ten a la mano cualquier información relevante
    - Si necesitas cerrar, puedes retomar la conversación citando el ID: {escalation_id}

    🎧 También puedes llamar directamente al +1-234-567-8900"""

@tool
def advanced_knowledge_search(query: str, search_type: str = "balanced") -> str:
    """
    Búsqueda avanzada en la Knowledge Base con diferentes configuraciones.
    
    Args:
        query: Consulta de búsqueda
        search_type: Tipo de búsqueda ("precise", "balanced", "broad")
        
    Returns:
        str: Resultados de búsqueda avanzada
    """
    tools_logger.info(f"🔍 TOOL CALLED: advanced_knowledge_search | Query: '{query}' | Type: {search_type}")
    
    # Configuraciones de búsqueda
    search_configs = {
        "precise": {"max_results": 5, "min_score": 0.3},
        "balanced": {"max_results": 15, "min_score": 0.1},
        "broad": {"max_results": 30, "min_score": 0.05}
    }
    
    if search_type not in search_configs:
        search_type = "balanced"
    
    config = search_configs[search_type]
    
    try:
        results = bedrock_client.retrieve(
            query, 
            max_results=config["max_results"], 
            min_score=config["min_score"]
        )
        
        if results.get('error'):
            tools_logger.error(f"🔍 ADVANCED SEARCH ERROR: {results['error']}")
            return f"❌ Error en búsqueda avanzada: {results['error']}"
        
        if not results['results']:
            return f"ℹ️ No se encontraron resultados para búsqueda {search_type} con: \"{query}\""
        
        # Formatear resultados avanzados
        formatted_results = []
        total_results = len(results['results'])
        
        # Mostrar más o menos resultados según el tipo de búsqueda
        show_count = {"precise": 3, "balanced": 5, "broad": 8}
        display_count = min(show_count[search_type], total_results)
        
        for i, result in enumerate(results['results'][:display_count], 1):
            score = result['score']
            content = result['content']
            location = result.get('location', {})
            
            # Información de fuente si está disponible
            source_info = ""
            if location:
                if 's3Location' in location:
                    s3_info = location['s3Location']
                    uri = s3_info.get('uri', 'N/A')
                    source_info = f"\n📍 **Fuente:** {uri}"
            
            # Limitar contenido según tipo de búsqueda
            content_limits = {"precise": 600, "balanced": 800, "broad": 400}
            limit = content_limits[search_type]
            content_preview = content[:limit] + "..." if len(content) > limit else content
            
            formatted_results.append(
                f"📄 **Resultado {i}** (relevancia: {score:.3f}){source_info}\n{content_preview}"
            )
        
        type_descriptions = {
            "precise": "🎯 búsqueda precisa (alta relevancia)",
            "balanced": "⚖️ búsqueda equilibrada",
            "broad": "🌐 búsqueda amplia (máxima cobertura)"
        }
        
        formatted_response = f"🔍 **Búsqueda avanzada ({type_descriptions[search_type]})**\n\n"
        formatted_response += f"📊 **{total_results} resultados** para: \"{query}\"\n"
        formatted_response += f"🎚️ **Configuración:** máx. {config['max_results']} resultados, relevancia mín. {config['min_score']}\n\n"
        formatted_response += "\n\n".join(formatted_results)
        
        if total_results > display_count:
            formatted_response += f"\n\n💡 *Se encontraron {total_results - display_count} resultados adicionales.*"
        
        tools_logger.info(f"🔍 ADVANCED SEARCH RESULT: {total_results} total results | Displayed: {display_count}")
        return formatted_response
        
    except Exception as e:
        tools_logger.error(f"🔍 ADVANCED SEARCH ERROR: {e}")
        return f"❌ Error en búsqueda avanzada: {str(e)}"

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
    knowledge_logger.info(f"📚 AGENT CALLED: knowledge_assistant | Query: '{query}'")
    
    try:
        agent = Agent(
            model=create_model_openai(),
            system_prompt="""Eres un asistente de conocimiento especializado en información de la empresa.
            Tu trabajo es responder preguntas frecuentes usando la información de la base de conocimientos.
            
            Pautas:
            - Prioriza usar search_knowledge_base que conecta con AWS Bedrock Knowledge Base
            - Para búsquedas específicas usa advanced_knowledge_search con el tipo apropiado
            - Sé claro y conciso en tus respuestas
            - Usa emojis para mejorar la legibilidad
            - Si no tienes la información exacta, sugiere contactar soporte
            - Siempre mantén un tono amigable y profesional
            
            Herramientas disponibles:
            - search_knowledge_base: Búsqueda principal en Bedrock KB
            - advanced_knowledge_search: Búsqueda avanzada con configuraciones específicas
            - get_current_time: Obtener fecha/hora actual""",
            tools=[search_knowledge_base, advanced_knowledge_search, get_current_time]
        )
        
        response = agent(f"Responde esta consulta usando la base de conocimientos: {query}")
        knowledge_logger.info(f"📚 AGENT RESPONSE: Length: {len(str(response))} chars | Preview: {str(response)[:100]}...")
        return str(response)
        
    except Exception as e:
        knowledge_logger.error(f"📚 AGENT ERROR: {e}")
        return f"❌ Error al procesar tu consulta. Por favor contacta a soporte: {str(e)}"


# ==========================================
# AGENTE PRINCIPAL (ORCHESTRATOR)
# ==========================================

class CustomerServiceOrchestrator:
    """Agente principal que coordina todos los asistentes especializados."""
    
    def __init__(self):
        self.model = create_model_openai()
        self.session_context = {}
        
        # Prompt del sistema optimizado para servicio al cliente con Bedrock
        self.system_prompt = """🤖 **Eres el Agente Principal de Servicio al Cliente con AWS Bedrock Knowledge Base**

                            Tu misión es proporcionar un servicio excepcional coordinando con asistentes especializados y accediendo a información actualizada desde AWS Bedrock.

                            ## 🎯 **Capacidades disponibles:**

                            **📚 Knowledge Assistant**: Información general, FAQ, políticas desde AWS Bedrock Knowledge Base
                            **🚀 Escalation**: Transferencia a agentes humanos cuando sea necesario

                            ## 📋 **Pautas de interacción:**

                            1. **Saluda cordialmente** y pregunta cómo puedes ayudar
                            2. **Analiza la consulta** para determinar el asistente especializado apropiado
                            3. **Prioriza información de Bedrock** para respuestas más precisas y actualizadas
                            4. **Delega** a los asistentes especializados según corresponda
                            5. **Mantén el contexto** de la conversación y da seguimiento
                            6. **Escala a humanos** para casos complejos o cuando el cliente lo solicite
                            7. **Sé proactivo** sugiriendo soluciones adicionales

                            ## 🎨 **Estilo de comunicación:**
                            - Amigable y profesional
                            - Claro y conciso
                            - Empático con las necesidades del cliente
                            - Uso apropiado de emojis para mejorar la experiencia
                            - Respuestas estructuradas y fáciles de leer
                            - Menciona cuando la información viene de la base de conocimientos actualizada

                            ## ⚠️ **Casos de escalación:**
                            - Quejas complejas
                            - Problemas que requieren autorización especial
                            - Consultas fuera del alcance de los asistentes
                            - Solicitud explícita del cliente
                            - Fallos en la conexión con Bedrock que no se pueden resolver

                            ## 🔧 **Manejo de errores:**
                            - Si hay problemas con Bedrock, responde que no hay conexión con la base de conocimientos y que no puedes ayudarlo en este momento.
                            - Si no te sabes la respuesta, no inventes información.
                            - Si la informacion no esta disponible, menciona que no tienes la informacion y que no sabes la respuesta.

                            Comienza cada conversación con una presentación amigable y pregunta específica sobre cómo puedes ayudar."""

        # Crear el agente principal
        self.orchestrator = Agent(
            model=self.model,
            system_prompt=self.system_prompt,
            tools=[
                knowledge_assistant,
                escalate_to_human,
                get_current_time,
            ]
        )
    
    def chat(self, message: str) -> str:
        """
        Procesa un mensaje del cliente y retorna la respuesta apropiada.
        
        Args:
            message: Mensaje del cliente
            
        Returns:
            str: Respuesta del agente de servicio al cliente
        """
        orchestrator_logger.info(f"🎯 ORCHESTRATOR INPUT: '{message}'")
        
        try:
            # Procesar mensaje con el orchestrator
            response = self.orchestrator(message)
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

def main():
    """Función principal para probar el agente de servicio al cliente."""
    
    print("🤖 " + "="*60)
    print("   AGENTE DE SERVICIO AL CLIENTE - STRANDS AGENTS")
    print("="*60)
    print("💡 Escribe 'exit' para salir del chat")
    print("💡 Escribe 'help' para ver comandos disponibles")
    print("-"*60)
    
    # Crear instancia del orchestrator
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
            
            # Procesar mensaje con el agente
            response = agent.chat(user_input)
            print(f"\n🤖 {response}\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 Conversación interrumpida. ¡Hasta la próxima!")
            break
        except Exception as e:
            print(f"\n❌ Error inesperado: {e}")
            print("🔧 Por favor intenta de nuevo o contacta a soporte técnico.\n")

if __name__ == "__main__":
    main()

