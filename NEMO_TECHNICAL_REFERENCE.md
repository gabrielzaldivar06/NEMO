# NEMO — Referencia Técnica Exhaustiva
## Sistema de Memoria Persistente para Inteligencias Artificiales

**Versión:** 1.1.0 (Sprint 10)  
**Autor:** Gabriel  
**Motor de búsqueda:** Qwen3-Embedding-4B + BGE-reranker-v2-m3  
**Transporte:** MCP (Model Context Protocol) via stdio  
**Benchmarks de producción:** Top-1 = 92 %, MRR = 0.9583, P95 = 2 095 ms  

---

## Tabla de Contenidos

1. [¿Qué es NEMO?](#1-qué-es-nemo)
2. [Filosofía de diseño](#2-filosofía-de-diseño)
3. [Arquitectura general](#3-arquitectura-general)
4. [Stack tecnológico](#4-stack-tecnológico)
5. [Componentes principales](#5-componentes-principales)
   - 5.1 [MCP Server (`ai_memory_mcp_server.py`)](#51-mcp-server)
   - 5.2 [Core (`ai_memory_core.py`)](#52-core)
   - 5.3 [Las cinco bases de datos SQLite](#53-las-cinco-bases-de-datos-sqlite)
   - 5.4 [Servicio de Embeddings](#54-servicio-de-embeddings)
   - 5.5 [Servicio de Reranking](#55-servicio-de-reranking)
   - 5.6 [Monitor de Conversaciones](#56-monitor-de-conversaciones)
   - 5.7 [Sistema de Configuración](#57-sistema-de-configuración)
   - 5.8 [Mantenimiento de Bases de Datos](#58-mantenimiento-de-bases-de-datos)
   - 5.9 [Extensión VS Code (nemo-vscode)](#59-extensión-vs-code-nemo-vscode)
   - 5.10 [Autostart Windows](#510-autostart-windows)
6. [Pipeline de búsqueda semántica](#6-pipeline-de-búsqueda-semántica)
   - 6.1 [Fase 1 — Generación del embedding de consulta](#61-fase-1--generación-del-embedding-de-consulta)
   - 6.2 [Fase 2 — Caché semántica de sesión](#62-fase-2--caché-semántica-de-sesión)
   - 6.3 [Fase 3 — Recuperación de candidatos (ANN coseno)](#63-fase-3--recuperación-de-candidatos-ann-coseno)
   - 6.4 [Fase 4 — Hybrid Rescoring (semántico + léxico)](#64-fase-4--hybrid-rescoring-semántico--léxico)
   - 6.5 [Fase 5 — Decaimiento temporal + bonus de recencia](#65-fase-5--decaimiento-temporal--bonus-de-recencia)
   - 6.6 [Fase 6 — Clasificador de intención de consulta](#66-fase-6--clasificador-de-intención-de-consulta)
   - 6.7 [Fase 7 — Boosts de calidad de memoria](#67-fase-7--boosts-de-calidad-de-memoria)
   - 6.8 [Fase 8 — Bypass adaptativo + Gap Router](#68-fase-8--bypass-adaptativo--gap-router)
   - 6.9 [Fase 9 — Reranking con BGE (Rank-Weighted Fusion)](#69-fase-9--reranking-con-bge-rank-weighted-fusion)
   - 6.10 [Fase 10 — Supresión de near-duplicados](#610-fase-10--supresión-de-near-duplicados)
   - 6.11 [Fase 11 — Access Count Feedback](#611-fase-11--access-count-feedback)
7. [Las 31 herramientas MCP](#7-las-31-herramientas-mcp)
8. [Sistema de agenda y recordatorios](#8-sistema-de-agenda-y-recordatorios)
9. [Auto-corrección y reflexión de la IA](#9-auto-corrección-y-reflexión-de-la-ia)
10. [Importación de conversaciones externas](#10-importación-de-conversaciones-externas)
11. [Deduplicación semántica en escritura](#11-deduplicación-semántica-en-escritura)
12. [Rendimiento y benchmarks](#12-rendimiento-y-benchmarks)
13. [Alcances (Scope)](#13-alcances-scope)
14. [Retos (Challenges)](#14-retos-challenges)
15. [Posibilidades futuras](#15-posibilidades-futuras)
16. [Guía de operación del sistema completo](#16-guía-de-operación-del-sistema-completo)
17. [Integración con VS Code Copilot (copilot-instructions.md)](#17-integración-con-vs-code-copilot-copilot-instructionsmd)

---

## 1. ¿Qué es NEMO?

NEMO es un **sistema de memoria persistente de largo plazo para modelos de lenguaje** que opera completamente en local, sin Internet, sin APIs de terceros, y sin suscripción. Su propósito es resolver el problema fundamental de los LLMs: **la amnesia entre sesiones**.

Cada vez que un usuario abre una nueva conversación con un asistente de IA, ese asistente no recuerda nada de las interacciones anteriores. NEMO construye una capa de memoria indexable semánticamente que el modelo puede consultar en cualquier momento a través del protocolo MCP (Model Context Protocol), recuperando contexto relevante con precisión quirúrgica.

**Casos de uso centrales:**
- El asistente recuerda decisiones técnicas previas del usuario.
- Se pueden recuperar conversaciones de hace semanas con una consulta en lenguaje natural.
- La agenda y recordatorios persisten entre todos los clientes de IA.
- El sistema aprende de sus propios errores mediante memorias de corrección.
- Los patrones de uso de herramientas se analizan para auto-mejora.

El nombre **NEMO** alude al capitán Nemo de "20.000 leguas de viaje submarino" — un sistema que opera en las profundidades, invisible para el usuario, pero controlando el contexto con precisión.

---

## 2. Filosofía de diseño

| Principio | Implementación |
|-----------|---------------|
| **100 % local** | Todo corre en el PC del usuario. No hay llamadas a la nube para embeddings, reranking ni almacenamiento. |
| **Privacidad absoluta** | Las memorias, conversaciones y agenda nunca salen del equipo. |
| **Sin vendor lock-in** | Soporta LM Studio, Ollama, llama.cpp, OpenAI (opcional). El proveedor es un parámetro de configuración. |
| **Durabilidad** | SQLite WAL mode, sin límite de retención para memorias y conversaciones. |
| **Semántica real** | La búsqueda no es una búsqueda de texto (LIKE): usa embeddings de 3 840 dimensiones (Qwen3) con coseno + reranker cross-encoder. |
| **Auto-correctivo** | El sistema tiene un tipo especial de memoria (`correction`) con boost +0.35 para que los errores del asistente se corrijan permanentemente. |
| **Transporte estándar** | MCP stdio es el protocolo de facto para tools en VS Code / Claude / cualquier cliente compatible. |

---

## 3. Arquitectura general

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENTE AI (VS Code, Claude, etc.)          │
│                         [usa MCP tools via stdio]                   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ MCP stdio
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              ai_memory_mcp_server.py  (AIMemoryMCPServer)           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  31 MCP Tools: search_memories, store_conversation,         │   │
│  │  create_memory, create_appointment, create_reminder,        │   │
│  │  get_system_health, reflect_on_tool_usage, get_weather, ... │   │
│  └────────────────────────────┬────────────────────────────────┘   │
└───────────────────────────────┼─────────────────────────────────────┘
                                │ Python async
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│               ai_memory_core.py  (PersistentAIMemorySystem)         │
│                                                                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐  │
│  │ConversationDB│ │AIMemoryDB    │ │ScheduleDB    │ │VSCodeDB  │  │
│  │conversations │ │curated_      │ │appointments  │ │project_  │  │
│  │.db           │ │memories.db   │ │reminders     │ │sessions  │  │
│  │              │ │              │ │schedule.db   │ │insights  │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────┘  │
│  ┌──────────────┐                                                   │
│  │MCPToolCallDB │   ← tool_calls, usage_stats,                     │
│  │mcp_tool_calls│     ai_reflections, usage_patterns               │
│  │.db           │                                                   │
│  └──────────────┘                                                   │
│                                                                     │
│  ┌──────────────────────────┐  ┌───────────────────────────────┐   │
│  │   EmbeddingService        │  │   RerankingService            │   │
│  │   Qwen3-Embedding-4B      │  │   BGE-reranker-v2-m3          │   │
│  │   → 3840 dims             │  │   → Rank-Weighted Fusion      │   │
│  │   fallback: nomic-embed   │  │   70% sem + 30% BGE           │   │
│  └──────────────────────────┘  └───────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  ConversationFileMonitor                                      │  │
│  │  watchdog + multi-format parser (LMStudio, Ollama, OpenWebUI,│  │
│  │  SillyTavern, Gemini CLI, text, VS Code chatSessions)        │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    LM Studio  (localhost:1234)                       │
│    ┌─────────────────────────────┐  ┌───────────────────────────┐  │
│    │  Qwen3-Embedding-4B         │  │  BGE-reranker-v2-m3        │  │
│    │  GET /v1/embeddings         │  │  POST /v1/rerank           │  │
│    │  3 840 dims                 │  │  ~438 MB                   │  │
│    └─────────────────────────────┘  └───────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                  │
                  │ monitorizado por
                  ▼
┌──────────────────────────────────┐
│  status_monitor.py               │  ← system tray / terminal
│  nemo-vscode/ (VS Code sidebar)  │  ← extensión local
│  start_nemo_system.ps1           │  ← autostart al encender el PC
└──────────────────────────────────┘
```

---

## 4. Stack tecnológico

| Componente | Tecnología | Versión / Notas |
|-----------|-----------|----------------|
| Lenguaje principal | Python | 3.10+ |
| Transporte IA | MCP (Model Context Protocol) | `mcp` 1.26.0, stdio transport |
| Bases de datos | SQLite | WAL mode, async via `asyncio.to_thread` |
| Embeddings (primario) | Qwen3-Embedding-4B | 3 840 dims, vía LM Studio `text-embedding-qwen3-embedding-4b` |
| Embeddings (fallback) | nomic-embed-text | 768 dims, vía Ollama o LM Studio |
| Reranker | BGE-reranker-v2-m3 | Cross-encoder, ~438 MB, GGUF Q4_K_M |
| LM Server | LM Studio | `lms` CLI, puerto 1234 |
| HTTP async | `aiohttp` | Para llamadas al LM Studio |
| Álgebra lineal | `numpy` | Coseno, normas, arrays float32 |
| Monitoreo archivos | `watchdog` | Observer pattern |
| Configuración | `pydantic-settings` | + `.env` + JSON |
| GUI tray | `pystray`, `customtkinter`, `pillow` | Status monitor |
| VS Code Extension | vanilla JS | TreeDataProvider, vscode API |
| Autostart | PowerShell + WScript.Shell | Windows Startup shortcut |
| Parsing de fechas | `python-dateutil` | Horarios recurrentes |

---

## 5. Componentes principales

### 5.1 MCP Server

**Archivo:** `ai_memory_mcp_server.py`  
**Clase:** `AIMemoryMCPServer`

El servidor MCP es el **punto de entrada único** para todos los clientes de IA. Implementa el protocolo MCP sobre `stdio`, lo que significa que el cliente lanza el proceso Python como subproceso y se comunica a través de stdin/stdout usando JSON-RPC.

**Inicialización:**
```python
class AIMemoryMCPServer:
    def __init__(self):
        self.memory_system = PersistentAIMemorySystem()
        self.mcp = FastMCP("ai-memory")
        self._register_handlers()
```

Al arrancar, el servidor crea una instancia de `PersistentAIMemorySystem` (que inicializa las 5 bases de datos, el servicio de embeddings y el de reranking), y luego registra los 31 tools MCP.

El servidor tiene una tarea de **auto-mantenimiento** en background que se ejecuta periódicamente para limpiar datos, comprimir bases de datos y aplicar políticas de retención.

**Configuración global MCP** (`%APPDATA%\Code\User\mcp.json`):
```json
{
  "servers": {
    "nemo": {
      "command": "C:\\dev\\memory persistence\\.venv\\Scripts\\python.exe",
      "args": ["C:\\dev\\memory persistence\\persistent-ai-memory\\ai_memory_mcp_server.py"],
      "type": "stdio"
    }
  }
}
```

---

### 5.2 Core

**Archivo:** `ai_memory_core.py`  
**Clase principal:** `PersistentAIMemorySystem`

Este es el **núcleo computacionalmente denso** del sistema. Contiene más de 4 900 líneas de código y coordina todas las operaciones: búsqueda, escritura, deduplicación, reranking y mantenimiento.

**Jerarquía de clases:**

```
DatabaseManager (base)
├── ConversationDatabase
├── AIMemoryDatabase
├── ScheduleDatabase
├── VSCodeProjectDatabase
└── MCPToolCallDatabase

EmbeddingService
RerankingService
ConversationFileMonitor
PersistentAIMemorySystem  ← orquestador principal
```

**`DatabaseManager`** implementa la capa de acceso a datos con:
- `get_connection()`: context manager SQLite con `isolation_level=None` (autocommit), `check_same_thread=False`, WAL mode, foreign keys ON.
- `execute_query(sql, params) → List[Dict]`: async via `asyncio.to_thread`, retorna dicts.
- `execute_update(sql, params)`: async, para INSERT/UPDATE/DELETE.
- **Migración automática de esquema:** en cada tabla existe lógica de `PRAGMA table_info` que detecta columnas faltantes y las agrega con `ALTER TABLE ADD COLUMN`. Cero downtime, retro-compatible.

**`PersistentAIMemorySystem.__init__`** inicializa:
- Las 5 instancias de bases de datos.
- `EmbeddingService` y `RerankingService` (desde `embedding_config.json`).
- `_search_cache: dict` — caché semántica de sesión (máx. 32 entradas, TTL 5 min).
- `_consolidation_threshold: float = 0.82` — umbral de near-duplicate no bloqueante.
- `ConversationFileMonitor` (si `enable_file_monitoring=True`).

---

### 5.3 Las cinco bases de datos SQLite

Todas residen en `~/.ai_memory/`. Rutas configurables vía `AI_MEMORY_DATA_DIR`.

#### `conversations.db`
Almacén de conversaciones brutas, con deduplicación por hash de contenido (ventana de 1 hora).

| Tabla | Columnas clave | Propósito |
|-------|---------------|-----------|
| `sessions` | `session_id`, `start_timestamp`, `context` | Agrupa conversaciones de una sesión |
| `conversations` | `conversation_id`, `session_id`, `topic_summary` | Hilo individual de chat |
| `messages` | `message_id`, `conversation_id`, `role`, `content`, `embedding` (BLOB) | Mensajes individuales con embedding |
| `source_tracking` | `source_type`, `source_path`, `status` | Tracking de fuentes externas |
| `conversation_relationships` | `source_conversation_id`, `related_conversation_id`, `relationship_type` | Relaciones cruzadas |

**Retención:** indefinida (sin límite de edad ni de cantidad).  
**Archivado:** opcional después de 180 días de inactividad.

#### `ai_memories.db`
La memoria curada y semánticamente indexada. Es la tabla más importante para la búsqueda.

| Tabla | Columnas clave | Propósito |
|-------|---------------|-----------|
| `curated_memories` | `memory_id`, `content`, `memory_type`, `importance_level` (1-10), `tags` (JSON), `embedding` (BLOB), `access_count`, `last_accessed_at` | Las memorias que el AI decide crear explícitamente |

**Tipos de memoria y sus pesos de calidad:**

| `memory_type` | Peso de calidad | Uso típico |
|--------------|----------------|-----------|
| `correction` | 1.0 + boost +0.35 | Corrección de errores del AI |
| `feature` | 0.9 | Feature building blocks del código |
| `testing` | 0.9 | Estrategias de testing |
| `configuration` | 0.9 | Config importante del sistema |
| `integration` | 0.9 | Entrypoints MCP, wiring de servicios |
| `project_decision` | 0.9 | Decisiones arquitectónicas |
| `operations` | 0.8 | Operaciones rutinarias |
| `general` | 0.7 | Información general |
| `noise` | 0.1 | Ruido, casi nunca recuperado |

#### `schedule.db`
Agenda completa con capacidad de recurrencia.

| Tabla | Columnas clave |
|-------|---------------|
| `appointments` | `appointment_id`, `scheduled_datetime`, `title`, `status` (scheduled/cancelled/completed) |
| `reminders` | `reminder_id`, `due_datetime`, `content`, `priority_level`, `is_completed` |

Los appointments soportan recurrencia (`daily`, `weekly`, `monthly`, `yearly`) con `recurrence_count` o `recurrence_end_date`.

#### `vscode_project.db`
Contexto de desarrollo en VS Code.

| Tabla | Propósito |
|-------|-----------|
| `project_sessions` | Sesiones de trabajo: workspace, rama git, archivos activos |
| `project_insights` | Insights específicos del proyecto con embedding |

#### `mcp_tool_calls.db`
Telemetría completa de uso de herramientas.

| Tabla | Propósito |
|-------|-----------|
| `tool_calls` | Log exhaustivo: qué tool, cuándo, parámetros, resultado, latencia, cliente |
| `tool_usage_stats` | Estadísticas diarias por tool: call_count, success_count, avg_execution_time_ms |
| `ai_reflections` | Reflexiones del AI sobre su propio uso (tipo, contenido, insights, recomendaciones) |
| `usage_patterns` | Patrones identificados: tipo, descripción, confianza, datos de soporte |

---

### 5.4 Servicio de Embeddings

**Clase:** `EmbeddingService`

El servicio de embeddings es el componente que convierte texto en vectores de alta dimensión que pueden compararse por similitud coseno.

**Jerarquía de providers:**
```
1. Primary: lm_studio @ localhost:1234  (Qwen3-Embedding-4B, 3840 dims)
   ↓ si falla
2. Fallback: ollama @ localhost:11434   (nomic-embed-text, 768 dims)
   ↓ si falla
3. Error: búsqueda de texto plano (fallback degradado)
```

**Providers soportados:** `lm_studio`, `ollama`, `openai`, `llama_cpp`, `custom`.

**Detalle técnico — `add_special_tokens: true`:**  
El servicio envía `"add_special_tokens": true` en cada payload a llama-server/LM Studio. Esto hace que el tokenizador envuelva el input con los tokens BOS y EOS del modelo (Qwen3 usa `<|im_start|>` ... `<|im_end|>`). Sin este flag, llama.cpp produce vectores "abiertos" que son más propensos a colisionar con documentos adyacentes dando falsos positivos en búsqueda.

**Construcción del texto contextual** (`_build_contextual_embedding_text`):  
Antes de generar el embedding, el sistema enriquece el contenido con metadatos:
```
importance:8 type:configuration tags:[docker,deployment]
Contenido de la memoria aquí...
```
Este prefijo numérico hace que las memorias de alta importancia queden en un subespacio vectorial propio, separado del ruido semántico.

**Sistema de disponibilidad:** cada provider tiene un flag `provider_availability[provider]` que se setea `True`/`False` en el primer intento, permitiendo bypass rápido si el fallback ya está marcado como disponible.

---

### 5.5 Servicio de Reranking

**Clase:** `RerankingService`

El reranker es la **segunda etapa de recuperación**, un modelo cross-encoder que recibe (query, documento) y devuelve un score de relevancia más preciso que la similitud coseno del embedding.

**Modelo:** `BGE-reranker-v2-m3` (BAAI General Embedding, cross-encoder, ~438 MB GGUF Q4_K_M)  
**Endpoint:** `http://localhost:1234/v1/rerank`

**Algoritmo Rank-Weighted Fusion (RWF):**
```
final_score(d) = 0.7 / semantic_rank(d) + 0.3 / bge_rank(d)
```
- `semantic_rank`: posición del documento en el ranking inicial por coseno.
- `bge_rank`: posición devuelta por BGE tras comparación cross-encoder.
- La fusión 70/30 impide que BGE anule completamente un ranking semántico fuerte, pero permite que corrija el orden cuando hay ambigüedad.

**Parámetros configurables** (en `embedding_config.json`):
| Parámetro | Por defecto | Significado |
|-----------|-------------|-------------|
| `candidate_count` | 15 | Cuántos candidatos se envían al reranker |
| `final_top_n` | 5 | Cuántos resultados finales se devuelven |
| `timeout_seconds` | 20 | Timeout de la llamada HTTP |
| `confidence_bypass_threshold` | 0.92 | Si top-1 coseno ≥ umbral, se salta BGE |
| `unavailable_retry_seconds` | 60 | Cooldown tras error del reranker |

**Sistema de cooldown:** si el endpoint falla, `_mark_provider_unavailable` registra un timestamp de "retry after". Mientras ese tiempo no expire, el reranker se bypasea silenciosamente y se usa el orden semántico puro.

**Detección de reranker generativo (Qwen3):**  
El servicio detecta si el reranker devuelve scores near-zero (abs_max < 1e-10). Esto ocurre cuando se sirve un modelo generativo (como Qwen3-Reranker) con `pooling=rank`, que no es compatible con la API de cross-encoder. En ese caso, el flag `_generative_reranker_detected` se activa y se bypasea el reranker para toda la sesión, sin márcar el provider como fallido permanente.

---

### 5.6 Monitor de Conversaciones

**Clase:** `ConversationFileMonitor`

Monitorea directorios del sistema de archivos usando `watchdog` y auto-importa conversaciones de múltiples plataformas de IA.

**Plataformas soportadas:**

| Plataforma | Formato | Ruta detectada automáticamente |
|-----------|---------|------------------------------|
| LM Studio | JSON con `versions[]` + `currentlySelected` | `%APPDATA%\LM Studio\conversations` |
| Ollama | SQLite (`chats`, `messages`) | `%LOCALAPPDATA%\Ollama\db.sqlite` |
| OpenWebUI | SQLite (`chat`, `message`) | `~\.open-webui\data\webui.db` |
| SillyTavern | JSON con `messages[].is_user` | `~/SillyTavern/data/chats` |
| Gemini CLI | JSON con `conversation[].input/response` | `~\.gemini\conversations` |
| text-generation-webui | Texto plano con markers role: | `~/text-generation-webui/logs` |
| VS Code | JSON de chatSessions (workspace storage) | `%APPDATA%\Code\User\workspaceStorage\*\chatSessions` |

**Pipeline de importación:**
1. El `Observer` de watchdog detecta creación/modificación de archivos.
2. Se calcula un MD5 del contenido actual. Si coincide con el hash anterior del mismo path, se ignora (evita reprocesar).
3. El parser identifica el formato del archivo/DB y extrae una lista de `{role, content, timestamp, metadata}`.
4. Si hay MCP server activo, cada mensaje se verifica contra él para evitar duplicar mensajes ya almacenados manualmente.
5. Los mensajes nuevos se guardan en `ConversationDatabase` con deduplicación por contenido+rol+sesión (ventana 1 hora).
6. Se genera embedding en background (`asyncio.create_task`).

---

### 5.7 Sistema de Configuración

**Archivo:** `settings.py` — Clase `MemorySettings` (Pydantic BaseSettings)

Todas las settings se pueden sobreescribir con variables de entorno prefijadas con `AI_MEMORY_`. Ejemplo: `AI_MEMORY_DATA_DIR=D:\mis_memorias`.

**Settings principales:**

| Variable env | Default | Descripción |
|-------------|---------|-------------|
| `AI_MEMORY_DATA_DIR` | `~/.ai_memory` | Directorio raíz de todas las DBs |
| `AI_MEMORY_EMBED_PROVIDER` | `lm_studio` | Provider de embeddings |
| `AI_MEMORY_EMBED_MODEL` | `nomic-embed-text` | Modelo de embeddings |
| `AI_MEMORY_ENABLE_MONITORING` | `True` | Activar monitoreo de archivos |
| `AI_MEMORY_CONV_RETENTION_DAYS` | `90` | Retención de conversaciones |
| `AI_MEMORY_SIMILARITY_THRESHOLD` | `0.3` | Umbral mínimo de similitud |

**Archivo `embedding_config.json`** (configuración avanzada de embeddings/reranking):
- Sección `embedding_configuration.primary/fallback`: provider, model, base_url, add_special_tokens.
- Sección `reranking_configuration.primary`: enabled, model, candidate_count, final_top_n, confidence_bypass_threshold.
- Sección `options`: presets para switching rápido entre providers.

---

### 5.8 Mantenimiento de Bases de Datos

**Archivo:** `database_maintenance.py` — Clase `DatabaseMaintenance`

El módulo de mantenimiento gestiona el ciclo de vida completo de las bases de datos:

1. **`discover_databases()`:** Escanea `~/.ai_memory/` buscando archivos `.db` con patrones conocidos (`conversations*.db`, `ai_memories*.db`, etc.). Extrae rangos de fechas de los nombres de archivo y verifica integridad con `PRAGMA integrity_check`.

2. **Políticas de retención:**
   - Conversaciones: sin límite de edad, archivado opcional a 180 días.
   - Memorias curadas: sin límite. Las memorias son irremplazables.
   - Schedule: limpieza de ítems completados y >90 días.
   - Tool calls: sin límite de edad.

3. **Rotación automática:** cuando una DB supera 3 GB, se crea una nueva con sufijo `_YYYY-MM`. La DB anterior pasa a modo lectura.

4. **`ANALYZE`:** actualiza las estadísticas del query planner de SQLite periódicamente para mantener performance.

5. **`TagManager`:** módulo auxiliar que indexa y normaliza los `tags` de las memorias, permitiendo búsquedas por etiqueta eficientes.

---

### 5.9 Extensión VS Code (nemo-vscode)

**Path:** `nemo-vscode/` → instalada en `~/.vscode/extensions/nemo-memory-1.0.0/`

Una extensión de VS Code que muestra el estado del stack NEMO en la barra lateral izquierda mediante un ícono hexagonal con la letra **N**.

**Estructura:**
```
nemo-vscode/
├── media/nemo.svg          ← ícono hexagonal (SVG, pointy-top)
├── package.json            ← manifest: activityBar, viewsContainers, commands
└── extension.js            ← lógica: NemoProvider (TreeDataProvider)
```

**`NemoProvider`** consulta cada 30 segundos:
1. **LM Studio** (`GET http://localhost:1234/v1/models`): detecta si el servidor está activo y si hay modelos de embedding/reranker cargados.
2. **Bases de datos SQLite**: intenta abrir cada una de las 5 DBs y reporta si son accesibles.
3. **MCP Server**: verifica si el proceso Python del servidor está corriendo.

**Secciones del TreeView:**
- `Servicios IA`: LM Studio (✓/✗), Embedding model (✓/✗), Reranker (✓/✗ o ⚠ si no hay modelo BGE cargado).
- `Base de Datos`: conversations, ai_memories, schedule, vscode_project, mcp_tool_calls.
- `MCP Server`: estado del proceso.

El ícono hexagonal con `N` está diseñado en SVG puro, sin dependencias externas, usando un hexágono pointy-top (vértice arriba) en stroke blanco sobre fondo transparente.

---

### 5.10 Autostart Windows

**Archivo:** `start_nemo_system.ps1`  
**Trigger:** shortcut en `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\NEMO System.lnk`

Secuencia de arranque automático al iniciar Windows:
1. **Sleep 8s** — espera que el escritorio cargue.
2. **`lms server status`** — comprueba si LM Studio ya está sirviendo en :1234.
3. **`lms server start --port 1234`** — si no está activo, lo inicia.
4. **`lms load text-embedding-qwen3-embedding-4b -y`** — carga el modelo de embeddings.
5. **`lms load text-embedding-bge-reranker-v2-m3 -y`** — carga el reranker.
6. **Comprueba `pythonw status_monitor.py`** — si no está corriendo, lo lanza en background.
7. **Log a `logs/autostart.log`** — cada paso queda registrado con timestamp.

En el log final aparece `=== Sistema NEMO listo ===` cuando todos los servicios están activos.

**Status monitor** (`status_monitor.py`): proceso de system tray con color coding de salud del sistema (verde/amarillo/rojo).

---

## 6. Pipeline de búsqueda semántica

La función `search_memories` es el corazón de NEMO. Implementa 11 fases sucesivas de refinamiento antes de devolver resultados.

```
query ──▶ [1] Embedding ──▶ [2] Cache ──▶ [3] Cosine ANN
                                                  │
                                          ┌───────▼────────┐
                                          │  Candidatos    │
                                          │  (hasta N×4)   │
                                          └───────┬────────┘
                                                  │
                [4] Hybrid Rescore ◀──────────────┤
                         │                        │
                [5] Temporal Decay                │
                         │                        │
                [6] Intent Tiebreak               │
                         │                        │
                [7] Quality Boost                 │
                         │                        │
                [8] Adaptive Bypass ──── yes ──►  │ (skip reranker)
                         │ no                     │
                [9] BGE Reranking (RWF)           │
                         │                        │
                [10] Near-dup Suppression         │
                         │                        │
                [11] Access Count Bump ◀──────────┘
                         │
                    final results[:top_n]
```

### 6.1 Fase 1 — Generación del embedding de consulta

```python
query_embedding = await self.embedding_service.generate_embedding(query)
```

Si falla (embedding service down), el sistema cae a `_text_based_search` que hace `LIKE` SQL literal. Es un fallback degradado pero funcional.

### 6.2 Fase 2 — Caché semántica de sesión

**Feature #4 — Semantic Query Cache**

La caché almacena hasta 32 pares `(embedding_vector, result_payload, timestamp)`. Antes de ejecutar la búsqueda completa, se compara el embedding de la consulta entrante contra todos los embeddings cacheados usando coseno. Si se encuentra una similitud ≥ 0.97 y el TTL de 5 minutos no expiró, se devuelve el resultado cacheado directamente.

Esto es crítico para reducir latencia en workflows repetitivos donde el AI consulta variaciones de la misma pregunta (p.ej. "¿qué sabemos sobre Docker?" vs "¿cómo configuramos Docker?").

Eviction: FIFO simple cuando alcanza 32 entradas + expiración de entradas viejas al inicio de cada búsqueda.

### 6.3 Fase 3 — Recuperación de candidatos (ANN coseno)

Búsqueda bruta de similitud coseno en todas las bases habilitadas:

```python
candidate_limit = max(limit * 4, 20)  # sobre-recuperar para el reranker
```

Por cada base (ai_memories, conversations, schedule, projects) se cargan todas las filas con `embedding IS NOT NULL`, se deserializa el BLOB `float32` con `numpy.frombuffer`, y se calcula la similitud coseno vectorialmente.

El umbral de corte inferior es `similarity > 0.3`. Resultados por debajo de ese umbral se descartan para no contaminar el pool de candidatos.

**Nota importante sobre dimensionalidad mixta:** El sistema acepta embeddings de diferentes dimensiones (768D de nomic-embed-text legacy, 3840D de Qwen3). Las comparaciones coseno entre vectores de distinta dimensión son inválidas, por lo que embeddings legacy aparecerán con scores bajos o errores. Esto es un reto activo (ver sección 14).

### 6.4 Fase 4 — Hybrid Rescoring (semántico + léxico)

**Feature — Lightweight Hybrid Rescoring**

```python
final_score = base_cosine_score + lexical_boost
```

`_calculate_lexical_match_score` calcula un bonus léxico basado en:
- Coincidencias de tokens del query en el contenido del resultado.
- Stopwords bilingües (EN/ES) filtradas con `SEARCH_STOPWORDS`.
- Aliases de tokens (correcciones de typos) via `SEARCH_TOKEN_ALIASES`.

Este boost es pequeño (~0.01-0.05) para no anular la señal semántica, pero mejora el tie-breaking cuando dos documentos tienen coseno muy similar.

### 6.5 Fase 5 — Decaimiento temporal + bonus de recencia

**Feature #5 — Temporal Relevance Decay**

```python
decay = max(0.80, math.exp(-lambda * age_days))  # half-life = 60 días
score *= decay
```

- Half-life: 60 días. Un documento de 60 días retiene 50% de su bonus; de 6 meses retiene ~11%.
- Bounded: nunca baja del 80% para que memorias antiguas sigan siendo recuperables.
- **Recency bonus (Sprint 9 T4):** memorias creadas en los últimos 3 días reciben ×1.02 en lugar de decaimiento, dando al sistema noción de "ahora".

### 6.6 Fase 6 — Clasificador de intención de consulta

**Feature #3 — Query Intent Microclassifier**

Clasifica la consulta en una de 3 categorías usando 20 reglas regex:

| Intent | Señales | Efecto |
|--------|---------|--------|
| `factual` | "what is", "define", "command", "when did" | Leve boost a memorias de alta importancia cortas |
| `procedural` | "how to", "steps", "install", "configure" | Leve boost a tipos `procedure`, `guide`, `howto` |
| `contextual` | (default) | Sin sesgo adicional |

El multiplicador de tie-break es pequeño (±0.004 por punto de importance), suficiente para desempatar sin distorsionar la señal semántica principal.

### 6.7 Fase 7 — Boosts de calidad de memoria

**Feature — Type-Quality Composite Boost (Sprint 6)**

```python
quality_boost = type_weight × (importance_level / 10) × 0.10
score += quality_boost
if memory_type == "correction": score += 0.35  # correctores siempre primero
```

La combinación de tipo y nivel de importancia crea una brecha 4-7× entre memorias ancla (feature, testing, configuration) y relleno sintético (noise, support_note). Esto resuelve el problema del "filler attack" donde contenido genérico con alta similitud léxica al query bloqueaba las memorias relevantes.

**Access Count Boost (Sprint 9 T2):**
```python
score += min(0.04, math.log1p(access_count) * 0.02)
```
Memorias que han respondido bien en el pasado reciben hasta +0.04 adicional. A ~1000 accesos el boost se satura.

### 6.8 Fase 8 — Bypass adaptativo + Gap Router

**Feature #1 — Adaptive Bypass Calibration (Sprint 10)**

En lugar de un umbral fijo de 0.92, el sistema calcula dinámicamente:
```python
adaptive_threshold = clamp(median(scores) + 1.5 × std(scores), 0.80, 0.95)
```

Si el top-1 coseno ya supera el umbral adaptativo, se considera que el resultado es tan claro que no vale la pena invocar al reranker (~1500ms de latencia).

**Feature #2 — Score-Gap Router (Sprint 10):**
```python
if top_raw - second_raw >= 0.05:  # gap_bypass
    skip_reranker = True
```

Si la diferencia entre el 1er y 2do candidato es suficientemente amplia (>0.05), el ranking es inequívoco. Este bypass fue bajado de 0.07 a 0.05 en Sprint 10 para aumentar el número de bypasses y reducir la P95 de latencia.

### 6.9 Fase 9 — Reranking con BGE (Rank-Weighted Fusion)

```python
rwf_score = 0.7 / semantic_rank(d) + 0.3 / bge_rank(d)
```

Todos los candidatos que llegan a esta fase se envían al endpoint `/v1/rerank` del BGE-reranker. El score final es una fusión ponderada que da el 70% al ranking semántico y el 30% al cross-encoder BGE. Esto previene que BGE anule completamente un ranking semántico fuerte cuando hay near-duplicates con keywords artificiales.

### 6.10 Fase 10 — Supresión de near-duplicados

**Feature — Importance-Preferent Near-Duplicate Suppression (Sprint 7 + 9 + 10)**

Algoritmo greedy sobre el top-50 de resultados:

- **Near-dup fuerte** (coseno > 0.95): el representante del cluster es el de mayor `importance_level`. En caso de empate (≤1 punto), gana el más *antiguo* (timestamp <= indica el original, el nuevo es el "imposter").
- **Near-dup débil** (coseno > 0.80) **+ meta-cluster** (mismo `memory_type` Y ≥3 tags comunes): el más *antiguo* es el canónico. El más nuevo se suprime.

La detección de imposters (Sprint 10) resuelve el caso donde el AI crea memorias casi idénticas a lo largo de varias sesiones: solo la primera aparece en los resultados.

**Imposter intercept en benchmarks de producción: 8%**, lo que significa que el 8% de las veces el sistema correctamente suprimió un near-duplicate redundante.

### 6.11 Fase 11 — Access Count Feedback

Después de devolver resultados al cliente, se lanza una tarea `asyncio.ensure_future` que incrementa `access_count` y actualiza `last_accessed_at` en todas las memorias que aparecieron en el top-N final. Este contador retroalimenta el boost de la Fase 7 en búsquedas futuras.

---

## 7. Las 31 herramientas MCP

Organizadas por categoría:

### Memoria y conocimiento
| Tool | Descripción |
|------|-------------|
| `search_memories` | Búsqueda semántica en todas las bases. Soporta `database_filter`, `min/max_importance`, `memory_type`. |
| `create_memory` | Crea una memoria curada. Incluye deduplicación semántica (coseno ≥ 0.92 rechaza). Devuelve warning si hay near-dup (0.82-0.92). |
| `update_memory` | Actualiza contenido/tags/importance de una memoria existente. |
| `create_correction` | Alias especializado de `create_memory` con `memory_type=correction` y boost +0.35. |
| `get_corrections` | Recupera memorias de tipo `correction` para contexto de auto-corrección. |
| `get_ai_insights` | Recupera insights almacenados sobre patrones de uso. |
| `write_ai_insights` | Escribe insights generados por el AI sobre sus patrones. |

### Conversaciones
| Tool | Descripción |
|------|-------------|
| `store_conversation` | Almacena un mensaje (user/assistant/system) con session_id e embedding async. |
| `get_recent_context` | Recupera los N mensajes más recientes, opcionalmente por sesión. |

### Agenda y recordatorios
| Tool | Descripción |
|------|-------------|
| `create_appointment` | Crea appointment con soporte de recurrencia (daily/weekly/monthly/yearly). |
| `create_reminder` | Crea reminder con `due_datetime` y `priority_level`. |
| `get_reminders` | Lista todos los reminders (activos + completados). |
| `get_active_reminders` | Solo reminders pendientes. |
| `get_completed_reminders` | Solo reminders completados. |
| `complete_reminder` | Marca reminder como completado con `completed_at`. |
| `reschedule_reminder` | Cambia `due_datetime` de un reminder existente. |
| `delete_reminder` | Elimina reminder permanentemente. |
| `get_appointments` | Lista appointments con filtros de fecha. |
| `get_upcoming_appointments` | Próximos N días de agenda. |
| `cancel_appointment` | Cancela appointment (status → 'cancelled'). |
| `complete_appointment` | Marca appointment como completado. |

### Auto-análisis y reflexión
| Tool | Descripción |
|------|-------------|
| `get_tool_usage_summary` | Estadísticas de uso de herramientas en los últimos N días. |
| `reflect_on_tool_usage` | Solicita al AI que analice sus patrones de uso y genere recomendaciones. |
| `store_ai_reflection` | Almacena una reflexión del AI con tipo, contenido, insights y recomendaciones. |

### Sistema y salud
| Tool | Descripción |
|------|-------------|
| `get_system_health` | Estado completo: todas las DBs, embedding service, reranker, file monitoring. |
| `get_current_time` | Hora actual con zona horaria local. |

### Utilidades
| Tool | Descripción |
|------|-------------|
| `get_weather_open_meteo` | Clima actual/previsión usando Open-Meteo API (gratis, sin API key). Configurable lat/lon/timezone. |
| `brave_web_search` | Búsqueda web via Brave Search API (requiere API key en config). |
| `brave_local_search` | Búsqueda local via Brave. |

---

## 8. Sistema de agenda y recordatorios

### Appointments con recurrencia

```python
await create_appointment(
    title="Reunión semanal",
    scheduled_datetime="2026-06-01T10:00:00",
    recurrence_pattern="weekly",
    recurrence_count=12,  # 12 semanas seguidas
)
```

Internamente usa `python-dateutil.relativedelta` para calcular cada ocurrencia. Los IDs de todas las instancias recurrentes se devuelven como lista.

**Deduplicación de appointments:** si se intenta crear un appointment con el mismo título, datetime, location y source_conversation_id, se devuelve el ID existente sin insertar duplicado.

### Reminders

Los reminders tienen dos flags de completado (`completed` e `is_completed`) por razones de migración de esquema: la versión actual usa `is_completed`. `reschedule_reminder` permite mover la fecha de vencimiento manteniendo el resto del contexto intacto.

---

## 9. Auto-corrección y reflexión de la IA

Este es uno de los sistemas más sofisticados de NEMO: permite que el AI **aprenda de sus errores de forma permanente**.

### Memorias de corrección

Cuando el usuario informa al AI de un error (`"eso está mal, la respuesta correcta es X"`), el AI puede llamar a `create_correction` con la corrección factual. Esta memoria tiene:
- `memory_type = "correction"`
- `importance_level` recomendado: 9-10
- Boost implícito de **+0.35** en todos los scorings futuros

Esto significa que en cualquier futura búsqueda relacionada con ese tema, la corrección **siempre aparecerá en los primeros resultados**, antes que cualquier otra memorización. Es un mecanismo de override permanente.

### Reflexión sobre patrones de uso

```python
# El AI puede auto-analizar su propio comportamiento
result = await get_tool_usage_summary(days=30)
# → Revela qué tools usa más, cuáles fallan, latencias

reflection = await reflect_on_tool_usage()
# → Genera y almacena insights + recomendaciones
```

Las reflexiones se guardan en `ai_reflections` con campos estructurados:
- `reflection_type`: `usage_patterns`, `performance`, `suggestions`, etc.
- `insights`: lista de insights específicos identificados.
- `recommendations`: lista de acciones recomendadas.
- `confidence_level`: qué tan seguro está el AI de su análisis.

Los `usage_patterns` identificados se almacenan por separado para análisis longitudinal.

---

## 10. Importación de conversaciones externas

### Flujo de importación manual

```python
# Importar una conversación específica
await store_conversation(content="...", role="user", session_id="session_abc")
await store_conversation(content="...", role="assistant", session_id="session_abc")
```

### Importación automática via file monitor

El sistema detecta automáticamente cuando las aplicaciones de IA guardan o modifican sus archivos de conversación. El proceso es completamente transparente:

1. **LM Studio** guarda cada chat en `conversations/` como JSON. El parser extrae texto de los `content[].parts` con tipo `"text"`, soportando multi-step y file attachments.
2. **Ollama** usa una SQLite local. El monitor la abre directamente con `sqlite3` y extrae todos los chats.
3. **OpenWebUI** sigue el mismo patrón SQLite pero con esquema de tablas diferente.
4. **VS Code** guarda sesiones de Copilot en `workspaceStorage/<hash>/chatSessions/`. Se importan como sesiones de desarrollo en `vscode_project.db`.

### Deduplicación

La deduplicación tiene dos niveles:
1. **Hash de archivo**: MD5 del contenido full del archivo. Si no cambió desde la última lectura, se ignora.
2. **Hash de mensaje**: MD5 de `"role:content"`. Si el MCP server está activo, se consulta si ese hash ya fue almacenado manualmente. Si es así, se filtra del batch de auto-importación.

---

## 11. Deduplicación semántica en escritura

Al llamar `create_memory`, antes de insertar se ejecuta un scan completo de embeddings existentes:

```python
for row in all_existing_memories_with_embedding:
    sim = cosine(new_embedding, stored_embedding)
    if sim >= 0.92:
        return {"status": "deduplicated", "existing_id": ...}
    elif sim >= 0.82:
        consolidation_warning = {...}  # advisory, no bloqueante
```

**Threshold de deduplicación dura: 0.92** — memorias con coseno ≥ 0.92 al vector nuevo se consideran semánticamente equivalentes. Se rechaza la inserción y se devuelve el ID de la memoria existente.

**Threshold de consolidación suave: 0.82** — se inserta la memoria pero se advierte al cliente que hay una near-duplicate. El cliente (AI) puede decidir si actualizar la existente en lugar de crear una nueva.

Esta deduplicación al escribir es computacionalmente costosa O(n) donde n = número de memorias con embedding, pero es fundamental para mantener la calidad del corpus: sin ella, el AI acumularía versiones sutilmente distintas de la misma información, fragmentando la distribución de scores y degradando la recuperación.

---

## 12. Rendimiento y benchmarks

### Benchmarks de producción (Sprint 10)

| Métrica | Valor |
|---------|-------|
| Top-1 accuracy | **92%** (documento correcto aparece primero) |
| MRR (Mean Reciprocal Rank) | **0.9583** |
| P95 latency | **2 095 ms** |
| Imposter intercept rate | **8%** |
| Production checks passed | **5/5** |

### Latencias típicas por componente

| Operación | Latencia estimada |
|-----------|-----------------|
| `generate_embedding` (Qwen3 local) | 200-500 ms |
| Coseno sobre 1000 memorias (numpy) | < 5 ms |
| Rescore + decay + boosts | < 1 ms |
| BGE reranking (15 candidatos) | 800-1500 ms |
| Bypass de reranker (alta confianza) | 0 ms |
| Cache hit (coseno ≥ 0.97) | < 0.1 ms |
| SQLite read (1000 filas con BLOB) | 10-50 ms |

### Evolución del sistema por sprints

| Sprint | Feature clave |
|--------|--------------|
| Sprint 6 | Type-Quality Composite Boost (reemplaza boost plano) |
| Sprint 7 | Near-duplicate suppression con cross-result cosine |
| Sprint 8 | Semantic query cache + memory consolidation threshold |
| Sprint 9 | Access count boost + Creation-order tiebreaker + Recency bonus |
| Sprint 10 | Adaptive bypass calibration + Gap router (P95 optimized) + Temporal authority system |

---

## 13. Alcances (Scope)

### ¿Qué puede hacer NEMO hoy?

**Búsqueda semántica real:**
- Recupera información por significado, no solo por palabras clave.
- "¿Cómo configuré el servidor de embeddings?" → encuentra la memoria de configuración aunque no contenga exactamente eso.
- Soporta consultas en inglés y español (stopwords bilingüe).

**Memoria permanente multi-sesión:**
- Todo lo que el AI anota persiste indefinidamente, sobreviviendo reinicios, cambios de modelo, y actualizaciones de software.
- El usuario puede volver a una conversación de meses atrás y el AI tendrá contexto completo.

**Agenda y recordatorios:**
- Crear appointments recurrentes, recordatorios con prioridad, gestión de ciclo de vida completo.
- Cualquier cliente MCP puede consultar/modificar la agenda.

**Auto-corrección permanente:**
- Un error del AI corregido explícitamente nunca vuelve a ocurrir para esa información específica.

**Importación automática de historial:**
- Al instalar NEMO, el historial de LM Studio, Ollama, OpenWebUI y demás plataformas se absorbe automáticamente al fondo de conversaciones.

**Reflexión y auto-mejora:**
- El AI puede analizar sus propios patrones de uso y generar recomendaciones almacenadas.

**Clima y web:**
- Consultas de clima local sin API key (Open-Meteo).
- Búsqueda web (Brave API, opcional).

**Telemetría interna:**
- Cada tool call queda loggeada con latencia, resultado y cliente. El AI puede auditar su propio comportamiento.

**Integración nativa en VS Code:**
- Estado visible en la barra lateral sin necesidad de abrir terminales.
- Autostart silencioso al encender el PC.

---

## 14. Retos (Challenges)

### 1. Dependencia de LM Studio como LM server
Todo el stack requiere que LM Studio (o llama.cpp) esté corriendo en `localhost:1234`. Si el servidor no está activo:
- Los embeddings nuevos no se generan (fallback a nomic/ollama, o búsqueda léxica degradada).
- El reranker no funciona.
- El sistema sigue funcionando pero con calidad de búsqueda reducida.

**Reto:** el autostart intenta mitigar esto, pero en máquinas lentas o con GPUs que tardan en cargar, puede haber una ventana de minutos donde el sistema está degradado.

### 2. Heterogeneidad de dimensiones de embeddings
El corpus acumula dos "generaciones" de vectores:
- 768D: embedings generados con nomic-embed-text (legacy).
- 3840D (Qwen3): los nuevos.

La comparación coseno entre vectores de dimensiones distintas es matemáticamente inválida. Actualmente, si una memoria fue creada con 768D y la consulta genera 3840D, el resultado de coseno es basura.

**Mitigación actual:** el sistema preserva memorias antiguas sin re-embedir (policy de "preservation"). Esto significa que memorias legacy con 768D tienen scores de búsqueda impredecibles.  
**Solución pendiente:** tarea de re-embedding masivo que actualice todos los BLOBs al modelo actual.

### 3. Escalabilidad de SQLite con búsqueda bruta O(n)
La búsqueda coseno actual carga todos los embeddings en memoria y los escanea secuencialmente. Para 10,000 memorias esto es instantáneo, pero a 100,000+ memorias la latencia puede superar los 5 segundos solo en la fase de coseno.

**No hay índice vectorial.** SQLite no soporta ANN nativo. Cada búsqueda es fuerza bruta.

**Solución pendiente:** integrar un vectorstore dedicado (Qdrant, pgvector, FAISS) para el almacenamiento de embeddings, manteniendo SQLite solo para los metadatos.

### 4. Reranker incompatible con modelos generativos
El sistema detecta automáticamente cuando el modelo servido en el endpoint `/v1/rerank` es un reranker generativo (Qwen3-Reranker) via `pooling=rank`. Estos modelos devuelven scores near-zero que no son comparables entre documentos.

En ese caso el reranker se desactiva para toda la sesión. El usuario debe usar explícitamente BGE-reranker-v2-m3 (cross-encoder discriminativo) para que el reranking funcione.

### 5. Latencia de la llamada HTTP al reranker
La llamada al reranker (800-1500ms) domina la latencia total del pipeline. Los bypasses adaptativos de Sprint 10 reducen la frecuencia de esta llamada, pero no la eliminan.

**Benchmark P95 = 2095ms** incluye los casos donde el reranker se invoca. Los casos con bypass tienen P95 ≈ 600ms.

### 6. El formato de embeddings contextuales puede crear ruido en el espacio vectorial
El prefijo numérico `importance:8 type:configuration tags:[...]` mejora la separación de clusters semánticos, pero introduce un artefacto: dos memorias con diferente importancia pero mismo contenido tendrán coseno más bajo de lo que su contenido demandaría. El threshold de deduplicación dura (0.92) asume que el prefijo ya fue incluido en ambos vectores.

Si el usuario cambia la importancia de una memoria y busca re-crearla con el mismo contenido pero `importance:9`, el sistema podría no detectarla como duplicado.

### 7. Sin cifrado de las bases de datos
Las 5 bases SQLite en `~/.ai_memory/` están en texto plano (SQLite no cifra por defecto). En un equipo compartido, cualquier usuario con acceso al directorio puede leer todas las memorias.

**Mitigación:** el directorio `~/.ai_memory/` tiene permisos de usuario por defecto en Windows y Linux.

### 8. Auto-importación de conversaciones puede ser intrusiva
Si el usuario tiene LM Studio con 500 conversaciones antiguas, la primera importación puede tomar varios minutos y generar carga significativa de CPU/GPU por los embeddings.

---

## 15. Posibilidades futuras

### Integración de vectorstore dedicado

Reemplazar el escaneo coseno O(n) con un índice ANN:

```
SQLite (metadatos) ←→ Qdrant/FAISS (vectores) 
```

Con 1M de memorias y un índice HNSW, la búsqueda aproximada sería < 50ms independientemente del tamaño del corpus.

### Re-embedding masivo automatizado

Detectar automáticamente memorias con dimensión "vieja" (768D) y lanzar tareas de re-embedding en background durante períodos de inactividad del sistema. Esto eliminaría el problema de heterogeneidad de dimensiones.

### Memory consolidation activo

El umbral de consolidación suave (0.82) ya genera warnings. El siguiente paso sería:
1. Presentar al usuario memorias near-duplicadas identificadas.
2. Ofrecer merge automático: combinar contenido + preservar la importancia/tags más alta.
3. Reducir el corpus a su forma mínima representativa.

### Dashboard web de memorias

Una interfaz web local (FastAPI + React) que permita:
- Visualizar y buscar memorias manualmente.
- Ver el grafo de relaciones entre conversaciones.
- Auditar/corregir/eliminar memorias individualmente.
- Ver métricas de uso y latencias históricas.

### Fine-tuning personalizado

Con suficiente historial de correcciones, el corpus de `correction` memories podría usarse como dataset para fine-tuning el modelo de embeddings propio, haciéndolo especializado en el vocabulario y dominio específico del usuario.

### Multi-usuario

Separar los namespaces de memorias por usuario:
```
~/.ai_memory/user_alice/
~/.ai_memory/user_bob/
```

Con un campo `owner_id` en todas las tablas, el servidor MCP podría servir a múltiples usuarios en una red local, manteniendo memorias aisladas.

### Integración con más clientes MCP

MCP ya es adoptado por:
- VS Code (Copilot)
- Claude Desktop
- Continue.dev
- Cursor

A medida que el ecosistema MCP madure, NEMO estará disponible automáticamente en todos ellos sin modificación.

### Expiración y archivado selectivo por relevancia

En lugar de retención por tiempo, implementar retención por **relevancia de uso**:
- Memorias que no se han recuperado en X meses y tienen importance < 5 → archivar.
- Memorias con access_count > 10 → proteger de archivado independientemente de edad.

### Soporte para embeddings multimodales

Si el usuario adjunta imágenes en sus conversaciones, se podría generar un embedding visual (CLIP, LLaVA-projector) y unificarlo con el texto embedding para búsqueda multimodal.

### API REST local

Además del transporte MCP, exponer una API REST en `localhost:8888` para que herramientas no-MCP (scripts Python, n8n, etc.) puedan escribir/leer memorias directamente.

---

## 16. Guía de operación del sistema completo

### Startup manual
```powershell
# 1. Iniciar LM Studio server
lms server start --port 1234

# 2. Cargar modelos necesarios
lms load text-embedding-qwen3-embedding-4b -y
lms load text-embedding-bge-reranker-v2-m3 -y

# 3. (Opcional) Iniciar status monitor
cd "C:\dev\memory persistence\persistent-ai-memory"
.\..\..venv\Scripts\pythonw status_monitor.py
```

### Autostart automático (ya instalado)
El shortcut `NEMO System.lnk` en la carpeta Startup de Windows ejecuta automáticamente `start_nemo_system.ps1` al iniciar sesión. El log en `logs/autostart.log` muestra el estado de cada paso.

### Verificación de salud del sistema
Desde cualquier cliente MCP (VS Code Copilot):
```
Usa la herramienta get_system_health
```

Respuesta esperada:
```json
{
  "status": "healthy",
  "databases": {
    "conversations": {"status": "healthy", "message_count": ...},
    "ai_memories": {"status": "healthy", "memory_count": ...},
    ...
  },
  "embedding_service": {"status": "healthy", "embedding_dimensions": 3840},
  "reranking_service": {"status": "healthy", "last_reranking_latency_ms": 950}
}
```

### Crear una memoria importante
```
Crea una memoria de tipo 'configuration', importance 9, tags ['nemo', 'setup']:
"El servidor de embeddings corre en localhost:1234 con Qwen3-Embedding-4B.
 El reranker BGE-reranker-v2-m3 usa el endpoint /v1/rerank del mismo puerto."
```

### Buscar en la memoria
```
Busca memorias sobre "configuración de embeddings" limitando a ai_memories
```

### Ver agenda próxima
```
Muéstrame los próximos 7 días de agenda incluyendo reminders activos
```

### Configuración de VS Code (ya activa)
El archivo `%APPDATA%\Code\User\mcp.json` tiene el servidor `nemo` configurado. VS Code lo inicia automáticamente cuando se abre una sesión de Copilot.

El archivo `.github/copilot-instructions.md` en la raíz del workspace define el comportamiento automático de NEMO en Agent mode (ver [sección 17](#17-integración-con-vs-code-copilot-copilot-instructionsmd)).

### Cambiar el proveedor de embeddings
Editar `embedding_config.json`, cambiar la sección `embedding_configuration.primary`, y reiniciar el servidor MCP (cerrar y reabrir VS Code o el cliente MCP).

---

## 17. Integración con VS Code Copilot (copilot-instructions.md)

### El problema que resuelve

Tener el servidor MCP activo es condición necesaria pero no suficiente para que NEMO se use de forma autónoma. Por defecto, un agente en modo Chat no llamará herramientas MCP a menos que el usuario lo pida explícitamente. En Agent mode puede hacerlo, pero de forma inconsistente y sin un protocolo definido.

El archivo `.github/copilot-instructions.md` soluciona esto: es leído automáticamente por VS Code Copilot al inicio de cada sesión y define *cuándo*, *cómo* y *con qué parámetros* el agente debe invocar las herramientas de NEMO.

### Ubicación y activación

```
C:\dev\memory persistence\persistent-ai-memory\
└── .github/
    └── copilot-instructions.md   ← archivo creado y activo
```

Requisito en VS Code `settings.json` (activo por defecto):
```json
"github.copilot.chat.codeGeneration.useInstructionFiles": true
```

Las instrucciones cargan al inicio de cada nueva sesión de chat. **No requieren reinicio de VS Code ni del servidor MCP.**

### Protocolo que implementa

#### Al inicio de conversación
1. `search_memories(query=<tema principal>)` — recupera contexto relevante de largo plazo.
2. `get_recent_context()` — superficie de actividad reciente (últimas 24–72 h).
3. Si el usuario no está en memoria: `create_memory(memory_type="preference")` con nombre y preferencias detectadas.

#### Durante la conversación
| Evento | Acción NEMO | Herramienta |
|--------|-------------|-------------|
| Usuario menciona hecho o preferencia nuevo | Crear memoria inmediatamente | `create_memory` |
| Usuario corrige algo | Registrar corrección | `create_correction` |
| Pregunta sobre tema ya discutido | Buscar antes de responder | `search_memories` |
| Mención de tarea / deadline | Ofrecer crear recordatorio | `create_reminder` |

#### Al cerrar sesión larga
- `store_conversation()` — persiste el hilo completo.
- `reflect_on_tool_usage()` — genera insight sobre patrones de uso.

### Reglas de calidad codificadas

- **No fabricar memorias**: si `search_memories` no retorna nada relevante, decirlo explícitamente en lugar de inventar contexto.
- **No duplicar**: NEMO ya deduplica en escritura (coseno > 0.92), pero el agente evita llamar `create_memory` para el mismo hecho dos veces en la misma sesión.
- **Búsqueda antes de negación**: ante "¿recuerdas X?", siempre buscar primero — no asumir que no existe.
- **Idioma fiel**: guardar memorias en el idioma en que el usuario las expresó.

### Tabla de tipos de memoria

| Tipo | Cuando usar | Importancia sugerida |
|------|-------------|---------------------|
| `preference` | Estilo de trabajo, gustos, configuraciones personales | 7 |
| `fact` | Dato sobre el usuario, proyecto o dominio | 6 |
| `procedure` | Proceso paso a paso que el usuario quiere recordado | 7 |
| `insight` | Conclusión no obvia generada en conversación | 6 |
| `correction` | Error cometido por la IA — usar `create_correction` | N/A |
| `episodic` | Evento específico con fecha/contexto relevante | 6 |

Escala de importancia: usar `8–10` solo para información que el usuario declara explícitamente como crítica.

### Diferencia entre modos de VS Code

| Modo | Comportamiento |
|------|---------------|
| **Agent mode** | El agente llama herramientas MCP autónomamente siguiendo las instrucciones |
| **Chat mode** | El archivo de instrucciones se carga pero MCP no se invoca sin petición explícita |
| **Edit/inline** | Las instrucciones no aplican — el contexto es el archivo activo |

### Persistencia entre agentes

Cambiar de agente (Claude, GPT-4o, Gemini, etc.) en VS Code Copilot **no borra la memoria**. La memoria vive en `~/.ai_memory/*.db` y es accesible por cualquier agente con acceso al servidor MCP `nemo`. Solo se pierde la ventana de conversación activa — la memoria de largo plazo persiste indefinidamente.

---

## Apéndice A: Esquema completo de bases de datos

```sql
-- conversations.db
sessions(session_id PK, start_timestamp, end_timestamp, context, embedding)
conversations(conversation_id PK, session_id FK, start_timestamp, topic_summary, embedding)
messages(message_id PK, conversation_id FK, timestamp, role, content, embedding BLOB, metadata, source_type, source_url)
source_tracking(source_id PK, source_type, source_name, source_path, last_check, status)
conversation_relationships(relationship_id PK, source_conversation_id FK, related_conversation_id FK, relationship_type)

-- ai_memories.db
curated_memories(memory_id PK, timestamp_created, timestamp_updated, content, memory_type, 
                 importance_level INTEGER, tags TEXT/JSON, embedding BLOB, 
                 access_count INTEGER DEFAULT 0, last_accessed_at TEXT)

-- schedule.db
appointments(appointment_id PK, timestamp_created, scheduled_datetime, title, description, 
             location, status CHECK('scheduled'|'cancelled'|'completed'), cancelled_at, completed_at, embedding BLOB)
reminders(reminder_id PK, timestamp_created, due_datetime, content, priority_level INTEGER,
          is_completed INTEGER DEFAULT 0, completed_at, embedding BLOB)

-- vscode_project.db
project_sessions(session_id PK, workspace_path, active_files TEXT/JSON, git_branch, session_summary, timestamp)
project_insights(insight_id PK, content, insight_type, related_files TEXT/JSON, importance_level, embedding BLOB)

-- mcp_tool_calls.db
tool_calls(call_id PK, timestamp, client_id, tool_name, parameters TEXT/JSON, result TEXT/JSON, 
           status, execution_time_ms, error_message)
tool_usage_stats(stat_id PK, tool_name, date, call_count, success_count, error_count, avg_execution_time_ms)
ai_reflections(reflection_id PK, timestamp, reflection_type, content, insights TEXT/JSON,
               recommendations TEXT/JSON, confidence_level REAL, source_period_days)
usage_patterns(pattern_id PK, timestamp, pattern_type, insight, analysis_period_days,
               confidence_score REAL, supporting_data TEXT/JSON)
```

---

## Apéndice B: Variables de entorno disponibles

```bash
AI_MEMORY_DATA_DIR          # Directorio raíz de datos (default: ~/.ai_memory)
AI_MEMORY_EMBED_PROVIDER    # lm_studio|ollama|openai (default: lm_studio)
AI_MEMORY_EMBED_MODEL       # Modelo de embeddings
AI_MEMORY_EMBED_URL         # URL del endpoint de embeddings
OPENAI_API_KEY              # Solo si usar OpenAI embeddings
AI_MEMORY_WEATHER_LAT       # Latitud para clima
AI_MEMORY_WEATHER_LON       # Longitud para clima
AI_MEMORY_WEATHER_TZ        # Timezone para clima
AI_MEMORY_ENABLE_MONITORING # true|false - monitoreo de archivos
AI_MEMORY_CONV_RETENTION_DAYS # Días de retención de conversaciones
AI_MEMORY_SIMILARITY_THRESHOLD # Umbral mínimo de similitud (default: 0.3)
AI_MEMORY_LOG_LEVEL         # DEBUG|INFO|WARNING|ERROR
```

---

*Documento generado el 2026-03-20. Versión del sistema: Sprint 10 / v1.1.0.*  
*Benchmarks de producción validados en hardware: GPU local con LM Studio, SQLite WAL, Windows 11.*
