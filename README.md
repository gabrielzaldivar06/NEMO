<div align="center">

```
███╗   ██╗███████╗███╗   ███╗ ██████╗
████╗  ██║██╔════╝████╗ ████║██╔═══██╗
██╔██╗ ██║█████╗  ██╔████╔██║██║   ██║
██║╚██╗██║██╔══╝  ██║╚██╔╝██║██║   ██║
██║ ╚████║███████╗██║ ╚═╝ ██║╚██████╔╝
╚═╝  ╚═══╝╚══════╝╚═╝     ╚═╝ ╚═════╝
```

### **Sistema de Memoria Persistente para IA**
*La IA que trabajó contigo ayer, lo recuerda hoy.*

---

[![Licencia: CC BY-NC 4.0](https://img.shields.io/badge/Licencia-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Release](https://img.shields.io/badge/release-v1.3.0--Sprint15-22c55e.svg)](https://github.com/gabrielzaldivar06/NEMO/releases)
[![MCP Tools](https://img.shields.io/badge/herramientas_MCP-44-8b5cf6.svg)](https://modelcontextprotocol.io/)

[![Top-1 Accuracy](https://img.shields.io/badge/precisión_Top--1-92%25-16a34a.svg)](#benchmarks)
[![MRR](https://img.shields.io/badge/MRR-0.9583-16a34a.svg)](#benchmarks)
[![Hybrid Search](https://img.shields.io/badge/FTS5%2BDense-Hybrid-3b82f6.svg)](#arquitectura)
[![100% Local](https://img.shields.io/badge/ejecución-100%25_local-f97316.svg)](#proveedores-de-embeddings)
[![No Cloud](https://img.shields.io/badge/sin_nube-sin_claves-ef4444.svg)](#licencia)

<br>

**Memoria semántica de largo plazo para agentes de IA — 100% local, sin suscripciones, sin nube.**

Compatible con&nbsp; `VS Code Copilot` &nbsp;·&nbsp; `LM Studio` &nbsp;·&nbsp; `Ollama` &nbsp;·&nbsp; `OpenWebUI` &nbsp;·&nbsp; `SillyTavern` &nbsp;·&nbsp; `Claude Desktop` &nbsp;·&nbsp; cualquier cliente MCP

</div>

---

## ¿Qué problema resuelve NEMO?

> Cada vez que abres un chat nuevo, tu IA olvida **todo**. Tu nombre, tu stack, tus decisiones de arquitectura, tus preferencias de código. Empiezas de cero. Siempre.

NEMO construye una **capa de memoria persistente y buscable semánticamente** que cualquier agente puede consultar a través del [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). Las memorias sobreviven reinicios, cambios de agente e incluso reinstalaciones. Todo en tu máquina.

---

## ⚡ Instalación en 3 pasos

> Sin cuentas. Sin configuración. Sin nube. Solo Python.

### Paso 1 — Instalar NEMO

<table>
<tr>
<td><b>🪟 Windows</b></td>
<td>

```cmd
curl -sSL https://raw.githubusercontent.com/gabrielzaldivar06/NEMO/main/install.bat -o install.bat && install.bat
```

</td>
</tr>
<tr>
<td><b>🐧 Linux / macOS</b></td>
<td>

```bash
curl -sSL https://raw.githubusercontent.com/gabrielzaldivar06/NEMO/main/install.sh | bash
```

</td>
</tr>
<tr>
<td><b>📦 Manual</b></td>
<td>

```bash
git clone https://github.com/gabrielzaldivar06/NEMO.git
cd persistent-ai-memory && pip install -r requirements.txt
```

</td>
</tr>
</table>

### Paso 2 — Conectar a tu IA

<details>
<summary><b>🖥️ VS Code Copilot</b> (recomendado)</summary>

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
<summary><b>🤖 Claude Desktop</b></summary>

Abre `%APPDATA%\Claude\claude_desktop_config.json` (Windows) o `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

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
<summary><b>🌊 Cursor / Windsurf</b></summary>

```json
{
  "nemo": {
    "command": "python",
    "args": ["/ruta/a/persistent-ai-memory/ai_memory_mcp_server.py"]
  }
}
```
</details>

### Paso 3 — Verificar que funciona

Reinicia tu editor. En Agent mode, pídele a la IA:

> *"Guarda en memoria que mi nombre es [tu nombre] y que trabajo con Python"*

Luego abre una sesión nueva y pregunta:

> *"¿Cómo me llamo?"*

**Si lo sabe — NEMO está funcionando ✓**

> **Recomendado:** [LM Studio](https://lmstudio.ai/) con `text-embedding-qwen3-embedding-4b` para búsqueda semántica completa.
> Sin él, NEMO funciona igual con búsqueda de texto básica (Ollama o fallback interno).

---

## 🆚 NEMO vs. otras soluciones

| | Otras soluciones | **NEMO** |
|---|---|---|
| **Búsqueda** | Similitud coseno simple | Pipeline propietario de múltiples etapas: búsqueda híbrida, reranking neuronal, señales contextuales y temporales |
| **Infraestructura** | Dependiente de la nube | 100% local — LM Studio + SQLite, sin internet |
| **Rendimiento** | Recuperación uniforme | Bypass adaptativo: enruta al camino rápido O al reranker completo según confianza |
| **Persistencia** | Olvida sesiones anteriores | SQLite — sobrevive reinicios, cambios de agente y reinstalaciones |
| **Duplicados** | Memorias repetidas | Deduplicación automática en escritura (coseno > 0.92) |
| **Ranking** | Fijo | Bucle de retroalimentación `access_count` — las más usadas suben en relevancia |

---

## 🧠 Cómo Funciona

NEMO expone **44 herramientas MCP** a través de un servidor Python stdio. Cuando un agente llama `search_memories`, la consulta pasa por un **pipeline de recuperación de múltiples etapas** desarrollado internamente:

- Combina búsqueda vectorial densa y búsqueda léxica en paralelo
- Aplica reranking neuronal para priorizar los resultados más relevantes
- Incorpora señales temporales, de calidad y de uso histórico para un ranking contextual
- Suprime resultados redundantes antes de retornar el conjunto final

El diseño exacto del pipeline es propietario. Los resultados hablan por sí solos en los benchmarks.

### Benchmarks de producción <a id="benchmarks"></a>

<table>
<tr><th>Métrica</th><th>Sprint 12 (reranker activo)</th><th>Stress test (48 queries)</th></tr>
<tr><td><b>Precisión Top-1</b></td><td>✅ 92%</td><td>✅ 83.33% global</td></tr>
<tr><td><b>MRR</b></td><td>✅ 0.9583</td><td>–</td></tr>
<tr><td><b>Latencia P95</b></td><td>2 847 ms (FTS5+Dense+Reranker)</td><td>–</td></tr>
<tr><td><b>confusory</b></td><td>–</td><td>✅ 91.67%</td></tr>
<tr><td><b>typo_severe</b></td><td>–</td><td>✅ 91.67%</td></tr>
<tr><td><b>paraphrase_ext.</b></td><td>–</td><td>⚠️ 58.33% (ceiling del modelo)</td></tr>
</table>

---

## ✨ Características Principales

| Característica | Detalle |
|---|---|
| 🔍 **Búsqueda híbrida** | Dense (Qwen3-4B, asimétrico) + FTS5 BM25 léxico en paralelo + reranker BGE |
| 🛠️ **44 herramientas MCP** | Memoria · conversaciones · agenda · correcciones · reflexiones · salud · roleplay · proyectos · cognición avanzada |
| 🗄️ **5 bases de datos SQLite** | `conversations` · `ai_memories` · `schedule` · `mcp_tool_calls` · `vscode_project` |
| 🔁 **Deduplicación semántica** | Umbral duro 0.92 · umbral suave 0.82 — sin memorias duplicadas |
| ⏳ **Autoridad temporal** | Decaimiento temporal evita que memorias obsoletas aparezcan |
| ✏️ **Auto-correcciones** | `create_correction` da boost permanente +0.35 — los errores no se repiten |
| 📥 **Importación multiplataforma** | LM Studio · Ollama · OpenWebUI · SillyTavern · Gemini CLI · VS Code |
| 📅 **Agenda completa** | Calendario con recurrencia diaria / semanal / mensual / anual |
| 🌊 **Degradación elegante** | Cae a Ollama → búsqueda de texto si los embeddings no están disponibles |
| 🎨 **Panel VS Code premium** | UI oscuro-dorado en tiempo real — estado de LM Studio, Reranker, DBs y MCP · launch del Dashboard 3D · polling cada 30 s |
| 🌐 **Dashboard Neural 3D** | Grafo 3D interactivo — bloom glow · hover tooltips · búsqueda en vivo · slider de similaridad |
| 🚀 **Autostart Windows** | Inicia LM Studio + carga modelos automáticamente al iniciar sesión |
| 🔒 **100% local** | Sin claves de API · sin nube · sin suscripciones |

---

## 🤖 Comportamiento Automático del Agente

El archivo `.github/copilot-instructions.md` instruye a VS Code Copilot para usar NEMO automáticamente — sin pedírselo:

| Momento | Acción automática |
|---|---|
| 🟢 Inicio de sesión | `prime_context` + `search_memories` + `get_recent_context` |
| 💡 Nuevo hecho duradero | `create_memory` inmediatamente |
| ❌ El usuario corrige a la IA | `create_correction` (boost permanente de recall) |
| 📌 Tarea o deadline mencionado | `create_reminder` |
| 🏁 Fin de sesión larga | `store_conversation` + `reflect_on_tool_usage` |

---

## 🛠️ 44 Herramientas MCP

<details>
<summary><b>🧠 Memoria (6 herramientas)</b></summary>

| Herramienta | Descripción |
|---|---|
| `prime_context` | Carga el contexto de trabajo — memorias, recordatorios y última sesión en una llamada |
| `create_memory` | Guardar una memoria de largo plazo con tipo, importancia y etiquetas |
| `search_memories` | Búsqueda semántica avanzada de múltiples etapas en todas las memorias |
| `update_memory` | Actualizar contenido, importancia o etiquetas de una memoria |
| `create_correction` | Registrar un error de la IA — boost permanente +0.35 de relevancia |
| `detect_redundancy` | Detectar memorias redundantes o duplicadas antes de guardar |
</details>

<details>
<summary><b>💬 Conversaciones (3 herramientas)</b></summary>

| Herramienta | Descripción |
|---|---|
| `store_conversation` | Persistir una sesión de conversación completa |
| `get_recent_context` | Mostrar actividad de las últimas 24–72 h |
| `memory_chronicle` | Historial cronológico narrativo de memorias y sesiones |
</details>

<details>
<summary><b>📅 Agenda y Recordatorios (10 herramientas)</b></summary>

| Herramienta | Descripción |
|---|---|
| `create_appointment` | Programar un evento con recurrencia opcional |
| `get_appointments` | Listar todas las citas |
| `get_upcoming_appointments` | Listar los próximos N días |
| `cancel_appointment` | Cancelar una cita programada |
| `complete_appointment` | Marcar una cita como completada |
| `create_reminder` | Crear un recordatorio con prioridad |
| `get_reminders` | Listar todos los recordatorios |
| `get_active_reminders` | Solo los recordatorios pendientes |
| `get_completed_reminders` | Recordatorios completados |
| `complete_reminder` | Marcar como hecho |
| `reschedule_reminder` | Mover a nueva fecha |
| `delete_reminder` | Eliminar un recordatorio |
</details>

<details>
<summary><b>🔬 Reflexiones e Insights (4 herramientas)</b></summary>

| Herramienta | Descripción |
|---|---|
| `reflect_on_tool_usage` | Generar insights a partir de patrones de uso de herramientas |
| `get_ai_insights` | Recuperar reflexiones almacenadas |
| `store_ai_reflection` | Guardar una reflexión manualmente |
| `get_tool_usage_summary` | Resumen estadístico del uso MCP |
| `write_ai_insights` | Escribir insights clave al finalizar una sesión |
</details>

<details>
<summary><b>🧬 Cognición Avanzada (6 herramientas)</b></summary>

| Herramienta | Descripción |
|---|---|
| `synaptic_tagging` | Conectar automáticamente memorias relacionadas (importancia ≥ 9) |
| `salience_score` | Calcular la relevancia de una memoria en el contexto actual |
| `cognitive_ingest` | Ingestión inteligente con deduplicación y clasificación automática |
| `anticipate` | Predecir qué memorias serán relevantes en la próxima sesión |
| `intent_anchor` | Anclar la intención del usuario para mejorar la recuperación |
| `get_system_health` | Verificación completa: DBs · embeddings · reranker |
</details>

<details>
<summary><b>🏗️ Proyectos y Desarrollo (5 herramientas)</b></summary>

| Herramienta | Descripción |
|---|---|
| `save_development_session` | Guardar el estado completo de una sesión de desarrollo |
| `store_project_insight` | Persistir decisiones técnicas, hallazgos y restricciones |
| `search_project_history` | Buscar en el historial de decisiones del proyecto |
| `link_code_context` | Vincular un archivo de código con memorias y decisiones |
| `get_project_continuity` | Recuperar el estado exacto donde se dejó el proyecto |
</details>

<details>
<summary><b>🎭 Roleplay y Narrativa (3 herramientas)</b></summary>

| Herramienta | Descripción |
|---|---|
| `get_character_context` | Recuperar contexto de personajes antes de cualquier roleplay |
| `store_roleplay_memory` | Persistir lo ocurrido en una sesión de roleplay |
| `search_roleplay_history` | Buscar en el historial de narrativas y personajes |
</details>

<details>
<summary><b>🌍 Utilidades del Sistema (7 herramientas)</b></summary>

| Herramienta | Descripción |
|---|---|
| `get_current_time` | Hora actual con zona horaria |
| `get_weather_open_meteo` | Clima vía Open-Meteo (sin clave de API) |
| `get_recent_context` | Actividad reciente unificada de todas las bases de datos |
| `get_system_health` | Estado del sistema: embeddings, reranker, DBs |
| `get_tool_usage_summary` | Estadísticas de uso de herramientas |
| `search_memories` | Búsqueda con filtros `memory_type`, `tags`, rango de fechas |
| `cognitive_ingest` | Ingestión masiva con clasificación semántica automática |
</details>

---

## 🖥️ Herramientas del Sistema

### Monitor de Estado (`status_monitor.py`)

Aplicación de escritorio con **ícono en la bandeja del sistema** que monitoriza en tiempo real:

- Estado de LM Studio (embeddings)
- Estado del Reranker (llama-server)
- Salud de la base de datos SQLite

**Requisitos adicionales:**
```bash
pip install pystray pillow customtkinter
```

**Iniciar:**
```bash
# Windows (sin ventana de consola)
start_monitor.bat

# Cualquier plataforma
python status_monitor.py
```

Al ejecutarse, aparece un ícono en el área de notificaciones de Windows. Clic derecho para ver el panel de estado o cerrar el monitor.

---

### Mantenimiento de Base de Datos (`database_maintenance.py`)

Módulo de mantenimiento automatizado para la base de datos SQLite:

- **Limpieza** — elimina memorias expiradas según política de retención configurable
- **Optimización** — ejecuta `VACUUM` y `ANALYZE` para mantener rendimiento óptimo
- **Sharding** — crea nuevas bases de datos cuando la activa supera el tamaño/tiempo límite
- **Rotación** — gestiona el ciclo de vida de múltiples archivos `.db` en `~/.ai_memory/`

**Ejecutar mantenimiento manual:**
```bash
python database_maintenance.py
```

**Servicio automático de mantenimiento:**
```bash
# Windows (servicio en background)
start_maintenance_service.bat

# PowerShell
.\start_maintenance_service.ps1
```

Configura el intervalo y políticas de retención en `memory_config.json`.

---

### Instrucciones para VS Code Copilot (`.github/copilot-instructions.md`)

Archivo de instrucciones que hace que **VS Code Copilot use NEMO automáticamente** sin que el usuario tenga que pedírselo.

**Instalación:**
1. Copia `.github/copilot-instructions.md` a la carpeta `.github/` de tu proyecto (o al nivel raíz del workspace).
2. VS Code Copilot lo carga automáticamente en cada sesión.

**Qué hace:**
- Obliga al agente a llamar `prime_context()` como primera acción en cada conversación
- Define el flujo de trabajo: cuándo guardar memorias, correcciones, insights
- Especifica los tipos de memoria y cuándo usar cada uno
- Habilita agenda, recordatorios y reflexiones de fin de sesión

> **Nota:** El archivo contiene un bloque `⚠️ EXECUTE RIGHT NOW` al inicio — esto es intencional para maximizar la probabilidad de que el modelo lo ejecute antes de responder.

---



```
┌──────────────────────────────────────────────────────────┐
│          Cliente IA  (VS Code Copilot · Claude · Cursor)  │
└───────────────────────────┬──────────────────────────────┘
                            │  MCP stdio
┌───────────────────────────▼──────────────────────────────┐
│       ai_memory_mcp_server.py   (44 herramientas MCP)     │
└───────────────────────────┬──────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────┐
│              ai_memory_core.py   (~4 900 líneas)          │
│  ┌───────────────────┐    ┌─────────────────────────────┐ │
│  │  EmbeddingService │    │      RerankingService        │ │
│  │  Qwen3-4B @ :1234 │    │  BGE-reranker-v2-m3 @ :8080  │ │
│  │  circuit-breaker  │    │     timeout 10s  ·  RWF      │ │
│  └───────────────────┘    └─────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────┐ │
│  │            PersistentAIMemorySystem                   │ │
│  │   multi-stage search  ·  FTS5+Dense paralelo           │ │
│  │   dedup semántico  ·  decaimiento  ·  near-dup        │ │
│  └──────────────────────────────────────────────────────┘ │
└───────────────────────────┬──────────────────────────────┘
                            │
         ┌──────────────────┼───────────────────┐
         ▼                  ▼                   ▼
  ai_memories.db    conversations.db      schedule.db
  vscode_project.db    mcp_tool_calls.db
              (~/.ai_memory/)
```

---

## 🔌 Proveedores de Embeddings <a id="proveedores-de-embeddings"></a>

| Proveedor | Modelo | Dimensiones | Costo |
|---|---|---|---|
| ⭐ **LM Studio** (recomendado) | Qwen3-Embedding-4B | 3 840D | Gratis |
| ⚙️ **llama_cpp** (reranker) | BGE-reranker-v2-m3-Q4_K_M | — | Gratis |
| 🦙 **Ollama** (respaldo) | nomic-embed-text | 768D | Gratis |
| ☁️ **OpenAI** (nube) | text-embedding-3-large | 3 072D | $$$ |

Configurar en `embedding_config.json`. El sistema cae graciosamente si LM Studio no está disponible.

---

## 🆕 Historial de versiones

<details open>
<summary><b>v1.3.0 — Sprint 15  (marzo 2026)</b></summary>

- **`synaptic_tagging`** — nueva herramienta MCP: conecta memorias relacionadas automáticamente (importancia ≥ 9)
- **Panel Neural 3D** — `dashboard.py` genera 3D interactivo (three.js + bloom glow + slider de similaridad)
- **Panel VS Code premium** — extensión `nemo-vscode` con UI oscuro-dorado, estado en tiempo real, botón de lanzamiento Dashboard 3D
- **Circuit Breaker** en `EmbeddingService` — timeout 10 s · semáforo 1 · cooldown 45 s — elimina freezes con LM Studio ocupado
- **Ícono de grafo neuronal** en la activity bar de VS Code
</details>

<details>
<summary><b>v1.2.0 — Sprint 11 & 12</b></summary>

**Sprint 11 — Recuperación Híbrida FTS5 + Dense**
- SQLite FTS5 (unicode61, sin diacríticos) para BM25 léxico
- Dense + FTS5 en paralelo vía `asyncio.gather` — sin latencia adicional
- Triggers automáticos mantienen el índice FTS5 sincronizado

**Sprint 12 — Embeddings Asimétricos + Reranker Real**
- Reranker corregido: apunta a `llama_cpp :8080` + detección de falso-200
- Query instruction B1: diferencia vocabulario abstracto de nombres técnicos (+4.2pp Top-1)
- Freeze fixes: 4 root causes eliminados en escrituras concurrentes
- Multi-workspace simultáneo: instancias en distintos workspaces ya no se matan entre sí
- Anti-alucinación: 4 estrategias integradas (grounding · confidence · source attribution · contradiction)
</details>

---

## 📚 Documentación

| Documento | Descripción |
|---|---|
| [INSTALL.md](INSTALL.md) | Guía de instalación completa |
| [CONFIGURATION.md](CONFIGURATION.md) | Todas las opciones de configuración |
| [API.md](API.md) | Referencia de la API Python |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Problemas comunes y soluciones |
| [REDDIT_QUICKSTART.md](REDDIT_QUICKSTART.md) | Inicio rápido en 5 minutos |
| [.github/copilot-instructions.md](.github/copilot-instructions.md) | Instrucciones para auto-uso en VS Code Copilot |

---

## 🔧 Tecnologías

| Tecnología | Rol |
|---|---|
| [Model Context Protocol](https://modelcontextprotocol.io/) | Capa de transporte — cómo los agentes llaman a NEMO |
| [LM Studio](https://lmstudio.ai/) | Hosting local de modelos de embeddings y reranking |
| [Qwen3-Embedding-4B](https://huggingface.co/Qwen/Qwen3-Embedding) | Modelo de embeddings principal (3 840D) |
| [BGE-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) | Reranker neuronal cross-encoder |
| [Ollama](https://ollama.com/) | Proveedor de embeddings de respaldo |
| [SQLite](https://www.sqlite.org/) | Almacenamiento persistente — sin servidor, portable |
| [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk) | Implementación del servidor MCP stdio |
| [Open-Meteo](https://open-meteo.com/) | API de clima sin clave requerida |

---

## 🤝 Contribuir

¡Las contribuciones son bienvenidas! Ver [CONTRIBUTORS.md](CONTRIBUTORS.md) para la configuración de desarrollo, estilo de código y proceso de contribución.

---

## 📄 Licencia

Este proyecto está licenciado bajo **Creative Commons Atribución-No Comercial 4.0 Internacional (CC BY-NC 4.0)**.

- ✅ **Permitido:** uso personal, educativo, investigación, proyectos no comerciales, modificar y compartir con atribución.
- ❌ **No permitido:** vender el software, incorporarlo en productos de pago, usarlo en servicios SaaS comerciales.
- 💼 **Uso comercial:** contacta al autor para un acuerdo de licencia.

Ver [LICENSE](LICENSE) · [Texto completo CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/legalcode)

---

## 🏆 Créditos

**Gabriel Zaldívar** · [@gabrielzaldivar06](https://github.com/gabrielzaldivar06) — Arquitecto y creador de NEMO.

**GitHub Copilot / Claude Sonnet (Anthropic)** — Socio de pair-programming. Trabajando iterativamente desde la especificación hasta producción.

**Comunidad Open Source** — El [ecosistema MCP](https://modelcontextprotocol.io/), [BAAI](https://huggingface.co/BAAI) por los modelos BGE, el [equipo Qwen de Alibaba](https://huggingface.co/Qwen) por Qwen3-Embedding, y el equipo de [LM Studio](https://lmstudio.ai/).

> NEMO es uno de los primeros proyectos open source construido como **colaboración de pair-programming humano ↔ IA**  
> usando el propio NEMO — donde las limitaciones de memoria de la IA eran exactamente el problema que se resolvía.

---

<div align="center">

**⭐ Si NEMO hace más inteligente a tu asistente de IA, ¡dale una estrella!**

Construido con determinación &nbsp;·&nbsp; Depurado con paciencia &nbsp;·&nbsp; Diseñado para el futuro de la IA

*Una colaboración humano-IA — porque las mejores herramientas las construyen quienes más las necesitan.*

</div>
