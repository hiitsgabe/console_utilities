"""
Embedded SPA client HTML for the Web Companion.

Single-page app served to phone browsers. Connects via SSE for state
updates and POST for actions. Pure JS, no framework dependencies.
"""

CLIENT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Console Utilities - Web Companion</title>
<style>
:root {
    --bg: #001400;
    --surface: #001e00;
    --surface-hover: #002800;
    --primary: #00ff41;
    --primary-dark: #00b42d;
    --secondary: #c8c800;
    --text: #00ff41;
    --text-dim: #00b42d;
    --text-disabled: #005014;
    --error: #ff3222;
    --radius: 4px;
}

* { margin: 0; padding: 0; box-sizing: border-box; }
html, body {
    width: 100%; height: 100%;
    background: var(--bg);
    color: var(--text);
    font-family: 'Courier New', monospace;
    font-size: 16px;
    overflow: hidden;
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
}

#app {
    display: flex;
    flex-direction: column;
    height: 100%;
    max-width: 100%;
}

/* Header bar */
.header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    background: var(--surface);
    border-bottom: 1px solid var(--primary-dark);
    flex-shrink: 0;
}
.header h1 {
    font-size: 14px;
    font-weight: normal;
    color: var(--primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
}
.status-dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    background: var(--error);
    margin-left: 8px;
    flex-shrink: 0;
    transition: background 0.3s;
}
.status-dot.connected { background: var(--primary); }

/* Tab bar */
.tab-bar {
    display: flex;
    background: var(--surface);
    border-bottom: 1px solid var(--primary-dark);
    flex-shrink: 0;
}
.tab-bar button {
    flex: 1;
    padding: 10px 12px;
    font-size: 13px;
    font-family: inherit;
    background: transparent;
    color: var(--text-dim);
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
}
.tab-bar button:hover {
    color: var(--text);
}
.tab-bar button.active {
    color: var(--primary);
    border-bottom-color: var(--primary);
}

/* MJPEG thumbnail */
.thumbnail-wrap {
    position: relative;
    background: #000;
    flex-shrink: 0;
    max-height: 180px;
    overflow: hidden;
    display: flex;
    justify-content: center;
    border-bottom: 1px solid var(--primary-dark);
}
.thumbnail-wrap img {
    height: 180px;
    width: auto;
    display: block;
    opacity: 0.85;
}
.thumbnail-wrap.collapsed { display: none; }
.thumb-toggle {
    position: absolute;
    bottom: 4px;
    right: 4px;
    background: rgba(0,0,0,0.7);
    color: var(--text-dim);
    border: 1px solid var(--primary-dark);
    border-radius: var(--radius);
    padding: 2px 6px;
    font-size: 11px;
    cursor: pointer;
    font-family: inherit;
}

/* Content area */
.content {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    -webkit-overflow-scrolling: touch;
}

/* Text input screen */
.text-input-wrap {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding-top: 8px;
}
.text-input-wrap label {
    font-size: 13px;
    color: var(--text-dim);
}
.text-input-wrap input {
    width: 100%;
    padding: 12px;
    font-size: 18px;
    font-family: inherit;
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--primary-dark);
    border-radius: var(--radius);
    outline: none;
    caret-color: var(--primary);
}
.text-input-wrap input:focus {
    border-color: var(--primary);
    box-shadow: 0 0 8px rgba(0,255,65,0.2);
}
.text-input-wrap .btn-row {
    display: flex;
    gap: 8px;
}
.btn {
    flex: 1;
    padding: 12px;
    font-size: 16px;
    font-family: inherit;
    background: var(--surface);
    color: var(--primary);
    border: 1px solid var(--primary-dark);
    border-radius: var(--radius);
    cursor: pointer;
    text-align: center;
    transition: background 0.15s;
}
.btn:active, .btn:hover {
    background: var(--surface-hover);
}
.btn.primary {
    background: var(--primary-dark);
    color: var(--bg);
    border-color: var(--primary);
    font-weight: bold;
}
.btn.primary:active {
    background: var(--primary);
}

/* List screen */
.list-items {
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.list-item {
    padding: 10px 12px;
    background: var(--surface);
    border: 1px solid transparent;
    border-radius: var(--radius);
    cursor: pointer;
    font-size: 14px;
    color: var(--text);
    transition: background 0.1s;
    display: flex;
    align-items: center;
    gap: 8px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.list-item:active {
    background: var(--surface-hover);
}
.list-item.divider {
    background: transparent;
    color: var(--text-disabled);
    font-size: 12px;
    padding: 6px 12px;
    cursor: default;
    border: none;
    pointer-events: none;
    margin-top: 8px;
}
.list-item.highlighted {
    border-color: var(--primary);
    background: var(--surface-hover);
}
.list-item.selected::before {
    content: '\\2713';
    color: var(--secondary);
    font-size: 16px;
}
.list-item .item-thumb {
    width: 36px;
    height: 36px;
    object-fit: contain;
    flex-shrink: 0;
    border-radius: 2px;
    background: var(--bg);
}
.list-item .item-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
}
.list-item .item-status {
    font-size: 12px;
    color: var(--text-dim);
}
.list-item .item-progress {
    width: 40px;
    height: 4px;
    background: var(--surface);
    border: 1px solid var(--primary-dark);
    border-radius: 2px;
    overflow: hidden;
}
.list-item .item-progress-bar {
    height: 100%;
    background: var(--primary);
    transition: width 0.3s;
}

/* File browser (companion in-app file browser - NOT the file manager tab) */
.breadcrumb {
    font-size: 12px;
    color: var(--text-dim);
    padding: 4px 0 8px;
    word-break: break-all;
}
.file-entry {
    padding: 10px 12px;
    background: var(--surface);
    border: 1px solid transparent;
    border-radius: var(--radius);
    cursor: pointer;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 2px;
}
.file-entry:active { background: var(--surface-hover); }
.file-entry.highlighted { border-color: var(--primary); }
.file-entry .icon { flex-shrink: 0; }
.file-entry .name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* Confirm modal */
.confirm-wrap {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding-top: 20px;
    text-align: center;
}
.confirm-message {
    font-size: 14px;
    color: var(--text);
    line-height: 1.5;
    white-space: pre-wrap;
}
.confirm-buttons {
    display: flex;
    gap: 8px;
}
.confirm-buttons .btn.active {
    border-color: var(--primary);
    background: var(--surface-hover);
}

/* Loading screen */
.loading-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
    padding-top: 40px;
    text-align: center;
}
.spinner {
    width: 32px; height: 32px;
    border: 3px solid var(--surface-hover);
    border-top-color: var(--primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-message {
    font-size: 14px;
    color: var(--text-dim);
}
.progress-bar-wrap {
    width: 80%;
    height: 6px;
    background: var(--surface);
    border: 1px solid var(--primary-dark);
    border-radius: 3px;
    overflow: hidden;
}
.progress-bar-fill {
    height: 100%;
    background: var(--primary);
    transition: width 0.3s;
}

/* Details screen */
.details-wrap {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding-top: 8px;
}
.details-name {
    font-size: 18px;
    color: var(--primary);
    word-break: break-word;
}
.details-info {
    font-size: 13px;
    color: var(--text-dim);
    line-height: 1.4;
}
.details-actions {
    display: flex;
    gap: 8px;
    margin-top: 8px;
}

/* Form screen */
.form-fields {
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.form-field {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 12px;
    background: var(--surface);
    border: 1px solid transparent;
    border-radius: var(--radius);
}
.form-field.highlighted {
    border-color: var(--primary);
}
.form-label {
    font-size: 14px;
    color: var(--text-dim);
}
.form-value {
    font-size: 14px;
    color: var(--text);
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* Search bar */
.search-bar {
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
}
.search-bar input {
    flex: 1;
    padding: 8px;
    font-size: 14px;
    font-family: inherit;
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--primary-dark);
    border-radius: var(--radius);
    outline: none;
}
.search-bar input:focus { border-color: var(--primary); }
.search-bar .btn { flex: 0 0 auto; padding: 8px 12px; }

/* Nav buttons */
.nav-bar {
    display: flex;
    gap: 4px;
    padding: 8px 12px;
    background: var(--surface);
    border-top: 1px solid var(--primary-dark);
    flex-shrink: 0;
}
.nav-bar .btn {
    font-size: 14px;
    padding: 10px;
}

/* Disconnected overlay */
.disconnected {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,20,0,0.9);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
    z-index: 100;
}
.disconnected.hidden { display: none; }
.disconnected p {
    color: var(--text-dim);
    font-size: 14px;
}

/* ============================================================
   FILE MANAGER TAB STYLES
   ============================================================ */

#fileManagerView {
    display: none;
    flex-direction: column;
    flex: 1;
    overflow: hidden;
}
#fileManagerView.active {
    display: flex;
}
#companionView {
    display: flex;
    flex-direction: column;
    flex: 1;
    overflow: hidden;
}
#companionView.hidden {
    display: none;
}

/* FM Toolbar */
.fm-toolbar {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 10px;
    background: var(--surface);
    border-bottom: 1px solid var(--primary-dark);
    flex-shrink: 0;
}
.fm-toolbar button {
    background: var(--surface);
    color: var(--primary);
    border: 1px solid var(--primary-dark);
    border-radius: var(--radius);
    padding: 6px 10px;
    font-family: inherit;
    font-size: 13px;
    cursor: pointer;
    flex-shrink: 0;
    transition: background 0.15s;
}
.fm-toolbar button:hover { background: var(--surface-hover); }
.fm-toolbar button:disabled {
    color: var(--text-disabled);
    cursor: default;
    background: var(--surface);
}
.fm-address-bar {
    flex: 1;
    padding: 6px 8px;
    font-family: inherit;
    font-size: 13px;
    background: var(--bg);
    color: var(--text);
    border: 1px solid var(--primary-dark);
    border-radius: var(--radius);
    outline: none;
    min-width: 0;
}
.fm-address-bar:focus { border-color: var(--primary); }

/* FM Action bar */
.fm-action-bar {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background: var(--surface);
    border-bottom: 1px solid var(--primary-dark);
    flex-shrink: 0;
    flex-wrap: wrap;
}
.fm-action-bar button {
    background: var(--surface);
    color: var(--primary);
    border: 1px solid var(--primary-dark);
    border-radius: var(--radius);
    padding: 5px 10px;
    font-family: inherit;
    font-size: 12px;
    cursor: pointer;
    transition: background 0.15s;
}
.fm-action-bar button:hover { background: var(--surface-hover); }
.fm-action-bar .fm-upload-progress {
    flex: 1;
    min-width: 100px;
    display: none;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--text-dim);
}
.fm-action-bar .fm-upload-progress.active { display: flex; }
.fm-upload-bar {
    flex: 1;
    height: 4px;
    background: var(--surface);
    border: 1px solid var(--primary-dark);
    border-radius: 2px;
    overflow: hidden;
}
.fm-upload-bar-fill {
    height: 100%;
    background: var(--primary);
    transition: width 0.2s;
    width: 0%;
}

/* FM selection action bar */
.fm-sel-bar {
    display: none;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background: var(--surface);
    border-bottom: 1px solid var(--primary-dark);
    flex-shrink: 0;
    font-size: 12px;
    color: var(--text-dim);
}
.fm-sel-bar.active { display: flex; }
.fm-sel-bar button {
    background: var(--surface);
    color: var(--primary);
    border: 1px solid var(--primary-dark);
    border-radius: var(--radius);
    padding: 4px 8px;
    font-family: inherit;
    font-size: 12px;
    cursor: pointer;
}
.fm-sel-bar button:hover { background: var(--surface-hover); }
.fm-sel-bar button.danger { color: var(--error); border-color: var(--error); }
.fm-sel-bar button.danger:hover { background: #1a0000; }
.fm-sel-bar .sel-count { margin-right: auto; }

/* FM Main file area */
.fm-main {
    flex: 1;
    overflow-y: auto;
    padding: 10px;
    -webkit-overflow-scrolling: touch;
    position: relative;
}
.fm-main.drag-over {
    background: rgba(0, 255, 65, 0.03);
}

/* FM Grid view */
.fm-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    gap: 6px;
}
.fm-grid-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 10px 6px 8px;
    border-radius: var(--radius);
    cursor: pointer;
    border: 1px solid transparent;
    transition: background 0.1s, border-color 0.1s;
    position: relative;
    min-height: 90px;
    user-select: none;
}
.fm-grid-item:hover {
    background: var(--surface-hover);
}
.fm-grid-item.selected {
    background: var(--surface-hover);
    border-color: var(--primary);
}
.fm-grid-item .fm-icon {
    font-size: 36px;
    line-height: 1;
    margin-bottom: 4px;
    pointer-events: none;
}
.fm-grid-item .fm-name {
    font-size: 11px;
    text-align: center;
    word-break: break-all;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    line-height: 1.2;
    max-height: 2.4em;
    color: var(--text);
    pointer-events: none;
}
.fm-grid-item .fm-checkbox {
    position: absolute;
    top: 4px;
    left: 4px;
    width: 16px;
    height: 16px;
    border: 1px solid var(--primary-dark);
    border-radius: 2px;
    background: var(--bg);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    color: var(--primary);
    opacity: 0;
    transition: opacity 0.15s;
}
.fm-grid-item:hover .fm-checkbox,
.fm-grid-item.selected .fm-checkbox {
    opacity: 1;
}
.fm-grid-item.selected .fm-checkbox {
    background: var(--primary-dark);
    color: var(--bg);
}

/* FM List view */
.fm-list-header {
    display: flex;
    padding: 4px 10px;
    font-size: 11px;
    color: var(--text-disabled);
    border-bottom: 1px solid var(--primary-dark);
    user-select: none;
}
.fm-list-header span:nth-child(1) { flex: 1; }
.fm-list-header span:nth-child(2) { width: 80px; text-align: right; }
.fm-list-header span:nth-child(3) { width: 120px; text-align: right; }

.fm-list {}
.fm-list-item {
    display: flex;
    align-items: center;
    padding: 6px 10px;
    cursor: pointer;
    border: 1px solid transparent;
    border-radius: 2px;
    transition: background 0.1s;
    gap: 8px;
    user-select: none;
}
.fm-list-item:hover {
    background: var(--surface-hover);
}
.fm-list-item.selected {
    background: var(--surface-hover);
    border-color: var(--primary);
}
.fm-list-item .fm-checkbox {
    width: 16px;
    height: 16px;
    border: 1px solid var(--primary-dark);
    border-radius: 2px;
    background: var(--bg);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    color: var(--primary);
    flex-shrink: 0;
    opacity: 0;
    transition: opacity 0.15s;
}
.fm-list-item:hover .fm-checkbox,
.fm-list-item.selected .fm-checkbox {
    opacity: 1;
}
.fm-list-item.selected .fm-checkbox {
    background: var(--primary-dark);
    color: var(--bg);
}
.fm-list-item .fm-icon {
    font-size: 18px;
    flex-shrink: 0;
    width: 24px;
    text-align: center;
    pointer-events: none;
}
.fm-list-item .fm-name {
    flex: 1;
    font-size: 13px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    pointer-events: none;
}
.fm-list-item .fm-size {
    width: 80px;
    text-align: right;
    font-size: 11px;
    color: var(--text-dim);
    flex-shrink: 0;
    pointer-events: none;
}
.fm-list-item .fm-modified {
    width: 120px;
    text-align: right;
    font-size: 11px;
    color: var(--text-dim);
    flex-shrink: 0;
    pointer-events: none;
}

/* FM Drop zone overlay */
.fm-drop-overlay {
    display: none;
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0, 255, 65, 0.08);
    border: 3px dashed var(--primary);
    border-radius: 8px;
    z-index: 50;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    gap: 12px;
    pointer-events: none;
}
.fm-drop-overlay.active {
    display: flex;
}
.fm-drop-overlay .drop-icon {
    font-size: 48px;
}
.fm-drop-overlay .drop-text {
    font-size: 16px;
    color: var(--primary);
}

/* FM Modal overlay */
.fm-modal-overlay {
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0, 20, 0, 0.85);
    z-index: 200;
    align-items: center;
    justify-content: center;
}
.fm-modal-overlay.active { display: flex; }
.fm-modal {
    background: var(--surface);
    border: 1px solid var(--primary-dark);
    border-radius: 6px;
    padding: 20px;
    min-width: 280px;
    max-width: 400px;
    width: 90%;
}
.fm-modal h3 {
    font-size: 14px;
    font-weight: normal;
    color: var(--primary);
    margin-bottom: 16px;
}
.fm-modal input {
    width: 100%;
    padding: 10px;
    font-family: inherit;
    font-size: 14px;
    background: var(--bg);
    color: var(--text);
    border: 1px solid var(--primary-dark);
    border-radius: var(--radius);
    outline: none;
    margin-bottom: 16px;
}
.fm-modal input:focus { border-color: var(--primary); }
.fm-modal p {
    font-size: 13px;
    color: var(--text);
    margin-bottom: 16px;
    line-height: 1.4;
    word-break: break-all;
}
.fm-modal .fm-modal-buttons {
    display: flex;
    gap: 8px;
}
.fm-modal .fm-modal-buttons button {
    flex: 1;
    padding: 10px;
    font-family: inherit;
    font-size: 14px;
    background: var(--surface);
    color: var(--primary);
    border: 1px solid var(--primary-dark);
    border-radius: var(--radius);
    cursor: pointer;
    transition: background 0.15s;
}
.fm-modal .fm-modal-buttons button:hover { background: var(--surface-hover); }
.fm-modal .fm-modal-buttons button.primary {
    background: var(--primary-dark);
    color: var(--bg);
    border-color: var(--primary);
    font-weight: bold;
}
.fm-modal .fm-modal-buttons button.primary:hover { background: var(--primary); }
.fm-modal .fm-modal-buttons button.danger {
    background: #2a0000;
    color: var(--error);
    border-color: var(--error);
}
.fm-modal .fm-modal-buttons button.danger:hover { background: #3a0000; }

/* FM Context menu */
.fm-context-menu {
    display: none;
    position: fixed;
    background: var(--surface);
    border: 1px solid var(--primary-dark);
    border-radius: var(--radius);
    z-index: 300;
    min-width: 150px;
    padding: 4px 0;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
}
.fm-context-menu.active { display: block; }
.fm-context-menu button {
    display: block;
    width: 100%;
    padding: 8px 14px;
    font-family: inherit;
    font-size: 13px;
    background: transparent;
    color: var(--text);
    border: none;
    cursor: pointer;
    text-align: left;
    transition: background 0.1s;
}
.fm-context-menu button:hover { background: var(--surface-hover); }
.fm-context-menu button.danger { color: var(--error); }
.fm-context-menu .ctx-sep {
    height: 1px;
    background: var(--primary-dark);
    margin: 4px 0;
}

/* FM Loading */
.fm-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 40px;
    gap: 12px;
    color: var(--text-dim);
    font-size: 13px;
}
.fm-loading .spinner {
    width: 20px; height: 20px;
    border-width: 2px;
}

/* FM Error */
.fm-error {
    padding: 20px;
    text-align: center;
    color: var(--error);
    font-size: 13px;
}

/* FM Empty */
.fm-empty {
    padding: 40px;
    text-align: center;
    color: var(--text-disabled);
    font-size: 13px;
}
</style>
</head>
<body>
<div id="app">
    <div class="header">
        <h1 id="title">Console Utilities</h1>
        <div class="status-dot" id="statusDot"></div>
    </div>
    <div class="tab-bar" id="tabBar">
        <button class="active" data-tab="companion">Companion</button>
        <button data-tab="files">Files</button>
    </div>

    <!-- Companion view (original) -->
    <div id="companionView">
        <div class="thumbnail-wrap" id="thumbWrap">
            <img id="thumbImg" src="/mjpeg" alt="Screen">
            <button class="thumb-toggle" id="thumbToggle">Hide</button>
        </div>
        <div class="content" id="content"></div>
        <div class="nav-bar" id="navBar">
            <button class="btn" onclick="sendAction({action:'back'})">Back</button>
            <button class="btn" onclick="sendAction({action:'navigate',direction:'up'})">Up</button>
            <button class="btn" onclick="sendAction({action:'navigate',direction:'down'})">Down</button>
            <button class="btn" onclick="sendAction({action:'select'})">Select</button>
        </div>
    </div>

    <!-- File Manager view -->
    <div id="fileManagerView">
        <div class="fm-toolbar">
            <button id="fmBackBtn" title="Go up">&#9664; Up</button>
            <input type="text" class="fm-address-bar" id="fmAddressBar" value="/" spellcheck="false" autocomplete="off">
            <button id="fmGoBtn" title="Navigate">Go</button>
            <button id="fmViewToggle" title="Toggle view">Grid</button>
        </div>
        <div class="fm-action-bar">
            <button id="fmUploadBtn">Upload Files</button>
            <button id="fmNewFolderBtn">New Folder</button>
            <div class="fm-upload-progress" id="fmUploadProgress">
                <span id="fmUploadLabel">Uploading...</span>
                <div class="fm-upload-bar">
                    <div class="fm-upload-bar-fill" id="fmUploadBarFill"></div>
                </div>
            </div>
        </div>
        <div class="fm-sel-bar" id="fmSelBar">
            <span class="sel-count" id="fmSelCount">0 selected</span>
            <button id="fmSelDownload">Download</button>
            <button id="fmSelRename">Rename</button>
            <button id="fmSelDelete" class="danger">Delete</button>
            <button id="fmSelClear">Clear</button>
        </div>
        <div class="fm-main" id="fmMain">
            <div id="fmContent"></div>
            <div class="fm-drop-overlay" id="fmDropOverlay">
                <span class="drop-icon">&#128229;</span>
                <span class="drop-text">Drop files here to upload</span>
            </div>
        </div>
    </div>
</div>

<div class="disconnected hidden" id="disconnected">
    <div class="spinner"></div>
    <p>Connecting to handheld...</p>
    <p style="font-size:12px;color:var(--text-disabled)">Make sure the app is running</p>
</div>

<!-- FM Context menu -->
<div class="fm-context-menu" id="fmContextMenu">
    <button data-action="open">Open</button>
    <div class="ctx-sep"></div>
    <button data-action="download">Download</button>
    <button data-action="rename">Rename</button>
    <div class="ctx-sep"></div>
    <button data-action="delete" class="danger">Delete</button>
</div>

<!-- FM Modal overlay -->
<div class="fm-modal-overlay" id="fmModalOverlay">
    <div class="fm-modal" id="fmModal"></div>
</div>

<!-- Hidden file input for uploads -->
<input type="file" id="fmFileInput" multiple style="display:none">

<script>
/* ============================================================
   COMPANION TAB (original code, untouched)
   ============================================================ */
const content = document.getElementById('content');
const titleEl = document.getElementById('title');
const statusDot = document.getElementById('statusDot');
const thumbWrap = document.getElementById('thumbWrap');
const thumbToggle = document.getElementById('thumbToggle');
const thumbImg = document.getElementById('thumbImg');
const navBar = document.getElementById('navBar');
const disconnectedOverlay = document.getElementById('disconnected');

let currentState = null;
let thumbVisible = true;
let evtSource = null;
let reconnectTimer = null;

// Thumb toggle
thumbToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    thumbVisible = !thumbVisible;
    thumbWrap.classList.toggle('collapsed', !thumbVisible);
    thumbToggle.textContent = thumbVisible ? 'Hide' : 'Show';
});

// SSE connection
function connectSSE() {
    if (evtSource) {
        evtSource.close();
    }
    evtSource = new EventSource('/events');

    evtSource.onopen = () => {
        statusDot.classList.add('connected');
        disconnectedOverlay.classList.add('hidden');
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
    };

    evtSource.onmessage = (e) => {
        try {
            const state = JSON.parse(e.data);
            currentState = state;
            renderState(state);
        } catch(err) {}
    };

    evtSource.onerror = () => {
        statusDot.classList.remove('connected');
        disconnectedOverlay.classList.remove('hidden');
        evtSource.close();
        // Reconnect after delay
        if (!reconnectTimer) {
            reconnectTimer = setTimeout(connectSSE, 2000);
        }
    };
}

function sendAction(obj) {
    fetch('/action', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(obj)
    }).catch(() => {});
}

// ---- Renderers ----

function renderState(state) {
    titleEl.textContent = state.title || 'Console Utilities';

    switch (state.screen_type) {
        case 'text_input': renderTextInput(state); break;
        case 'list': renderList(state); break;
        case 'file_browser': renderFileBrowser(state); break;
        case 'confirm': renderConfirm(state); break;
        case 'loading': renderLoading(state); break;
        case 'details': renderDetails(state); break;
        case 'form': renderForm(state); break;
        case 'roster_preview': renderRosterPreview(state); break;
        case 'color_picker': renderColorPicker(state); break;
        default: renderUnknown(state); break;
    }
}

function renderTextInput(state) {
    // Don't re-render if already showing text input (preserve focus/cursor)
    const existing = content.querySelector('.text-input-wrap');
    if (existing) {
        const inp = existing.querySelector('input');
        // Only update if text changed externally (not from our own typing)
        if (inp && inp.dataset.lastSent !== undefined && inp.value === inp.dataset.lastSent) {
            if (inp.value !== state.text) {
                inp.value = state.text;
            }
        }
        return;
    }

    const inputType = state.input_type === 'password' ? 'password' :
                      state.input_type === 'email' ? 'email' :
                      state.input_type === 'url' ? 'url' : 'text';

    content.innerHTML = `
        <div class="text-input-wrap">
            <label>${escHtml(state.title)}</label>
            <input type="${inputType}" id="textInput" value="${escAttr(state.text || '')}"
                   autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false">
            <div class="btn-row">
                <button class="btn" onclick="sendAction({action:'back'})">Cancel</button>
                <button class="btn primary" id="sendBtn">Send</button>
            </div>
        </div>
    `;

    const inp = document.getElementById('textInput');
    const sendBtn = document.getElementById('sendBtn');
    inp.dataset.lastSent = '';

    sendBtn.addEventListener('click', () => {
        inp.dataset.lastSent = inp.value;
        sendAction({action: 'set_text', text: inp.value});
        setTimeout(() => sendAction({action: 'submit_text'}), 50);
    });

    inp.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            inp.dataset.lastSent = inp.value;
            sendAction({action: 'set_text', text: inp.value});
            setTimeout(() => sendAction({action: 'submit_text'}), 50);
        }
    });

    // Auto-focus after a short delay (helps on mobile)
    setTimeout(() => inp.focus(), 100);
}

function renderList(state) {
    const items = state.items || [];
    let html = '';

    // Search bar if search is present
    if (state.search !== undefined && state.search !== null) {
        const searchType = state.searchable ? 'filter' : 'search';
        html += `<div class="search-bar">
            <input type="text" id="searchInput" value="${escAttr(state.search)}"
                   placeholder="Search..." autocomplete="off" data-search-type="${searchType}">
            <button class="btn" onclick="doSearch()">Go</button>
        </div>`;
    }

    html += '<div class="list-items">';
    items.forEach((item, i) => {
        if (item.is_divider) {
            html += `<div class="list-item divider">${escHtml(item.name)}</div>`;
            return;
        }

        const cls = [];
        if (i === state.highlighted) cls.push('highlighted');
        if (item.selected) cls.push('selected');

        let thumb = '';
        if (item.thumb_url) {
            thumb = `<img class="item-thumb" src="${escAttr(item.thumb_url)}" loading="lazy" onerror="this.style.display='none'">`;
        }

        let extra = '';
        if (item.status) {
            extra += `<span class="item-status">${escHtml(item.status)}</span>`;
        }
        if (item.progress !== undefined && item.progress > 0 && item.progress < 1) {
            extra += `<div class="item-progress"><div class="item-progress-bar" style="width:${Math.round(item.progress*100)}%"></div></div>`;
        }

        html += `<div class="list-item ${cls.join(' ')}" onclick="sendAction({action:'select_index',index:${i}})">
            ${thumb}
            <span class="item-name">${escHtml(item.name)}</span>
            ${extra}
        </div>`;
    });
    html += '</div>';

    // Wizard action buttons
    if (state.wizard_action) {
        html += '<div class="btn-row" style="margin-top:8px">';
        if (state.wizard_action === 'dedupe_review') {
            html += `<button class="btn" onclick="sendAction({action:'navigate',direction:'left'})">Prev Group</button>`;
            html += `<button class="btn primary" onclick="sendAction({action:'select'})">Confirm</button>`;
            html += `<button class="btn" onclick="sendAction({action:'navigate',direction:'right'})">Next Group</button>`;
        } else if (state.wizard_action === 'rename_auto') {
            html += `<button class="btn primary" onclick="sendAction({action:'select'})">Rename All</button>`;
            html += `<button class="btn" onclick="sendAction({action:'back'})">Cancel</button>`;
        } else if (state.wizard_action === 'rename_manual') {
            html += `<button class="btn primary" onclick="sendAction({action:'select'})">Toggle</button>`;
            html += `<button class="btn" onclick="sendAction({action:'back'})">Cancel</button>`;
        } else if (state.wizard_action === 'scraper_rom_list') {
            html += `<button class="btn primary" onclick="sendAction({action:'select'})">Toggle</button>`;
            html += `<button class="btn" onclick="sendAction({action:'back'})">Start Scraping</button>`;
        } else {
            html += `<button class="btn primary" onclick="sendAction({action:'select'})">Select</button>`;
            html += `<button class="btn" onclick="sendAction({action:'back'})">Back</button>`;
        }
        html += '</div>';
    }

    content.innerHTML = html;

    // Auto-scroll to highlighted
    const highlighted = content.querySelector('.list-item.highlighted');
    if (highlighted) {
        highlighted.scrollIntoView({block: 'nearest', behavior: 'auto'});
    }

    // Wire up search
    if (state.search !== undefined) {
        const searchInp = document.getElementById('searchInput');
        if (searchInp) {
            searchInp.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    doSearch();
                }
            });
            // Real-time filter for league browser
            if (searchInp.dataset.searchType === 'filter') {
                searchInp.addEventListener('input', () => {
                    sendAction({action: 'set_text', text: searchInp.value});
                });
            }
        }
    }
}

function doSearch() {
    const inp = document.getElementById('searchInput');
    if (!inp) return;
    if (inp.dataset.searchType === 'filter') {
        // League browser: set_text updates the filter query directly
        sendAction({action: 'set_text', text: inp.value});
    } else {
        sendAction({action: 'search', text: inp.value});
    }
}

function renderFileBrowser(state) {
    let html = `<div class="breadcrumb">${escHtml(state.current_path || '/')}</div>`;

    if (state.show_select_button) {
        html += `<div class="btn-row" style="margin-bottom:8px">
            <button class="btn primary" onclick="sendAction({action:'select_folder'})">Select This Folder</button>
            <button class="btn" onclick="sendAction({action:'back'})">Cancel</button>
        </div>`;
    }

    html += '<div class="list-items">';
    const entries = state.entries || [];
    entries.forEach((entry, i) => {
        const cls = i === state.highlighted ? 'file-entry highlighted' : 'file-entry';
        let icon;
        if (entry.type === 'parent') icon = '&#11148;';
        else if (entry.type === 'create_folder') icon = '&#10133;';
        else if (entry.is_dir) icon = '&#128193;';
        else icon = '&#128196;';
        html += `<div class="${cls}" onclick="sendAction({action:'browse_into',index:${i}})">
            <span class="icon">${icon}</span>
            <span class="name">${escHtml(entry.name)}</span>
        </div>`;
    });
    html += '</div>';

    if (!state.show_select_button) {
        html += `<div class="btn-row" style="margin-top:8px">
            <button class="btn" onclick="sendAction({action:'back'})">Cancel</button>
        </div>`;
    }

    content.innerHTML = html;
}

function renderConfirm(state) {
    const buttons = state.buttons || ['OK', 'Cancel'];
    let btnsHtml = '';
    buttons.forEach((label, i) => {
        if (!label) return;
        const cls = i === state.selected ? 'btn active' : 'btn';
        btnsHtml += `<button class="${cls}" onclick="sendAction({action:'confirm_button',index:${i}})">${escHtml(label)}</button>`;
    });

    content.innerHTML = `
        <div class="confirm-wrap">
            <div class="confirm-message">${escHtml(state.message || '')}</div>
            <div class="confirm-buttons">${btnsHtml}</div>
        </div>
    `;
}

function renderLoading(state) {
    const progress = state.progress || 0;
    const showBar = progress > 0;
    content.innerHTML = `
        <div class="loading-wrap">
            <div class="spinner"></div>
            <div class="loading-message">${escHtml(state.message || 'Loading...')}</div>
            ${showBar ? `<div class="progress-bar-wrap"><div class="progress-bar-fill" style="width:${progress}%"></div></div>` : ''}
        </div>
    `;
}

function renderDetails(state) {
    let thumbHtml = '';
    if (state.thumb_url) {
        thumbHtml = `<img src="${escAttr(state.thumb_url)}" style="max-width:120px;max-height:120px;object-fit:contain;border-radius:4px;background:var(--bg)" onerror="this.style.display='none'">`;
    }

    let actionsHtml = '';
    (state.actions || []).forEach((action, i) => {
        actionsHtml += `<button class="btn primary" onclick="sendAction({action:'select'})">${escHtml(action)}</button>`;
    });
    actionsHtml += `<button class="btn" onclick="sendAction({action:'back'})">Back</button>`;

    content.innerHTML = `
        <div class="details-wrap">
            ${thumbHtml}
            <div class="details-name">${escHtml(state.name || '')}</div>
            <div class="details-info">${escHtml(state.info || '')}</div>
            <div class="details-actions">${actionsHtml}</div>
        </div>
    `;
}

function renderForm(state) {
    let html = '<div class="form-fields">';
    (state.fields || []).forEach((field, i) => {
        const cls = i === state.highlighted ? 'form-field highlighted' : 'form-field';
        if (field.type === 'cycle') {
            // Cyclable field (season, language) — show left/right arrows
            html += `<div class="${cls}" style="display:flex;align-items:center;gap:4px">
                <span class="form-label" style="flex:1">${escHtml(field.label || '')}</span>
                <div onclick="event.stopPropagation();sendAction({action:'cycle_field',index:${i},direction:'left'})" style="width:44px;height:44px;display:flex;align-items:center;justify-content:center;border-radius:8px;background:var(--surface);cursor:pointer;font-size:20px;font-weight:bold;user-select:none;-webkit-tap-highlight-color:transparent">&lsaquo;</div>
                <span class="form-value" style="min-width:60px;text-align:center">${escHtml(field.value || '')}</span>
                <div onclick="event.stopPropagation();sendAction({action:'cycle_field',index:${i},direction:'right'})" style="width:44px;height:44px;display:flex;align-items:center;justify-content:center;border-radius:8px;background:var(--surface);cursor:pointer;font-size:20px;font-weight:bold;user-select:none;-webkit-tap-highlight-color:transparent">&rsaquo;</div>
            </div>`;
        } else if (field.action === 'locked') {
            html += `<div class="${cls}" style="opacity:0.5;cursor:default">
                <span class="form-label">${escHtml(field.label || '')}</span>
                <span class="form-value">${escHtml(field.value || '')}</span>
            </div>`;
        } else {
            html += `<div class="${cls}" onclick="sendAction({action:'select_index',index:${i}})">
                <span class="form-label">${escHtml(field.label || '')}</span>
                <span class="form-value">${escHtml(field.value || '')}</span>
            </div>`;
        }
    });
    html += '</div>';
    content.innerHTML = html;
}

function renderRosterPreview(state) {
    const teams = state.teams || [];
    const players = state.players || [];
    const selTeam = state.selected_team || 0;
    const selPlayer = state.selected_player || 0;
    let html = '<div style="display:flex;gap:12px;height:calc(100vh - 180px);min-height:300px">';
    // Team list
    html += '<div style="flex:0 0 40%;overflow-y:auto;border-right:1px solid var(--border)">';
    html += '<div style="padding:4px 8px;font-weight:600;color:var(--text-dim);font-size:13px">Teams</div>';
    teams.forEach((t, i) => {
        const sel = i === selTeam ? 'background:var(--accent);color:#fff;' : '';
        const status = t.loading ? ' (loading...)' : t.error ? ' (error)' : '';
        html += `<div style="padding:8px 10px;cursor:pointer;border-radius:6px;margin:2px 4px;${sel}" onclick="sendAction({action:'select_index',index:${i}})">
            ${escHtml(t.name)}${status}</div>`;
    });
    html += '</div>';
    // Player list
    html += '<div style="flex:1;overflow-y:auto">';
    html += '<div style="padding:4px 8px;font-weight:600;color:var(--text-dim);font-size:13px">Players</div>';
    if (players.length === 0) {
        html += '<div style="padding:16px;color:var(--text-dim)">No players loaded</div>';
    }
    players.forEach((p, i) => {
        const num = p.number != null ? `#${p.number} ` : '';
        const pos = p.position ? `<span style="color:var(--text-dim);font-size:12px"> ${escHtml(p.position)}</span>` : '';
        html += `<div style="padding:6px 10px;border-radius:6px;margin:2px 4px">${num}${escHtml(p.name)}${pos}</div>`;
    });
    html += '</div></div>';
    html += `<div style="text-align:center;padding:12px"><button class="btn" onclick="sendAction({action:'back'})">Close</button></div>`;
    content.innerHTML = html;
}

function renderColorPicker(state) {
    const teams = state.teams || [];
    const selTeam = state.selected_team || 0;
    const palette = state.palette || [];
    const colorIdx = state.color_index || 0;
    const picking = state.picking || 'primary';

    let html = '<div style="display:flex;gap:12px;height:calc(100vh - 180px);min-height:300px">';

    // Team list (left panel)
    html += '<div style="flex:0 0 45%;overflow-y:auto;border-right:1px solid var(--border)">';
    html += '<div style="padding:4px 8px;font-weight:600;color:var(--text-dim);font-size:13px">Teams</div>';
    teams.forEach((t, i) => {
        const sel = i === selTeam ? 'background:var(--accent);color:#fff;' : '';
        const pri = t.color ? '#' + t.color : '#555';
        const sec = t.alternate_color ? '#' + t.alternate_color : '#555';
        html += `<div style="padding:6px 10px;cursor:pointer;border-radius:6px;margin:2px 4px;display:flex;align-items:center;gap:6px;${sel}" onclick="sendAction({action:'select_index',index:${i}})">
            <div style="width:16px;height:16px;border-radius:3px;background:${pri};border:1px solid rgba(255,255,255,0.2);flex-shrink:0"></div>
            <div style="width:16px;height:16px;border-radius:3px;background:${sec};border:1px solid rgba(255,255,255,0.2);flex-shrink:0"></div>
            <span style="font-size:13px">${escHtml(t.name)}</span>
        </div>`;
    });
    html += '</div>';

    // Color palette (right panel)
    html += '<div style="flex:1;padding:8px">';
    if (teams.length > 0 && selTeam < teams.length) {
        const t = teams[selTeam];
        html += `<div style="font-weight:600;margin-bottom:8px">${escHtml(t.name)}</div>`;
        html += `<div style="color:var(--text-dim);font-size:13px;margin-bottom:12px">Pick ${picking} color:</div>`;
    }
    html += '<div style="display:flex;flex-wrap:wrap;gap:8px">';
    palette.forEach((c, ci) => {
        const border = ci === colorIdx ? '3px solid var(--accent)' : '1px solid rgba(255,255,255,0.3)';
        html += `<div onclick="sendAction({action:'pick_color',color_index:${ci}})" style="width:48px;height:48px;border-radius:8px;background:#${c.hex};border:${border};cursor:pointer;display:flex;align-items:center;justify-content:center" title="${escAttr(c.name)}">
            ${ci === colorIdx ? '<span style="font-size:10px;text-shadow:0 0 3px #000,0 0 3px #000">&#10003;</span>' : ''}
        </div>`;
    });
    html += '</div>';
    html += '</div></div>';
    html += `<div style="text-align:center;padding:12px"><button class="btn" onclick="sendAction({action:'back'})">Close</button></div>`;
    content.innerHTML = html;
}

function renderUnknown(state) {
    content.innerHTML = `
        <div class="loading-wrap">
            <p style="color:var(--text-dim)">Screen: ${escHtml(state.mode || state.screen_type || '?')}</p>
        </div>
    `;
}

// Helpers
function escHtml(s) {
    if (!s) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function escAttr(s) {
    return escHtml(s).replace(/'/g, '&#39;');
}

// Start
connectSSE();

/* ============================================================
   TAB SWITCHING
   ============================================================ */
const tabBar = document.getElementById('tabBar');
const companionView = document.getElementById('companionView');
const fileManagerView = document.getElementById('fileManagerView');
let activeTab = 'companion';

tabBar.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-tab]');
    if (!btn) return;
    const tab = btn.dataset.tab;
    if (tab === activeTab) return;
    activeTab = tab;

    // Update tab button styling
    tabBar.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    if (tab === 'companion') {
        companionView.classList.remove('hidden');
        fileManagerView.classList.remove('active');
    } else {
        companionView.classList.add('hidden');
        fileManagerView.classList.add('active');
        // Load roms directory on first switch to Files tab
        if (!fm.loaded) {
            fm.init();
        }
    }
});

/* ============================================================
   FILE MANAGER
   ============================================================ */
const fm = {
    currentPath: '/',
    viewMode: 'grid', // 'grid' or 'list'
    entries: [],
    selected: new Set(), // indices
    loaded: false,
    loading: false,
    history: [],
    contextTarget: null,

    // DOM refs
    addressBar: document.getElementById('fmAddressBar'),
    contentEl: document.getElementById('fmContent'),
    mainEl: document.getElementById('fmMain'),
    backBtn: document.getElementById('fmBackBtn'),
    goBtn: document.getElementById('fmGoBtn'),
    viewToggle: document.getElementById('fmViewToggle'),
    uploadBtn: document.getElementById('fmUploadBtn'),
    newFolderBtn: document.getElementById('fmNewFolderBtn'),
    uploadProgress: document.getElementById('fmUploadProgress'),
    uploadLabel: document.getElementById('fmUploadLabel'),
    uploadBarFill: document.getElementById('fmUploadBarFill'),
    selBar: document.getElementById('fmSelBar'),
    selCount: document.getElementById('fmSelCount'),
    selDownload: document.getElementById('fmSelDownload'),
    selRename: document.getElementById('fmSelRename'),
    selDelete: document.getElementById('fmSelDelete'),
    selClear: document.getElementById('fmSelClear'),
    dropOverlay: document.getElementById('fmDropOverlay'),
    contextMenu: document.getElementById('fmContextMenu'),
    modalOverlay: document.getElementById('fmModalOverlay'),
    modal: document.getElementById('fmModal'),
    fileInput: document.getElementById('fmFileInput'),

    // Fetch config and navigate to roms directory
    async init() {
        try {
            const resp = await fetch('/api/files/config');
            if (resp.ok) {
                const cfg = await resp.json();
                if (cfg.roms_dir) {
                    this.currentPath = cfg.roms_dir;
                }
            }
        } catch(e) {}
        this.navigate(this.currentPath);
    },

    // Navigate to a path
    async navigate(path) {
        path = path || '/';
        // Normalize
        if (!path.startsWith('/')) path = '/' + path;
        if (path !== '/' && path.endsWith('/')) path = path.slice(0, -1);

        this.loading = true;
        this.selected.clear();
        this.updateSelBar();
        this.renderLoading();

        try {
            const resp = await fetch('/api/files?path=' + encodeURIComponent(path));
            if (!resp.ok) {
                const err = await resp.text();
                throw new Error(err || resp.statusText);
            }
            const data = await resp.json();
            this.entries = data.entries || [];
            this.currentPath = data.path || path;
            this.addressBar.value = this.currentPath;
            this.loaded = true;
            this.loading = false;
            this.render();
        } catch(err) {
            this.loading = false;
            this.renderError(err.message || 'Failed to load directory');
        }
    },

    // Go to parent directory
    goUp() {
        if (this.currentPath === '/') return;
        const parts = this.currentPath.split('/').filter(Boolean);
        parts.pop();
        const parent = '/' + parts.join('/');
        this.history.push(this.currentPath);
        this.navigate(parent);
    },

    // Enter a subdirectory or open a folder
    enter(index) {
        const entry = this.entries[index];
        if (!entry) return;
        if (entry.is_dir) {
            this.history.push(this.currentPath);
            const newPath = this.currentPath === '/'
                ? '/' + entry.name
                : this.currentPath + '/' + entry.name;
            this.navigate(newPath);
        }
    },

    // Toggle selection of an item
    toggleSelect(index, additive) {
        if (additive) {
            if (this.selected.has(index)) {
                this.selected.delete(index);
            } else {
                this.selected.add(index);
            }
        } else {
            if (this.selected.has(index) && this.selected.size === 1) {
                this.selected.clear();
            } else {
                this.selected.clear();
                this.selected.add(index);
            }
        }
        this.updateSelBar();
        this.updateSelectionVisuals();
    },

    updateSelBar() {
        const n = this.selected.size;
        if (n > 0) {
            this.selBar.classList.add('active');
            this.selCount.textContent = n + ' selected';
            // Only show rename if exactly 1 selected
            this.selRename.style.display = n === 1 ? '' : 'none';
        } else {
            this.selBar.classList.remove('active');
        }
    },

    updateSelectionVisuals() {
        const items = this.mainEl.querySelectorAll('.fm-grid-item, .fm-list-item');
        items.forEach((el) => {
            const idx = parseInt(el.dataset.index, 10);
            const isSel = this.selected.has(idx);
            el.classList.toggle('selected', isSel);
            const cb = el.querySelector('.fm-checkbox');
            if (cb) cb.innerHTML = isSel ? '&#10003;' : '';
        });
    },

    // Get file icon emoji by extension
    getIcon(entry) {
        if (entry.is_dir) return '&#128193;';
        const name = (entry.name || '').toLowerCase();
        const ext = name.includes('.') ? name.split('.').pop() : '';
        if (['zip', '7z', 'rar', 'tar', 'gz', 'bz2', 'xz', 'nsz'].includes(ext)) return '&#128230;';
        if (['rom', 'bin', 'sfc', 'smc', 'nes', 'gb', 'gbc', 'gba', 'n64', 'z64', 'nds', 'iso', 'cso', 'chd', 'cue', 'pbp'].includes(ext)) return '&#127918;';
        if (['json', 'xml', 'yaml', 'yml', 'toml', 'ini', 'cfg', 'conf'].includes(ext)) return '&#128203;';
        if (['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg', 'ico'].includes(ext)) return '&#128444;';
        if (['txt', 'md', 'log', 'csv'].includes(ext)) return '&#128221;';
        if (['py', 'js', 'sh', 'c', 'cpp', 'h', 'java', 'rs'].includes(ext)) return '&#128196;';
        if (['mp3', 'wav', 'ogg', 'flac', 'aac'].includes(ext)) return '&#127925;';
        if (['mp4', 'mkv', 'avi', 'mov', 'webm'].includes(ext)) return '&#127909;';
        return '&#128196;';
    },

    // Format file size
    formatSize(bytes) {
        if (bytes === undefined || bytes === null) return '';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
    },

    // Format date
    formatDate(ts) {
        if (!ts) return '';
        const d = new Date(ts * 1000);
        const pad = n => n < 10 ? '0' + n : n;
        return d.getFullYear() + '-' + pad(d.getMonth()+1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
    },

    // Build full path for an entry
    entryPath(entry) {
        if (this.currentPath === '/') return '/' + entry.name;
        return this.currentPath + '/' + entry.name;
    },

    // Render grid view
    renderGrid() {
        if (this.entries.length === 0) {
            this.contentEl.innerHTML = '<div class="fm-empty">This folder is empty</div>';
            return;
        }
        let html = '<div class="fm-grid">';
        this.entries.forEach((entry, i) => {
            const sel = this.selected.has(i) ? ' selected' : '';
            html += `<div class="fm-grid-item${sel}" data-index="${i}">
                <div class="fm-checkbox">${this.selected.has(i) ? '&#10003;' : ''}</div>
                <span class="fm-icon">${this.getIcon(entry)}</span>
                <span class="fm-name">${escHtml(entry.name)}</span>
            </div>`;
        });
        html += '</div>';
        this.contentEl.innerHTML = html;
    },

    // Render list view
    renderList() {
        if (this.entries.length === 0) {
            this.contentEl.innerHTML = '<div class="fm-empty">This folder is empty</div>';
            return;
        }
        let html = '<div class="fm-list-header"><span>Name</span><span>Size</span><span>Modified</span></div>';
        html += '<div class="fm-list">';
        this.entries.forEach((entry, i) => {
            const sel = this.selected.has(i) ? ' selected' : '';
            html += `<div class="fm-list-item${sel}" data-index="${i}">
                <div class="fm-checkbox">${this.selected.has(i) ? '&#10003;' : ''}</div>
                <span class="fm-icon">${this.getIcon(entry)}</span>
                <span class="fm-name">${escHtml(entry.name)}</span>
                <span class="fm-size">${entry.is_dir ? '' : this.formatSize(entry.size)}</span>
                <span class="fm-modified">${this.formatDate(entry.modified)}</span>
            </div>`;
        });
        html += '</div>';
        this.contentEl.innerHTML = html;
    },

    render() {
        if (this.viewMode === 'grid') {
            this.renderGrid();
        } else {
            this.renderList();
        }
        this.viewToggle.textContent = this.viewMode === 'grid' ? 'List' : 'Grid';
    },

    renderLoading() {
        this.contentEl.innerHTML = '<div class="fm-loading"><div class="spinner"></div> Loading...</div>';
    },

    renderError(msg) {
        this.contentEl.innerHTML = '<div class="fm-error">' + escHtml(msg) + '</div>';
    },

    // --- Actions ---

    async downloadSelected() {
        for (const idx of this.selected) {
            const entry = this.entries[idx];
            if (!entry || entry.is_dir) continue;
            const path = this.entryPath(entry);
            // Trigger browser download
            const a = document.createElement('a');
            a.href = '/api/files/download?path=' + encodeURIComponent(path);
            a.download = entry.name;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }
    },

    async deleteSelected() {
        const indices = Array.from(this.selected);
        const names = indices.map(i => this.entries[i].name);
        const msg = names.length === 1
            ? 'Delete "' + names[0] + '"?'
            : 'Delete ' + names.length + ' items?\\n\\n' + names.slice(0, 5).join('\\n') + (names.length > 5 ? '\\n...' : '');

        this.showConfirmDialog(msg, async () => {
            for (const idx of indices) {
                const entry = this.entries[idx];
                if (!entry) continue;
                try {
                    await fetch('/api/files/delete', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({path: this.entryPath(entry)})
                    });
                } catch(e) {}
            }
            this.selected.clear();
            this.updateSelBar();
            this.navigate(this.currentPath);
        });
    },

    async renameSelected() {
        if (this.selected.size !== 1) return;
        const idx = Array.from(this.selected)[0];
        const entry = this.entries[idx];
        if (!entry) return;

        this.showInputDialog('Rename', entry.name, async (newName) => {
            if (!newName || newName === entry.name) return;
            try {
                await fetch('/api/files/rename', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({path: this.entryPath(entry), name: newName})
                });
                this.selected.clear();
                this.updateSelBar();
                this.navigate(this.currentPath);
            } catch(e) {}
        });
    },

    async createFolder() {
        this.showInputDialog('New Folder', '', async (name) => {
            if (!name) return;
            const folderPath = this.currentPath === '/'
                ? '/' + name
                : this.currentPath + '/' + name;
            try {
                await fetch('/api/files/mkdir', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({path: folderPath})
                });
                this.navigate(this.currentPath);
            } catch(e) {}
        });
    },

    async uploadFiles(files) {
        if (!files || files.length === 0) return;
        this.uploadProgress.classList.add('active');
        const total = files.length;
        let done = 0;

        for (const file of files) {
            this.uploadLabel.textContent = escHtml(file.name);
            this.uploadBarFill.style.width = Math.round((done / total) * 100) + '%';

            const formData = new FormData();
            formData.append('file', file);

            try {
                const xhr = new XMLHttpRequest();
                await new Promise((resolve, reject) => {
                    xhr.open('POST', '/api/files/upload?path=' + encodeURIComponent(this.currentPath));
                    xhr.upload.onprogress = (e) => {
                        if (e.lengthComputable) {
                            const filePct = e.loaded / e.total;
                            const totalPct = ((done + filePct) / total) * 100;
                            this.uploadBarFill.style.width = Math.round(totalPct) + '%';
                        }
                    };
                    xhr.onload = () => resolve();
                    xhr.onerror = () => reject();
                    xhr.send(formData);
                });
            } catch(e) {}
            done++;
        }

        this.uploadBarFill.style.width = '100%';
        setTimeout(() => {
            this.uploadProgress.classList.remove('active');
            this.uploadBarFill.style.width = '0%';
            this.navigate(this.currentPath);
        }, 500);
    },

    // --- Dialogs ---

    showInputDialog(title, defaultValue, onOk) {
        this.modal.innerHTML = `
            <h3>${escHtml(title)}</h3>
            <input type="text" id="fmDialogInput" value="${escAttr(defaultValue || '')}" spellcheck="false" autocomplete="off">
            <div class="fm-modal-buttons">
                <button id="fmDialogCancel">Cancel</button>
                <button id="fmDialogOk" class="primary">OK</button>
            </div>
        `;
        this.modalOverlay.classList.add('active');

        const inp = document.getElementById('fmDialogInput');
        setTimeout(() => {
            inp.focus();
            inp.select();
        }, 50);

        document.getElementById('fmDialogCancel').onclick = () => {
            this.modalOverlay.classList.remove('active');
        };
        document.getElementById('fmDialogOk').onclick = () => {
            this.modalOverlay.classList.remove('active');
            onOk(inp.value.trim());
        };
        inp.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.modalOverlay.classList.remove('active');
                onOk(inp.value.trim());
            } else if (e.key === 'Escape') {
                this.modalOverlay.classList.remove('active');
            }
        });
    },

    showConfirmDialog(message, onOk) {
        this.modal.innerHTML = `
            <h3>Confirm</h3>
            <p>${escHtml(message)}</p>
            <div class="fm-modal-buttons">
                <button id="fmDialogCancel">Cancel</button>
                <button id="fmDialogOk" class="danger">Delete</button>
            </div>
        `;
        this.modalOverlay.classList.add('active');

        document.getElementById('fmDialogCancel').onclick = () => {
            this.modalOverlay.classList.remove('active');
        };
        document.getElementById('fmDialogOk').onclick = () => {
            this.modalOverlay.classList.remove('active');
            onOk();
        };
    },

    // --- Context menu ---

    showContextMenu(x, y, entryIndex) {
        this.contextTarget = entryIndex;
        const entry = this.entries[entryIndex];
        const menu = this.contextMenu;

        // Show/hide "Open" based on type
        const openBtn = menu.querySelector('[data-action="open"]');
        if (entry && entry.is_dir) {
            openBtn.style.display = '';
            openBtn.textContent = 'Open';
        } else {
            openBtn.style.display = 'none';
        }

        // Show/hide download for files only
        const dlBtn = menu.querySelector('[data-action="download"]');
        dlBtn.style.display = (entry && !entry.is_dir) ? '' : 'none';

        menu.classList.add('active');

        // Position within viewport
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        let left = x;
        let top = y;
        // Defer measurement
        requestAnimationFrame(() => {
            const mw = menu.offsetWidth;
            const mh = menu.offsetHeight;
            if (left + mw > vw) left = vw - mw - 4;
            if (top + mh > vh) top = vh - mh - 4;
            if (left < 0) left = 4;
            if (top < 0) top = 4;
            menu.style.left = left + 'px';
            menu.style.top = top + 'px';
        });
    },

    hideContextMenu() {
        this.contextMenu.classList.remove('active');
        this.contextTarget = null;
    },

    handleContextAction(action) {
        const idx = this.contextTarget;
        this.hideContextMenu();
        if (idx === null || idx === undefined) return;
        const entry = this.entries[idx];
        if (!entry) return;

        switch(action) {
            case 'open':
                this.enter(idx);
                break;
            case 'download':
                if (!entry.is_dir) {
                    const a = document.createElement('a');
                    a.href = '/api/files/download?path=' + encodeURIComponent(this.entryPath(entry));
                    a.download = entry.name;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                }
                break;
            case 'rename':
                this.selected.clear();
                this.selected.add(idx);
                this.updateSelBar();
                this.updateSelectionVisuals();
                this.renameSelected();
                break;
            case 'delete':
                this.selected.clear();
                this.selected.add(idx);
                this.updateSelBar();
                this.updateSelectionVisuals();
                this.deleteSelected();
                break;
        }
    }
};

// --- Wire up FM events ---

// Back / Go
fm.backBtn.addEventListener('click', () => fm.goUp());
fm.goBtn.addEventListener('click', () => fm.navigate(fm.addressBar.value.trim()));
fm.addressBar.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        fm.navigate(fm.addressBar.value.trim());
    }
});

// View toggle
fm.viewToggle.addEventListener('click', () => {
    fm.viewMode = fm.viewMode === 'grid' ? 'list' : 'grid';
    fm.render();
});

// Upload button
fm.uploadBtn.addEventListener('click', () => fm.fileInput.click());
fm.fileInput.addEventListener('change', () => {
    if (fm.fileInput.files.length > 0) {
        fm.uploadFiles(Array.from(fm.fileInput.files));
        fm.fileInput.value = '';
    }
});

// New Folder
fm.newFolderBtn.addEventListener('click', () => fm.createFolder());

// Selection bar actions
fm.selDownload.addEventListener('click', () => fm.downloadSelected());
fm.selRename.addEventListener('click', () => fm.renameSelected());
fm.selDelete.addEventListener('click', () => fm.deleteSelected());
fm.selClear.addEventListener('click', () => {
    fm.selected.clear();
    fm.updateSelBar();
    fm.updateSelectionVisuals();
});

// Click handler on file content area (delegation)
fm.mainEl.addEventListener('click', (e) => {
    // Close context menu on any click
    fm.hideContextMenu();

    const item = e.target.closest('.fm-grid-item, .fm-list-item');
    if (!item) {
        // Click on empty space: clear selection
        fm.selected.clear();
        fm.updateSelBar();
        fm.updateSelectionVisuals();
        return;
    }

    const idx = parseInt(item.dataset.index, 10);
    const entry = fm.entries[idx];
    if (!entry) return;

    // Check if clicking the checkbox area
    const cb = item.querySelector('.fm-checkbox');
    const cbClicked = cb && cb.contains(e.target);

    if (cbClicked || e.ctrlKey || e.metaKey) {
        // Toggle selection (additive)
        fm.toggleSelect(idx, true);
    } else if (e.shiftKey && fm.selected.size > 0) {
        // Range selection
        const first = Math.min(...fm.selected);
        const start = Math.min(first, idx);
        const end = Math.max(first, idx);
        for (let i = start; i <= end; i++) fm.selected.add(i);
        fm.updateSelBar();
        fm.updateSelectionVisuals();
    } else {
        // Single click
        if (entry.is_dir && fm.selected.size === 0) {
            // Navigate into folder if nothing selected
            fm.enter(idx);
        } else if (entry.is_dir && fm.selected.has(idx) && fm.selected.size === 1) {
            // Double-purpose: if already selected folder, navigate
            fm.selected.clear();
            fm.updateSelBar();
            fm.enter(idx);
        } else {
            fm.toggleSelect(idx, false);
        }
    }
});

// Double-click to open folder or download file
fm.mainEl.addEventListener('dblclick', (e) => {
    const item = e.target.closest('.fm-grid-item, .fm-list-item');
    if (!item) return;
    const idx = parseInt(item.dataset.index, 10);
    const entry = fm.entries[idx];
    if (!entry) return;

    if (entry.is_dir) {
        fm.selected.clear();
        fm.updateSelBar();
        fm.enter(idx);
    } else {
        // Download on double-click for files
        const a = document.createElement('a');
        a.href = '/api/files/download?path=' + encodeURIComponent(fm.entryPath(entry));
        a.download = entry.name;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }
});

// Right-click / context menu
fm.mainEl.addEventListener('contextmenu', (e) => {
    const item = e.target.closest('.fm-grid-item, .fm-list-item');
    if (!item) return;
    e.preventDefault();
    const idx = parseInt(item.dataset.index, 10);
    fm.showContextMenu(e.clientX, e.clientY, idx);
});

// Long press for mobile context menu
let longPressTimer = null;
let longPressTarget = null;
fm.mainEl.addEventListener('touchstart', (e) => {
    const item = e.target.closest('.fm-grid-item, .fm-list-item');
    if (!item) return;
    longPressTarget = item;
    longPressTimer = setTimeout(() => {
        const idx = parseInt(item.dataset.index, 10);
        const touch = e.touches[0];
        fm.showContextMenu(touch.clientX, touch.clientY, idx);
        longPressTimer = null;
    }, 600);
}, {passive: true});
fm.mainEl.addEventListener('touchend', () => {
    if (longPressTimer) { clearTimeout(longPressTimer); longPressTimer = null; }
});
fm.mainEl.addEventListener('touchmove', () => {
    if (longPressTimer) { clearTimeout(longPressTimer); longPressTimer = null; }
});

// Context menu button clicks
fm.contextMenu.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;
    fm.handleContextAction(btn.dataset.action);
});

// Close context menu on outside click
document.addEventListener('click', (e) => {
    if (!fm.contextMenu.contains(e.target)) {
        fm.hideContextMenu();
    }
});

// Close modal on overlay click (not on modal itself)
fm.modalOverlay.addEventListener('click', (e) => {
    if (e.target === fm.modalOverlay) {
        fm.modalOverlay.classList.remove('active');
    }
});

// Drag and drop
let dragCounter = 0;
fm.mainEl.addEventListener('dragenter', (e) => {
    e.preventDefault();
    dragCounter++;
    fm.dropOverlay.classList.add('active');
    fm.mainEl.classList.add('drag-over');
});
fm.mainEl.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dragCounter--;
    if (dragCounter <= 0) {
        dragCounter = 0;
        fm.dropOverlay.classList.remove('active');
        fm.mainEl.classList.remove('drag-over');
    }
});
fm.mainEl.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
});
fm.mainEl.addEventListener('drop', (e) => {
    e.preventDefault();
    dragCounter = 0;
    fm.dropOverlay.classList.remove('active');
    fm.mainEl.classList.remove('drag-over');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        fm.uploadFiles(Array.from(e.dataTransfer.files));
    }
});

// Also handle drag on the whole document for better UX
document.addEventListener('dragenter', (e) => {
    if (activeTab === 'files') {
        e.preventDefault();
    }
});
document.addEventListener('dragover', (e) => {
    if (activeTab === 'files') {
        e.preventDefault();
    }
});
document.addEventListener('drop', (e) => {
    if (activeTab === 'files') {
        e.preventDefault();
    }
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (activeTab !== 'files') return;
    // Don't handle if typing in an input
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    if (e.key === 'Backspace' || (e.altKey && e.key === 'ArrowUp')) {
        e.preventDefault();
        fm.goUp();
    } else if (e.key === 'Delete') {
        if (fm.selected.size > 0) {
            fm.deleteSelected();
        }
    } else if (e.key === 'F2') {
        if (fm.selected.size === 1) {
            fm.renameSelected();
        }
    } else if (e.key === 'a' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        fm.entries.forEach((_, i) => fm.selected.add(i));
        fm.updateSelBar();
        fm.updateSelectionVisuals();
    } else if (e.key === 'Escape') {
        if (fm.modalOverlay.classList.contains('active')) {
            fm.modalOverlay.classList.remove('active');
        } else if (fm.contextMenu.classList.contains('active')) {
            fm.hideContextMenu();
        } else {
            fm.selected.clear();
            fm.updateSelBar();
            fm.updateSelectionVisuals();
        }
    }
});
</script>
</body>
</html>"""
