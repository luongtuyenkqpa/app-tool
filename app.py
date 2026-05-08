import os, json, time, random, hashlib, threading, requests, shutil, base64, secrets, hmac, string
from urllib.parse import urlparse
from html import escape
from flask import Flask, request, jsonify, redirect, make_response, session

# [VÁ LỖI LỆCH MÚI GIỜ CLOUD]
try:
    os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
    time.tzset()
except: pass

app = Flask(__name__)

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

# ĐỊA CHỈ WEB CỦA BẠN
WEB_URL = "https://app-tool-trlp.onrender.com"

# ========================================================
# SCRIPT VIOLENTMONKEY (V9.0) ẨN TRONG SERVER
# ========================================================
OLM_SCRIPT = """// ==UserScript==
// @name         OLM GOD MODE VIP - DEV.TIỆP (CLOUD AUTH + WEB SYNC + NEW UI)
// @namespace    http://tampermonkey.net/
// @version      9.0
// @description  Hệ thống bảo vệ đa tầng. Giao diện mới yêu cầu đăng nhập từ Web, ẩn hoàn toàn ô nhập Key thủ công.
// @author       DEV.TIỆP
// @match        *://olm.vn/*
// @match        *://*.olm.vn/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @run-at       document-start
// ==/UserScript==

(function() {
    'use strict';

    // LƯU TRỮ TÊN TÀI KHOẢN THẬT (Để API Vòng ngoài hoạt động bình thường)
    let REAL_USERNAME = "N/A";
    try { 
        let cookies = document.cookie.split(';'); 
        for (let i = 0; i < cookies.length; i++) { 
            let c = cookies[i].trim(); 
            if (c.startsWith("username=")) { 
                REAL_USERNAME = decodeURIComponent(c.substring(9)).replace(/^"|"$/g, '').trim(); 
            } 
        } 
    } catch(e) {}

    const SERVER_URL = "https://app-tool-trlp.onrender.com"; 
    let savedKey = GM_getValue('lvt_olm_vip_key', '');

    function generateRobustHWID() {
        let canvas = document.createElement('canvas');
        let ctx = canvas.getContext('2d');
        ctx.textBaseline = "top"; ctx.font = "14px 'Arial'"; ctx.fillStyle = "#f60"; ctx.fillRect(125,1,62,20);
        ctx.fillStyle = "#069"; ctx.fillText("OLM_LVT_VIP", 2, 15); ctx.fillStyle = "rgba(102, 204, 0, 0.7)"; ctx.fillText("OLM_LVT_VIP", 4, 17);
        let b64 = canvas.toDataURL().replace("data:image/png;base64,","");
        
        let nav = navigator.userAgent + navigator.hardwareConcurrency + navigator.language + screen.width + screen.height;
        let combined = b64 + nav;
        let hash = 0;
        for(let i=0; i<combined.length; i++) {
            let char = combined.charCodeAt(i);
            hash = ((hash<<5)-hash)+char;
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
            let data = encoder.encode(msg);
            let hashBuffer = await crypto.subtle.digest('SHA-256', data);
            let hashArray = Array.from(new Uint8Array(hashBuffer));
            sig = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        }
        
        bodyObj.timestamp = ts;
        bodyObj.signature = sig;
        bodyObj.olm_name = REAL_USERNAME; 
        
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: 'POST',
                url: SERVER_URL + path,
                headers: { 'Content-Type': 'application/json' },
                data: JSON.stringify(bodyObj),
                onload: (response) => {
                    try { resolve(JSON.parse(response.responseText)); } 
                    catch(e) { reject("Lỗi phân tích dữ liệu từ Server."); }
                },
                onerror: (e) => reject("Lỗi kết nối mạng hoặc Server đang ngủ.")
            });
        });
    }

    function showWelcomePopup(username) {
        if(document.getElementById('tiep-welcome-overlay')) return;
        let overlay = document.createElement('div');
        overlay.id = 'tiep-welcome-overlay';
        overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:2147483647;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(8px);";
        overlay.innerHTML = `
            <div style="background:#0a0a12; border:2px solid #00ffcc; padding:40px; border-radius:15px; text-align:center; box-shadow:0 0 40px rgba(0,255,204,0.4); animation: zoomInTiep 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);">
                <style>@keyframes zoomInTiep { from {transform:scale(0.5); opacity:0;} to {transform:scale(1); opacity:1;} }</style>
                <div style="font-size:50px; margin-bottom:10px;">🎉</div>
                <h1 style="color:#00ffcc; margin:0 0 15px 0; font-family:'Orbitron', sans-serif; text-shadow:0 0 15px #00ffcc; letter-spacing:2px;">CHÚC MỪNG</h1>
                <p style="color:#ccc; font-size:16px; font-family:sans-serif; line-height:1.6;">Tài khoản OLM đã định danh:<br>
                <strong style="color:#ff3366; font-size:24px; display:block; margin-top:10px; text-shadow:0 0 10px rgba(255,51,102,0.5);">${username}</strong></p>
                <p style="color:#888; font-size:13px; margin-top:15px;">Đăng nhập hệ thống VIP thành công!</p>
                <button id="tiep-close-welcome" style="margin-top:25px; padding:12px 40px; background:linear-gradient(45deg, #00ffcc, #0099ff); color:#000; border:none; border-radius:8px; font-weight:900; cursor:pointer; font-size:16px; font-family:'Orbitron', sans-serif; transition:0.3s; text-transform:uppercase;">BẮT ĐẦU SỬ DỤNG</button>
            </div>
        `;
        document.body.appendChild(overlay);
        document.getElementById('tiep-close-welcome').onclick = () => {
            overlay.style.opacity = '0';
            overlay.style.transition = 'opacity 0.4s ease';
            setTimeout(() => overlay.remove(), 400);
        };
    }

    function showKeyPrompt(errorMsg = "") {
        if(document.getElementById('tiep-auth-overlay')) return;
        
        const authStyle = document.createElement('style');
        authStyle.textContent = `
            @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap');
            #tiep-auth-overlay { position: fixed; inset: 0; z-index: 2147483647; background: rgba(5, 5, 10, 0.98); backdrop-filter: blur(15px); display: flex; align-items: center; justify-content: center; font-family: 'Share Tech Mono', monospace; }
            .auth-box { background: #0a0a12; border: 2px solid #00ffcc; padding: 40px; border-radius: 15px; box-shadow: 0 0 40px rgba(0,255,204,0.3); text-align: center; width: 400px; max-width: 90%; position: relative; overflow: hidden; }
            .auth-box::before { content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%; background: conic-gradient(transparent, rgba(0,255,204,0.3), transparent 30%); animation: rotate 4s linear infinite; z-index: 0; opacity: 0.5; }
            .auth-box::after { content: ''; position: absolute; inset: 2px; background: #0a0a12; border-radius: 13px; z-index: 1; }
            @keyframes rotate { 100% { transform: rotate(1turn); } }
            .auth-content { position: relative; z-index: 2; }
            .auth-title { color: #00ffcc; font-size: 28px; font-weight: 900; margin-bottom: 5px; font-family: 'Orbitron', sans-serif; text-shadow: 0 0 15px rgba(0,255,204,0.6); letter-spacing: 2px; }
            .auth-sub { color: #888; font-size: 12px; margin-bottom: 25px; letter-spacing: 1px; text-transform: uppercase; }
            .auth-msg { color: #fff; font-size: 16px; margin: 25px 0; padding: 15px; background: rgba(0,255,204,0.1); border: 1px solid #00ffcc; border-radius: 8px; font-weight: bold; line-height: 1.5; text-shadow: 0 0 5px rgba(0,255,204,0.3); }
            .auth-error { color: #ff3366; font-size: 14px; margin-top: 15px; display: block; font-weight: bold; text-shadow: 0 0 5px rgba(255,51,102,0.4); }
            .auth-footer { margin-top: 30px; font-size: 14px; }
            .auth-footer a { color: #00ffcc; text-decoration: none; font-weight: bold; border-bottom: 1px dashed #00ffcc; padding-bottom: 2px; transition: 0.3s; letter-spacing: 1px;}
            .auth-footer a:hover { color: #fff; border-color: #fff; text-shadow: 0 0 10px #00ffcc; }
        `;
        document.head.appendChild(authStyle);

        const authDiv = document.createElement('div');
        authDiv.id = 'tiep-auth-overlay';
        authDiv.innerHTML = `
            <div class="auth-box">
                <div class="auth-content">
                    <div class="auth-title">OLM VIP PRO</div>
                    <div class="auth-sub">HỆ THỐNG BẢO MẬT & ĐỒNG BỘ ĐÁM MÂY</div>
                    <div class="auth-msg">⚠️ VUI LÒNG ĐĂNG NHẬP KEY<br>Ở WEB ĐỂ SỬ DỤNG</div>
                    <div id="tiep-auth-error" class="auth-error">${errorMsg}</div>
                    <div class="auth-footer"><a href="${SERVER_URL}" target="_blank">🌍 ĐI TỚI WEBSITE MUA / NHẬP KEY</a></div>
                </div>
            </div>
        `;

        if (document.body) {
            document.body.appendChild(authDiv);
        } else {
            window.addEventListener('DOMContentLoaded', () => document.body.appendChild(authDiv));
        }
    }
    
    function kickUserToWeb(msg) {
        let kickDiv = document.createElement('div');
        kickDiv.style.cssText = "position:fixed;inset:0;background:rgba(20,0,0,0.98);z-index:2147483647;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff;font-family:sans-serif;text-align:center;padding:20px;";
        kickDiv.innerHTML = `<div style="font-size:60px;margin-bottom:10px;text-shadow:0 0 20px red;">⚠️</div><h1 style="color:#ff3366;margin:0 0 15px 0;font-weight:900;">TRUY CẬP BỊ TỪ CHỐI</h1><p style="color:#ccc;font-size:18px;max-width:600px;line-height:1.5;">${msg}</p><p style="margin-top:30px;font-size:14px;color:#888;">Đang làm sạch bộ nhớ và cấm hệ thống...</p>`;
        
        if(document.body) {
            let old = document.getElementById('tiep-auth-overlay');
            if(old) old.remove();
            let oldPopup = document.getElementById('tiep-welcome-overlay');
            if(oldPopup) oldPopup.remove();
            document.body.appendChild(kickDiv);
        }
        
        GM_setValue('lvt_olm_vip_key', ''); 
        setTimeout(() => { window.location.href = SERVER_URL; }, 5000); 
    }

    function initHackSystem(activeKey) {
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
                        if (v && typeof v === 'string' && v.includes('"username"')) {
                            return v.replace(/"username":"[^"]+"/, '"username":"' + TARGET + '"');
                        }
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
                    console.log("[OLM VIP] Đã áp dụng FUSION MASK thành công. Lõi Hack đã bị Đánh lừa!");
                } catch(e) {}
            })();\\n\\n`;

            scriptTag.textContent = fusedMask + scriptContent;
            (document.head || document.documentElement).appendChild(scriptTag);
            scriptTag.remove();
        }

        GM_xmlhttpRequest({
            method: 'GET',
            url: CORE_URL + '?t=' + new Date().getTime(),
            onload: function(response) {
                if (response.status === 200 && response.responseText !== cachedCore) {
                    GM_setValue('tiep_core_cache', response.responseText);
                    if (!cachedCore) {
                        if (isTargetPage) injectScript(response.responseText);
                        else {
                            sessionStorage.setItem('tiep_loader_seen', '1');
                            showMatrixLoader(response.responseText);
                        }
                    }
                }
            }
        });

        if (cachedCore) {
            if (isTargetPage || hasSeenLoader) injectScript(cachedCore);
            else {
                sessionStorage.setItem('tiep_loader_seen', '1');
                showMatrixLoader(cachedCore);
            }
        }

        function showMatrixLoader(scriptContent) {
            const style = document.createElement('style');
            style.textContent = `@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&display=swap'); #tiep-matrix-loader { position: fixed; inset: 0; z-index: 2147483647; background: #020c06; font-family: 'Share Tech Mono', monospace; color: #00ff88; display: flex; align-items: center; justify-content: center; overflow: hidden; }`;
            document.head.appendChild(style);
            
            setTimeout(() => {
                let loader = document.getElementById('tiep-matrix-loader');
                if (loader) loader.remove();
                injectScript(scriptContent);
            }, 3000);
        }

        setInterval(() => { secureApiCall('/api/script_ping', { key: activeKey }).catch(e => {}); }, 30000);
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
                if (res.assigned_user && REAL_USERNAME !== "N/A" && REAL_USERNAME !== res.assigned_user) {
                    secureApiCall('/api/ban_key', { key: savedKey, reason: "Sử dụng sai tài khoản OLM" });
                    kickUserToWeb(`GIAN LẬN: Key này chỉ dành cho tài khoản [${res.assigned_user}]. Bạn đang dùng cho [${REAL_USERNAME}]. Key đã bị Khóa Vĩnh Viễn!`);
                    return;
                }

                if (!sessionStorage.getItem('tiep_welcomed')) {
                    showWelcomePopup(assignedUser);
                    sessionStorage.setItem('tiep_welcomed', '1');
                }

                if (res.loader_enabled) initHackSystem(savedKey); 
                else showKeyPrompt("⚠️ ADMIN ĐÃ TẮT SPOOFER CHO KEY NÀY!");
            } else {
                showKeyPrompt(res.message);
                GM_setValue('lvt_olm_vip_key', '');
            }
        }).catch(e => {
            console.log("[LVT VIP] Lỗi check ngầm:", e);
            showKeyPrompt("LỖI KẾT NỐI MÁY CHỦ BẢO MẬT");
        });
    } else {
        if (document.readyState === "loading") window.addEventListener('DOMContentLoaded', () => showKeyPrompt());
        else showKeyPrompt();
    }
})();"""

# ========================================================
# CẤU HÌNH SHOP KEY
# ========================================================
SHOP_PACKAGES = {
    "1H": {"name": "1 Giờ", "price": 10000, "dur_ms": 3600000, "vip": False},
    "7D": {"name": "7 Ngày", "price": 30000, "dur_ms": 604800000, "vip": True},
    "30D": {"name": "1 Tháng", "price": 100000, "dur_ms": 2592000000, "vip": True},
    "1Y": {"name": "1 Năm Học", "price": 150000, "dur_ms": 31536000000, "vip": True}
}

# HÀM BẢO VỆ CHỐNG SẬP WEB 500
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

# ========================================================
# DATABASE CORE & KHỞI TẠO ADMIN
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
            if not data: data = {"users": {}, "keys": {}, "banned_ips": [], "admin_logs": [], "security_alerts": []}
            try:
                data.setdefault("users", {})
                data.setdefault("keys", {})
                data.setdefault("banned_ips", [])
                data.setdefault("admin_logs", [])
                data.setdefault("security_alerts", []) 
                
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
        try: db_str = json.dumps(db, indent=2, ensure_ascii=False)
        except: return 
        temp_file = DB_FILE + f'.{int(time.time() * 1000)}.tmp'
        try:
            with open(temp_file, 'w', encoding='utf-8') as f: f.write(db_str)
            os.replace(temp_file, DB_FILE)
            shutil.copy2(DB_FILE, DB_BACKUP)
            _last_db_mtime = os.path.getmtime(DB_FILE)
        except Exception: 
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

def garbage_collector():
    global used_signatures
    while True:
        time.sleep(3600) 
        now_ms = int(time.time() * 1000)
        try:
            with api_rate_lock:
                to_del_sig = [s for s, t in used_signatures.items() if now_ms - t > 20000]
                for s in to_del_sig: del used_signatures[s]
            
            db = load_db()
            changed = False
            with db_lock:
                for k in list(db.get("keys", {}).keys()):
                    exp = db["keys"][k].get("exp")
                    if exp != "permanent" and exp != "pending":
                        if isinstance(exp, int) and (now_ms - exp) > 604800000:
                            del db["keys"][k]
                            changed = True
                if len(db.get("security_alerts", [])) > 100:
                    db["security_alerts"] = db["security_alerts"][:50]
                    changed = True
            if changed: save_db(db)
        except: pass

threading.Thread(target=garbage_collector, daemon=True).start()

# ========================================================
# HỆ THỐNG BẢO VỆ LAYER 7 & FIREWALL & IPS
# ========================================================
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
        if any(bot in ua for bot in blocked_bots): return "Firewall Blocked Suspicious Bot/Scanner.", 403
            
        if request.path.startswith("/admin") and request.path not in ["/admin_login", "/login", "/register", "/logout"]:
            if session.get('role') != 'admin':
                return redirect('/admin_login')
    except: pass

@app.errorhandler(404)
def not_found_trap(e):
    try:
        ip = get_real_ip()
        suspicious_paths = ['.env', 'wp-admin', 'wp-login.php', 'config.php', 'backup.zip', '.git', 'phpmyadmin']
        if any(s in request.path for s in suspicious_paths):
            report_bad_signature(ip)
    except: pass
    return "Not Found", 404

def report_bad_signature(ip):
    global bad_sig_cache
    if len(bad_sig_cache) > 5000: bad_sig_cache.clear()
    bad_sig_cache[ip] = bad_sig_cache.get(ip, 0) + 1
    if bad_sig_cache[ip] >= 3:
        db = load_db()
        with db_lock:
            if ip not in db.setdefault("banned_ips", []):
                db["banned_ips"].append(ip)
                db.setdefault("security_alerts", []).insert(0, {"time": int(time.time()*1000), "id": ip, "reason": "Dò mật khẩu / Quét thư mục ẩn"})
                save_db(db)

# ========================================================
# API SPOOFER & CẤP PHÉP BƠM CODE
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
    with db_lock:
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
                db.setdefault("security_alerts", []).insert(0, {"time": now, "id": ip, "user": req_olm_name, "reason": f"Sử dụng Key ({key}) sai tài khoản chỉ định ({bound_olm})"})
                save_db(db)
                return False, f"GIAN LẬN: Key này chỉ dành cho tài khoản [{bound_olm}]. Bạn dùng cho [{req_olm_name}]. Key đã bị Khóa Vĩnh Viễn!"

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

        # TRẢ VỀ THÊM TÊN TÀI KHOẢN ĐÃ GHIM ĐỂ SCRIPT CHẶN
        return jsonify({
            "status": "success", 
            "loader_enabled": db["keys"][key].get("loader_enabled", True),
            "assigned_user": db["keys"][key].get("bound_olm", "")
        })
    except Exception as e: return jsonify({"status": "error", "message": "Lỗi API Check"}), 500

@app.route('/api/ban_key', methods=['POST', 'OPTIONS'])
def api_ban_key():
    try:
        if request.method == 'OPTIONS': return make_response("ok", 200)
        data = request.json or {}
        key = data.get('key', '')
        reason = data.get('reason', 'System Auto Ban')
        db = load_db()
        with db_lock:
            if key in db.get("keys", {}):
                db["keys"][key]["status"] = "banned"
                ip = get_real_ip()
                db.setdefault("security_alerts", []).insert(0, {"time": int(time.time()*1000), "id": ip, "reason": reason})
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
                    v = kd["violations"]
                    if v == 1:
                        kd["temp_ban_until"] = now + (30 * 60 * 1000)
                        log_admin_action(db, f"Phạt 30 Phút Key {key} (Share IP)")
                    elif v == 2:
                        kd["temp_ban_until"] = now + (12 * 3600 * 1000)
                        log_admin_action(db, f"Phạt 12 Giờ Key {key} (Share IP)")
                    else:
                        kd["status"] = "banned"
                        log_admin_action(db, f"Banned Vĩnh Viễn Key {key} (Share IP)")
                    kd["known_ips"] = {}
                    save_db(db)
                    return "Banned for sharing", 403
                active_sessions[key] = {"ip": ip, "key": key, "last_seen": time.time()}
                return "ok", 200
        return "invalid", 403
    except: return "error", 500

@app.route('/api/script/olm_vip.user.js')
def serve_olm_script():
    resp = make_response(OLM_SCRIPT)
    resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    return resp

# ========================================================
# GIAO DIỆN CSS & HTML TOÀN CỤC Y HỆT ẢNH
# ========================================================
CSS_GLASS = """
body { background-color: #05050A !important; color: #fff !important; font-family: 'Segoe UI', Tahoma, sans-serif; min-height: 100vh; margin:0; }
.glass-panel { background-color: #11111A !important; border: 1px solid #333 !important; border-radius: 20px !important; box-shadow: 0 10px 40px rgba(0,0,0,0.8) !important; padding: 40px; text-align: center; width: 100%; max-width: 400px; margin: 50px auto; }
.card { background-color: #11111A !important; border-radius: 15px !important; border: 1px solid #333 !important; box-shadow: 0 5px 15px rgba(0,0,0,0.5) !important; transition: 0.3s; }
.card:hover { border-color: #00ffcc !important; box-shadow: 0 0 15px rgba(0,255,204,0.2) !important; }
h2, h3, h4, h5 { color: #00ffcc !important; font-weight: 900 !important; letter-spacing: 1px !important; }
.text-neon { color: #00ffcc !important; text-shadow: 0 0 10px rgba(0,255,204,0.5) !important; }
.text-purple { color: #bd00ff !important; text-shadow: 0 0 10px rgba(189,0,255,0.5) !important; }
.form-control, .form-select, textarea { background-color: #0a0a12 !important; border: 1px solid #444 !important; color: #fff !important; padding: 12px; border-radius: 8px; margin-bottom: 15px; }
.form-control:focus, .form-select:focus, textarea:focus { border-color: #00ffcc !important; box-shadow: 0 0 10px rgba(0,255,204,0.3) !important; outline: none !important; }
.btn-neon { background: linear-gradient(45deg, #00ffcc, #bd00ff) !important; border: none !important; color: #000 !important; font-weight: bold !important; width: 100%; padding: 12px; border-radius: 8px; transition: 0.3s !important; cursor: pointer; }
.btn-neon:hover { transform: translateY(-2px) !important; box-shadow: 0 5px 20px rgba(0,255,204,0.4) !important; }
a.link-neon { color: #bd00ff !important; text-decoration: none !important; font-weight: bold !important; transition: 0.3s !important; }
a.link-neon:hover { color: #00ffcc !important; text-shadow: 0 0 10px #00ffcc !important; }
.table { color: #fff !important; }
.table-dark { --bs-table-bg: transparent !important; --bs-table-striped-bg: rgba(0, 255, 204, 0.05) !important; border-color: #333 !important; }
.table-active { background-color: #1a1a2e !important; }
.badge { font-size: 12px !important; padding: 5px 8px !important; }
.vip-glow { animation: vipPulse 2s infinite alternate; border: 2px solid #bd00ff !important; box-shadow: 0 0 20px rgba(189,0,255,0.4) !important; }
@keyframes vipPulse { from { box-shadow: 0 0 10px rgba(189,0,255,0.2); } to { box-shadow: 0 0 30px rgba(189,0,255,0.8); border-color: #ff00ff; } }
.nor-glow { border: 2px solid #0099ff !important; }
"""

@app.route('/')
def home():
    try:
        shop_html = ""
        for pkg_id, pkg in SHOP_PACKAGES.items():
            vip_tag = '<div class="badge bg-danger mb-2">🔥 VIP PRO</div>' if pkg["vip"] else '<div class="badge bg-secondary mb-2">THƯỜNG</div>'
            border_c = "#bd00ff" if pkg["vip"] else "#0099ff"
            shop_html += f'''
            <div class="col-md-3 col-6 mb-3">
                <div class="card p-3 h-100 text-center" style="border-color:{border_c};">
                    {vip_tag}
                    <h5 class="text-white fw-bold">{pkg["name"]}</h5>
                    <div style="font-size:22px;font-weight:900;color:{border_c};margin:10px 0;">{pkg["price"]:,}đ</div>
                    <a href="/login" class="btn btn-outline-info w-100 mt-auto fw-bold">MUA NGAY</a>
                </div>
            </div>'''

        welcome_script = ""
        if not session.get('welcomed'):
            session['welcomed'] = True
            welcome_script = "Swal.fire({ title: 'CHÀO MỪNG ĐẾN VỚI LVT TOOL!', html: '<b style=\"color:#00ffcc\">Hệ thống tự động hóa và bảo mật đỉnh cao.</b><br><br>👉 Vui lòng Đăng nhập hoặc Đăng ký để trải nghiệm!', icon: 'success', background: '#11111A', color: '#fff', confirmButtonColor: '#bd00ff', confirmButtonText: 'ĐÃ HIỂU' });"

        return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>LVT TOOL - Trang Chủ</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>{CSS_GLASS} .hero{{background:linear-gradient(135deg,#000,#0a192f);padding:80px 20px;text-align:center;border-bottom:1px solid #00ffcc;}}</style></head><body>
        <div class="hero"><h1 class="text-neon fw-bold mb-3">⚡ HỆ THỐNG LVT TOOL VIP ⚡</h1><p class="text-secondary fs-5 mb-4">Tự động hóa thông minh - Bảo mật đa tầng - Kích hoạt trên thiết bị cực dễ</p><a href="#shop" class="btn btn-lg fw-bold mb-2" style="background:#00ffcc;color:#000;">XEM BẢNG GIÁ</a> <a href="/login" class="btn btn-outline-info btn-lg fw-bold ms-md-2 mb-2">ĐĂNG NHẬP LẤY KEY</a> <a href="/register" class="btn btn-outline-light btn-lg fw-bold ms-md-2 mb-2">ĐĂNG KÝ</a></div>
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

        return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Đăng Nhập</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>{CSS_GLASS}</style></head><body><div class="glass-panel"><h2 class="text-neon">⚡ ĐĂNG NHẬP</h2><form method="POST"><input type="text" name="username" class="form-control" placeholder="Tên đăng nhập" required><input type="password" name="password" class="form-control" placeholder="Mật khẩu" required><button type="submit" class="btn-neon">VÀO HỆ THỐNG</button></form><div class="mt-4"><p class="text-secondary">Chưa có tài khoản? <a href="/register" class="link-neon">Đăng ký ngay</a></p><a href="/" class="text-muted" style="text-decoration:none;font-size:12px;">🏠 Trở về Trang chủ</a></div></div></body></html>'''
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
            return swal_redirect("Tuyệt vời!", "Đăng ký thành công. Hãy đăng nhập!", "success", "/login")

        return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Đăng Ký</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>{CSS_GLASS}</style></head><body><div class="glass-panel"><h2 class="text-neon">⚡ TẠO TÀI KHOẢN</h2><form method="POST"><input type="text" name="username" class="form-control" placeholder="Tên đăng nhập (liền không dấu)" required><input type="password" name="password" class="form-control" placeholder="Mật khẩu (Tối thiểu 6 ký tự)" required><button type="submit" class="btn-neon">ĐĂNG KÝ NGAY</button></form><div class="mt-4"><p class="text-secondary">Đã có tài khoản? <a href="/login" class="link-neon">Đăng nhập</a></p><a href="/" class="text-muted" style="text-decoration:none;font-size:12px;">🏠 Trở về Trang chủ</a></div></div></body></html>'''
    except Exception as e: return f"LỖI HỆ THỐNG: {str(e)}", 200

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ========================================================
# DASHBOARD NGƯỜI DÙNG & QUẢN LÝ KEY CỦA TÔI
# ========================================================
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
            shop_html += f'''
            <div class="col-lg-3 col-6 mb-3">
                <div class="card p-3 h-100 text-center" style="border-color:{border_c}; cursor:pointer;" onclick="confirmBuy('{pkg_id}', '{pkg['name']}', {pkg['price']})">
                    {vip_tag}
                    <h6 class="text-white fw-bold">{pkg['name']}</h6>
                    <h4 style="color:{border_c}; font-weight:900;">{pkg['price']:,}đ</h4>
                    <button class="btn btn-sm w-100 fw-bold mt-auto" style="background:{border_c}; color:#fff;">MUA NGAY</button>
                </div>
            </div>'''

        # DANH SÁCH KEY ĐÃ MUA CỦA NGƯỜI DÙNG
        now = int(time.time() * 1000)
        my_keys_html = ""
        for pk in owned_keys:
            k = pk['key']
            kd = db["keys"].get(k)
            if not kd: continue # Key đã bị admin xóa
            
            exp = kd.get("exp")
            if exp == "permanent": exp_str = '<span class="text-success">Vĩnh viễn</span>'
            elif exp == "pending": exp_str = '<span class="text-info">Chưa KH</span>'
            else:
                if exp < now: exp_str = '<span class="text-danger">Hết hạn</span>'
                else: exp_str = f'<span class="text-warning">{time.strftime("%d/%m/%Y", time.localtime(exp/1000))}</span>'
                
            rc = kd.get("reset_count", 0)
            vip_icon = "💎 " if kd.get("vip") else "🔑 "
            my_keys_html += f'''
            <tr>
                <td>
                    <strong class="text-info" style="cursor:pointer;" onclick="copyMyKey('{k}')" title="Bấm Copy">{vip_icon}{k} <i class="fas fa-copy text-secondary fs-6"></i></strong>
                </td>
                <td>{exp_str}</td>
                <td>{rc} lần</td>
                <td>
                    <form action="/user_delete_key" method="POST" onsubmit="return confirm('Bạn có chắc chắn muốn xóa vĩnh viễn Key này khỏi tài khoản của bạn?');" class="m-0">
                        <input type="hidden" name="key_to_delete" value="{k}">
                        <button type="submit" class="btn btn-sm btn-outline-danger fw-bold">XÓA</button>
                    </form>
                </td>
            </tr>
            '''
        if not my_keys_html:
            my_keys_html = '<tr><td colspan="4" class="text-muted py-4">Bạn chưa có Key nào. Vui lòng mua Key bên trên!</td></tr>'

        return f'''
        <!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Dashboard - User</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>{CSS_GLASS}</style></head>
        <body class="p-2 p-md-4">
        <div class="container" style="max-width:1100px;">
            <div class="d-flex flex-column flex-md-row justify-content-between align-items-center mb-4 border-bottom border-secondary pb-3">
                <h2 class="text-neon mb-3 mb-md-0 m-0">⚡ LVT SHOP CÁ NHÂN</h2>
                <div><span class="me-3">Xin chào, <b class="text-info">{username.upper()}</b></span> <a href="/logout" class="btn btn-sm btn-outline-danger fw-bold">Thoát</a></div>
            </div>
            
            <div class="row g-4">
                <div class="col-md-4">
                    <div class="card p-4 text-center border-info h-100">
                        <h5 class="text-secondary">SỐ DƯ CỦA BẠN</h5>
                        <h2 class="text-neon" style="font-size:40px;">{balance:,}<small style="font-size:20px;">đ</small></h2>
                        <hr class="border-secondary">
                        <p class="text-warning mb-1" style="font-size:14px;"><i class="fas fa-university"></i> <b>CÁCH NẠP TIỀN AUTO</b></p>
                        <p class="text-muted" style="font-size:12px;">Chuyển khoản với nội dung:<br><strong class="text-white fs-6">NAP {username.upper()}</strong></p>
                        <a href="https://zalo.me/123456789" target="_blank" class="btn btn-outline-info btn-sm fw-bold mt-auto">Liên hệ Admin (Zalo)</a>
                    </div>
                </div>
                <div class="col-md-8">
                    <div class="card p-4 border-secondary h-100">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h4 class="text-purple m-0"><i class="fas fa-shopping-cart"></i> MUA MÃ KEY MỚI</h4>
                        </div>
                        <div class="row g-2">{shop_html}</div>
                    </div>
                </div>
                
                <div class="col-12">
                    <div class="card p-4 border-success text-center">
                        <h4 class="text-neon mb-2"><i class="fas fa-rocket"></i> VÀO PHÒNG ĐIỀU KHIỂN HACK</h4>
                        <p class="text-muted mb-3">Vào phòng điều khiển để liên kết Key và kích hoạt Hack V9.0.</p>
                        <a href="/key_login" class="btn fw-bold w-100 mt-2" style="background:linear-gradient(45deg,#00ffcc,#0099ff);color:#000;padding:12px; font-size:18px;">
                            ĐĂNG NHẬP VÀO KHOANG LÁI <i class="fas fa-arrow-right"></i>
                        </a>
                    </div>
                </div>

                <div class="col-12">
                    <div class="card p-3 border-secondary">
                        <h5 class="text-info mb-3"><i class="fas fa-key"></i> QUẢN LÝ KEY CỦA BẠN</h5>
                        <div class="table-responsive">
                            <table class="table table-dark table-hover table-sm align-middle text-center mb-0">
                                <thead class="table-active">
                                    <tr><th>🔑 Mã Key (Bấm copy)</th><th>⏳ Thời gian</th><th>🔄 Lượt Reset</th><th>⚙️ Thao tác</th></tr>
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
        <script>
            {swal_scripts}
            function copyMyKey(k) {{ navigator.clipboard.writeText(k); Swal.fire({{toast:true,position:'top-end',icon:'success',title:'Đã copy Key!',showConfirmButton:false,timer:1500,background:'#111',color:'#fff'}}); }}
            function confirmBuy(id, name, price) {{
                Swal.fire({{
                    title: 'CHỈ ĐỊNH TÀI KHOẢN OLM',
                    html: `<p>Gói <b>${{name}}</b> (${{price.toLocaleString()}}đ)</p>
                           <input type="text" id="swal-olm" class="swal2-input" placeholder="Nhập nick OLM (Ví dụ: hp_luongvantuyen)" style="width: 80%; background: #000; color: #00ffcc; border: 1px solid #00ffcc;">
                           <div style="margin-top: 15px; font-size: 14px;">
                               <b>CHỌN HỆ ĐIỀU HÀNH BẠN ĐANG XÀI:</b><br>
                               <label class="me-3"><input type="radio" name="swal-os" value="android" checked> <i class="fab fa-android"></i> Android/PC</label>
                               <label><input type="radio" name="swal-os" value="ios"> <i class="fab fa-apple"></i> iOS</label>
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

# ========================================================
# HỆ THỐNG ĐĂNG NHẬP KEY & KÍCH HOẠT HACK (KEY DASHBOARD MỚI)
# ========================================================
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

        return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Kích Hoạt Key</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>{CSS_GLASS}</style></head><body><div class="glass-panel"><h2 class="text-neon">🔑 KHỞI ĐỘNG KEY</h2><form method="POST"><input type="text" name="key_input" class="form-control text-center fs-5" placeholder="Dán mã Key của bạn vào đây..." required><button type="submit" class="btn-neon">ĐĂNG NHẬP KEY</button></form><div class="mt-4"><a href="/dashboard" class="link-neon">⬅ Trở về Quầy Shop</a></div></div></body></html>'''
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
        <style>{CSS_GLASS} .card-key{{background:#11111A !important;border-radius:15px !important;}}</style></head>
        <body class="p-3">
        <div class="container" style="max-width:800px;">
            <div class="d-flex justify-content-between align-items-center mb-4 border-bottom border-secondary pb-2">
                <h3 style="color:#00ffcc;margin:0;font-weight:900;">⚡ KHOANG LÁI HACK</h3>
                <div>
                    <a href="/dashboard" class="btn btn-outline-light btn-sm fw-bold me-2">Shop/Quản Lý</a>
                    <a href="/logout_key" class="btn btn-danger btn-sm fw-bold">Đăng Xuất Key</a>
                </div>
            </div>
            
            <div class="card-key {card_class} p-4 text-center mb-4">
                <div class="badge mb-3" style="background:{'#bd00ff' if is_vip else '#0099ff'}; font-size:16px;">{vip_text}</div>
                <h2 class="text-white mb-2" style="font-family:monospace;letter-spacing:2px;cursor:pointer;" onclick="copyT('{active_key}')">{active_key} <i class="fas fa-copy text-muted fs-5"></i></h2>
                
                <div class="my-3 py-2" style="background:#000; border-radius:8px; border:1px dashed #444;">
                    <p class="text-secondary mb-1" style="font-size:12px;">KEY OLM MODE CỦA HỆ THỐNG</p>
                    <b class="text-warning" style="font-family:monospace; font-size:18px;">OLM_VIP_786B-XQCH-BYEF-SYUS</b>
                </div>

                <div id="countdown-box" class="mt-3">
                    <p class="text-muted mb-0">Thời gian còn lại:</p>
                    <h3 id="timer" class="text-danger fw-bold" style="font-family:monospace;">ĐANG TÍNH...</h3>
                </div>
                
                <div class="d-flex justify-content-center gap-5 mt-3 pt-3 border-top border-secondary">
                    <div><small class="text-secondary">Thiết Bị Của Bạn</small><br><b class="fs-4 text-info">{len(kd.get('devices', []))}/{kd.get('maxDevices', 1)}</b></div>
                </div>
            </div>
            
            <div class="row g-3">
                <div class="col-12 mt-4 text-center">
                    <p class="text-warning fw-bold mb-2">🚀 Ấn nút bên dưới hệ thống sẽ tự động đồng bộ Key và mở khóa OLM.VN</p>
                    <a href="https://olm.vn/?lvt_key={active_key}" target="_blank" class="btn w-100 p-3 fw-bold fs-5 text-dark" style="background:linear-gradient(45deg,#00ffcc,#0099ff);box-shadow:0 0 20px rgba(0,255,204,0.4);border-radius:12px;">
                        MỞ KHÓA VÀ SỬ DỤNG HACK NGAY
                    </a>
                    <div class="mt-3">
                        <small class="text-muted">Chưa cài đặt Userscript? <a href="/api/script/olm_vip.user.js" target="_blank" style="color:#00ffcc; text-decoration:none;">Bấm vào đây để cài đặt (Lần đầu)</a></small>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            function copyT(t){{ navigator.clipboard.writeText(t); Swal.fire({{toast:true,position:'top-end',icon:'success',title:'Đã sao chép Key!',showConfirmButton:false,timer:1500,background:'#111',color:'#fff'}}); }}
            
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

@app.route('/user_reset_hwid', methods=['POST'])
def user_reset_hwid():
    try:
        if 'username' not in session: return redirect('/login')
        active_key = session.get('active_key')
        if not active_key: return redirect('/key_login')
        
        db = load_db()
        with db_lock:
            u = db["users"].get(session['username'])
            kd = db["keys"].get(active_key)
            if not kd: return swal_back("Lỗi", "Key không tồn tại", "error")
            
            rc = kd.get("reset_count", 0)
            if rc == 0:
                kd["devices"] = []; kd["known_ips"] = {}; kd["bound_olm"] = ""; kd["reset_count"] += 1
                save_db(db)
                return swal_redirect("Reset Thành Công!", "Đã gỡ thiết bị và xóa định danh OLM miễn phí (Lần 1).", "success", "/key_dashboard")
            else:
                if u["balance"] < 10000: return swal_back("Thất bại!", "Bạn cần 10,000đ để Reset từ lần thứ 2 trở đi.", "error")
                u["balance"] -= 10000
                kd["devices"] = []; kd["known_ips"] = {}; kd["bound_olm"] = ""; kd["reset_count"] += 1
                save_db(db)
                return swal_redirect("Reset Thành Công!", "Đã trừ 10,000đ và gỡ thiết bị thành công.", "success", "/key_dashboard")
    except Exception as e: return swal_back("Lỗi", str(e), "error")

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
        
        return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Admin Login</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>{CSS_GLASS}</style></head><body><div class="glass-panel"><h2 class="text-neon">🔐 QUẢN TRỊ VIÊN</h2><form method="POST"><input type="text" name="username" class="form-control" placeholder="Tên Admin" required><input type="password" name="password" class="form-control" placeholder="Mật Khẩu" required><button type="submit" class="btn-neon">VÀO PHÒNG ĐIỀU KHIỂN</button></form></div></body></html>'''
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
            
            u_keys = "<br>".join([f"🔑 {escape(pk.get('key'))}" for pk in udata.get("purchased_keys", [])]) or "<span class='text-muted'>Chưa có</span>"
            u_ips = "<br>".join([escape(ip) for ip in udata.get("ips", [])]) or "<span class='text-muted'>Trống</span>"
            created = time.strftime("%d/%m/%y", time.localtime(udata.get("created_at", 0)/1000))
            
            users_html += f'''
            <tr>
                <td><strong class="text-warning">{escape(uname)}</strong><br><small class="text-muted">{created}</small></td>
                <td><span class="badge bg-success">{bal:,}đ</span></td>
                <td style="font-size:11px; text-align:left;">{u_keys}</td>
                <td style="font-size:11px; text-align:left; color:#ffcc00;">{u_ips}</td>
                <td>
                    <form action="/admin/add_balance" method="POST" class="d-flex gap-1 justify-content-center m-0">
                        <input type="hidden" name="username" value="{escape(uname)}">
                        <input type="number" name="amount" class="form-control form-control-sm bg-dark text-light border-secondary px-1 text-center m-0" style="width:70px;font-size:12px;height:28px;" placeholder="± Tiền" required>
                        <button type="submit" class="btn btn-sm btn-primary fw-bold" style="font-size:11px;height:28px;">CỘNG</button>
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

            keys_html += f'''
            <tr class="key-row">
                <td>
                    <strong class="text-info" style="font-size:12px; cursor:pointer;" onclick="copyKey('{safe_k}')" title="Bấm để copy">{safe_k} <i class="fas fa-copy text-muted"></i></strong><br>
                    {vip_badge} {status_badge}<br>
                    <small class="text-warning">Chủ: {escape(data.get('owner', 'Admin'))}</small>
                </td>
                <td style="font-size:11px;">{exp_text}</td>
                <td><span class="badge bg-info text-dark">{len(data.get('devices', []))}/{data.get('maxDevices', 1)}</span></td>
                <td>
                    <div class="d-flex flex-wrap gap-1 justify-content-center">
                        <a href="/admin/action/reset-dev/{safe_k}" class="btn btn-primary btn-sm" style="font-size:10px;">🔄 Máy</a>
                        <a href="/admin/action/unban_temp/{safe_k}" class="btn btn-success btn-sm" style="font-size:10px;">Gỡ Phạt</a>
                        <a href="/admin/action/{"unban" if is_banned else "ban"}/{safe_k}" class="btn btn-{"light" if is_banned else "danger"} btn-sm" style="font-size:10px;">{"Cứu" if is_banned else "Trảm"}</a>
                        <a href="/admin/action/delete/{safe_k}" class="btn btn-dark btn-sm" onclick="return confirm('Xóa vĩnh viễn Key này?')" style="font-size:10px;">🗑️</a>
                    </div>
                </td>
            </tr>'''

        blacklist_rows = "".join([f'<li class="list-group-item bg-dark text-light d-flex justify-content-between align-items-center" style="font-size:12px;">{escape(ip)} <a href="/admin/unban_ip/{escape(ip)}" class="btn btn-sm btn-danger p-0 px-2">Gỡ</a></li>' for ip in banned_ips])
        if not blacklist_rows: blacklist_rows = '<li class="list-group-item bg-dark text-muted text-center" style="font-size:12px;">Sạch sẽ</li>'
        
        safe_admin_script = escape(db.get("users", {}).get("admin", {}).get("custom_script", ""))

        return f'''
        <!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ADMIN DASHBOARD</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>{CSS_GLASS} .card{{background:#11111A;border:1px solid #333;border-radius:12px;}} h5{{color:#00ffcc;font-weight:900;}} .table-container{{max-height:450px;overflow-y:auto;}} tbody tr:hover{{background:rgba(0,255,204,0.05)!important;}}</style>
        </head><body class="p-2 p-md-4">
        <div class="container-fluid">
            <div class="d-flex justify-content-between align-items-center mb-3 border-bottom border-secondary pb-2">
                <h3 class="m-0 text-neon">⚡ LVT SECURE ADMIN</h3>
                <div><a href="/logout" class="btn btn-outline-danger btn-sm fw-bold">Thoát</a></div>
            </div>
            
            <div class="row g-3">
                <div class="col-lg-7">
                    <div class="card p-3 h-100" style="border-color:#3366ff;">
                        <h5 style="color:#3366ff;"><i class="fas fa-users"></i> DANH SÁCH USER</h5>
                        <div class="table-container">
                            <table class="table table-dark table-hover table-sm align-middle mb-0 text-center">
                                <thead class="table-active"><tr><th>Tài Khoản</th><th>Số Dư</th><th>Keys Sỡ Hữu</th><th>IP Đăng Nhập</th><th>Cộng/Trừ Tiền</th></tr></thead>
                                <tbody>{users_html}</tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div class="col-lg-5">
                    <div class="row g-3 h-100">
                        <div class="col-md-12">
                            <div class="card p-3 h-100" style="border-color:#bd00ff;">
                                <h5 style="color:#bd00ff;"><i class="fas fa-key"></i> TẠO KEY MỚI</h5>
                                <form action="/admin/create" method="POST" class="row g-2 mt-1">
                                    <div class="col-6"><input type="text" name="prefix" class="form-control form-control-sm bg-dark text-light border-secondary" placeholder="Mã (T)"></div>
                                    <div class="col-6"><input type="number" name="quantity" class="form-control form-control-sm bg-dark text-light border-secondary" value="1" placeholder="Số Lượng"></div>
                                    <div class="col-6"><input type="number" name="duration" class="form-control form-control-sm bg-dark text-light border-secondary" placeholder="Độ dài" required></div>
                                    <div class="col-6"><select name="type" class="form-select form-select-sm bg-dark text-light border-secondary"><option value="hour">Giờ</option><option value="day" selected>Ngày</option><option value="month">Tháng</option><option value="permanent">V.Viễn</option></select></div>
                                    
                                    <div class="col-12 mt-2 d-flex justify-content-center align-items-center">
                                        <div class="form-check form-switch fs-5">
                                          <input class="form-check-input" type="checkbox" role="switch" name="is_vip" id="vipSwitch">
                                          <label class="form-check-label text-warning fw-bold ms-2" for="vipSwitch">🔑 Gắn mác Key VIP PRO</label>
                                        </div>
                                    </div>
                                    
                                    <div class="col-12 mt-2"><button type="submit" class="btn btn-sm w-100 fw-bold" style="background:#bd00ff;color:white;">🚀 TẠO NGAY</button></div>
                                </form>
                            </div>
                        </div>
                        <div class="col-md-12 mt-3">
                            <div class="card p-3 h-100" style="border-color:#ff3366;">
                                <h5 class="text-danger"><i class="fas fa-shield-virus"></i> FIREWALL BANS</h5>
                                <form action="/admin/ban_ip" method="POST" class="d-flex gap-2 mb-2">
                                    <input type="text" name="ip" class="form-control form-control-sm bg-dark text-light border-secondary" placeholder="Nhập IP..." required>
                                    <button type="submit" class="btn btn-sm btn-danger fw-bold">Chặn</button>
                                </form>
                                <ul class="list-group list-group-flush" style="max-height:100px;overflow-y:auto;">{blacklist_rows}</ul>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-lg-12">
                    <div class="card p-3 h-100" style="border-color:#00ffcc;">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="m-0 text-neon"><i class="fas fa-database"></i> TẤT CẢ MÃ KEY</h5>
                            <input type="text" class="form-control form-control-sm bg-dark text-light border-info m-0" style="width:200px;" placeholder="🔍 Tìm Key..." onkeyup="let s=this.value.toLowerCase();document.querySelectorAll('.key-row').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(s)?'':'none');">
                        </div>
                        <div class="table-container">
                            <table class="table table-dark table-sm align-middle table-hover text-center mb-0">
                                <thead class="table-active"><tr><th>🔑 Key / Chủ</th><th>⏳ Hạn Dùng</th><th>💻 Thiết bị</th><th>⚙️ Thao tác</th></tr></thead>
                                <tbody>{keys_html}</tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            function copyKey(t){{ navigator.clipboard.writeText(t); Swal.fire({{toast:true,position:'top-end',icon:'success',title:'Đã Copy Key!',showConfirmButton:false,timer:1000,background:'#111',color:'#00ffcc'}}); }}
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

@app.route('/admin/update_script', methods=['POST'])
def admin_update_script():
    try:
        if session.get('role') != 'admin': return redirect('/login')
        ns = request.form.get('script_content', '')
        db = load_db()
        with db_lock:
            db["users"]["admin"]["custom_script"] = ns
            save_db(db)
        return redirect('/admin')
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
