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
[![Release](https://img.shields.io/badge/release-v1.4.0-22c55e.svg)](https://github.com/gabrielzaldivar06/NEMO/releases)
[![MCP Tools](https://img.shields.io/badge/herramientas_MCP-42-8b5cf6.svg)](https://modelcontextprotocol.io/)

[![Top-1 Accuracy](https://img.shields.io/badge/precisión_Top--1-91.67%25-16a34a.svg)](#benchmarks)
[![MRR](https://img.shields.io/badge/MRR-0.9583-16a34a.svg)](#benchmarks)
[![Confusory](https://img.shields.io/badge/adversarial-100%25-16a34a.svg)](#benchmarks)
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

> ## 🐳 Quickstart con Docker (recomendado, vendor-agnóstico)
>
> Una sola dependencia (Docker), funciona en Linux/macOS/Windows, conecta a **cualquier IA** en segundos. Sin Python local, sin venvs, sin LM Studio/Ollama instalados a mano.
>
> El flujo completo son **tres pasos secuenciales**. Los dos primeros se hacen *una sola vez*; el tercero es el comando que repites por cada proyecto:
>
> 1. **🛠️ Setup único por máquina** — levantar el servidor (1 vez en la vida).
> 2. **🔌 Vincular tu cliente AI** — pegar la URL de NEMO en su config (1 vez por cliente).
> 3. **⭐ Activar NEMO en un proyecto** — el comando que repites a diario por cada proyecto.
> 4. **¿Cómo saber si NEMO ya está listo?** — validación end-to-end.
>
> ---
>
> ### 1. 🛠️ Setup único por máquina — levantar el servidor
>
> Construye la imagen `nemo:local` y deja al servidor corriendo en `http://localhost:8765` con `restart: unless-stopped`. Después no lo vuelves a tocar — se auto-arranca con tu sistema.
>
> ```bash
> git clone https://github.com/gabrielzaldivar06/NEMO.git
> cd NEMO
> docker compose up -d --build
> ```
>
> Esto deja tres puertas listas en el mismo puerto `8765`:
>
> | Endpoint | Cliente |
> |---|---|
> | `http://localhost:8765/mcp/sse` | Claude Code/Desktop, Cursor, Windsurf, Cline, VS Code Copilot |
> | `http://localhost:8765/openapi.json` | ChatGPT custom GPTs (importar como Action) |
> | `http://localhost:8765/api/...` | Gemini, LangChain, n8n, scripts (REST plano) |
>
> > ⚠️ **El servidor ya está disponible — pero ninguna IA sabe que existe todavía.** Eso lo resuelve el siguiente paso.
>
> ---
>
> ### 2. 🔌 Vincular cada cliente AI con NEMO (manual)
>
> Cada cliente lee la URL de NEMO de un sitio distinto. Hazlo **una vez** por cliente, no por proyecto:
>
> | Cliente | Acción única |
> |---|---|
> | **Claude Code** | `claude mcp add nemo http://localhost:8765/mcp/sse --transport sse` |
> | **Claude Desktop** | Pegar URL en `claude_desktop_config.json` |
> | **Cursor / Windsurf / Cline** | Settings → MCP → URL `http://localhost:8765/mcp/sse` |
> | **VS Code Copilot** | URL en `~/.config/Code/User/mcp.json` |
> | **ChatGPT custom GPT** | Builder → Actions → Import URL `http://localhost:8765/openapi.json` |
> | **Gemini / LangChain / n8n** | URL REST en tu código |
>
> Una vez vinculados, NEMO queda como un "fondo" para tus IAs — siempre presente, siempre disponible. Solo te falta forzarlo a usarse en cada proyecto.
>
> ---
>
> ### 3. ⭐ Activar NEMO en un proyecto (una vez por cada proyecto nuevo)
>
> Una sola línea, idempotente, cubre Claude, Cursor, Windsurf, Cline, VS Code Copilot y cualquier cliente que lea `AGENTS.md`. Elige tu sistema:
>
> #### 🐧 Linux / macOS / WSL (bash, zsh)
>
> ```bash
> cd ~/tu-proyecto-favorito        # el proyecto donde quieres avanzar a velocidades cercanas a la luz 🚀
> docker run --rm --add-host=host.docker.internal:host-gateway -v "$PWD":/workdir nemo:local nemo-attach
> ```
>
> #### 🪟 Windows (PowerShell — viene de fábrica con Windows 10/11)
>
> ```powershell
> cd $HOME\tu-proyecto-favorito    # el proyecto donde quieres avanzar a velocidades cercanas a la luz 🚀
> docker run --rm --add-host=host.docker.internal:host-gateway -v "${PWD}:/workdir" nemo:local nemo-attach
> ```
>
> > 💡 ¿Usas el viejo `cmd.exe` ("Símbolo del sistema") en lugar de PowerShell? Sustituye `"${PWD}:/workdir"` por `"%cd%:/workdir"` en el comando de arriba. PowerShell es más cómodo y ya lo tienes instalado.
>
> > 🤔 **¿Por qué este comando?** Porque sin él, tu IA *sabe* que NEMO existe (vía la URL del paso 2) pero ~10 % de las veces "se le olvida" llamarla. Lo que este comando instala son los archivos de reglas (`CLAUDE.md`, `.cursor/rules/nemo.mdc`, `.windsurfrules`, `.clinerules`, `.github/copilot-instructions.md`, `AGENTS.md`) que **fuerzan** al modelo a llamar `prime_context` antes de responderte y `create_correction` cuando lo corriges.
>
> Detalles de lo que hace en una sola corrida idempotente:
>
> - Crea o actualiza los 6 archivos de reglas. Si ya existían, hace **merge** sin duplicar (delimita su bloque con marcadores `<!-- BEGIN NEMO RULES vN -->`).
> - Re-ejecutar trae la versión nueva del bloque sin tocar nada más.
> - Añade `--with-hooks` para escribir *SessionStart* + *Stop* hooks en `~/.claude/settings.json` (con backup `.bak`). Los hooks llaman a NEMO automáticamente vía shell — el modelo no puede "olvidarse".
>
> > 🔁 **¿Cuándo lo vuelves a correr?** Solo cuando abras **otro proyecto nuevo** donde también quieras NEMO. NO necesitas re-correrlo por reboot del PC ni por sesión nueva de tu IA: los archivos de reglas viven en la carpeta del proyecto y persisten para siempre, y el servidor del paso 1 se auto-arranca con tu sistema (`restart: unless-stopped`). La excepción: re-correrlo en un proyecto existente cuando salga una versión nueva del template (el bloque pasa de `v1` a `v2` y se actualiza in-place sin tocar el resto del archivo).
>
> ---
>
> ### 4. ¿Cómo saber si NEMO ya está listo?
>
> Tres comprobaciones de menos de 30 segundos para confirmar que cada pieza está viva:
>
> **① Desde el navegador** (cualquier navegador, sin instalar nada):
>
> | Abre esta URL | Qué deberías ver | Si no se ve eso… |
> |---|---|---|
> | <http://localhost:8765/health> | JSON con `"status": "ok"` y un bloque por cada base SQLite (`conversations`, `ai_memories`, `schedule`, `vscode_project`, `mcp_tool_calls`) reportando `healthy` | El contenedor no arrancó. Revisa `docker compose logs nemo --tail 50`. |
> | <http://localhost:8765/openapi.json> | JSON grande con la spec OpenAPI de las ~34 tools | Si no responde, repite el paso 1 (`docker compose up -d`). Si responde pero la lista de tools está vacía, NEMO arrancó pero el core no inicializó — mira los logs. |
> | <http://localhost:8765/docs> | UI interactiva de Swagger donde puedes invocar tools desde el navegador (útil para probar `prime_context` o `search_memories` sin escribir código) | — |
>
> **② Desde la terminal**:
>
> ##### 🐧 Linux / macOS / WSL
>
> ```bash
> curl -s http://localhost:8765/health | grep -o '"status":"[^"]*"'
> # Esperado: "status":"ok"
>
> curl -s http://localhost:8765/api/tools | python3 -c "import json,sys; print('tools:', len(json.load(sys.stdin)['tools']))"
> # Esperado: tools: 34
> ```
>
> ##### 🪟 Windows (PowerShell)
>
> ```powershell
> (Invoke-RestMethod http://localhost:8765/health).status
> # Esperado: ok
>
> (Invoke-RestMethod http://localhost:8765/api/tools).tools.Count
> # Esperado: 34
> ```
>
> > 💡 `Invoke-RestMethod` parsea JSON automáticamente — más limpio que pipear a `python3` y no necesita Python instalado en el host.
>
> **③ Desde tu IA** (la prueba de fuego: que la IA *use* NEMO):
>
> En tu cliente AI ya configurado, pídele literalmente esto:
>
> > *"Llama la tool `prime_context` y dime qué memorias y recordatorios tienes. Si no tienes acceso a NEMO o falla, dímelo."*
>
> Tres resultados posibles:
>
> - ✅ **Funciona y devuelve algo** (puede estar vacío si es tu primera vez — eso también es señal de éxito).
> - ❌ **"No tengo acceso a esa tool"** → el cliente no está vinculado. Vuelve al **paso 2**.
> - ❌ **"NEMO no responde / connection refused"** → el servidor no está corriendo. Vuelve al **paso 1** y ejecuta `docker compose up -d`.
> - ❌ **`Unable to find image 'nemo:local'`** al correr el comando del paso 3 → la imagen no se ha construido todavía. Haz el **paso 1** primero (es el único momento donde se construye).
>
> Para una prueba más completa que ejercita el ciclo entero (escribir → reiniciar → leer):
>
> ##### 🐧 Linux / macOS / WSL
>
> ```bash
> # Crea una memoria
> curl -s -X POST http://localhost:8765/api/memory -H "Content-Type: application/json" -d '{"content":"smoke-test: NEMO está listo","memory_type":"fact","tags":["smoke"]}'
>
> # Reinicia el contenedor (simula apagar el ordenador)
> docker compose restart nemo && sleep 6
>
> # Búscala — debe aparecer
> curl -s -X POST http://localhost:8765/api/memory/search -H "Content-Type: application/json" -d '{"query":"smoke-test","limit":3}'
> ```
>
> ##### 🪟 Windows (PowerShell)
>
> ```powershell
> # Crea una memoria
> $body = '{"content":"smoke-test: NEMO está listo","memory_type":"fact","tags":["smoke"]}'
> Invoke-RestMethod -Method POST -Uri http://localhost:8765/api/memory -ContentType "application/json" -Body $body
>
> # Reinicia el contenedor (simula apagar el ordenador)
> docker compose restart nemo; Start-Sleep -Seconds 6
>
> # Búscala — debe aparecer
> $query = '{"query":"smoke-test","limit":3}'
> Invoke-RestMethod -Method POST -Uri http://localhost:8765/api/memory/search -ContentType "application/json" -Body $query
> ```
>
> > 💡 En PowerShell el JSON va en una variable (`$body`, `$query`) para esquivar las trampas de comillas anidadas. `Invoke-RestMethod` reemplaza `curl … -d …` y devuelve un objeto ya parseado.
>
> Si la búsqueda recupera la memoria después del `restart`, **la persistencia funciona** y el sistema completo está operativo.
>
> ---
>
> Detalles, perfiles GPU (Ollama orquestado por Docker Compose) y troubleshooting → [DOCKER.md](DOCKER.md).

---

## ⚡ Instalación clásica (Python local, sin Docker)

> Si prefieres no usar Docker o quieres iterar sobre el código directamente. Sin cuentas. Sin nube. Solo Python.

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

### Paso 3 — Configurar proveedores de embeddings (opcional pero recomendado)

NEMO funciona sin embeddings (fallback a búsqueda de texto), pero para el pipeline completo necesitas al menos un proveedor de embeddings.

<details open>
<summary><b>⭐ Opción A — LM Studio (recomendado, máximo rendimiento)</b></summary>

1. Descarga e instala [LM Studio](https://lmstudio.ai/)
2. Descarga el modelo `Qwen3-Embedding-4B` desde la interfaz de LM Studio
3. Cárgalo y verifica que el servidor esté en `http://localhost:1234`
4. **(Opcional) Reranker BGE** — para activar el pipeline completo:
   ```bash
   # Descarga el modelo GGUF de BGE-reranker-v2-m3
   # Inicia con llama-server (incluido con llama.cpp):
   llama-server -m bge-reranker-v2-m3-Q4_K_M.gguf --reranking --embedding --pooling rank --port 8080 --ctx-size 2048 --parallel 4
   ```
   Verifica: `curl http://localhost:8080/health` → `{"status":"ok"}`

NEMO detecta automáticamente LM Studio en `:1234` y el reranker en `:8080`.
</details>

<details>
<summary><b>🦙 Opción B — Ollama (ligero, sin GPU dedicada)</b></summary>

```bash
# Instala Ollama desde https://ollama.com
ollama pull nomic-embed-text
```

Edita `embedding_config.json` y establece Ollama como primario:
```json
{
  "embedding_configuration": {
    "primary": {
      "provider": "ollama",
      "model": "nomic-embed-text",
      "base_url": "http://localhost:11434"
    }
  }
}
```
</details>

<details>
<summary><b>☁️ Opción C — OpenAI (requiere API key)</b></summary>

Edita `embedding_config.json`:
```json
{
  "embedding_configuration": {
    "primary": {
      "provider": "openai",
      "model": "text-embedding-3-small",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-..."
    }
  }
}
```
</details>

### Paso 4 — Verificar que funciona

Reinicia tu editor. En Agent mode, pídele a la IA:

> *"Guarda en memoria que mi nombre es [tu nombre] y que trabajo con Python"*

Luego abre una sesión nueva y pregunta:

> *"¿Cómo me llamo?"*

**Si lo sabe — NEMO está funcionando ✓**

### Paso 5 — Ejecutar benchmark (opcional)

Verifica que tu instalación alcanza el rendimiento esperado:

```bash
python examples/benchmark_nemo_suite.py --preset quick
```

Resultados esperados con LM Studio + Reranker: Top-1 ≥ 91%, MRR ≥ 0.95, Confusory = 100%.

---

## 🆚 NEMO vs. otras soluciones

| | Otras soluciones | **NEMO** |
|---|---|---|
| **Búsqueda** | Similitud coseno simple | Pipeline de 11 fases: FTS5 + Dense + reranker BGE + fusión RWF adaptativa con gating léxico |
| **Precisión** | ~70–75% Top-1 (estimado) | **91.67% Top-1** · MRR 0.9583 · Recall@3 100% en producción |
| **Adversarial** | Sin protección contra imposters | 100% de rechazo en pruebas confusory · 6.25% de intercepción de imposters |
| **Benchmark** | Métricas internas no publicadas | Suite pública reproducible con 48 queries en 4 categorías · [ver comparativa](#competencia) |
| **Infraestructura** | Dependiente de la nube | 100% local — LM Studio + Ollama + SQLite, sin internet |
| **Costo** | $20–99+/mes (APIs + SaaS) | $0 — todo corre en tu máquina |
| **Rendimiento** | Recuperación uniforme | Bypass adaptativo por confianza: enruta al camino rápido o al pipeline completo según gap de scores |
| **Resiliencia** | Un solo proveedor | Circuit breaker con backoff exponencial · fallback Qwen3 → Ollama → texto · dimension guard |
| **Persistencia** | Olvida sesiones anteriores | 5 bases SQLite — sobrevive reinicios, cambios de agente y reinstalaciones |
| **Duplicados** | Memorias repetidas | Deduplicación semántica en escritura: duro 0.92 · suave 0.82 · L1 cache 0.97 |
| **Ranking** | Fijo | Bucle de retroalimentación `access_count` + boost permanente +0.35 para correcciones |
| **Privacidad** | Datos en APIs cloud | Total — nada sale de tu máquina |

---

## 🧠 Pipeline de Búsqueda Semántica

NEMO expone **42 herramientas MCP** a través de un servidor Python stdio. Cuando un agente llama `search_memories`, la consulta pasa por un **pipeline de recuperación de múltiples etapas**:

### Arquitectura del Pipeline <a id="arquitectura"></a>

```
  Consulta
    │
    ├─────────────────────────────────┐
    ▼                                 ▼
  Dense (Qwen3-4B)               FTS5 BM25
  similitud coseno               ranking léxico
    │                                 │
    └────────┬────────────────────────┘
             ▼
   Filtrado por umbral adaptativo
   floor=0.92 · ceiling=0.95
   median(cosenos) + 1.5·std
             │
             ▼
   Gap bypass router (threshold=0.12)
   ┌─── gap > 0.12 ──→ camino rápido (líder claro)
   │
   └─── gap ≤ 0.12 ──→ Reranker BGE-v2-m3
                         cross-encoder neuronal
                         15 candidatos → top 5
                              │
                              ▼
                    Fusión RWF (Reciprocal Weighted Fusion)
                    sem=0.55 / bge=0.45
                              │
                              ▼
                    Lexical Gating Adaptativo
                    ┌── gap base < 0.03: ceiling 0.10 (empate → tiebreaker)
                    ├── gap base > 0.10: ceiling 0.02 (líder claro → protección)
                    └── spread léxico < 0.03: cap 0.03 (ruido → suprimir)
                              │
                              ▼
                    Señales contextuales
                    token_coverage · fuzzy_coverage
                    phrase_boost · identifier_boost
                    tag_boost · correction_boost (+0.35)
                    decaimiento temporal · access_count
                              │
                              ▼
                    Deduplicación near-dup
                    Resultado final top-N
```

### Detalles Técnicos del Pipeline

| Componente | Parámetro | Valor |
|---|---|---|
| **Fusión RWF** | Peso semántico (`_W_SEM`) | `0.55` |
| | Peso BGE reranker (`_W_BGE`) | `0.45` |
| **Umbral adaptativo** | Floor / Ceiling | `0.92` / `0.95` |
| | Fórmula | `median(cosenos) + 1.5 × std(cosenos)` |
| **Gap bypass** | Umbral de confianza | `0.12` |
| **Lexical gating** | Ceiling máximo (empate) | `0.10` |
| | Ceiling mínimo (líder claro) | `0.02` |
| | Spread check | `< 0.03` → cap en `0.03` |
| **Reranker** | Candidatos primera etapa | `15` |
| | Resultado final | `top 5` |
| | Timeout | `20s` |
| | Confianza bypass | `0.92` |
| **Deduplicación** | Umbral duro (escritura) | `0.92` |
| | Umbral suave (consolidación) | `0.82` |
| | Cache de sesión L1 | `0.97` |
| **Correcciones** | Boost permanente de relevancia | `+0.35` |

### Benchmarks de Producción <a id="benchmarks"></a>

Resultados del benchmark suite completo v1.4.0 (`benchmark_nemo_suite.py`), ejecutado localmente con LM Studio (Qwen3-4B) + Reranker BGE-v2-m3 + Ollama fallback.

#### 📊 Resumen Ejecutivo

| Métrica | Baseline | Producción | Entropy |
|---|:---:|:---:|:---:|
| **Top-1 Accuracy** | 91.67% | 91.67% | 87.50% |
| **MRR** | 0.9444 | 0.9583 | 0.9035 |
| **Recall@3** | 97.22% | 100% | 93.75% |
| **Recall@5** | 97.22% | — | 95.83% |
| **Recall@10** | 97.22% | — | 95.83% |
| **Imposter Intercept** | — | 8.33% | 6.25% |
| **Avg Score Gap** | — | 0.18 | 0.12 |
| **Latencia P50** | 2 055 ms | 2 303 ms | 2 510 ms |
| **Latencia P95** | 2 558 ms | 2 722 ms | 3 182 ms |
| **Token avg/query** | — | 44.08 | — |

#### 🧪 Run 1 — Baseline (50 memorias · 36 queries)

Corpus de 50 memorias variadas, 36 queries en 3 categorías:

| Categoría | Top-1 | Queries |
|---|:---:|:---:|
| Clean | 86.67% | 15 |
| Paraphrase | 100% | 12 |
| Typo | 88.89% | 9 |
| **Agregado** | **91.67%** | **36** |

Recall@5 = 97.22% · MRR = 0.9444 · Avg store latency = 8.57 ms

#### 🏭 Run 2 — Producción (24 corpus · 24 queries · 5 checks)

Simula producción real con 12 memorias limpias + 12 imposters semánticamente cercanos:

| Check de calidad | Umbral | Resultado |
|---|---|:---:|
| Top-1 clean ≥ 90% | 90% | ✅ 91.67% |
| Top-1 confusory ≥ 75% | 75% | ✅ 91.67% |
| Imposter intercept ≤ 15% | 15% | ✅ 8.33% |
| Score gap avg ≥ 0.10 | 0.10 | ✅ 0.18 |
| P95 latency ≤ 4 000 ms | 4 000 ms | ✅ 2 722 ms |

**5/5 checks pasados.** Recall@3 = 100% · MRR = 0.9583 · Elapsed = 76.1 s

#### 🌪️ Run 3 — Entropy (120 corpus · 48 queries · 4 categorías adversariales)

El test más exigente. Corpus de 120 memorias con composición adversarial diseñada para confundir al sistema:

**Composición del corpus:**
| Tipo | Cantidad | Propósito |
|---|:---:|---|
| Anchors | 12 | Memorias correctas (ground truth) |
| Imposters | 12 | Semánticamente similares pero incorrectas |
| Distractors | 12 | Temas relacionados para crear ruido |
| Cross-topic | 12 | Memorias de otros dominios |
| Filler | 72 | Relleno para simular base de datos real |
| **Total** | **120** | **Ratio señal/ruido: 10%** |

**Resultados por categoría adversarial:**
| Categoría | Top-1 | Queries | Dificultad |
|---|:---:|:---:|---|
| Clean | 91.67% | 12 | Queries directas sin modificar |
| Confusory | **100%** | 12 | Queries diseñadas para engañar al ranking |
| Paraphrase extreme | 75.00% | 12 | Reformulaciones radicales (vocabulario distinto) |
| Typo severe | 83.33% | 12 | Errores ortográficos severos acumulados |
| **Agregado** | **87.50%** | **48** | — |

Top-1 adversarial (confusory) = **100%** · Imposter intercept = **6.25%** (3/48) · MRR = 0.9035

#### ⚡ Latencia End-to-End y Tokens

| Métrica | Valor |
|---|---|
| End-to-end mediana (retrieval + context assembly) | 2 124 ms |
| End-to-end P95 | 2 433 ms |
| Tokens promedio por query | 9.08 |
| Tokens promedio de contexto devuelto | 35 |
| Tokens totales por llamada | 44.08 |

#### 📈 Accuracy vs Context Size

| Límite de resultados | Top-1 | Tokens contexto avg | Tokens total avg | Latencia P95 |
|:---:|:---:|:---:|:---:|:---:|
| 1 | 91.67% | 35 | 44.08 | 2 433 ms |
| 5 | 91.67% | 181.75 | 190.83 | 1 116 ms |

> Top-1 se mantiene idéntico con 1 o 5 resultados: el pipeline identifica correctamente al líder en la primera posición.

---

### 🆚 Comparativa con Competencia <a id="competencia"></a>

Comparación detallada con las dos principales soluciones open source de memoria para IA: **Mem0** y **Zep**.

#### Métricas Directas

| Métrica | **NEMO v1.4.0** | **Mem0** | **Zep** |
|---|:---:|:---:|:---:|
| **Top-1 Accuracy** | **91.67%** | ~70–75%¹ | No publicado |
| **MRR** | **0.9583** | No publicado | No publicado |
| **Recall@5** | **97.22%** | No publicado | No publicado |
| **Adversarial (confusory)** | **100%** | No evaluado | No evaluado |
| **Imposter intercept** | **6.25%** | No evaluado | No evaluado |
| **Latencia P95** | 2 722 ms | ~150–300 ms² | ~100–200 ms³ |
| **Corpus de test** | 120 memorias | No divulgado | No divulgado |
| **Queries de test** | 48 (4 categorías) | Variable | Variable |
| **Ejecución** | 100% local | Cloud/hybrid | Cloud (SaaS) |
| **Costo** | $0 (gratis) | $0–$99+/mes | $0–$99+/mes |

<sub>¹ Estimado a partir del paper de Mem0 "MemoryRAG benchmark" que reporta ~26% sobre RAG estándar con accuracy base de ~55–60%. ² Mem0 usa APIs cloud con indexación vectorial serverless — la latencia baja es de red + cache, no de pipeline de búsqueda complejo. ³ Zep usa serverless PostgreSQL con pgvector — latencia refleja búsqueda vectorial simple sin reranking multi-etapa.</sub>

#### Arquitectura de Búsqueda

| Capacidad | **NEMO** | **Mem0** | **Zep** |
|---|:---:|:---:|:---:|
| Búsqueda densa (embeddings) | ✅ Qwen3-4B (2 560D) | ✅ OpenAI/custom | ✅ OpenAI |
| Búsqueda léxica (BM25/FTS5) | ✅ FTS5 en paralelo | ❌ | ❌ |
| Reranker cross-encoder | ✅ BGE-v2-m3 | ❌ | ❌ |
| Fusión multi-señal (RWF) | ✅ sem+bge+léxico | ❌ Cosine simple | ❌ Cosine simple |
| Gap bypass adaptativo | ✅ threshold 0.12 | ❌ | ❌ |
| Umbral adaptativo | ✅ [0.92–0.95] dinámico | ❌ Threshold fijo | ❌ Threshold fijo |
| Lexical gating | ✅ Condicional por confianza | ❌ | ❌ |
| Protección adversarial | ✅ Confusory + imposter | ❌ | ❌ |
| Deduplicación semántica | ✅ Duro 0.92 / suave 0.82 | ✅ Básica | ✅ Básica |

#### Infraestructura y Modelo de Despliegue

| Aspecto | **NEMO** | **Mem0** | **Zep** |
|---|---|---|---|
| **Despliegue** | 100% local (SQLite) | Cloud API / self-hosted | Cloud SaaS / self-hosted |
| **Base de datos** | 5 × SQLite + FTS5 | Qdrant / pgvector (cloud) | PostgreSQL + pgvector |
| **Embeddings** | Qwen3-4B local (LM Studio) | OpenAI API (cloud) | OpenAI API (cloud) |
| **Reranker** | BGE-v2-m3 local (llama.cpp) | No incluido | No incluido |
| **Privacidad** | Total — nada sale de tu máquina | Datos pasan por APIs cloud | Datos en infraestructura Zep |
| **Internet requerido** | No | Sí (APIs) | Sí (SaaS) |
| **Costo a 10K memorias** | $0 | ~$20–50/mes (API + hosting) | ~$25–99/mes (plan Pro) |
| **Protocolo** | MCP (stdio + HTTP) | REST API / SDK | REST API / SDK |
| **Resiliencia** | Circuit breaker + 3 fallbacks | Retry básico | Retry básico |

#### Metodología de Benchmark

| Aspecto | **NEMO** | **Mem0** | **Zep** |
|---|---|---|---|
| **Suite pública** | ✅ `benchmark_nemo_suite.py` incluido | ❌ Benchmark interno | ❌ Sin benchmark público |
| **Reproducible** | ✅ `--preset quick` en 2 min | No — requiere API keys | No — requiere cuenta SaaS |
| **Corpus controlado** | 120 memorias con composición conocida | No divulgado | No divulgado |
| **Test adversarial** | 4 categorías (clean, confusory, paraphrase, typo) | No evaluado | No evaluado |
| **Detección de imposters** | ✅ Métrica dedicada | No evaluado | No evaluado |
| **Métricas publicadas** | Top-1, MRR, Recall@k, P95, tokens, imposter, confusory | Accuracy general | Latencia general |

> **Nota sobre transparencia:** NEMO publica corpus, queries, métricas y código del benchmark. Los competidores no divulgan tamaño de corpus, composición adversarial ni métricas granulares, lo que dificulta una comparación directa exacta. Las cifras de Mem0 y Zep provienen de sus papers, blogs y documentación pública.

> **Suite de benchmarks incluido:** ejecuta `python examples/benchmark_nemo_suite.py --preset quick` para replicar.

---

## ✨ Características Principales

| Característica | Detalle |
|---|---|
| 🔍 **Búsqueda híbrida** | Dense (Qwen3-4B, instrucción asimétrica) + FTS5 BM25 léxico en paralelo + reranker BGE cross-encoder |
| 🧮 **Fusión RWF adaptativa** | Reciprocal Weighted Fusion (sem 0.55 / bge 0.45) + lexical gating condicional por confianza del ranking |
| 🛡️ **Protección adversarial** | Gap bypass 0.12 · umbral adaptativo [0.92–0.95] · spread check · 100% confusory rejection |
| 🛠️ **42 herramientas MCP** | Memoria · conversaciones · agenda · correcciones · reflexiones · salud · roleplay · proyectos · cognición avanzada |
| 🗄️ **5 bases de datos SQLite** | `conversations` · `ai_memories` · `schedule` · `mcp_tool_calls` · `vscode_project` |
| ⚡ **Circuit breaker** | Backoff exponencial: base 2s → max 45s · semáforo 2 concurrentes · HTTP timeout 10s/3s connect |
| 🔒 **Dimension guard** | Detecta y rechaza embeddings de fallback con dimensiones incompatibles (ej: 2560D vs 768D) |
| 🔁 **Deduplicación semántica** | Duro 0.92 · suave 0.82 · contradicción 0.70 · L1 cache de sesión 0.97 |
| ⏳ **Autoridad temporal** | Decaimiento temporal evita que memorias obsoletas aparezcan |
| ✏️ **Auto-correcciones** | `create_correction` da boost permanente +0.35 — los errores no se repiten |
| 📥 **Importación multiplataforma** | LM Studio · Ollama · OpenWebUI · SillyTavern · Gemini CLI · VS Code |
| 📅 **Agenda completa** | Calendario con recurrencia diaria / semanal / mensual / anual |
| 🌊 **Degradación elegante** | Cae a Ollama → búsqueda de texto si los embeddings no están disponibles · dimension guard previene crashes |
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

## 🛠️ 42 Herramientas MCP

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
│       ai_memory_mcp_server.py   (42 herramientas MCP)     │
│       HTTP API :11435  ·  SSE /events  ·  /api/graph      │
└───────────────────────────┬──────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────┐
│              ai_memory_core.py   (~7 100 líneas)          │
│  ┌───────────────────┐    ┌─────────────────────────────┐ │
│  │  EmbeddingService │    │      RerankingService        │ │
│  │  Qwen3-4B @ :1234 │    │  BGE-reranker-v2-m3 @ :8080  │ │
│  │  circuit-breaker  │    │  15 cand → top 5 · RWF       │ │
│  │  dim-guard · L1$  │    │  timeout 20s · bypass 0.92   │ │
│  │  fallback → Ollama│    │  lexical gating adaptativo   │ │
│  └───────────────────┘    └─────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────┐ │
│  │            PersistentAIMemorySystem                   │ │
│  │   FTS5+Dense paralelo · umbral adaptativo [0.92-0.95] │ │
│  │   gap bypass 0.12 · dedup 0.92/0.82 · near-dup       │ │
│  │   RWF sem=0.55 bge=0.45 · correction boost +0.35     │ │
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

NEMO soporta múltiples proveedores de embeddings, todos configurables en `embedding_config.json`. El sistema degrada graciosamente si el proveedor primario no está disponible, con **dimension guard** que previene crashes por mezcla de dimensiones.

| Proveedor | Modelo | Dimensiones | Rol | Costo |
|---|---|---|---|---|
| ⭐ **LM Studio** (primario) | Qwen3-Embedding-4B | 2 560D | Embeddings asimétricos con query instruction | Gratis |
| ⚙️ **llama_cpp** (reranker) | BGE-reranker-v2-m3-Q4_K_M | — | Cross-encoder neuronal en `/v1/rerank` | Gratis |
| 🦙 **Ollama** (respaldo) | nomic-embed-text | 768D | Fallback automático con circuit breaker | Gratis |
| ☁️ **OpenAI** (nube) | text-embedding-3-small | 1 536D | Alternativa en la nube | $$$ |

### Configuración de puertos

| Servicio | Puerto | Endpoint |
|---|---|---|
| LM Studio (embeddings) | `:1234` | `/v1/embeddings` |
| Ollama (fallback) | `:11434` | `/api/embeddings` |
| Reranker (llama_cpp) | `:8080` | `/v1/rerank` |
| NEMO HTTP API | `:11435` | `/api/health` · `/events` (SSE) · `/api/graph` |

### Circuit Breaker y Resiliencia

| Parámetro | Valor |
|---|---|
| HTTP timeout | `10s total` · `3s connect` |
| Cooldown base (tras 1er fallo) | `2s` |
| Cooldown máximo | `45s` |
| Semáforo concurrente | `2` requests simultáneos |
| Reranker retry | `60s` tras fallo |
| Dimension guard | Rechaza fallback con dim ≠ primario |
| L1 cache de sesión | Reutiliza embedding si coseno ≥ `0.97` |

---

## 🆕 Historial de versiones

<details open>
<summary><b>v1.4.0 (abril 2026) — Pipeline de búsqueda avanzado</b></summary>

- **Fusión RWF adaptativa** — Reciprocal Weighted Fusion de 2 señales (sem 0.55 + BGE 0.45) con lexical gating condicional
- **Lexical gating por confianza** — dos pases: mide el gap del ranking base, luego escala la señal léxica inversamente a la confianza. Spread check suprime ruido cuando el lexical no discrimina
- **Gap bypass router** — si el líder semántico tiene gap > 0.12, omite reranking costoso (camino rápido)
- **Umbral adaptativo** — `median + 1.5·std` clamped a [0.92, 0.95] en lugar de threshold fijo
- **Dimension guard** — previene crashes por mezcla de dimensiones cuando el fallback (768D) difiere del primario (2560D)
- **Circuit breaker mejorado** — backoff exponencial base 2s → max 45s, semáforo de 2 concurrentes
- **L1 session cache** — reutiliza embeddings intra-sesión si coseno ≥ 0.97
- **Benchmark suite** — `benchmark_nemo_suite.py` con 4 categorías: baseline, producción, entropy y confusory adversarial
- **Protección adversarial** — 100% confusory rejection, 6.25% imposter intercept, MRR 0.9583
- **Puerto HTTP** separado del servidor de embeddings: `:11435`
</details>

<details>
<summary><b>v1.3.0 (marzo 2026) — Dashboard y cognición</b></summary>

- **`synaptic_tagging`** — nueva herramienta MCP: conecta memorias relacionadas automáticamente (importancia ≥ 9)
- **Panel Neural 3D** — `dashboard.py` genera 3D interactivo (three.js + bloom glow + slider de similaridad)
- **Panel VS Code premium** — extensión `nemo-vscode` con UI oscuro-dorado, estado en tiempo real, botón de lanzamiento Dashboard 3D
- **Circuit Breaker** en `EmbeddingService` — timeout 10 s · semáforo 1 · cooldown 45 s — elimina freezes con LM Studio ocupado
- **Ícono de grafo neuronal** en la activity bar de VS Code
</details>

<details>
<summary><b>v1.2.0 — Búsqueda híbrida y embeddings asimétricos</b></summary>

- SQLite FTS5 (unicode61, sin diacríticos) para BM25 léxico en paralelo con dense
- Triggers automáticos mantienen el índice FTS5 sincronizado
- Reranker BGE apuntando a `llama_cpp :8080` con detección de falso-200
- Query instruction asimétrica para diferenciar vocabulario abstracto de técnico (+4.2pp Top-1)
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
| [LM Studio](https://lmstudio.ai/) | Hosting local de modelos de embeddings |
| [llama.cpp / llama-server](https://github.com/ggerganov/llama.cpp) | Servidor del reranker BGE en `:8080` con `/v1/rerank` |
| [Qwen3-Embedding-4B](https://huggingface.co/Qwen/Qwen3-Embedding) | Modelo de embeddings principal (2 560D, instrucción asimétrica) |
| [BGE-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) | Reranker neuronal cross-encoder (GGUF Q4_K_M) |
| [Ollama](https://ollama.com/) | Proveedor de embeddings de respaldo (nomic-embed-text, 768D) |
| [SQLite + FTS5](https://www.sqlite.org/) | Almacenamiento persistente + índice léxico BM25 |
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
