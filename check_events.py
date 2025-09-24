#!/usr/bin/env python3
"""
Verificador de eventos de AgentCore
==================================

Verifica qué eventos se han guardado recientemente.
"""

import os
from dotenv import load_dotenv
from bedrock_agentcore.memory import MemoryClient

def check_recent_events():
    load_dotenv()
    
    memory_id = os.getenv("AGENTCORE_MEMORY_ID")
    region = os.getenv("AWS_REGION")
    
    print(f"📝 Verificando eventos recientes...")
    print(f"Memory ID: {memory_id}")
    print("=" * 50)
    
    try:
        client = MemoryClient(region_name=region)
        
        # Buscar eventos para ambos usuarios
        users = ["123", "124", "125", "126", "127", "128", "1", "2"]
        
        for user in users:
            print(f"\n👤 EVENTOS PARA: {user}")
            print("-" * 30)
            
            try:
                # Buscar eventos específicos del usuario
                print(f"   🔍 Buscando eventos para {user}...")
                
                # Buscar eventos con múltiples queries para obtener todos los eventos
                all_events = []
                queries = ["user", "test", "customer", "message"]
                
                for query in queries:
                    try:
                        response = client.retrieve_memories(
                            memory_id=memory_id,
                            query=query,
                            namespace="/"
                        )
                        if isinstance(response, list):
                            all_events.extend(response)
                    except Exception as e:
                        print(f"      ⚠️ Error con query '{query}': {e}")
                
                # Eliminar duplicados
                unique_events = []
                seen_ids = set()
                for event in all_events:
                    if isinstance(event, dict):
                        event_id = event.get('memoryRecordId', str(event))
                        if event_id not in seen_ids:
                            seen_ids.add(event_id)
                            unique_events.append(event)
                
                # Filtrar solo eventos que realmente pertenecen a este usuario
                user_events = []
                for event in unique_events:
                    if isinstance(event, dict):
                        namespaces = event.get('namespaces', [])
                        # Verificar si el evento pertenece a este usuario
                        # (incluyendo eventos de sesiones)
                        for ns in namespaces:
                            if f"/actors/customer_{user}" in ns:
                                user_events.append(event)
                                break
                
                response = user_events
                
                if isinstance(response, list):
                    print(f"Eventos encontrados: {len(response)}")
                    
                    # Mostrar algunos eventos de ejemplo
                    for i, event in enumerate(response[:3], 1):  # Mostrar máximo 3
                        try:
                            if isinstance(event, dict):
                                content = event.get('content', event.get('text', str(event)))
                                print(f"   {i}. {str(content)[:150]}...")
                                print(f"      Campos: {list(event.keys())}")
                            else:
                                print(f"   {i}. {str(event)[:150]}...")
                        except Exception as e:
                            print(f"   {i}. ❌ Error: {e}")
                            
                    if len(response) > 3:
                        print(f"   ... y {len(response) - 3} eventos más")
                else:
                    print(f"Eventos encontrados: N/A (tipo: {type(response)})")
                
            except Exception as e:
                print(f"❌ Error buscando eventos: {e}")
        
        print(f"\n💡 SUGERENCIA:")
        print(f"Si no encuentras los eventos aquí, revisa la consola AWS en:")
        print(f"Bedrock > AgentCore > Memory > {memory_id} > Events")
        
    except Exception as e:
        print(f"❌ Error general: {e}")

if __name__ == "__main__":
    check_recent_events()
