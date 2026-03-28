// build_ext.js — writes extension.js (premium UI)
const fs   = require('fs');
const path = require('path');

const OUT_SRC  = path.join(__dirname, 'extension.js');
const OUT_INST = path.join(process.env.USERPROFILE, '.vscode', 'extensions', 'nemo-memory-1.0.0', 'extension.js');

const JS = `// NEMO V1.0 — Neural Engine Memory Observer
// VS Code Extension — Premium dark-gold WebviewView

const vscode = require('vscode');
const http   = require('http');
const cp     = require('child_process');
const fs     = require('fs');
const path   = require('path');
const os     = require('os');

const POLL_MS      = 30_000;
const HTTP_TIMEOUT = 3_000;
const LM_URL       = 'http://localhost:1234/v1/models';
const RK_KW        = ['rerank', 'bge'];
const DB_PATH      = path.join(os.homedir(), '.ai_memory', 'ai_memories.db');
const CONV_DB_PATH = path.join(os.homedir(), '.ai_memory', 'conversations.db');

function checkLmStudio() {
    return new Promise((resolve) => {
        const chunks = [];
        const req = http.get(LM_URL, { timeout: HTTP_TIMEOUT }, (res) => {
            res.on('data', c => chunks.push(c));
            res.on('end', () => {
                try {
                    const data = JSON.parse(Buffer.concat(chunks).toString());
                    const ids  = (data.data || []).map(m => (m.id || '').toLowerCase());
                    resolve({ lmOk: res.statusCode < 500, rkOk: ids.some(id => RK_KW.some(kw => id.includes(kw))) });
                } catch (_) { resolve({ lmOk: true, rkOk: false }); }
            });
        });
        req.on('error',   () => resolve({ lmOk: false, rkOk: false }));
        req.on('timeout', () => { req.destroy(); resolve({ lmOk: false, rkOk: false }); });
        setTimeout(() => { try { req.destroy(); } catch (_) {} resolve({ lmOk: false, rkOk: false }); }, HTTP_TIMEOUT + 500);
    });
}

function getNemoCwd() {
    const folders = vscode.workspace.workspaceFolders;
    if (!folders || !folders.length) return null;
    const root = folders[0].uri.fsPath;
    const sub  = path.join(root, 'persistent-ai-memory');
    return fs.existsSync(path.join(sub, 'dashboard.py')) ? sub : root;
}

function getPython() {
    const folders = vscode.workspace.workspaceFolders;
    const root    = folders && folders.length ? folders[0].uri.fsPath : null;
    const candidates = root ? [
        path.join(path.dirname(root), '.venv', 'Scripts', 'python.exe'),
        path.join(root, '.venv', 'Scripts', 'python.exe'),
        path.join(root, '.venv', 'bin', 'python'),
    ] : [];
    for (const c of candidates) if (fs.existsSync(c)) return c;
    return 'python';
}

function spawnDashboard(noOpen) {
    const cwd    = getNemoCwd();
    const python = getPython();
    if (!cwd) { vscode.window.showErrorMessage('NEMO: No se encontro persistent-ai-memory.'); return; }
    const args = noOpen ? ['dashboard.py', '--no-open'] : ['dashboard.py'];
    cp.spawn(python, args, { cwd, detached: true, stdio: 'ignore' }).unref();
}

const CSS = \`
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{height:100%;background:#141210}
body{
  min-height:100%;padding-bottom:20px;
  background:
    radial-gradient(ellipse 80% 40% at 15% 0%, rgba(58,34,8,.85) 0%, transparent 100%),
    radial-gradient(ellipse 60% 50% at 85% 100%, rgba(26,18,8,.9) 0%, transparent 100%),
    #141210;
  color:#f0ece4;
  font-family:var(--vscode-font-family,'Segoe UI',system-ui,sans-serif);
  font-size:12px;user-select:none;
}
::-webkit-scrollbar{width:3px}
::-webkit-scrollbar-thumb{background:rgba(212,175,100,.18);border-radius:2px}

.wrap{padding:14px 12px;display:flex;flex-direction:column;gap:12px}

/* hero */
.hero{
  padding:16px 14px 44px;border-radius:14px;position:relative;overflow:hidden;
  background:linear-gradient(145deg,rgba(212,175,100,.1) 0%,rgba(140,90,20,.05) 60%,rgba(60,30,5,.08) 100%);
  border:1px solid rgba(212,175,100,.16);
}
.hero::after{
  content:'';position:absolute;
  top:-40px;right:-40px;width:140px;height:140px;border-radius:50%;
  background:radial-gradient(circle,rgba(212,175,100,.1) 0%,transparent 65%);
  pointer-events:none;
}
.hero-eyebrow{font-size:8.5px;letter-spacing:3.5px;text-transform:uppercase;color:rgba(212,175,100,.5);margin-bottom:5px}
.hero-title{
  font-size:26px;font-weight:900;letter-spacing:.5px;line-height:1;
  background:linear-gradient(100deg,#c8a040 0%,#f5d78e 45%,#b8902c 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.hero-sub{font-size:9.5px;color:rgba(240,236,228,.35);margin-top:5px;letter-spacing:.4px}

/* orb */
.hero-orb{
  position:absolute;bottom:10px;right:12px;
  width:40px;height:40px;border-radius:50%;
  background:conic-gradient(from 0deg,#c8a040,#7a5510,#f5d78e,#c8a040);
  animation:spin 10s linear infinite;
  box-shadow:0 0 22px rgba(212,175,100,.28);
}
.hero-orb-inner{
  position:absolute;inset:3px;border-radius:50%;
  background:#1c1509;
  display:flex;align-items:center;justify-content:center;
  font-size:17px;
}
@keyframes spin{to{transform:rotate(360deg)}}

/* status strip */
.strip{
  display:flex;align-items:center;justify-content:space-between;
  padding:7px 11px;border-radius:9px;
  border:1px solid rgba(212,175,100,.1);
  background:rgba(255,255,255,.025);
}
.strip-left{display:flex;align-items:center;gap:7px;font-size:10px;font-weight:600}
.pulse{
  width:6px;height:6px;border-radius:50%;flex-shrink:0;
  animation:glow 2.5s ease-in-out infinite;
}
@keyframes glow{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(.8)}}
.strip-ts{font-size:9px;color:rgba(240,236,228,.22)}

/* section label */
.lbl{font-size:8px;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:rgba(212,175,100,.38);padding:0 1px}

/* service rows */
.rows{display:flex;flex-direction:column;border-radius:11px;overflow:hidden;border:1px solid rgba(255,255,255,.05)}
.row{
  display:flex;align-items:center;gap:9px;padding:8px 11px;
  background:rgba(255,255,255,.02);
  border-bottom:1px solid rgba(255,255,255,.04);
  transition:background .15s;
}
.row:last-child{border-bottom:none}
.row:hover{background:rgba(212,175,100,.05)}
.r-icon{font-size:13px;width:20px;text-align:center;flex-shrink:0;opacity:.6}
.r-body{flex:1;min-width:0;display:flex;flex-direction:column;gap:1px}
.r-name{font-size:11px;font-weight:600;color:#f0ece4}
.r-detail{font-size:9px;color:rgba(240,236,228,.28);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.badge{font-size:8.5px;font-weight:700;letter-spacing:.4px;padding:2px 7px;border-radius:20px;flex-shrink:0;border:1px solid}

/* divider */
.sep{border:none;border-top:1px solid rgba(212,175,100,.07)}

/* buttons */
.btn-gold{
  display:flex;align-items:center;justify-content:center;gap:8px;
  width:100%;padding:12px 14px;border:none;border-radius:12px;cursor:pointer;
  font-size:12px;font-weight:700;letter-spacing:.7px;
  background:linear-gradient(130deg,#c8a040 0%,#f5d78e 52%,#b8902c 100%);
  color:#1a1208;
  box-shadow:0 4px 18px rgba(212,175,100,.22),0 1px 0 rgba(255,255,255,.15) inset;
  transition:opacity .15s,transform .1s;
}
.btn-gold:hover{opacity:.88;box-shadow:0 6px 26px rgba(212,175,100,.35)}
.btn-gold:active{transform:scale(.98);opacity:.78}

.btn-ghost{
  display:flex;align-items:center;justify-content:center;gap:6px;
  width:100%;padding:9px 14px;
  border:1px solid rgba(212,175,100,.18);border-radius:12px;cursor:pointer;
  font-size:11px;font-weight:600;letter-spacing:.3px;
  background:rgba(212,175,100,.04);
  color:rgba(240,236,228,.65);
  transition:all .15s;
}
.btn-ghost:hover{background:rgba(212,175,100,.1);border-color:rgba(212,175,100,.32);color:#f0ece4}
.btn-ghost:active{background:rgba(212,175,100,.16)}

.btn-row{display:flex;gap:7px}
.btn-row .btn-ghost{flex:1}
\`;

function buildHtml(state) {
    const { lmOk, rkOk, memOk, convOk, ts } = state;
    const allOk = lmOk && memOk;

    function dot(ok, isWarn) {
        if (ok)     return '#9cdb5f';
        if (isWarn) return '#f7b731';
        return '#ff5e57';
    }
    function lbl(ok, isWarn) {
        if (ok)     return 'Activo';
        if (isWarn) return 'Aviso';
        return 'Offline';
    }

    const sysColor = allOk ? '#9cdb5f' : '#f7b731';

    const services = [
        { icon: '◈', name: 'LM Studio',     detail: lmOk  ? ':1234  online'       : ':1234  offline',     ok: lmOk,   warn: false },
        { icon: '◎', name: 'Reranker',      detail: rkOk  ? 'BGE cargado'         : 'No detectado',      ok: rkOk,   warn: !rkOk },
        { icon: '▣', name: 'ai_memories',   detail: memOk ? 'ai_memories.db ✓'    : 'No encontrada',     ok: memOk,  warn: false },
        { icon: '▤', name: 'conversations', detail: convOk? 'conversations.db ✓'  : 'No encontrada',     ok: convOk, warn: false },
        { icon: '⬡', name: 'nemo MCP',      detail: 'ai_memory_mcp_server.py',                           ok: true,   warn: false },
    ];

    const rowsHtml = services.map(s => {
        const c = dot(s.ok, s.warn);
        const t = lbl(s.ok, s.warn);
        return \`<div class="row">
  <span class="r-icon">\${s.icon}</span>
  <div class="r-body">
    <span class="r-name">\${s.name}</span>
    <span class="r-detail">\${s.detail}</span>
  </div>
  <span class="badge" style="color:\${c};border-color:\${c}30;background:\${c}12">\${t}</span>
</div>\`;
    }).join('');

    return \`<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';">
<style>\${CSS}</style>
</head>
<body>
<div class="wrap">

<div class="hero">
  <div class="hero-eyebrow">Neural Engine Memory</div>
  <div class="hero-title">NEMO</div>
  <div class="hero-sub">Memory Observer · V1.0</div>
  <div class="hero-orb"><div class="hero-orb-inner">🧠</div></div>
</div>

<div class="strip">
  <div class="strip-left">
    <span class="pulse" style="background:\${sysColor};box-shadow:0 0 8px \${sysColor}"></span>
    <span style="color:\${sysColor}">\${allOk ? 'Sistema nominal' : 'Requiere atención'}</span>
  </div>
  <span class="strip-ts">\${ts}</span>
</div>

<div class="lbl">Servicios</div>
<div class="rows">\${rowsHtml}</div>

<hr class="sep">

<div class="lbl">Dashboard Neural 3D</div>
<button class="btn-gold" onclick="post('launch')">⬡ &nbsp;Lanzar Dashboard 3D</button>
<div class="btn-row" style="margin-top:8px">
  <button class="btn-ghost" onclick="post('regenerate')">🔄 Regenerar</button>
  <button class="btn-ghost" onclick="post('refresh')">↻ Actualizar</button>
</div>

</div>
<script>const vscode=acquireVsCodeApi();function post(c){vscode.postMessage({command:c})}</script>
</body></html>\`;
}

const NEMO_VIEW_TYPE = 'nemo.statusView';

class NemoViewProvider {
    constructor() { this._view = null; this._timer = null; this._state = { lmOk:false, rkOk:false, memOk:false, convOk:false, ts:'—' }; }
    resolveWebviewView(webviewView) {
        this._view = webviewView;
        webviewView.webview.options = { enableScripts: true };
        webviewView.webview.html = buildHtml(this._state);
        webviewView.webview.onDidReceiveMessage(msg => {
            if (msg.command === 'launch')     { spawnDashboard(false); vscode.window.showInformationMessage('NEMO: Dashboard 3D abierto.'); }
            if (msg.command === 'regenerate') { spawnDashboard(true);  vscode.window.showInformationMessage('NEMO: dashboard.html regenerado.'); }
            if (msg.command === 'refresh')    { this.poll(); }
        });
        this.poll();
        this._timer = setInterval(() => this.poll(), POLL_MS);
    }
    async poll() {
        const [{ lmOk, rkOk }, memOk, convOk] = await Promise.all([
            checkLmStudio(),
            Promise.resolve(fs.existsSync(DB_PATH)),
            Promise.resolve(fs.existsSync(CONV_DB_PATH)),
        ]);
        this._state = { lmOk, rkOk, memOk, convOk, ts: new Date().toLocaleTimeString('es-ES') };
        if (this._view) this._view.webview.html = buildHtml(this._state);
    }
    dispose() { if (this._timer) clearInterval(this._timer); }
}

function activate(context) {
    const provider = new NemoViewProvider();
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(NEMO_VIEW_TYPE, provider),
        vscode.commands.registerCommand('nemo.refresh',             () => provider.poll()),
        vscode.commands.registerCommand('nemo.launchDashboard',     () => { spawnDashboard(false); vscode.window.showInformationMessage('NEMO: Dashboard 3D abierto.'); }),
        vscode.commands.registerCommand('nemo.regenerateDashboard', () => { spawnDashboard(true);  vscode.window.showInformationMessage('NEMO: dashboard.html regenerado.'); })
    );
    vscode.window.setStatusBarMessage('$(graph) NEMO V1.0 activo', 4000);
}

function deactivate() {}
module.exports = { activate, deactivate };
`;

fs.writeFileSync(OUT_SRC,  JS, 'utf8');
fs.writeFileSync(OUT_INST, JS, 'utf8');
console.log('OK — lines:', JS.split('\n').length);
