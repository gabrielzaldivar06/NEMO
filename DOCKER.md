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

Los scripts de arranque detectan automáticamente si tienes GPU NVIDIA disponible y eligen el perfil correcto. No necesitas saber qué compose usar.

#### 🐧 Linux / macOS / WSL

```bash
git clone https://github.com/gabrielzaldivar06/NEMO.git
cd NEMO
cp .env.example .env            # opcional; todos los defaults funcionan
./start.sh --build
```

#### 🪟 Windows (PowerShell)

```powershell
git clone https://github.com/gabrielzaldivar06/NEMO.git
cd NEMO
copy .env.example .env          # opcional; todos los defaults funcionan
.\start.ps1 -Build
```

Verifica:
```bash
curl http://localhost:8765/health
```

Listo. Ahora conecta la AI que uses.

### Opciones del script

| Opción | Linux/macOS | Windows | Efecto |
|--------|-------------|---------|--------|
| Primera vez / rebuild | `./start.sh --build` | `.\start.ps1 -Build` | Construye la imagen antes de arrancar |
| Arranque normal | `./start.sh` | `.\start.ps1` | Arranca sin reconstruir (más rápido) |
| Detener | `./start.sh --down` | `.\start.ps1 -Down` | Para los contenedores |

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
`http://localhost:8765/openapi.json`. La especificación OpenAPI y las rutas
REST exponen el **conjunto común** de tools (actualmente ~34). Los extras
específicos por cliente que existen en `AIMemoryMCPServer._detect_client_type()`
(por ejemplo, tools adicionales para VS Code o SillyTavern) **solo aplican al
modo MCP-stdio original** — el servidor universal HTTP no inspecciona el
`User-Agent` por petición, porque hacerlo de forma proceso-global no sería
seguro bajo conexiones concurrentes.

### Gemini / LangChain / n8n / curl

Llamada HTTP directa para búsqueda semántica:

#### 🐧 Linux / macOS / WSL

```bash
curl -X POST http://localhost:8765/api/memory/search -H 'Content-Type: application/json' -d '{"query": "decisiones de arquitectura", "limit": 5}'
```

#### 🪟 Windows (PowerShell)

```powershell
$body = '{"query": "decisiones de arquitectura", "limit": 5}'
Invoke-RestMethod -Method POST -Uri http://localhost:8765/api/memory/search -ContentType "application/json" -Body $body
```

Para llamar cualquier tool por nombre:

#### 🐧 Linux / macOS / WSL

```bash
curl -X POST http://localhost:8765/api/tools/prime_context -H 'Content-Type: application/json' -d '{"arguments": {"topic": "NEMO"}}'
```

#### 🪟 Windows (PowerShell)

```powershell
$body = '{"arguments": {"topic": "NEMO"}}'
Invoke-RestMethod -Method POST -Uri http://localhost:8765/api/tools/prime_context -ContentType "application/json" -Body $body
```

---

## Consideraciones de seguridad

NEMO guarda **todo** lo que decides recordar — preferencias, decisiones, fragmentos de
conversaciones, recordatorios. Trátalo como datos personales sensibles. Los defaults
están pensados para uso individual en un equipo de confianza.

### Defaults seguros

- **Bind a `127.0.0.1`** (loopback). El contenedor solo es alcanzable desde el equipo donde corre Docker. Tus dispositivos en la misma red WiFi **no** pueden hablarle.
- **CORS restringido a `localhost`** en sus puertos típicos. Una webpage maliciosa abierta en tu navegador no puede hacer fetch de tus memorias vía cross-origin.
- **Volúmenes nombrados** propiedad del usuario `nemo` (UID 1000) — no exposición a otros usuarios del equipo si bloqueas tu sesión.
- **Sin telemetría externa**: NEMO no llama a la nube para nada (los embeddings los procesa el sidecar fastembed dentro del propio contenedor).

### Lo que SÍ deberías hacer si planeas exponer NEMO

- **Para acceso desde otros equipos en tu LAN**: pon `NEMO_BIND_ADDRESS=0.0.0.0` en `.env` y entiende que cualquier persona en esa red puede leer tus memorias sin autenticación. Solo úsalo en redes que controlas (tu casa, una VPN privada).
- **Para una dashboard en otro puerto** (e.g. desarrollo local en `:3000`): añade `http://localhost:3000` a `NEMO_CORS_ORIGINS=` (lista separada por comas). No uses `*` salvo en redes aisladas.
- **Si vas a exponer NEMO públicamente** (no recomendado sin las dos cosas siguientes): pon un proxy delante (Caddy, nginx) con autenticación HTTP básica o un OAuth2 proxy, **y** un firewall que limite IPs.

### Limitaciones conocidas (no implementadas todavía)

- **Sin autenticación en `/api/*`** — quien alcance el puerto puede llamar a cualquier tool, incluidas las destructivas (`delete_reminder`, `cancel_appointment`). El bind por loopback mitiga el riesgo en ~95 % de los casos. Una capa de bearer-token opcional vía `NEMO_AUTH_TOKEN` está pendiente.
- **Sin rate-limiting** — un cliente malicioso local puede saturar el servidor. Mitigado en la práctica por el bind a loopback.
- **Sin cifrado at-rest** de las bases SQLite. Si tu disco es accesible por terceros (laptop robada, backups en cloud sin cifrar), las memorias son texto plano. Cifra el filesystem si te preocupa.

---

## Perfil GPU (opcional)

Los scripts `start.sh` / `start.ps1` activan este perfil automáticamente si detectan una GPU NVIDIA con el Container Toolkit instalado. No necesitas hacer nada extra.

### ¿Qué activa el perfil GPU?

- Arranca un contenedor `nemo-ollama` con acceso directo a la GPU.
- Un job one-shot `nemo-ollama-init` descarga `nomic-embed-text` la primera vez (~1-2 min).
- NEMO espera a que Ollama esté sano antes de arrancar.
- El provider de embeddings cambia a `ollama` automáticamente.

### Requisitos para el perfil GPU

1. GPU NVIDIA en el host.
2. [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) instalado y configurado en Docker.

Puedes verificar que el toolkit está activo con:

```bash
docker info | grep -i nvidia
# Esperado: aparece "nvidia" en la lista de runtimes
```

### ¿No tienes GPU NVIDIA pero quieres usar Ollama en CPU?

El script arrancará en modo CPU con fastembed (más ligero que Ollama en CPU para embeddings). Si igualmente prefieres Ollama en CPU, puedes forzarlo editando `docker-compose.gpu.yml` y eliminando el bloque `deploy:` del servicio `ollama`, luego corriendo el comando manual:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

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
