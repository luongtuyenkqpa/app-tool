import os, json, time, random, hashlib, threading, requests, shutil, base64, secrets, hmac, string, copy, traceback
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

# [VÁ LỖI CSS_GLASS]
CSS_GLASS = """
.glass-panel { background: rgba(17, 17, 26, 0.7); backdrop-filter: blur(15px); border: 1px solid rgba(0, 255, 204, 0.3); border-radius: 15px; padding: 30px; box-shadow: 0 0 20px rgba(0, 255, 204, 0.2); max-width: 400px; margin: 50px auto; text-align: center; }
.text-neon { color: #00ffcc; text-shadow: 0 0 10px rgba(0, 255, 204, 0.5); }
.btn-neon { background: linear-gradient(90deg, #00ffcc, #0099ff); border: none; color: #000; font-weight: bold; padding: 10px 20px; border-radius: 8px; width: 100%; transition: 0.3s; }
.btn-neon:hover { transform: scale(1.05); box-shadow: 0 0 15px rgba(0, 255, 204, 0.5); }
"""

# ========================================================
# HỆ THỐNG BOT TELEGRAM & MINI APP CAO CẤP
# ========================================================
TELEGRAM_BOT_TOKEN = "8714375866:AAG9r0aCCFOKtgR6B-LcFYBAnJ7x9yMs-8o"
TELEGRAM_CHAT_ID = "7363320876"
WEB_URL = "https://app-tool-trlp.onrender.com" 

def send_telegram_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    def _send():
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
            requests.post(url, json=payload, timeout=5)
        except: pass
    threading.Thread(target=_send, daemon=True).start()

def send_telegram_backup():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        with open(DB_FILE, 'rb') as f:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"📦 BACKUP DATABASE LVT TOOL\nThời gian: {time.strftime('%d/%m/%Y %H:%M:%S')}"}, files={"document": f}, timeout=10)
    except: pass

def telegram_polling():
    offset = 0
    while True:
        try:
            url_base = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
            res = requests.get(url_base + "/getUpdates", params={"offset": offset, "timeout": 30}, timeout=35).json()
            if res.get("ok"):
                for update in res.get("result", []):
                    offset = update["update_id"] + 1
                    
                    if "message" in update:
                        msg = update["message"]
                        chat_id = str(msg.get("chat", {}).get("id", ""))
                        text = msg.get("text", "").strip()
                        msg_id = msg.get("message_id")
                        user_first_name = msg.get("from", {}).get("first_name", "Khách hàng")
                        
                        if text.startswith("/start"):
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage", json={"chat_id": chat_id, "message_id": msg_id})
                            welcome = f"🌟 <b>HỆ THỐNG BÁN KEY TỰ ĐỘNG</b> 🌟\n\nXin chào <b>{user_first_name}</b>!\nNhấn vào nút bên dưới để Đăng ký/Đăng nhập mua Key và Cài đặt Hack:"
                            keyboard = {"inline_keyboard": [
                                [{"text": "🛒 MỞ ỨNG DỤNG (MUA KEY & HACK)", "web_app": {"url": f"{WEB_URL}/telegram_mini_app"}}]
                            ]}
                            requests.post(url_base + "/sendMessage", json={"chat_id": chat_id, "text": welcome, "parse_mode": "HTML", "reply_markup": keyboard})
                        
                        elif text.startswith("/naptien") and chat_id == TELEGRAM_CHAT_ID:
                            parts = text.split()
                            if len(parts) >= 3:
                                uname = parts[1].lower()
                                try:
                                    amt = int(parts[2])
                                    db = load_db()
                                    with db_lock:
                                        if uname in db.get("users", {}):
                                            db["users"][uname]["balance"] += amt
                                            if db["users"][uname]["balance"] < 0: db["users"][uname]["balance"] = 0
                                            action = "Cộng" if amt >= 0 else "Trừ"
                                            db["users"][uname].setdefault("notices", []).append(f"Admin vừa {action} cho bạn {abs(amt):,}đ")
                                            log_admin_action(db, f"TeleBot: {action} {abs(amt)}đ cho {uname}")
                                            save_db(db)
                                            send_telegram_alert(f"✅ Đã {action} {abs(amt):,}đ cho User: <b>{uname}</b>")
                                        else:
                                            send_telegram_alert(f"❌ Không tìm thấy user: {uname}")
                                except ValueError: send_telegram_alert("❌ Số tiền không hợp lệ!")
                        
                        elif text.startswith("/check") and chat_id == TELEGRAM_CHAT_ID:
                            parts = text.split()
                            if len(parts) >= 2:
                                uname = parts[1].lower()
                                db = load_db()
                                u = db.get("users", {}).get(uname)
                                if u:
                                    keys_info = "".join([f"- <code>{pk['key'][:10]}...</code>\n" for pk in u.get("purchased_keys", [])]) or "Không có key nào."
                                    send_telegram_alert(f"👤 <b>USER: {uname}</b>\n💰 Số dư: {u.get('balance', 0):,}đ\n🔑 <b>Key:</b>\n{keys_info}")
                                else: send_telegram_alert(f"❌ Không tìm thấy user: {uname}")
                        
                        elif text.startswith("// ==UserScript==") and chat_id == TELEGRAM_CHAT_ID:
                            db = load_db()
                            with db_lock:
                                db.setdefault("settings", {})["violentmonkey_script"] = text
                                log_admin_action(db, "TeleBot: Cập nhật Script Gốc")
                                save_db(db)
                            send_telegram_alert("✅ Đã cập nhật và xuất bản Code Violentmonkey mới!")
        except Exception as e: print("LỖI BOT TELE:", str(e))
        time.sleep(2)

threading.Thread(target=telegram_polling, daemon=True).start()

# GLOBAL EXCEPTION CATCHER 
@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException): return e
    error_detail = traceback.format_exc()
    send_telegram_alert(f"<b>CRITICAL CRASH NGĂN CHẶN THÀNH CÔNG:</b>\n<pre>{error_detail[-300:]}</pre>")
    return "Hệ thống đang bảo trì.", 500

# BẢO MẬT FLASK SESSION
app.secret_key = os.environ.get('SECRET_KEY', hashlib.sha256(f"LVT_SECURE_KEY_2026_VIP".encode()).hexdigest())
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True      
app.config['SESSION_COOKIE_HTTPONLY'] = True    

DB_FILE = './database.json'
DB_BACKUP = './database.backup.json'

db_lock = threading.RLock()
api_rate_lock = threading.Lock()

active_sessions = {}
api_rate_cache = {}
used_signatures = {} 
admin_login_attempts = {}

GLOBAL_DB = {}
_last_db_mtime = 0
_last_mtime_check = 0 

# ========================================================
# CORE CONFIG & UTILS
# ========================================================
SHOP_PACKAGES = {
    "TEST_VIP": {"name": "Key Test (VIP)", "price": 10000, "dur_ms": 3600000, "vip": True, "desc": "Trải nghiệm Hack OLM VIP"},
    "7D_VIP": {"name": "7 Ngày (VIP)", "price": 30000, "dur_ms": 604800000, "vip": True, "desc": ""},
    "30D_VIP": {"name": "1 Tháng (VIP)", "price": 100000, "dur_ms": 2592000000, "vip": True, "desc": ""},
    "1Y_VIP": {"name": "1 Năm Học (VIP)", "price": 200000, "dur_ms": 31536000000, "vip": True, "desc": ""},
    "1H_NOR": {"name": "1 Giờ (Thường)", "price": 5000, "dur_ms": 3600000, "vip": False, "desc": "Study Assistant Mở Rộng"},
    "7D_NOR": {"name": "7 Ngày (Thường)", "price": 25000, "dur_ms": 604800000, "vip": False, "desc": "Study Assistant Mở Rộng"},
    "30D_NOR": {"name": "1 Tháng (Thường)", "price": 55000, "dur_ms": 2592000000, "vip": False, "desc": "Study Assistant Mở Rộng"},
    "1Y_NOR": {"name": "1 Năm Học (Thường)", "price": 125000, "dur_ms": 31536000000, "vip": False, "desc": "Study Assistant Mở Rộng"}
}

def safe_int(val, default=0):
    try: return int(val)
    except: return default

def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def swal_redirect(title, text, icon, url):
    return f"""<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #05050A; }}</style></head><body><script>
        Swal.fire({{ title: `{title}`, html: `{text}`, icon: '{icon}', background: '#11111A', color: '#fff', confirmButtonColor: '#00ffcc', allowOutsideClick: false, customClass: {{ popup: 'border border-info' }}
        }}).then(() => {{ window.location.href = '{url}'; }});
    </script></body></html>"""

def swal_back(title, text, icon):
    return f"""<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #05050A; }}</style></head><body><script>
        Swal.fire({{ title: `{title}`, html: `{text}`, icon: '{icon}', background: '#11111A', color: '#fff', confirmButtonColor: '#bd00ff', allowOutsideClick: false, customClass: {{ popup: 'border border-danger' }}
        }}).then(() => {{ window.history.back(); }});
    </script></body></html>"""

def render_template_string_safe(content):
    resp = make_response(content)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp

# ========================================================
# DATABASE ENGINE & MẶC ĐỊNH SCRIPT V18.1 NGUYÊN BẢN
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

    // =========================================================================
    // [PHẦN 0]: HÀM LẤY TÊN TÀI KHOẢN THẬT (ĐÃ TỐI ƯU CHỐNG ĐƠ WEB)
    // =========================================================================
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

    // =========================================================================
    // [PHẦN 1]: CẤU HÌNH API ĐÁM MÂY (VÒNG NGOÀI)
    // =========================================================================
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

    // =========================================================================
    // [PHẦN 2]: MODULE STUDY ASSISTANT (ĐỈNH CAO HACKER V18.0 - APEX MINER)
    // =========================================================================
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
            console.log("[LVT] Khởi động Siêu Máy Quét (React Fiber & State Scanner)...");
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
                console.log("[LVT] Quét thành công " + uniqueQ.length + " câu hỏi từ lõi React & RAM.");
                this.processApiData(uniqueQ);
            } else {
                console.log("[LVT] Scanner không tìm thấy dữ liệu bị giấu.");
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

    // =========================================================================
    // [PHẦN 3]: GIAO DIỆN CHUYỂN HƯỚNG WEB & CẢNH BÁO
    // =========================================================================
    function showWelcomePopup(username, isVIP) {
        if(document.getElementById('tiep-welcome-overlay')) return;
        let overlay = document.createElement('div');
        overlay.id = 'tiep-welcome-overlay';
        overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:2147483647;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(8px);";
        let tierColor = isVIP ? "#bd00ff" : "#00ffcc";
        let tierName = isVIP ? "VIP PRO" : "STANDARD";
        overlay.innerHTML = `
            <div style="background:#0a0a12; border:2px solid ${tierColor}; padding:40px; border-radius:15px; text-align:center; box-shadow:0 0 40px ${isVIP?'rgba(189,0,255,0.4)':'rgba(0,255,204,0.4)'};">
                <div style="font-size:50px; margin-bottom:10px;">🎉</div>
                <h1 style="color:${tierColor}; margin:0 0 15px 0; font-family:sans-serif; letter-spacing:2px;">CHÚC MỪNG</h1>
                <p style="color:#ccc; font-size:16px;">Tài khoản định danh:<br><strong style="color:#ff3366; font-size:24px;">${username}</strong></p>
                <p style="color:#888; font-size:13px; margin-top:15px;">Đăng nhập hệ thống [${tierName}] thành công!</p>
                <button id="tiep-close-welcome" style="margin-top:25px; padding:12px 40px; background:${tierColor}; color:#000; border:none; border-radius:8px; font-weight:900; cursor:pointer;">BẮT ĐẦU SỬ DỤNG</button>
            </div>
        `;
        document.body.appendChild(overlay);
        document.getElementById('tiep-close-welcome').onclick = () => overlay.remove();
    }

    function showKeyPrompt(errorMsg = "", showCountdown = 0) {
        if(document.getElementById('tiep-auth-overlay')) document.getElementById('tiep-auth-overlay').remove();
        const authDiv = document.createElement('div');
        authDiv.id = 'tiep-auth-overlay';
        authDiv.style.cssText = "position:fixed;inset:0;background:rgba(5,5,10,0.98);z-index:2147483647;display:flex;align-items:center;justify-content:center;font-family:sans-serif;";
        authDiv.innerHTML = `
            <div style="background:#0a0a12; border:2px solid #00ffcc; padding:40px; border-radius:15px; text-align:center; width:400px;">
                <h2 style="color:#00ffcc;">OLM VIP PRO</h2>
                <div style="color:#fff; font-size:16px; margin:25px 0; padding:15px; background:rgba(0,255,204,0.1); border:1px solid #00ffcc; border-radius:8px; font-weight:bold;">⚠️ VUI LÒNG ĐĂNG NHẬP KEY<br>Ở WEB ĐỂ SỬ DỤNG</div>
                <div id="tiep-error-msg" style="color:#ff3366; font-size:14px; margin-top:15px; font-weight:bold;">${errorMsg}</div>
                <div style="margin-top:30px;"><a href="${SERVER_URL}" target="_blank" style="color:#00ffcc; font-weight:bold; text-decoration:none; border-bottom:1px dashed #00ffcc;">🌍 ĐI TỚI WEBSITE</a></div>
            </div>
        `;
        (document.body || document.documentElement).appendChild(authDiv);
        
        if (showCountdown > 0) {
            let el = document.getElementById('tiep-error-msg');
            let timer = setInterval(() => {
                let rem = showCountdown - Date.now();
                if (rem <= 0) { clearInterval(timer); window.location.reload(); }
                else {
                    let d = Math.floor(rem / 86400000);
                    let h = Math.floor((rem % 86400000) / 3600000);
                    let m = Math.floor((rem % 3600000) / 60000);
                    let s = Math.floor((rem % 60000) / 1000);
                    el.innerHTML = `${errorMsg}<br><br><span style="color:#fff">Mở khóa sau: ${d} ngày ${h}g ${m}p ${s}s</span>`;
                }
            }, 1000);
        }
    }
    
    function kickUserToWeb(msg, countdownTo = 0) {
        GM_setValue('lvt_olm_vip_key', ''); 
        try {
            let desc = Object.getOwnPropertyDescriptor(Document.prototype, 'cookie') || Object.getOwnPropertyDescriptor(HTMLDocument.prototype, 'cookie');
            if (desc && desc.set) desc.set.call(document, "username=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;");
            else document.cookie = "username=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
        } catch(e) { document.cookie = "username=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;"; }
        sessionStorage.removeItem('tiep_welcomed');

        if (countdownTo > 0) {
            showKeyPrompt(msg, countdownTo);
        } else {
            let kickDiv = document.createElement('div');
            kickDiv.style.cssText = "position:fixed;inset:0;background:rgba(20,0,0,0.98);z-index:2147483647;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff;font-family:sans-serif;text-align:center;padding:20px;";
            kickDiv.innerHTML = `<div style="font-size:60px;margin-bottom:10px;">⚠️</div><h1 style="color:#ff3366;">TRUY CẬP BỊ TỪ CHỐI</h1><p style="color:#ccc;max-width:600px;">${msg}</p>`;
            (document.body || document.documentElement).appendChild(kickDiv);
            setTimeout(() => { window.location.href = window.location.pathname; }, 4000); 
        }
    }

    function showGlobalNotice(msg) {
        if (!msg || localStorage.getItem('lvt_hidden_notice') === msg) return;
        let ndiv = document.createElement('div');
        ndiv.style.cssText = "position:fixed;top:20px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,0.9);border:2px solid #ffcc00;color:#fff;padding:20px;border-radius:10px;z-index:2147483647;box-shadow:0 0 20px rgba(255,204,0,0.5);text-align:center;min-width:300px;";
        ndiv.innerHTML = `
            <h3 style="color:#ffcc00;margin:0 0 10px 0;">🔔 THÔNG BÁO HỆ THỐNG</h3>
            <p>${msg}</p>
            <button id="btn-close-notice" style="margin-top:10px;padding:5px 15px;background:#ffcc00;color:#000;border:none;border-radius:5px;cursor:pointer;font-weight:bold;">ĐÃ HIỂU (ẨN 2H)</button>
        `;
        document.body.appendChild(ndiv);
        document.getElementById('btn-close-notice').onclick = () => {
            localStorage.setItem('lvt_hidden_notice', msg);
            setTimeout(() => localStorage.removeItem('lvt_hidden_notice'), 7200000);
            ndiv.remove();
        };
    }

    // =========================================================================
    // [PHẦN 4]: LÕI HACK CHÍNH & MẶT NẠ DÍNH KÈM (DÀNH CHO KEY VIP)
    // =========================================================================
    function initVipHackSystem(activeKey) {
        const CORE_URL = 'https://fakemoithu.io.vn/core.js';
        let cachedCore = GM_getValue('tiep_core_cache', '');
        const currentUrl = window.location.href;
        const isTargetPage = currentUrl.includes('/chu-de/') || currentUrl.includes('/bai-kiem-tra/') || currentUrl.includes('/video') || currentUrl.includes('/luyen-tap');
        const hasSeenLoader = sessionStorage.getItem('tiep_loader_seen');

        function injectScript(scriptContent) {
            const scriptTag = document.createElement('script');
            const fusedMask = `
            /* [MẶT NẠ FUSION - CHẠY Ở VỊ TRÍ SỐ 0, TRƯỚC LÕI HACK OLM MODE] */
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
                        else { sessionStorage.setItem('tiep_loader_seen', '1'); showMatrixLoader(res.responseText); }
                    }
                }
            }
        });

        if (cachedCore) {
            if (isTargetPage || hasSeenLoader) injectScript(cachedCore);
            else { sessionStorage.setItem('tiep_loader_seen', '1'); showMatrixLoader(cachedCore); }
        }

        function showMatrixLoader(scriptContent) {
            const style = document.createElement('style');
            style.textContent = `@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap'); #tiep-matrix-loader { position: fixed; inset: 0; z-index: 2147483647; background: #020c06; font-family: 'Share Tech Mono', monospace; color: #00ff88; display: flex; align-items: center; justify-content: center; }`;
            document.head.appendChild(style);
            setTimeout(() => {
                let loader = document.getElementById('tiep-matrix-loader');
                if (loader) loader.remove();
                injectScript(scriptContent);
            }, 3000);
        }
        
        setInterval(() => secureApiCall('/api/script_ping', { key: activeKey }).catch(e => {}), 30000);
    }

    // =========================================================================
    // [PHẦN 5]: BỘ KHỞI ĐỘNG CHÍNH (QUYẾT ĐỊNH LOAD MODULE NÀO)
    // =========================================================================
    
    let urlParams = new URLSearchParams(window.location.search);
    let webKey = urlParams.get('lvt_key');
    if (webKey) {
        GM_setValue('lvt_olm_vip_key', webKey);
        savedKey = webKey;
        window.history.replaceState(null, null, window.location.pathname);
    }

    if (savedKey) {
        secureApiCall('/api/check', { key: savedKey, deviceId: deviceId }).then(res => {
            if (res.status === 'maintenance') {
                kickUserToWeb(`🛠 HỆ THỐNG ĐANG BẢO TRÌ BỞI ADMIN`, res.maintenance_until);
                return;
            }
            if (res.status === 'banned_olm') {
                kickUserToWeb(`⛔ TÀI KHOẢN OLM NÀY BỊ ADMIN KHÓA TRUY CẬP TOOL`, res.ban_until);
                return;
            }
            if (res.global_notice) showGlobalNotice(res.global_notice);

            if (res.status === 'success') {
                
                let assignedUser = res.assigned_user || REAL_USERNAME;
                let keyType = (res.key_type || 'NORMAL').toUpperCase();

                setInterval(() => {
                    let currentUserNow = getRealUsername();
                    if (assignedUser && currentUserNow !== "N/A" && currentUserNow !== "hp_luongvantuyen" && currentUserNow !== assignedUser) {
                        secureApiCall('/api/ban_key', { key: savedKey, reason: "Đổi tài khoản trái phép sang: " + currentUserNow });
                        kickUserToWeb(`GIAN LẬN: Cố tình đăng nhập nick lạ [${currentUserNow}]. Key này chỉ định cho [${assignedUser}]. ĐÃ BỊ KHÓA VĨNH VIỄN!`);
                    }
                }, 2000);

                if (res.assigned_user && REAL_USERNAME !== "N/A" && REAL_USERNAME !== "hp_luongvantuyen" && REAL_USERNAME !== res.assigned_user) {
                    secureApiCall('/api/ban_key', { key: savedKey, reason: "Sử dụng sai tài khoản OLM" });
                    kickUserToWeb(`GIAN LẬN: Key này chỉ dành cho tài khoản [${res.assigned_user}]. Bạn đang dùng cho [${REAL_USERNAME}]. Key đã bị Khóa Vĩnh Viễn!`);
                    return;
                }

                if (!sessionStorage.getItem('tiep_welcomed')) {
                    showWelcomePopup(assignedUser, keyType === 'VIP');
                    sessionStorage.setItem('tiep_welcomed', '1');
                }

                if (!res.loader_enabled) {
                    kickUserToWeb("⚠️ ADMIN ĐÃ TẮT HỆ THỐNG SPOOFER CHO KEY NÀY!");
                    return;
                }

                if (keyType === 'VIP') {
                    console.log("[LVT] Kích hoạt Hack VIP (OLM MODE)");
                    initVipHackSystem(savedKey);
                } else {
                    console.log("[LVT] Kích hoạt Hack Thường (Study Assistant)");
                    StudyAssistantManager.init();
                }

            } else {
                kickUserToWeb(res.message);
            }
        }).catch(e => {
            showKeyPrompt("LỖI KẾT NỐI MÁY CHỦ BẢO MẬT");
        });
    } else {
        if (document.readyState === "loading") window.addEventListener('DOMContentLoaded', () => showKeyPrompt());
        else showKeyPrompt();
    }

})();"""

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
            if not data: data = {"users": {}, "keys": {}, "banned_ips": [], "admin_logs": [], "security_alerts": [], "settings": {}, "banned_olms": {}}
            try:
                data.setdefault("users", {})
                data.setdefault("keys", {})
                data.setdefault("banned_ips", [])
                data.setdefault("admin_logs", [])
                data.setdefault("security_alerts", []) 
                data.setdefault("settings", {})
                data.setdefault("banned_olms", {})
                data.setdefault("game_keys", {}) # <--- MỚI THÊM VÀO THEO YÊU CẦU
                
                if "maintenance_until" not in data["settings"]: data["settings"]["maintenance_until"] = 0
                if "global_notice" not in data["settings"]: data["settings"]["global_notice"] = ""
                if "violentmonkey_script" not in data["settings"]: data["settings"]["violentmonkey_script"] = DEFAULT_OLM_SCRIPT
                if "tg_admins" not in data["settings"]: data["settings"]["tg_admins"] = [TELEGRAM_CHAT_ID]
                
                if "admin" not in data["users"]:
                    data["users"]["admin"] = {"password_hash": hash_pwd("120510@"), "role": "admin", "balance": 0, "created_at": int(time.time() * 1000), "ips": [], "purchased_keys": [], "notices": [], "custom_script": 'console.log("HACK OLM BY LVT ĐÃ KÍCH HOẠT!");', "banned_until": 0}
                
                for u in data["users"]:
                    data["users"][u].setdefault("notices", [])
                    data["users"][u].setdefault("custom_script", "")
                    data["users"][u].setdefault("banned_until", 0)

                for k in data["keys"]:
                    data["keys"][k].setdefault("owner", "admin")
                    data["keys"][k].setdefault("violations", 0)
                    data["keys"][k].setdefault("temp_ban_until", 0)
                    data["keys"][k].setdefault("loader_enabled", True)
                    data["keys"][k].setdefault("devices", [])
                    data["keys"][k].setdefault("reset_count", 0) 
                    data["keys"][k].setdefault("bound_olm", "") 
                    data["keys"][k].setdefault("os", "android")
                    data["keys"][k].setdefault("vip", False)
                GLOBAL_DB = data
                _last_db_mtime = current_mtime
            except Exception: pass
        return GLOBAL_DB

def save_db(db=None):
    global _last_db_mtime
    if db is None: db = GLOBAL_DB
    with db_lock:
        try: 
            safe_db = copy.deepcopy(db)
            db_str = json.dumps(safe_db, indent=2, ensure_ascii=False)
        except Exception as e:
            send_telegram_alert(f"Lỗi Serialize DB: {str(e)}")
            return 
            
        temp_file = DB_FILE + f'.{int(time.time() * 1000)}.tmp'
        try:
            with open(temp_file, 'w', encoding='utf-8') as f: 
                f.write(db_str)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, DB_FILE)
            shutil.copy2(DB_FILE, DB_BACKUP)
            _last_db_mtime = os.path.getmtime(DB_FILE)
        except Exception as e: 
            send_telegram_alert(f"LỖI GHI FILE DATABASE CHÍ MẠNG: {str(e)}")
            if os.path.exists(temp_file): os.remove(temp_file)

def generate_secure_key(prefix="", is_vip=False):
    chars = string.ascii_letters + string.digits
    safe_chars = ''.join([c for c in chars if c not in 'IlO0'])
    rand_str = ''.join(secrets.choice(safe_chars) for _ in range(12))
    t_vip = "VIP" if is_vip else "NOR"
    if prefix: return f"{prefix}-{t_vip}-{rand_str}"
    return f"LVT-{t_vip}-{rand_str}"

def generate_game_key_15():
    # Ký tự an toàn chống đoán, 15 ký tự bảo mật cho game
    charset = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(charset) for _ in range(15))

def log_admin_action(db, action_text):
    db.setdefault("admin_logs", []).insert(0, {"time": int(time.time() * 1000), "action": action_text})
    db["admin_logs"] = db["admin_logs"][:100]

def garbage_collector():
    global used_signatures, api_rate_cache
    backup_counter = 0
    while True:
        time.sleep(3600) 
        backup_counter += 1
        now_ms = int(time.time() * 1000)
        try:
            with api_rate_lock:
                to_del_sig = [s for s, t in used_signatures.items() if now_ms - t > 20000]
                for s in to_del_sig: del used_signatures[s]
                if len(used_signatures) > 10000: used_signatures.clear()
                if len(api_rate_cache) > 10000: api_rate_cache.clear()
            
            db = load_db()
            changed = False
            with db_lock:
                for k in list(db.get("keys", {}).keys()):
                    exp = db["keys"][k].get("exp")
                    if exp != "permanent" and exp != "pending":
                        if isinstance(exp, int) and (now_ms - exp) > 604800000:
                            del db["keys"][k]
                            changed = True
                
                for olm_id in list(db.get("banned_olms", {}).keys()):
                    if db["banned_olms"][olm_id] != "permanent" and db["banned_olms"][olm_id] < now_ms:
                        del db["banned_olms"][olm_id]
                        changed = True
                
                if len(db.get("security_alerts", [])) > 100:
                    db["security_alerts"] = db["security_alerts"][:50]
                    changed = True
                    
            if changed: save_db(db)
            
            if backup_counter >= 12:
                send_telegram_backup()
                backup_counter = 0
        except Exception as e: 
            send_telegram_alert(f"Lỗi Garbage Collector: {str(e)}")

threading.Thread(target=garbage_collector, daemon=True).start()

def get_real_ip():
    try:
        if request.headers.get("CF-Connecting-IP"): return request.headers.get("CF-Connecting-IP")
        if request.headers.getlist("X-Forwarded-For"): return request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
        return request.remote_addr
    except: return "Unknown_IP"

@app.before_request
def firewall_and_csrf():
    try:
        db = load_db()
        banned_ips = set(db.get("banned_ips", []))
        ip = get_real_ip()
        if ip in banned_ips: return "⚠️ BẠN ĐÃ BỊ TỪ CHỐI TRUY CẬP BỞI HỆ THỐNG FIREWALL LVT.", 403

        ua = (request.headers.get('User-Agent') or '').lower()
        blocked_bots = ['curl', 'postman', 'python', 'nmap', 'sqlmap', 'masscan', 'zgrab', 'wget', 'urllib', 'nikto']
        if any(bot in ua for bot in blocked_bots): 
            send_telegram_alert(f"Phát hiện Bot/Scanner truy cập trái phép.\nIP: {ip}\nUser-Agent: {ua}")
            return "Firewall Blocked Suspicious Bot/Scanner.", 403
            
        if request.path.startswith("/admin") and request.path not in ["/admin_login", "/login", "/register", "/logout", "/telegram_mini_app", "/api/tg_admin/get_data", "/api/tg_admin/action_user", "/api/tg_admin/create_keys", "/api/tg_admin/ban_olm", "/api/tg_admin/update_script", "/api/tg_admin/system_actions", "/api/tg_app/auth", "/api/tg_app/user_data", "/api/tg_app/buy", "/api/tg_app/init", "/api/verify_hack_key"]:
            if session.get('role') != 'admin':
                return redirect('/admin_login')
    except: pass

@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN' 
    response.headers['X-Content-Type-Options'] = 'nosniff' 
    response.headers['X-XSS-Protection'] = '1; mode=block' 
    return response

@app.errorhandler(404)
def not_found_trap(e):
    return "Not Found", 404

# ========================================================
# TRANG CHỦ (VÁ LỖI NOT FOUND 404 BẠN GỬI)
# ========================================================
@app.route('/')
def home_page():
    html = f"""
    <!DOCTYPE html>
    <html lang="vi" data-bs-theme="dark">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>LVT SYSTEM - TRANG CHỦ</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;800&display=swap');
            body {{ background: #05050A; color: #fff; font-family: 'Be Vietnam Pro', sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
            .container {{ text-align: center; background: rgba(17,17,26,0.8); padding: 40px; border-radius: 20px; border: 1px solid #00ffcc; box-shadow: 0 0 30px rgba(0,255,204,0.1); backdrop-filter: blur(10px); max-width: 400px; width: 90%; }}
            h1 {{ color: #00ffcc; font-weight: 800; margin-bottom: 10px; text-shadow: 0 0 10px rgba(0,255,204,0.5); }}
            p {{ color: #8892b0; font-size: 14px; margin-bottom: 30px; }}
            .btn-action {{ display: block; width: 100%; padding: 15px; margin-bottom: 15px; border-radius: 12px; font-weight: bold; text-decoration: none; transition: 0.3s; box-sizing: border-box; }}
            .btn-tg {{ background: linear-gradient(90deg, #0088cc, #00aaff); color: #fff; border: none; }}
            .btn-tg:hover {{ box-shadow: 0 0 15px rgba(0,170,255,0.5); transform: scale(1.02); }}
            .btn-admin {{ background: transparent; color: #ffcc00; border: 2px solid #ffcc00; }}
            .btn-admin:hover {{ background: rgba(255,204,0,0.1); box-shadow: 0 0 15px rgba(255,204,0,0.3); transform: scale(1.02); }}
        </style>
    </head>
    <body>
        <div class="container">
            <i class="fas fa-shield-alt" style="font-size: 50px; color: #00ffcc; margin-bottom: 20px;"></i>
            <h1>LVT SERVER API</h1>
            <p>Hệ thống máy chủ xử lý & Cấp phát Key bảo mật tự động.</p>
            <a href="https://t.me/tên_bot_của_bạn" class="btn-action btn-tg" target="_blank"><i class="fab fa-telegram"></i> MỞ BOT TELEGRAM</a>
            <a href="/telegram_mini_app" class="btn-action" style="background:#bd00ff; color:#fff; text-decoration:none;"><i class="fas fa-mobile-alt"></i> MỞ MINI APP (WEB)</a>
            <a href="/admin_login" class="btn-action btn-admin"><i class="fas fa-user-shield"></i> DÀNH CHO QUẢN TRỊ VIÊN</a>
        </div>
    </body>
    </html>
    """
    return html

# ========================================================
# API TRẠNG THÁI (CHO WEB CLIENT POLLING BẢO TRÌ & KHÓA)
# ========================================================
@app.route('/api/my_status')
def my_status():
    if 'username' not in session: return jsonify({"logged_in": False})
    db = load_db()
    u = db.get("users", {}).get(session['username'])
    if not u: return jsonify({"logged_in": False})
    mnt = db.get("settings", {}).get("maintenance_until", 0)
    return jsonify({
        "logged_in": True,
        "banned_until": u.get("banned_until", 0),
        "maintenance_until": mnt
    })

# ========================================================
# API SPOOFER & CẤP PHÉP BƠM CODE (CÓ BẢO TRÌ)
# ========================================================
def check_api_rate_limit(ip):
    try:
        now = time.time()
        with api_rate_lock:
            if len(api_rate_cache) > 5000: api_rate_cache.clear()
            history = api_rate_cache.get(ip, [])
            history = [t for t in history if now - t < 5] 
            if len(history) >= 15: return False
            history.append(now)
            api_rate_cache[ip] = history
            return True
    except: return True

def verify_request_signature(data):
    try:
        ts = int(data.get("timestamp", 0))
        sig = data.get("signature", "")
        key = data.get("key", "")
        if abs(int(time.time() * 1000) - ts) > 15000: return False
        global used_signatures
        with api_rate_lock:
            if sig in used_signatures: return False
            used_signatures[sig] = int(time.time() * 1000)
        expected = hashlib.sha256(f"{key}{ts}{key}".encode()).hexdigest()
        return hmac.compare_digest(sig, expected)
    except: return False

def _core_validate(db, key, deviceId=None, req_olm_name="N/A", ip=""):
    now = int(time.time() * 1000)
    
    mnt = db.get("settings", {}).get("maintenance_until", 0)
    if isinstance(mnt, int) and mnt > now:
        return False, "maintenance", mnt
    
    with db_lock:
        banned_olms = db.get("banned_olms", {})
        if req_olm_name != "N/A" and req_olm_name in banned_olms:
            ban_exp = banned_olms[req_olm_name]
            if ban_exp == "permanent" or ban_exp > now:
                return False, "banned_olm", ban_exp

        if key not in db["keys"]: return False, "error", "Mã Key không tồn tại!"
        kd = db["keys"][key]
        if kd.get('status') == 'banned': return False, "error", "TÀI KHOẢN BỊ KHÓA: Key của bạn đã bị Admin ban vĩnh viễn!"
        
        temp_ban = kd.get("temp_ban_until", 0)
        if temp_ban > now:
            rem = (temp_ban - now) // 60000
            return False, "error", f"PHẠT SHARE KEY: Key đang bị khóa tạm thời. Thử lại sau {rem} phút."

        db_changed = False
        if kd.get('exp') == 'pending': 
            kd['exp'] = now + kd.get('durationMs', 0)
            db_changed = True
            
        if kd.get('exp') != 'permanent' and now > kd.get('exp', 0): 
            return False, "error", "KEY HẾT HẠN: Vui lòng lên Web mua Key mới!"
        
        bound_olm = kd.get("bound_olm", "").strip()
        if bound_olm and req_olm_name != "N/A":
            if bound_olm.lower() != req_olm_name.lower():
                kd["status"] = "banned"
                db.setdefault("security_alerts", []).insert(0, {"time": now, "id": ip, "user": req_olm_name, "reason": f"Sử dụng sai định danh"})
                save_db(db)
                return False, "error", f"GIAN LẬN: Key này chỉ dành cho tài khoản [{bound_olm}]. Key đã bị Khóa Vĩnh Viễn!"

        if deviceId:
            devices = kd.setdefault("devices", [])
            if deviceId not in devices:
                if len(devices) >= kd.get("maxDevices", 1): return False, "error", "VƯỢT THIẾT BỊ: Key đã đạt giới hạn thiết bị tối đa!"
                devices.append(deviceId)
                db_changed = True
        
        if db_changed: save_db(db)
        return True, "success", "OK"

@app.route('/api/check', methods=['POST', 'OPTIONS'])
def check_api():
    try:
        ip = get_real_ip()
        if not check_api_rate_limit(ip): return jsonify({"status": "error", "message": "Spam API!"}), 429
        if request.method == 'OPTIONS': return make_response("ok", 200)
        
        data = request.json or {}
        if not verify_request_signature(data):
            return jsonify({"status": "error", "message": "Chữ ký API không hợp lệ. Hãy làm lại theo hướng dẫn!"}), 403

        key = data.get('key', '')[:100]
        deviceId = data.get('deviceId', '')[:100]
        olm_name = data.get('olm_name', 'N/A')[:100]
        
        db = load_db()
        valid, code, msg_or_time = _core_validate(db, key, deviceId, olm_name, ip)
        
        if not valid:
            if code == "maintenance": return jsonify({"status": "maintenance", "maintenance_until": msg_or_time})
            if code == "banned_olm": return jsonify({"status": "banned_olm", "ban_until": msg_or_time})
            return jsonify({"status": "error", "message": msg_or_time}), 400

        is_vip = db["keys"][key].get("vip", False)
        key_type = "VIP" if is_vip else "NORMAL"
        global_notice = db.get("settings", {}).get("global_notice", "")

        return jsonify({
            "status": "success", 
            "loader_enabled": db["keys"][key].get("loader_enabled", True),
            "assigned_user": db["keys"][key].get("bound_olm", ""),
            "key_type": key_type,
            "global_notice": global_notice
        })
    except Exception as e: return jsonify({"status": "error", "message": "Lỗi API Check"}), 500

@app.route('/api/ban_key', methods=['POST', 'OPTIONS'])
def api_ban_key():
    try:
        if request.method == 'OPTIONS': return make_response("ok", 200)
        data = request.json or {}
        key = data.get('key', '')
        db = load_db()
        with db_lock:
            if key in db.get("keys", {}):
                db["keys"][key]["status"] = "banned"
                save_db(db)
        return jsonify({"status": "success"})
    except: return jsonify({"status": "error"}), 500

@app.route('/api/core', methods=['POST', 'OPTIONS'])
def serve_core_payload():
    try:
        ip = get_real_ip()
        if not check_api_rate_limit(ip): return jsonify({"status": "error"}), 429
        if request.method == 'OPTIONS': return make_response("ok", 200)

        data = request.json or {}
        if not verify_request_signature(data): return jsonify({"status": "error"}), 403
        
        key = data.get('key', '')
        deviceId = data.get('deviceId', '')
        olm_name = data.get('olm_name', 'N/A')
        
        db = load_db()
        valid, code, _ = _core_validate(db, key, deviceId, olm_name, ip)
        if not valid: return jsonify({"status": "error"}), 403

        custom_script = db.get("users", {}).get("admin", {}).get("custom_script", "")
        encoded_core = base64.b64encode(custom_script.encode('utf-8')).decode('utf-8')
        reversed_core = encoded_core[::-1]
        return jsonify({"status": "success", "payload": reversed_core})
    except: return jsonify({"status": "error"}), 500

@app.route('/api/script_ping', methods=['POST', 'OPTIONS'])
def script_ping():
    try:
        ip = get_real_ip()
        if not check_api_rate_limit(ip): return "Too Many Requests", 429
        if request.method == 'OPTIONS': return make_response("ok", 200)
        data = request.json or {}
        key = data.get("key")
        db = load_db()
        now = int(time.time() * 1000)
        
        with db_lock:
            if key in db.get("keys", {}):
                kd = db["keys"][key]
                known_ips = kd.setdefault("known_ips", {})
                to_del = [i for i, t in known_ips.items() if now - t > 120000]
                for i in to_del: del known_ips[i]
                
                known_ips[ip] = now
                if len(known_ips) > kd.get("maxDevices", 1):
                    kd["violations"] = kd.get("violations", 0) + 1
                    kd["known_ips"] = {}
                    save_db(db)
                    return "Banned for sharing", 403
                active_sessions[key] = {"ip": ip, "key": key, "last_seen": time.time()}
                return "ok", 200
        return "invalid", 403
    except: return "error", 500

@app.route('/api/script/core_engine.js')
def serve_core_engine():
    db = load_db()
    raw_script = db.get("settings", {}).get("violentmonkey_script", DEFAULT_OLM_SCRIPT)
    lines = raw_script.split('\n')
    body = []
    in_header = False
    for line in lines:
        if line.strip().startswith('// ==UserScript=='): in_header = True
        elif line.strip().startswith('// ==/UserScript=='): in_header = False
        elif not in_header: body.append(line)
    body_str = '\n'.join(body)
    
    b64 = base64.b64encode(body_str.encode('utf-8')).decode('utf-8')
    rev_b64 = b64[::-1]
    
    secure_core = f"""
    (function() {{
        try {{
            const _0x3c = "{rev_b64}";
            const _0x4d = _0x3c.split('').reverse().join('');
            const _0x5e = decodeURIComponent(escape(atob(_0x4d)));
            new Function(_0x5e)(); 
        }} catch(e) {{ console.error("[LVT] Lỗi cấu trúc Core ngầm:", e); }}
    }})();
    """
    resp = make_response(secure_core)
    resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    return resp

@app.route('/api/script/olm_vip.user.js')
def serve_loader_script():
    db = load_db()
    raw_script = db.get("settings", {}).get("violentmonkey_script", DEFAULT_OLM_SCRIPT)
    host_url = WEB_URL if WEB_URL else request.url_root.rstrip('/')
    
    lines = raw_script.split('\n')
    header = []
    in_header = False
    for line in lines:
        if line.strip().startswith('// ==UserScript=='):
            in_header = True; header.append(line)
        elif line.strip().startswith('// ==/UserScript=='):
            header.append(line); in_header = False; break
        elif in_header: header.append(line)
            
    header_str = '\n'.join(header)
    if '@grant        GM_xmlhttpRequest' not in header_str and '@grant GM_xmlhttpRequest' not in header_str:
        header_str = header_str.replace('// ==/UserScript==', '// @grant        GM_xmlhttpRequest\n// ==/UserScript==')
    
    loader_logic = f"""
// =========================================================================
// LOADER BẢO MẬT & KÉO CODE ĐỘNG ĐỈNH CAO BỞI LVT
// =========================================================================
(function() {{
    'use strict';
    if (window.top !== window.self) return;
    console.log("%c[LVT SECURITY]%c Đang khởi động Siêu Loader...", "color:#00ffcc; font-weight:bold; font-size:14px", "color:white");
    
    document.addEventListener('contextmenu', e => e.preventDefault());
    document.addEventListener('keydown', e => {{
        if (e.key === 'F12' || (e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'J' || e.key === 'C')) || (e.ctrlKey && e.key === 'u') || (e.ctrlKey && e.key === 'U')) {{
            e.preventDefault();
        }}
    }});

    GM_xmlhttpRequest({{
        method: 'GET',
        url: '{host_url}/api/script/core_engine.js?t=' + Date.now(),
        onload: function(res) {{
            if (res.status === 200) {{
                try {{ eval(res.responseText); }} catch(e) {{ console.error("[LVT] Lỗi khởi chạy Lõi:", e); }}
            }}
        }}
    }});
}})();
"""
    resp = make_response(header_str + "\n" + loader_logic)
    resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    return resp

# ========================================================
# API & CHỨC NĂNG VÀO KHOANG LÁI (KIWI BROWSER)
# ========================================================
@app.route('/api/verify_hack_key', methods=['POST'])
def verify_hack_key():
    data = request.json or {}
    key = data.get('key', '').strip()
    db = load_db()
    kd = db.get("keys", {}).get(key)
    if not kd: return jsonify({"status": "error", "msg": "Mã Key không tồn tại trong hệ thống!"})
    
    now = int(time.time() * 1000)
    if kd.get("status") == "banned": return jsonify({"status": "error", "msg": "Key đã bị Admin khóa vĩnh viễn do vi phạm!"})
    if kd.get("temp_ban_until", 0) > now: return jsonify({"status": "error", "msg": "Key đang bị phạt khóa tạm thời do dùng nhiều máy!"})
    if kd.get("exp") != "pending" and kd.get("exp") != "permanent" and kd.get("exp") < now:
        return jsonify({"status": "error", "msg": "Key của bạn đã hết hạn sử dụng!"})
        
    return jsonify({"status": "success"})

@app.route('/auto_login_hack')
def auto_login_hack():
    key = request.args.get('key', '').strip()
    if key:
        db = load_db()
        if key in db.get("keys", {}):
            session['active_key'] = key
            return redirect(f'https://olm.vn/?lvt_key={key}')
    return swal_redirect("Lỗi Đăng Nhập", "Mã Key không hợp lệ hoặc đã bị xóa!", "error", "/")

@app.route('/open_hack')
def open_hack_route():
    key = request.args.get('key', '').strip()
    intent_url = f"intent://{request.host}/auto_login_hack?key={key}#Intent;scheme=https;package=com.kiwibrowser.browser;end"
    
    html = f"""
    <!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Sử Dụng Hack OLM</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>body {{ background: #05050A; color: #fff; font-family: sans-serif; }}</style></head>
    <body class="d-flex align-items-center justify-content-center vh-100 p-3">
        <div class="text-center" style="background:rgba(17,17,26,0.9); padding:30px; border-radius:15px; border:1px solid #00ffcc; max-width:500px;">
            <i class="fab fa-android text-success mb-3" style="font-size:50px;"></i>
            <h3 class="text-info fw-bold mb-4">MỞ HACK TRÊN KIWI BROWSER</h3>
            <p>Hệ thống tự động mở trình duyệt Kiwi và Nạp Key. Nếu chưa cài đặt, vui lòng tải ứng dụng bên dưới.</p>
            <a href="{intent_url}" class="btn btn-primary w-100 fw-bold mb-3 p-3" style="border-radius:10px; background: linear-gradient(90deg, #00ffcc, #0099ff); color:#000;">🚀 MỞ BẰNG KIWI BROWSER (BẤM VÀO ĐÂY)</a>
            <a href="https://play.google.com/store/apps/details?id=com.kiwibrowser.browser" target="_blank" class="btn btn-outline-success w-100 fw-bold p-2" style="border-radius:10px;"><i class="fas fa-download"></i> Tải Kiwi Browser Từ CH Play</a>
            <hr class="border-secondary mt-4 mb-4">
            <h5 class="text-warning">CÁCH DÙNG HACK (Chỉ làm 1 lần)</h5>
            <ol class="text-start text-secondary" style="font-size:14px; line-height:1.6;">
                <li>Tải Kiwi Browser và mở link bằng Kiwi.</li>
                <li>Cài đặt tiện ích <b>Violentmonkey</b> trên Cửa hàng Chrome.</li>
                <li>Gắn script vào Violentmonkey.</li>
                <li>Bấm vào nút <b>🚀 MỞ BẰNG KIWI BROWSER</b> bên trên!</li>
            </ol>
            <a href="/" class="text-muted mt-3 d-block" style="text-decoration:none;"><i class="fas fa-home"></i> Trở về Trang chủ</a>
        </div>
    </body></html>
    """
    return html

# ========================================================
# API BACKEND CHO TELEGRAM MINI APP (ALL IN ONE)
# ========================================================
def verify_telegram_webapp(init_data):
    try:
        vals = dict(urllib.parse.parse_qsl(init_data))
        if 'hash' not in vals: return False
        hash_val = vals.pop('hash')
        data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(vals.items()))
        secret_key = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(calc_hash, hash_val)
    except: return False

def get_tg_user_id_from_init_data(init_data):
    try:
        vals = dict(urllib.parse.parse_qsl(init_data))
        user_data = json.loads(vals.get('user', '{}'))
        return str(user_data.get('id', ''))
    except: return ''

def verify_tg_admin():
    init_data = request.headers.get('X-Init-Data', '')
    admin_id = str(request.headers.get('X-Admin-ID', ''))
    
    if init_data:
        if not verify_telegram_webapp(init_data): abort(403)
        admin_id = get_tg_user_id_from_init_data(init_data)
        
    db = load_db()
    allowed = db.get("settings", {}).get("tg_admins", [TELEGRAM_CHAT_ID])
    if admin_id not in allowed and admin_id != str(TELEGRAM_CHAT_ID):
        abort(403)
    return admin_id

@app.route('/api/tg_app/init', methods=['POST'])
def tg_app_init():
    data = request.json or {}
    init_data = request.headers.get('X-Init-Data', '')
    tg_id = str(data.get('tg_id', ''))
    
    if init_data and verify_telegram_webapp(init_data):
        tg_id = get_tg_user_id_from_init_data(init_data)

    db = load_db()
    allowed_admins = db.get("settings", {}).get("tg_admins", [TELEGRAM_CHAT_ID])
    is_admin = (tg_id in allowed_admins) or (tg_id == str(TELEGRAM_CHAT_ID))
    
    logged_in = 'username' in session
    username = session.get('username', '')
    
    return jsonify({
        "is_admin": is_admin,
        "logged_in": logged_in,
        "username": username
    })

@app.route('/api/tg_app/auth', methods=['POST'])
def tg_app_auth():
    data = request.json or {}
    action = data.get('action')
    user = data.get('username', '').lower().strip()
    pwd = data.get('password', '').strip()
    db = load_db()
    
    if action == 'login':
        u_data = db.get("users", {}).get(user)
        if u_data and u_data.get("password_hash") == hash_pwd(pwd):
            if isinstance(u_data.get("banned_until"), int) and u_data.get("banned_until") > int(time.time()*1000) or u_data.get("banned_until") == "permanent":
                return jsonify({"status": "error", "msg": "Tài khoản của bạn đã bị Admin khóa!"})
            session['username'] = user
            session['role'] = u_data.get("role", "user")
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "msg": "Sai tài khoản hoặc mật khẩu!"})
        
    elif action == 'register':
        if not user.isalnum() or len(user) < 4: return jsonify({"status": "error", "msg": "Tên đăng nhập > 4 ký tự, không dấu!"})
        if len(pwd) < 6: return jsonify({"status": "error", "msg": "Mật khẩu >= 6 ký tự!"})
        with db_lock:
            if user in db.setdefault("users", {}): return jsonify({"status": "error", "msg": "Tài khoản đã tồn tại!"})
            db["users"][user] = {"password_hash": hash_pwd(pwd), "role": "user", "balance": 0, "created_at": int(time.time() * 1000), "ips": [get_real_ip()], "purchased_keys": [], "notices": [], "custom_script": "", "banned_until": 0}
            save_db(db)
        return jsonify({"status": "success", "msg": "Đăng ký thành công!"})
    
    elif action == 'logout':
        session.clear()
        return jsonify({"status": "success"})

@app.route('/api/tg_app/user_data', methods=['GET'])
def tg_app_user_data():
    if 'username' not in session: return jsonify({"error": "not_logged_in"}), 401
    db = load_db()
    u = db["users"].get(session['username'])
    if not u: return jsonify({"error": "not_logged_in"}), 401
    
    now = int(time.time() * 1000)
    my_keys = []
    for pk in u.get("purchased_keys", []):
        k = pk['key']
        kd = db["keys"].get(k)
        if not kd: continue
        exp = kd.get("exp")
        if exp == "permanent": exp_str = "Vĩnh viễn"
        elif exp == "pending": exp_str = "Chưa KH"
        else: 
            exp_str = "Hết hạn" if exp < now else time.strftime("%d/%m %H:%M", time.localtime(exp/1000))
        my_keys.append({
            "key": k, "exp": exp_str, "status": kd.get("status"), 
            "bound_olm": kd.get("bound_olm", ""), "vip": kd.get("vip")
        })
        
    return jsonify({
        "balance": u["balance"],
        "keys": my_keys,
        "shop": SHOP_PACKAGES
    })

@app.route('/api/tg_app/buy', methods=['POST'])
def tg_app_buy():
    if 'username' not in session: return jsonify({"status": "error", "msg": "Chưa đăng nhập!"})
    username = session['username']
    data = request.json or {}
    pkg_id = data.get('pkg_id')
    os_type = data.get('os_type', 'android')
    olm_name = data.get('olm_name', '').strip()
    
    if pkg_id not in SHOP_PACKAGES: return jsonify({"status": "error", "msg": "Gói không tồn tại!"})
    pkg = SHOP_PACKAGES[pkg_id]
    price = pkg['price']
    
    db = load_db()
    with db_lock:
        user_data = db["users"].get(username)
        if user_data['balance'] < price: return jsonify({"status": "error", "msg": "Số Dư Không Đủ! Hãy nạp thêm tiền."})
        
        user_data['balance'] -= price
        nk = generate_secure_key("TOOL", pkg["vip"])
        
        db["keys"][nk] = {
            "exp": "pending", "durationMs": pkg['dur_ms'], "maxDevices": 1, "devices": [], 
            "known_ips": {}, "status": "active", "vip": pkg["vip"], "loader_enabled": True, 
            "violations": 0, "temp_ban_until": 0, "owner": username, "os": os_type, "reset_count": 0, 
            "bound_olm": olm_name
        }
        user_data.setdefault("purchased_keys", []).insert(0, {"key": nk, "package_name": pkg['name'], "buy_time": int(time.time() * 1000)})
        save_db(db)
        
    return jsonify({"status": "success", "msg": "Mua thành công!", "new_key": nk})

@app.route('/api/tg_admin/get_data', methods=['GET'])
def tg_admin_get_data():
    verify_tg_admin()
    db = load_db()
    now_ms = int(time.time() * 1000)
    total_keys = len(db.get("keys", {}))
    active_keys = sum(1 for v in db.get("keys", {}).values() if v.get("status") == "active" and (v.get("exp") == "permanent" or v.get("exp") == "pending" or (isinstance(v.get("exp"), int) and v.get("exp") > now_ms)))
    expired_keys = total_keys - active_keys

    user_list = []
    for uname, udata in db.get("users", {}).items():
        if udata.get("role") == "admin": continue
        u_keys_formatted = []
        for pk in udata.get("purchased_keys", []):
            k_id = pk['key']
            kd = db.get("keys", {}).get(k_id)
            if kd:
                k_exp = kd.get("exp")
                if k_exp == "permanent": exp_str = "Vĩnh viễn"
                elif k_exp == "pending": exp_str = "Chưa KH"
                elif k_exp < now_ms: exp_str = "Hết hạn"
                else: exp_str = time.strftime('%d/%m %H:%M', time.localtime(k_exp/1000))
                u_keys_formatted.append({"key": k_id, "exp": exp_str, "status": kd.get("status", "active")})

        ban_status = udata.get("banned_until", 0)
        is_banned = ban_status == "permanent" or (isinstance(ban_status, int) and ban_status > now_ms)
        user_list.append({"username": uname, "balance": udata.get("balance", 0), "ips": udata.get("ips", []), "keys": u_keys_formatted, "is_banned": is_banned, "banned_until": ban_status})

    return jsonify({"stats": {"total": total_keys, "active": active_keys, "expired": expired_keys}, "users": user_list})

@app.route('/api/tg_admin/action_user', methods=['POST'])
def tg_admin_action_user():
    verify_tg_admin()
    data = request.json or {}
    action = data.get('action')
    uname = data.get('username')
    db = load_db()
    with db_lock:
        if uname not in db.get("users", {}): return jsonify({"status": "error", "msg": "User không tồn tại"})
        u = db["users"][uname]
        if action == "add_balance":
            amt = safe_int(data.get('amount', 0))
            u["balance"] += amt
            if u["balance"] < 0: u["balance"] = 0
            act_str = "Cộng" if amt >=0 else "Trừ"
            u.setdefault("notices", []).append(f"Admin vừa {act_str} cho bạn {abs(amt):,}đ")
            save_db(db)
            return jsonify({"status": "success", "msg": f"Đã {act_str} {abs(amt):,}đ cho {uname}"})
        elif action == "ban_web":
            dur = safe_int(data.get('duration', 0))
            unit = data.get('unit', 'd')
            if unit == "permanent": u["banned_until"] = "permanent"
            else:
                multiplier = {"m": 60000, "h": 3600000, "d": 86400000}.get(unit, 86400000)
                u["banned_until"] = int(time.time() * 1000) + (dur * multiplier)
            save_db(db)
            return jsonify({"status": "success", "msg": f"Đã khóa truy cập Web của {uname}"})
        elif action == "unban_web":
            u["banned_until"] = 0
            save_db(db)
            return jsonify({"status": "success", "msg": f"Đã mở khóa Web cho {uname}"})
        elif action == "delete_user":
            del db["users"][uname]
            save_db(db)
            return jsonify({"status": "success", "msg": f"Đã xóa vĩnh viễn user {uname}"})
        elif action == "reset_pass":
            new_pass = data.get('new_pass', '')
            if not new_pass: return jsonify({"status": "error", "msg": "Mật khẩu không được để trống!"})
            u["password_hash"] = hash_pwd(new_pass)
            save_db(db)
            return jsonify({"status": "success", "msg": f"Đã Reset Pass thành công!"})
    return jsonify({"status": "error", "msg": "Lỗi không xác định"})

@app.route('/api/tg_admin/create_keys', methods=['POST'])
def tg_admin_create_keys():
    verify_tg_admin()
    data = request.json or {}
    prefix = data.get('prefix', '').strip()
    qty = safe_int(data.get('quantity', 1))
    dur = safe_int(data.get('duration', 1))
    unit = data.get('unit', 'day')
    is_vip = data.get('is_vip', False)
    generated = []
    db = load_db()
    with db_lock:
        for _ in range(qty):
            nk = generate_secure_key(prefix, is_vip)
            db["keys"][nk] = {"exp": "pending", "maxDevices": 1, "devices": [], "known_ips": {}, "status": "active", "vip": is_vip, "loader_enabled": True, "violations": 0, "temp_ban_until": 0, "owner": "admin", "reset_count": 0, "bound_olm": ""}
            if unit != 'permanent': db["keys"][nk]["durationMs"] = dur * {"hour":3600000, "day":86400000, "month":2592000000}.get(unit, 86400000)
            else: db["keys"][nk]["exp"] = "permanent"
            generated.append(nk)
        save_db(db)
    return jsonify({"status": "success", "keys": generated})

@app.route('/api/tg_admin/ban_olm', methods=['POST'])
def tg_admin_ban_olm():
    verify_tg_admin()
    data = request.json or {}
    olm_name = data.get('olm_name', '').strip()
    dur = safe_int(data.get('duration', 1))
    unit = data.get('unit', 'd')
    if not olm_name: return jsonify({"status": "error", "msg": "Tên OLM trống!"})
    exp_time = "permanent"
    if unit != "permanent":
        multiplier = {"m": 60000, "h": 3600000, "d": 86400000}.get(unit, 86400000)
        exp_time = int(time.time() * 1000) + (dur * multiplier)
    db = load_db()
    with db_lock:
        db.setdefault("banned_olms", {})[olm_name] = exp_time
        save_db(db)
    return jsonify({"status": "success", "msg": f"Đã cấm tài khoản OLM: {olm_name}!"})

@app.route('/api/tg_admin/update_script', methods=['POST'])
def tg_admin_update_script():
    verify_tg_admin()
    data = request.json or {}
    ns = data.get('script_content', '')
    if not ns.strip().startswith('// ==UserScript=='): return jsonify({"status": "error", "msg": "Script không hợp lệ"})
    db = load_db()
    with db_lock:
        db.setdefault("settings", {})["violentmonkey_script"] = ns
        save_db(db)
    return jsonify({"status": "success", "msg": "Đã cập nhật Code Script thành công!"})

@app.route('/api/tg_admin/system_actions', methods=['POST'])
def tg_admin_system_actions():
    verify_tg_admin()
    data = request.json or {}
    action = data.get('action')
    db = load_db()
    with db_lock:
        if action == "global_notice":
            msg = data.get('message', '').strip()
            if msg:
                db.setdefault("settings", {})["global_notice"] = msg
                for u in db.get("users", {}): db["users"][u].setdefault("notices", []).append(f"🔔 THÔNG BÁO TỪ ADMIN: {msg}")
                save_db(db)
                return jsonify({"status": "success", "msg": "Đã đẩy thông báo!"})
        elif action == "maintenance":
            dur = safe_int(data.get('duration', 0))
            unit = data.get('unit', 'h')
            if dur <= 0:
                db.setdefault("settings", {})["maintenance_until"] = 0
                save_db(db)
                return jsonify({"status": "success", "msg": "Đã TẮT chế độ bảo trì."})
            multiplier = {"m": 60000, "h": 3600000, "d": 86400000}.get(unit, 3600000)
            mnt = int(time.time() * 1000) + (dur * multiplier)
            db.setdefault("settings", {})["maintenance_until"] = mnt
            save_db(db)
            return jsonify({"status": "success", "msg": "Đã BẬT bảo trì."})
    return jsonify({"status": "error", "msg": "Hành động không hợp lệ!"})

# ========================================================
# TRANG GIAO DIỆN TELEGRAM MINI APP (ALL IN ONE UI)
# ========================================================
@app.route('/telegram_mini_app')
def telegram_mini_app():
    html_content = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>LVT Mini App</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;800&display=swap');
            body { background-color: #0f111a; color: #ffffff; font-family: 'Be Vietnam Pro', sans-serif; margin: 0; padding: 15px; -webkit-tap-highlight-color: transparent; }
            .screen { display: none; animation: fadeIn 0.3s ease; }
            .screen.active { display: block; }
            @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            
            .btn-primary { background: linear-gradient(90deg, #00ffcc, #0099ff); border: none; width: 100%; padding: 14px; border-radius: 10px; color: #000; font-size: 15px; font-weight: 800; cursor: pointer; transition: 0.2s;}
            .btn-primary:active { transform: scale(0.98); }
            .form-control { width: 100%; box-sizing: border-box; background: #1a1d29; border: 1px solid rgba(255,255,255,0.1); color: white; padding: 14px; border-radius: 10px; margin-bottom: 15px; font-family: inherit;}
            .form-control:focus { outline: none; border-color: #00ffcc; }
            
            /* User Dashboard Styles */
            .balance-card { background: linear-gradient(135deg, rgba(0, 255, 204, 0.15), rgba(189, 0, 255, 0.1)); border: 1px solid rgba(0, 255, 204, 0.4); border-radius: 16px; padding: 20px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center;}
            .balance-amt { font-size: 28px; font-weight: 900; color: #00ffcc; }
            .kiwi-card { background: linear-gradient(135deg, rgba(189, 0, 255, 0.15), rgba(0, 153, 255, 0.1)); border: 1px solid rgba(189, 0, 255, 0.4); border-radius: 16px; padding: 20px; margin-bottom: 25px; text-align: center; cursor: pointer;}
            .shop-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
            .pkg-card { background: #1a1d29; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 15px; text-align: center; }
            .pkg-vip { border-color: #bd00ff; box-shadow: 0 0 10px rgba(189,0,255,0.1); }
            .pkg-nor { border-color: #0099ff; }
            
            /* Admin Styles */
            .section-title { font-size: 15px; font-weight: 800; margin-bottom: 15px; display: flex; align-items: center; gap: 10px; color: #8892b0; text-transform: uppercase;}
            .select-btn { background: #1a1d29; border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; padding: 15px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; cursor: pointer; transition: 0.2s;}
            .icon-box { width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px; }
            .btn-back { background: rgba(255,255,255,0.1); border: none; padding: 10px 15px; border-radius: 10px; color: white; font-weight: 600; margin-bottom: 15px; display: inline-flex; align-items: center; gap: 8px; cursor: pointer;}
            
            .header-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <div id="screen-auth" class="screen active">
            <div style="text-align:center; margin-top:30px; margin-bottom: 30px;">
                <i class="fas fa-shield-alt" style="font-size: 60px; color: #00ffcc;"></i>
                <h2 style="color: #00ffcc; margin-top: 15px;">LVT SHOP HACK</h2>
                <p style="color:#8892b0;">Vui lòng đăng nhập để mua Key</p>
            </div>
            <div style="background:#1a1d29; padding:20px; border-radius:15px; border:1px solid rgba(255,255,255,0.1);">
                <input type="text" id="auth-user" class="form-control" placeholder="Tên đăng nhập (Liền không dấu)">
                <input type="password" id="auth-pwd" class="form-control" placeholder="Mật khẩu">
                <button class="btn-primary mb-3" onclick="doAuth('login')">ĐĂNG NHẬP</button>
                <button class="btn-primary" style="background:rgba(255,255,255,0.1); color:#fff;" onclick="doAuth('register')">ĐĂNG KÝ MỚI</button>
            </div>
        </div>

        <div id="screen-user" class="screen">
            <div class="header-bar">
                <div>Xin chào, <b id="display-uname" style="color:#00ffcc; text-transform:uppercase;">...</b></div>
                <div style="display:flex; gap:8px;">
                    <button id="btn-admin-panel" style="display:none; background:#ffcc00; color:#000; border:none; padding:5px 10px; border-radius:8px; font-weight:bold;" onclick="navTo('screen-admin-main')"><i class="fas fa-crown"></i> ADMIN</button>
                    <button style="background:rgba(255,68,68,0.2); color:#ff4444; border:none; padding:5px 10px; border-radius:8px; font-weight:bold;" onclick="logout()">Thoát</button>
                </div>
            </div>
            
            <div class="balance-card">
                <div><div style="font-size:12px; color:#8892b0;">SỐ DƯ (VNĐ)</div><div class="balance-amt" id="display-balance">0</div></div>
                <button style="background:#00ffcc; color:#000; border:none; padding:10px 15px; border-radius:10px; font-weight:bold;" onclick="window.open('https://zalo.me/0343627516', '_blank')">NẠP TIỀN</button>
            </div>
            
            <div class="kiwi-card" onclick="openHackPrompt()">
                <h4 style="color:#bd00ff; margin:0 0 5px 0;"><i class="fas fa-rocket"></i> NHẬP KEY SỬ DỤNG HACK</h4>
                <div style="font-size:12px; color:#8892b0;">Hệ thống tự động liên kết với Kiwi Browser</div>
            </div>
            
            <h4 style="color:#fff; margin-bottom:10px;"><i class="fas fa-shopping-cart"></i> MUA KEY MỚI</h4>
            <div class="shop-grid" id="shop-container"></div>
            
            <h4 style="color:#fff; margin-bottom:10px; margin-top:20px;"><i class="fas fa-key"></i> KEY CỦA TÔI</h4>
            <div id="my-keys-container"></div>
        </div>

        <div id="screen-admin-main" class="screen">
            <div class="header-bar">
                <button class="btn-back" style="margin:0;" onclick="navTo('screen-user')"><i class="fas fa-arrow-left"></i> Về Shop</button>
                <div style="background:#ffcc00; color:#000; padding:5px 10px; border-radius:8px; font-weight:bold;"><i class="fas fa-crown"></i> ADMIN PANEL</div>
            </div>
            
            <div class="section-title">HỆ THỐNG GLOBAL</div>
            <div class="select-btn" onclick="navTo('screen-admin-system')">
                <div class="select-btn-left">
                    <div class="icon-box" style="background:rgba(255,204,0,0.1); color:#ffcc00;"><i class="fas fa-bullhorn"></i></div>
                    <div><div style="font-size: 15px; font-weight: 800;">Thông Báo & Bảo Trì</div><div style="font-size: 12px; color: #8892b0;">Gửi thông báo, Đóng server</div></div>
                </div><i class="fas fa-chevron-right" style="color: #8892b0;"></i>
            </div>
            
            <div class="section-title">CHỨC NĂNG QUẢN TRỊ</div>
            <div class="select-btn" onclick="navTo('screen-admin-keys')">
                <div class="select-btn-left">
                    <div class="icon-box" style="background:rgba(34, 197, 94, 0.1); color:#22c55e;"><i class="fas fa-key"></i></div>
                    <div><div style="font-size: 15px; font-weight: 800;">Tạo & Quản Lý Key</div><div style="font-size: 12px; color: #8892b0;">Tạo Auto/Thủ công</div></div>
                </div><i class="fas fa-chevron-right" style="color: #8892b0;"></i>
            </div>
            
            <div class="select-btn" onclick="navTo('screen-admin-users')">
                <div class="select-btn-left">
                    <div class="icon-box" style="background:rgba(59, 130, 246, 0.1); color:#3b82f6;"><i class="fas fa-users"></i></div>
                    <div><div style="font-size: 15px; font-weight: 800;">Quản Lý Người Dùng</div><div style="font-size: 12px; color: #8892b0;">Nạp tiền, Khóa, Xóa Web</div></div>
                </div><i class="fas fa-chevron-right" style="color: #8892b0;"></i>
            </div>

            <div class="select-btn" onclick="navTo('screen-admin-olm')">
                <div class="select-btn-left">
                    <div class="icon-box" style="background:rgba(239, 68, 68, 0.1); color:#ef4444;"><i class="fas fa-shield-alt"></i></div>
                    <div><div style="font-size: 15px; font-weight: 800;">Cấm Truy Cập OLM</div><div style="font-size: 12px; color: #8892b0;">Chặn Tool định danh OLM</div></div>
                </div><i class="fas fa-chevron-right" style="color: #8892b0;"></i>
            </div>

            <div class="select-btn" onclick="navTo('screen-admin-script')">
                <div class="select-btn-left">
                    <div class="icon-box" style="background:rgba(168, 85, 247, 0.1); color:#a855f7;"><i class="fas fa-code"></i></div>
                    <div><div style="font-size: 15px; font-weight: 800;">Cập Nhật Script Lõi</div><div style="font-size: 12px; color: #8892b0;">Thay code Violentmonkey</div></div>
                </div><i class="fas fa-chevron-right" style="color: #8892b0;"></i>
            </div>
        </div>

        <div id="screen-admin-system" class="screen">
            <button class="btn-back" onclick="navTo('screen-admin-main')"><i class="fas fa-arrow-left"></i> Quay lại</button>
            <h3 style="margin-top:0; color:#ffcc00;">🔔 HỆ THỐNG GLOBAL</h3>
            <div style="background:#1a1d29; padding:20px; border-radius:15px; margin-bottom: 20px;">
                <h5 style="color:#fff; margin-top:0;">Gửi Thông Báo Tất Cả User</h5>
                <textarea id="sys-msg" class="form-control" rows="3" placeholder="Nhập nội dung..."></textarea>
                <button class="btn-primary" style="background:linear-gradient(90deg, #ffcc00, #f97316);" onclick="sendGlobalNotice()">GỬI THÔNG BÁO</button>
            </div>
            <div style="background:#1a1d29; padding:20px; border-radius:15px;">
                <h5 style="color:#ef4444; margin-top:0;">Bật Chế Độ Bảo Trì Tool</h5>
                <div style="display:flex; gap:10px;">
                    <input type="number" id="mnt-dur" class="form-control" value="0" placeholder="Thời gian (0 để Tắt)">
                    <select id="mnt-unit" class="form-control"><option value="m">Phút</option><option value="h" selected>Giờ</option><option value="d">Ngày</option></select>
                </div>
                <button class="btn-primary" style="background:linear-gradient(90deg, #ef4444, #b91c1c);" onclick="setMaintenance()">CẬP NHẬT BẢO TRÌ</button>
            </div>
        </div>

        <div id="screen-admin-keys" class="screen">
            <button class="btn-back" onclick="navTo('screen-admin-main')"><i class="fas fa-arrow-left"></i> Quay lại</button>
            <h3 style="margin-top:0; color:#00ffcc;">🔑 TẠO KEY MỚI</h3>
            <div style="background:#1a1d29; padding:20px; border-radius:15px;">
                <input type="text" id="k-prefix" class="form-control" placeholder="Tiền tố (VD: TEST)">
                <div style="display:flex; gap:10px;">
                    <input type="number" id="k-qty" class="form-control" value="1" placeholder="Số lượng">
                    <input type="number" id="k-dur" class="form-control" value="1" placeholder="Độ dài">
                </div>
                <select id="k-unit" class="form-control">
                    <option value="hour">Giờ</option><option value="day" selected>Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh Viễn</option>
                </select>
                <div style="display:flex; align-items:center; gap:10px; margin-bottom:15px;">
                    <input type="checkbox" id="k-vip" style="width:20px; height:20px;">
                    <label for="k-vip" style="color:#ffcc00; font-weight:bold;">Tạo dưới dạng Key VIP PRO</label>
                </div>
                <button class="btn-primary" onclick="createKeys()">🚀 TẠO NGAY</button>
            </div>
        </div>

        <div id="screen-admin-users" class="screen">
            <button class="btn-back" onclick="navTo('screen-admin-main')"><i class="fas fa-arrow-left"></i> Quay lại</button>
            <h3 style="margin-top:0; color:#3b82f6;">👥 DANH SÁCH USER WEB</h3>
            <input type="text" id="u-search" class="form-control" placeholder="🔍 Tìm user..." onkeyup="filterUsers()">
            <div id="user-list-container"><div style="text-align:center; padding:20px; color:#8892b0;">Đang tải dữ liệu...</div></div>
        </div>

        <div id="screen-admin-olm" class="screen">
            <button class="btn-back" onclick="navTo('screen-admin-main')"><i class="fas fa-arrow-left"></i> Quay lại</button>
            <h3 style="margin-top:0; color:#ef4444;">🚫 CHẶN OLM DÙNG TOOL</h3>
            <div style="background:#1a1d29; padding:20px; border-radius:15px;">
                <input type="text" id="o-name" class="form-control" placeholder="Nhập tên định danh OLM">
                <div style="display:flex; gap:10px;">
                    <input type="number" id="o-dur" class="form-control" value="1" placeholder="Thời gian">
                    <select id="o-unit" class="form-control">
                        <option value="m">Phút</option><option value="h">Giờ</option><option value="d" selected>Ngày</option><option value="permanent">Khóa Vĩnh Viễn</option>
                    </select>
                </div>
                <button class="btn-primary" style="background:linear-gradient(90deg, #ef4444, #f97316);" onclick="banOlm()">CHẶN NGAY</button>
            </div>
        </div>

        <div id="screen-admin-script" class="screen">
            <button class="btn-back" onclick="navTo('screen-admin-main')"><i class="fas fa-arrow-left"></i> Quay lại</button>
            <h3 style="margin-top:0; color:#a855f7;">📜 CẬP NHẬT LÕI SCRIPT</h3>
            <div style="background:#1a1d29; padding:20px; border-radius:15px;">
                <textarea id="s-code" class="form-control" rows="8" placeholder="// ==UserScript==\n..."></textarea>
                <button class="btn-primary" style="background:linear-gradient(90deg, #a855f7, #6366f1);" onclick="updateScript()">LƯU VÀ XUẤT BẢN NHANH</button>
            </div>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            let adminId = tg.initDataUnsafe?.user?.id || "7363320876"; 
            let initData = tg.initData || ""; 
            let allUsersData = [];

            function navTo(screenId) {
                document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
                document.getElementById(screenId).classList.add('active');
                if(screenId === 'screen-admin-users') loadAdminUsers();
            }

            function apiCall(endpoint, data, onSuccess) {
                tg.MainButton.showProgress();
                fetch(endpoint, {
                    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Admin-ID': adminId, 'X-Init-Data': initData },
                    body: JSON.stringify(data)
                }).then(res => res.json()).then(res => {
                    tg.MainButton.hideProgress();
                    if(res.status === 'success') {
                        if(onSuccess) onSuccess(res);
                        else Swal.fire({toast:true, position:'top', icon:'success', title: res.msg || 'Thành công!', showConfirmButton:false, timer:2000, background:'#1a1d29', color:'#fff'});
                    } else { Swal.fire({icon:'error', title:'Lỗi', text:res.msg, background:'#1a1d29', color:'#fff'}); }
                }).catch(e => {
                    tg.MainButton.hideProgress(); Swal.fire({icon:'error', title:'Lỗi mạng', text:e.toString(), background:'#1a1d29', color:'#fff'});
                });
            }

            function copyT(t) {
                navigator.clipboard.writeText(t); tg.HapticFeedback.impactOccurred('light');
                Swal.fire({toast:true, position:'top', icon:'success', title:'Đã copy!', showConfirmButton:false, timer:1500, background:'#1a1d29', color:'#fff'});
            }

            // INIT APP
            function initApp() {
                fetch('/api/tg_app/init', { method: 'POST', headers: {'Content-Type':'application/json', 'X-Init-Data': initData}, body: JSON.stringify({tg_id: adminId}) })
                .then(r => r.json()).then(d => {
                    if (d.is_admin) document.getElementById('btn-admin-panel').style.display = 'block';
                    if (d.logged_in) {
                        document.getElementById('display-uname').innerText = d.username;
                        loadUserData();
                        navTo('screen-user');
                    } else {
                        navTo('screen-auth');
                    }
                });
            }

            // AUTH
            function doAuth(action) {
                let u = document.getElementById('auth-user').value; let p = document.getElementById('auth-pwd').value;
                if(!u || !p) return Swal.fire({icon:'error', title:'Lỗi', text:'Nhập đủ thông tin', background:'#1a1d29', color:'#fff'});
                apiCall('/api/tg_app/auth', {action: action, username: u, password: p}, (res) => {
                    Swal.fire({toast:true, position:'top', icon:'success', title:res.msg || 'Thành công', showConfirmButton:false, timer:1500, background:'#1a1d29', color:'#fff'});
                    initApp();
                });
            }
            function logout() {
                apiCall('/api/tg_app/auth', {action: 'logout'}, () => { initApp(); });
            }

            // USER DASHBOARD
            function loadUserData() {
                fetch('/api/tg_app/user_data', { headers: { 'X-Admin-ID': adminId, 'X-Init-Data': initData } }).then(r=>r.json()).then(d => {
                    if(d.error) { initApp(); return; }
                    document.getElementById('display-balance').innerText = d.balance.toLocaleString();
                    
                    let sHtml = '';
                    for (let pid in d.shop) {
                        let p = d.shop[pid];
                        let cClass = p.vip ? 'pkg-vip' : 'pkg-nor';
                        let tag = p.vip ? '<span style="color:#bd00ff;font-size:10px;font-weight:bold;border:1px solid #bd00ff;padding:2px 5px;border-radius:4px;">VIP</span>' : '';
                        sHtml += `
                        <div class="pkg-card ${cClass}" onclick="buyKey('${pid}', '${p.name}', ${p.price}, ${p.vip})">
                            ${tag}
                            <div style="font-weight:bold; margin-top:5px; color:#fff;">${p.name}</div>
                            <div style="color:${p.vip?'#bd00ff':'#00ffcc'}; font-weight:900; font-size:16px; margin-top:5px;">${p.price.toLocaleString()}đ</div>
                        </div>`;
                    }
                    document.getElementById('shop-container').innerHTML = sHtml;
                    
                    let kHtml = '';
                    if (d.keys.length === 0) kHtml = '<div style="color:#8892b0; text-align:center; padding:20px;">Bạn chưa mua Key nào.</div>';
                    d.keys.forEach(k => {
                        let stHtml = k.status === 'active' ? '<span style="color:#22c55e;">Hoạt động</span>' : '<span style="color:#ef4444;">Bị khóa</span>';
                        let vHtml = k.vip ? '<span style="color:#bd00ff;">[VIP]</span>' : '<span style="color:#0099ff;">[NOR]</span>';
                        kHtml += `
                        <div style="background:#1a1d29; border:1px solid rgba(255,255,255,0.1); padding:15px; border-radius:12px; margin-bottom:10px;">
                            <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                                <strong style="color:#00ffcc; font-size:16px;" onclick="copyT('${k.key}')">${k.key.substring(0,8)}... <i class="fas fa-copy"></i></strong>
                                ${stHtml}
                            </div>
                            <div style="font-size:12px; color:#8892b0;">HSD: <span style="color:#fff;">${k.exp}</span> ${vHtml}</div>
                            <div style="font-size:12px; color:#8892b0; margin-top:5px;">Ghim OLM: <span style="color:#ffcc00;">${k.bound_olm || 'Chưa ghim'}</span></div>
                        </div>`;
                    });
                    document.getElementById('my-keys-container').innerHTML = kHtml;
                });
            }

            function buyKey(id, name, price, isVip) {
                Swal.fire({
                    title: 'MUA KEY', html: `<p>Gói: <b>${name}</b><br>Giá: <b style="color:#00ffcc;">${price.toLocaleString()}đ</b></p>
                    <input type="text" id="swal-olm" class="swal2-input" placeholder="Nhập nick OLM khách" style="width: 85%; background: rgba(10,10,18,0.8); color: #00ffcc; border: 1px solid #00ffcc; border-radius:10px;">
                    <div style="margin-top: 15px; font-size: 14px; text-align:left; padding-left:20px;">
                        <b>CHỌN HỆ ĐIỀU HÀNH:</b><br>
                        <label class="mt-2"><input type="radio" name="swal-os" value="android" checked> <i class="fab fa-android"></i> Android/PC</label><br>
                        <label class="mt-2"><input type="radio" name="swal-os" value="ios"> <i class="fab fa-apple"></i> iOS</label>
                    </div>`,
                    showCancelButton: true, confirmButtonText: 'XÁC NHẬN MUA', background: '#1a1d29', color: '#fff', confirmButtonColor: '#00ffcc',
                    preConfirm: () => {
                        const olm = document.getElementById('swal-olm').value.trim();
                        const os = document.querySelector('input[name="swal-os"]:checked').value;
                        if(!olm) { Swal.showValidationMessage('Phải nhập nick OLM!'); return false; }
                        return { olm: olm, os: os };
                    }
                }).then((r) => {
                    if(r.isConfirmed) {
                        apiCall('/api/tg_app/buy', {pkg_id: id, os_type: r.value.os, olm_name: r.value.olm}, (res) => {
                            Swal.fire({title:'MUA THÀNH CÔNG', html:`<p>Mã Key của bạn:</p><div style='background:#000;color:#00ffcc;padding:10px;border-radius:8px;font-family:monospace;' onclick="copyT('${res.new_key}')">${res.new_key}</div>`, background:'#1a1d29', color:'#fff', confirmButtonColor:'#00ffcc'});
                            loadUserData();
                        });
                    }
                });
            }

            function openHackPrompt() {
                Swal.fire({
                    title: 'NHẬP MÃ KEY SỬ DỤNG HACK',
                    input: 'text',
                    inputPlaceholder: 'Dán mã Key của bạn...',
                    showCancelButton: true, confirmButtonText: 'MỞ HACK (KIWI)', cancelButtonText: 'Hủy',
                    background: '#1a1d29', color: '#fff', confirmButtonColor: '#00ffcc',
                    preConfirm: (key) => { if (!key) Swal.showValidationMessage('Vui lòng nhập Key!'); return key; }
                }).then((r) => {
                    if(r.isConfirmed) {
                        fetch('/api/verify_hack_key', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({key: r.value}) })
                        .then(res => res.json()).then(data => {
                            if(data.status === 'success') {
                                Swal.fire({toast:true, position:'top', icon:'success', title:'Đang xử lý...', showConfirmButton:false, timer:2000, background:'#1a1d29', color:'#fff'});
                                setTimeout(() => { 
                                    // [VÁ LỖI ERR_UNKNOWN_URL_SCHEME]: 
                                    // Đẩy ra trình duyệt ngoài vì Telegram WebView không hiểu intent://
                                    tg.openLink(`https://${window.location.host}/open_hack?key=${r.value}`); 
                                }, 1000);
                            } else { Swal.fire({icon:'error', title:'Lỗi', text:data.msg, background:'#1a1d29', color:'#fff'}); }
                        }).catch(e => { Swal.fire({icon:'error', title:'Lỗi mạng', text:e.toString(), background:'#1a1d29', color:'#fff'}); });
                    }
                });
            }

            // ADMIN DASHBOARD
            function loadAdminUsers() {
                fetch('/api/tg_admin/get_data', { headers: { 'X-Admin-ID': adminId, 'X-Init-Data': initData } }).then(r => r.json()).then(data => {
                    allUsersData = data.users; renderUsers(allUsersData);
                });
            }

            function renderUsers(users) {
                let container = document.getElementById('user-list-container'); container.innerHTML = '';
                if(users.length === 0) { container.innerHTML = '<div style="color:#8892b0; padding:20px;">Trống</div>'; return; }
                users.forEach(u => {
                    let kHtml = u.keys.map(k => `<div>🔑 <code style="color:#00ffcc;" onclick="copyT('${k.key}')">${k.key.substring(0,8)}...</code> <span style="color:${k.status==='active'?'#22c55e':'#ef4444'}">[${k.exp}]</span></div>`).join('');
                    let banBadge = u.is_banned ? `<span style="background:rgba(239,68,68,0.2); color:#ef4444; padding:2px 6px; border-radius:4px; font-size:10px; border:1px solid #ef4444;">BỊ KHÓA</span>` : '';
                    let card = `
                    <div style="background:#1a1d29; border:1px solid rgba(255,255,255,0.1); border-radius:12px; padding:15px; margin-bottom:15px;">
                        <div style="display:flex; justify-content:space-between; border-bottom:1px dashed rgba(255,255,255,0.1); padding-bottom:10px; margin-bottom:10px;">
                            <b style="color:#fff;" onclick="copyT('${u.username}')">${u.username} <i class="fas fa-copy"></i></b> ${banBadge}
                        </div>
                        <div style="font-size:13px; color:#8892b0;">
                            <div>Dư: <b style="color:#ffcc00;">${u.balance.toLocaleString()}đ</b></div>
                            <div style="margin-top:8px; border-top:1px solid rgba(255,255,255,0.05); padding-top:8px;">${kHtml || 'Chưa mua key'}</div>
                        </div>
                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:12px;">
                            <button style="background:rgba(34,197,94,0.1); color:#22c55e; border:none; padding:8px; border-radius:6px; font-weight:bold;" onclick="actionUser('${u.username}', 'add_balance')"><i class="fas fa-plus"></i> Tiền</button>
                            <button style="background:rgba(59,130,246,0.1); color:#3b82f6; border:none; padding:8px; border-radius:6px; font-weight:bold;" onclick="actionUser('${u.username}', 'reset_pass')"><i class="fas fa-key"></i> Đổi Pass</button>
                            ${u.is_banned ? `<button style="background:rgba(249,115,22,0.1); color:#f97316; border:none; padding:8px; border-radius:6px; font-weight:bold;" onclick="apiCall('/api/tg_admin/action_user', {action:'unban_web', username:'${u.username}'}, ()=>{loadAdminUsers();})"><i class="fas fa-unlock"></i> Mở Khóa</button>` : `<button style="background:rgba(249,115,22,0.1); color:#f97316; border:none; padding:8px; border-radius:6px; font-weight:bold;" onclick="actionUser('${u.username}', 'ban_web')"><i class="fas fa-ban"></i> Khóa Web</button>`}
                            <button style="background:rgba(239,68,68,0.1); color:#ef4444; border:none; padding:8px; border-radius:6px; font-weight:bold;" onclick="actionUser('${u.username}', 'delete_user')"><i class="fas fa-trash"></i> Xóa</button>
                        </div>
                    </div>`;
                    container.innerHTML += card;
                });
            }
            function filterUsers() { let s = document.getElementById('u-search').value.toLowerCase(); renderUsers(allUsersData.filter(u => u.username.toLowerCase().includes(s))); }

            function actionUser(uname, action) {
                if(action === 'add_balance') {
                    Swal.fire({ title: `Nạp Tiền: ${uname}`, input: 'number', showCancelButton: true, background:'#1a1d29', color:'#fff', confirmButtonColor:'#22c55e'
                    }).then(r => { if(r.isConfirmed) apiCall('/api/tg_admin/action_user', {action:'add_balance', username:uname, amount:r.value}, ()=>{loadAdminUsers();}); });
                } else if(action === 'ban_web') {
                    Swal.fire({ title: `Khóa Web: ${uname}`, html: `<input type="number" id="b-dur" class="swal2-input" value="1"><select id="b-unit" class="swal2-select"><option value="h">Giờ</option><option value="d" selected>Ngày</option><option value="permanent">Vĩnh Viễn</option></select>`, showCancelButton: true, background:'#1a1d29', color:'#fff', confirmButtonColor:'#f97316', preConfirm: () => { return { dur: document.getElementById('b-dur').value, unit: document.getElementById('b-unit').value }; }
                    }).then(r => { if(r.isConfirmed) apiCall('/api/tg_admin/action_user', {action:'ban_web', username:uname, duration:r.value.dur, unit:r.value.unit}, ()=>{loadAdminUsers();}); });
                } else if(action === 'reset_pass') {
                    Swal.fire({ title: `Đổi Pass: ${uname}`, input: 'text', inputPlaceholder: 'Nhập Pass mới', showCancelButton: true, background:'#1a1d29', color:'#fff', confirmButtonColor:'#3b82f6', preConfirm: (v)=>{if(!v)Swal.showValidationMessage('Trống!'); return v;}
                    }).then(r => { if(r.isConfirmed) apiCall('/api/tg_admin/action_user', {action:'reset_pass', username:uname, new_pass:r.value}, ()=>{loadAdminUsers();}); });
                } else if(action === 'delete_user') {
                    Swal.fire({ title: 'Xóa vĩnh viễn?', icon: 'error', showCancelButton: true, background:'#1a1d29', color:'#fff', confirmButtonColor:'#ef4444' }).then(r => { if(r.isConfirmed) apiCall('/api/tg_admin/action_user', {action:'delete_user', username:uname}, ()=>{loadAdminUsers();}); });
                }
            }

            function createKeys() {
                let p = document.getElementById('k-prefix').value; let q = document.getElementById('k-qty').value; let d = document.getElementById('k-dur').value; let u = document.getElementById('k-unit').value; let v = document.getElementById('k-vip').checked;
                apiCall('/api/tg_admin/create_keys', {prefix: p, quantity: q, duration: d, unit: u, is_vip: v}, (res) => {
                    let kHtml = res.keys.map(k => `<div style="background:#000; color:#00ffcc; padding:8px; margin:5px 0; border-radius:5px; font-family:monospace; font-size:12px; cursor:pointer;" onclick="copyT('${k}')">${k}</div>`).join('');
                    Swal.fire({title: 'ĐÃ TẠO XONG', html: `<div style="text-align:left; max-height:200px; overflow-y:auto;">${kHtml}</div>`, background:'#1a1d29', color:'#fff', confirmButtonColor:'#00ffcc'});
                });
            }

            function banOlm() {
                let n = document.getElementById('o-name').value; let d = document.getElementById('o-dur').value; let u = document.getElementById('o-unit').value;
                if(!n) return Swal.fire({icon:'error', title:'Lỗi', text:'Chưa nhập', background:'#1a1d29', color:'#fff'});
                apiCall('/api/tg_admin/ban_olm', {olm_name: n, duration: d, unit: u});
            }

            function updateScript() {
                let code = document.getElementById('s-code').value;
                if(!code) return Swal.fire({icon:'error', title:'Lỗi', text:'Chưa dán code', background:'#1a1d29', color:'#fff'});
                apiCall('/api/tg_admin/update_script', {script_content: code});
            }
            
            function sendGlobalNotice() {
                let msg = document.getElementById('sys-msg').value;
                if(!msg) return Swal.fire({icon:'error', title:'Lỗi', text:'Chưa nhập', background:'#1a1d29', color:'#fff'});
                apiCall('/api/tg_admin/system_actions', {action: 'global_notice', message: msg});
            }

            function setMaintenance() {
                let d = document.getElementById('mnt-dur').value; let u = document.getElementById('mnt-unit').value;
                apiCall('/api/tg_admin/system_actions', {action: 'maintenance', duration: d, unit: u});
            }

            initApp();
        </script>
    </body>
    </html>
    """
    return render_template_string_safe(html_content)

# ADMIN WEB ROUTES
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    try:
        ip = get_real_ip()
        
        global admin_login_attempts
        now = time.time()
        admin_login_attempts = {k: v for k, v in admin_login_attempts.items() if now - v['time'] < 300} 
        
        attempts = admin_login_attempts.get(ip, {'count': 0, 'time': now})
        if attempts['count'] >= 5:
            return swal_back("Bị Khóa Tạm Thời", "Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau 5 phút!", "error")

        if request.method == 'POST':
            db = load_db()
            username = request.form.get('username', '').strip().lower()
            pwd = request.form.get('password', '').strip()
            
            u_data = db.get("users", {}).get(username)
            if u_data and u_data.get("role") == "admin" and u_data.get("password_hash") == hash_pwd(pwd):
                session['username'] = username
                session['role'] = 'admin'
                admin_login_attempts.pop(ip, None) 
                with db_lock: log_admin_action(db, f"Đăng nhập Admin: {ip}")
                save_db(db)
                return redirect('/admin')
            
            attempts['count'] += 1
            attempts['time'] = now
            admin_login_attempts[ip] = attempts
            
            return swal_back("Từ Chối Truy Cập", f"Thông tin sai! Bạn còn {5 - attempts['count']} lần thử.", "error")
            
        return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Admin Login</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>{CSS_GLASS}</style></head><body><div class="glass-panel"><h2 class="text-neon mb-4">🔐 QUẢN TRỊ VIÊN</h2><form method="POST"><input type="text" name="username" class="form-control" placeholder="Tên Admin" required><input type="password" name="password" class="form-control" placeholder="Mật Khẩu" required><button type="submit" class="btn-neon mt-2">VÀO PHÒNG ĐIỀU KHIỂN</button></form></div></body></html>'''
    except Exception as e: return f"LỖI HỆ THỐNG: {str(e)}", 200

@app.route('/admin')
def admin_dashboard():
    try:
        if session.get('role') != 'admin': return redirect('/admin_login')
        db = load_db()
        with db_lock:
            keys_items = list(db.get("keys", {}).items())
            users_items = list(db.get("users", {}).items())
            banned_ips = list(db.get("banned_ips", []))
            tg_admins = list(db.get("settings", {}).get("tg_admins", [TELEGRAM_CHAT_ID]))

        now_ms = int(time.time() * 1000)

        users_html = ""
        for uname, udata in users_items:
            if udata.get("role") == "admin": continue
            bal = udata.get("balance", 0)
            u_keys = "<br>".join([f"🔑 {escape(pk.get('key')[:8])}..." for pk in udata.get("purchased_keys", [])]) or "<span class='text-muted'>Chưa có</span>"
            u_ips = "<br>".join([escape(ip) for ip in udata.get("ips", [])]) or "<span class='text-muted'>Trống</span>"
            users_html += f'''<tr class="text-nowrap"><td><strong class="text-warning">{escape(uname)}</strong></td><td><span class="badge bg-success">{bal:,}đ</span></td><td style="font-size:11px; text-align:left;">{u_keys}</td><td style="font-size:11px; text-align:left; color:#ffcc00;">{u_ips}</td><td><form action="/admin/add_balance" method="POST" class="d-flex gap-1 justify-content-center m-0"><input type="hidden" name="username" value="{escape(uname)}"><input type="number" name="amount" class="form-control form-control-sm bg-dark text-light border-secondary px-1 text-center m-0" style="width:70px;font-size:12px;height:28px;" placeholder="± Tiền" required><button type="submit" class="btn btn-sm btn-primary fw-bold" style="font-size:11px;height:28px; border-radius:6px;">CỘNG</button></form></td></tr>'''

        keys_html = ''
        for k, data in sorted(keys_items, key=lambda x: x[1].get('exp', 0) if isinstance(x[1].get('exp'), int) else 9999999999999, reverse=True):
            st = data.get('status', 'active')
            is_banned = (st == 'banned')
            temp_ban = data.get('temp_ban_until', 0)
            status_badge = '<span class="badge bg-success">Hoạt động</span>'
            if is_banned: status_badge = '<span class="badge bg-dark border border-danger text-danger">TỬ HÌNH</span>'
            elif temp_ban > now_ms: status_badge = f'<span class="badge bg-warning text-dark">Phạt Share ({ (temp_ban - now_ms)//60000 }p)</span>'
            vip_badge = '<span class="badge bg-danger">VIP</span>' if data.get('vip', False) else '<span class="badge bg-secondary">THƯỜNG</span>'
            
            is_expired = False
            if data.get('exp') == 'pending': exp_text = '<span class="text-info">Chưa KH</span>'
            elif data.get('exp') == 'permanent': exp_text = '<span class="text-success fw-bold">V.Viễn</span>'
            else:
                is_expired = now_ms > data.get('exp', 0)
                exp_text = f'<span class="{"text-danger fw-bold" if is_expired else "text-light"}">{time.strftime("%d/%m/%y %H:%M", time.localtime(data.get("exp", 0) / 1000))}</span>'
            
            if is_expired and not is_banned: status_badge = '<span class="badge bg-secondary">HẾT HẠN</span>'
            safe_k = escape(str(k))
            bound_olm = escape(data.get('bound_olm', ''))
            keys_html += f'''<tr class="key-row text-nowrap"><td><strong class="text-info" style="font-size:12px; cursor:pointer;" onclick="copyKey('{safe_k}')" title="Bấm để copy">{safe_k[:8]}...</strong><br>{vip_badge} {status_badge}<br><small class="text-warning">Chủ: {escape(data.get('owner', 'Admin'))}</small><br><small class="text-danger">Ghim: {bound_olm}</small></td><td style="font-size:11px;">{exp_text}</td><td><span class="badge bg-info text-dark">{len(data.get('devices', []))}/{data.get('maxDevices', 1)}</span></td><td><div class="d-flex flex-wrap gap-1 justify-content-center"><button class="btn btn-info btn-sm fw-bold text-dark" style="font-size:10px; border-radius:6px;" onclick="openAddTimeModal('{safe_k}')">⏳ Giờ</button><button class="btn btn-warning btn-sm" style="font-size:10px; border-radius:6px;" onclick="openBindModal('{safe_k}', '{bound_olm}')">Ghim</button><a href="/admin/action/reset-dev/{safe_k}" class="btn btn-primary btn-sm" style="font-size:10px; border-radius:6px;">🔄 Máy</a><a href="/admin/action/unban_temp/{safe_k}" class="btn btn-success btn-sm" style="font-size:10px; border-radius:6px;">Gỡ Phạt</a><a href="/admin/action/{"unban" if is_banned else "ban"}/{safe_k}" class="btn btn-{"light" if is_banned else "danger"} btn-sm" style="font-size:10px; border-radius:6px;">{"Cứu" if is_banned else "Trảm"}</a><a href="/admin/action/delete/{safe_k}" class="btn btn-dark btn-sm" onclick="return confirm('Xóa vĩnh viễn Key này?')" style="font-size:10px; border-radius:6px;">🗑️</a></div></td></tr>'''

        blacklist_rows = "".join([f'<li class="list-group-item bg-transparent text-light d-flex justify-content-between align-items-center border-secondary border-bottom px-1" style="font-size:12px;">{escape(ip)} <a href="/admin/unban_ip/{escape(ip)}" class="btn btn-sm btn-danger p-0 px-2 rounded-pill">Gỡ</a></li>' for ip in banned_ips]) or '<li class="list-group-item bg-transparent text-muted text-center border-0" style="font-size:12px;">Sạch sẽ</li>'
        
        tg_admin_rows = "".join([f'<li class="list-group-item bg-transparent text-light d-flex justify-content-between align-items-center border-secondary border-bottom px-1" style="font-size:12px;">ID: {escape(str(tid))} {"(Chủ Tịch)" if str(tid)==TELEGRAM_CHAT_ID else f"<a href='/admin/del_tg_admin/{escape(str(tid))}' class='btn btn-sm btn-danger p-0 px-2 rounded-pill'>Xóa</a>"}</li>' for tid in tg_admins]) or '<li class="list-group-item bg-transparent text-muted text-center border-0" style="font-size:12px;">Chưa có</li>'
        
        safe_vm_script = escape(db.get("settings", {}).get("violentmonkey_script", DEFAULT_OLM_SCRIPT))

        return f'''
        <!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ADMIN DASHBOARD</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>{CSS_GLASS} h5{{font-weight:900;}} .table-container{{max-height:450px;overflow-y:auto;}}</style></head><body class="p-2 p-md-4">
        <div class="container-fluid">
            <div class="d-flex justify-content-between align-items-center mb-4 border-bottom border-secondary pb-3">
                <h3 class="m-0 text-neon fw-bold"><i class="fas fa-shield-alt"></i> LVT SECURE ADMIN</h3>
                <div>
                    <a href="/admin/hack_game" class="btn btn-warning btn-sm fw-bold rounded-pill px-3 me-2">🎮 HACK GAME</a>
                    <a href="/logout" class="btn btn-outline-danger btn-sm fw-bold rounded-pill px-3">Thoát</a>
                </div>
            </div>
            <div class="row g-4">
                <div class="col-lg-7">
                    <div class="card p-4 h-100" style="border-color:rgba(51,102,255,0.4);">
                        <h5 style="color:#3366ff; margin-bottom:20px;"><i class="fas fa-users"></i> DANH SÁCH USER</h5>
                        <div class="table-container table-responsive"><table class="table table-dark table-hover table-sm align-middle mb-0 text-center text-nowrap"><thead class="table-active"><tr><th>Tài Khoản</th><th>Số Dư</th><th>Keys Sỡ Hữu</th><th>IP Đăng Nhập</th><th>Cộng/Trừ Tiền</th></tr></thead><tbody>{users_html}</tbody></table></div>
                    </div>
                </div>
                <div class="col-lg-5">
                    <div class="row g-4 h-100">
                        <div class="col-md-12">
                            <div class="card p-4 h-100" style="border-color:rgba(0,255,204,0.4);">
                                <h5 style="color:#00ffcc; margin-bottom:15px;"><i class="fab fa-telegram"></i> CẤP QUYỀN TG ADMIN THAY BẠN</h5>
                                <form action="/admin/add_tg_admin" method="POST" class="d-flex gap-2 mb-3">
                                    <input type="text" name="tg_id" class="form-control form-control-sm m-0" placeholder="Nhập ID Telegram..." required>
                                    <button type="submit" class="btn btn-sm btn-info fw-bold px-3 rounded-pill text-dark">Cấp Quyền</button>
                                </form>
                                <ul class="list-group list-group-flush" style="max-height:120px;overflow-y:auto; border: 1px solid rgba(255,255,255,0.05); border-radius:8px; padding:5px;">{tg_admin_rows}</ul>
                            </div>
                        </div>
                        <div class="col-md-12">
                            <div class="card p-4 h-100" style="border-color:rgba(189,0,255,0.4);">
                                <h5 style="color:#bd00ff; margin-bottom:15px;"><i class="fas fa-key"></i> TẠO KEY MỚI</h5>
                                <form action="/admin/create" method="POST" class="row g-3">
                                    <div class="col-6"><input type="text" name="prefix" class="form-control form-control-sm m-0" placeholder="Mã (VD: TEST)"></div>
                                    <div class="col-6"><input type="number" name="quantity" class="form-control form-control-sm m-0" value="1" placeholder="Số Lượng"></div>
                                    <div class="col-6"><input type="number" name="duration" class="form-control form-control-sm m-0" placeholder="Độ dài" required></div>
                                    <div class="col-6"><select name="type" class="form-select form-select-sm m-0"><option value="hour">Giờ</option><option value="day" selected>Ngày</option><option value="month">Tháng</option><option value="permanent">V.Viễn</option></select></div>
                                    <div class="col-12 d-flex justify-content-center align-items-center"><div class="form-check form-switch fs-5 mt-1"><input class="form-check-input" type="checkbox" role="switch" name="is_vip" id="vipSwitch"><label class="form-check-label text-warning fw-bold ms-2" for="vipSwitch" style="font-size:14px;">🔑 Gắn mác VIP PRO</label></div></div>
                                    <div class="col-12"><button type="submit" class="btn btn-sm w-100 fw-bold py-2" style="background:linear-gradient(45deg, #bd00ff, #3366ff);color:white; border-radius:10px;">🚀 TẠO NGAY</button></div>
                                </form>
                            </div>
                        </div>
                        <div class="col-md-12">
                            <div class="card p-4 h-100" style="border-color:rgba(255,51,102,0.4);">
                                <h5 class="text-danger margin-bottom:15px;"><i class="fas fa-shield-virus"></i> FIREWALL BANS IP</h5>
                                <form action="/admin/ban_ip" method="POST" class="d-flex gap-2 mb-3"><input type="text" name="ip" class="form-control form-control-sm m-0" placeholder="Nhập IP..." required><button type="submit" class="btn btn-sm btn-danger fw-bold px-3 rounded-pill">Chặn</button></form>
                                <ul class="list-group list-group-flush" style="max-height:120px;overflow-y:auto; border: 1px solid rgba(255,255,255,0.05); border-radius:8px; padding:5px;">{blacklist_rows}</ul>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-lg-12">
                    <div class="card p-4 h-100" style="border-color:rgba(0,255,204,0.4);">
                        <div class="d-flex justify-content-between align-items-center mb-4"><h5 class="m-0 text-neon"><i class="fas fa-database"></i> TẤT CẢ MÃ KEY</h5><input type="text" class="form-control form-control-sm m-0" style="width:250px; background:rgba(0,0,0,0.3);" placeholder="🔍 Tìm Key..." onkeyup="let s=this.value.toLowerCase();document.querySelectorAll('.key-row').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(s)?'':'none');"></div>
                        <div class="table-container border border-secondary table-responsive"><table class="table table-dark table-sm align-middle table-hover text-center mb-0 text-nowrap"><thead class="table-active"><tr><th>🔑 Key / Chủ</th><th>⏳ Hạn Dùng</th><th>💻 Thiết bị</th><th>⚙️ Thao tác</th></tr></thead><tbody>{keys_html}</tbody></table></div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="modal fade" id="bindModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:rgba(17,17,26,0.95);border:1px solid #ffcc00; backdrop-filter: blur(15px);"><form action="/admin/bind_olm" method="POST"><div class="modal-body text-center p-4"><input type="hidden" name="key" id="bindKeyInput"><p class="text-white mb-2">Ghim Định Danh OLM cho Key:</p><p><strong id="bindKeyDisplay" class="text-info" style="word-break: break-all;"></strong></p><input type="text" name="olm_name" id="bindOlmInput" class="form-control mt-3" placeholder="Tên nick OLM khách (để trống: hủy)"></div><div class="modal-footer border-secondary p-2"><button type="submit" class="btn btn-warning w-100 fw-bold text-dark rounded-pill">Ghim Chặt Cứng</button></div></form></div></div></div>
        <div class="modal fade" id="addTimeModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:rgba(17,17,26,0.95);border:1px solid #00ffcc; backdrop-filter: blur(15px);"><form action="/admin/add_time" method="POST"><div class="modal-body text-center p-4"><input type="hidden" name="key" id="addTimeKeyInput"><p class="text-white mb-2">Thêm thời gian cho Key:</p><p><strong id="addTimeKeyDisplay" class="text-info" style="word-break: break-all;"></strong></p><input type="number" name="time_val" class="form-control mt-3" placeholder="Số lượng (Ví dụ: 10)" required><select name="time_unit" class="form-select mt-2" style="background-color:rgba(10,10,18,0.8); color:white;"><option value="hours">Giờ</option><option value="days" selected>Ngày</option><option value="months">Tháng</option></select></div><div class="modal-footer border-secondary p-2"><button type="submit" class="btn btn-info w-100 fw-bold text-dark rounded-pill">XÁC NHẬN CỘNG</button></div></form></div></div></div>
        
        <div class="modal fade" id="vmScriptModal" tabindex="-1" data-bs-theme="dark">
          <div class="modal-dialog modal-lg modal-dialog-centered">
            <div class="modal-content" style="background:rgba(17,17,26,0.95); border:1px solid #00ffcc; backdrop-filter: blur(15px);">
              <form action="/admin/update_vm_script" method="POST">
                  <div class="modal-header border-secondary">
                      <h5 class="modal-title" style="color:#00ffcc;font-weight:bold;">CẬP NHẬT CODE SCRIPT GỐC MỚI</h5>
                      <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                  </div>
                  <div class="modal-body p-4">
                      <p class="text-warning mb-2" style="font-size:13px;">⚠️ Dán toàn bộ Code Violentmonkey mới vào đây. Hệ thống sẽ TỰ ĐỘNG bóc tách Header, băm Body tạo Core ẩn và truyền quyền cho Loader.</p>
                      <textarea name="vm_script_content" class="form-control" rows="15" style="font-family:monospace; font-size:12px;">{safe_vm_script}</textarea>
                  </div>
                  <div class="modal-footer border-secondary p-3"><button type="submit" class="btn btn-info fw-bold w-100 text-dark rounded-pill">LƯU & XUẤT BẢN CODE MỚI</button></div>
              </form>
            </div>
          </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            function copyKey(t){{ navigator.clipboard.writeText(t); Swal.fire({{toast:true,position:'top-end',icon:'success',title:'Đã Copy!',showConfirmButton:false,timer:1000,background:'#111',color:'#00ffcc'}}); }}
            function openBindModal(key, current_olm) {{ document.getElementById('bindKeyInput').value = key; document.getElementById('bindKeyDisplay').innerText = key; document.getElementById('bindOlmInput').value = current_olm; new bootstrap.Modal(document.getElementById('bindModal')).show(); }}
            function openAddTimeModal(key) {{ document.getElementById('addTimeKeyInput').value = key; document.getElementById('addTimeKeyDisplay').innerText = key; new bootstrap.Modal(document.getElementById('addTimeModal')).show(); }}
        </script>
        </body></html>
        '''
    except Exception as e: return f"LỖI HỆ THỐNG: {str(e)}", 200

@app.route('/admin/add_tg_admin', methods=['POST'])
def add_tg_admin():
    if session.get('role') != 'admin': return redirect('/login')
    tg_id = request.form.get('tg_id', '').strip()
    db = load_db()
    with db_lock:
        admins = db.setdefault("settings", {}).setdefault("tg_admins", [TELEGRAM_CHAT_ID])
        if tg_id and tg_id not in admins:
            admins.append(tg_id)
            save_db(db)
    return swal_redirect("Thành công", f"Đã cấp quyền truy cập Mini App cho ID: {tg_id}", "success", "/admin")

@app.route('/admin/del_tg_admin/<path:tg_id>')
def del_tg_admin(tg_id):
    if session.get('role') != 'admin': return redirect('/login')
    if tg_id == TELEGRAM_CHAT_ID: return swal_back("Lỗi", "Không thể xóa quyền của Chủ Tịch (Bot Owner)!", "error")
    db = load_db()
    with db_lock:
        admins = db.setdefault("settings", {}).setdefault("tg_admins", [TELEGRAM_CHAT_ID])
        if tg_id in admins:
            admins.remove(tg_id)
            save_db(db)
    return redirect('/admin')

@app.route('/admin/add_balance', methods=['POST'])
def add_balance():
    if session.get('role') != 'admin': return redirect('/login')
    username = request.form.get('username')
    amt = safe_int(request.form.get('amount'))
    db = load_db()
    with db_lock:
        if username in db.get("users", {}):
            db["users"][username]["balance"] += amt
            if db["users"][username]["balance"] < 0: db["users"][username]["balance"] = 0
            if amt > 0: db["users"][username].setdefault("notices", []).append(f"Admin vừa nạp cho bạn +{amt:,}đ")
            elif amt < 0: db["users"][username].setdefault("notices", []).append(f"Admin vừa trừ của bạn {amt:,}đ")
            save_db(db)
    return redirect('/admin')

@app.route('/admin/create', methods=['POST'])
def create_key():
    if session.get('role') != 'admin': return redirect('/login')
    dur = safe_int(request.form.get('duration'))
    md = safe_int(request.form.get('maxDevices'), 1)
    qty = safe_int(request.form.get('quantity'), 1)
    t = request.form.get('type')
    vip = request.form.get('is_vip') == 'on'
    pfx = request.form.get('prefix', '').strip()
    db = load_db()
    with db_lock:
        for _ in range(qty):
            nk = generate_secure_key(pfx, vip)
            db["keys"][nk] = {"exp": "pending", "maxDevices": md, "devices": [], "known_ips": {}, "status": "active", "vip": vip, "loader_enabled": True, "violations": 0, "temp_ban_until": 0, "owner": "admin", "reset_count": 0, "bound_olm": ""}
            if t != 'permanent': db["keys"][nk]["durationMs"] = dur * {"hour":3600000, "day":86400000, "month":2592000000}.get(t, 60000)
            else: db["keys"][nk]["exp"] = "permanent"
        save_db(db)
    return redirect('/admin')

@app.route('/admin/add_time', methods=['POST'])
def admin_add_time():
    if session.get('role') != 'admin': return redirect('/login')
    key = request.form.get('key', '').strip()
    t_val = safe_int(request.form.get('time_val', 0))
    t_unit = request.form.get('time_unit', 'days')
    if t_val <= 0: return swal_back("Lỗi", "Số lượng > 0", "error")
    ms_to_add = 0
    if t_unit == 'hours': ms_to_add = t_val * 3600000
    elif t_unit == 'days': ms_to_add = t_val * 86400000
    elif t_unit == 'months': ms_to_add = t_val * 2592000000
    db = load_db()
    with db_lock:
        if key in db.get("keys", {}):
            kd = db["keys"][key]
            if kd.get("exp") == "permanent": return swal_back("Lỗi", "Key vĩnh viễn không cần cộng giờ!", "error")
            now = int(time.time() * 1000)
            if kd.get("exp") == "pending": kd["durationMs"] = kd.get("durationMs", 0) + ms_to_add
            else:
                current_exp = kd.get("exp", now)
                if current_exp < now: current_exp = now
                kd["exp"] = current_exp + ms_to_add
            save_db(db)
    return redirect('/admin')

@app.route('/admin/bind_olm', methods=['POST'])
def admin_bind_olm():
    if session.get('role') != 'admin': return redirect('/login')
    key = request.form.get('key', '').strip()
    olm = request.form.get('olm_name', '').strip()
    db = load_db()
    with db_lock:
        if key in db.get("keys", {}):
            db["keys"][key]["bound_olm"] = olm
            save_db(db)
    return redirect('/admin')

@app.route('/admin/update_vm_script', methods=['POST'])
def admin_update_vm_script():
    if session.get('role') != 'admin': return redirect('/login')
    ns = request.form.get('vm_script_content', '')
    if not ns.strip().startswith('// ==UserScript=='): return swal_back("Lỗi", "Script không hợp lệ", "error")
    db = load_db()
    with db_lock:
        db.setdefault("settings", {})["violentmonkey_script"] = ns
        save_db(db)
    return swal_redirect("Thành công", "Đã cập nhật Code mới", "success", "/admin")

@app.route('/admin/ban_ip', methods=['POST'])
def web_ban_ip():
    if session.get('role') != 'admin': return redirect('/login')
    ip = request.form.get('ip', '').strip()
    if ip:
        db = load_db()
        with db_lock:
            if ip not in db.setdefault("banned_ips", []):
                db["banned_ips"].append(ip)
                save_db(db)
    return redirect('/admin')

@app.route('/admin/unban_ip/<path:ip>')
def unban_ip(ip):
    if session.get('role') != 'admin': return redirect('/login')
    db = load_db()
    with db_lock:
        if ip in db.setdefault("banned_ips", []):
            db["banned_ips"].remove(ip)
            save_db(db)
    return redirect('/admin')

@app.route('/admin/action/<action>/<key>')
def key_actions(action, key):
    if session.get('role') != 'admin': return redirect('/login')
    db = load_db()
    with db_lock:
        if key in db.get("keys", {}):
            kd = db["keys"][key]
            if action == 'ban': kd['status'] = 'banned'
            elif action == 'unban': 
                kd['status'] = 'active'
                kd['temp_ban_until'] = 0
                kd['violations'] = 0
            elif action == 'unban_temp':
                kd['temp_ban_until'] = 0
                kd['violations'] = 0
            elif action == 'delete': 
                db["keys"].pop(key, None)
                for u in db["users"]: db["users"][u]["purchased_keys"] = [pk for pk in db["users"][u].get("purchased_keys", []) if pk["key"] != key]
            elif action == 'reset-dev':
                kd['devices'] = []
                kd['known_ips'] = {}
            save_db(db)
    return redirect('/admin')

# ========================================================
# MODULE HACK GAME (QUẢN LÝ KEY 15 KÝ TỰ BẢO MẬT)
# ========================================================
@app.route('/admin/hack_game')
def admin_hack_game():
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    with db_lock:
        game_keys = list(db.get("game_keys", {}).items())

    now_ms = int(time.time() * 1000)
    keys_html = ''
    
    for k, data in sorted(game_keys, key=lambda x: x[1].get('exp', 0) if isinstance(x[1].get('exp'), int) else 9999999999999, reverse=True):
        st = data.get('status', 'active')
        is_banned = (st == 'banned')
        status_badge = '<span class="badge bg-success">Hoạt động</span>' if not is_banned else '<span class="badge bg-danger text-light border border-light">BỊ KHÓA</span>'
        
        is_expired = False
        if data.get('exp') == 'pending': 
            exp_text = '<span class="text-info fw-bold">Chưa kích hoạt</span>'
        elif data.get('exp') == 'permanent': 
            exp_text = '<span class="text-success fw-bold">Vĩnh Viễn</span>'
        else:
            is_expired = now_ms > data.get('exp', 0)
            exp_text = f'<span class="{"text-danger fw-bold" if is_expired else "text-light"}">{time.strftime("%d/%m/%Y %H:%M", time.localtime(data.get("exp", 0) / 1000))}</span>'
        
        if is_expired and not is_banned: status_badge = '<span class="badge bg-secondary">HẾT HẠN</span>'
        
        safe_k = escape(str(k))
        dev_count = len(data.get('devices', []))
        max_dev = data.get('maxDevices', 1)
        
        keys_html += f'''
        <tr class="align-middle text-nowrap">
            <td>
                <strong class="text-warning fs-6" style="cursor:pointer;" onclick="copyKey('{safe_k}')" title="Bấm để copy">{safe_k}</strong><br>
                {status_badge}
            </td>
            <td>{exp_text}</td>
            <td><span class="badge bg-info text-dark fs-6">{dev_count} / {max_dev}</span></td>
            <td>
                <div class="d-flex gap-1 justify-content-center">
                    <button class="btn btn-sm btn-info fw-bold text-dark rounded-pill" onclick="openGameTimeModal('{safe_k}')">⏳ Thêm Giờ</button>
                    <button class="btn btn-sm btn-warning fw-bold text-dark rounded-pill" onclick="openDeviceModal('{safe_k}')">💻 Thêm Máy</button>
                    <a href="/admin/hack_game/action/{"unban" if is_banned else "ban"}/{safe_k}" class="btn btn-sm btn-{"light" if is_banned else "danger"} fw-bold rounded-pill">{"Mở Khóa" if is_banned else "Band Key"}</a>
                    <a href="/admin/hack_game/action/delete/{safe_k}" class="btn btn-sm btn-dark border-secondary rounded-pill" onclick="return confirm('Xóa vĩnh viễn Key Game này?')">🗑️</a>
                </div>
            </td>
        </tr>'''

    return f'''
    <!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>QUẢN LÝ HACK GAME</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <style>{CSS_GLASS}</style></head><body class="p-4">
    <div class="container">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h3 class="text-neon fw-bold">🎮 BẢNG ĐIỀU KHIỂN HACK GAME</h3>
            <a href="/admin" class="btn btn-outline-light rounded-pill">⬅ Trở về Admin Lõi</a>
        </div>
        
        <div class="card p-4 mb-4" style="border-color:#ffcc00; background:rgba(17,17,26,0.8);">
            <h5 class="text-warning fw-bold mb-3">🚀 TẠO KEY HACK GAME (15 KÍ TỰ ĐẶC BIỆT)</h5>
            <form action="/admin/hack_game/create" method="POST" class="row g-3">
                <div class="col-md-3">
                    <input type="number" name="quantity" class="form-control" value="1" placeholder="Số lượng key cần tạo" required>
                </div>
                <div class="col-md-3">
                    <input type="number" name="time_val" class="form-control" placeholder="Nhập thời gian" required>
                </div>
                <div class="col-md-3">
                    <select name="time_unit" class="form-select bg-dark text-light border-secondary">
                        <option value="minutes">Phút</option>
                        <option value="hours">Giờ</option>
                        <option value="days" selected>Ngày</option>
                        <option value="months">Tháng</option>
                        <option value="years">Năm</option>
                        <option value="permanent">Vĩnh Viễn</option>
                    </select>
                </div>
                <div class="col-md-3">
                    <button type="submit" class="btn w-100 fw-bold" style="background:#ffcc00; color:#000;">TẠO KEY NGAY</button>
                </div>
            </form>
        </div>

        <div class="card p-4" style="border-color:#00ffcc; background:rgba(17,17,26,0.8);">
            <h5 class="text-info fw-bold mb-3">🔑 DANH SÁCH KEY GAME HIỆN TẠI</h5>
            <div class="table-responsive" style="max-height:500px; overflow-y:auto;">
                <table class="table table-dark table-hover text-center">
                    <thead class="table-active"><tr><th>Mã Key Hack</th><th>Hạn Sử Dụng</th><th>Thiết Bị (Mặc định 1)</th><th>Bảng Điều Khiển Key</th></tr></thead>
                    <tbody>{keys_html}</tbody>
                </table>
            </div>
        </div>
    </div>

    <div class="modal fade" id="timeModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:rgba(17,17,26,0.95);border:1px solid #00ffcc;"><form action="/admin/hack_game/add_time" method="POST"><div class="modal-body text-center p-4"><input type="hidden" name="key" id="timeKeyInput"><p class="text-white mb-2">Thêm thời gian cho Key:</p><h6 id="timeKeyDisplay" class="text-warning mb-3"></h6><input type="number" name="t_val" class="form-control mb-2" placeholder="Giá trị" required><select name="t_unit" class="form-select"><option value="minutes">Phút</option><option value="hours">Giờ</option><option value="days" selected>Ngày</option><option value="months">Tháng</option><option value="years">Năm</option></select></div><div class="modal-footer p-2"><button type="submit" class="btn btn-info w-100 fw-bold rounded-pill">CỘNG THÊM</button></div></form></div></div></div>

    <div class="modal fade" id="deviceModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:rgba(17,17,26,0.95);border:1px solid #ffcc00;"><form action="/admin/hack_game/add_device" method="POST"><div class="modal-body text-center p-4"><input type="hidden" name="key" id="devKeyInput"><p class="text-white mb-2">Mở rộng giới hạn máy cho Key:</p><h6 id="devKeyDisplay" class="text-info mb-3"></h6><input type="number" name="dev_add" class="form-control" value="1" placeholder="Thêm bao nhiêu máy?" required></div><div class="modal-footer p-2"><button type="submit" class="btn btn-warning w-100 fw-bold rounded-pill">CẤP PHÉP</button></div></form></div></div></div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function copyKey(t){{ navigator.clipboard.writeText(t); Swal.fire({{toast:true,position:'top',icon:'success',title:'Đã Copy!',showConfirmButton:false,timer:1000,background:'#111',color:'#00ffcc'}}); }}
        function openGameTimeModal(key) {{ document.getElementById('timeKeyInput').value = key; document.getElementById('timeKeyDisplay').innerText = key; new bootstrap.Modal(document.getElementById('timeModal')).show(); }}
        function openDeviceModal(key) {{ document.getElementById('devKeyInput').value = key; document.getElementById('devKeyDisplay').innerText = key; new bootstrap.Modal(document.getElementById('deviceModal')).show(); }}
    </script>
    </body></html>'''

@app.route('/admin/hack_game/create', methods=['POST'])
def game_key_create():
    if session.get('role') != 'admin': return redirect('/admin_login')
    qty = safe_int(request.form.get('quantity'), 1)
    t_val = safe_int(request.form.get('time_val'), 0)
    t_unit = request.form.get('time_unit')
    
    multipliers = {"minutes": 60000, "hours": 3600000, "days": 86400000, "months": 2592000000, "years": 31536000000}
    
    db = load_db()
    with db_lock:
        for _ in range(qty):
            new_key = generate_game_key_15()
            key_data = {
                "exp": "pending",
                "maxDevices": 1, 
                "devices": [],
                "status": "active"
            }
            if t_unit == 'permanent': 
                key_data["exp"] = "permanent"
            else:
                key_data["durationMs"] = t_val * multipliers.get(t_unit, 0)
            
            db.setdefault("game_keys", {})[new_key] = key_data
        save_db(db)
    return redirect('/admin/hack_game')

@app.route('/admin/hack_game/add_time', methods=['POST'])
def game_key_add_time():
    if session.get('role') != 'admin': return redirect('/admin_login')
    key = request.form.get('key', '')
    t_val = safe_int(request.form.get('t_val'), 0)
    t_unit = request.form.get('t_unit')
    
    multipliers = {"minutes": 60000, "hours": 3600000, "days": 86400000, "months": 2592000000, "years": 31536000000}
    ms_to_add = t_val * multipliers.get(t_unit, 0)
    
    db = load_db()
    with db_lock:
        if key in db.get("game_keys", {}):
            k_data = db["game_keys"][key]
            if k_data.get("exp") != "permanent":
                if k_data.get("exp") == "pending":
                    k_data["durationMs"] = k_data.get("durationMs", 0) + ms_to_add
                else:
                    now = int(time.time() * 1000)
                    curr_exp = max(k_data.get("exp", now), now)
                    k_data["exp"] = curr_exp + ms_to_add
            save_db(db)
    return redirect('/admin/hack_game')

@app.route('/admin/hack_game/add_device', methods=['POST'])
def game_key_add_device():
    if session.get('role') != 'admin': return redirect('/admin_login')
    key = request.form.get('key', '')
    dev_add = safe_int(request.form.get('dev_add'), 1)
    
    db = load_db()
    with db_lock:
        if key in db.get("game_keys", {}):
            db["game_keys"][key]["maxDevices"] = db["game_keys"][key].get("maxDevices", 1) + dev_add
            save_db(db)
    return redirect('/admin/hack_game')

@app.route('/admin/hack_game/action/<action>/<key>')
def game_key_actions(action, key):
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    with db_lock:
        if key in db.get("game_keys", {}):
            if action == 'ban': 
                db["game_keys"][key]["status"] = "banned"
            elif action == 'unban': 
                db["game_keys"][key]["status"] = "active"
            elif action == 'delete': 
                del db["game_keys"][key]
            save_db(db)
    return redirect('/admin/hack_game')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
