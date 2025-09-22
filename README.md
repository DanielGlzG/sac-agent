# Agente de Consulta de Base de Datos con PyAutoGen

Este proyecto implementa un asistente de IA usando PyAutoGen que puede consultar información en una base de datos PostgreSQL alojada en AWS a través de una interfaz de línea de comandos. El agente recibe consultas de texto y devuelve información relevante obtenida directamente de la base de datos.

## 📋 Requisitos Previos

- Python 3.8 o superior
- Acceso a una base de datos PostgreSQL en AWS
- API Key para OpenAI (modelos GPT)

## 🚀 Instalación

Sigue estos pasos para configurar el proyecto en tu entorno local:

1. **Clona el repositorio:**

```bash
git clone <url_del_repositorio>
```

2. **Crea un entorno virtual:**

```bash
python -m venv .venv
```

3. **Activa el entorno virtual:**

En Windows:

```bash
.venv\Scripts\activate
```

En macOS/Linux:

```bash
source .venv/bin/activate
```

4. **Instala las dependencias:**

```bash
pip install -r requirements.txt
```

## ⚙️ Configuración

### Archivo .env

Crea un archivo `.env` en la raíz del proyecto con las siguientes variables:

```
PROJ_API_KEY=tu_api_key_de_openai

AWS_POSTGRES_HOST=tu_host_aws
AWS_POSTGRES_DB=tu_nombre_de_base_datos
AWS_POSTGRES_USER=tu_usuario
AWS_POSTGRES_PASSWORD=tu_contraseña
AWS_POSTGRES_PORT=5432
```

Reemplaza los valores con tus propias credenciales:

- `PROJ_API_KEY`: API key de OpenAI para acceder a los modelos GPT
- Credenciales de PostgreSQL en AWS para la conexión

## 🖥️ Uso

Para ejecutar el asistente:

```bash
python main.py
```

Una vez iniciado, verás el siguiente mensaje:

```
Ingrese lo que desea buscar (o 'salir' para terminar):
```

Ejemplos de consultas:

- "¿Cuántas suscripciones nuevas hay este mes?"
- "Mostrar las últimas 10 suscripciones"
- "Listar suscripciones activas"

Para salir del programa, escribe: "salir", "exit", "q" o "quit".

## 📁 Estructura del Proyecto

- `main.py`: Punto de entrada de la aplicación
- `config.py`: Configuración y carga de variables de entorno
- `agents/agent_clients.py`: Gestión de agentes de PyAutoGen
- `agents/aws_agent.py`: Configuración de los agentes específicos para AWS
- `tools/aws_tool.py`: Funciones para consultar la base de datos AWS PostgreSQL

## 🔧 Notas Técnicas

- Este sistema utiliza `sys.pycache_prefix` para centralizar todos los archivos `__pycache__` en una carpeta raíz, manteniendo el proyecto limpio y organizado.
- Por razones de seguridad, sólo se permiten consultas SELECT en la base de datos.

# text-to-sql-empresa

curl -X POST http://localhost:8080/invocations \
 -H "Content-Type: application/json" \
 -d '{
"prompt": "Necesito ayuda con mi cuenta, no puedo acceder",
"user_id": "247",
"metadata": {}
}'

aws logs delete-log-group \
 --log-group-name "/aws/bedrock-agentcore/runtimes/agentcore_app-0zf2Td5dn0-DEFAULT"

aws logs delete-log-group \
 --log-group-name "/aws/bedrock-agentcore/runtimes/agentcore_app-VZu3VRA4TG-DEFAULT"

aws logs delete-log-group \
 --log-group-name "/aws/bedrock-agentcore/runtimes/agentcore_app-VZu3VRA4TG-endpoint_bz9co"
