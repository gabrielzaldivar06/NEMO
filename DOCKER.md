# NEMO en Docker — instalación opcional

> Para la instalación recomendada ver [README.md](README.md#-instalación-clásica-python-local-sin-docker--recomendado).

Docker es una alternativa para quien prefiere no gestionar Python/venvs. El contenedor corre el servidor MCP por stdio — sin HTTP, sin FastAPI, sin docker compose. El cliente AI lo invoca directamente como si fuera un proceso local.

La calidad de embeddings depende de LM Studio u Ollama instalados en tu máquina, igual que en la instalación tradicional.

---

## Construir la imagen

```bash
git clone https://github.com/gabrielzaldivar06/NEMO.git
cd NEMO
docker build -f docker/Dockerfile -t nemo:local .
```

La imagen incluye fastembed como fallback. Si tienes LM Studio u Ollama corriendo en el host, NEMO los detecta automáticamente.

---

## Conectar cada cliente AI

El cliente ejecuta el contenedor por stdio. No hay servidor persistente ni puerto HTTP.

### Claude Code
```bash
claude mcp add nemo docker run -i --rm -v nemo-data:/app/.ai_memory -v nemo-models:/models nemo:local
```

### Claude Desktop — `claude_desktop_config.json`
```json
{
  "mcpServers": {
    "nemo": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-v", "nemo-data:/app/.ai_memory", "-v", "nemo-models:/models", "nemo:local"]
    }
  }
}
```

### VS Code Copilot — `~/.config/Code/User/mcp.json`
```json
{
  "servers": {
    "nemo": {
      "type": "stdio",
      "command": "docker",
      "args": ["run", "-i", "--rm", "-v", "nemo-data:/app/.ai_memory", "-v", "nemo-models:/models", "nemo:local"]
    }
  }
}
```

### Cursor / Windsurf
Usa `command: docker` con los mismos args en su config MCP stdio.

---

## Activar NEMO en cada proyecto

Conectar el cliente AI a NEMO es solo la mitad del trabajo. La IA también necesita **instrucciones explícitas** para que llame a NEMO en cada sesión — de lo contrario simplemente no lo usa.

`nemo-attach` escribe esas instrucciones en los archivos de reglas de cada cliente (CLAUDE.md, .cursor/rules/nemo.mdc, AGENTS.md, etc.). Corre una vez por proyecto; después el cliente las lee automáticamente en cada sesión.

```bash
# 🐧 Linux / macOS / WSL  (corre en la raíz del proyecto)
docker run --rm -it -v "$PWD":/workdir nemo:local nemo-attach

# 🪟 Windows (PowerShell)
docker run --rm -it -v "${PWD}:/workdir" nemo:local nemo-attach
```

El script muestra un menú interactivo y pregunta qué clientes usas. Si prefieres saltarte el menú:

```bash
# Configurar solo Claude Code
docker run --rm -v "$PWD":/workdir nemo:local nemo-attach --clients claude

# Configurar todos los clientes de una vez
docker run --rm -v "$PWD":/workdir nemo:local nemo-attach --clients all
```

> Sin este paso la IA tiene acceso a las herramientas NEMO pero no sabe que debe usarlas — opera sin memoria persistente.

---

## Persistencia

Los datos viven en volúmenes Docker nombrados:

| Volumen | Contenido |
|---|---|
| `nemo-data` | Bases SQLite (`ai_memories.db`, `conversations.db`, etc.) |
| `nemo-models` | Pesos de fastembed cacheados |

Sobreviven a reinicios y actualizaciones de imagen. Para borrar todo:
```bash
docker volume rm nemo-data nemo-models
```

---

## Actualizar

```bash
git pull
docker build -f docker/Dockerfile -t nemo:local .
```

No hay contenedor corriendo que reiniciar — el cliente levanta el contenedor en cada sesión.

---

## Comandos útiles

Con el enfoque stdio (`--rm`), el contenedor existe solo mientras el cliente AI está conectado. No hay un proceso persistente que arrancar o parar manualmente. Estos son los comandos relevantes:

### Imagen

```bash
# Verificar que la imagen existe
docker images nemo:local

# Reconstruir tras un git pull
docker build -f docker/Dockerfile -t nemo:local .

# Eliminar la imagen (para reconstruir desde cero)
docker rmi nemo:local
```

### Sesiones activas

```bash
# Ver si hay una sesión de NEMO activa ahora mismo (cliente AI conectado)
docker ps --filter ancestor=nemo:local

# Ver logs de la sesión activa
docker logs $(docker ps -q --filter ancestor=nemo:local)
```

> `docker start` y `docker stop` no aplican aquí — el contenedor se crea y destruye automáticamente en cada sesión (`--rm`). Si ves el contenedor en `docker ps` significa que tu cliente AI está conectado en este momento.

### Volúmenes y datos

```bash
# Ver que los volúmenes existen
docker volume ls | grep nemo

# Inspeccionar qué hay en las bases de datos
docker run --rm -v nemo-data:/data alpine ls /data

# Borrar todos los datos de NEMO (irreversible)
docker volume rm nemo-data nemo-models
```

### Depuración

```bash
# Probar NEMO manualmente en modo interactivo (sin cliente AI)
docker run -it --rm \
  -v nemo-data:/app/.ai_memory \
  -v nemo-models:/models \
  nemo:local \
  python -c "from ai_memory_core import PersistentAIMemorySystem; print('OK')"

# Abrir shell dentro del contenedor
docker run -it --rm \
  -v nemo-data:/app/.ai_memory \
  -v nemo-models:/models \
  nemo:local \
  bash
```
