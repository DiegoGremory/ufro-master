# UFRO Orchestrator

Agente orquestador MCP con analítica en MongoDB que identifica personas y responde consultas normativas.

## Estado del Proyecto

⚠️ **Estructura completa implementada, funcionalidad parcial**

- ✅ Setup inicial, MongoDB, Cliente PP1, API REST, Lógica de fusión
- ⚠️ **Problema crítico**: Integración PP2 no funciona correctamente (siempre retorna "unknown")
- Ver sección [Debugging](#debugging) para más detalles

## Descripción

Sistema orquestador que expone API REST y tools MCP para:
- Identificar personas usando PP2 (verificador facial) ⚠️
- Responder consultas normativas usando PP1 (chatbot) ✅
- Almacenar trazas y analítica en MongoDB ✅

## Requisitos

- Python 3.11+
- Docker y Docker Compose
- MongoDB (se puede iniciar con Docker)

## Instalación

```bash
# 1. Clonar repositorio
git clone <repository-url>
cd ufro-master

# 2. Crear entorno virtual
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus configuraciones (⚠️ NO exponer IPs reales en repositorios públicos)

# 5. Iniciar MongoDB
docker-compose up -d mongodb

# 6. Crear índices
python -m db.ensure_indexes
```

## Configuración

Variables de entorno en `.env`:

```env
# MongoDB
MONGODB_URI=mongodb://admin:admin123@localhost:27017
DB_NAME=ufro

# PP1 (Chatbot) - ⚠️ Reemplazar [IP_PP1] con la IP real
PP1_URL=http://[IP_PP1]:8081

# PP2 (Verificador) - ⚠️ Reemplazar [IP_PP2] con la IP real
PP2_URL=http://[IP_PP2]:5000

# Reglas de Fusión
THRESHOLD=0.75
MARGIN=0.1
FUSION_METHOD=delta
```

## Uso

### Iniciar API REST

```bash
# Desarrollo
uvicorn api.app:app --reload

# Producción
bash scripts/run_gunicorn.sh
```

### Endpoints Principales

#### POST /identify-and-answer

⚠️ **Nota**: Actualmente bloqueado por problemas en integración PP2.

```bash
curl -X POST http://localhost:8000/identify-and-answer \
  -F "image=@persona.jpg" \
  -F "query=¿Cuál es el reglamento?" \
  -F "provider=deepseek"
```

#### GET /healthz

```bash
curl http://localhost:8000/healthz
```

#### GET /metrics/*

```bash
curl http://localhost:8000/metrics/identification-rate
curl http://localhost:8000/metrics/query-statistics
```

## Debugging

### Problema: PP2 siempre retorna "unknown"

Si el sistema retorna siempre `"decision": "unknown"` con `"successful_services": 0`:

1. **Verificar logs en MongoDB:**
```bash
mongosh mongodb://admin:admin123@localhost:27017/ufro
db.service_logs.find().sort({timestamp: -1}).limit(1).pretty()
```

2. **Probar PP2 directamente:**
```bash
curl -X POST ${PP2_URL}/verify -F "file=@test_image.jpg"
```

3. **Puntos de verificación:**
- `orchestrator/pp2_client.py` línea 156: Formato multipart
- `orchestrator/pp2_client.py` línea 161: Parseo JSON
- `orchestrator/fuse.py` línea 271: Filtrado de resultados exitosos

## Estructura del Proyecto

```
ufro-master/
├── api/app.py              # FastAPI application
├── orchestrator/           # Clientes PP1/PP2, fusión
├── db/                     # MongoDB conexión y queries
├── mcp_server/             # Servidor MCP
├── conf/registry.yaml      # Configuración PP2
├── docker-compose.yml      # MongoDB Docker
└── requirements.txt
```

## Tecnologías

- Python 3.11+, FastAPI, httpx, MongoDB, Pydantic, Docker

## Hitos Completados

- ✅ H1: Setup inicial
- ✅ H2: MongoDB
- ⚠️ H3-H4: Cliente PP2 (problemas en ejecución)
- ✅ H5: Fusión (lógica implementada, no ejecutada)
- ✅ H6: Cliente PP1
- ✅ H7: API REST (estructura completa, funcionalidad parcial)
- ⏳ H8-H15: Pendientes

## Licencia

[Especificar licencia]
