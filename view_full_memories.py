#!/usr/bin/env python3
"""
Visualizador completo de memorias de AgentCore
=============================================

Muestra todo el contenido sin recortar.
"""

import os
import json
from dotenv import load_dotenv
from bedrock_agentcore.memory import MemoryClient

def view_full_memories():
    load_dotenv()
    
    memory_id = os.getenv("AGENTCORE_MEMORY_ID")
    region = os.getenv("AWS_REGION")
    
    print(f"🔍 VISUALIZADOR COMPLETO DE MEMORIAS")
    print(f"Memory ID: {memory_id}")
    print(f"Región: {region}")
    print("=" * 80)
    
    try:
        client = MemoryClient(region_name=region)
        
        users = ["customer_123", "customer_124", "customer_125", "customer_126", "customer_127", "customer_128", "customer_1", "customer_2"]
        
        namespaces = {
            "🎯 PREFERENCIAS DE USUARIO": "/strategies/memory_preference_bd9id-xvqsYoHxht/actors/{}",
            "📝 RESÚMENES (SEMÁNTICA)": "/strategies/summary_builtin_bd9id-4YmlmD7r2Y/actors/{}",
            "🧠 MEMORIA SEMÁNTICA": "/strategies/memory_semantic_bd9id-QMh3mK4352/actors/{}"
        }
        
        for user in users:
            print(f"\n" + "="*80)
            print(f"👤 USUARIO: {user.upper()}")
            print("="*80)
            
            for ns_name, ns_template in namespaces.items():
                namespace = ns_template.format(user)
                
                print(f"\n{ns_name}")
                print(f"Namespace: {namespace}")
                print("-" * 80)
                
                try:
                    response = client.retrieve_memories(
                        memory_id=memory_id,
                        query="user information",
                        namespace=namespace
                    )
                    
                    if isinstance(response, list):
                        memories = response
                    else:
                        memories = response.get("memories", [])
                    
                    if memories:
                        for i, memory in enumerate(memories, 1):
                            print(f"\n📋 MEMORIA #{i}:")
                            print("-" * 40)
                            
                            if isinstance(memory, dict):
                                # Mostrar información estructurada
                                print(f"🆔 ID: {memory.get('memoryRecordId', 'N/A')}")
                                print(f"📅 Creado: {memory.get('createdAt', 'N/A')}")
                                print(f"⭐ Score: {memory.get('score', 'N/A')}")
                                print(f"🎯 Strategy: {memory.get('memoryStrategyId', 'N/A')}")
                                
                                # Contenido principal
                                content = memory.get('content', memory.get('text', ''))
                                print(f"\n📄 CONTENIDO COMPLETO:")
                                print(f"{content}")
                                
                                # Si el contenido parece JSON, intentar parsearlo
                                try:
                                    if content.startswith('{') and content.endswith('}'):
                                        parsed = json.loads(content)
                                        print(f"\n📊 CONTENIDO PARSEADO:")
                                        for key, value in parsed.items():
                                            print(f"   {key}: {value}")
                                except:
                                    pass
                            else:
                                print(f"📄 CONTENIDO: {memory}")
                            
                            print("")
                    else:
                        print("❌ No hay memorias en este namespace")
                        
                except Exception as e:
                    print(f"❌ Error: {e}")
        
        print("\n" + "="*80)
        print("✅ VISUALIZACIÓN COMPLETADA")
        print("="*80)
        
    except Exception as e:
        print(f"❌ Error general: {e}")

if __name__ == "__main__":
    view_full_memories()
