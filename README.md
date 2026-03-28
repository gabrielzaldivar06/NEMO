<h1 align="center">NEMO</h1>
<h3 align="center">Sistema de Memoria Persistente para IA</h3>

<p align="center">
  <i>La IA que trabajó contigo ayer, lo recuerda hoy.</i>
</p>

<p align="center">
  <a href="https://creativecommons.org/licenses/by-nc/4.0/"><img src="https://img.shields.io/badge/Licencia-CC%20BY--NC%204.0-lightgrey.svg" alt="Licencia: CC BY-NC 4.0"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"></a>
  <img src="https://img.shields.io/badge/release-v1.3.0--Sprint15-green.svg" alt="Release">
  <img src="https://img.shields.io/badge/herramientas_MCP-37-blueviolet.svg" alt="MCP Tools">
</p>
<p align="center">
  <img src="https://img.shields.io/badge/precisión_Top--1-92%25-brightgreen.svg" alt="Top-1 Accuracy">
  <img src="https://img.shields.io/badge/MRR-0.9583-brightgreen.svg" alt="MRR">
  <img src="https://img.shields.io/badge/FTS5%2BDense-Hybrid-blue.svg" alt="FTS5 Hybrid">
  <img src="https://img.shields.io/badge/ejecución-100%25_local-orange.svg" alt="100% Local">
  <img src="https://img.shields.io/badge/sin_nube-sin_claves-red.svg" alt="Sin Nube">
</p>

<p align="center">
  <b>Memoria semántica de largo plazo para agentes de IA — 100% local, sin suscripciones, sin nube.</b><br>
  Compatible con VS Code Copilot · LM Studio · Ollama · OpenWebUI · SillyTavern · Claude Desktop · cualquier cliente MCP
</p>

---

## Instalación en 3 pasos

> Sin configurar nada, sin cuentas, sin nube. Solo Python y VS Code.

### Paso 1 — Instalar NEMO

**Windows** (copia y pega en CMD o PowerShell):
```cmd
curl -sSL https://raw.githubusercontent.com/gabrielzaldivar06/NEMO/main/install.bat -o install.bat && install.bat
```

**Linux / macOS** (terminal):
```bash
curl -sSL https://raw.githubusercontent.com/gabrielzaldivar06/NEMO/main/install.sh | bash
```

**Manual** (cualquier sistema):
```bash
git clone https://github.com/gabrielzaldivar06/NEMO.git
cd persistent-ai-memory
pip install -r requirements.txt
```

---

### Paso 2 — Conectar a tu IA

Elige tu cliente:

<details>
<summary><b>VS Code Copilot</b> (recomendado)</summary>

Abre `%APPDATA%\Code\User\mcp.json` (Windows) o `~/.config/Code/User/mcp.json` (Linux/macOS) y añade:

```json
{
  "servers": {
    "nemo": {
      "type": "stdio",
      "command": "python",
      "args": ["C:/ruta/a/persistent-ai-memory/ai_memory_mcp_server.py"]
    }
  }
}
```

Copia también `.github/copilot-instructions.md` a tu proyecto para que el agente use NEMO automáticamente.
</details>

<details>
<summary><b>Claude Desktop</b></summary>

Abre `%APPDATA%\Claude\claude_desktop_config.json` (Windows) o `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) y añade:

```json
{
  "mcpServers": {
    "nemo": {
      "command": "python",
      "args": ["C:/ruta/a/persistent-ai-memory/ai_memory_mcp_server.py"]
    }
  }
}
```
</details>

<details>
<summary><b>Cursor / Windsurf</b></summary>

Añade en la configuración MCP del editor:

```json
{
  "nemo": {
    "command": "python",
    "args": ["/ruta/a/persistent-ai-memory/ai_memory_mcp_server.py"]
  }
}
```
</details>

---

### Paso 3 — Verificar que funciona

Reinicia tu editor. En Agent mode, pídele a la IA:

> *"Guarda en memoria que mi nombre es [tu nombre] y que trabajo con Python"*

Luego abre una sesión nueva y pregunta:

> *"¿Cómo me llamo?"*

Si lo sabe — NEMO está funcionando. ✓

---

> **Requisito opcional pero recomendado:** [LM Studio](https://lmstudio.ai/) con el modelo `text-embedding-qwen3-embedding-4b` para búsqueda semántica completa.  
> Sin LM Studio, NEMO funciona igual con búsqueda de texto básica (Ollama o fallback interno).

---

## ¿Por qué NEMO?

> La mayoría de soluciones de "memoria para IA" guardan texto en una base vectorial y lo llaman suficiente.  
> NEMO ejecuta un pipeline de recuperación de 11 fases de calidad de producción que rivaliza con búsqueda en la nube — completamente en tu máquina local.

| Otras soluciones | NEMO |
|-----------------|------|
| Similitud coseno simple | Pipeline de 11 fases con reranking, decaimiento temporal y clasificación de intención |
| Dependiente de la nube | 100% local — LM Studio + SQLite, sin internet |
| Recuperación uniforme | Bypass adaptativo: enruta consultas al camino rápido O al reranker completo según confianza |
| Olvida sesiones anteriores | Persistencia SQLite — las memorias sobreviven reinicios, cambios de agente y reinstalaciones |
| Gestión manual de memoria | Deduplicación automática en escritura (coseno > 0.92) y supresión de near-dups en lectura |
| Ranking fijo | Bucle de retroalimentación `access_count` — las memorias más recuperadas suben en relevancia |

---

## ¿Qué es NEMO?

NEMO resuelve el problema fundamental de los LLMs: **la amnesia entre sesiones**. Cada vez que abres un chat nuevo, la IA olvida todo. NEMO construye una capa de memoria persistente y buscable semánticamente que cualquier agente puede consultar a través del [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

- Las memorias sobreviven cambios de agente, reinicios de VS Code y reinicios del sistema
- La búsqueda usa embeddings vectoriales locales (Qwen3-4B) + reranking neuronal (BGE)
- Todos los datos viven en `~/.ai_memory/` como SQLite — sin nube, sin rastreo

```
Benchmarks de producción (Sprint 12 — reranker activo):
  Precisión Top-1  →  92 %     (24 queries, corpus real)
  MRR              →  0.9583
  Latencia P95     →  2 847 ms  (pipeline completo — FTS5+Dense+Reranker)

Benchmark stress (48 queries, 120 memorias, categorías extremas):
  Top-1 global     →  83.33 %
  confusory        →  91.67 %
  typo_severe      →  91.67 %
  paraphrase_ext.  →  58.33 %  (ceiling del modelo con vocabulario abstracto)
```

---

## Cómo Funciona

NEMO expone **31 herramientas MCP** a través de un servidor Python stdio. Cuando un agente llama `search_memories`, NEMO ejecuta un pipeline de 11 fases:

```
Consulta
  │
  ├─ 1. Generar embedding asimétrico (Qwen3-4B — query_instruction B1)
  ├─ 2. Caché semántica de sesión (omitir si está en caché)
  ├─ 3. Dense ANN coseno (top-50) + FTS5 BM25 en paralelo (asyncio.gather)
  │     └─ candidatos FTS-only reciben coseno y entran al pipeline
  ├─ 4. Hybrid rescoring (0.7 × semántico + 0.3 × BM25)
  ├─ 5. Decaimiento temporal + bonus de recencia
  ├─ 6. Clasificador de intención de consulta (factual / procedimental / contextual)
  ├─ 7. Boosts de calidad (importancia, corrección +0.35, access count)
  ├─ 8. Bypass adaptativo + gap router
  ├─ 9. Reranking neuronal — BGE-reranker-v2-m3 via llama_cpp :8080 (RWF)
  ├─ 10. Supresión de near-duplicados (coseno > 0.95 duro, > 0.80 suave)
  └─ 11. Retroalimentación access count → retornar top-N
```

---

## Novedades en v1.3.0 (Sprint 15)

### Sprint 15 — Synaptic Tagging · Dashboard 3D · Panel VS Code · Circuit Breaker
- **`synaptic_tagging`**: nueva herramienta MCP que conecta automáticamente memorias relacionadas (importancia ≥ 9 activa el tagging automático)
- **Dashboard neural 3D**: `dashboard.py` genera `dashboard.html` con grafo 3D interactivo (3d-force-graph + three.js), bloom glow, tooltips, búsqueda en vivo y slider de similaridad
- **Panel lateral VS Code `nemo-vscode`**: extensión local con diseño premium oscuro-dorado — estado del sistema en tiempo real, botones de lanzamiento del dashboard 3D, polling automático cada 30 s
- **Circuit Breaker en EmbeddingService**: timeout 10 s (antes 30 s), semáforo 1 concurrente, cooldown 45 s — elimina los freezes del PC al llamar herramientas con LM Studio ocupado
- **Ícono de grafo neuronal** en la activity bar de VS Code (reemplaza el ícono de señal)

---

## Novedades en v1.2.0 (Sprint 11 & 12)

### Sprint 11 — Recuperación Híbrida FTS5 + Dense
- **SQLite FTS5** como índice de texto completo (unicode61, sin diacríticos) para BM25 léxico
- Búsqueda densa y FTS5 corren en **paralelo** (`asyncio.gather`) — sin latencia adicional
- Candidatos exclusivos de FTS5 entran al pipeline de reranking con coseno calculado al vuelo
- Triggers automáticos mantienen el índice FTS5 sincronizado; backfill idempotente en startup

### Sprint 12 — Embeddings Asimétricos + Reranker Real
- **Reranker corregido**: `embedding_config.json` ahora apunta a `llama_cpp` `:8080` (LM Studio no implementa `/v1/rerank`); se añadió detección de falso-200
- **Query instruction B1**: Qwen3 con instrucción asimétrica optimizada — diferencia vocabulario abstracto de nombres técnicos específicos (+4.2pp Top-1 en stress test)
- **`generate_document_embedding()`**: método utilitario disponible para experimentos de recuperación simétrica futura
- **Freeze fixes**: 4 root causes eliminados en el servidor MCP bajo escrituras concurrentes
- **Multi-workspace simultáneo**: instancias en diferentes workspaces ya no se matan entre sí
- **Anti-alucinación**: 4 estrategias integradas (grounding verification, confidence scoring, source attribution, contradiction detection)

---

## Características Principales

| Característica | Detalle |
|----------------|---------|
| **Búsqueda híbrida** | Dense (Qwen3-4B, asimétrico) + FTS5 BM25 léxico en paralelo + reranker BGE |
| **31 herramientas MCP** | Memoria, conversaciones, agenda, correcciones, reflexiones, salud |
| **5 bases de datos SQLite** | conversations · ai_memories · schedule · mcp_tool_calls · vscode_project |
| **Deduplicación semántica** | Umbral duro 0.92 · umbral suave 0.82 (sin memorias duplicadas) |
| **Autoridad temporal** | Decaimiento temporal evita que memorias obsoletas aparezcan |
| **Auto-correcciones** | `create_correction` da boost permanente +0.35 — los errores no se repiten |
| **Importación multiplataforma** | LM Studio · Ollama · OpenWebUI · SillyTavern · Gemini CLI · VS Code |
| **Agenda y recordatorios** | Calendario completo con recurrencia diaria/semanal/mensual/anual |
| **Degradación elegante** | Cae a Ollama → búsqueda de texto si los embeddings no están disponibles |
| **Panel lateral VS Code** | Panel premium oscuro-dorado — estado en vivo de LM Studio, Reranker, DBs y MCP · botones para lanzar Dashboard 3D · polling cada 30 s |
| **Dashboard Neural 3D** | Grafo 3D interactivo generado localmente — bloom glow, hover tooltips, búsqueda en vivo, slider de similaridad |
| **Autostart en Windows** | Inicia LM Studio + carga modelos automáticamente al iniciar sesión |
| **100% local** | Sin claves de API, sin nube, sin suscripciones |

---

## Inicio Rápido

### 1. Requisitos

- Python 3.10+
- [LM Studio](https://lmstudio.ai/) con estos modelos cargados:
  - `text-embedding-qwen3-embedding-4b` (embeddings principales)
  - `text-embedding-bge-reranker-v2-m3` (reranker neuronal)
- O [Ollama](https://ollama.com/) con `nomic-embed-text` como respaldo

### 2. Instalación

```bash
git clone https://github.com/gabrielzaldivar06/NEMO.git
cd persistent-ai-memory
pip install -r requirements.txt
```

### 3. Verificación

```bash
python tests/test_health_check.py
```

Resultado esperado:
```
[✓] Imported ai_memory_core
[✓] Found embedding_config.json
[✓] System health check passed
[✓] All health checks passed! System is ready to use.
```

### 4. Conectar a VS Code Copilot

Agregar a `%APPDATA%\Code\User\mcp.json` (Windows) o `~/.config/Code/User/mcp.json` (Linux/macOS):

```json
{
  "servers": {
    "nemo": {
      "type": "stdio",
      "command": "python",
      "args": ["C:/ruta/a/persistent-ai-memory/ai_memory_mcp_server.py"],
      "env": {}
    }
  }
}
```

Reiniciar VS Code. NEMO estará disponible en Agent mode como servidor MCP `nemo`.

---

## Comportamiento Automático del Agente (VS Code)

El archivo `.github/copilot-instructions.md` incluido indica a VS Code Copilot que use NEMO automáticamente:

- **Inicio de sesión** → `search_memories` + `get_recent_context`
- **Nuevo hecho duradero** → `create_memory` inmediatamente
- **El usuario corrige a la IA** → `create_correction` (boost permanente de recall)
- **Tarea o deadline mencionado** → `create_reminder`
- **Fin de sesión larga** → `store_conversation` + `reflect_on_tool_usage`

No hace falta pedirle al agente que use NEMO — ocurre solo en Agent mode.

---

## Las 31 Herramientas MCP

<details>
<summary><b>Memoria (5 herramientas)</b></summary>

| Herramienta | Descripción |
|-------------|-------------|
| `create_memory` | Guardar una memoria de largo plazo con tipo, importancia y etiquetas |
| `search_memories` | Búsqueda semántica de 11 fases en todas las memorias |
| `get_recent_memories` | Obtener las N memorias más recientes sin búsqueda |
| `update_memory` | Actualizar contenido, importancia o etiquetas de una memoria |
| `delete_memory` | Eliminar permanentemente una memoria |
</details>

<details>
<summary><b>Conversaciones (5 herramientas)</b></summary>

| Herramienta | Descripción |
|-------------|-------------|
| `store_conversation` | Persistir una sesión de conversación completa |
| `search_conversations` | Búsqueda semántica en el historial de conversaciones |
| `get_conversation_history` | Obtener lista cronológica de conversaciones |
| `get_recent_context` | Mostrar actividad de las últimas 24–72 h |
| `import_conversations` | Importar desde LM Studio, OpenWebUI, SillyTavern, VS Code |
</details>

<details>
<summary><b>Agenda (8 herramientas)</b></summary>

| Herramienta | Descripción |
|-------------|-------------|
| `create_appointment` | Programar un evento con recurrencia opcional |
| `get_upcoming_appointments` | Listar los próximos N días de citas |
| `cancel_appointment` | Cancelar una cita programada |
| `complete_appointment` | Marcar una cita como completada |
| `create_reminder` | Crear un recordatorio con prioridad |
| `get_active_reminders` | Listar todos los recordatorios pendientes |
| `complete_reminder` | Marcar un recordatorio como hecho |
| `reschedule_reminder` | Mover un recordatorio a una nueva fecha |
</details>

<details>
<summary><b>Correcciones y Conocimiento (3 herramientas)</b></summary>

| Herramienta | Descripción |
|-------------|-------------|
| `create_correction` | Registrar un error de la IA — boost permanente +0.35 de relevancia |
| `create_memory` | Guardar memorias tipo factual / procedimental / insight / episódico |
| `search_memories` | Consultar con filtro `memory_type` para recuperación específica |
</details>

<details>
<summary><b>Reflexiones e Insights (4 herramientas)</b></summary>

| Herramienta | Descripción |
|-------------|-------------|
| `reflect_on_tool_usage` | Generar insights de IA a partir de patrones de uso de herramientas |
| `get_ai_insights` | Recuperar reflexiones almacenadas de la IA |
| `store_ai_reflection` | Guardar una reflexión manualmente |
| `get_tool_usage_summary` | Resumen estadístico del uso de herramientas MCP |
</details>

<details>
<summary><b>Sistema y Utilidades (6 herramientas)</b></summary>

| Herramienta | Descripción |
|-------------|-------------|
| `get_system_health` | Verificación completa: DBs, embeddings, reranker |
| `get_current_time` | Hora actual con zona horaria |
| `get_weather_open_meteo` | Clima vía Open-Meteo (sin clave de API) |
| `brave_web_search` | Búsqueda web vía Brave Search API |
| `brave_local_search` | Búsqueda de negocios y lugares locales |
| `get_recent_context` | Actividad reciente unificada de todas las bases de datos |
</details>

---

## Arquitectura

```
┌─────────────────────────────────────────────────────┐
│        Cliente IA (VS Code Copilot, Claude…)         │
└────────────────────────┬────────────────────────────┘
                         │ MCP stdio
┌────────────────────────▼────────────────────────────┐
│       ai_memory_mcp_server.py  (31 herramientas)     │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│            ai_memory_core.py  (~4900 líneas)         │
│  ┌─────────────────┐  ┌──────────────────────────┐  │
│  │ EmbeddingService│  │    RerankingService       │  │
  │  │ Qwen3-4B @:1234 │  │ BGE-reranker-v2-m3 @:8080│  │
│  └─────────────────┘  └──────────────────────────┘  │
│  ┌─────────────────────────────────────────────────┐ │
│  │         PersistentAIMemorySystem                 │ │
  │  │  búsqueda 11 fases · FTS5+Dense paralelo        │ │
  │  │  dedup semántico · decaimiento · RWF · near-dup  │ │
│  └─────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────┘
                         │
          ┌──────────────┼───────────────┐
          ▼              ▼               ▼
  conversations.db  ai_memories.db  schedule.db
  vscode_project.db  mcp_tool_calls.db
          (~/.ai_memory/)
```

---

## Proveedores de Embeddings

| Proveedor | Modelo | Dimensiones | Costo |
|-----------|--------|-------------|-------|
| **LM Studio** (recomendado) | Qwen3-Embedding-4B | 3840D | Gratis |
| **llama_cpp** (reranker) | BGE-reranker-v2-m3-Q4_K_M | — | Gratis |
| **Ollama** (respaldo) | nomic-embed-text | 768D | Gratis |
| **OpenAI** (nube) | text-embedding-3-large | 3072D | $$$ |

Configurar en `embedding_config.json`. El sistema cae graciosamente si LM Studio no está disponible.

---

## Documentación

| Documento | Descripción |
|-----------|-------------|
| [NEMO_TECHNICAL_REFERENCE.md](NEMO_TECHNICAL_REFERENCE.md) | Referencia técnica exhaustiva (17 secciones, esquemas, benchmarks) |
| [INSTALL.md](INSTALL.md) | Guía de instalación completa |
| [CONFIGURATION.md](CONFIGURATION.md) | Todas las opciones de configuración |
| [API.md](API.md) | Referencia de la API Python |
| [TESTING.md](TESTING.md) | Suite de pruebas y verificaciones de salud |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Problemas comunes y soluciones |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Guía de despliegue en producción |
| [REDDIT_QUICKSTART.md](REDDIT_QUICKSTART.md) | Inicio rápido en 5 minutos |

---

## Tecnologías Utilizadas

NEMO se apoya en excelentes proyectos de código abierto y estándares abiertos:

| Tecnología | Rol | Enlace |
|------------|-----|--------|
| [Model Context Protocol](https://modelcontextprotocol.io/) | Capa de transporte — cómo los agentes llaman a NEMO | Anthropic / Estándar abierto |
| [LM Studio](https://lmstudio.ai/) | Aloja modelos de embeddings y reranking localmente | lmstudio.ai |
| [Qwen3-Embedding-4B](https://huggingface.co/Qwen/Qwen3-Embedding) | Modelo de embeddings principal (3840D) | Alibaba / HuggingFace |
| [BGE-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) | Reranker neuronal cross-encoder | BAAI / HuggingFace |
| [Ollama](https://ollama.com/) | Proveedor de embeddings de respaldo (`nomic-embed-text`) | ollama.com |
| [SQLite](https://www.sqlite.org/) | Todo el almacenamiento persistente — sin servidor, portable | sqlite.org |
| [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk) | Implementación del servidor MCP stdio | Anthropic |
| [Open-Meteo](https://open-meteo.com/) | API de clima — sin clave requerida | open-meteo.com |
| [Brave Search API](https://brave.com/search/api/) | Herramientas de búsqueda web y local | brave.com |

---

## Contribuir

¡Las contribuciones son bienvenidas! Ver [CONTRIBUTORS.md](CONTRIBUTORS.md) para configuración de desarrollo, estilo de código y el proceso de contribución.

---

## Licencia

Este proyecto está licenciado bajo **Creative Commons Atribución-No Comercial 4.0 Internacional (CC BY-NC 4.0)**.

- **Permitido:** uso personal, educativo, investigación, proyectos no comerciales, modificar y compartir con atribución.
- **No permitido:** vender el software, incorporarlo en productos de pago, usarlo en servicios SaaS comerciales, ni cualquier uso que genere ingresos directa o indirectamente.
- **Uso comercial:** contacta al autor para un acuerdo de licencia.

Ver [LICENSE](LICENSE) · [Texto completo CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/legalcode)

---

## Créditos

NEMO es el resultado de una colaboración inusual — y creemos que vale la pena decirlo en voz alta.

### Gabriel &nbsp;·&nbsp; [@gabrielzaldivar06](https://github.com/gabrielzaldivar06)

Arquitecto del proyecto y fuerza motriz detrás de NEMO.

### GitHub Copilot &nbsp;·&nbsp; Claude Sonnet (Anthropic)

Socio principal de implementación en todos los sprints. Motor central de (`ai_memory_core.py`), diseñó el pipeline de recuperación de 11 fases, implementó la integración del reranker, el sistema de autoridad temporal, la deduplicación semántica y la extensión de VS Code — trabajando iterativamente con Gabriel desde la especificación hasta el código de producción.

> NEMO es uno de los primeros proyectos de código abierto construido explícitamente como una **colaboración de pair-programming humano ↔ IA**,  
> donde las propias limitaciones de memoria de la IA eran el problema que se resolvía.  

### Comunidad Open Source

El [ecosistema MCP](https://modelcontextprotocol.io/), [BAAI](https://huggingface.co/BAAI) por los modelos BGE, el [equipo Qwen de Alibaba](https://huggingface.co/Qwen) por Qwen3-Embedding, y el equipo de [LM Studio](https://lmstudio.ai/) por hacer accesible el serving local de modelos.

---

<p align="center">
  <b>⭐ Si NEMO hace más inteligente a tu asistente de IA, ¡dale una estrella!</b>
</p>
<p align="center">
  Construido con determinación &nbsp;·&nbsp; Depurado con paciencia &nbsp;·&nbsp; Diseñado para el futuro de la IA
</p>
<p align="center">
  <sub>Una colaboración humano-IA — porque las mejores herramientas las construyen quienes más las necesitan.</sub>
</p>
