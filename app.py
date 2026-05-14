import os, json, time, random, hashlib, threading, requests, shutil, base64, secrets, hmac, string, copy, traceback
import urllib.parse
from html import escape
from flask import Flask, request, jsonify, redirect, make_response, session, abort
from werkzeug.exceptions import HTTPException

try:
    os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
    time.tzset()
except: pass

app = Flask(__name__)

CSS_GLASS = """
.glass-panel { background: rgba(17, 17, 26, 0.7); backdrop-filter: blur(15px); border: 1px solid rgba(0, 255, 204, 0.3); border-radius: 15px; padding: 30px; box-shadow: 0 0 20px rgba(0, 255, 204, 0.2); max-width: 400px; margin: 50px auto; text-align: center; }
.text-neon { color: #00ffcc; text-shadow: 0 0 10px rgba(0, 255, 204, 0.5); }
.btn-neon { background: linear-gradient(90deg, #00ffcc, #0099ff); border: none; color: #000; font-weight: bold; padding: 10px 20px; border-radius: 8px; width: 100%; transition: 0.3s; }
.btn-neon:hover { transform: scale(1.05); box-shadow: 0 0 15px rgba(0, 255, 204, 0.5); }
"""

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
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"BACKUP DB\nTime: {time.strftime('%d/%m/%Y %H:%M:%S')}"}, files={"document": f}, timeout=10)
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
                        if text.startswith("/start"):
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage", json={"chat_id": chat_id, "message_id": msg_id})
                            welcome = f"<b>SYSTEM SECURE</b>\n\nMở Mini App để xác thực ID:"
                            keyboard = {"inline_keyboard": [[{"text": "MỞ MINI APP", "web_app": {"url": f"{WEB_URL}/telegram_mini_app"}}]]}
                            requests.post(url_base + "/sendMessage", json={"chat_id": chat_id, "text": welcome, "parse_mode": "HTML", "reply_markup": keyboard})
                        elif text.startswith("// ==UserScript==") and chat_id == TELEGRAM_CHAT_ID:
                            db = load_db()
                            with db_lock:
                                db.setdefault("settings", {})["violentmonkey_script"] = text
                                log_admin_action(db, "TeleBot: Update Script")
                                save_db(db)
                            send_telegram_alert("Updated Violentmonkey Script!")
        except Exception: pass
        time.sleep(2)

threading.Thread(target=telegram_polling, daemon=True).start()

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException): return e
    return "Maintenance", 500

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

def safe_int(val, default=0):
    try: return int(val)
    except: return default

def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def swal_redirect(title, text, icon, url):
    return f"""<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #05050A; }}</style></head><body><script>Swal.fire({{ title: `{title}`, html: `{text}`, icon: '{icon}', background: '#11111A', color: '#fff', confirmButtonColor: '#00ffcc', allowOutsideClick: false, customClass: {{ popup: 'border border-info' }}}}).then(() => {{ window.location.href = '{url}'; }});</script></body></html>"""

def swal_back(title, text, icon):
    return f"""<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #05050A; }}</style></head><body><script>Swal.fire({{ title: `{title}`, html: `{text}`, icon: '{icon}', background: '#11111A', color: '#fff', confirmButtonColor: '#bd00ff', allowOutsideClick: false, customClass: {{ popup: 'border border-danger' }}}}).then(() => {{ window.history.back(); }});</script></body></html>"""

def render_template_string_safe(content):
    resp = make_response(content)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp

DEFAULT_OLM_SCRIPT = r"""// ==UserScript==
// @name         LVT SECURE OLM LOADER
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  LVT SYSTEM
// @author       LVT
// @match        *://olm.vn/*
// @match        *://*.olm.vn/*
// @grant        unsafeWindow
// @grant        GM_addStyle
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @run-at       document-start
// ==/UserScript==
"""

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
                data.setdefault("tg_auth_ids", {})
                
                if "maintenance_until" not in data["settings"]: data["settings"]["maintenance_until"] = 0
                if "global_notice" not in data["settings"]: data["settings"]["global_notice"] = ""
                if "violentmonkey_script" not in data["settings"]: data["settings"]["violentmonkey_script"] = DEFAULT_OLM_SCRIPT
                if "tg_admins" not in data["settings"]: data["settings"]["tg_admins"] = [TELEGRAM_CHAT_ID]
                
                if "admin" not in data["users"]:
                    data["users"]["admin"] = {"password_hash": hash_pwd("120510@"), "role": "admin", "balance": 0, "created_at": int(time.time() * 1000), "ips": [], "purchased_keys": [], "notices": [], "custom_script": 'console.log("SYSTEM ACTIVE!");', "banned_until": 0}

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
                    data["keys"][k].setdefault("activated", False)
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
        except Exception: return 
        temp_file = DB_FILE + f'.{int(time.time() * 1000)}.tmp'
        try:
            with open(temp_file, 'w', encoding='utf-8') as f: 
                f.write(db_str)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, DB_FILE)
            shutil.copy2(DB_FILE, DB_BACKUP)
            _last_db_mtime = os.path.getmtime(DB_FILE)
        except Exception:
            if os.path.exists(temp_file): os.remove(temp_file)

def generate_secure_key(prefix="", is_vip=False):
    chars = string.ascii_letters + string.digits
    safe_chars = ''.join([c for c in chars if c not in 'IlO0'])
    rand_str = ''.join(secrets.choice(safe_chars) for _ in range(15))
    t_vip = "VIP" if is_vip else "NOR"
    if prefix: return f"{prefix}-{t_vip}-{rand_str}"
    return f"LVT-{t_vip}-{rand_str}"

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
                if changed: save_db(db)
            if backup_counter >= 12:
                send_telegram_backup()
                backup_counter = 0
        except Exception: pass

threading.Thread(target=garbage_collector, daemon=True).start()

def get_real_ip():
    try:
        if request.headers.get("CF-Connecting-IP"): return request.headers.get("CF-Connecting-IP")
        if request.headers.getlist("X-Forwarded-For"): return request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
        return request.remote_addr
    except: return "Unknown"

@app.before_request
def firewall_and_csrf():
    try:
        db = load_db()
        banned_ips = set(db.get("banned_ips", []))
        ip = get_real_ip()
        if ip in banned_ips: return "Blocked", 403
        ua = (request.headers.get('User-Agent') or '').lower()
        blocked_bots = ['curl', 'postman', 'python', 'nmap', 'sqlmap', 'masscan', 'zgrab', 'wget', 'urllib', 'nikto']
        if any(bot in ua for bot in blocked_bots): return "Blocked", 403
        if request.path.startswith("/admin") and request.path not in ["/admin_login", "/telegram_mini_app"]:
            if session.get('role') != 'admin': return redirect('/admin_login')
    except: pass

@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN' 
    response.headers['X-Content-Type-Options'] = 'nosniff' 
    response.headers['X-XSS-Protection'] = '1; mode=block' 
    return response

@app.errorhandler(404)
def not_found_trap(e):
    return redirect('/telegram_mini_app')

@app.route('/')
def home_page():
    return redirect('/telegram_mini_app')

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
    if isinstance(mnt, int) and mnt > now: return False, "maintenance", mnt
    with db_lock:
        banned_olms = db.get("banned_olms", {})
        if req_olm_name != "N/A" and req_olm_name in banned_olms:
            ban_exp = banned_olms[req_olm_name]
            if ban_exp == "permanent" or ban_exp > now: return False, "banned_olm", ban_exp

        if key not in db["keys"]: return False, "error", "KEY_NOT_FOUND"
        kd = db["keys"][key]
        if not kd.get("activated", False): return False, "error", "KEY_NOT_ACTIVATED"
        if kd.get('status') == 'banned': return False, "error", "KEY_BANNED"
        temp_ban = kd.get("temp_ban_until", 0)
        if temp_ban > now: return False, "error", "TEMP_BANNED"
        db_changed = False
        if kd.get('exp') == 'pending': 
            kd['exp'] = now + kd.get('durationMs', 0)
            db_changed = True
        if kd.get('exp') != 'permanent' and now > kd.get('exp', 0): return False, "error", "KEY_EXPIRED"
        bound_olm = kd.get("bound_olm", "").strip()
        if bound_olm and req_olm_name != "N/A":
            if bound_olm.lower() != req_olm_name.lower():
                return False, "error", "INVALID_OLM"
        if deviceId:
            devices = kd.setdefault("devices", [])
            if deviceId not in devices:
                if len(devices) >= kd.get("maxDevices", 1): return False, "error", "DEVICE_LIMIT"
                devices.append(deviceId)
                db_changed = True
        if db_changed: save_db(db)
        return True, "success", "OK"

@app.route('/api/check', methods=['POST', 'OPTIONS'])
def check_api():
    try:
        ip = get_real_ip()
        if not check_api_rate_limit(ip): return jsonify({"status": "error"}), 429
        if request.method == 'OPTIONS': return make_response("ok", 200)
        data = request.json or {}
        if not verify_request_signature(data): return jsonify({"status": "error"}), 403
        key = data.get('key', '')[:100]
        deviceId = data.get('deviceId', '')[:100]
        olm_name = data.get('olm_name', 'N/A')[:100]
        db = load_db()
        valid, code, msg_or_time = _core_validate(db, key, deviceId, olm_name, ip)
        if not valid:
            if code == "maintenance": return jsonify({"status": "maintenance", "time": msg_or_time})
            if code == "banned_olm": return jsonify({"status": "banned_olm", "time": msg_or_time})
            return jsonify({"status": "error", "msg": msg_or_time}), 400
        kd = db["keys"][key]
        return jsonify({
            "status": "success", 
            "vip": kd.get("vip", False),
            "exp": kd.get("exp"),
            "name": key
        })
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
        enc = base64.b64encode(custom_script.encode('utf-8')).decode('utf-8')
        return jsonify({"status": "success", "payload": enc[::-1]})
    except: return jsonify({"status": "error"}), 500

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
    hx = rev_b64.encode('utf-8').hex()
    
    secure_core = f"""
    (function() {{
        try {{
            var _0x1a = "{hx}";
            var _0x2b = '';
            for(var i=0; i<_0x1a.length; i+=2) _0x2b += String.fromCharCode(parseInt(_0x1a.substr(i,2), 16));
            var _0x3c = _0x2b.split('').reverse().join('');
            var _0x4d = decodeURIComponent(escape(atob(_0x3c)));
            new Function(_0x4d)(); 
        }} catch(e) {{}}
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
    if '@grant        GM_xmlhttpRequest' not in header_str:
        header_str = header_str.replace('// ==/UserScript==', '// @grant        GM_xmlhttpRequest\n// ==/UserScript==')
    
    loader_logic = f"""
(function() {{
    'use strict';
    if (window.top !== window.self) return;
    const API = '{host_url}';
    
    function genHW() {{
        let c = document.createElement('canvas'); let ctx = c.getContext('2d');
        ctx.fillText("LVT_SEC", 2, 15);
        let hash = 0, str = c.toDataURL() + navigator.userAgent;
        for(let i=0; i<str.length; i++) hash = ((hash<<5)-hash)+str.charCodeAt(i);
        return "HW-" + Math.abs(hash).toString(16);
    }}
    let dev = localStorage.getItem('lvt_hw') || genHW();
    localStorage.setItem('lvt_hw', dev);
    
    function getU() {{
        let f = "N/A";
        try {{
            let c = document.cookie.split(';');
            for(let i=0;i<c.length;i++) {{
                if(c[i].trim().startsWith("username=")) f=decodeURIComponent(c[i].trim().substring(9)).replace(/^"|"$/g,'');
            }}
        }} catch(e) {{}}
        return f;
    }}
    
    function showP(msg, type="error") {{
        let d = document.createElement('div');
        d.style.cssText = "position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#111;border:2px solid "+(type==="error"?"#ff3366":"#00ffcc")+";color:#fff;padding:20px;border-radius:10px;z-index:999999;font-family:sans-serif;text-align:center;box-shadow:0 0 20px "+(type==="error"?"rgba(255,51,102,0.4)":"rgba(0,255,204,0.4)");
        d.innerHTML = `<h3>${{msg}}</h3><button id="lvt_cls" style="margin-top:10px;padding:5px 15px;background:#fff;color:#000;border:none;cursor:pointer;">Đóng</button>`;
        document.body.appendChild(d);
        document.getElementById('lvt_cls').onclick = () => d.remove();
    }}

    async function req(k) {{
        let ts = Date.now(), msg = k+ts+k, sig = "";
        if (window.crypto && window.crypto.subtle) {{
            let h = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(msg));
            sig = Array.from(new Uint8Array(h)).map(b=>b.toString(16).padStart(2,'0')).join('');
        }}
        return new Promise((r) => {{
            GM_xmlhttpRequest({{
                method:'POST', url: API+'/api/check', headers:{{'Content-Type':'application/json'}},
                data: JSON.stringify({{key:k, deviceId:dev, olm_name:getU(), timestamp:ts, signature:sig}}),
                onload: (res) => r(JSON.parse(res.responseText)), onerror: () => r({{status:'net_err'}})
            }});
        }});
    }}
    
    function loadC() {{
        GM_xmlhttpRequest({{
            method:'GET', url: API+'/api/script/core_engine.js?t='+Date.now(),
            onload: (res) => {{ if(res.status===200) try{{ eval(res.responseText); }}catch(e){{}} }}
        }});
    }}

    async function init() {{
        let saved = GM_getValue('lvt_key', '');
        if (!saved) {{
            let k = prompt("HỆ THỐNG LVT: Nhập Key đã kích hoạt trên Mini App:");
            if (k) {{ GM_setValue('lvt_key', k); saved = k; }} else return;
        }}
        let r = await req(saved);
        if (r.status === 'success') {{
            let remain = r.exp === 'permanent' ? 'Vĩnh Viễn' : Math.floor((r.exp - Date.now())/3600000) + ' giờ';
            showP(`Kích hoạt thành công!<br>Key: ${{r.name}}<br>Loại: ${{r.vip?'VIP':'THƯỜNG'}}<br>Thời gian: ${{remain}}`, "success");
            loadC();
        }} else {{
            GM_setValue('lvt_key', '');
            if(r.status==='maintenance') showP("Server bảo trì!");
            else if(r.status==='banned_olm') showP("OLM Banned!");
            else showP(r.msg || "Key không hợp lệ hoặc chưa kích hoạt!");
        }}
    }}
    
    if(document.readyState==="loading") document.addEventListener('DOMContentLoaded', init);
    else init();
}})();
"""
    resp = make_response(header_str + "\n" + loader_logic)
    resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    return resp

def is_tg_authorized(tg_id):
    db = load_db()
    auths = db.get("tg_auth_ids", {})
    if tg_id not in auths: return False
    now = int(time.time()*1000)
    data = auths[tg_id]
    if data.get("banned_until", 0) > now or data.get("banned_until") == "permanent": return "BANNED"
    if data.get("exp") != "permanent" and data.get("exp", 0) < now: return "EXPIRED"
    return True

@app.route('/api/tg/auth_check', methods=['POST'])
def tg_auth_check():
    data = request.json or {}
    tg_id = data.get("tg_id", "").strip()
    status = is_tg_authorized(tg_id)
    if status == True:
        db = load_db()
        return jsonify({"status": "ok", "exp": db["tg_auth_ids"][tg_id]["exp"], "banned": 0})
    if status == "BANNED":
        db = load_db()
        return jsonify({"status": "banned", "banned_until": db["tg_auth_ids"][tg_id]["banned_until"]})
    return jsonify({"status": "error"})

@app.route('/api/tg/activate_key', methods=['POST'])
def tg_activate_key():
    data = request.json or {}
    tg_id = data.get("tg_id", "")
    key = data.get("key", "").strip()
    olm = data.get("olm", "").strip()
    if is_tg_authorized(tg_id) != True: return jsonify({"status": "error", "msg": "ID Tele không hợp lệ!"})
    db = load_db()
    with db_lock:
        if key not in db["keys"]: return jsonify({"status": "error", "msg": "Key không tồn tại!"})
        kd = db["keys"][key]
        if kd.get("activated"): return jsonify({"status": "error", "msg": "Key đã được kích hoạt trước đó!"})
        kd["activated"] = True
        kd["bound_olm"] = olm
        kd["tg_owner"] = tg_id
        save_db(db)
    return jsonify({"status": "success", "msg": "Kích hoạt thành công!", "vip": kd["vip"]})

@app.route('/api/tg/my_keys', methods=['POST'])
def tg_my_keys():
    data = request.json or {}
    tg_id = data.get("tg_id", "")
    if is_tg_authorized(tg_id) != True: return jsonify({"status": "error"})
    db = load_db()
    my_keys = []
    now = int(time.time()*1000)
    for k, v in db.get("keys", {}).items():
        if v.get("tg_owner") == tg_id:
            exp_str = "Vĩnh viễn" if v["exp"]=="permanent" else ("Chưa KH" if v["exp"]=="pending" else ("Hết hạn" if v["exp"]<now else time.strftime("%d/%m %H:%M", time.localtime(v["exp"]/1000))))
            my_keys.append({"key": k, "exp": exp_str, "olm": v.get("bound_olm",""), "status": v.get("status"), "devs": len(v.get("devices",[])), "vip": v.get("vip")})
    return jsonify({"status": "success", "keys": my_keys})

@app.route('/telegram_mini_app')
def telegram_mini_app():
    db = load_db()
    mnt = db.get("settings", {}).get("maintenance_until", 0)
    now = int(time.time()*1000)
    is_mnt = "true" if (isinstance(mnt, int) and mnt > now) else "false"
    admin_notice = escape(db.get("settings", {}).get("global_notice", ""))
    
    html = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>LVT Mini App</title>
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>
            body {{ background: #0f111a; color: #fff; font-family: sans-serif; margin: 0; padding: 15px; }}
            .screen {{ display: none; }} .screen.active {{ display: block; }}
            .btn {{ background: linear-gradient(90deg, #00ffcc, #0099ff); border: none; width: 100%; padding: 14px; border-radius: 10px; color: #000; font-weight: bold; margin-bottom: 10px; }}
            .inp {{ width: 100%; box-sizing: border-box; background: #1a1d29; border: 1px solid #333; color: white; padding: 14px; border-radius: 10px; margin-bottom: 15px; }}
            .card {{ background: #1a1d29; border: 1px solid #333; padding: 15px; border-radius: 12px; margin-bottom: 10px; }}
            .nav {{ display: flex; gap: 5px; margin-bottom: 20px; }}
            .nav-btn {{ flex: 1; padding: 10px; background: #222; text-align: center; border-radius: 8px; color: #fff; border: 1px solid #444; }}
            .nav-btn.act {{ background: #00ffcc; color: #000; }}
            #welc {{ position:fixed; inset:0; background:rgba(0,0,0,0.9); z-index:99; display:none; align-items:center; justify-content:center; flex-direction:column; padding:20px; text-align:center; }}
        </style>
    </head>
    <body>
        <div id="welc">
            <h2 style="color:#00ffcc;">CHÀO MỪNG QUÝ KHÁCH</h2>
            <p>Trải nghiệm dịch vụ của tôi chúc bạn sử dụng vui vẻ nhé có thắc mắc gì bạn hãy liên hệ admin tele : @luongtuyen20</p>
            <button class="btn" onclick="hideW('2h')" style="margin-top:20px;">Ẩn 2 Giờ</button>
            <button class="btn" style="background:#ff3366;" onclick="hideW('forever')">Đóng vĩnh viễn</button>
        </div>
        <div id="scr-auth" class="screen active">
            <h2 style="text-align:center; color:#00ffcc; margin-top:50px;">XÁC THỰC ID TELEGRAM</h2>
            <input type="text" id="tg_id_inp" class="inp" placeholder="Nhập ID Telegram được cấp phép...">
            <button class="btn" onclick="auth()">XÁC NHẬN</button>
        </div>
        <div id="scr-dash" class="screen">
            <div class="nav">
                <div class="nav-btn act" onclick="switchT('act')">Kích Hoạt</div>
                <div class="nav-btn" onclick="switchT('mgr')">Quản Lý</div>
                <div class="nav-btn" onclick="switchT('scr')">Script</div>
            </div>
            <div id="tab-act" style="display:block;">
                <input type="text" id="k_inp" class="inp" placeholder="Nhập Key...">
                <input type="text" id="o_inp" class="inp" placeholder="Nhập Tài Khoản OLM Chỉ Định...">
                <button class="btn" onclick="actKey()">KÍCH HOẠT KEY</button>
            </div>
            <div id="tab-mgr" style="display:none;"><div id="k_list"></div></div>
            <div id="tab-scr" style="display:none;">
                <div class="card">
                    <h4 style="color:#00ffcc;margin-top:0;">VIOLENTMONKEY LOADER</h4>
                    <p style="font-size:12px;color:#ccc;">Auto kéo script ẩn. Copy mã dưới dán vào Violentmonkey.</p>
                    <textarea class="inp" rows="5" readonly style="font-family:monospace;font-size:10px;">// ==UserScript==
// @name LVT LOADER
// @match *://olm.vn/*
// @grant GM_xmlhttpRequest
// ==/UserScript==
(function(){{GM_xmlhttpRequest({{method:'GET',url:'{WEB_URL}/api/script/olm_vip.user.js?t='+Date.now(),onload:r=>{{try{{eval(r.responseText)}}catch(e){{}}}}}})}})();</textarea>
                </div>
            </div>
        </div>
        <script>
            let tgId = localStorage.getItem('lvt_tg_id');
            let isMnt = {is_mnt}; let notice = "{admin_notice}";
            if(isMnt) Swal.fire({{title:"BẢO TRÌ", text:"Hệ thống đang nâng cấp", icon:"warning", allowOutsideClick:false}});
            if(notice && !sessionStorage.getItem('notified')) {{ Swal.fire({{title:"THÔNG BÁO", text:notice}}); sessionStorage.setItem('notified','1'); }}
            
            function chkW() {{
                let hide = localStorage.getItem('hide_welc');
                if(hide === 'forever') return;
                if(hide && Date.now() < parseInt(hide)) return;
                document.getElementById('welc').style.display='flex';
            }}
            function hideW(t) {{
                if(t==='forever') localStorage.setItem('hide_welc','forever');
                else localStorage.setItem('hide_welc', Date.now() + 7200000);
                document.getElementById('welc').style.display='none';
            }}
            
            function api(path, body, cb) {{
                fetch(path, {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(body)}}).then(r=>r.json()).then(cb);
            }}
            function auth() {{
                let id = document.getElementById('tg_id_inp').value || tgId;
                if(!id) return;
                api('/api/tg/auth_check', {{tg_id: id}}, r => {{
                    if(r.status==='ok') {{
                        tgId = id; localStorage.setItem('lvt_tg_id', id);
                        document.getElementById('scr-auth').classList.remove('active');
                        document.getElementById('scr-dash').classList.add('active');
                        chkW(); loadK();
                    }} else if(r.status==='banned') {{
                        document.body.innerHTML = `<h1 style='color:red;text-align:center;margin-top:50px;'>ID BỊ CẤM</h1>`;
                    }} else Swal.fire('Lỗi', 'ID không có quyền truy cập!', 'error');
                }});
            }}
            if(tgId) auth();
            
            setInterval(()=>{{ if(tgId && document.getElementById('scr-dash').classList.contains('active')) auth(); }}, 30000);
            
            function switchT(t) {{
                ['act','mgr','scr'].forEach(x=>{{ document.getElementById('tab-'+x).style.display='none'; }});
                document.getElementById('tab-'+t).style.display='block';
                if(t==='mgr') loadK();
            }}
            function actKey() {{
                let k = document.getElementById('k_inp').value, o = document.getElementById('o_inp').value;
                if(!k||!o) return Swal.fire('Lỗi','Nhập đủ thông tin','error');
                api('/api/tg/activate_key', {{tg_id:tgId, key:k, olm:o}}, r => {{
                    if(r.status==='success') Swal.fire('Thành công', `Key ${{r.vip?'VIP':'THƯỜNG'}} kích hoạt thành công!`, 'success');
                    else Swal.fire('Lỗi', r.msg, 'error');
                }});
            }}
            function loadK() {{
                api('/api/tg/my_keys', {{tg_id:tgId}}, r => {{
                    if(r.status==='success') {{
                        let h = '';
                        r.keys.forEach(k=>{{
                            h+=`<div class="card">
                            <b style="color:#00ffcc;">${{k.key}}</b> ${{k.vip?'[VIP]':''}}<br>
                            OLM: <span style="color:#ffcc00;">${{k.olm}}</span><br>
                            HSD: ${{k.exp}} | TB: ${{k.devs}}<br>
                            Trạng thái: ${{k.status==='active'?'Hoạt động':'Khóa'}}
                            </div>`;
                        }});
                        document.getElementById('k_list').innerHTML = h || 'Trống';
                    }}
                }});
            }}
        </script>
    </body>
    </html>
    """
    return render_template_string_safe(html)

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        db = load_db()
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '').strip()
        ud = db.get("users", {}).get(u)
        if ud and ud.get("role") == "admin" and ud.get("password_hash") == hash_pwd(p):
            session['role'] = 'admin'
            return redirect('/admin')
        return swal_back("Lỗi", "Sai thông tin", "error")
    return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><title>Admin Login</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>{CSS_GLASS}</style></head><body><div class="glass-panel"><h2 class="text-neon mb-4">ADMIN LVT</h2><form method="POST"><input type="text" name="username" class="form-control" required><input type="password" name="password" class="form-control mt-2" required><button class="btn-neon mt-3">LOGIN</button></form></div></body></html>'''

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    auths = db.get("tg_auth_ids", {})
    now = int(time.time()*1000)
    
    tg_html = ""
    for tid, tdata in auths.items():
        exp = tdata.get("exp")
        exp_s = "Vĩnh viễn" if exp=="permanent" else time.strftime("%d/%m %H:%M", time.localtime(exp/1000))
        ban = tdata.get("banned_until", 0)
        ban_s = "Banned" if (ban=="permanent" or ban>now) else "Hoạt động"
        tg_html += f"<tr><td>{escape(tid)}</td><td>{exp_s}</td><td>{ban_s}</td><td><a href='/admin/tg_del/{escape(tid)}' class='btn btn-sm btn-danger'>Xóa</a> <a href='/admin/tg_ban/{escape(tid)}' class='btn btn-sm btn-warning'>Ban</a></td></tr>"

    return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><title>Admin Control</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"></head><body class="p-4"><div class="container"><h2 class="text-info">QUẢN LÝ ID TELEGRAM MINI APP</h2>
    <div class="card p-3 bg-dark mb-4"><form action="/admin/tg_add" method="POST" class="d-flex gap-2"><input type="text" name="tg_id" class="form-control" placeholder="ID Tele" required><input type="number" name="time_val" class="form-control" placeholder="Thời gian"><select name="time_unit" class="form-select"><option value="days">Ngày</option><option value="months">Tháng</option><option value="permanent">Vĩnh Viễn</option></select><button class="btn btn-success">Thêm</button></form></div>
    <table class="table table-dark"><thead><tr><th>ID Telegram</th><th>Hạn Dùng Admin</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>{tg_html}</tbody></table>
    </div></body></html>'''

@app.route('/admin/tg_add', methods=['POST'])
def admin_tg_add():
    if session.get('role') != 'admin': return redirect('/admin_login')
    tid = request.form.get("tg_id", "").strip()
    tv = safe_int(request.form.get("time_val"))
    tu = request.form.get("time_unit")
    db = load_db()
    with db_lock:
        auths = db.setdefault("tg_auth_ids", {})
        if tu == "permanent": exp = "permanent"
        else:
            mult = {"days": 86400000, "months": 2592000000}.get(tu, 86400000)
            exp = int(time.time()*1000) + (tv * mult)
        auths[tid] = {"exp": exp, "banned_until": 0}
        save_db(db)
    return redirect('/admin')

@app.route('/admin/tg_del/<tid>')
def admin_tg_del(tid):
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    with db_lock:
        db.setdefault("tg_auth_ids", {}).pop(tid, None)
        save_db(db)
    return redirect('/admin')

@app.route('/admin/tg_ban/<tid>')
def admin_tg_ban(tid):
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    with db_lock:
        if tid in db.setdefault("tg_auth_ids", {}):
            db["tg_auth_ids"][tid]["banned_until"] = "permanent"
            save_db(db)
    return redirect('/admin')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
