# NEMO en Docker — despliegue universal

Un solo `docker compose up` y NEMO queda conectable desde **cualquier AI** — Claude,
ChatGPT, Gemini, Copilot, Cursor, LangChain, n8n, scripts propios… Sin Python local,
sin rutas absolutas, sin `pip install` en cada máquina.

---

## Qué se levanta

La imagen expone **un solo puerto (`8765`)** con tres interfaces en paralelo:

| Ruta                     | Para qué sirve                                          | Lo consume               |
|--------------------------|---------------------------------------------------------|--------------------------|
| `GET /mcp/sse`                  | MCP sobre Server-Sent Events                       | Claude Desktop / Code, Cursor, Windsurf, Cline, VS Code Copilot |
| `POST /mcp/messages/`           | Canal de retorno MCP para los clientes SSE         | (lo usa el cliente MCP automáticamente) |
| `GET /api/tools`                | Lista de todas las tools con su schema             | Exploración, LangChain, n8n |
| `POST /api/tools/{name}`        | Ejecuta cualquier tool por nombre                  | ChatGPT custom GPTs, Gemini, scripts |
| `POST /api/memory`              | Atajo REST: crear memoria curada                   | Integraciones simples    |
| `POST /api/memory/conversation` | Atajo REST: persistir un mensaje de conversación   | Integraciones simples    |
| `POST /api/memory/search`       | Atajo REST: búsqueda semántica                     | Integraciones simples    |
| `GET /api/memory/prime`         | Atajo REST: prime context inicial                  | Integraciones simples    |
| `GET /openapi.json`             | OpenAPI 3 auto-generado                            | Importar como custom GPT |
| `GET /health`                   | Liveness + readiness probe                         | Docker healthcheck, monitoreo |

---

## Arranque en 30 segundos

```bash
git clone https://github.com/gabrielzaldivar06/NEMO.git
cd NEMO
cp .env.example .env            # opcional; todos los defaults funcionan
docker compose up -d
```

Verifica:
```bash
curl http://localhost:8765/health
```

Listo. Ahora conecta la AI que uses.

---

## Conectar cada cliente

### Claude Desktop / Claude Code
```json
{
  "mcpServers": {
    "nemo": { "url": "http://localhost:8765/mcp/sse" }
  }
}
```
Claude Desktop: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) o `%APPDATA%\Claude\claude_desktop_config.json` (Windows).
Claude Code: `claude mcp add nemo http://localhost:8765/mcp/sse --transport sse`.

### VS Code (Copilot + MCP)
`~/.config/Code/User/mcp.json`:
```json
{ "servers": { "nemo": { "type": "sse", "url": "http://localhost:8765/mcp/sse" } } }
```

### Cursor / Windsurf / Cline
Añade un MCP server remoto apuntando a `http://localhost:8765/mcp/sse`.

### ChatGPT custom GPT
En el builder del GPT → **Configure → Actions → Import from URL** →
`http://localhost:8765/openapi.json`. El conjunto de tools expuestas por REST
varía según el cliente que detecte NEMO vía `User-Agent` (por defecto verás el
conjunto común — actualmente ~34 tools — y los clientes específicos como
VS Code reciben extras adicionales).

### Gemini / LangChain / n8n / curl
Llamada HTTP directa:
```bash
curl -X POST http://localhost:8765/api/memory/search \
     -H 'Content-Type: application/json' \
     -d '{"query": "decisiones de arquitectura", "limit": 5}'
```

Para llamar cualquier tool por nombre:
```bash
curl -X POST http://localhost:8765/api/tools/prime_context \
     -H 'Content-Type: application/json' \
     -d '{"arguments": {"topic": "NEMO"}}'
```

---

## Perfil GPU (opcional)

¿Tienes GPU NVIDIA y quieres máximo rendimiento en embeddings? Añade el override:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

Esto:
- Arranca un contenedor `ollama` con acceso a la GPU (requiere [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)).
- Hace `ollama pull nomic-embed-text` la primera vez (job one-shot, 1-2 min).
- Espera a que Ollama esté sano antes de arrancar NEMO.
- Cambia el provider de NEMO a `ollama` automáticamente.

Sin GPU NVIDIA, Ollama sigue funcionando en CPU — solo quita el bloque `deploy:`
del servicio `ollama` en `docker-compose.gpu.yml`.

---

## Persistencia

Dos volúmenes nombrados:
- `nemo-data` → `/app/.ai_memory` en el contenedor → todas las bases SQLite (`conversations.db`, `ai_memories.db`, `schedule.db`, etc.)
- `nemo-models` → `/models` → pesos pre-descargados de fastembed

Ambos sobreviven a `docker compose down`. Para borrar todo:
```bash
docker compose down -v
```

---

## Personalizar

Copia `.env.example` → `.env` y ajusta. Las variables más relevantes:

| Variable                | Default                                                 | Qué cambia |
|-------------------------|---------------------------------------------------------|------------|
| `NEMO_HOST_PORT`        | `8765`                                                  | Puerto expuesto en el host |
| `EMBEDDING_MODEL`       | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Modelo fastembed ([catálogo](https://qdrant.github.io/fastembed/examples/Supported_Models/)) |
| `EMBEDDING_PROVIDER`    | `custom`                                                | `custom` / `ollama` / `lm_studio` / `openai` |
| `EMBEDDING_BASE_URL`    | (auto → sidecar interno)                                | URL del servicio de embeddings externo |
| `RERANK_ENABLED`        | `false`                                                 | Activa reranking (requiere `RERANK_BASE_URL`) |

---

## Actualizar

```bash
git pull
docker compose build --pull
docker compose up -d
```

---

## Troubleshooting

**El contenedor arranca pero `/health` tarda mucho.**
Primera carga del modelo fastembed (~30-45s). El healthcheck ya considera eso (`start_period: 45s`).

**En Mac/Windows no puedo conectar a `http://localhost:1234` desde el contenedor (LM Studio).**
Usa `http://host.docker.internal:1234` en `EMBEDDING_BASE_URL`.

**Linux no resuelve `host.docker.internal`.**
Añade en `docker-compose.yml`:
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

**Reranking roto / `503 degraded`.**
Deja `RERANK_ENABLED=false` salvo que tengas un endpoint compatible. NEMO funciona
sin reranking; es un boost de calidad opcional.
