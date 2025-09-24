#!/usr/bin/env python3
"""
Inspector de memorias de AgentCore
=================================

Script para ver el contenido real de las memorias almacenadas.
"""

import os
from dotenv import load_dotenv
from bedrock_agentcore.memory import MemoryClient

def inspect_memories():
    load_dotenv()
    
    # Configuración
    memory_id = os.getenv("AGENTCORE_MEMORY_ID")
    region = os.getenv("AWS_REGION")
    
    print(f"🔍 Inspeccionando memorias...")
    print(f"Memory ID: {memory_id}")
    print(f"Región: {region}")
    print("=" * 60)
    
    try:
        client = MemoryClient(region_name=region)
        
        # Usuarios a inspeccionar
        users = ["customer_123", "customer_124", "customer_125", "customer_126", "customer_127", "customer_128", "customer_1"]
        
        # Namespaces a revisar
        namespaces = {
            "user_preferences": "/strategies/memory_preference_bd9id-xvqsYoHxht/actors/{}",
            "semantic_memory": "/strategies/summary_builtin_bd9id-4YmlmD7r2Y/actors/{}",
            "conversation_summaries": "/strategies/memory_semantic_bd9id-QMh3mK4352/actors/{}"
        }
        
        for user in users:
            print(f"\n👤 USUARIO: {user}")
            print("-" * 40)
            
            for ns_type, ns_template in namespaces.items():
                namespace = ns_template.format(user)
                
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
                    
                    print(f"\n🧠 {ns_type.upper()}:")
                    print(f"   Namespace: {namespace}")
                    print(f"   Memorias encontradas: {len(memories)}")
                    
                    for i, memory in enumerate(memories, 1):
                        try:
                            if isinstance(memory, dict):
                                content = memory.get('content', memory.get('text', str(memory)))
                            else:
                                content = str(memory)
                            
                            # Mostrar contenido limpio
                            content_str = str(content)
                            preview = content_str[:200] + ('...' if len(content_str) > 200 else '')
                            print(f"   {i}. {preview}")
                            
                            # Si es un dict, mostrar todos los campos disponibles
                            if isinstance(memory, dict):
                                print(f"      Campos disponibles: {list(memory.keys())}")
                                
                        except Exception as e:
                            print(f"   {i}. ❌ Error mostrando memoria: {e}")
                            print(f"      Tipo de memoria: {type(memory)}")
                            print(f"      Memoria raw: {memory}")
                        
                except Exception as e:
                    print(f"   ❌ Error: {e}")
        
        print("\n" + "=" * 60)
        print("✅ Inspección completada")
        
    except Exception as e:
        print(f"❌ Error general: {e}")

if __name__ == "__main__":
    inspect_memories()
