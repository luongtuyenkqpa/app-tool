import os, json, time, random, hashlib, threading, requests, shutil, base64, secrets, hmac, string, copy, traceback
import urllib.parse
from html import escape
from flask import Flask, request, jsonify, redirect, make_response, session, abort

# [VÁ LỖI LỆCH MÚI GIỜ CLOUD]
try:
    os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
    time.tzset()
except: pass

app = Flask(__name__)

# ========================================================
# HỆ THỐNG BOT TELEGRAM & MINI APP CAO CẤP
# ========================================================
TELEGRAM_BOT_TOKEN = "8714375866:AAG9r0aCCFOKtgR6B-LcFYBAnJ7x9yMs-8o"
TELEGRAM_CHAT_ID = "7363320876"
# Đổi link này thành link web thực tế của bạn trên Render
WEB_URL = "https://app-tool-trlp.onrender.com" 

def send_telegram_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=5)
    except: pass

def send_telegram_backup():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        with open(DB_FILE, 'rb') as f:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"📦 BACKUP DATABASE LVT TOOL\nThời gian: {time.strftime('%d/%m/%Y %H:%M:%S')}"}, files={"document": f}, timeout=10)
    except: pass

# LUỒNG POLLING TELEGRAM
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
                        
                        if chat_id != TELEGRAM_CHAT_ID: continue
                        
                        text = msg.get("text", "").strip()
                        msg_id = msg.get("message_id")
                        
                        if text.startswith("/start"):
                            # Xóa tin nhắn /start để dọn dẹp UI
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage", json={"chat_id": chat_id, "message_id": msg_id})
                            
                            welcome = "🌟 <b>HỆ THỐNG LVT MINI APP</b> 🌟\n\n"
                            welcome += "Hệ thống quản trị đồ họa cao cấp đã sẵn sàng. Vui lòng ấn nút bên dưới để khởi chạy App!"
                            
                            # Tích hợp nút mở Telegram Mini App
                            keyboard = {
                                "inline_keyboard": [
                                    [{"text": "📱 MỞ LVT APP 📱", "web_app": {"url": f"{WEB_URL}/telegram_mini_app"}}]
                                ]
                            }
                            requests.post(url_base + "/sendMessage", json={"chat_id": chat_id, "text": welcome, "parse_mode": "HTML", "reply_markup": keyboard})
                        
                        # Giữ nguyên các lệnh text cũ làm phương án dự phòng
                        elif text.startswith("/naptien"):
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
                        
                        elif text.startswith("/check"):
                            parts = text.split()
                            if len(parts) >= 2:
                                uname = parts[1].lower()
                                db = load_db()
                                u = db.get("users", {}).get(uname)
                                if u:
                                    keys_info = "".join([f"- <code>{pk['key'][:10]}...</code>\n" for pk in u.get("purchased_keys", [])]) or "Không có key nào."
                                    send_telegram_alert(f"👤 <b>USER: {uname}</b>\n💰 Số dư: {u.get('balance', 0):,}đ\n🔑 <b>Key:</b>\n{keys_info}")
                                else: send_telegram_alert(f"❌ Không tìm thấy user: {uname}")
                        
                        elif text.startswith("/banolm"):
                            parts = text.split()
                            if len(parts) >= 4:
                                olm_name = parts[1]
                                try:
                                    duration = int(parts[2])
                                    unit = parts[3].lower()
                                    multiplier = {"s": 1000, "m": 60000, "h": 3600000, "d": 86400000}.get(unit)
                                    if not multiplier: continue
                                    exp_time = int(time.time() * 1000) + (duration * multiplier)
                                    db = load_db()
                                    with db_lock:
                                        db.setdefault("banned_olms", {})[olm_name] = exp_time
                                        save_db(db)
                                    send_telegram_alert(f"🚫 Đã cấm OLM: <b>{olm_name}</b>\n⏳ Thời gian: {duration}{unit}")
                                except ValueError: pass
                        
                        elif text.startswith("// ==UserScript=="):
                            db = load_db()
                            with db_lock:
                                db.setdefault("settings", {})["violentmonkey_script"] = text
                                log_admin_action(db, "TeleBot: Cập nhật Script Gốc")
                                save_db(db)
                            send_telegram_alert("✅ Đã xuất bản Code mới!")
        except Exception as e: print("LỖI BOT TELE:", str(e))
        time.sleep(2)

threading.Thread(target=telegram_polling, daemon=True).start()

# GLOBAL EXCEPTION CATCHER
@app.errorhandler(Exception)
def handle_exception(e):
    error_detail = traceback.format_exc()
    send_telegram_alert(f"<b>CRITICAL CRASH NGĂN CHẶN THÀNH CÔNG:</b>\n<pre>{error_detail[-300:]}</pre>")
    return "Hệ thống đang bảo trì.", 500

# BẢO MẬT FLASK SESSION
app.secret_key = os.environ.get('SECRET_KEY', hashlib.sha256(f"LVT_SECURE_KEY_2026_VIP".encode()).hexdigest())
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

DB_FILE = './database.json'
DB_BACKUP = './database.backup.json'

db_lock = threading.RLock()
api_rate_lock = threading.Lock()

active_sessions = {}
api_rate_cache = {}
bad_sig_cache = {} 
used_signatures = {} 

GLOBAL_DB = {}
_last_db_mtime = 0
_last_mtime_check = 0 

# ========================================================
# TRANG GIAO DIỆN TELEGRAM MINI APP (ĐẸP NHƯ ẢNH YÊU CẦU)
# ========================================================
@app.route('/telegram_mini_app')
def telegram_mini_app():
    # Thống kê thực tế từ DB để hiển thị lên App
    db = load_db()
    total_keys = len(db.get("keys", {}))
    active_keys = sum(1 for k, v in db.get("keys", {}).items() if v.get("status") == "active" and (v.get("exp") == "permanent" or v.get("exp") == "pending" or (isinstance(v.get("exp"), int) and v.get("exp") > int(time.time()*1000))))
    expired_keys = total_keys - active_keys

    html_content = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>LVT Mini App</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;800&display=swap');
            body {{
                background-color: #0f111a;
                color: #ffffff;
                font-family: 'Be Vietnam Pro', sans-serif;
                margin: 0;
                padding: 20px;
                -webkit-tap-highlight-color: transparent;
            }}
            .top-bar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }}
            .promo-tag {{
                background: linear-gradient(90deg, #ff416c, #ff4b2b);
                padding: 6px 12px;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 800;
                display: flex;
                align-items: center;
                gap: 5px;
            }}
            .user-id-badge {{
                background: rgba(255, 255, 255, 0.05);
                padding: 6px 12px;
                border-radius: 8px;
                font-size: 12px;
                color: #8892b0;
                border: 1px solid rgba(255,255,255,0.1);
            }}
            .profile-section {{ text-align: center; margin-bottom: 30px; }}
            .avatar-circle {{
                width: 90px;
                height: 90px;
                border-radius: 50%;
                background: linear-gradient(135deg, #667eea, #764ba2);
                display: inline-flex;
                align-items: center;
                justify-content: center;
                font-size: 35px;
                font-weight: 800;
                border: 3px solid #00ffcc;
                box-shadow: 0 0 20px rgba(0,255,204,0.4);
                margin-bottom: 15px;
            }}
            .profile-name {{ font-size: 20px; font-weight: 800; margin: 0; }}
            .profile-username {{ font-size: 13px; color: #8892b0; margin-top: 5px; }}
            .verified-badge {{ color: #1d9bf0; margin-left: 5px; font-size: 14px; }}
            
            .stats-container {{
                display: flex;
                background: #1a1d29;
                border-radius: 16px;
                padding: 15px;
                margin-bottom: 30px;
                border: 1px solid rgba(255,255,255,0.05);
            }}
            .stat-box {{ flex: 1; text-align: center; }}
            .stat-value {{ font-size: 18px; font-weight: 800; }}
            .stat-label {{ font-size: 11px; color: #8892b0; margin-top: 4px; text-transform: uppercase; }}
            .stat-divider {{ width: 1px; background: rgba(255,255,255,0.1); margin: 0 10px; }}
            
            .section-title {{ font-size: 16px; font-weight: 800; margin-bottom: 15px; display: flex; align-items: center; gap: 10px; }}
            .action-card {{
                background: #1a1d29;
                border-radius: 16px;
                padding: 20px;
                border: 1px solid rgba(255,255,255,0.05);
            }}
            .select-btn {{
                background: #232736;
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 12px;
                padding: 15px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 15px;
                cursor: pointer;
            }}
            .select-btn-left {{ display: flex; align-items: center; gap: 15px; }}
            .icon-box {{
                width: 40px;
                height: 40px;
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 18px;
            }}
            .icon-green {{ background: rgba(34, 197, 94, 0.1); color: #22c55e; }}
            .btn-primary {{
                background: linear-gradient(90deg, #667eea, #764ba2);
                border: none;
                width: 100%;
                padding: 15px;
                border-radius: 12px;
                color: white;
                font-size: 16px;
                font-weight: 800;
                cursor: pointer;
                opacity: 0.5;
            }}
        </style>
    </head>
    <body>
        <div class="top-bar">
            <div class="promo-tag"><i class="fas fa-fire"></i> LVT ADMIN</div>
            <div class="user-id-badge" id="displayUserId">...</div>
        </div>

        <div class="profile-section">
            <div class="avatar-circle" id="avatarInitials">LT</div>
            <h2 class="profile-name" id="displayName">Admin <i class="fas fa-check-circle verified-badge"></i></h2>
            <div class="profile-username" id="displayUsername">@luongtuyen20</div>
        </div>

        <div class="stats-container">
            <div class="stat-box">
                <div class="stat-value" style="color: #fff;">{total_keys}</div>
                <div class="stat-label">Tổng key</div>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-box">
                <div class="stat-value" style="color: #22c55e;">{active_keys}</div>
                <div class="stat-label">Hoạt động</div>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-box">
                <div class="stat-value" style="color: #f59e0b;">{expired_keys}</div>
                <div class="stat-label">Hết hạn</div>
            </div>
        </div>

        <div class="section-title"><i class="fas fa-shopping-cart"></i> Menu Điều Khiển Nhanh</div>
        <div class="action-card">
            <div style="font-size: 13px; color: #8892b0; margin-bottom: 10px;"><i class="fas fa-cube text-primary"></i> Quản lý OLM</div>
            <div class="select-btn" onclick="alert('Chức năng đang mở rộng trên App. Vui lòng dùng lệnh bot bên ngoài.');">
                <div class="select-btn-left">
                    <div class="icon-box icon-green"><i class="fas fa-gamepad"></i></div>
                    <div>
                        <div style="font-size: 15px; font-weight: 800;">Tạo / Quản lý Key</div>
                        <div style="font-size: 12px; color: #8892b0;">Hệ thống lõi VIP</div>
                    </div>
                </div>
                <i class="fas fa-chevron-right" style="color: #8892b0;"></i>
            </div>
            <button class="btn-primary" onclick="Telegram.WebApp.close()">Đóng Ứng Dụng</button>
        </div>

        <script>
            // Khởi tạo Telegram Web App
            let tg = window.Telegram.WebApp;
            tg.expand(); // Mở full màn hình

            // Tự động lấy tên và ID của người dùng Telegram để hiển thị cho đẹp
            let user = tg.initDataUnsafe.user;
            if (user) {{
                document.getElementById('displayUserId').innerText = user.id;
                document.getElementById('displayName').innerHTML = user.first_name + ' <i class="fas fa-check-circle verified-badge"></i>';
                document.getElementById('displayUsername').innerText = user.username ? '@' + user.username : 'Admin';
                
                // Tạo Avatar chữ cái đầu
                let initials = (user.first_name.charAt(0) + (user.last_name ? user.last_name.charAt(0) : '')).toUpperCase();
                document.getElementById('avatarInitials').innerText = initials;
            }}
        </script>
    </body>
    </html>
    """
    return render_template_string_safe(html_content)

def render_template_string_safe(content):
    resp = make_response(content)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp

# ========================================================
# SCRIPT VIOLENTMONKEY MẶC ĐỊNH & CÁC HÀM CŨ (GIỮ NGUYÊN)
# ========================================================
DEFAULT_OLM_SCRIPT = r"""// ==UserScript==
// @name         OLM GOD MODE VIP - DEV.TIỆP
// @namespace    http://tampermonkey.net/
// @version      13.0
// @description  Hệ thống bảo vệ đa tầng. Phân luồng Key VIP và Key Thường.
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
    if (window.top !== window.self) return;

    const Config = { VERSION: '13.0', API_KEYWORDS: ['get-question-of-ids', 'get-question?belongs=1'] };

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
                let scripts = document.getElementsByTagName('script');
                for (let i = 0; i < scripts.length; i++) {
                    let text = scripts[i].innerHTML;
                    if (text && text.includes('"username"')) {
                        let match = text.match(/"username"\s*:\s*"([^"]+)"/);
                        if (match && match[1] && match[1] !== "hp_luongvantuyen") {
                            found = match[1].trim();
                            break; 
                        }
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
        formatNumber: (num) => (typeof num === 'number' ? num.toLocaleString('vi-VN') : '0')
    };

    const HintParser = {
        _extractTextFromNode(node) {
            let text = '';
            if (!node) return text;
            if (node.text) text += node.text;
            if (node.children && Array.isArray(node.children)) {
                text += node.children.map(child => this._extractTextFromNode(child)).join('');
            }
            return text;
        },
        _deepScanJsonNode(node, hints, parentNode = null, q_type = 0) {
            if (!node || typeof node !== 'object') return;
            let identified = false;

            if (q_type === 10 && node.name === 'group-list' && node.children) {
                node.children.forEach((listItem, index) => {
                    if (listItem.type !== 'olm-list-item' || !listItem.children) return;
                    const titleNode = listItem.children.find(c => c.type === 'group-title');
                    const title = titleNode ? this._extractTextFromNode(titleNode).trim() : 'Nhóm';
                    const answers = listItem.children.filter(c => c.position === 'group').map(c => this._extractTextFromNode(c).trim()).filter(Boolean);
                    if (answers.length > 0) {
                        hints.push({ type: 'Kéo nhóm', content: `${title}: ${answers.join(', ')}`, subIndex: index + 1 });
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
                                hints.push({ type: 'Điền từ', content: part, subIndex: qNum });
                            });
                        });
                        identified = true;
                    }
                }
            }

            if (!identified && node.correct === true && (node.type === 'olm-list-item' || node.type === 'list-item')) {
                const text = this._extractTextFromNode(node).trim();
                if (text) {
                    const type = (node.name === 'true-false' || (parentNode && parentNode.name === 'true-false')) ? 'Đúng/Sai' : 'Trắc nghiệm';
                    hints.push({ type, content: text.replace(/^#/, '').trim(), subIndex: null });
                    identified = true;
                }
            }

            if (!identified && q_type !== 2 && q_type !== 3) {
                if (node.type === 'fillme-input' && node.content) {
                    node.content.split('||').map(s => s.trim()).filter(Boolean).forEach(part => hints.push({ type: 'Điền từ', content: part, subIndex: null }));
                    identified = true;
                }
                if (!identified && node.type === 'olm-input-text' && node.name === 'dragtext' && node.content) {
                    node.content.split('||').map(s => s.trim()).filter(Boolean).forEach(part => hints.push({ type: 'Điền từ', content: part, subIndex: null }));
                    identified = true;
                }
                if (!identified && node.type === 'drag-more-item' && node.children) {
                    const text = this._extractTextFromNode(node).trim();
                    if (text) { hints.push({ type: 'Kéo thả', content: text, subIndex: null }); identified = true; }
                }
            }

            if (!identified && node.type === 'olm-list-item' && parentNode && parentNode.name === 'link-list' && Array.isArray(node.children)) {
                const leftNode = node.children.find(c => c.position === 'left');
                const rightNode = node.children.find(c => c.position === 'right');
                if (leftNode && rightNode) {
                    const leftText = this._extractTextFromNode(leftNode).trim();
                    const rightText = this._extractTextFromNode(rightNode).trim();
                    if (leftText && rightText) { hints.push({ type: 'Nối', content: `${leftText} ➔ ${rightText}`, subIndex: null }); identified = true; }
                }
            }

            if (!identified && Array.isArray(node.children) && node.children.length >= 3) {
                const pieces = node.children.map(ch => (ch.text || '').trim()).filter(Boolean);
                if (pieces.length >= 3 && pieces.every(t => /^[A-Za-zÀ-ỹ0-9'’.,!?-]+$/.test(t))) {
                    hints.push({ type: 'Sắp xếp', content: pieces.join(' '), subIndex: null });
                    identified = true;
                }
            }

            if (!identified && node.name === 'exp' && (q_type === 18 || q_type === 11) && node.children) {
                const text = this._extractTextFromNode(node).trim();
                const cleanText = text.replace(/^Hư[ơớ]ng d[ẫâ]n gi[aả]i:?/i, '').trim();
                if (cleanText) { hints.push({ type: (q_type === 11) ? 'Chọn từ' : 'Tự luận', content: cleanText, subIndex: null }); identified = true; }
            }

            if (!identified && node.children && Array.isArray(node.children)) {
                 node.children.forEach(child => this._deepScanJsonNode(child, hints, node, q_type));
            }
        },
        parse(question) {
            const hints = [];
            if (question.json_content) {
                try {
                    const data = typeof question.json_content === 'string' ? JSON.parse(question.json_content) : question.json_content;
                    if (data && data.root) this._deepScanJsonNode(data.root, hints, null, question.q_type);
                } catch (e) {}
            }
            if (question.content) {
                const htmlContent = Utils.decodeBase64(question.content);
                if (htmlContent) {
                    const tempDiv = Utils.createElement('div', { innerHTML: htmlContent });
                    tempDiv.querySelectorAll('.correctAnswer, .correct-answer').forEach(el => {
                        const text = el.textContent.trim();
                        if (text) hints.push({ type: 'Gợi ý (cũ)', content: text });
                    });
                    const inputAccept = tempDiv.querySelector('input[data-accept]');
                    if (inputAccept) {
                        (inputAccept.getAttribute('data-accept') || '').split('|').forEach(ans => {
                            if (ans.trim()) hints.push({ type: 'Điền từ (cũ)', content: ans.trim() });
                        });
                    }
                    if (question.q_type === 18 || question.q_type === 11) {
                        const explanationDiv = tempDiv.querySelector('.exp .exp-in');
                        if (explanationDiv) {
                            const expText = Array.from(explanationDiv.childNodes).map(n => (n.textContent || '').trim()).filter(Boolean).join('\n');
                            if (expText) hints.push({ type: (question.q_type === 11) ? 'Chọn từ' : 'Tự luận', content: expText });
                        }
                    }
                }
            }
            const uniqueHints = [];
            const seen = new Set();
            for (const hint of hints) {
                const key = (hint.content || '').toLowerCase();
                if (!key || seen.has(key)) continue;
                seen.add(key);
                uniqueHints.push(hint);
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
                    Utils.createElement('span', { className: 'study-footer-left', children: ['Tiệp Gà Cui • OLM Assistant'] }),
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
            this.contentArea.appendChild(Utils.createElement('div', { className: 'study-no-data', children: ['🔍 Đang chờ dữ liệu câu hỏi từ OLM...'] }));
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
                const isHiddenType = (hint.type === 'Trắc nghiệm' || hint.type === 'Đúng/Sai' || (hint.type === 'Điền từ' && hint.subIndex) || hint.type === 'Chọn từ');
                const label = Utils.createElement('span', { className: 'hint-type-label', children: [`[${hint.type}]`], style: { display: isHiddenType ? 'none' : 'inline-block' } });
                const body = Utils.createElement('span', { className: 'hint-text', innerHTML: (hint.content || '').replace(/\n/g, '<br>') });
                return Utils.createElement('li', { children: [label, body], style: { borderLeftColor: (hint.type === 'Trắc nghiệm' || hint.type === 'Chọn từ') ? '#22c55e' : '#6366f1' } });
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
            if (Config.API_KEYWORDS.some(k => url.includes(k))) {
                try { const d = JSON.parse(textData); const q = d?.questions || d; if (Array.isArray(q) && q.length > 0) return q; } catch (e) {}
            }
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
                    const cleanOptionText = (option.textContent || option.value || '').trim().replace(/\s+/g, ' ').replace(/\s/g, '').replace(/&nbsp;/g, '');
                    if (!cleanOptionText) return;
                    if (hintTexts.some(hint => {
                        const cleanHint = (hint || '').replace(/\\/g, '').replace(/\s/g, '').replace(/&nbsp;/g, '');
                        return cleanOptionText && (cleanOptionText.includes(cleanHint) || cleanHint.includes(cleanOptionText));
                    })) {
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
            this.panel.clearData(); this.panel.setVisible(true);
            this.panel.setSummary({ questionCount: processed.length, hintCount: processed.reduce((sum, item) => sum + (item.hints?.length || 0), 0), statusText: 'Đã lấy dữ liệu' });
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
                        if (hintsForPanel.length > 1 && hintsForPanel.every(h => h.type === 'Điền từ')) { hintsForPanel[0].content = hintsForPanel.map(h => h.content).join(' | '); hintsForPanel.splice(1); }
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
                .hint-type-label { font-size: 10px; border-radius: 999px; background: rgba(55, 65, 81, 0.9); padding: 2px 5px; flex-shrink: 0; }
                .hint-text { line-height: 1.4; }
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

    function showKeyPrompt(errorMsg = "") {
        if(document.getElementById('tiep-auth-overlay')) return;
        const authDiv = document.createElement('div');
        authDiv.id = 'tiep-auth-overlay';
        authDiv.style.cssText = "position:fixed;inset:0;background:rgba(5,5,10,0.98);z-index:2147483647;display:flex;align-items:center;justify-content:center;font-family:sans-serif;";
        authDiv.innerHTML = `
            <div style="background:#0a0a12; border:2px solid #00ffcc; padding:40px; border-radius:15px; text-align:center; width:400px;">
                <h2 style="color:#00ffcc;">OLM VIP PRO</h2>
                <div style="color:#fff; font-size:16px; margin:25px 0; padding:15px; background:rgba(0,255,204,0.1); border:1px solid #00ffcc; border-radius:8px; font-weight:bold;">⚠️ VUI LÒNG ĐĂNG NHẬP KEY<br>Ở WEB ĐỂ SỬ DỤNG</div>
                <div style="color:#ff3366; font-size:14px; margin-top:15px; font-weight:bold;">${errorMsg}</div>
                <div style="margin-top:30px;"><a href="${SERVER_URL}" target="_blank" style="color:#00ffcc; font-weight:bold; text-decoration:none; border-bottom:1px dashed #00ffcc;">🌍 ĐI TỚI WEBSITE</a></div>
            </div>
        `;
        (document.body || document.documentElement).appendChild(authDiv);
    }
    
    function kickUserToWeb(msg) {
        GM_setValue('lvt_olm_vip_key', ''); 
        try {
            let desc = Object.getOwnPropertyDescriptor(Document.prototype, 'cookie') || Object.getOwnPropertyDescriptor(HTMLDocument.prototype, 'cookie');
            if (desc && desc.set) desc.set.call(document, "username=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;");
            else document.cookie = "username=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
        } catch(e) { document.cookie = "username=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;"; }
        sessionStorage.removeItem('tiep_welcomed');

        let kickDiv = document.createElement('div');
        kickDiv.style.cssText = "position:fixed;inset:0;background:rgba(20,0,0,0.98);z-index:2147483647;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff;font-family:sans-serif;text-align:center;padding:20px;";
        kickDiv.innerHTML = `<div style="font-size:60px;margin-bottom:10px;">⚠️</div><h1 style="color:#ff3366;">TRUY CẬP BỊ TỪ CHỐI</h1><p style="color:#ccc;max-width:600px;">${msg}</p>`;
        (document.body || document.documentElement).appendChild(kickDiv);
        setTimeout(() => { window.location.href = window.location.pathname; }, 4000); 
    }

    function initVipHackSystem(activeKey) {
        const CORE_URL = 'https://fakemoithu.io.vn/core.js';
        let cachedCore = GM_getValue('tiep_core_cache', '');
        const currentUrl = window.location.href;
        const isTargetPage = currentUrl.includes('/chu-de/') || currentUrl.includes('/bai-kiem-tra/') || currentUrl.includes('/video') || currentUrl.includes('/luyen-tap');
        const hasSeenLoader = sessionStorage.getItem('tiep_loader_seen');

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
                    console.log("[LVT] Kích hoạt Hack VIP");
                    initVipHackSystem(savedKey);
                } else {
                    console.log("[LVT] Kích hoạt Hack Thường");
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
                
                if "violentmonkey_script" not in data["settings"]:
                    data["settings"]["violentmonkey_script"] = DEFAULT_OLM_SCRIPT
                
                if "admin" not in data["users"]:
                    data["users"]["admin"] = {"password_hash": hash_pwd("120510@"), "role": "admin", "balance": 0, "created_at": int(time.time() * 1000), "ips": [], "purchased_keys": [], "notices": [], "custom_script": 'console.log("HACK OLM BY LVT ĐÃ KÍCH HOẠT!");\n// Dán code hack gốc vào đây...'}
                
                for u in data["users"]:
                    data["users"][u].setdefault("notices", [])
                    data["users"][u].setdefault("custom_script", "")

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

def log_admin_action(db, action_text):
    db.setdefault("admin_logs", []).insert(0, {"time": int(time.time() * 1000), "action": action_text})
    db["admin_logs"] = db["admin_logs"][:100]

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
            
        if request.path.startswith("/admin") and request.path not in ["/admin_login", "/login", "/register", "/logout"]:
            if session.get('role') != 'admin':
                return redirect('/admin_login')
    except: pass

@app.errorhandler(404)
def not_found_trap(e):
    return "Not Found", 404

@app.route('/api/ping', methods=['GET'])
def uptime_ping():
    return jsonify({"status": "alive", "timestamp": int(time.time())}), 200

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
    with db_lock:
        banned_olms = db.get("banned_olms", {})
        if req_olm_name != "N/A" and req_olm_name in banned_olms:
            ban_exp = banned_olms[req_olm_name]
            if ban_exp == "permanent" or ban_exp > now:
                return False, "Tài khoản OLM này đã bị Admin đưa vào danh sách cấm sử dụng Tool!"

        if key not in db["keys"]: return False, "Mã Key không tồn tại!"
        kd = db["keys"][key]
        if kd.get('status') == 'banned': return False, "TÀI KHOẢN BỊ KHÓA: Key của bạn đã bị Admin ban vĩnh viễn!"
        
        temp_ban = kd.get("temp_ban_until", 0)
        if temp_ban > now:
            rem = (temp_ban - now) // 60000
            return False, f"PHẠT SHARE KEY: Key đang bị khóa tạm thời. Thử lại sau {rem} phút."

        db_changed = False
        if kd.get('exp') == 'pending': 
            kd['exp'] = now + kd.get('durationMs', 0)
            db_changed = True
            
        if kd.get('exp') != 'permanent' and now > kd.get('exp', 0): 
            return False, "KEY HẾT HẠN: Vui lòng lên Web mua Key mới!"
        
        bound_olm = kd.get("bound_olm", "").strip()
        if bound_olm and req_olm_name != "N/A":
            if bound_olm.lower() != req_olm_name.lower():
                kd["status"] = "banned"
                db.setdefault("security_alerts", []).insert(0, {"time": now, "id": ip, "user": req_olm_name, "reason": f"Sử dụng sai định danh"})
                save_db(db)
                return False, f"GIAN LẬN: Key này chỉ dành cho tài khoản [{bound_olm}]. Key đã bị Khóa Vĩnh Viễn!"

        if deviceId:
            devices = kd.setdefault("devices", [])
            if deviceId not in devices:
                if len(devices) >= kd.get("maxDevices", 1): return False, "VƯỢT THIẾT BỊ: Key đã đạt giới hạn thiết bị tối đa!"
                devices.append(deviceId)
                db_changed = True
        
        if db_changed: save_db(db)
        return True, "Success"

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
        valid, msg = _core_validate(db, key, deviceId, olm_name, ip)
        if not valid: return jsonify({"status": "error", "message": msg}), 400

        is_vip = db["keys"][key].get("vip", False)
        key_type = "VIP" if is_vip else "NORMAL"

        return jsonify({
            "status": "success", 
            "loader_enabled": db["keys"][key].get("loader_enabled", True),
            "assigned_user": db["keys"][key].get("bound_olm", ""),
            "key_type": key_type 
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
        valid, _ = _core_validate(db, key, deviceId, olm_name, ip)
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
        if line.strip().startswith('// ==UserScript=='):
            in_header = True
        elif line.strip().startswith('// ==/UserScript=='):
            in_header = False
        elif not in_header:
            body.append(line)
    body_str = '\n'.join(body)
    quoted_body = urllib.parse.quote(body_str)
    b64 = base64.b64encode(quoted_body.encode('utf-8')).decode('utf-8')
    rev_b64 = b64[::-1]
    
    anti_debug = """
    const _0xLVT = function() {
        let _0x = new Date().getTime();
        setInterval(() => {
            let _0y = new Date().getTime();
            if (_0y - _0x > 1000) { while(true) { eval("debugger"); } }
            _0x = new Date().getTime();
            try { Function("debugger")(); } catch(e) {}
        }, 300);
    };
    _0xLVT();
    """
    secure_core = f"""
    (function() {{
        {anti_debug}
        try {{
            const _0x3c = "{rev_b64}";
            const _0x4d = _0x3c.split('').reverse().join('');
            const _0x5e = decodeURIComponent(atob(_0x4d));
            eval(_0x5e); 
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
            in_header = True
            header.append(line)
        elif line.strip().startswith('// ==/UserScript=='):
            header.append(line)
            in_header = False
            break
        elif in_header:
            header.append(line)
            
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

    setInterval(() => {{
        const t1 = performance.now();
        eval("debugger;");
        const t2 = performance.now();
        if (t2 - t1 > 150) {{ 
            document.body.innerHTML = "<div style='background:#05050A;color:#ff3366;height:100vh;display:flex;align-items:center;justify-content:center;font-family:sans-serif;font-size:28px;font-weight:bold;text-transform:uppercase;'>HỆ THỐNG BẢO MẬT LVT: GIAN LẬN BỊ PHÁT HIỆN</div>";
            window.location.href = "about:blank";
        }}
    }}, 1000);

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

CSS_GLASS = """
body { background-color: #05050A !important; color: #fff !important; font-family: 'Segoe UI', Tahoma, sans-serif; min-height: 100vh; margin:0; }
.glass-panel { background-color: rgba(17, 17, 26, 0.8) !important; border: 1px solid rgba(255, 255, 255, 0.1) !important; border-radius: 20px !important; box-shadow: 0 10px 40px rgba(0,0,0,0.8) !important; padding: 40px; text-align: center; width: 100%; max-width: 400px; margin: 50px auto; backdrop-filter: blur(12px); }
.card { background-color: rgba(17, 17, 26, 0.9) !important; border-radius: 16px !important; border: 1px solid rgba(255,255,255,0.05) !important; box-shadow: 0 8px 32px rgba(0,0,0,0.5) !important; transition: 0.3s; backdrop-filter: blur(10px); }
.card:hover { border-color: rgba(0,255,204,0.4) !important; transform: translateY(-3px); box-shadow: 0 10px 25px rgba(0,255,204,0.15) !important; }
h2, h3, h4, h5 { color: #00ffcc !important; font-weight: 900 !important; letter-spacing: 1px !important; }
.text-neon { color: #00ffcc !important; text-shadow: 0 0 12px rgba(0,255,204,0.6) !important; }
.text-purple { color: #bd00ff !important; text-shadow: 0 0 12px rgba(189,0,255,0.6) !important; }
.balance-card { background: linear-gradient(135deg, rgba(0, 255, 204, 0.15), rgba(189, 0, 255, 0.1)); border: 1px solid rgba(0, 255, 204, 0.4); border-radius: 16px; padding: 20px 25px; display: flex; align-items: center; justify-content: space-between; backdrop-filter: blur(10px); box-shadow: 0 10px 30px rgba(0,255,204,0.1); }
.balance-card .balance-amount { font-size: 32px; font-weight: 900; color: #00ffcc; text-shadow: 0 0 15px rgba(0,255,204,0.5); line-height: 1; margin-top: 5px; }
.launch-card { background: linear-gradient(135deg, rgba(189, 0, 255, 0.15), rgba(0, 153, 255, 0.1)); border: 1px solid rgba(189, 0, 255, 0.4); border-radius: 16px; padding: 20px 25px; display: flex; flex-direction: column; justify-content: center; backdrop-filter: blur(10px); text-align: center; height: 100%; transition: 0.3s; box-shadow: 0 10px 30px rgba(189,0,255,0.1); }
.launch-card:hover { box-shadow: 0 10px 30px rgba(189,0,255,0.3); border-color: #bd00ff; cursor: pointer; }
.form-control, .form-select, textarea { background-color: rgba(10, 10, 18, 0.8) !important; border: 1px solid rgba(255,255,255,0.1) !important; color: #fff !important; padding: 12px; border-radius: 10px; margin-bottom: 15px; }
.form-control:focus, .form-select:focus, textarea:focus { border-color: #00ffcc !important; box-shadow: 0 0 12px rgba(0,255,204,0.3) !important; outline: none !important; }
.btn-neon { background: linear-gradient(45deg, #00ffcc, #bd00ff) !important; border: none !important; color: #000 !important; font-weight: bold !important; width: 100%; padding: 12px; border-radius: 10px; transition: 0.3s !important; cursor: pointer; text-transform: uppercase; letter-spacing: 1px; box-shadow: 0 5px 15px rgba(0,255,204,0.2) !important; }
.btn-neon:hover { transform: translateY(-2px) !important; box-shadow: 0 8px 25px rgba(0,255,204,0.5) !important; }
a.link-neon { color: #bd00ff !important; text-decoration: none !important; font-weight: bold !important; transition: 0.3s !important; }
a.link-neon:hover { color: #00ffcc !important; text-shadow: 0 0 10px #00ffcc !important; }
.table-container { border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); overflow-x: auto; -webkit-overflow-scrolling: touch; }
.table { color: #fff !important; margin-bottom: 0; white-space: nowrap; }
.table-dark { --bs-table-bg: transparent !important; --bs-table-striped-bg: rgba(0, 255, 204, 0.05) !important; border-color: rgba(255,255,255,0.05) !important; }
.table-active { background-color: rgba(255,255,255,0.05) !important; }
tbody tr:hover { background: rgba(0,255,204,0.05) !important; }
.badge { font-size: 11px !important; padding: 5px 8px !important; border-radius: 6px; font-weight: 700; letter-spacing: 0.5px; }
.text-nowrap { white-space: nowrap !important; }
"""

@app.route('/')
def home():
    try:
        shop_html = ""
        for pkg_id, pkg in SHOP_PACKAGES.items():
            vip_tag = '<div class="badge bg-danger mb-2">🔥 VIP PRO</div>' if pkg["vip"] else '<div class="badge bg-secondary mb-2">THƯỜNG</div>'
            border_c = "#bd00ff" if pkg["vip"] else "#0099ff"
            desc_html = f'<p class="text-warning mb-1" style="font-size:12px;">{pkg["desc"]}</p>' if pkg.get("desc") else ''
            
            shop_html += f'''
            <div class="col-md-3 col-6 mb-3">
                <div class="card p-3 h-100 text-center" style="border-color:{border_c};">
                    {vip_tag}
                    <h5 class="text-white fw-bold">{pkg["name"]}</h5>
                    {desc_html}
                    <div style="font-size:22px;font-weight:900;color:{border_c};margin:10px 0;">{pkg["price"]:,}đ</div>
                    <a href="/login" class="btn btn-outline-info w-100 mt-auto fw-bold" style="border-radius:8px;">MUA NGAY</a>
                </div>
            </div>'''

        welcome_script = ""
        if not session.get('welcomed'):
            session['welcomed'] = True
            welcome_script = "Swal.fire({ title: 'CHÀO MỪNG ĐẾN VỚI LVT TOOL!', html: '<b style=\"color:#00ffcc\">Hệ thống tự động hóa và bảo mật đỉnh cao.</b><br><br>👉 Vui lòng Đăng nhập hoặc Đăng ký để trải nghiệm!', icon: 'success', background: '#11111A', color: '#fff', confirmButtonColor: '#bd00ff', confirmButtonText: 'ĐÃ HIỂU' });"

        return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>LVT TOOL - Trang Chủ</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>{CSS_GLASS} .hero{{background:linear-gradient(135deg,#000,#0a192f);padding:80px 20px;text-align:center;border-bottom:1px solid rgba(0,255,204,0.3);}}</style></head><body>
        <div class="hero"><h1 class="text-neon fw-bold mb-3">⚡ HỆ THỐNG LVT TOOL VIP ⚡</h1><p class="text-secondary fs-5 mb-4">Tự động hóa thông minh - Bảo mật đa tầng - Kích hoạt trên thiết bị cực dễ</p><a href="#shop" class="btn btn-lg fw-bold mb-2" style="background:#00ffcc;color:#000;border-radius:10px;">XEM BẢNG GIÁ</a> <a href="/login" class="btn btn-outline-info btn-lg fw-bold ms-md-2 mb-2" style="border-radius:10px;">ĐĂNG NHẬP LẤY KEY</a> <a href="/register" class="btn btn-outline-light btn-lg fw-bold ms-md-2 mb-2" style="border-radius:10px;">ĐĂNG KÝ</a></div>
        <div class="container py-5" id="shop"><h2 class="text-center text-neon fw-bold mb-5">BẢNG GIÁ DỊCH VỤ</h2><div class="row justify-content-center">{shop_html}</div></div><script>{welcome_script}</script></body></html>'''
    except Exception as e: return f"LỖI HỆ THỐNG: {str(e)}", 200

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if 'username' in session: 
            if session.get('role') == 'admin': return redirect('/admin')
            return redirect('/dashboard')

        if request.method == 'POST':
            username = request.form.get('username', '').strip().lower()
            password = request.form.get('password', '').strip()
            db = load_db()
            user_data = db.get("users", {}).get(username)
            if user_data and user_data.get("password_hash") == hash_pwd(password):
                session['username'] = username
                session['role'] = user_data.get("role", "user")
                ip = get_real_ip()
                with db_lock:
                    if ip not in db["users"][username].setdefault("ips", []): db["users"][username]["ips"].append(ip)
                    save_db(db)
                return swal_redirect("Thành công!", f"Chào mừng {username.upper()} quay trở lại.", "success", "/dashboard" if session['role'] != 'admin' else "/admin")
            else:
                return swal_back("Thất bại!", f"Sai tài khoản hoặc mật khẩu.", "error")

        return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Đăng Nhập</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>{CSS_GLASS}</style></head><body><div class="glass-panel"><h2 class="text-neon mb-4">⚡ ĐĂNG NHẬP</h2><form method="POST"><input type="text" name="username" class="form-control" placeholder="Tên đăng nhập" required><input type="password" name="password" class="form-control" placeholder="Mật khẩu" required><button type="submit" class="btn-neon mt-2">VÀO HỆ THỐNG</button></form><div class="mt-4"><p class="text-secondary">Chưa có tài khoản? <a href="/register" class="link-neon">Đăng ký ngay</a></p><a href="/" class="text-muted" style="text-decoration:none;font-size:13px;"><i class="fas fa-home"></i> Trở về Trang chủ</a></div></div></body></html>'''
    except Exception as e: return f"LỖI HỆ THỐNG: {str(e)}", 200

@app.route('/register', methods=['GET', 'POST'])
def register():
    try:
        if 'username' in session: return redirect('/')
        if request.method == 'POST':
            username = request.form.get('username', '').strip().lower()
            password = request.form.get('password', '').strip()
            if not username.isalnum() or len(username) < 4: return swal_back("Lỗi", "Tên đăng nhập > 4 ký tự và không có dấu!", "warning")
            if len(password) < 6: return swal_back("Lỗi", "Mật khẩu từ 6 ký tự trở lên!", "warning")

            db = load_db()
            with db_lock:
                if username in db.setdefault("users", {}): return swal_back("Lỗi", "Tên đăng nhập đã tồn tại!", "error")
                db["users"][username] = {"password_hash": hash_pwd(password), "role": "user", "balance": 0, "created_at": int(time.time() * 1000), "ips": [get_real_ip()], "purchased_keys": [], "notices": [], "custom_script": ""}
                save_db(db)
            
            send_telegram_alert(f"🎉 <b>CÓ NGƯỜI ĐĂNG KÝ WEB MỚI</b>\n- User: <code>{username}</code>\n- IP: {get_real_ip()}\n<i>(Mật khẩu đã được mã hóa Hash SHA-256 an toàn, không hiển thị để bảo mật)</i>")
            return swal_redirect("Tuyệt vời!", "Đăng ký thành công. Hãy đăng nhập!", "success", "/login")

        return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Đăng Ký</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>{CSS_GLASS}</style></head><body><div class="glass-panel"><h2 class="text-neon mb-4">⚡ TẠO TÀI KHOẢN</h2><form method="POST"><input type="text" name="username" class="form-control" placeholder="Tên đăng nhập (liền không dấu)" required><input type="password" name="password" class="form-control" placeholder="Mật khẩu (Tối thiểu 6 ký tự)" required><button type="submit" class="btn-neon mt-2">ĐĂNG KÝ NGAY</button></form><div class="mt-4"><p class="text-secondary">Đã có tài khoản? <a href="/login" class="link-neon">Đăng nhập</a></p><a href="/" class="text-muted" style="text-decoration:none;font-size:13px;"><i class="fas fa-home"></i> Trở về Trang chủ</a></div></div></body></html>'''
    except Exception as e: return f"LỖI HỆ THỐNG: {str(e)}", 200

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/user_transfer_key', methods=['POST'])
def user_transfer_key():
    try:
        if 'username' not in session or session.get('role') != 'user': return redirect('/login')
        username = session['username']
        old_key = request.form.get('old_key', '').strip()
        new_olm = request.form.get('new_olm', '').strip()

        if not old_key or not new_olm:
            return swal_back("Lỗi", "Vui lòng nhập đầy đủ thông tin!", "warning")

        db = load_db()
        with db_lock:
            u = db["users"].get(username)
            kd = db["keys"].get(old_key)
            
            if not kd or old_key not in [k["key"] for k in u.get("purchased_keys", [])]:
                return swal_back("Lỗi", "Key không tồn tại hoặc không thuộc về bạn!", "error")
            
            is_vip = kd.get("vip", False)
            if not is_vip:
                return swal_back("Từ chối!", "Tính năng DEEP RESET chỉ dành riêng cho Key VIP PRO!", "error")

            if new_olm.lower() == kd.get("bound_olm", "").lower():
                return swal_back("Lỗi", "Nick OLM mới phải KHÁC nick OLM hiện tại!", "warning")

            rc = kd.get("reset_count", 0)
            if rc >= 2:
                return swal_back("Giới hạn", "Key này đã hết lượt Reset (Tối đa 2 lần)!", "error")

            fee = 0 if rc == 0 else 10000

            if u["balance"] < fee:
                return swal_back("Thất bại!", f"Bạn cần {fee:,}đ để Deep Reset từ lần thứ 2.", "error")

            u["balance"] -= fee
            
            new_key = generate_secure_key("TOOL", is_vip)
            
            db["keys"][new_key] = {
                "exp": kd.get("exp"),
                "durationMs": kd.get("durationMs", 0),
                "maxDevices": kd.get("maxDevices", 1),
                "devices": [],
                "known_ips": {},
                "status": kd.get("status", "active"),
                "vip": is_vip,
                "loader_enabled": kd.get("loader_enabled", True),
                "violations": kd.get("violations", 0),
                "temp_ban_until": kd.get("temp_ban_until", 0),
                "owner": kd.get("owner"),
                "os": kd.get("os", "android"),
                "reset_count": rc + 1,
                "bound_olm": new_olm
            }
            
            for pk in u.get("purchased_keys", []):
                if pk["key"] == old_key:
                    pk["key"] = new_key
                    break
                    
            del db["keys"][old_key]
            save_db(db)

        if session.get('active_key') == old_key:
            session['active_key'] = new_key

        html_msg = f"""<div style='text-align:left; font-size:14px;'>
            <p>Phí chuyển đổi: <b>{fee:,}đ</b></p>
            <p>Đã ghim OLM mới: <b style='color:#ff3366'>{escape(new_olm)}</b></p>
            <p>Mã Key <strong class="text-success">MỚI TINH</strong> của bạn là:</p>
            <div style='background:#000; padding:10px; border:1px dashed #00ffcc; border-radius:5px; text-align:center; font-family:monospace; font-size:18px; color:#00ffcc; margin-bottom:15px; cursor:pointer;' onclick='navigator.clipboard.writeText("{new_key}");Swal.showValidationMessage("Đã copy!");'>{new_key}</div>
            <p class='text-warning mt-2' style='font-size:12px;'>*Key cũ đã bị vô hiệu hóa hoàn toàn khỏi hệ thống.</p>
        </div>"""
        
        return swal_redirect("🎉 ĐỔI KEY VÀ NICK THÀNH CÔNG!", html_msg, "success", "/dashboard")

    except Exception as e: return swal_back("Lỗi", str(e), "error")

@app.route('/dashboard')
def user_dashboard():
    try:
        if 'username' not in session or session.get('role') != 'user': return redirect('/login')
        
        username = session['username']
        db = load_db()
        user_data = db["users"].get(username, {})
        balance = user_data.get("balance", 0)
        owned_keys = user_data.get("purchased_keys", [])
        
        notices = user_data.get("notices", [])
        swal_scripts = ""
        if notices:
            msg = "<br>".join(notices)
            swal_scripts = f"Swal.fire({{title: 'TING TING 💰', html: '{msg}', icon: 'success', background: '#11111A', color: '#00ffcc'}});"
            with db_lock:
                db["users"][username]["notices"] = []
                save_db(db)

        shop_html = ""
        for pkg_id, pkg in SHOP_PACKAGES.items():
            vip_tag = '<div class="badge bg-danger mb-2">🔥 VIP PRO</div>' if pkg["vip"] else '<div class="badge bg-secondary mb-2">THƯỜNG</div>'
            border_c = "#bd00ff" if pkg["vip"] else "#0099ff"
            desc_html = f'<p class="text-warning mb-1" style="font-size:12px;">{pkg["desc"]}</p>' if pkg.get("desc") else ''
            
            shop_html += f'''
            <div class="col-lg-3 col-6 mb-3">
                <div class="card p-3 h-100 text-center" style="border-color:{border_c}; cursor:pointer;" onclick="confirmBuy('{pkg_id}', '{pkg['name']}', {pkg['price']})">
                    {vip_tag}
                    <h6 class="text-white fw-bold mt-1">{pkg['name']}</h6>
                    {desc_html}
                    <h4 style="color:{border_c}; font-weight:900; margin: 10px 0;">{pkg['price']:,}đ</h4>
                    <button class="btn btn-sm w-100 fw-bold mt-auto" style="background:rgba(255,255,255,0.1); color:{border_c}; border: 1px solid {border_c}; border-radius:8px;">MUA NGAY</button>
                </div>
            </div>'''

        now = int(time.time() * 1000)
        my_keys_html = ""
        for pk in owned_keys:
            k = pk['key']
            kd = db["keys"].get(k)
            if not kd: continue 
            
            st = kd.get('status', 'active')
            is_banned = (st == 'banned')
            temp_ban = kd.get('temp_ban_until', 0)
            
            status_html = '<span class="badge bg-success">Hoạt động</span>'
            if is_banned: status_html = '<span class="badge bg-danger">Bị khóa</span>'
            elif temp_ban > now: status_html = f'<span class="badge bg-warning text-dark">Phạt ({(temp_ban - now)//60000}p)</span>'

            exp = kd.get("exp")
            if exp == "permanent": exp_str = '<span class="text-success fw-bold">Vĩnh viễn</span>'
            elif exp == "pending": exp_str = '<span class="text-info">Chưa KH</span>'
            else:
                if exp < now: 
                    exp_str = '<span class="text-danger">Hết hạn</span>'
                    if not is_banned: status_html = '<span class="badge bg-secondary">Hết hạn</span>'
                else: 
                    exp_str = f'<span class="text-warning">{time.strftime("%d/%m/%y", time.localtime(exp/1000))}</span>'
                
            rc = kd.get("reset_count", 0)
            is_vip = kd.get("vip", False)
            vip_icon = "💎 " if is_vip else "🔑 "
            bound_olm = kd.get("bound_olm", "")
            bound_str = f'<span class="text-warning fw-bold">{escape(bound_olm)}</span>' if bound_olm else '<span class="text-muted">Chưa ghim</span>'

            my_keys_html += f'''
            <tr class="text-nowrap">
                <td><strong class="text-info" style="cursor:pointer;" onclick="copyMyKey('{k}')" title="Bấm Copy">{vip_icon}{k[:8]}... <i class="fas fa-copy text-secondary fs-6"></i></strong></td>
                <td>{status_html}</td>
                <td>{exp_str}</td>
                <td>{rc}/2 lần</td>
                <td>{bound_str}</td>
                <td>
                    <div class="d-flex justify-content-center gap-2">
                        <button class="btn btn-sm btn-outline-warning fw-bold py-1 px-2" style="font-size:11px; border-radius:6px;" onclick="confirmTransfer('{k}', '{escape(bound_olm)}', {rc}, {'true' if is_vip else 'false'})" title="Đổi Mã Key & Đổi Nick">DEEP RESET</button>
                        <form action="/user_delete_key" method="POST" onsubmit="return confirm('Bạn có chắc chắn muốn xóa vĩnh viễn Key này khỏi tài khoản?');" class="m-0">
                            <input type="hidden" name="key_to_delete" value="{k}">
                            <button type="submit" class="btn btn-sm btn-outline-danger fw-bold py-1 px-2" style="font-size:11px; border-radius:6px;">XÓA</button>
                        </form>
                    </div>
                </td>
            </tr>
            '''
        if not my_keys_html:
            my_keys_html = '<tr><td colspan="6" class="text-muted py-4">Bạn chưa có Key nào. Vui lòng mua Key bên trên!</td></tr>'

        return f'''
        <!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Dashboard - User</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>{CSS_GLASS}</style></head>
        <body class="p-2 p-md-4">
        <div class="container" style="max-width:1100px;">
            <div class="d-flex flex-column flex-md-row justify-content-between align-items-center mb-4 border-bottom border-secondary pb-3">
                <h2 class="text-neon mb-3 mb-md-0 m-0"><i class="fas fa-bolt"></i> LVT SHOP CÁ NHÂN</h2>
                <div><span class="me-3">Xin chào, <b class="text-info">{username.upper()}</b></span> <a href="/logout" class="btn btn-sm btn-outline-danger fw-bold rounded-pill px-3">Thoát</a></div>
            </div>
            
            <div class="row g-4 mb-4">
                <div class="col-md-6">
                    <div class="balance-card">
                        <div>
                            <div style="font-size: 12px; color: #9ca3af; letter-spacing: 1px;">SỐ DƯ TÀI KHOẢN</div>
                            <div class="balance-amount">{balance:,}đ</div>
                        </div>
                        <div>
                            <a href="https://zalo.me/0343627516" target="_blank" class="btn btn-sm btn-outline-info fw-bold rounded-pill px-3 py-2 text-nowrap">NẠP TIỀN AUTO</a>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="launch-card cursor-pointer" onclick="window.location.href='/key_login'">
                        <h4 class="text-purple m-0 fw-bold"><i class="fas fa-rocket"></i> VÀO KHOANG LÁI HACK</h4>
                        <div class="text-muted mt-2" style="font-size: 13px;">Đăng nhập Key để kích hoạt Hack OLM.</div>
                    </div>
                </div>
            </div>

            <div class="row g-4">
                <div class="col-12">
                    <div class="card p-4 border-secondary h-100">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h4 class="text-info m-0 fw-bold"><i class="fas fa-shopping-cart"></i> MUA M mã KEY MỚI</h4>
                        </div>
                        <div class="row g-2">{shop_html}</div>
                    </div>
                </div>
                
                <div class="col-12">
                    <div class="card p-3 border-secondary">
                        <h5 class="text-purple mb-3 fw-bold"><i class="fas fa-key"></i> QUẢN LÝ KEY CỦA BẠN</h5>
                        <div class="table-container table-responsive">
                            <table class="table table-dark table-hover table-sm align-middle text-center mb-0 text-nowrap">
                                <thead class="table-active">
                                    <tr><th>🔑 Mã Key (Copy)</th><th>🟢 Trạng thái</th><th>⏳ Hạn dùng</th><th>🔄 Lượt Reset</th><th>👤 OLM Đã Ghim</th><th>⚙️ Thao tác</th></tr>
                                </thead>
                                <tbody>
                                    {my_keys_html}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <form id="buyForm" action="/buy" method="POST"><input type="hidden" name="pkg_id" id="pkgInput"><input type="hidden" name="os_type" id="osInput"><input type="hidden" name="olm_name" id="olmInput"></form>
        <form id="transferForm" action="/user_transfer_key" method="POST"><input type="hidden" name="old_key" id="transOldKeyInput"><input type="hidden" name="new_olm" id="transNewOlmInput"></form>

        <script>
            {swal_scripts}
            function copyMyKey(k) {{ navigator.clipboard.writeText(k); Swal.fire({{toast:true,position:'top-end',icon:'success',title:'Đã copy Key!',showConfirmButton:false,timer:1500,background:'#111',color:'#fff'}}); }}
            
            function confirmBuy(id, name, price) {{
                Swal.fire({{
                    title: 'CHỈ ĐỊNH TÀI KHOẢN OLM',
                    html: `<p>Gói <b>${{name}}</b> (${{price.toLocaleString()}}đ)</p>
                           <input type="text" id="swal-olm" class="swal2-input" placeholder="Nhập nick OLM (Ví dụ: hp_luongvantuyen)" style="width: 80%; background: rgba(10,10,18,0.8); color: #00ffcc; border: 1px solid #00ffcc; border-radius:10px;">
                           <div style="margin-top: 15px; font-size: 14px;">
                               <b>CHỌN HỆ ĐIỀU HÀNH BẠN ĐANG XÀI:</b><br>
                               <label class="me-3 mt-2"><input type="radio" name="swal-os" value="android" checked> <i class="fab fa-android"></i> Android/PC</label>
                               <label class="mt-2"><input type="radio" name="swal-os" value="ios"> <i class="fab fa-apple"></i> iOS</label>
                           </div>`,
                    icon: 'info', showCancelButton: true, confirmButtonText: 'MUA NGAY', cancelButtonText: 'Hủy',
                    background: '#11111A', color: '#fff', confirmButtonColor: '#bd00ff',
                    preConfirm: () => {{
                        const olm = document.getElementById('swal-olm').value.trim();
                        const os = document.querySelector('input[name="swal-os"]:checked').value;
                        if(!olm) {{ Swal.showValidationMessage('Bạn phải nhập tên tài khoản OLM!'); }}
                        return {{ olm: olm, os: os }};
                    }}
                }}).then((res) => {{
                    if(res.isConfirmed) {{
                        document.getElementById('pkgInput').value = id;
                        document.getElementById('osInput').value = res.value.os;
                        document.getElementById('olmInput').value = res.value.olm;
                        document.getElementById('buyForm').submit();
                    }}
                }});
            }}

            function confirmTransfer(oldKey, currentOlm, resetCount, isVip) {{
                if (!isVip) {{
                    Swal.fire({{ title: 'Từ chối', text: 'Chức năng Deep Reset chỉ dành cho Key VIP PRO!', icon: 'error', background: '#11111A', color: '#fff' }});
                    return;
                }}
                if (resetCount >= 2) {{
                    Swal.fire({{ title: 'Giới hạn', text: 'Key này đã hết lượt Reset (Tối đa 2 lần).', icon: 'error', background: '#11111A', color: '#fff' }});
                    return;
                }}
                let fee = resetCount === 0 ? "Miễn phí (Lần 1)" : "10,000đ (Lần 2)";
                Swal.fire({{
                    title: 'DEEP RESET KEY & ĐỔI NICK OLM',
                    html: `
                        <div style="text-align:left; font-size:14px; margin-bottom: 15px; background:rgba(255,255,255,0.05); padding:10px; border-radius:8px;">
                            <p class="mb-1">Nick đang ghim: <b class="text-danger">${{currentOlm || 'Chưa có'}}</b></p>
                            <p class="mb-0">Phí đổi: <b class="text-warning">${{fee}}</b></p>
                        </div>
                        <p class="text-info fw-bold mb-3" style="font-size:13px;">Hệ thống sẽ tạo 1 mã Key HOÀN TOÀN MỚI và chuyển toàn bộ ngày sử dụng sang nick OLM mới.</p>
                        <input type="text" id="swal-new-olm" class="swal2-input" placeholder="Nhập nick OLM MỚI (Bắt buộc)" style="width: 85%; background: rgba(10,10,18,0.8); color: #00ffcc; border: 1px solid #00ffcc; border-radius:10px; margin:0 auto;">
                    `,
                    icon: 'warning', showCancelButton: true, confirmButtonText: 'ĐỔI NGAY', cancelButtonText: 'Hủy',
                    background: '#11111A', color: '#fff', confirmButtonColor: '#bd00ff',
                    preConfirm: () => {{
                        const newOlm = document.getElementById('swal-new-olm').value.trim();
                        if(!newOlm) {{ Swal.showValidationMessage('Vui lòng nhập nick OLM mới!'); return false; }}
                        if(newOlm.toLowerCase() === currentOlm.toLowerCase()) {{ Swal.showValidationMessage('Nick mới phải KHÁC nick cũ!'); return false; }}
                        return newOlm;
                    }}
                }}).then((res) => {{
                    if(res.isConfirmed) {{
                        document.getElementById('transOldKeyInput').value = oldKey;
                        document.getElementById('transNewOlmInput').value = res.value;
                        document.getElementById('transferForm').submit();
                    }}
                }});
            }}
        </script>
        </body></html>
        '''
    except Exception as e: return f"LỖI HỆ THỐNG: {str(e)}", 200

@app.route('/buy', methods=['POST'])
def buy_key():
    try:
        if 'username' not in session or session.get('role') != 'user': return redirect('/login')
        username = session['username']
        pkg_id = request.form.get('pkg_id')
        os_type = request.form.get('os_type', 'android')
        olm_name = request.form.get('olm_name', '').strip()
        
        if pkg_id not in SHOP_PACKAGES: return swal_back("Lỗi", "Gói không tồn tại!", "error")
        pkg = SHOP_PACKAGES[pkg_id]
        price = pkg['price']
        
        db = load_db()
        with db_lock:
            user_data = db["users"].get(username)
            if user_data['balance'] < price: return swal_back("Số Dư Không Đủ!", "Hãy nạp thêm tiền.", "warning")
            
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
            
        html_msg = f"""<div style='text-align:left; font-size:14px;'><p>Gói mua: <b class='text-purple'>{pkg['name']}</b> ({'iOS' if os_type=='ios' else 'Android/PC'})</p><p>Ghim OLM: <b style='color:#ff3366'>{escape(olm_name)}</b></p><p>Mã Key của bạn là:</p>
            <div style='background:#000; padding:10px; border:1px dashed #00ffcc; border-radius:5px; text-align:center; font-family:monospace; font-size:18px; color:#00ffcc; margin-bottom:15px; cursor:pointer;' onclick='navigator.clipboard.writeText("{nk}");Swal.showValidationMessage("Đã copy!");'>{nk}</div></div>"""
        return swal_redirect("🎉 MUA KEY THÀNH CÔNG!", html_msg, "success", "/dashboard")
    except Exception as e: return swal_back("Lỗi", f"Có lỗi xảy ra: {str(e)}", "error")

@app.route('/user_delete_key', methods=['POST'])
def user_delete_key():
    try:
        if 'username' not in session or session.get('role') != 'user': return redirect('/login')
        username = session['username']
        k = request.form.get('key_to_delete', '').strip()
        
        db = load_db()
        with db_lock:
            user_data = db["users"].get(username)
            if user_data:
                user_data["purchased_keys"] = [pk for pk in user_data.get("purchased_keys", []) if pk["key"] != k]
                if k in db.get("keys", {}):
                    del db["keys"][k]
                save_db(db)
        
        if session.get('active_key') == k:
            session.pop('active_key', None)
            
        return swal_redirect("Thành Công!", "Đã xóa Key vĩnh viễn khỏi hệ thống.", "success", "/dashboard")
    except Exception as e: return swal_back("Lỗi", str(e), "error")

@app.route('/key_login', methods=['GET', 'POST'])
def key_login():
    try:
        if 'username' not in session or session.get('role') != 'user': return redirect('/login')
        if request.method == 'POST':
            k = request.form.get('key_input', '').strip()
            db = load_db()
            if k in db.get("keys", {}):
                session['active_key'] = k
                return swal_redirect("Chấp nhận mã Key!", "Đang đưa bạn vào Khoang Lái...", "success", "/key_dashboard")
            return swal_back("Thất bại", "Mã Key không tồn tại trong hệ thống!", "error")

        return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Kích Hoạt Key</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>{CSS_GLASS}</style></head><body><div class="glass-panel"><h2 class="text-neon mb-4">🔑 KHỞI ĐỘNG KEY</h2><form method="POST"><input type="text" name="key_input" class="form-control text-center fs-5" placeholder="Dán mã Key của bạn vào đây..." required><button type="submit" class="btn-neon mt-2">ĐĂNG NHẬP KEY</button></form><div class="mt-4"><a href="/dashboard" class="link-neon"><i class="fas fa-arrow-left"></i> Trở về Quầy Shop</a></div></div></body></html>'''
    except Exception as e: return f"LỖI HỆ THỐNG: {str(e)}", 200

@app.route('/logout_key')
def logout_key():
    session.pop('active_key', None)
    return redirect('/key_login')

@app.route('/key_dashboard')
def key_dashboard():
    try:
        if 'username' not in session: return redirect('/login')
        
        active_key = session.get('active_key')
        if not active_key: return redirect('/key_login')

        db = load_db()
        kd = db.get("keys", {}).get(active_key)
        if not kd: 
            session.pop('active_key', None)
            return swal_redirect("Lỗi", "Key đã bị xóa khỏi hệ thống!", "error", "/key_login")

        now = int(time.time() * 1000)
        if kd.get("status") == "banned":
            session.pop('active_key', None)
            return swal_redirect("BỊ KHÓA TỬ HÌNH", "Key của bạn đã bị BAN vĩnh viễn do vi phạm!", "error", "/key_login")
        if kd.get("temp_ban_until", 0) > now:
            rem = (kd["temp_ban_until"] - now) // 60000
            session.pop('active_key', None)
            return swal_redirect("PHẠT TẠM THỜI", f"Key bị khóa tạm thời do Share Máy. Thử lại sau {rem} phút.", "warning", "/key_login")
        if kd.get("exp") != "pending" and kd.get("exp") != "permanent" and kd.get("exp") < now:
            session.pop('active_key', None)
            return swal_redirect("HẾT HẠN", "Key của bạn đã hết thời gian sử dụng. Vui lòng mua mới!", "info", "/key_login")

        is_vip = kd.get("vip", False)
        card_class = "vip-glow" if is_vip else "nor-glow"
        vip_text = "💎 VIP PRO" if is_vip else "THƯỜNG"
        
        exp_ms = kd.get("exp")
        exp_val = "permanent" if exp_ms == "permanent" else ("pending" if exp_ms == "pending" else exp_ms)

        return f'''
        <!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Phòng Điều Khiển</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>{CSS_GLASS} .card-key{{background:rgba(17,17,26,0.9) !important;border-radius:16px !important; backdrop-filter: blur(10px);}}</style></head>
        <body class="p-3">
        <div class="container" style="max-width:800px;">
            <div class="d-flex justify-content-between align-items-center mb-4 border-bottom border-secondary pb-2">
                <h3 style="color:#00ffcc;margin:0;font-weight:900;">⚡ KHOANG LÁI HACK</h3>
                <div>
                    <a href="/dashboard" class="btn btn-outline-info btn-sm fw-bold me-2 rounded-pill">Shop/Quản Lý</a>
                    <a href="/logout_key" class="btn btn-danger btn-sm fw-bold rounded-pill">Đăng Xuất Key</a>
                </div>
            </div>
            
            <div class="card-key {card_class} p-4 text-center mb-4 shadow">
                <div class="badge mb-3" style="background:{'#bd00ff' if is_vip else '#0099ff'}; font-size:16px; padding: 6px 12px !important;">{vip_text}</div>
                <h2 class="text-white mb-2" style="font-family:monospace;letter-spacing:2px;cursor:pointer;" onclick="copyT('{active_key}')">{active_key} <i class="fas fa-copy text-muted fs-5"></i></h2>
                
                <div class="my-3 py-3" style="background:rgba(0,0,0,0.5); border-radius:10px; border:1px dashed rgba(255,255,255,0.2);">
                    <p class="text-secondary mb-1" style="font-size:12px;">KEY OLM MODE CỦA HỆ THỐNG</p>
                    <b class="text-warning" style="font-family:monospace; font-size:18px; letter-spacing:1px;">OLM_VIP_786B-XQCH-BYEF-SYUS</b>
                </div>

                <div id="countdown-box" class="mt-3">
                    <p class="text-muted mb-0">Thời gian còn lại:</p>
                    <h3 id="timer" class="text-danger fw-bold" style="font-family:monospace; text-shadow: 0 0 10px rgba(255,0,0,0.3);">ĐANG TÍNH...</h3>
                </div>
                
                <div class="d-flex justify-content-center gap-5 mt-4 pt-3 border-top border-secondary">
                    <div><small class="text-secondary">Thiết Bị Của Bạn</small><br><b class="fs-4 text-info">{len(kd.get('devices', []))}/{kd.get('maxDevices', 1)}</b></div>
                </div>
            </div>
            
            <div class="row g-3">
                <div class="col-12 mt-2 text-center">
                    <p class="text-warning fw-bold mb-3">🚀 Ấn nút bên dưới hệ thống sẽ tự động đồng bộ Key và mở khóa OLM.VN</p>
                    <a href="https://olm.vn/?lvt_key={active_key}" target="_blank" class="btn w-100 p-3 fw-bold fs-5 text-dark" style="background:linear-gradient(45deg,#00ffcc,#0099ff);box-shadow:0 10px 25px rgba(0,255,204,0.4);border-radius:12px;" onclick="checkInstallFirst(event, this.href)">
                        MỞ KHÓA VÀ SỬ DỤNG HACK NGAY
                    </a>
                    <div class="mt-4">
                        <small class="text-muted">Chưa cài đặt Userscript? <a href="/api/script/olm_vip.user.js" target="_blank" style="color:#00ffcc; text-decoration:none; border-bottom: 1px dashed #00ffcc;">Bấm vào đây để cài đặt Siêu Loader (Cài 1 lần)</a></small>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            function copyT(t){{ navigator.clipboard.writeText(t); Swal.fire({{toast:true,position:'top-end',icon:'success',title:'Đã sao chép Key!',showConfirmButton:false,timer:1500,background:'#111',color:'#fff'}}); }}
            
            function checkInstallFirst(e, link) {{
                Swal.fire({{
                    toast: true, position: 'top', icon: 'info',
                    title: 'Đang mở khóa OLM...', text: 'Hãy chắc chắn bạn đã cài đặt tiện ích Script trước đó!',
                    showConfirmButton: false, timer: 2000, background: '#111', color: '#fff'
                }});
            }}

            let expVal = "{exp_val}";
            let timerEl = document.getElementById('timer');
            if(expVal === "permanent") {{ timerEl.innerHTML = "<span class='text-success'>VĨNH VIỄN</span>"; timerEl.classList.replace('text-danger', 'text-success'); }}
            else if(expVal === "pending") {{ timerEl.innerHTML = "<span class='text-info'>CHƯA KÍCH HOẠT (Sẽ trừ giờ khi dùng)</span>"; timerEl.classList.replace('text-danger', 'text-info'); }}
            else {{
                let expTime = parseInt(expVal);
                setInterval(() => {{
                    let now = new Date().getTime();
                    let distance = expTime - now;
                    if (distance < 0) {{ timerEl.innerHTML = "ĐÃ HẾT HẠN"; window.location.reload(); return; }}
                    let days = Math.floor(distance / (1000 * 60 * 60 * 24));
                    let hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                    let minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                    let seconds = Math.floor((distance % (1000 * 60)) / 1000);
                    timerEl.innerHTML = `${{days}}n ${{hours}}g ${{minutes}}p ${{seconds}}s`;
                }}, 1000);
            }}
        </script></body></html>
        '''
    except Exception as e: return f"LỖI HỆ THỐNG: {str(e)}", 200

# ========================================================
# GIAO DIỆN WEB ADMIN QUẢN LÝ
# ========================================================
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    try:
        if request.method == 'POST':
            db = load_db()
            username = request.form.get('username', '').strip().lower()
            pwd = request.form.get('password', '').strip()
            
            u_data = db.get("users", {}).get(username)
            if u_data and u_data.get("role") == "admin" and u_data.get("password_hash") == hash_pwd(pwd):
                session['username'] = username
                session['role'] = 'admin'
                session['admin_auth'] = True 
                session['admin_ip'] = get_real_ip()
                with db_lock: log_admin_action(db, f"Đăng nhập Admin thành công: {get_real_ip()}")
                save_db(db)
                return redirect('/admin')
            return swal_back("Từ Chối Truy Cập", f"Thông tin sai!", "error")
        
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
            admin_logs = list(db.get("admin_logs", []))

        now_ms = int(time.time() * 1000)

        users_html = ""
        for uname, udata in users_items:
            if udata.get("role") == "admin": continue
            bal = udata.get("balance", 0)
            
            u_keys = "<br>".join([f"🔑 {escape(pk.get('key')[:8])}..." for pk in udata.get("purchased_keys", [])]) or "<span class='text-muted'>Chưa có</span>"
            u_ips = "<br>".join([escape(ip) for ip in udata.get("ips", [])]) or "<span class='text-muted'>Trống</span>"
            created = time.strftime("%d/%m/%y", time.localtime(udata.get("created_at", 0)/1000))
            
            users_html += f'''
            <tr class="text-nowrap">
                <td><strong class="text-warning">{escape(uname)}</strong><br><small class="text-muted">{created}</small></td>
                <td><span class="badge bg-success">{bal:,}đ</span></td>
                <td style="font-size:11px; text-align:left;">{u_keys}</td>
                <td style="font-size:11px; text-align:left; color:#ffcc00;">{u_ips}</td>
                <td>
                    <form action="/admin/add_balance" method="POST" class="d-flex gap-1 justify-content-center m-0">
                        <input type="hidden" name="username" value="{escape(uname)}">
                        <input type="number" name="amount" class="form-control form-control-sm bg-dark text-light border-secondary px-1 text-center m-0" style="width:70px;font-size:12px;height:28px;" placeholder="± Tiền" required>
                        <button type="submit" class="btn btn-sm btn-primary fw-bold" style="font-size:11px;height:28px; border-radius:6px;">CỘNG</button>
                    </form>
                </td>
            </tr>
            '''

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
            bnd_html = f"<br><small class='text-danger'>Ghim: {bound_olm}</small>" if bound_olm else ""

            keys_html += f'''
            <tr class="key-row text-nowrap">
                <td>
                    <strong class="text-info" style="font-size:12px; cursor:pointer;" onclick="copyKey('{safe_k}')" title="Bấm để copy">{safe_k[:8]}... <i class="fas fa-copy text-muted"></i></strong><br>
                    {vip_badge} {status_badge}<br>
                    <small class="text-warning">Chủ: {escape(data.get('owner', 'Admin'))}</small>{bnd_html}
                </td>
                <td style="font-size:11px;">{exp_text}</td>
                <td><span class="badge bg-info text-dark">{len(data.get('devices', []))}/{data.get('maxDevices', 1)}</span></td>
                <td>
                    <div class="d-flex flex-wrap gap-1 justify-content-center">
                        <button class="btn btn-info btn-sm fw-bold text-dark" style="font-size:10px; border-radius:6px;" onclick="openAddTimeModal('{safe_k}')">⏳ Giờ</button>
                        <button class="btn btn-warning btn-sm" style="font-size:10px; border-radius:6px;" onclick="openBindModal('{safe_k}', '{bound_olm}')">Ghim</button>
                        <a href="/admin/action/reset-dev/{safe_k}" class="btn btn-primary btn-sm" style="font-size:10px; border-radius:6px;">🔄 Máy</a>
                        <a href="/admin/action/unban_temp/{safe_k}" class="btn btn-success btn-sm" style="font-size:10px; border-radius:6px;">Gỡ Phạt</a>
                        <a href="/admin/action/{"unban" if is_banned else "ban"}/{safe_k}" class="btn btn-{"light" if is_banned else "danger"} btn-sm" style="font-size:10px; border-radius:6px;">{"Cứu" if is_banned else "Trảm"}</a>
                        <a href="/admin/action/delete/{safe_k}" class="btn btn-dark btn-sm" onclick="return confirm('Xóa vĩnh viễn Key này?')" style="font-size:10px; border-radius:6px;">🗑️</a>
                    </div>
                </td>
            </tr>'''

        blacklist_rows = "".join([f'<li class="list-group-item bg-transparent text-light d-flex justify-content-between align-items-center border-secondary border-bottom px-1" style="font-size:12px;">{escape(ip)} <a href="/admin/unban_ip/{escape(ip)}" class="btn btn-sm btn-danger p-0 px-2 rounded-pill">Gỡ</a></li>' for ip in banned_ips])
        if not blacklist_rows: blacklist_rows = '<li class="list-group-item bg-transparent text-muted text-center border-0" style="font-size:12px;">Sạch sẽ</li>'
        
        safe_vm_script = escape(db.get("settings", {}).get("violentmonkey_script", DEFAULT_OLM_SCRIPT))

        return f'''
        <!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ADMIN DASHBOARD</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>{CSS_GLASS} h5{{font-weight:900;}} .table-container{{max-height:450px;overflow-y:auto;}}</style>
        </head><body class="p-2 p-md-4">
        <div class="container-fluid">
            <div class="d-flex justify-content-between align-items-center mb-4 border-bottom border-secondary pb-3">
                <h3 class="m-0 text-neon fw-bold"><i class="fas fa-shield-alt"></i> LVT SECURE ADMIN</h3>
                <div><a href="/logout" class="btn btn-outline-danger btn-sm fw-bold rounded-pill px-3">Thoát</a></div>
            </div>
            
            <div class="row g-4">
                <div class="col-lg-7">
                    <div class="card p-4 h-100" style="border-color:rgba(51,102,255,0.4);">
                        <h5 style="color:#3366ff; margin-bottom:20px;"><i class="fas fa-users"></i> DANH SÁCH USER</h5>
                        <div class="table-container table-responsive">
                            <table class="table table-dark table-hover table-sm align-middle mb-0 text-center text-nowrap">
                                <thead class="table-active"><tr><th>Tài Khoản</th><th>Số Dư</th><th>Keys Sỡ Hữu</th><th>IP Đăng Nhập</th><th>Cộng/Trừ Tiền</th></tr></thead>
                                <tbody>{users_html}</tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div class="col-lg-5">
                    <div class="row g-4 h-100">
                        <div class="col-md-12">
                            <div class="card p-4 h-100" style="border-color:rgba(189,0,255,0.4);">
                                <h5 style="color:#bd00ff; margin-bottom:15px;"><i class="fas fa-key"></i> TẠO KEY MỚI</h5>
                                <form action="/admin/create" method="POST" class="row g-3">
                                    <div class="col-6"><input type="text" name="prefix" class="form-control form-control-sm m-0" placeholder="Mã (VD: TEST)"></div>
                                    <div class="col-6"><input type="number" name="quantity" class="form-control form-control-sm m-0" value="1" placeholder="Số Lượng"></div>
                                    <div class="col-6"><input type="number" name="duration" class="form-control form-control-sm m-0" placeholder="Độ dài" required></div>
                                    <div class="col-6"><select name="type" class="form-select form-select-sm m-0"><option value="hour">Giờ</option><option value="day" selected>Ngày</option><option value="month">Tháng</option><option value="permanent">V.Viễn</option></select></div>
                                    
                                    <div class="col-12 d-flex justify-content-center align-items-center">
                                        <div class="form-check form-switch fs-5 mt-1">
                                          <input class="form-check-input" type="checkbox" role="switch" name="is_vip" id="vipSwitch">
                                          <label class="form-check-label text-warning fw-bold ms-2" for="vipSwitch" style="font-size:14px;">🔑 Gắn mác Key VIP PRO</label>
                                        </div>
                                    </div>
                                    
                                    <div class="col-12"><button type="submit" class="btn btn-sm w-100 fw-bold py-2" style="background:linear-gradient(45deg, #bd00ff, #3366ff);color:white; border-radius:10px;">🚀 TẠO NGAY</button></div>
                                </form>
                            </div>
                        </div>
                        <div class="col-md-12">
                            <div class="card p-4 h-100" style="border-color:rgba(255,153,0,0.4);">
                                <h5 style="color:#ff9900; margin-bottom:15px;"><i class="fas fa-code"></i> SET SCRIPT MẶC ĐỊNH</h5>
                                <button class="btn btn-sm btn-outline-info w-100 fw-bold py-2 rounded-pill" data-bs-toggle="modal" data-bs-target="#vmScriptModal">Dán Code HACK / Cập Nhật Core</button>
                            </div>
                        </div>
                        <div class="col-md-12">
                            <div class="card p-4 h-100" style="border-color:rgba(255,51,102,0.4);">
                                <h5 class="text-danger margin-bottom:15px;"><i class="fas fa-shield-virus"></i> FIREWALL BANS</h5>
                                <form action="/admin/ban_ip" method="POST" class="d-flex gap-2 mb-3">
                                    <input type="text" name="ip" class="form-control form-control-sm m-0" placeholder="Nhập IP..." required>
                                    <button type="submit" class="btn btn-sm btn-danger fw-bold px-3 rounded-pill">Chặn</button>
                                </form>
                                <ul class="list-group list-group-flush" style="max-height:120px;overflow-y:auto; border: 1px solid rgba(255,255,255,0.05); border-radius:8px; padding:5px;">{blacklist_rows}</ul>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-lg-12">
                    <div class="card p-4 h-100" style="border-color:rgba(0,255,204,0.4);">
                        <div class="d-flex justify-content-between align-items-center mb-4">
                            <h5 class="m-0 text-neon"><i class="fas fa-database"></i> TẤT CẢ MÃ KEY</h5>
                            <input type="text" class="form-control form-control-sm m-0" style="width:250px; background:rgba(0,0,0,0.3);" placeholder="🔍 Tìm Key..." onkeyup="let s=this.value.toLowerCase();document.querySelectorAll('.key-row').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(s)?'':'none');">
                        </div>
                        <div class="table-container border border-secondary table-responsive">
                            <table class="table table-dark table-sm align-middle table-hover text-center mb-0 text-nowrap">
                                <thead class="table-active"><tr><th>🔑 Key / Chủ</th><th>⏳ Hạn Dùng</th><th>💻 Thiết bị</th><th>⚙️ Thao tác</th></tr></thead>
                                <tbody>{keys_html}</tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="modal fade" id="bindModal" tabindex="-1" data-bs-theme="dark">
            <div class="modal-dialog modal-sm modal-dialog-centered">
                <div class="modal-content" style="background:rgba(17,17,26,0.95);border:1px solid #ffcc00; backdrop-filter: blur(15px);">
                    <form action="/admin/bind_olm" method="POST">
                        <div class="modal-body text-center p-4">
                            <input type="hidden" name="key" id="bindKeyInput">
                            <p class="text-white mb-2">Ghim Định Danh OLM cho Key:</p>
                            <p><strong id="bindKeyDisplay" class="text-info" style="word-break: break-all;"></strong></p>
                            <input type="text" name="olm_name" id="bindOlmInput" class="form-control mt-3" placeholder="Tên nick OLM khách (để trống: hủy)">
                        </div>
                        <div class="modal-footer border-secondary p-2"><button type="submit" class="btn btn-warning w-100 fw-bold text-dark rounded-pill">Ghim Chặt Cứng</button></div>
                    </form>
                </div>
            </div>
        </div>
        
        <div class="modal fade" id="addTimeModal" tabindex="-1" data-bs-theme="dark">
            <div class="modal-dialog modal-sm modal-dialog-centered">
                <div class="modal-content" style="background:rgba(17,17,26,0.95);border:1px solid #00ffcc; backdrop-filter: blur(15px);">
                    <form action="/admin/add_time" method="POST">
                        <div class="modal-body text-center p-4">
                            <input type="hidden" name="key" id="addTimeKeyInput">
                            <p class="text-white mb-2">Thêm thời gian cho Key:</p>
                            <p><strong id="addTimeKeyDisplay" class="text-info" style="word-break: break-all;"></strong></p>
                            <input type="number" name="time_val" class="form-control mt-3" placeholder="Số lượng (Ví dụ: 10)" required>
                            <select name="time_unit" class="form-select mt-2" style="background-color:rgba(10,10,18,0.8); color:white;">
                                <option value="hours">Giờ</option>
                                <option value="days" selected>Ngày</option>
                                <option value="months">Tháng</option>
                            </select>
                        </div>
                        <div class="modal-footer border-secondary p-2"><button type="submit" class="btn btn-info w-100 fw-bold text-dark rounded-pill">XÁC NHẬN CỘNG</button></div>
                    </form>
                </div>
            </div>
        </div>

        <div class="modal fade" id="vmScriptModal" tabindex="-1" data-bs-theme="dark">
          <div class="modal-dialog modal-lg modal-dialog-centered">
            <div class="modal-content" style="background:rgba(17,17,26,0.95); border:1px solid #00ffcc; backdrop-filter: blur(15px);">
              <form action="/admin/update_vm_script" method="POST">
                  <div class="modal-header border-secondary">
                      <h5 class="modal-title" style="color:#00ffcc;font-weight:bold;">CẬP NHẬT CODE SCRIPT GỐC MỚI</h5>
                      <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                  </div>
                  <div class="modal-body p-4">
                      <p class="text-warning mb-2" style="font-size:13px;">⚠️ Dán toàn bộ Code mới vào đây. Hệ thống sẽ TỰ ĐỘNG bóc tách Header, băm Body tạo Core ẩn và truyền quyền cho Loader.</p>
                      <textarea name="vm_script_content" class="form-control" rows="15" style="font-family:monospace; font-size:12px;">{safe_vm_script}</textarea>
                  </div>
                  <div class="modal-footer border-secondary p-3"><button type="submit" class="btn btn-info fw-bold w-100 text-dark rounded-pill">LƯU & XUẤT BẢN CODE MỚI</button></div>
              </form>
            </div>
          </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            function copyKey(t){{ navigator.clipboard.writeText(t); Swal.fire({{toast:true,position:'top-end',icon:'success',title:'Đã Copy Key!',showConfirmButton:false,timer:1000,background:'#111',color:'#00ffcc'}}); }}
            
            function openBindModal(key, current_olm) {{
                document.getElementById('bindKeyInput').value = key;
                document.getElementById('bindKeyDisplay').innerText = key;
                document.getElementById('bindOlmInput').value = current_olm;
                new bootstrap.Modal(document.getElementById('bindModal')).show();
            }}
            
            function openAddTimeModal(key) {{
                document.getElementById('addTimeKeyInput').value = key;
                document.getElementById('addTimeKeyDisplay').innerText = key;
                new bootstrap.Modal(document.getElementById('addTimeModal')).show();
            }}
        </script>
        </body></html>
        '''
    except Exception as e: return f"LỖI HỆ THỐNG: {str(e)}", 200

@app.route('/admin/add_balance', methods=['POST'])
def add_balance():
    try:
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
                log_admin_action(db, f"Cộng/Trừ {amt}đ cho tài khoản {username}")
                save_db(db)
        return redirect('/admin')
    except Exception as e: return swal_back("Lỗi", str(e), "error")

@app.route('/admin/create', methods=['POST'])
def create_key():
    try:
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
            log_admin_action(db, f"Tạo {qty} Key Tool mới ({dur} {t}) - Mác VIP: {vip}")
            save_db(db)
        return redirect('/admin')
    except Exception as e: return swal_back("Lỗi", str(e), "error")

@app.route('/admin/add_time', methods=['POST'])
def admin_add_time():
    try:
        if session.get('role') != 'admin': return redirect('/login')
        key = request.form.get('key', '').strip()
        t_val = safe_int(request.form.get('time_val', 0))
        t_unit = request.form.get('time_unit', 'days')
        
        if t_val <= 0: return swal_back("Lỗi", "Số lượng phải lớn hơn 0", "error")
        
        ms_to_add = 0
        if t_unit == 'hours': ms_to_add = t_val * 3600000
        elif t_unit == 'days': ms_to_add = t_val * 86400000
        elif t_unit == 'months': ms_to_add = t_val * 2592000000
        
        db = load_db()
        with db_lock:
            if key in db.get("keys", {}):
                kd = db["keys"][key]
                if kd.get("exp") == "permanent":
                    return swal_back("Lỗi", "Key vĩnh viễn không cần cộng giờ!", "error")
                
                now = int(time.time() * 1000)
                if kd.get("exp") == "pending":
                    kd["durationMs"] = kd.get("durationMs", 0) + ms_to_add
                else:
                    current_exp = kd.get("exp", now)
                    if current_exp < now: current_exp = now
                    kd["exp"] = current_exp + ms_to_add
                
                log_admin_action(db, f"Cộng {t_val} {t_unit} cho Key {key}")
                save_db(db)
        return swal_redirect("Thành Công", f"Đã cộng thêm {t_val} {t_unit} cho Key {key}!", "success", "/admin")
    except Exception as e: return swal_back("Lỗi", str(e), "error")

@app.route('/admin/bind_olm', methods=['POST'])
def admin_bind_olm():
    try:
        if session.get('role') != 'admin': return redirect('/login')
        key = request.form.get('key', '').strip()
        olm = request.form.get('olm_name', '').strip()
        db = load_db()
        with db_lock:
            if key in db.get("keys", {}):
                db["keys"][key]["bound_olm"] = olm
                log_admin_action(db, f"Ghim OLM {olm} cho Key {key}")
                save_db(db)
        return redirect('/admin')
    except Exception as e: return swal_back("Lỗi", str(e), "error")

@app.route('/admin/update_vm_script', methods=['POST'])
def admin_update_vm_script():
    try:
        if session.get('role') != 'admin': return redirect('/login')
        ns = request.form.get('vm_script_content', '')
        db = load_db()
        with db_lock:
            db.setdefault("settings", {})["violentmonkey_script"] = ns
            log_admin_action(db, "Cập nhật Script Gốc Mới Nhất")
            save_db(db)
        return swal_redirect("Tuyệt Vời!", "Hệ thống đã cập nhật và biên dịch thành công Core mới ngầm không cần cài lại!", "success", "/admin")
    except Exception as e: return swal_back("Lỗi", str(e), "error")

@app.route('/admin/ban_ip', methods=['POST'])
def web_ban_ip():
    try:
        if session.get('role') != 'admin': return redirect('/login')
        ip = request.form.get('ip', '').strip()
        if ip:
            db = load_db()
            with db_lock:
                if ip not in db.setdefault("banned_ips", []):
                    db["banned_ips"].append(ip)
                    log_admin_action(db, f"Chặn IP: {ip}")
                    save_db(db)
        return redirect('/admin')
    except Exception as e: return swal_back("Lỗi", str(e), "error")

@app.route('/admin/unban_ip/<path:ip>')
def unban_ip(ip):
    try:
        if session.get('role') != 'admin': return redirect('/login')
        db = load_db()
        with db_lock:
            if ip in db.setdefault("banned_ips", []):
                db["banned_ips"].remove(ip)
                log_admin_action(db, f"Gỡ Firewall cho IP: {ip}")
                save_db(db)
        return redirect('/admin')
    except Exception as e: return swal_back("Lỗi", str(e), "error")

@app.route('/admin/action/<action>/<key>')
def key_actions(action, key):
    try:
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
                    for u in db["users"]:
                        db["users"][u]["purchased_keys"] = [pk for pk in db["users"][u].get("purchased_keys", []) if pk["key"] != key]
                elif action == 'reset-dev':
                    kd['devices'] = []
                    kd['known_ips'] = {}
                log_admin_action(db, f"Lệnh [{action}] trên Key {key}")
                save_db(db)
        return redirect('/admin')
    except Exception as e: return swal_back("Lỗi", str(e), "error")

# ========================================================
# HÀM RENDER TEMPLATE HTML CHO FLASK
# ========================================================
from flask import render_template_string
def render_template_string_safe(content):
    resp = make_response(content)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
