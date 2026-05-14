import os, json, time, hashlib, threading, requests, shutil, base64, secrets, hmac, string, copy, traceback
import urllib.parse
from html import escape
from flask import Flask, request, jsonify, redirect, make_response, session, abort
from werkzeug.exceptions import HTTPException

# [VÁ LỖI LỆCH MÚI GIỜ CLOUD]
try:
    os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
    time.tzset()
except: pass

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = "8714375866:AAG9r0aCCFOKtgR6B-LcFYBAnJ7x9yMs-8o"
TELEGRAM_CHAT_ID = "7363320876"
WEB_URL = "https://app-tool-trlp.onrender.com" 

app.secret_key = os.environ.get('SECRET_KEY', hashlib.sha256(b"LVT_SECURE_KEY_2026_VIP_V2").hexdigest())
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

DB_FILE = './database.json'
DB_BACKUP = './database.backup.json'
db_lock = threading.RLock()
api_rate_lock = threading.Lock()

GLOBAL_DB = {}
_last_db_mtime = 0
_last_mtime_check = 0
api_rate_cache = {}
admin_login_attempts = {}

# ========================================================
# CODE SCRIPT VIOLENTMONKEY LÕI (DEFAULT)
# CẢNH BÁO: KHÔNG CẮT BỚT BẤT KỲ DÒNG NÀO
# ========================================================
DEFAULT_OLM_SCRIPT = r"""// ==UserScript==
// @name         OLM GOD MODE VIP - DEV.TIỆP (ULTIMATE MERGE + APEX MINER + ANTI-FREEZE)
// @namespace    http://tampermonkey.net/
// @version      18.1
// @description  Hệ thống bảo vệ đa tầng. Đỉnh cao cuối cùng: Window Bruteforcer (Cào bộ nhớ RAM). Fix lỗi đơ web (100% CPU).
// @author       DEV.TIỆP
// @match        *://olm.vn/*
// @match        *://*.olm.vn/*
// @grant        unsafeWindow
// @grant        GM_addStyle
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @run-at       document-start
// ==/UserScript==

(function() {
    'use strict';

    const Config = {
        VERSION: '18.1',
        API_KEYWORDS: ['get-question', 'get-exam', 'get-test', 'practice', 'kiem-tra', 'chu-de', 'api/question', 'graphql', 'assignment', 'get-question-of-ids', 'get-question?belongs=1']
    };

    const originalCookieGetter = (() => {
        let desc = Object.getOwnPropertyDescriptor(Document.prototype, 'cookie') || Object.getOwnPropertyDescriptor(HTMLDocument.prototype, 'cookie');
        return desc ? desc.get : null;
    })();

    function getRealUsername() {
        let found = "N/A";
        try {
            let rawCookie = originalCookieGetter ? originalCookieGetter.call(document) : document.cookie;
            if (rawCookie) {
                let cookies = rawCookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    let c = cookies[i].trim();
                    if (c.startsWith("username=")) {
                        found = decodeURIComponent(c.substring(9)).replace(/^"|"$/g, '').trim();
                    }
                }
            }
        } catch(e) {}

        if (found === "N/A" || found === "hp_luongvantuyen") {
            try {
                if (typeof unsafeWindow !== 'undefined') {
                    if (unsafeWindow.userData && unsafeWindow.userData.username && unsafeWindow.userData.username !== "hp_luongvantuyen") {
                        found = unsafeWindow.userData.username;
                    } else if (unsafeWindow.__INITIAL_STATE__ && unsafeWindow.__INITIAL_STATE__.currentUser && unsafeWindow.__INITIAL_STATE__.currentUser.username && unsafeWindow.__INITIAL_STATE__.currentUser.username !== "hp_luongvantuyen") {
                        found = unsafeWindow.__INITIAL_STATE__.currentUser.username;
                    }
                }
            } catch(e) {}
        }
        return found;
    }

    let REAL_USERNAME = getRealUsername();

    const SERVER_URL = "https://app-tool-trlp.onrender.com"; 
    let savedKey = GM_getValue('lvt_olm_vip_key', '');

    function generateRobustHWID() {
        let canvas = document.createElement('canvas');
        let ctx = canvas.getContext('2d');
        ctx.textBaseline = "top"; ctx.font = "14px 'Arial'"; ctx.fillStyle = "#f60"; ctx.fillRect(125,1,62,20);
        ctx.fillStyle = "#069"; ctx.fillText("OLM_LVT_VIP", 2, 15); ctx.fillStyle = "rgba(102, 204, 0, 0.7)"; ctx.fillText("OLM_LVT_VIP", 4, 17);
        let b64 = canvas.toDataURL().replace("data:image/png;base64,","");
        let nav = navigator.userAgent + navigator.hardwareConcurrency + navigator.language + screen.width + screen.height;
        let hash = 0;
        let combined = b64 + nav;
        for(let i=0; i<combined.length; i++) {
            hash = ((hash<<5)-hash)+combined.charCodeAt(i);
            hash = hash & hash;
        }
        return "HWID-" + Math.abs(hash).toString(16).toUpperCase();
    }
    
    let deviceId = localStorage.getItem('lvt_olm_hwid_v2') || generateRobustHWID();
    localStorage.setItem('lvt_olm_hwid_v2', deviceId);

    async function secureApiCall(path, bodyObj) {
        let ts = Date.now();
        let msg = bodyObj.key + ts + bodyObj.key;
        let sig = "";
        if (window.crypto && window.crypto.subtle) {
            let encoder = new TextEncoder();
            let hashBuffer = await crypto.subtle.digest('SHA-256', encoder.encode(msg));
            sig = Array.from(new Uint8Array(hashBuffer)).map(b => b.toString(16).padStart(2, '0')).join('');
        }
        bodyObj.timestamp = ts;
        bodyObj.signature = sig;
        bodyObj.olm_name = getRealUsername(); 
        
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: 'POST',
                url: SERVER_URL + path,
                headers: { 'Content-Type': 'application/json' },
                data: JSON.stringify(bodyObj),
                onload: (res) => {
                    try { resolve(JSON.parse(res.responseText)); } 
                    catch(e) { reject("Lỗi phân tích JSON."); }
                },
                onerror: () => reject("Lỗi kết nối mạng.")
            });
        });
    }

    const Utils = {
        decodeBase64(base64) {
            if (!base64) return null;
            try { return new TextDecoder('utf-8').decode(new Uint8Array(atob(base64).split('').map(c => c.charCodeAt(0)))); } 
            catch (e) { return null; }
        },
        createElement(tag, { id, className, style, children, innerHTML, ...attrs } = {}) {
            const el = document.createElement(tag);
            if (id) el.id = id;
            if (className) el.className = className;
            if (style) Object.assign(el.style, style);
            if (innerHTML !== undefined) el.innerHTML = innerHTML;
            Object.keys(attrs).forEach(key => el.setAttribute(key, attrs[key]));
            if (children) children.forEach(child => {
                if (typeof child === 'string') el.appendChild(document.createTextNode(child));
                else if (child instanceof Node) el.appendChild(child);
            });
            return el;
        },
        sleep: (ms) => new Promise(res => setTimeout(res, ms)),
        formatNumber: (num) => (typeof num === 'number' ? num.toLocaleString('vi-VN') : '0'),
        cleanText(str) {
            if (!str) return '';
            return String(str).normalize('NFC').replace(/<[^>]*>?/gm, '').replace(/&nbsp;/gi, ' ')
                .replace(/[\u200B-\u200D\uFEFF]/g, '').replace(/\s+/g, ' ').trim();
        },
        smartMatch(target, keyword) {
            if (!target || !keyword) return false;
            let t = this.cleanText(target).toLowerCase().replace(/\s/g, '');
            let k = this.cleanText(keyword).toLowerCase().replace(/\s/g, '');
            return t && k && (t.includes(k) || k.includes(t));
        }
    };

    const HintParser = {
        _extractTextFromNode(node) {
            let text = '';
            if (!node) return text;
            if (node.text) text += node.text;
            if (node.children && Array.isArray(node.children)) {
                for (let i = 0; i < node.children.length; i++) {
                    text += this._extractTextFromNode(node.children[i]);
                }
            }
            return text;
        },
        parse(question) {
            const hints = [];
            const omniExtract = (obj) => {
                if (!obj || typeof obj !== 'object') return;
                if (obj.correct === true || obj.is_correct === true || obj.is_correct === 1 || obj.isCorrect === true || obj.correct === 1 || obj.correct === "1") {
                    const text = obj.text || obj.content || obj.value || obj.name;
                    if (text && String(text).trim() && String(text) !== "true") {
                        hints.push({ type: 'Hack Đáp Án', content: Utils.cleanText(String(text).replace(/^#/, '')), subIndex: null });
                    }
                }
                ['correctAnswer', 'correct_answer', 'answer', 'correctOption', 'correct_options'].forEach(key => {
                    if (obj[key] !== undefined && obj[key] !== null) {
                        let ans = obj[key];
                        if (typeof ans === 'string' || typeof ans === 'number') {
                            hints.push({ type: 'Hack Kéo/Điền', content: Utils.cleanText(String(ans)), subIndex: null });
                        } else if (Array.isArray(ans)) {
                            ans.forEach(a => {
                                if(a && (typeof a === 'string' || typeof a === 'number')) hints.push({ type: 'Hack Kéo/Điền', content: Utils.cleanText(String(a)), subIndex: null });
                                else if(a && typeof a === 'object') omniExtract(a);
                            });
                        }
                    }
                });
                Object.values(obj).forEach(val => {
                    if (val && typeof val === 'object') omniExtract(val);
                });
            };
            try { omniExtract(question); } catch(e) {}
            const _deepScanLegacy = (node, parentNode = null, q_type = 0) => {
                if (!node || typeof node !== 'object') return;
                let identified = false;
                if (q_type === 10 && node.name === 'group-list' && node.children) {
                    node.children.forEach((listItem, index) => {
                        if (listItem.type !== 'olm-list-item' || !listItem.children) return;
                        const titleNode = listItem.children.find(c => c.type === 'group-title');
                        const title = titleNode ? this._extractTextFromNode(titleNode) : 'Nhóm';
                        const answers = listItem.children.filter(c => c.position === 'group').map(c => this._extractTextFromNode(c)).filter(Boolean);
                        if (answers.length > 0) {
                            hints.push({ type: 'Kéo nhóm', content: Utils.cleanText(`${title}: ${answers.join(', ')}`), subIndex: index + 1 });
                        }
                    });
                    identified = true;
                }
                if (!identified && (q_type === 2 || q_type === 3) && node.type === 'paragraph' && node.children) {
                    const firstChild = node.children[0];
                    if (firstChild && firstChild.text && /^\d+\.\s/.test(firstChild.text.trim())) {
                        const match = firstChild.text.trim().match(/^(\d+)\./);
                        const qNum = match ? match[1] : '0';
                        const inputs = node.children.filter(c => (c.type === 'fillme-input' || c.type === 'olm-input-text') && c.content);
                        if (inputs.length > 0) {
                            inputs.forEach(input => {
                                input.content.split('||').map(s => s.trim()).filter(Boolean).forEach(part => {
                                    hints.push({ type: 'Điền từ', content: Utils.cleanText(part), subIndex: qNum });
                                });
                            });
                            identified = true;
                        }
                    }
                }
                if (!identified && node.correct === true && (node.type === 'olm-list-item' || node.type === 'list-item')) {
                    const text = this._extractTextFromNode(node);
                    if (text && text.trim()) {
                        const type = (node.name === 'true-false' || (parentNode && parentNode.name === 'true-false')) ? 'Đúng/Sai' : 'Trắc nghiệm';
                        hints.push({ type, content: Utils.cleanText(text.replace(/^#/, '')), subIndex: null });
                        identified = true;
                    }
                }
                if (!identified && node.name === 'exp' && (q_type === 18 || q_type === 11) && node.children) {
                    const text = this._extractTextFromNode(node);
                    const cleanText = text.replace(/^Hư[ơớ]ng d[ẫâ]n gi[aả]i:?/i, '').trim();
                    if (cleanText) { hints.push({ type: (q_type === 11) ? 'Chọn từ' : 'Tự luận', content: Utils.cleanText(cleanText), subIndex: null }); identified = true; }
                }
                if (node.children && Array.isArray(node.children)) {
                     for(let i = 0; i < node.children.length; i++) {
                         _deepScanLegacy(node.children[i], node, q_type);
                     }
                }
            };
            if (question.json_content) {
                try {
                    const data = typeof question.json_content === 'string' ? JSON.parse(question.json_content) : question.json_content;
                    if (data && data.root) _deepScanLegacy(data.root, null, question.q_type);
                } catch (e) {}
            }
            if (question.content) {
                const htmlContent = Utils.decodeBase64(question.content);
                if (htmlContent) {
                    const tempDiv = Utils.createElement('div', { innerHTML: htmlContent });
                    tempDiv.querySelectorAll('.correctAnswer, .correct-answer, .HackĐápÁn').forEach(el => {
                        const text = el.textContent;
                        if (text && text.trim()) hints.push({ type: 'Hack Đáp Án', content: Utils.cleanText(text) });
                    });
                    const inputAccept = tempDiv.querySelector('input[data-accept]');
                    if (inputAccept) {
                        (inputAccept.getAttribute('data-accept') || '').split('|').forEach(ans => {
                            if (ans.trim()) hints.push({ type: 'Hack Điền Từ', content: Utils.cleanText(ans) });
                        });
                    }
                    if (question.q_type === 18 || question.q_type === 11) {
                        const explanationDiv = tempDiv.querySelector('.exp .exp-in');
                        if (explanationDiv) {
                            const expText = Array.from(explanationDiv.childNodes).map(n => (n.textContent || '')).filter(Boolean).join('\n');
                            if (expText.trim()) hints.push({ type: 'Tự luận', content: Utils.cleanText(expText) });
                        }
                    }
                }
            }
            const uniqueHints = [];
            const seen = new Set();
            for (let i = 0; i < hints.length; i++) {
                const key = hints[i].content.toLowerCase().replace(/\s+/g, '');
                if (!key || seen.has(key)) continue;
                seen.add(key);
                uniqueHints.push(hints[i]);
            }
            return uniqueHints;
        }
    };

    class StudyPanel {
        constructor() {
            this.isCollapsed = GM_getValue('isPanelCollapsed', false);
            this.position = GM_getValue('panelPosition', { x: window.innerWidth - 470, y: 100 });
            this.container = null; this.header = null; this.summaryBar = null; this.contentArea = null; this.footer = null; this.collapseButton = null;
        }
        init() {
            this.container = this._createPanelContainer();
            this._addEventListeners();
            document.body.appendChild(this.container);
            this.updateCollapseState(true);
        }
        _createPanelContainer() {
            this.contentArea = Utils.createElement('div', { id: 'study-assistant-content' });
            this.collapseButton = Utils.createElement('button', { className: 'study-control-btn', children: ['−'], title: 'Thu gọn/Mở rộng' });
            const closeButton = Utils.createElement('button', { className: 'study-control-btn', children: ['×'], title: 'Đóng panel' });
            closeButton.onclick = () => this.setVisible(false);
            const renderMathButton = Utils.createElement('button', { className: 'study-control-btn', children: ['∑'], title: 'Render lại Toán' });
            renderMathButton.onclick = () => this.finalizeRender();
            const settingsButton = Utils.createElement('button', { className: 'study-control-btn', children: ['⚙'], title: 'Thông tin' });
            settingsButton.onclick = () => { alert(`Study Assistant Pro v${Config.VERSION}\nThiết bị: ${deviceId}\nKey: ${savedKey}`); };
            
            const titleSpan = Utils.createElement('span', {
                className: 'study-header-title',
                children: [ '🎓 Study Assistant Pro', Utils.createElement('span', { className: 'study-status-badge', children: ['NORMAL'] }) ]
            });
            this.header = Utils.createElement('div', {
                className: 'study-assistant-header',
                children: [ titleSpan, Utils.createElement('div', { className: 'study-controls', children: [renderMathButton, settingsButton, this.collapseButton, closeButton] }) ]
            });
            this.summaryBar = Utils.createElement('div', {
                className: 'study-summary',
                children: [
                    Utils.createElement('div', { className: 'summary-pill summary-questions', children: [ Utils.createElement('span', { className: 'summary-label', children: ['Câu hỏi'] }), Utils.createElement('span', { className: 'summary-value', children: ['0'] }) ] }),
                    Utils.createElement('div', { className: 'summary-pill summary-hints', children: [ Utils.createElement('span', { className: 'summary-label', children: ['Gợi ý'] }), Utils.createElement('span', { className: 'summary-value', children: ['0'] }) ] }),
                    Utils.createElement('div', { className: 'summary-pill summary-status', children: [ Utils.createElement('span', { className: 'summary-label', children: ['Trạng thái'] }), Utils.createElement('span', { className: 'summary-value summary-status-text', children: ['Chờ dữ liệu...'] }) ] })
                ]
            });
            this.footer = Utils.createElement('div', {
                className: 'study-footer',
                children: [
                    Utils.createElement('span', { className: 'study-footer-left', children: ['Tiệp Gà Cui • OLM APEX MINER'] }),
                    Utils.createElement('button', { className: 'study-footer-btn', children: ['🧹 Xóa panel'], onclick: () => this.clearData() })
                ]
            });
            return Utils.createElement('div', {
                id: 'study-assistant-container',
                style: { left: `${this.position.x}px`, top: `${this.position.y}px` },
                children: [this.header, this.summaryBar, this.contentArea, this.footer]
            });
        }
        _addEventListeners() {
            this.collapseButton.addEventListener('click', (e) => { e.stopPropagation(); this.toggleCollapse(); });
            this.header.addEventListener('dblclick', () => this.toggleCollapse());
            this.header.addEventListener('click', () => { if (this.isCollapsed) this.toggleCollapse(); });
            this._setupDragEvents();
        }
        _setupDragEvents() {
            let isDragging = false; let startX, startY, initialX, initialY;
            const startDrag = (e) => {
                if (e.target.classList.contains('study-control-btn') || this.isCollapsed) return;
                isDragging = true; this.container.classList.add('dragging');
                const touch = e.touches ? e.touches[0] : e;
                startX = touch.clientX; startY = touch.clientY;
                const rect = this.container.getBoundingClientRect();
                initialX = rect.left; initialY = rect.top;
                document.addEventListener('mousemove', onDrag, { passive: false }); document.addEventListener('touchmove', onDrag, { passive: false });
                document.addEventListener('mouseup', stopDrag); document.addEventListener('touchend', stopDrag);
                e.preventDefault();
            };
            const onDrag = (e) => {
                if (!isDragging) return;
                const touch = e.touches ? e.touches[0] : e;
                let newX = Math.max(10, Math.min(initialX + (touch.clientX - startX), window.innerWidth - this.container.offsetWidth - 10));
                let newY = Math.max(10, Math.min(initialY + (touch.clientY - startY), window.innerHeight - this.container.offsetHeight - 10));
                this.container.style.left = `${newX}px`; this.container.style.top = `${newY}px`;
                e.preventDefault();
            };
            const stopDrag = () => {
                isDragging = false; this.container.classList.remove('dragging');
                document.removeEventListener('mousemove', onDrag); document.removeEventListener('touchmove', onDrag);
                document.removeEventListener('mouseup', stopDrag); document.removeEventListener('touchend', stopDrag);
                this.position = { x: this.container.getBoundingClientRect().left, y: this.container.getBoundingClientRect().top };
                GM_setValue('panelPosition', this.position);
            };
            this.header.addEventListener('mousedown', startDrag); this.header.addEventListener('touchstart', startDrag);
        }
        toggleCollapse() { this.isCollapsed = !this.isCollapsed; this.updateCollapseState(); GM_setValue('isPanelCollapsed', this.isCollapsed); }
        updateCollapseState(isInitial = false) {
            if (!isInitial) this.container.style.transition = 'all 0.25s ease';
            this.container.classList.toggle('collapsed', this.isCollapsed);
            this.collapseButton.innerHTML = this.isCollapsed ? '+' : '−';
            if (!isInitial) setTimeout(() => { this.container.style.transition = ''; }, 260);
        }
        setVisible(isVisible) { if (this.container) this.container.style.display = isVisible ? 'flex' : 'none'; }
        
        clearData() {
            if (!this.contentArea) return;
            this.contentArea.innerHTML = '';
            this.contentArea.appendChild(Utils.createElement('div', { className: 'study-no-data', children: ['🔍 Đang rà quét Hệ thống OLM...'] }));
            this.setSummary({ questionCount: 0, hintCount: 0, statusText: 'Chờ dữ liệu...' });
        }
        
        setSummary({ questionCount, hintCount, statusText }) {
            if (!this.summaryBar) return;
            const qEl = this.summaryBar.querySelector('.summary-questions .summary-value');
            const hEl = this.summaryBar.querySelector('.summary-hints .summary-value');
            const sEl = this.summaryBar.querySelector('.summary-status-text');
            if (qEl) qEl.textContent = Utils.formatNumber(questionCount || 0);
            if (hEl) hEl.textContent = Utils.formatNumber(hintCount || 0);
            if (sEl) sEl.textContent = statusText || 'Đã cập nhật';
        }
        
        appendQuestion(item) {
            if (!this.contentArea) return;
            if (this.contentArea.querySelector('.study-no-data')) this.contentArea.innerHTML = '';

            const hintSpans = item.hints.map(hint => {
                const isHiddenType = (hint.type === 'Hack Đáp Án' || hint.type === 'Trắc nghiệm' || hint.type === 'Đúng/Sai' || (hint.type === 'Điền từ' && hint.subIndex) || hint.type === 'Chọn từ');
                const label = Utils.createElement('span', { className: 'hint-type-label', children: [`[${hint.type}]`], style: { display: isHiddenType ? 'none' : 'inline-block' } });
                const body = Utils.createElement('span', { className: 'hint-text', innerHTML: (hint.content || '').replace(/\n/g, '<br>') });
                return Utils.createElement('li', { children: [label, body], style: { borderLeftColor: (hint.type === 'Hack Đáp Án' || hint.type === 'Hack Kéo/Điền') ? '#facc15' : '#6366f1' } });
            });

            this.contentArea.appendChild(Utils.createElement('div', {
                className: 'study-reference-item',
                children: [
                    Utils.createElement('div', { className: 'study-reference-title', children: [`📝 ${item.title} (${item.hints.length} gợi ý)`] }),
                    Utils.createElement('div', { className: 'study-reference-body', children: [ hintSpans.length > 0 ? Utils.createElement('ul', { children: hintSpans }) : Utils.createElement('div', { style: { color: '#a0aec0', textAlign: 'center', padding: '10px' }, children: ['Không tìm thấy gợi ý cụ thể.'] }) ] })
                ]
            }));
        }
        
        finalizeRender() {
            const render = () => {
                try { if (typeof unsafeWindow.MathJax !== 'undefined' && unsafeWindow.MathJax.typesetPromise) unsafeWindow.MathJax.typesetPromise([this.contentArea]).catch(err => {}); } catch (e) {}
            };
            if (typeof unsafeWindow.MathJax !== 'undefined') { render(); } else {
                unsafeWindow.MathJax = { tex: { inlineMath: [['$', '$'], ['\\(', '\\)']], displayMath: [['$$', '$$'], ['\\[', '\\]']] }, svg: { fontCache: 'global' } };
                const script = Utils.createElement('script', { src: 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js', async: true });
                script.onload = render; document.head.appendChild(script);
            }
        }
    }

    const ApiInterceptor = {
        _initialized: false,
        init(callback) {
            if (this._initialized) return;
            this._initialized = true;
            this._patchFetch(callback);
            this._patchXHR(callback);
        },
        _processResponse(textData, url) {
            try {
                if (!textData || (!textData.includes('{') && !textData.includes('['))) return null;
                const d = JSON.parse(textData);
                let extracted = [];
                const deepExtract = (obj) => {
                    if (!obj || typeof obj !== 'object') return;
                    if (Array.isArray(obj)) obj.forEach(deepExtract);
                    else {
                        if ((obj.q_type !== undefined || obj.question_id !== undefined || obj.id !== undefined) && (obj.content !== undefined || obj.json_content !== undefined || obj.options !== undefined)) {
                            extracted.push(obj);
                        }
                        Object.values(obj).forEach(deepExtract);
                    }
                };
                deepExtract(d);
                if (extracted.length > 0) return extracted;
            } catch (e) {}
            return null;
        },
        _patchFetch(callback) {
            const originalFetch = unsafeWindow.fetch;
            if (!originalFetch) return;
            unsafeWindow.fetch = async (...args) => {
                const response = await originalFetch.apply(this, args);
                const requestUrl = args[0] instanceof Request ? args[0].url : args[0];
                if (response && response.ok) {
                    response.clone().text().then(text => { const qs = this._processResponse(text, requestUrl); if (qs) callback(qs); });
                }
                return response;
            };
        },
        _patchXHR(callback) {
            const originalSend = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.send = function (...args) {
                this.addEventListener('load', () => {
                    if (this.status === 200) { const qs = ApiInterceptor._processResponse(this.responseText, this.responseURL || ''); if (qs) callback(qs); }
                });
                return originalSend.apply(this, args);
            };
        }
    };

    const StudyAssistantManager = {
        isPanelEnabled: GM_getValue('isScriptEnabled', true), 
        panel: null,
        toggleButton: null,
        init() {
            this._injectStyles();
            this.panel = new StudyPanel();
            this.panel.init();
            this.panel.clearData();
            this.toggleButton = this._createMasterToggle();
            this.updateUIState();
            ApiInterceptor.init(this.processApiData.bind(this));
            
            setTimeout(() => {
                if (this.panel && this.panel.contentArea && this.panel.contentArea.querySelector('.study-no-data')) {
                    this.scanReactFiberAndDOM();
                }
            }, 3000);
        },
        
        scanReactFiberAndDOM() {
            let rawQuestions = [];
            
            try {
                if (unsafeWindow.__INITIAL_STATE__ && unsafeWindow.__INITIAL_STATE__.questions) {
                    Object.values(unsafeWindow.__INITIAL_STATE__.questions).forEach(q => rawQuestions.push(q));
                }
            } catch(e) {}

            const elements = document.querySelectorAll('.question-item, div[data-question-id], div[id^="question_"], div[class*="question"]');
            for (let i = 0; i < elements.length; i++) {
                let el = elements[i];
                try {
                    let reactKey = Object.keys(el).find(k => k.startsWith('__reactProps$') || k.startsWith('__reactFiber$'));
                    if (reactKey) {
                        let props = el[reactKey];
                        let qData = JSON.stringify(props);
                        if (qData && (qData.includes('"q_type"') || qData.includes('"question_id"'))) {
                            let parsed = JSON.parse(qData);
                            const extractFiber = (obj) => {
                                if (!obj || typeof obj !== 'object') return;
                                if (Array.isArray(obj)) obj.forEach(extractFiber);
                                else {
                                    if (obj.q_type !== undefined && (obj.content || obj.json_content || obj.options)) {
                                        rawQuestions.push(obj);
                                    }
                                    Object.values(obj).forEach(extractFiber);
                                }
                            };
                            extractFiber(parsed);
                        }
                    }
                } catch(e) {}
            }

            document.querySelectorAll('[data-content], [data-json], [data-react-props]').forEach(el => {
                ['data-content', 'data-json', 'data-react-props'].forEach(attr => {
                    let jsonStr = el.getAttribute(attr);
                    if (jsonStr) {
                        try {
                            let decoded = jsonStr.includes('{') ? jsonStr : Utils.decodeBase64(jsonStr);
                            rawQuestions.push(JSON.parse(decoded));
                        } catch(e) {}
                    }
                });
            });

            try {
                let wKeys = Object.keys(unsafeWindow);
                for (let i = 0; i < wKeys.length; i++) {
                    let key = wKeys[i];
                    try {
                        let val = unsafeWindow[key];
                        if (key.length > 2 && typeof val === 'string' && val.startsWith('ey')) { 
                            let decoded = Utils.decodeBase64(val);
                            if (decoded && decoded.includes('"q_type"')) {
                                let parsed = JSON.parse(decoded);
                                if (parsed) rawQuestions.push(parsed);
                            }
                        }
                    } catch(e){}
                }
            } catch(e) {}
            
            const uniqueQ = [];
            const seenQ = new Set();
            rawQuestions.forEach(q => {
                const qId = q.id || q._id || q.question_id;
                if (qId && !seenQ.has(qId)) {
                    seenQ.add(qId);
                    uniqueQ.push(q);
                }
            });

            if (uniqueQ.length > 0) {
                this.processApiData(uniqueQ);
            } else {
                if (this.panel && this.panel.contentArea) {
                    this.panel.contentArea.innerHTML = '<div class="study-no-data" style="color:#facc15;">⚠️ KHÔNG CÓ ĐÁP ÁN ẨN TRÊN MÁY BẠN!<br><br><span style="font-size:11px;color:#9ca3af;">(OLM dùng Server-Side Validation: Cấu trúc bài này chỉ gửi đáp án về sau khi bạn ấn nộp bài.)</span></div>';
                    this.panel.setSummary({ questionCount: 0, hintCount: 0, statusText: 'Bảo mật máy chủ' });
                }
            }
        },

        updateUIState() {
            this.toggleButton.classList.add('valid');
            if (this.isPanelEnabled) {
                this.toggleButton.innerHTML = '🚀'; this.toggleButton.title = 'Tắt hỗ trợ học tập';
            } else {
                this.toggleButton.innerHTML = '🔓'; this.toggleButton.title = 'Bật hỗ trợ học tập';
            }
            this.panel.setVisible(this.isPanelEnabled);
        },
        _createMasterToggle() {
            const toggle = Utils.createElement('div', { id: 'study-master-toggle' });
            toggle.addEventListener('click', () => {
                this.isPanelEnabled = !this.isPanelEnabled;
                GM_setValue('isScriptEnabled', this.isPanelEnabled);
                this.updateUIState();
            });
            document.body.appendChild(toggle);
            return toggle;
        },
        highlightHintsOnPage(processedQuestions) {
            document.querySelectorAll('[data-highlighted-by-study]').forEach(el => { el.style.backgroundColor = ''; el.style.border = ''; el.style.borderRadius = ''; el.removeAttribute('data-highlighted-by-study'); });
            const domQuestions = Array.from(document.querySelectorAll('.question-item, [data-question-id], div[id^="question_"], div[id^="elm-question-"]'));
            const getNumberFromDom = (container) => {
                if (!container) return null;
                for (const el of container.querySelectorAll('a, strong, span, div, h3, h4')) {
                    const txt = (el.textContent || '').trim();
                    const m = txt.match(/(?:Question|Câu)\s+(\d+)/i);
                    if (m) { const num = parseInt(m[1], 10); if (!isNaN(num)) return num; }
                }
                return null;
            };
            const getAllNumbersFromDom = (container) => {
                const numbers = [];
                if (!container) return numbers;
                for (const el of container.querySelectorAll('a, strong, span, div, h3, h4')) {
                    const txt = (el.textContent || '').trim();
                    const m = txt.match(/(?:Question|Câu)\s+(\d+)/i);
                    if (m) { const num = parseInt(m[1], 10); if (!isNaN(num) && !numbers.includes(num)) numbers.push(num); }
                }
                return numbers.sort((a, b) => a - b);
            };
            processedQuestions.forEach(item => {
                const question = item.question; const hints = item.hints || [];
                if (!hints.length) return;
                let questionElement = (question._id ? document.querySelector(`.question-item[data-id="${question._id}"]`) || document.querySelector(`div[id^="question_${question._id}"]`) : null) 
                                   || (question.id ? document.querySelector(`div[id="elm-question-${question.id}"]`) || document.querySelector(`div[data-id="${question.id}"]`) : null);
                if (!questionElement) return;
                const container = questionElement.closest('.question-item, [data-question-id]') || questionElement;
                if (question.q_type === 21 || question.q_type === 22) {
                    const displayNumbers = getAllNumbersFromDom(container);
                    if (displayNumbers.length > 0) question._displayIndices = displayNumbers;
                } else {
                    let displayIndex = getNumberFromDom(container);
                    if (!displayIndex) { const idx = domQuestions.indexOf(container); if (idx !== -1) displayIndex = idx + 1; }
                    if (displayIndex) question._displayIndex = displayIndex;
                }
                const hintTexts = hints.map(h => h.content).filter(Boolean);
                if (!hintTexts.length) return;
                
                container.querySelectorAll('.answer-option, .option, li, input, textarea, .dragmore, .selecttext').forEach(option => {
                    const optionRaw = option.textContent || option.value || '';
                    if (!optionRaw.trim()) return;
                    
                    if (hintTexts.some(hint => Utils.smartMatch(optionRaw, hint))) {
                        option.style.backgroundColor = 'rgba(72, 187, 120, 0.18)';
                        option.style.border = '2px solid #48bb78'; option.style.borderRadius = '8px';
                        option.style.transition = 'background-color 0.2s ease, transform 0.1s ease';
                        option.setAttribute('data-highlighted-by-study', 'true');
                    }
                });
            });
        },
        async processApiData(rawQuestions) {
            if (!this.isPanelEnabled) return;
            const processed = rawQuestions.map(q => ({ question: q, hints: HintParser.parse(q) }));
            this.highlightHintsOnPage(processed);
            
            const totalHints = processed.reduce((sum, item) => sum + (item.hints?.length || 0), 0);
            this.panel.clearData(); 
            this.panel.setVisible(true);
            this.panel.setSummary({ questionCount: processed.length, hintCount: totalHints, statusText: 'Hack thành công!' });
            
            if (totalHints === 0) {
                this.panel.contentArea.innerHTML = '<div class="study-no-data" style="color:#facc15;">⚠️ KHÔNG CÓ ĐÁP ÁN ẨN TRÊN MÁY BẠN!<br><br><span style="font-size:11px;color:#9ca3af;">(OLM dùng Server-Side Validation: Cấu trúc bài này chỉ gửi đáp án về sau khi bạn ấn nộp bài.)</span></div>';
                return;
            }

            let fallbackIndex = 1;
            for (const item of processed) {
                const q = item.question;
                const baseTitle = (q.title && String(q.title).trim()) || (q._id ? `ID: ${String(q._id).slice(-4)}` : (q.id || '?'));
                if (!item.hints.some(h => h.subIndex)) {
                    const displayIndex = q._displayIndex || fallbackIndex++;
                    if (item.hints.length > 0) this.panel.appendQuestion({ title: `Câu ${displayIndex}: ${baseTitle}`, hints: item.hints });
                } else {
                    const groupedHints = {};
                    item.hints.forEach(hint => { const idx = hint.subIndex || 'general'; if (!groupedHints[idx]) groupedHints[idx] = []; groupedHints[idx].push(hint); });
                    const displayIndices = q._displayIndices || []; let subIndexCounter = 0;
                    for (const subIndex in groupedHints) {
                        const hintsForPanel = groupedHints[subIndex];
                        if (hintsForPanel.length === 0) continue;
                        let displayIndex = (subIndex !== 'general' && !isNaN(parseInt(subIndex))) ? subIndex : (displayIndices.length > 0 ? (displayIndices[subIndexCounter] || (displayIndices[0] + subIndexCounter)) : (q._displayIndex || fallbackIndex) + subIndexCounter);
                        if (hintsForPanel.length > 1 && hintsForPanel.every(h => h.type === 'Hack Điền Từ' || h.type === 'Điền từ')) { hintsForPanel[0].content = hintsForPanel.map(h => h.content).join(' | '); hintsForPanel.splice(1); }
                        this.panel.appendQuestion({ title: `Câu ${displayIndex}: ${baseTitle}`, hints: hintsForPanel });
                        subIndexCounter++;
                    }
                    fallbackIndex += subIndexCounter;
                }
                await Utils.sleep(8);
            }
        },
        _injectStyles() {
            GM_addStyle(`
                #study-assistant-container { font-family: system-ui, -apple-system, sans-serif; position: fixed; width: 460px; height: 520px; min-height: 220px; max-height: 80vh; border-radius: 18px; z-index: 10001; display: flex; flex-direction: column; overflow: hidden; background: radial-gradient(circle at top left, rgba(94, 234, 212, 0.25), transparent 55%), radial-gradient(circle at bottom right, rgba(129, 140, 248, 0.3), transparent 55%), linear-gradient(145deg, #020617, #020617); box-shadow: 0 18px 45px rgba(15, 23, 42, 0.85), 0 0 0 1px rgba(148, 163, 184, 0.3); border: 1px solid rgba(148, 163, 184, 0.65); backdrop-filter: blur(14px); color: #e5e7eb; }
                #study-assistant-container::before { content: ''; position: absolute; inset: -40%; background: radial-gradient(circle at 0% 0%, rgba(59, 130, 246, 0.4), transparent 60%), radial-gradient(circle at 100% 100%, rgba(244, 114, 182, 0.35), transparent 60%); opacity: 0.35; filter: blur(32px); z-index: -1; }
                #study-assistant-container.dragging { transition: none !important; cursor: grabbing !important; }
                .study-assistant-header { display: flex; justify-content: space-between; align-items: center; padding: 0 18px; height: 58px; cursor: move; flex-shrink: 0; background: linear-gradient(to right, rgba(15, 23, 42, 0.9), rgba(15, 23, 42, 0.6)); border-bottom: 1px solid rgba(148, 163, 184, 0.4); user-select: none; }
                .study-header-title { background: linear-gradient(135deg, #60a5fa, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 14px; font-weight: 700; display: flex; align-items: center; gap: 6px; }
                .study-status-badge { background: #22c55e; color: white; padding: 2px 6px; border-radius: 999px; font-size: 9px; font-weight: 800; text-transform: uppercase; }
                .study-controls { display: flex; gap: 6px; }
                .study-control-btn { width: 30px; height: 30px; border-radius: 10px; border: none; cursor: pointer; background: radial-gradient(circle at 30% 0, rgba(248, 250, 252, 0.08), transparent 60%), rgba(15, 23, 42, 0.9); color: #9ca3af; font-size: 15px; display: flex; align-items: center; justify-content: center; }
                .study-control-btn:hover { color: #e5e7eb; box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.6); background: rgba(15, 23, 42, 1); }
                #study-assistant-content { padding: 12px 14px 10px; flex: 1; overflow-y: auto; position: relative; }
                #study-assistant-content::-webkit-scrollbar { width: 6px; }
                #study-assistant-content::-webkit-scrollbar-thumb { background: linear-gradient(135deg, #6366f1, #a855f7); border-radius: 999px; }
                .study-summary { display: flex; gap: 8px; padding: 8px 12px 6px; background: linear-gradient(to right, rgba(15, 23, 42, 0.9), rgba(15, 23, 42, 0.75)); border-bottom: 1px solid rgba(148, 163, 184, 0.35); flex-shrink: 0; }
                .summary-pill { flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 6px 9px; border-radius: 10px; border: 1px solid rgba(148, 163, 184, 0.6); }
                .summary-questions { border-color: rgba(59, 130, 246, 0.75); } .summary-hints { border-color: rgba(16, 185, 129, 0.8); } .summary-status { border-style: dashed; }
                .summary-label { font-size: 9px; text-transform: uppercase; color: #9ca3af; margin-bottom: 2px; } .summary-value { font-size: 13px; font-weight: 600; color: #e5e7eb; }
                .study-reference-item { margin-bottom: 10px; padding: 11px 10px; background: rgba(15, 23, 42, 0.92); border-radius: 12px; border: 1px solid rgba(148, 163, 184, 0.5); }
                .study-reference-title { font-weight: 600; font-size: 13px; margin-bottom: 6px; }
                .study-reference-body ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px; }
                .study-reference-body li { display: flex; gap: 6px; padding: 6px 8px; background: rgba(15, 23, 42, 0.9); border-radius: 9px; border-left: 2px solid #6366f1; font-size: 12px; }
                .hint-type-label { font-size: 10px; border-radius: 999px; background: rgba(55, 65, 81, 0.9); padding: 2px 5px; flex-shrink: 0; color: #facc15; font-weight: bold; }
                .hint-text { line-height: 1.4; color: #facc15; }
                .study-no-data { text-align: center; padding: 40px 16px; color: #9ca3af; font-size: 13px; }
                .study-footer { height: 32px; padding: 4px 10px 6px; display: flex; align-items: center; justify-content: space-between; border-top: 1px solid rgba(148, 163, 184, 0.4); font-size: 11px; color: #9ca3af; }
                .study-footer-btn { border: 1px solid rgba(248, 113, 113, 0.6); padding: 4px 8px; border-radius: 999px; background: rgba(220, 38, 38, 0.15); color: #fecaca; cursor: pointer; }
                #study-master-toggle { position: fixed; bottom: 20px; right: 20px; width: 58px; height: 58px; border-radius: 50%; cursor: pointer; z-index: 9999; display: flex; align-items: center; justify-content: center; font-size: 26px; color: white; background: linear-gradient(145deg, #6366f1, #7c3aed); box-shadow: 0 14px 28px rgba(79, 70, 229, 0.55); border: 2px solid rgba(255, 255, 255, 0.2); }
                #study-master-toggle.valid { background: linear-gradient(145deg, #22c55e, #16a34a); box-shadow: 0 14px 28px rgba(34, 197, 94, 0.6); }
                #study-assistant-container.collapsed { width: 60px !important; height: 60px !important; min-height: 0; border-radius: 16px; }
                #study-assistant-container.collapsed .study-assistant-header { cursor: pointer; }
                #study-assistant-container.collapsed .study-header-title, #study-assistant-container.collapsed #study-assistant-content, #study-assistant-container.collapsed .study-controls, #study-assistant-container.collapsed .study-summary, #study-assistant-container.collapsed .study-footer { display: none; }
            `);
        }
    };

    function initVipHackSystem(activeKey) {
        const CORE_URL = 'https://fakemoithu.io.vn/core.js';
        let cachedCore = GM_getValue('tiep_core_cache', '');
        const currentUrl = window.location.href;
        const isTargetPage = currentUrl.includes('/chu-de/') || currentUrl.includes('/bai-kiem-tra/') || currentUrl.includes('/video') || currentUrl.includes('/luyen-tap');

        function injectScript(scriptContent) {
            const scriptTag = document.createElement('script');
            const fusedMask = `
            (function() {
                const TARGET = "hp_luongvantuyen";
                try {
                    const cookieDesc = Object.getOwnPropertyDescriptor(Document.prototype, 'cookie') || Object.getOwnPropertyDescriptor(HTMLDocument.prototype, 'cookie');
                    if (cookieDesc && cookieDesc.get) {
                        Object.defineProperty(document, 'cookie', {
                            get: function() {
                                let c = cookieDesc.get.call(this);
                                if (c && c.includes('username=')) return c.replace(/username=[^;]+/, 'username=' + TARGET);
                                return c ? c + '; username=' + TARGET : 'username=' + TARGET;
                            },
                            set: function(v) { cookieDesc.set.call(this, v); }
                        });
                    }
                    const origGet = Storage.prototype.getItem;
                    Storage.prototype.getItem = function(k) {
                        let v = origGet.call(this, k);
                        if (v && typeof v === 'string' && v.includes('"username"')) return v.replace(/"username":"[^"]+"/, '"username":"' + TARGET + '"');
                        return v;
                    };
                    const origParse = JSON.parse;
                    JSON.parse = function(text, reviver) {
                        let obj = origParse(text, reviver);
                        if (obj && typeof obj === 'object') {
                            if (obj.username) obj.username = TARGET;
                            if (obj.data && obj.data.username) obj.data.username = TARGET;
                            if (obj.account && obj.account.username) obj.account.username = TARGET;
                        }
                        return obj;
                    };
                    if (window.userData) window.userData.username = TARGET;
                } catch(e) {}
            })();\n\n`;
            scriptTag.textContent = fusedMask + scriptContent;
            (document.head || document.documentElement).appendChild(scriptTag);
            scriptTag.remove();
        }

        GM_xmlhttpRequest({
            method: 'GET',
            url: CORE_URL + '?t=' + new Date().getTime(),
            onload: function(res) {
                if (res.status === 200 && res.responseText !== cachedCore) {
                    GM_setValue('tiep_core_cache', res.responseText);
                    if (!cachedCore) {
                        if (isTargetPage) injectScript(res.responseText);
                    }
                }
            }
        });

        if (cachedCore) {
            if (isTargetPage) injectScript(cachedCore);
        }
    }

    let urlParams = new URLSearchParams(window.location.search);
    let webKey = urlParams.get('lvt_key');
    if (webKey) {
        GM_setValue('lvt_olm_vip_key', webKey);
        savedKey = webKey;
        window.history.replaceState(null, null, window.location.pathname);
    }

    if (savedKey) {
        secureApiCall('/api/check', { key: savedKey, deviceId: deviceId }).then(res => {
            if (res.status === 'success') {
                let keyType = (res.key_type || 'NORMAL').toUpperCase();
                if (keyType === 'VIP') {
                    initVipHackSystem(savedKey);
                } else {
                    StudyAssistantManager.init();
                }
            }
        }).catch(e => {
            console.log("LỖI KẾT NỐI MÁY CHỦ BẢO MẬT");
        });
    }

})();"""

# ========================================================
# DATABASE FUNCTIONS
# ========================================================
def load_db():
    global GLOBAL_DB, _last_db_mtime, _last_mtime_check
    now = time.time()
    with db_lock:
        if now - _last_mtime_check > 1.0:
            try: current_mtime = os.path.getmtime(DB_FILE)
            except OSError: current_mtime = 0
            _last_mtime_check = now
        else: current_mtime = _last_db_mtime

        if current_mtime > _last_db_mtime or not GLOBAL_DB:
            if not os.path.exists(DB_FILE) and os.path.exists(DB_BACKUP): shutil.copy2(DB_BACKUP, DB_FILE)
            data = None
            if os.path.exists(DB_FILE):
                try:
                    with open(DB_FILE, 'r', encoding='utf-8') as f: data = json.load(f)
                except Exception: pass
            if not data: data = {}
            try:
                data.setdefault("keys", {})
                data.setdefault("tg_auth_ids", {TELEGRAM_CHAT_ID: {"exp": "permanent", "banned_until": 0}})
                data.setdefault("banned_ips", [])
                data.setdefault("settings", {})
                data.setdefault("banned_olms", {})
                if "maintenance_until" not in data["settings"]: data["settings"]["maintenance_until"] = 0
                if "global_notice" not in data["settings"]: data["settings"]["global_notice"] = ""
                if "violentmonkey_script" not in data["settings"]: data["settings"]["violentmonkey_script"] = DEFAULT_OLM_SCRIPT
                GLOBAL_DB = data
                _last_db_mtime = current_mtime
            except Exception: pass
        return GLOBAL_DB

def save_db(db=None):
    global _last_db_mtime
    if db is None: db = GLOBAL_DB
    with db_lock:
        try: 
            db_str = json.dumps(db, indent=2, ensure_ascii=False)
            temp_file = DB_FILE + f'.{int(time.time() * 1000)}.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f: 
                f.write(db_str)
                f.flush()
                os.fsync(f.fileno()) # [VÁ LỖI MẤT DỮ LIỆU]: Ghi đồng bộ an toàn
            os.replace(temp_file, DB_FILE)
            shutil.copy2(DB_FILE, DB_BACKUP)
            _last_db_mtime = os.path.getmtime(DB_FILE)
        except: pass

def generate_secure_key(prefix="", is_vip=False):
    chars = string.ascii_letters + string.digits
    safe_chars = ''.join([c for c in chars if c not in 'IlO0'])
    rand_str = ''.join(secrets.choice(safe_chars) for _ in range(12))
    t_vip = "VIP" if is_vip else "NOR"
    if prefix: return f"{prefix}-{t_vip}-{rand_str}"
    return f"LVT-{t_vip}-{rand_str}"

def get_real_ip():
    try:
        if request.headers.get("CF-Connecting-IP"): return request.headers.get("CF-Connecting-IP")
        if request.headers.getlist("X-Forwarded-For"): return request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
        return request.remote_addr
    except: return "Unknown_IP"

def safe_int(val, default=0):
    try: return int(val)
    except: return default

# ========================================================
# SECURITY & MIDDLEWARE
# ========================================================
@app.before_request
def firewall():
    db = load_db()
    if get_real_ip() in set(db.get("banned_ips", [])): return "BLOCKED", 403

def check_api_rate_limit(ip):
    try:
        now = time.time()
        with api_rate_lock:
            # [VÁ LỖI MEMORY LEAK]: Dọn dẹp cache cũ an toàn hơn
            if len(api_rate_cache) > 5000: 
                keys_to_del = [k for k, v in api_rate_cache.items() if not v or now - v[-1] > 60]
                for k in keys_to_del: api_rate_cache.pop(k, None)
                if len(api_rate_cache) > 5000: api_rate_cache.clear()
            
            history = api_rate_cache.get(ip, [])
            history = [t for t in history if now - t < 5] 
            if len(history) >= 20: return False
            history.append(now)
            api_rate_cache[ip] = history
            return True
    except: return True

# ========================================================
# TELEGRAM MINI APP - UI ĐẸP & CHỨC NĂNG ADMIN MỚI
# ========================================================
@app.route('/')
def home():
    return redirect('/telegram_mini_app')

@app.route('/telegram_mini_app')
def mini_app():
    h = """<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;800&display=swap');body{background:#0f111a;color:#fff;font-family:'Be Vietnam Pro',sans-serif;margin:0;padding:15px;-webkit-tap-highlight-color:transparent}.s{display:none;animation:f .3s ease}.s.a{display:block}@keyframes f{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}.btn-neon{background:linear-gradient(90deg,#00ffcc,#0099ff);color:#000;font-weight:900;box-shadow:0 0 15px rgba(0,255,204,0.4);border:none;padding:15px;border-radius:12px;width:100%;font-size:15px;text-transform:uppercase;transition:.3s;cursor:pointer}.btn-neon:active{transform:scale(.95)}.inp{width:100%;box-sizing:border-box;background:#1a1d29;border:1px solid rgba(255,255,255,.1);color:#fff;padding:14px;border-radius:12px;margin-bottom:15px;font-family:inherit}.inp:focus{outline:none;border-color:#00ffcc}.m-i{background:linear-gradient(135deg,#1a1d29,#232736);border:1px solid rgba(255,255,255,.05);border-radius:16px;padding:18px;display:flex;align-items:center;margin-bottom:15px;cursor:pointer;transition:all .3s ease;box-shadow:0 8px 20px rgba(0,0,0,0.4)}.m-i:hover{transform:translateY(-3px);border-color:rgba(0,255,204,0.3);box-shadow:0 12px 25px rgba(0,255,204,0.15)}.m-i:active{transform:scale(.96)}.ic{width:50px;height:50px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:22px;margin-right:18px;box-shadow:inset 0 0 10px rgba(255,255,255,.1)}.b-b{background:rgba(255,255,255,.1);border:none;padding:10px 15px;border-radius:10px;color:#fff;font-weight:600;margin-bottom:15px;display:inline-flex;align-items:center;gap:8px;cursor:pointer}.glass-panel{background:rgba(26,29,41,0.8);border:1px solid rgba(255,255,255,.1);border-radius:16px;padding:20px;backdrop-filter:blur(10px);margin-bottom:15px}.c-d{background:linear-gradient(135deg,#1a1d29,#232736);border:1px solid rgba(0,255,204,0.3);border-radius:14px;padding:15px;margin-bottom:12px;font-size:13px;box-shadow:0 5px 15px rgba(0,255,204,0.05)}</style></head><body>
    <div id="s-auth" class="s a"><div style="text-align:center;margin:60px 0 40px"><i class="fas fa-shield-alt" style="font-size:70px;color:#00ffcc;text-shadow:0 0 20px #00ffcc"></i><h2 style="color:#00ffcc;margin-top:20px;font-weight:900">HỆ THỐNG QUẢN TRỊ</h2><p style="color:#8892b0;font-size:14px">Vui lòng xác thực ID truy cập hệ thống</p></div><div class="glass-panel"><input type="text" id="t-id" class="inp" placeholder="Nhập ID Telegram được cấp phép"><button class="btn-neon" onclick="auth()">XÁC THỰC NGAY</button></div></div>
    
    <div id="s-menu" class="s"><div class="glass-panel" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:25px"><div><div style="color:#8892b0;font-size:11px;text-transform:uppercase;letter-spacing:1px">Đang dùng ID</div><b id="d-id" style="color:#00ffcc;font-size:18px"></b></div><div style="text-align:right"><div id="d-exp" style="color:#ffcc00;font-size:12px;margin-bottom:5px;font-weight:bold"></div><button style="background:rgba(239,68,68,0.15);color:#ef4444;border:1px solid rgba(239,68,68,0.3);padding:6px 12px;border-radius:8px;font-weight:bold;cursor:pointer" onclick="lout()"><i class="fas fa-sign-out-alt"></i> Thoát</button></div></div>
    <div class="m-i" onclick="n('s-act')"><div class="ic" style="background:linear-gradient(135deg,#bd00ff,#7c3aed);color:#fff"><i class="fas fa-rocket"></i></div><div><b style="font-size:16px;color:#fff">Kích Hoạt Key</b><div style="font-size:12px;color:#8892b0;margin-top:4px">Chỉ định Key vào tài khoản OLM</div></div></div>
    <div class="m-i" onclick="n('s-list');loadK()"><div class="ic" style="background:linear-gradient(135deg,#00ffcc,#3b82f6);color:#000"><i class="fas fa-list"></i></div><div><b style="font-size:16px;color:#fff">Quản Lý Key Kích Hoạt</b><div style="font-size:12px;color:#8892b0;margin-top:4px">Xem danh sách Key đã liên kết</div></div></div>
    <div class="m-i" onclick="n('s-cre')"><div class="ic" style="background:linear-gradient(135deg,#ffcc00,#f97316);color:#000"><i class="fas fa-key"></i></div><div><b style="font-size:16px;color:#fff">Tạo Key Mới</b><div style="font-size:12px;color:#8892b0;margin-top:4px">Tạo mã Key VIP/Thường tự động</div></div></div>
    <div class="m-i" onclick="n('s-scr')"><div class="ic" style="background:linear-gradient(135deg,#3b82f6,#2563eb);color:#fff"><i class="fas fa-code"></i></div><div><b style="font-size:16px;color:#fff">Nạp Script Gốc</b><div style="font-size:12px;color:#8892b0;margin-top:4px">Thay đổi mã nguồn Violentmonkey lõi</div></div></div>
    <div class="m-i" onclick="n('s-ban')"><div class="ic" style="background:linear-gradient(135deg,#ef4444,#b91c1c);color:#fff"><i class="fas fa-user-slash"></i></div><div><b style="font-size:16px;color:#fff">Chặn Định Danh OLM</b><div style="font-size:12px;color:#8892b0;margin-top:4px">Cấm tài khoản OLM dùng Tool</div></div></div>
    <div class="m-i" onclick="getL()"><div class="ic" style="background:linear-gradient(135deg,#a855f7,#7e22ce);color:#fff"><i class="fas fa-download"></i></div><div><b style="font-size:16px;color:#fff">Lấy Script Loader</b><div style="font-size:12px;color:#8892b0;margin-top:4px">Copy code ẩn nạp vào trình duyệt</div></div></div>
    <div class="m-i" onclick="n('s-sys')"><div class="ic" style="background:linear-gradient(135deg,#f97316,#ea580c);color:#fff"><i class="fas fa-cogs"></i></div><div><b style="font-size:16px;color:#fff">Hệ Thống & Bảo Trì</b><div style="font-size:12px;color:#8892b0;margin-top:4px">Set thời gian bảo trì, Gửi thông báo</div></div></div></div>
    
    <div id="s-act" class="s"><button class="b-b" onclick="n('s-menu')"><i class="fas fa-arrow-left"></i> Về Menu</button><h3 style="color:#bd00ff;margin-top:0;font-weight:900"><i class="fas fa-rocket"></i> KÍCH HOẠT KEY</h3><div class="glass-panel" style="border-color:rgba(189,0,255,0.3)"><input type="text" id="a-k" class="inp" placeholder="Nhập mã Key"><input type="text" id="a-o" class="inp" placeholder="Nhập tài khoản OLM khách"><button class="btn-neon" style="background:linear-gradient(90deg,#bd00ff,#7c3aed);color:#fff" onclick="actK()">XÁC NHẬN KÍCH HOẠT</button></div></div>
    
    <div id="s-list" class="s"><button class="b-b" onclick="n('s-menu')"><i class="fas fa-arrow-left"></i> Về Menu</button><h3 style="color:#00ffcc;margin-top:0;font-weight:900"><i class="fas fa-list"></i> KEY ĐÃ KÍCH HOẠT</h3><div id="k-c"></div></div>
    
    <div id="s-cre" class="s"><button class="b-b" onclick="n('s-menu')"><i class="fas fa-arrow-left"></i> Về Menu</button><h3 style="color:#ffcc00;margin-top:0;font-weight:900"><i class="fas fa-key"></i> TẠO KEY</h3><div class="glass-panel" style="border-color:rgba(255,204,0,0.3)"><div style="display:flex;gap:10px"><input type="number" id="c-q" class="inp" value="1" placeholder="Số lượng"><input type="number" id="c-d" class="inp" value="1" placeholder="Thời gian"></div><select id="c-u" class="inp"><option value="m">Phút</option><option value="h">Giờ</option><option value="d" selected>Ngày</option><option value="p">Vĩnh viễn</option></select><div style="display:flex;align-items:center;gap:10px;margin-bottom:15px;background:rgba(0,0,0,0.2);padding:10px;border-radius:10px"><input type="checkbox" id="c-v" style="width:20px;height:20px;accent-color:#bd00ff"><label style="color:#ffcc00;font-weight:bold">Tạo Key VIP PRO</label></div><button class="btn-neon" style="background:linear-gradient(90deg,#ffcc00,#f97316)" onclick="creK()">TẠO NGAY</button></div></div>
    
    <div id="s-scr" class="s"><button class="b-b" onclick="n('s-menu')"><i class="fas fa-arrow-left"></i> Về Menu</button><h3 style="color:#3b82f6;margin-top:0;font-weight:900"><i class="fas fa-code"></i> SCRIPT LÕI GỐC</h3><div class="glass-panel" style="border-color:rgba(59,130,246,0.3)"><textarea id="s-c" class="inp" rows="12" style="font-family:monospace;font-size:11px;background:#000" placeholder="// ==UserScript=="></textarea><button class="btn-neon" style="background:linear-gradient(90deg,#3b82f6,#2563eb);color:#fff" onclick="upS()">LƯU VÀ XUẤT BẢN CODE</button></div></div>
    
    <div id="s-ban" class="s"><button class="b-b" onclick="n('s-menu')"><i class="fas fa-arrow-left"></i> Về Menu</button><h3 style="color:#ef4444;margin-top:0;font-weight:900"><i class="fas fa-user-slash"></i> CHẶN OLM</h3><div class="glass-panel" style="border-color:rgba(239,68,68,0.3)"><input type="text" id="b-o" class="inp" placeholder="Tên OLM cần chặn"><div style="display:flex;gap:10px"><input type="number" id="b-d" class="inp" value="1"><select id="b-u" class="inp"><option value="m">Phút</option><option value="h">Giờ</option><option value="d" selected>Ngày</option><option value="p">Vĩnh viễn</option></select></div><button class="btn-neon" style="background:linear-gradient(90deg,#ef4444,#b91c1c);color:#fff" onclick="banO()">XÁC NHẬN CHẶN</button></div></div>
    
    <div id="s-sys" class="s"><button class="b-b" onclick="n('s-menu')"><i class="fas fa-arrow-left"></i> Về Menu</button><h3 style="color:#f97316;margin-top:0;font-weight:900"><i class="fas fa-cogs"></i> HỆ THỐNG</h3><div class="glass-panel" style="border-color:rgba(249,115,22,0.3);margin-bottom:15px"><h4 style="color:#fff;margin-top:0">Thông Báo Global</h4><textarea id="sy-m" class="inp" rows="3" placeholder="Nhập thông báo gửi đến các Client..."></textarea><button class="btn-neon" style="background:linear-gradient(90deg,#ffcc00,#f97316)" onclick="sN()">GỬI THÔNG BÁO</button></div><div class="glass-panel" style="border-color:rgba(239,68,68,0.3)"><h4 style="color:#ef4444;margin-top:0">Chế Độ Bảo Trì</h4><div style="display:flex;gap:10px"><input type="number" id="m-d" class="inp" value="0" placeholder="0 để tắt bảo trì"><select id="m-u" class="inp"><option value="m">Phút</option><option value="h" selected>Giờ</option><option value="d">Ngày</option></select></div><button class="btn-neon" style="background:linear-gradient(90deg,#ef4444,#b91c1c);color:#fff" onclick="sM()">CẬP NHẬT BẢO TRÌ</button></div></div>
    
    <script>let tid=localStorage.getItem('t_id');let tmr;function n(id){document.querySelectorAll('.s').forEach(e=>e.classList.remove('a'));document.getElementById(id).classList.add('a')}function api(u,d,cb){Swal.showLoading();fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tid:tid,...d})}).then(r=>r.json()).then(r=>{Swal.close();if(r.banned){localStorage.removeItem('t_id');clearInterval(tmr);Swal.fire({icon:'error',title:'BỊ CẤM',html:'Tài khoản Admin của bạn đã bị khóa tạm thời.<br>Mở khóa sau: <b id="cd" style="color:#ef4444"></b>',allowOutsideClick:false,background:'#1a1d29',color:'#fff'});setInterval(()=>{let rem=r.exp-Date.now();if(rem<=0)location.reload();let h=Math.floor((rem%86400000)/3600000),m=Math.floor((rem%3600000)/60000),s=Math.floor((rem%60000)/1000);document.getElementById('cd').innerText=`${h}h ${m}m ${s}s`},1000);return}if(r.e)return Swal.fire({title:'Lỗi',text:r.m,icon:'error',background:'#1a1d29',color:'#fff'});cb(r)})}function chk(){if(!tid)return;api('/api/tg/chk',{},r=>{document.getElementById('d-id').innerText=tid;document.getElementById('d-exp').innerText='HSD Admin: '+(r.exp==='permanent'?'Vĩnh viễn':new Date(r.exp).toLocaleString());n('s-menu');if(!tmr)tmr=setInterval(chk,15000)})}function auth(){tid=document.getElementById('t-id').value;if(!tid)return;localStorage.setItem('t_id',tid);chk()}function lout(){localStorage.removeItem('t_id');clearInterval(tmr);location.reload()}function actK(){api('/api/tg/act',{k:document.getElementById('a-k').value,o:document.getElementById('a-o').value},r=>{Swal.fire({title:'KÍCH HOẠT THÀNH CÔNG',html:`Hệ thống nhận diện Key: <b style="color:${r.t==='VIP'?'#bd00ff':'#00ffcc'}">${r.t}</b><br>Đã chỉ định cho OLM: <b style="color:#ffcc00">${r.o}</b>`,icon:'success',background:'#1a1d29',color:'#fff'});document.getElementById('a-k').value='';document.getElementById('a-o').value=''})}function loadK(){api('/api/tg/get_k',{},r=>{let h='';r.d.forEach(k=>{let stHtml=k.s==='active'?'<span style="color:#22c55e"><i class="fas fa-check-circle"></i> Hoạt động</span>':'<span style="color:#ef4444"><i class="fas fa-times-circle"></i> Bị khóa</span>';let vHtml=k.v?'<span style="background:rgba(189,0,255,0.2);color:#bd00ff;padding:4px 8px;border-radius:6px;font-size:10px;font-weight:900;border:1px solid #bd00ff">VIP PRO</span>':'<span style="background:rgba(0,255,204,0.2);color:#00ffcc;padding:4px 8px;border-radius:6px;font-size:10px;font-weight:900;border:1px solid #00ffcc">THƯỜNG</span>';h+=`<div class="c-d"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><b style="color:#00ffcc;font-size:16px;cursor:pointer" onclick="navigator.clipboard.writeText('${k.k}');Swal.fire({toast:true,position:'top',icon:'success',title:'Đã Copy',showConfirmButton:false,timer:1000,background:'#111',color:'#0f0'})">${k.k.substring(0,10)}... <i class="fas fa-copy"></i></b> ${vHtml}</div><div style="color:#8892b0;font-size:13px;display:flex;justify-content:space-between;margin-bottom:5px"><span>Thiết bị: <b style="color:#fff">${k.d_c}/${k.m_d}</b></span> ${stHtml}</div><div style="color:#8892b0;font-size:13px;margin-bottom:8px">HSD: <b style="color:#fff">${k.e}</b></div><div style="background:rgba(255,204,0,0.1);color:#ffcc00;padding:8px;border-radius:8px;font-size:13px;text-align:center;border:1px dashed rgba(255,204,0,0.3)">Chỉ định OLM: <b style="font-size:14px">${k.o}</b></div></div>`});document.getElementById('k-c').innerHTML=h||'<div style="text-align:center;color:#8892b0;padding:30px;background:rgba(0,0,0,0.2);border-radius:12px">Danh sách trống</div>'})}function creK(){api('/api/tg/cre',{q:document.getElementById('c-q').value,d:document.getElementById('c-d').value,u:document.getElementById('c-u').value,v:document.getElementById('c-v').checked},r=>{let ks=r.k.map(x=>`<div style="background:#000;color:#00ffcc;padding:10px;margin:5px 0;border-radius:8px;font-family:monospace;font-size:14px;border:1px solid #333;cursor:pointer" onclick="navigator.clipboard.writeText('${x}');Swal.fire({toast:true,position:'top',icon:'success',title:'Đã Copy',showConfirmButton:false,timer:1000,background:'#111',color:'#0f0'})">${x}</div>`).join('');Swal.fire({title:'ĐÃ TẠO XONG',html:`<div style="text-align:left;max-height:250px;overflow-y:auto;padding-right:5px">${ks}</div><p style="font-size:12px;color:#aaa;margin-top:10px">Bấm vào key để Copy</p>`,background:'#1a1d29',color:'#fff'})})}function upS(){api('/api/tg/scr',{s:document.getElementById('s-c').value},r=>Swal.fire({title:'Xong',text:'Lưu và xuất bản Script thành công!',icon:'success',background:'#1a1d29',color:'#fff'}))}function banO(){api('/api/tg/ban_o',{o:document.getElementById('b-o').value,d:document.getElementById('b-d').value,u:document.getElementById('b-u').value},r=>Swal.fire({title:'Xong',text:'Đã cấm tài khoản OLM',icon:'success',background:'#1a1d29',color:'#fff'}))}function sN(){api('/api/tg/sys',{a:'n',m:document.getElementById('sy-m').value},r=>Swal.fire({title:'Xong',text:'Đã đẩy thông báo tới toàn bộ Client',icon:'success',background:'#1a1d29',color:'#fff'}))}function sM(){api('/api/tg/sys',{a:'m',d:document.getElementById('m-d').value,u:document.getElementById('m-u').value},r=>Swal.fire({title:'Xong',text:'Đã cập nhật chế độ bảo trì',icon:'success',background:'#1a1d29',color:'#fff'}))}function getL(){api('/api/tg/ld',{},r=>{navigator.clipboard.writeText(r.c);Swal.fire({title:'LẤY CODE THÀNH CÔNG',html:'<p style="font-size:14px;color:#aaa">Code ẩn đã được tự động Copy vào khay nhớ tạm. Hãy tạo file mới và Dán ngay vào Violentmonkey để sử dụng.</p>',icon:'success',background:'#1a1d29',color:'#fff',confirmButtonColor:'#00ffcc'})})}if(tid)chk();</script></body></html>"""
    return make_response(h)

# ========================================================
# ADMIN API LOGIC
# ========================================================
def c_t(d):
    t = d.get('tid')
    if not t: return False, {"e":True,"m":"Vui lòng xác thực ID!"}
    db = load_db()
    if t not in db["tg_auth_ids"]: return False, {"e":True,"m":"ID của bạn chưa được cấp phép truy cập!"}
    u = db["tg_auth_ids"][t]
    now = int(time.time()*1000)
    b = u.get("banned_until",0)
    if b == "permanent" or (isinstance(b,int) and b > now): return False, {"banned":True,"exp":b}
    e = u.get("exp")
    if e != "permanent" and e < now: return False, {"e":True,"m":"ID của bạn đã hết hạn quyền Admin!"}
    return True, u

@app.route('/api/tg/chk', methods=['POST'])
def tg_chk():
    if not check_api_rate_limit(get_real_ip()): return jsonify({"e":True,"m":"Spam API"}), 429
    v, r = c_t(request.json)
    return jsonify({"exp": r.get("exp")} if v else r)

@app.route('/api/tg/act', methods=['POST'])
def tg_act():
    if not check_api_rate_limit(get_real_ip()): return jsonify({"e":True,"m":"Spam API"}), 429
    v, r = c_t(request.json)
    if not v: return jsonify(r)
    k, o = request.json.get('k','').strip(), request.json.get('o','').strip()
    if not k or not o: return jsonify({"e":True,"m":"Vui lòng nhập đầy đủ mã Key và Tên OLM!"})
    db = load_db()
    with db_lock:
        if k not in db["keys"]: return jsonify({"e":True,"m":"Mã Key không tồn tại trên hệ thống máy chủ!"})
        kd = db["keys"][k]
        if kd.get("bound_olm"): return jsonify({"e":True,"m":"Lỗi: Key này đã được kích hoạt và chỉ định cho OLM khác trước đó!"})
        kd["bound_olm"] = o
        if kd.get("exp") == "pending": kd["exp"] = int(time.time()*1000) + kd.get("durationMs",0)
        save_db(db)
        return jsonify({"t": "VIP" if kd.get("vip") else "THƯỜNG", "o": o})

@app.route('/api/tg/get_k', methods=['POST'])
def tg_gk():
    if not check_api_rate_limit(get_real_ip()): return jsonify({"e":True,"m":"Spam API"}), 429
    v, r = c_t(request.json)
    if not v: return jsonify(r)
    db = load_db()
    now = int(time.time()*1000)
    res = []
    for k, d in sorted(db["keys"].items(), key=lambda x: x[1].get('exp',0) if isinstance(x[1].get('exp'),int) else 9e12, reverse=True):
        if not d.get("bound_olm"): continue
        e = d.get("exp")
        es = "Vĩnh viễn" if e=="permanent" else ("Hết hạn" if e<now else time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(e/1000)))
        res.append({
            "k": k, "e": es, "o": d.get("bound_olm"), "s": d.get("status"), 
            "v": d.get("vip"), "d_c": len(d.get("devices",[])), "m_d": d.get("maxDevices", 1)
        })
    return jsonify({"d": res})

@app.route('/api/tg/cre', methods=['POST'])
def tg_cre():
    if not check_api_rate_limit(get_real_ip()): return jsonify({"e":True,"m":"Spam API"}), 429
    v, r = c_t(request.json)
    if not v: return jsonify(r)
    j = request.json
    q, d, u, vi = int(j.get('q',1)), int(j.get('d',1)), j.get('u','d'), j.get('v',False)
    db = load_db()
    res = []
    with db_lock:
        for _ in range(q):
            nk = generate_secure_key("", vi)
            db["keys"][nk] = {"exp":"pending","bound_olm":"","status":"active","vip":vi,"maxDevices":1,"devices":[]}
            if u != 'p': db["keys"][nk]["durationMs"] = d * {"m":60000,"h":3600000,"d":86400000}.get(u,86400000)
            else: db["keys"][nk]["exp"] = "permanent"
            res.append(nk)
        save_db(db)
    return jsonify({"k": res})

@app.route('/api/tg/scr', methods=['POST'])
def tg_scr():
    v, r = c_t(request.json)
    if not v: return jsonify(r)
    db = load_db()
    with db_lock:
        db.setdefault("settings",{})["violentmonkey_script"] = request.json.get('s','')
        save_db(db)
    return jsonify({"s":1})

@app.route('/api/tg/ban_o', methods=['POST'])
def tg_bo():
    v, r = c_t(request.json)
    if not v: return jsonify(r)
    j = request.json
    o, d, u = j.get('o',''), int(j.get('d',1)), j.get('u','d')
    if not o: return jsonify({"e":True,"m":"Chưa nhập tên OLM"})
    db = load_db()
    with db_lock:
        e = "permanent" if u=='p' else int(time.time()*1000) + d * {"m":60000,"h":3600000,"d":86400000}.get(u,86400000)
        db.setdefault("banned_olms",{})[o] = e
        save_db(db)
    return jsonify({"s":1})

@app.route('/api/tg/sys', methods=['POST'])
def tg_sys():
    v, r = c_t(request.json)
    if not v: return jsonify(r)
    j = request.json
    db = load_db()
    with db_lock:
        if j.get('a') == 'n': db.setdefault("settings",{})["global_notice"] = j.get('m','')
        else:
            d = int(j.get('d',0))
            db.setdefault("settings",{})["maintenance_until"] = 0 if d<=0 else int(time.time()*1000) + d * {"m":60000,"h":3600000,"d":86400000}.get(j.get('u'),3600000)
        save_db(db)
    return jsonify({"s":1})

# ========================================================
# HỆ THỐNG MÃ HÓA LOADER SCRIPT BẢO MẬT
# ========================================================
@app.route('/api/tg/ld', methods=['POST'])
def tg_ld():
    v, r = c_t(request.json)
    if not v: return jsonify(r)
    
    # [VÁ LỖI XSS/BASE64 JS]: Sử dụng encodeURIComponent để tránh lỗi font UTF-8 tiếng việt
    js = f"""(function(){{let U=location.origin;let k=localStorage.getItem('_vk_lvt');function go(){{let m=document.cookie.match(/username=([^;]+)/);if(m)return decodeURIComponent(m[1]).replace(/"/g,'');if(window.userData&&window.userData.username)return window.userData.username;return 'N/A';}}if(!k){{k=prompt('HỆ THỐNG BẢO MẬT OLM LVT\\n\\nVUI LÒNG NHẬP MÃ KEY ĐÃ ĐƯỢC ADMIN KÍCH HOẠT:');if(k)localStorage.setItem('_vk_lvt',k);else return;}}GM_xmlhttpRequest({{method:'POST',url:'{request.host_url}api/v/l',headers:{{'Content-Type':'application/json'}},data:JSON.stringify({{k:k,o:go()}}),onload:function(r){{try{{let d=JSON.parse(r.responseText);if(d.e){{alert('LỖI HỆ THỐNG:\\n'+d.m);if(d.c)localStorage.removeItem('_vk_lvt');return;}}if(d.mn){{alert('HỆ THỐNG ĐANG BẢO TRÌ ĐẾN:\\n'+d.mt);return;}}if(d.nt&&localStorage.getItem('_vn_lvt')!==d.nt){{let n=document.createElement('div');n.style.cssText='position:fixed;top:20px;left:50%;transform:translateX(-50%);background:rgba(10,10,15,0.95);color:#ffcc00;padding:25px;border:2px solid #ffcc00;border-radius:15px;z-index:9999999;text-align:center;min-width:300px;box-shadow:0 0 30px rgba(255,204,0,0.3);';n.innerHTML=`<h3 style="margin-top:0;color:#ffcc00">🔔 THÔNG BÁO TỪ ADMIN</h3><p style="color:#fff;font-size:14px">${{d.nt}}</p><button id='_vnc' style='margin-top:15px;background:#ffcc00;color:#000;border:none;padding:8px 20px;border-radius:8px;font-weight:bold;cursor:pointer'>ĐÃ HIỂU (Ẩn 2 giờ)</button>`;document.body.appendChild(n);document.getElementById('_vnc').onclick=()=>{localStorage.setItem('_vn_lvt',d.nt);setTimeout(()=>localStorage.removeItem('_vn_lvt'),7200000);n.remove()}}}let v_w=localStorage.getItem('_vw_lvt');if(!v_w||(v_w!=='forever'&&Date.now()-parseInt(v_w)>7200000)){{let w=document.createElement('div');w.style.cssText='position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(10,10,15,0.95);border:2px solid #00ffcc;border-radius:15px;padding:25px;z-index:9999999;color:#fff;text-align:center;min-width:300px;box-shadow:0 0 30px rgba(0,255,204,0.3);';w.innerHTML=`<h3 style="color:#00ffcc;margin-top:0">CHÀO MỪNG QUÝ KHÁCH</h3><p style="font-size:14px;color:#ccc;line-height:1.5;">Chào mừng quý khách trải nghiệm dịch vụ của tôi<br>chúc bạn sử dụng vui vẻ nhé<br>có thắc mắc gì bạn hãy liên hệ admin tele : luongtuyen20</p><div style="margin-top:20px;display:flex;gap:10px;justify-content:center;"><button id="_btn_h" style="background:#ffcc00;color:#000;border:none;padding:8px 15px;border-radius:8px;font-weight:bold;cursor:pointer;">Ẩn 2 giờ</button><button id="_btn_c" style="background:#ef4444;color:#fff;border:none;padding:8px 15px;border-radius:8px;font-weight:bold;cursor:pointer;">Đóng vĩnh viễn</button></div>`;document.body.appendChild(w);document.getElementById('_btn_h').onclick=()=>{localStorage.setItem('_vw_lvt',Date.now().toString());w.remove();};document.getElementById('_btn_c').onclick=()=>{localStorage.setItem('_vw_lvt','forever');w.remove();}}}let s=document.createElement('div');s.style.cssText='position:fixed;top:15px;right:15px;background:rgba(10,10,15,0.9);color:#00ffcc;padding:12px;border:1px solid #00ffcc;border-radius:10px;z-index:9999998;font-family:sans-serif;font-size:12px;box-shadow:0 0 15px rgba(0,255,204,0.2)';s.innerHTML=`<b style="color:${{d.kn==='VIP'?'#bd00ff':'#00ffcc'}}">KEY ${{d.kn}} ĐANG CHẠY</b><br><div id='_vt' style="margin:5px 0;color:#ffcc00;font-weight:bold"></div><button id='_vsc' style='width:100%;background:#ef4444;color:#fff;border:none;padding:5px;border-radius:5px;font-size:10px;cursor:pointer'>ĐÓNG BẢNG NÀY</button>`;document.body.appendChild(s);document.getElementById('_vsc').onclick=()=>s.remove();let t_i=setInterval(()=>{if(d.ex==='permanent'){{document.getElementById('_vt').innerText='Hạn dùng: Vĩnh viễn';clearInterval(t_i);return;}}let rm=d.ex-Date.now();if(rm<=0){{alert('KEY ĐÃ HẾT HẠN SỬ DỤNG!');localStorage.removeItem('_vk_lvt');location.reload();}}let hs=Math.floor((rm%86400000)/3600000),ms=Math.floor((rm%3600000)/60000),ss=Math.floor((rm%60000)/1000);document.getElementById('_vt').innerText=`CÒN: ${{hs}}h ${{ms}}p ${{ss}}s`}},1000);new Function(decodeURIComponent(escape(atob(d.p))))();}}catch(e){{console.log('Loader Error');}}}})}})();"""
    # Encode Base64 cho đoạn mã JS trên
    b64 = base64.b64encode(js.encode('utf-8')).decode('utf-8')
    res = f"// ==UserScript==\n// @name         OLM GOD MODE AUTO LOADER\n// @namespace    http://tampermonkey.net/\n// @version      1.0\n// @description  Hệ thống Loader siêu cấp mã hóa tự động kéo lõi script OLM\n// @match        *://olm.vn/*\n// @match        *://*.olm.vn/*\n// @grant        GM_xmlhttpRequest\n// @grant        unsafeWindow\n// @run-at       document-start\n// ==/UserScript==\n\nnew Function(atob('{b64}'))();"
    return jsonify({"c": res})

@app.route('/api/v/l', methods=['POST'])
def v_l():
    if not check_api_rate_limit(get_real_ip()): return jsonify({"e":True,"m":"Spam API","c":False}), 429
    j = request.json
    k, o = j.get('k','').strip(), j.get('o','').strip()
    db = load_db()
    now = int(time.time()*1000)
    
    mnt = db.get("settings",{}).get("maintenance_until",0)
    if mnt > now: return jsonify({"mn":True,"mt":time.strftime("%d/%m/%Y %H:%M", time.localtime(mnt/1000))})
    
    b_o = db.get("banned_olms",{}).get(o,0)
    if b_o == "permanent" or (isinstance(b_o,int) and b_o > now): return jsonify({"e":True,"m":f"Tài khoản OLM [{o}] đã bị Admin chặn truy cập Tool!","c":True})
    
    if k not in db["keys"]: return jsonify({"e":True,"m":"Key không tồn tại trên hệ thống máy chủ!","c":True})
    kd = db["keys"][k]
    
    if kd.get("status") == "banned": return jsonify({"e":True,"m":"Key này đã bị Admin khóa vĩnh viễn do vi phạm!","c":True})
    
    bo = kd.get("bound_olm","")
    if not bo: return jsonify({"e":True,"m":"Key chưa được Admin kích hoạt chỉ định ở Mini App. Vui lòng báo Admin kích hoạt Key cho bạn trước!","c":True})
    if bo.lower() != o.lower() and o != "N/A": return jsonify({"e":True,"m":f"Key này đã được chỉ định bảo mật cho tài khoản OLM: [{bo}]. Bạn không thể dùng cho tài khoản [{o}]!","c":True})
    
    if kd.get("exp") != "permanent" and kd.get("exp") < now: return jsonify({"e":True,"m":"Key của bạn đã hết hạn sử dụng! Vui lòng liên hệ Admin.","c":True})
    
    raw_script = db.get("settings",{}).get("violentmonkey_script", DEFAULT_OLM_SCRIPT)
    lines = raw_script.split('\n')
    body = []
    in_header = False
    for line in lines:
        if line.strip().startswith('// ==UserScript=='): in_header = True
        elif line.strip().startswith('// ==/UserScript=='): in_header = False
        elif not in_header: body.append(line)
    body_str = '\n'.join(body)
    
    scr = base64.b64encode(urllib.parse.quote(body_str).encode('utf-8')).decode('utf-8')
    return jsonify({"p":scr,"kn": "VIP" if kd.get("vip") else "NOR","ex":kd.get("exp"),"nt":db.get("settings",{}).get("global_notice","")})

# ========================================================
# WEB ADMIN BẢO MẬT (QUẢN LÝ ID TELEGRAM)
# ========================================================
@app.route('/admin', methods=['GET', 'POST'])
def admin_p():
    ip = get_real_ip()
    global admin_login_attempts
    now = time.time()
    
    # [VÁ LỖI BẢO MẬT]: Chống dò mật khẩu (Brute-force)
    admin_login_attempts = {k: v for k, v in admin_login_attempts.items() if now - v['time'] < 300} 
    attempts = admin_login_attempts.get(ip, {'count': 0, 'time': now})
    
    if attempts['count'] >= 5:
        return "<script>alert('Bị Khóa Tạm Thời! Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau 5 phút!');window.location.href='/';</script>"

    if request.method == 'POST':
        p = request.form.get('p','')
        if hashlib.sha256(p.encode()).hexdigest() == "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92": 
            session['a'] = 1
            admin_login_attempts.pop(ip, None) # Xóa bộ đếm nếu nhập đúng
            return redirect('/admin')
        
        attempts['count'] += 1
        attempts['time'] = now
        admin_login_attempts[ip] = attempts
        return f"<script>alert('Sai mật khẩu! Bạn còn {5 - attempts['count']} lần thử.');window.history.back();</script>"
    
    if not session.get('a'): 
        return '''<!DOCTYPE html><html lang="vi"><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{background:#0a0a12;color:#fff;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;font-family:sans-serif;}form{background:#1a1d29;padding:30px;border-radius:15px;border:1px solid #00ffcc;box-shadow:0 0 20px rgba(0,255,204,0.2);text-align:center;}input{width:100%;padding:10px;margin-bottom:15px;border-radius:8px;border:1px solid #333;background:#000;color:#fff;box-sizing:border-box;}button{width:100%;padding:12px;background:linear-gradient(90deg,#00ffcc,#0099ff);border:none;border-radius:8px;font-weight:bold;cursor:pointer;}</style></head><body><form method="POST"><h3 style="color:#00ffcc;margin-top:0;">XÁC THỰC QUẢN TRỊ</h3><input type="password" name="p" placeholder="Nhập mã truy cập Web..."><button type="submit">ĐĂNG NHẬP WEB ADMIN</button></form></body></html>'''
    
    db = load_db()
    if request.args.get('act') == 'add':
        tid = request.args.get('t', '').strip()
        dur = safe_int(request.args.get('d', 1))
        unit = request.args.get('u', 'd')
        if tid:
            with db_lock:
                if unit == 'p': e = "permanent"
                else: e = int(time.time()*1000) + dur * {"m":60000,"h":3600000,"d":86400000,"M":2592000000}.get(unit, 86400000)
                db.setdefault("tg_auth_ids",{})[tid] = {"exp":e, "banned_until":0}
                save_db(db)
        return redirect('/admin')
        
    if request.args.get('act') == 'del':
        with db_lock:
            db["tg_auth_ids"].pop(request.args.get('t'), None)
            save_db(db)
        return redirect('/admin')
        
    if request.args.get('act') == 'add_time':
        tid = request.args.get('t')
        dur = safe_int(request.args.get('d', 1))
        unit = request.args.get('u', 'd')
        with db_lock:
            if tid in db.get("tg_auth_ids", {}):
                ud = db["tg_auth_ids"][tid]
                if ud.get("exp") != "permanent":
                    add_ms = dur * {"m":60000,"h":3600000,"d":86400000,"M":2592000000}.get(unit, 0)
                    now_ms = int(time.time()*1000)
                    curr = max(ud.get("exp", now_ms), now_ms)
                    ud["exp"] = curr + add_ms
                save_db(db)
        return redirect('/admin')

    if request.args.get('act') == 'ban':
        tid = request.args.get('t')
        dur = safe_int(request.args.get('d', 1))
        unit = request.args.get('u', 'd')
        with db_lock:
            if tid in db.get("tg_auth_ids", {}):
                if unit == 'p': b = "permanent"
                else: b = int(time.time()*1000) + dur * {"m":60000,"h":3600000,"d":86400000,"M":2592000000}.get(unit, 86400000)
                db["tg_auth_ids"][tid]["banned_until"] = b
                save_db(db)
        return redirect('/admin')
        
    if request.args.get('act') == 'unban':
        tid = request.args.get('t')
        with db_lock:
            if tid in db.get("tg_auth_ids", {}):
                db["tg_auth_ids"][tid]["banned_until"] = 0
                save_db(db)
        return redirect('/admin')

    now = int(time.time()*1000)
    h = """<!DOCTYPE html><html lang="vi"><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Web Admin Quản Lý Truy Cập</title><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>body{background:#0a0a12;color:#fff;font-family:sans-serif;margin:0;padding:20px;} .container{max-width:900px;margin:auto;background:#1a1d29;padding:25px;border-radius:15px;border:1px solid #3b82f6;box-shadow: 0 10px 30px rgba(0,0,0,0.5);} table{width:100%;border-collapse:collapse;margin-top:20px;} th,td{padding:12px;border:1px solid rgba(255,255,255,0.1);text-align:center;} th{background:rgba(59,130,246,0.2);color:#3b82f6;} .btn{padding:8px 12px;border:none;border-radius:6px;cursor:pointer;font-weight:bold;color:#fff;} .btn-add{background:#22c55e;} .btn-del{background:#ef4444;} .btn-ban{background:#f97316;} .inp{padding:8px;border-radius:6px;border:1px solid #333;background:#000;color:#fff;} select.inp{cursor:pointer;}</style></head><body>"""
    h += "<div class='container'><div style='display:flex;justify-content:space-between;align-items:center;'><h2 style='color:#3b82f6;margin:0;'><i class='fab fa-telegram'></i> QUẢN LÝ ID TELEGRAM CẤP PHÉP</h2><a href='/telegram_mini_app' class='btn' style='background:#00ffcc;color:#000;text-decoration:none;'>Mở Mini App</a></div><hr style='border-color:rgba(255,255,255,0.1);margin:20px 0;'>"
    
    h += "<h4><i class='fas fa-plus-circle'></i> THÊM ID TELE MỚI</h4><form action='/admin' style='display:flex;gap:10px;margin-bottom:30px;flex-wrap:wrap;'><input type='hidden' name='act' value='add'><input type='text' name='t' class='inp' placeholder='Nhập ID Tele' required><input type='number' name='d' class='inp' value='1' style='width:100px;'><select name='u' class='inp'><option value='m'>Phút</option><option value='h'>Giờ</option><option value='d' selected>Ngày</option><option value='M'>Tháng</option><option value='p'>Vĩnh viễn</option></select><button class='btn btn-add'>CẤP PHÉP NGAY</button></form>"
    
    h += "<div style='overflow-x:auto;'><table><tr><th>ID TELEGRAM</th><th>TRẠNG THÁI</th><th>HẠN SỬ DỤNG</th><th>THÊM THỜI GIAN</th><th>BAND TẠM THỜI</th><th>XÓA</th></tr>"
    for t, d in db.get("tg_auth_ids",{}).items():
        # [VÁ LỖI XSS]: Escape output HTML
        safe_t = escape(t)
        e = d.get('exp')
        es = "<b style='color:#22c55e;'>Vĩnh viễn</b>" if e == "permanent" else ("<b style='color:#ef4444;'>Hết hạn</b>" if e < now else time.strftime("%d/%m/%Y %H:%M", time.localtime(e/1000)))
        
        b = d.get('banned_until', 0)
        is_ban = b == "permanent" or (isinstance(b, int) and b > now)
        sts = f"<span style='background:rgba(239,68,68,0.2);color:#ef4444;padding:4px 8px;border-radius:4px;'>Bị Band ({'V.Viễn' if b=='permanent' else 'Tạm thời'})</span>" if is_ban else "<span style='background:rgba(34,197,94,0.2);color:#22c55e;padding:4px 8px;border-radius:4px;'>Hoạt động</span>"
        
        frm_add = f"<form action='/admin' style='display:flex;gap:5px;justify-content:center;'><input type='hidden' name='act' value='add_time'><input type='hidden' name='t' value='{safe_t}'><input type='number' name='d' class='inp' style='width:60px;padding:4px;' value='1'><select name='u' class='inp' style='padding:4px;'><option value='m'>P</option><option value='h'>H</option><option value='d' selected>Ngày</option><option value='M'>Tháng</option></select><button class='btn' style='background:#3b82f6;padding:4px 8px;'><i class='fas fa-plus'></i></button></form>" if e != "permanent" else "-"
        
        btn_ban = f"<a href='/admin?act=unban&t={safe_t}' class='btn' style='background:#8b5cf6;text-decoration:none;'>Mở Band</a>" if is_ban else f"<form action='/admin' style='display:flex;gap:5px;justify-content:center;'><input type='hidden' name='act' value='ban'><input type='hidden' name='t' value='{safe_t}'><input type='number' name='d' class='inp' style='width:60px;padding:4px;' value='1'><select name='u' class='inp' style='padding:4px;'><option value='m'>P</option><option value='h'>H</option><option value='d' selected>Ngày</option><option value='M'>Tháng</option><option value='p'>V.Viễn</option></select><button class='btn btn-ban' style='padding:4px 8px;'><i class='fas fa-lock'></i></button></form>"
        
        h += f"<tr><td><b style='color:#00ffcc;'>{safe_t}</b></td><td>{sts}</td><td>{es}</td><td>{frm_add}</td><td>{btn_ban}</td><td><a href='/admin?act=del&t={safe_t}' class='btn btn-del' style='text-decoration:none;' onclick='return confirm(\"Xóa ID này?\")'><i class='fas fa-trash'></i></a></td></tr>"
    
    h += "</table></div></div></body></html>"
    return h

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
