// NEMO V1.0 — Neural Engine Memory Observer
// VS Code Extension — sidebar status panel

const vscode = require('vscode');
const http   = require('http');
const fs     = require('fs');
const path   = require('path');
const os     = require('os');

const POLL_MS       = 30_000;
const HTTP_TIMEOUT  = 3_000;
const LM_URL        = 'http://localhost:1234/v1/models';
const RK_MODEL_KW   = ['rerank', 'bge'];   // keywords to detect reranker in model list
const DB_PATH       = path.join(os.homedir(), '.ai_memory', 'ai_memories.db');
const CONV_DB_PATH  = path.join(os.homedir(), '.ai_memory', 'conversations.db');

// ── HTTP helper ────────────────────────────────────────────────────────────────
function checkHttp(url) {
    return new Promise((resolve) => {
        const req = http.get(url, { timeout: HTTP_TIMEOUT }, (res) => {
            res.resume();
            resolve(res.statusCode >= 200 && res.statusCode < 500);
        });
        req.on('error',   () => resolve(false));
        req.on('timeout', () => { req.destroy(); resolve(false); });
        setTimeout(() => { try { req.destroy(); } catch (_) {} resolve(false); }, HTTP_TIMEOUT + 500);
    });
}

// Returns {ok, loaded} — ok=LM Studio up, loaded=reranker model detected
function checkLmStudioModels() {
    return new Promise((resolve) => {
        const chunks = [];
        const req = http.get(LM_URL, { timeout: HTTP_TIMEOUT }, (res) => {
            res.on('data', c => chunks.push(c));
            res.on('end', () => {
                try {
                    const data = JSON.parse(Buffer.concat(chunks).toString());
                    const ids  = (data.data || []).map(m => (m.id || '').toLowerCase());
                    const lmOk = res.statusCode >= 200 && res.statusCode < 500;
                    const rkOk = ids.some(id => RK_MODEL_KW.some(kw => id.includes(kw)));
                    resolve({ lmOk, rkOk });
                } catch (_) { resolve({ lmOk: true, rkOk: false }); }
            });
        });
        req.on('error',   () => resolve({ lmOk: false, rkOk: false }));
        req.on('timeout', () => { req.destroy(); resolve({ lmOk: false, rkOk: false }); });
        setTimeout(() => { try { req.destroy(); } catch (_) {} resolve({ lmOk: false, rkOk: false }); }, HTTP_TIMEOUT + 500);
    });
}

// ── TreeItem factory ───────────────────────────────────────────────────────────
function makeItem(label, detail, state) {
    const item = new vscode.TreeItem(`${label}`, vscode.TreeItemCollapsibleState.None);
    item.description = detail;
    switch (state) {
        case 'ok':
            item.iconPath = new vscode.ThemeIcon('check', new vscode.ThemeColor('testing.iconPassed'));
            item.tooltip  = `${label}: OK`;
            break;
        case 'warn':
            item.iconPath = new vscode.ThemeIcon('warning', new vscode.ThemeColor('editorWarning.foreground'));
            item.tooltip  = `${label}: advertencia`;
            break;
        default:
            item.iconPath = new vscode.ThemeIcon('error', new vscode.ThemeColor('testing.iconFailed'));
            item.tooltip  = `${label}: sin conexión`;
    }
    return item;
}

// ── Section separator ──────────────────────────────────────────────────────────
function makeSection(label) {
    const item = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.None);
    item.description = '';
    item.iconPath    = new vscode.ThemeIcon('dash');
    return item;
}

// ── Tree Data Provider ─────────────────────────────────────────────────────────
class NemoProvider {
    constructor() {
        this._onChange = new vscode.EventEmitter();
        this.onDidChangeTreeData = this._onChange.event;
        this._items  = [];
        this._status = 'loading';
        this._timer  = null;
        this._start();
    }

    _start() {
        this._poll();
        this._timer = setInterval(() => this._poll(), POLL_MS);
    }

    async _poll() {
        const [{ lmOk, rkOk }, memOk, convOk] = await Promise.all([
            checkLmStudioModels(),
            Promise.resolve(fs.existsSync(DB_PATH)),
            Promise.resolve(fs.existsSync(CONV_DB_PATH)),
        ]);

        const allOk  = lmOk && memOk;
        this._status = allOk ? 'ok' : 'error';

        this._items = [
            makeSection('— Servicios IA'),
            makeItem('LM Studio',  lmOk ? 'Activo · :1234' : 'Offline · :1234',           lmOk ? 'ok' : 'error'),
            makeItem('Reranker',   rkOk ? 'BGE-reranker · :1234' : 'No cargado — run start_reranker.bat', rkOk ? 'ok' : 'warn'),
            makeSection('— Base de Datos'),
            makeItem('ai_memories',    memOk  ? 'ai_memories.db ✓'   : 'No encontrada', memOk  ? 'ok' : 'warn'),
            makeItem('conversations',  convOk ? 'conversations.db ✓' : 'No encontrada', convOk ? 'ok' : 'warn'),
            makeSection('— MCP Server'),
            makeItem('nemo MCP', 'ai_memory_mcp_server.py', 'ok'),
        ];

        this._onChange.fire();
    }

    getTreeItem(element) { return element; }
    getChildren()        { return this._items; }

    dispose() {
        if (this._timer) clearInterval(this._timer);
        this._onChange.dispose();
    }
}

// ── Activation ─────────────────────────────────────────────────────────────────
function activate(context) {
    const provider = new NemoProvider();

    const treeView = vscode.window.createTreeView('nemo.statusView', {
        treeDataProvider: provider,
        showCollapseAll:  false,
    });

    treeView.title = 'NEMO V1.0';
    treeView.description = 'Neural Engine Memory Observer';

    const refreshCmd = vscode.commands.registerCommand('nemo.refresh', () => {
        provider._poll();
    });

    context.subscriptions.push(treeView, refreshCmd, provider);

    vscode.window.setStatusBarMessage('$(check) NEMO V1.0 activo', 4000);
}

function deactivate() {}

module.exports = { activate, deactivate };
