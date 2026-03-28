const vscode = require('vscode');
const cp     = require('child_process');
const path   = require('path');
const fs     = require('fs');

// ── Helpers ────────────────────────────────────────────────────────────────

function getWorkspaceRoot() {
  const folders = vscode.workspace.workspaceFolders;
  return folders && folders.length > 0 ? folders[0].uri.fsPath : null;
}

function getNemoCwd() {
  const root = getWorkspaceRoot();
  if (!root) return null;
  // Support both single-root (repo itself) and multi-root workspaces
  const candidate = path.join(root, 'persistent-ai-memory');
  return fs.existsSync(path.join(candidate, 'dashboard.py')) ? candidate : root;
}

function getPython() {
  // Prefer the workspace venv if present
  const root = getWorkspaceRoot();
  const candidates = root ? [
    path.join(path.dirname(root), '.venv', 'Scripts', 'python.exe'),
    path.join(root, '.venv', 'Scripts', 'python.exe'),
    path.join(root, '.venv', 'bin', 'python'),
  ] : [];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return 'python'; // fallback
}

function spawnDashboard(noOpen) {
  const cwd  = getNemoCwd();
  const python = getPython();
  if (!cwd) {
    vscode.window.showErrorMessage('NEMO: Cannot locate persistent-ai-memory folder.');
    return null;
  }
  const args = ['dashboard.py'];
  if (noOpen) args.push('--no-open');
  const proc = cp.spawn(python, args, {
    cwd,
    detached: true,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
  });
  proc.unref();
  return proc;
}

// ── WebviewView provider ────────────────────────────────────────────────────

class NemoPanelProvider {
  static viewType = 'nemo.sidePanel';

  constructor(extensionUri) {
    this._extensionUri = extensionUri;
    this._view = null;
    this._status = 'idle';  // idle | running | error
    this._lastOutput = '';
  }

  resolveWebviewView(webviewView) {
    this._view = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.html = this._buildHtml('idle', '');

    webviewView.webview.onDidReceiveMessage(msg => {
      switch (msg.command) {
        case 'launch':      this._doLaunch(false); break;
        case 'regenerate':  this._doLaunch(true);  break;
        case 'openHtml':    this._openHtmlInBrowser(); break;
      }
    });
  }

  _doLaunch(noOpen) {
    this._setStatus('running', noOpen ? 'Regenerating…' : 'Launching…');
    const proc = spawnDashboard(noOpen);
    if (!proc) { this._setStatus('error', 'Python not found'); return; }

    let out = '';
    proc.stdout && proc.stdout.on('data', d => { out += d.toString(); });
    proc.stderr && proc.stderr.on('data', d => { out += d.toString(); });
    proc.on('close', code => {
      if (code === 0) {
        this._setStatus('idle', out.trim().split('\n').pop() || 'Done');
        if (!noOpen) vscode.window.showInformationMessage('NEMO 3D Dashboard opened in browser.');
      } else {
        this._setStatus('error', out.trim().split('\n').pop() || `Exit ${code}`);
        vscode.window.showErrorMessage('NEMO Dashboard error — check output.');
      }
    });
  }

  _openHtmlInBrowser() {
    const cwd = getNemoCwd();
    if (!cwd) return;
    const htmlPath = path.join(cwd, 'dashboard.html');
    if (!fs.existsSync(htmlPath)) {
      vscode.window.showWarningMessage('dashboard.html not found — generate it first.');
      return;
    }
    vscode.env.openExternal(vscode.Uri.file(htmlPath));
  }

  _setStatus(status, msg) {
    this._status = status;
    this._lastOutput = msg || '';
    if (this._view) {
      this._view.webview.html = this._buildHtml(status, this._lastOutput);
    }
  }

  // ── HTML ──────────────────────────────────────────────────────────────────

  _buildHtml(status, output) {
    const statusColor = { idle: '#06d6a0', running: '#ff9f1c', error: '#ff4757' }[status] || '#6a80a7';
    const statusLabel = { idle: 'ready', running: 'working…', error: 'error' }[status] || status;
    const spinStyle   = status === 'running' ? 'animation:spin 1s linear infinite;' : '';

    return /* html */`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: var(--vscode-font-family, 'Segoe UI', system-ui, sans-serif);
    font-size: 12px;
    color: var(--vscode-foreground);
    background: var(--vscode-sideBar-background);
    padding: 12px 10px;
    user-select: none;
  }

  /* ── Header ── */
  .header {
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 16px;
  }
  .logo-ring {
    width: 32px; height: 32px; border-radius: 50%;
    background: radial-gradient(circle at 40% 35%, #06d6a0 0%, #00b4d8 45%, #a855f7 100%);
    display: flex; align-items: center; justify-content: center;
    font-size: 16px; line-height: 1;
    box-shadow: 0 0 10px rgba(0,180,216,0.5);
    flex-shrink: 0;
    ${spinStyle}
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .title-block { flex: 1; }
  .title { font-size: 13px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase;
    color: var(--vscode-foreground); }
  .subtitle { font-size: 10px; color: var(--vscode-descriptionForeground); letter-spacing: 0.3px; }

  /* ── Status pill ── */
  .status-pill {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 3px 9px; border-radius: 20px;
    font-size: 10px; letter-spacing: 0.4px; font-weight: 600;
    background: rgba(0,0,0,0.25);
    border: 1px solid ${statusColor}44;
    color: ${statusColor};
    margin-bottom: 14px;
  }
  .status-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: ${statusColor};
    box-shadow: 0 0 5px ${statusColor};
  }

  /* ── Buttons ── */
  .btn-primary {
    display: flex; align-items: center; justify-content: center; gap: 8px;
    width: 100%; padding: 10px 12px; margin-bottom: 8px;
    border: none; border-radius: 6px; cursor: pointer;
    font-size: 12px; font-weight: 700; letter-spacing: 0.5px;
    background: linear-gradient(135deg, #00b4d8, #06d6a0);
    color: #03050d;
    transition: opacity 0.15s, transform 0.1s;
  }
  .btn-primary:hover  { opacity: 0.90; }
  .btn-primary:active { transform: scale(0.98); }
  .btn-primary:disabled { opacity: 0.4; cursor: default; }

  .btn-secondary {
    display: flex; align-items: center; justify-content: center; gap: 6px;
    width: 100%; padding: 7px 12px; margin-bottom: 8px;
    border: 1px solid var(--vscode-button-border, rgba(0,180,216,0.3));
    border-radius: 6px; cursor: pointer;
    font-size: 11px;
    background: rgba(0,180,216,0.08);
    color: var(--vscode-foreground);
    transition: background 0.15s;
  }
  .btn-secondary:hover  { background: rgba(0,180,216,0.18); }
  .btn-secondary:active { background: rgba(0,180,216,0.28); }

  /* ── Divider ── */
  .divider {
    border: none; border-top: 1px solid var(--vscode-sideBarSectionHeader-border, rgba(255,255,255,0.06));
    margin: 14px 0;
  }

  /* ── Output log ── */
  .log {
    font-size: 10px; line-height: 1.5;
    color: var(--vscode-descriptionForeground);
    background: rgba(0,0,0,0.2);
    border-radius: 4px; padding: 7px 9px;
    word-break: break-all; white-space: pre-wrap;
    min-height: 32px;
  }

  /* ── Info rows ── */
  .info-row {
    display: flex; justify-content: space-between; align-items: center;
    font-size: 10px; color: var(--vscode-descriptionForeground);
    margin-bottom: 5px;
  }
  .info-row span:last-child { color: var(--vscode-foreground); font-weight: 600; }

  /* ── Section header ── */
  .section-hdr {
    font-size: 9px; font-weight: 700; letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--vscode-descriptionForeground);
    margin-bottom: 8px;
  }
</style>
</head>
<body>

<div class="header">
  <div class="logo-ring">&#x1F9E0;</div>
  <div class="title-block">
    <div class="title">NEMO</div>
    <div class="subtitle">Neural Memory System</div>
  </div>
</div>

<div class="status-pill">
  <span class="status-dot"></span>
  ${statusLabel}
</div>

<p class="section-hdr">3D Neural Dashboard</p>

<button class="btn-primary" ${status === 'running' ? 'disabled' : ''} onclick="send('launch')">
  &#x1F9E0; Launch 3D Dashboard
</button>

<button class="btn-secondary" ${status === 'running' ? 'disabled' : ''} onclick="send('regenerate')">
  &#x1F504; Regenerate HTML only
</button>

<button class="btn-secondary" onclick="send('openHtml')">
  &#x1F4C4; Open last dashboard.html
</button>

<hr class="divider">

<p class="section-hdr">Output</p>
<div class="log">${escHtml(output || '—')}</div>

<script>
  const vscode = acquireVsCodeApi();
  function send(command) { vscode.postMessage({ command }); }
</script>
</body>
</html>`;
  }
}

// naive HTML escape for output text
function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// ── Activation ──────────────────────────────────────────────────────────────

function activate(context) {
  const provider = new NemoPanelProvider(context.extensionUri);

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(NemoPanelProvider.viewType, provider)
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('nemo.launchDashboard', () => {
      provider._doLaunch(false);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('nemo.regenerateDashboard', () => {
      provider._doLaunch(true);
    })
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
