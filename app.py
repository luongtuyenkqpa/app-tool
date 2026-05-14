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
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"BACKUP\n{time.strftime('%d/%m/%Y %H:%M:%S')}"}, files={"document": f}, timeout=10)
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
                            keyboard = {"inline_keyboard": [[{"text": "🛒 MỞ ỨNG DỤNG (MUA KEY & HACK)", "web_app": {"url": f"{WEB_URL}/telegram_mini_app"}}]]}
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
        except Exception: pass
        time.sleep(2)

threading.Thread(target=telegram_polling, daemon=True).start()

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException): return e
    return "Hệ thống đang bảo trì.", 500

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
    return f"""<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #05050A; }}</style></head><body><script>Swal.fire({{ title: `{title}`, html: `{text}`, icon: '{icon}', background: '#11111A', color: '#fff', confirmButtonColor: '#00ffcc', allowOutsideClick: false, customClass: {{ popup: 'border border-info' }}}}).then(() => {{ window.location.href = '{url}'; }});</script></body></html>"""

def swal_back(title, text, icon):
    return f"""<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #05050A; }}</style></head><body><script>Swal.fire({{ title: `{title}`, html: `{text}`, icon: '{icon}', background: '#11111A', color: '#fff', confirmButtonColor: '#bd00ff', allowOutsideClick: false, customClass: {{ popup: 'border border-danger' }}}}).then(() => {{ window.history.back(); }});</script></body></html>"""

def render_template_string_safe(content):
    resp = make_response(content)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp

DEFAULT_OLM_SCRIPT = r"""// ==UserScript==
// @name         OLM GOD MODE VIP
// @namespace    http://tampermonkey.net/
// @version      18.1
// @description  Hệ thống bảo vệ đa tầng
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
            if not data: data = {"users": {}, "keys": {}, "banned_ips": [], "admin_logs": [], "security_alerts": [], "settings": {}, "banned_olms": {}, "tg_auth_ids": {}}
            try:
                data.setdefault("users", {})
                data.setdefault("keys", {})
                data.setdefault("banned_ips", [])
                data.setdefault("admin_logs", [])
                data.setdefault("security_alerts", []) 
                data.setdefault("settings", {})
                data.setdefault("banned_olms", {})
                data.setdefault("tg_auth_ids", {str(TELEGRAM_CHAT_ID): {"exp": "permanent", "banned_until": 0}})
                
                if "maintenance_until" not in data["settings"]: data["settings"]["maintenance_until"] = 0
                if "global_notice" not in data["settings"]: data["settings"]["global_notice"] = ""
                if "violentmonkey_script" not in data["settings"]: data["settings"]["violentmonkey_script"] = DEFAULT_OLM_SCRIPT
                
                if "admin" not in data["users"]:
                    data["users"]["admin"] = {"password_hash": hash_pwd("120510@"), "role": "admin", "balance": 0, "created_at": int(time.time() * 1000), "ips": [], "purchased_keys": [], "notices": [], "custom_script": 'console.log("SYSTEM ACTIVE!");', "banned_until": 0}
                
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
    rand_str = ''.join(secrets.choice(safe_chars) for _ in range(12))
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
                if len(db.get("security_alerts", [])) > 100:
                    db["security_alerts"] = db["security_alerts"][:50]
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
        d.innerHTML = `<h3>${{msg}}</h3><button id="lvt_cls" style="margin-top:10px;padding:5px 15px;background:#fff;color:#000;border:none;cursor:pointer;border-radius:5px;font-weight:bold;">Đóng</button>`;
        document.body.appendChild(d);
        document.getElementById('lvt_cls').onclick = () => d.remove();
        if(type!=="error") {{
            let cd = document.createElement('div');
            cd.id = 'lvt_cd'; cd.style.marginTop = '10px'; cd.style.color = '#ffcc00';
            d.insertBefore(cd, document.getElementById('lvt_cls'));
        }}
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
            showP(`Kích hoạt thành công!<br>Key: ${{r.name}}<br>Loại: ${{r.vip?'VIP':'THƯỜNG'}}<br>Hạn dùng đang đếm ngược...`, "success");
            let expTime = r.exp;
            if(expTime !== 'permanent') {{
                setInterval(()=>{{
                    let el = document.getElementById('lvt_cd');
                    if(el) {{
                        let rem = expTime - Date.now();
                        if(rem<=0) {{ el.innerHTML="HẾT HẠN"; GM_setValue('lvt_key',''); location.reload(); }}
                        else {{
                            let d=Math.floor(rem/86400000), h=Math.floor((rem%86400000)/3600000), m=Math.floor((rem%3600000)/60000), s=Math.floor((rem%60000)/1000);
                            el.innerHTML = `Còn: ${{d}}d ${{h}}h ${{m}}m ${{s}}s`;
                        }}
                    }}
                }}, 1000);
            }}
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
    ban = data.get("banned_until", 0)
    if ban == "permanent" or (isinstance(ban, int) and ban > now): return "BANNED"
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
            my_keys.append({"key": k, "exp": exp_str, "exp_ms": v["exp"], "olm": v.get("bound_olm",""), "status": v.get("status"), "devs": len(v.get("devices",[])), "vip": v.get("vip")})
    return jsonify({"status": "success", "keys": my_keys})

@app.route('/telegram_mini_app')
def telegram_mini_app():
    db = load_db()
    mnt = db.get("settings", {}).get("maintenance_until", 0)
    now = int(time.time()*1000)
    is_mnt = "true" if (isinstance(mnt, int) and mnt > now) else "false"
    mnt_time = mnt if is_mnt == "true" else 0
    admin_notice = escape(db.get("settings", {}).get("global_notice", ""))
    
    html = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Xác Thực LVT</title>
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@500;700;900&display=swap');
            body {{ background: #12141d; color: #fff; font-family: 'Roboto', sans-serif; margin: 0; padding: 0; height: 100vh; display: flex; flex-direction: column; }}
            .screen {{ display: none; width: 100%; height: 100%; padding: 20px; box-sizing: border-box; }} .screen.active {{ display: block; }}
            .title-top {{ text-align: center; color: #00e5ff; font-size: 16px; font-weight: 900; margin-top: 30px; margin-bottom: 20px; letter-spacing: 1px; }}
            .inp {{ width: 100%; box-sizing: border-box; background: #1a1c26; border: 1px solid #2a2d3d; color: #8892b0; padding: 16px; border-radius: 6px; font-size: 14px; margin-bottom: 15px; outline: none; }}
            .inp::placeholder {{ color: #4a4d5d; }}
            .btn-blue {{ background: #00bfff; border: none; width: 100%; padding: 16px; border-radius: 6px; color: #000; font-weight: 900; font-size: 14px; cursor: pointer; }}
            
            .card {{ background: #1a1c26; border: 1px solid #2a2d3d; padding: 15px; border-radius: 12px; margin-bottom: 10px; }}
            .nav {{ display: flex; gap: 5px; margin-bottom: 20px; }}
            .nav-btn {{ flex: 1; padding: 12px; background: #1a1c26; text-align: center; border-radius: 8px; color: #8892b0; border: 1px solid #2a2d3d; font-size: 14px; font-weight: 700; }}
            .nav-btn.act {{ background: #00bfff; color: #000; border-color: #00bfff; }}
            #welc {{ position:fixed; inset:0; background:rgba(18,20,29,0.95); z-index:99; display:none; align-items:center; justify-content:center; flex-direction:column; padding:20px; text-align:center; }}
            #mnt-overlay {{ position:fixed; inset:0; background:rgba(18,20,29,0.98); z-index:999; display:none; align-items:center; justify-content:center; flex-direction:column; padding:20px; text-align:center; color:#ff3366; }}
            #ban-overlay {{ position:fixed; inset:0; background:rgba(255,0,0,0.95); z-index:1000; display:none; align-items:center; justify-content:center; flex-direction:column; padding:20px; text-align:center; color:#fff; }}
        </style>
    </head>
    <body>
        <div id="mnt-overlay">
            <h1 style="margin:0;font-size:40px;">⚠️</h1>
            <h2>HỆ THỐNG BẢO TRÌ</h2>
            <p id="mnt-cd" style="font-size:20px; font-weight:bold; color:#00e5ff;"></p>
        </div>
        <div id="ban-overlay">
            <h1 style="margin:0;font-size:50px;">⛔</h1>
            <h2>TÀI KHOẢN BỊ KHÓA</h2>
            <p id="ban-cd" style="font-size:18px; font-weight:bold;"></p>
        </div>
        <div id="welc">
            <h2 style="color:#00e5ff;">CHÀO MỪNG QUÝ KHÁCH</h2>
            <p style="color:#8892b0; line-height:1.6;">Chào mừng quý khách trải nghiệm dịch vụ của tôi chúc bạn sử dụng vui vẻ nhé có thắc mắc gì bạn hãy liên hệ admin tele : luongtuyen20</p>
            <p style="color:#fff; font-weight:bold; margin-top:20px;">{admin_notice}</p>
            <button class="btn-blue" onclick="hideW('2h')" style="margin-top:20px; background:#22c55e; color:#fff;">Ẩn 2 Giờ</button>
            <button class="btn-blue" style="background:#ef4444; color:#fff; margin-top:10px;" onclick="hideW('forever')">Đóng vĩnh viễn</button>
        </div>
        
        <div id="scr-auth" class="screen active">
            <div class="title-top">XÁC THỰC ID TELEGRAM</div>
            <input type="text" id="tg_id_inp" class="inp" placeholder="Nhập ID Telegram được cấp phép...">
            <button class="btn-blue" onclick="auth()">XÁC NHẬN</button>
        </div>
        
        <div id="scr-dash" class="screen">
            <div class="nav">
                <div class="nav-btn act" onclick="switchT('act')">KÍCH HOẠT</div>
                <div class="nav-btn" onclick="switchT('mgr')">QUẢN LÝ</div>
                <div class="nav-btn" onclick="switchT('scr')">SCRIPT</div>
            </div>
            <div id="tab-act" style="display:block;">
                <input type="text" id="k_inp" class="inp" placeholder="Nhập Key...">
                <input type="text" id="o_inp" class="inp" placeholder="Nhập Tài Khoản OLM Chỉ Định...">
                <button class="btn-blue" onclick="actKey()">KÍCH HOẠT KEY</button>
            </div>
            <div id="tab-mgr" style="display:none;">
                <h4 style="color:#00e5ff; margin-top:0; margin-bottom:15px; font-size:14px;">DANH SÁCH KEY CỦA TÔI</h4>
                <div id="k_list"></div>
            </div>
            <div id="tab-scr" style="display:none;">
                <div class="card">
                    <h4 style="color:#00e5ff;margin-top:0;font-size:14px;">VIOLENTMONKEY LOADER</h4>
                    <p style="font-size:12px;color:#8892b0;">Auto kết nối. Copy đoạn code dưới dán vào Violentmonkey.</p>
                    <textarea class="inp" rows="8" readonly style="font-family:monospace;font-size:11px;color:#00ffcc;background:#0d0e14;">// ==UserScript==
// @name LVT LOADER
// @match *://olm.vn/*
// @match *://*.olm.vn/*
// @grant GM_xmlhttpRequest
// ==/UserScript==
(function(){{GM_xmlhttpRequest({{method:'GET',url:'{WEB_URL}/api/script/olm_vip.user.js?t='+Date.now(),onload:r=>{{try{{eval(r.responseText)}}catch(e){{}}}}}})}})();</textarea>
                </div>
            </div>
        </div>
        <script>
            let tgId = localStorage.getItem('lvt_tg_id');
            let isMnt = {is_mnt}; let mntTime = {mnt_time}; let notice = "{admin_notice}";
            let checkBanInterval, checkMntInterval;
            
            if(isMnt) {{
                document.getElementById('mnt-overlay').style.display='flex';
                setInterval(()=>{{
                    let rem = mntTime - Date.now();
                    if(rem<=0) location.reload();
                    else {{
                        let d=Math.floor(rem/86400000), h=Math.floor((rem%86400000)/3600000), m=Math.floor((rem%3600000)/60000), s=Math.floor((rem%60000)/1000);
                        document.getElementById('mnt-cd').innerHTML = `Đếm ngược: ${{d}}d ${{h}}h ${{m}}m ${{s}}s`;
                    }}
                }}, 1000);
            }}
            
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
            
            function startBanCheck() {{
                if(checkBanInterval) clearInterval(checkBanInterval);
                checkBanInterval = setInterval(()=>{{
                    api('/api/tg/auth_check', {{tg_id: tgId}}, r => {{
                        if(r.status==='banned') {{
                            document.getElementById('ban-overlay').style.display='flex';
                            let b_cd = document.getElementById('ban-cd');
                            if(r.banned_until === 'permanent') b_cd.innerHTML = 'VĨNH VIỄN';
                            else {{
                                let rem = r.banned_until - Date.now();
                                if(rem<=0) location.reload();
                                else {{
                                    let d=Math.floor(rem/86400000), h=Math.floor((rem%86400000)/3600000), m=Math.floor((rem%3600000)/60000), s=Math.floor((rem%60000)/1000);
                                    b_cd.innerHTML = `Còn: ${{d}}d ${{h}}h ${{m}}m ${{s}}s`;
                                }}
                            }}
                        }} else if(r.status==='error') {{
                            localStorage.removeItem('lvt_tg_id'); location.reload();
                        }} else {{ document.getElementById('ban-overlay').style.display='none'; }}
                    }});
                }}, 3000);
            }}

            function auth() {{
                let id = document.getElementById('tg_id_inp').value || tgId;
                if(!id) return;
                api('/api/tg/auth_check', {{tg_id: id}}, r => {{
                    if(r.status==='ok') {{
                        tgId = id; localStorage.setItem('lvt_tg_id', id);
                        document.getElementById('scr-auth').classList.remove('active');
                        document.getElementById('scr-dash').classList.add('active');
                        chkW(); loadK(); startBanCheck();
                    }} else if(r.status==='banned') {{
                        Swal.fire('Lỗi', 'ID BỊ CẤM', 'error');
                    }} else Swal.fire('Lỗi', 'ID không có quyền truy cập!', 'error');
                }});
            }}
            if(tgId && !isMnt) auth();
            
            function switchT(t) {{
                ['act','mgr','scr'].forEach(x=>{{ 
                    document.getElementById('tab-'+x).style.display='none'; 
                    document.querySelector('.nav-btn:nth-child('+({'act':1,'mgr':2,'scr':3}[x])+')').classList.remove('act');
                }});
                document.getElementById('tab-'+t).style.display='block';
                document.querySelector('.nav-btn:nth-child('+({'act':1,'mgr':2,'scr':3}[t])+')').classList.add('act');
                if(t==='mgr') loadK();
            }}
            
            function actKey() {{
                let k = document.getElementById('k_inp').value, o = document.getElementById('o_inp').value;
                if(!k||!o) return Swal.fire('Lỗi','Nhập đủ thông tin','error');
                api('/api/tg/activate_key', {{tg_id:tgId, key:k, olm:o}}, r => {{
                    if(r.status==='success') Swal.fire('Thành công', `Xác thực thành công!<br>Key: ${{r.vip?'VIP':'THƯỜNG'}}`, 'success');
                    else Swal.fire('Lỗi', r.msg, 'error');
                }});
            }}
            
            function loadK() {{
                api('/api/tg/my_keys', {{tg_id:tgId}}, r => {{
                    if(r.status==='success') {{
                        let h = '';
                        r.keys.forEach(k=>{{
                            let sColor = k.status==='active' ? '#22c55e' : '#ef4444';
                            let sText = k.status==='active' ? 'Hoạt động' : 'Bị khóa';
                            let cdId = 'cd_' + k.key;
                            h+=`<div class="card" style="font-size:13px; line-height:1.6;">
                            <div style="display:flex;justify-content:space-between;border-bottom:1px dashed #2a2d3d;padding-bottom:8px;margin-bottom:8px;">
                                <b style="color:#00bfff;">${{k.key.substring(0,10)}}...</b>
                                <b style="color:${{k.vip?'#bd00ff':'#ffcc00'}}">${{k.vip?'VIP':'THƯỜNG'}}</b>
                            </div>
                            <div style="color:#8892b0;">Tài khoản chỉ định: <span style="color:#fff;">${{k.olm}}</span></div>
                            <div style="color:#8892b0;">Thiết bị: <span style="color:#fff;">${{k.devs}}</span></div>
                            <div style="color:#8892b0;">Trạng thái: <span style="color:${{sColor}};font-weight:bold;">${{sText}}</span></div>
                            <div style="color:#8892b0; margin-top:5px;">Hạn: <span id="${{cdId}}" style="color:#00ffcc;font-weight:bold;">${{k.exp}}</span></div>
                            </div>`;
                            
                            if(k.exp_ms !== 'permanent' && k.exp_ms !== 'pending' && k.status === 'active') {{
                                setInterval(()=>{{
                                    let el = document.getElementById(cdId);
                                    if(el) {{
                                        let rem = k.exp_ms - Date.now();
                                        if(rem<=0) el.innerHTML = "HẾT HẠN";
                                        else {{
                                            let d=Math.floor(rem/86400000), hr=Math.floor((rem%86400000)/3600000), m=Math.floor((rem%3600000)/60000), s=Math.floor((rem%60000)/1000);
                                            el.innerHTML = `${{d}}d ${{hr}}h ${{m}}m ${{s}}s`;
                                        }}
                                    }}
                                }}, 1000);
                            }}
                        }});
                        document.getElementById('k_list').innerHTML = h || '<div style="color:#8892b0;text-align:center;">Chưa có key nào.</div>';
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
    try:
        ip = get_real_ip()
        global admin_login_attempts
        now = time.time()
        admin_login_attempts = {k: v for k, v in admin_login_attempts.items() if now - v['time'] < 300} 
        attempts = admin_login_attempts.get(ip, {'count': 0, 'time': now})
        if attempts['count'] >= 5: return swal_back("Khóa", "Thử lại sau 5 phút!", "error")
        if request.method == 'POST':
            db = load_db()
            u = request.form.get('username', '').strip().lower()
            p = request.form.get('password', '').strip()
            ud = db.get("users", {}).get(u)
            if ud and ud.get("role") == "admin" and ud.get("password_hash") == hash_pwd(p):
                session['username'] = u
                session['role'] = 'admin'
                admin_login_attempts.pop(ip, None) 
                with db_lock: log_admin_action(db, f"Admin Login: {ip}")
                save_db(db)
                return redirect('/admin')
            attempts['count'] += 1
            attempts['time'] = now
            admin_login_attempts[ip] = attempts
            return swal_back("Lỗi", f"Sai thông tin! Còn {5 - attempts['count']} lần.", "error")
        return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><title>Admin Login</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>{CSS_GLASS}</style></head><body><div class="glass-panel"><h2 class="text-neon mb-4">🔐 QUẢN TRỊ VIÊN</h2><form method="POST"><input type="text" name="username" class="form-control" placeholder="Tên Admin" required><input type="password" name="password" class="form-control mt-2" placeholder="Mật Khẩu" required><button type="submit" class="btn-neon mt-3">VÀO HỆ THỐNG</button></form></div></body></html>'''
    except: return "LỖI", 200

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    with db_lock:
        keys_items = list(db.get("keys", {}).items())
        users_items = list(db.get("users", {}).items())
        banned_ips = list(db.get("banned_ips", []))
        tg_auths = list(db.get("tg_auth_ids", {}).items())

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
    
    tg_admin_rows = ""
    for tid, tdata in tg_auths:
        exp_ms = tdata.get("exp")
        ban_ms = tdata.get("banned_until", 0)
        exp_str = "Vĩnh viễn" if exp_ms == "permanent" else time.strftime("%d/%m %H:%M", time.localtime(exp_ms/1000))
        st_str = "<span class='text-danger'>Banned</span>" if (ban_ms == "permanent" or ban_ms > now_ms) else "<span class='text-success'>Live</span>"
        tg_admin_rows += f'<li class="list-group-item bg-transparent text-light border-secondary border-bottom p-2" style="font-size:12px;"><div class="d-flex justify-content-between align-items-center mb-1"><strong class="text-info">{escape(tid)}</strong> {st_str}</div><div class="d-flex justify-content-between align-items-center mb-1"><span class="text-muted">HSD: {exp_str}</span></div><div class="d-flex justify-content-between gap-1"><button class="btn btn-sm btn-outline-info flex-grow-1 p-0" style="font-size:10px;" onclick="addTgTime(\'{escape(tid)}\')">+ Giờ</button><button class="btn btn-sm btn-outline-warning flex-grow-1 p-0" style="font-size:10px;" onclick="banTgTime(\'{escape(tid)}\')">Ban</button><a href="/admin/tg_del/{escape(tid)}" class="btn btn-sm btn-outline-danger flex-grow-1 p-0" style="font-size:10px;">Xóa</a></div></li>'
        
    safe_vm_script = escape(db.get("settings", {}).get("violentmonkey_script", DEFAULT_OLM_SCRIPT))

    return f'''
    <!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ADMIN DASHBOARD</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>{CSS_GLASS} h5{{font-weight:900;}} .table-container{{max-height:450px;overflow-y:auto;}}</style></head><body class="p-2 p-md-4">
    <div class="container-fluid">
        <div class="d-flex justify-content-between align-items-center mb-4 border-bottom border-secondary pb-3">
            <h3 class="m-0 text-neon fw-bold"><i class="fas fa-shield-alt"></i> LVT SECURE ADMIN</h3>
            <div><button class="btn btn-warning btn-sm fw-bold rounded-pill px-3 me-2" data-bs-toggle="modal" data-bs-target="#sysModal">⚙️ HỆ THỐNG GLOBAL</button><button class="btn btn-info btn-sm fw-bold rounded-pill px-3 me-2" data-bs-toggle="modal" data-bs-target="#vmScriptModal">📜 CODE SCRIPT LÕI</button><a href="/logout" class="btn btn-outline-danger btn-sm fw-bold rounded-pill px-3">Thoát</a></div>
        </div>
        <div class="row g-4">
            <div class="col-lg-7">
                <div class="card p-4 h-100" style="border-color:rgba(51,102,255,0.4);">
                    <h5 style="color:#3366ff; margin-bottom:20px;"><i class="fas fa-users"></i> DANH SÁCH USER (CŨ)</h5>
                    <div class="table-container table-responsive"><table class="table table-dark table-hover table-sm align-middle mb-0 text-center text-nowrap"><thead class="table-active"><tr><th>Tài Khoản</th><th>Số Dư</th><th>Keys Sỡ Hữu</th><th>IP Đăng Nhập</th><th>Cộng/Trừ Tiền</th></tr></thead><tbody>{users_html}</tbody></table></div>
                </div>
            </div>
            <div class="col-lg-5">
                <div class="row g-4 h-100">
                    <div class="col-md-12">
                        <div class="card p-4 h-100" style="border-color:rgba(0,255,204,0.4);">
                            <h5 style="color:#00ffcc; margin-bottom:15px;"><i class="fab fa-telegram"></i> QUẢN LÝ ID TELEGRAM MINI APP</h5>
                            <form action="/admin/tg_add" method="POST" class="d-flex gap-1 mb-3">
                                <input type="text" name="tg_id" class="form-control form-control-sm m-0" placeholder="ID Tele..." required>
                                <input type="number" name="time_val" class="form-control form-control-sm m-0" placeholder="Hạn">
                                <select name="time_unit" class="form-select form-select-sm m-0"><option value="minutes">Phút</option><option value="hours">Giờ</option><option value="days">Ngày</option><option value="months">Tháng</option><option value="permanent">V.Viễn</option></select>
                                <button type="submit" class="btn btn-sm btn-info fw-bold px-3 rounded-pill text-dark">Thêm</button>
                            </form>
                            <ul class="list-group list-group-flush" style="max-height:150px;overflow-y:auto; border: 1px solid rgba(255,255,255,0.05); border-radius:8px;">{tg_admin_rows}</ul>
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
    <div class="modal fade" id="vmScriptModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-lg modal-dialog-centered"><div class="modal-content" style="background:rgba(17,17,26,0.95); border:1px solid #00ffcc; backdrop-filter: blur(15px);"><form action="/admin/update_vm_script" method="POST"><div class="modal-header border-secondary"><h5 class="modal-title" style="color:#00ffcc;font-weight:bold;">CẬP NHẬT CODE SCRIPT GỐC MỚI</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body p-4"><p class="text-warning mb-2" style="font-size:13px;">Dán toàn bộ Code Violentmonkey mới vào đây.</p><textarea name="vm_script_content" class="form-control" rows="15" style="font-family:monospace; font-size:12px;">{safe_vm_script}</textarea></div><div class="modal-footer border-secondary p-3"><button type="submit" class="btn btn-info fw-bold w-100 text-dark rounded-pill">LƯU & XUẤT BẢN CODE MỚI</button></div></form></div></div></div>
    
    <div class="modal fade" id="sysModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-dialog-centered"><div class="modal-content" style="background:rgba(17,17,26,0.95); border:1px solid #ffcc00; backdrop-filter: blur(15px);"><div class="modal-header border-secondary"><h5 class="modal-title" style="color:#ffcc00;font-weight:bold;">HỆ THỐNG GLOBAL</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body p-4"><form action="/admin/system" method="POST" class="mb-4"><h6>🔔 Thông báo toàn bộ User</h6><textarea name="global_notice" class="form-control mb-2" rows="2" placeholder="Nhập nội dung..."></textarea><button class="btn btn-warning btn-sm w-100 fw-bold">GỬI THÔNG BÁO</button></form><hr class="border-secondary"><form action="/admin/maintenance" method="POST"><h6>⚠️ Bảo trì hệ thống</h6><div class="d-flex gap-2 mb-2"><input type="number" name="duration" class="form-control" placeholder="Thời gian (0 = Tắt)"><select name="unit" class="form-select"><option value="m">Phút</option><option value="h" selected>Giờ</option><option value="d">Ngày</option></select></div><button class="btn btn-danger btn-sm w-100 fw-bold">CẬP NHẬT BẢO TRÌ</button></form></div></div></div></div>

    <div class="modal fade" id="tgTimeModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:rgba(17,17,26,0.95);border:1px solid #00ffcc;"><form action="/admin/tg_add" method="POST"><div class="modal-body text-center p-4"><input type="hidden" name="tg_id" id="tgTimeIdInput"><p class="text-white mb-2">Thêm thời gian cho ID:</p><h6 id="tgTimeIdDisplay" class="text-info mb-3"></h6><input type="number" name="time_val" class="form-control mb-2" placeholder="Giá trị" required><select name="time_unit" class="form-select"><option value="minutes">Phút</option><option value="hours">Giờ</option><option value="days" selected>Ngày</option><option value="months">Tháng</option></select></div><div class="modal-footer p-2"><button type="submit" class="btn btn-info w-100 fw-bold rounded-pill">CỘNG THÊM</button></div></form></div></div></div>
    <div class="modal fade" id="tgBanModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:rgba(17,17,26,0.95);border:1px solid #ffcc00;"><form action="/admin/tg_ban" method="POST"><div class="modal-body text-center p-4"><input type="hidden" name="tg_id" id="tgBanIdInput"><p class="text-white mb-2">Band tạm thời ID:</p><h6 id="tgBanIdDisplay" class="text-warning mb-3"></h6><input type="number" name="ban_val" class="form-control mb-2" placeholder="Thời gian ban"><select name="ban_unit" class="form-select"><option value="minutes">Phút</option><option value="hours" selected>Giờ</option><option value="days">Ngày</option><option value="months">Tháng</option><option value="permanent">Vĩnh Viễn</option></select></div><div class="modal-footer p-2"><button type="submit" class="btn btn-warning w-100 fw-bold rounded-pill">THỰC THI</button></div></form></div></div></div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function copyKey(t){{ navigator.clipboard.writeText(t); Swal.fire({{toast:true,position:'top-end',icon:'success',title:'Đã Copy!',showConfirmButton:false,timer:1000,background:'#111',color:'#00ffcc'}}); }}
        function openBindModal(key, current_olm) {{ document.getElementById('bindKeyInput').value = key; document.getElementById('bindKeyDisplay').innerText = key; document.getElementById('bindOlmInput').value = current_olm; new bootstrap.Modal(document.getElementById('bindModal')).show(); }}
        function openAddTimeModal(key) {{ document.getElementById('addTimeKeyInput').value = key; document.getElementById('addTimeKeyDisplay').innerText = key; new bootstrap.Modal(document.getElementById('addTimeModal')).show(); }}
        function addTgTime(id) {{ document.getElementById('tgTimeIdInput').value = id; document.getElementById('tgTimeIdDisplay').innerText = id; new bootstrap.Modal(document.getElementById('tgTimeModal')).show(); }}
        function banTgTime(id) {{ document.getElementById('tgBanIdInput').value = id; document.getElementById('tgBanIdDisplay').innerText = id; new bootstrap.Modal(document.getElementById('tgBanModal')).show(); }}
    </script>
    </body></html>
    '''

@app.route('/admin/add_balance', methods=['POST'])
def add_balance():
    if session.get('role') != 'admin': return redirect('/admin_login')
    username = request.form.get('username')
    amt = safe_int(request.form.get('amount'))
    db = load_db()
    with db_lock:
        if username in db.get("users", {}):
            db["users"][username]["balance"] += amt
            if db["users"][username]["balance"] < 0: db["users"][username]["balance"] = 0
            save_db(db)
    return redirect('/admin')

@app.route('/admin/create', methods=['POST'])
def create_key():
    if session.get('role') != 'admin': return redirect('/admin_login')
    dur = safe_int(request.form.get('duration'))
    qty = safe_int(request.form.get('quantity'), 1)
    t = request.form.get('type')
    vip = request.form.get('is_vip') == 'on'
    pfx = request.form.get('prefix', '').strip()
    db = load_db()
    with db_lock:
        for _ in range(qty):
            nk = generate_secure_key(pfx, vip)
            db["keys"][nk] = {"exp": "pending", "maxDevices": 1, "devices": [], "known_ips": {}, "status": "active", "vip": vip, "loader_enabled": True, "violations": 0, "temp_ban_until": 0, "owner": "admin", "reset_count": 0, "bound_olm": "", "activated": False}
            if t != 'permanent': db["keys"][nk]["durationMs"] = dur * {"hour":3600000, "day":86400000, "month":2592000000}.get(t, 60000)
            else: db["keys"][nk]["exp"] = "permanent"
        save_db(db)
    return redirect('/admin')

@app.route('/admin/add_time', methods=['POST'])
def admin_add_time():
    if session.get('role') != 'admin': return redirect('/admin_login')
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
            if kd.get("exp") == "permanent": return swal_back("Lỗi", "Key vĩnh viễn!", "error")
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
    if session.get('role') != 'admin': return redirect('/admin_login')
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
    if session.get('role') != 'admin': return redirect('/admin_login')
    ns = request.form.get('vm_script_content', '')
    if not ns.strip().startswith('// ==UserScript=='): return swal_back("Lỗi", "Script không hợp lệ", "error")
    db = load_db()
    with db_lock:
        db.setdefault("settings", {})["violentmonkey_script"] = ns
        save_db(db)
    return swal_redirect("Thành công", "Đã cập nhật", "success", "/admin")

@app.route('/admin/system', methods=['POST'])
def admin_system():
    if session.get('role') != 'admin': return redirect('/admin_login')
    msg = request.form.get('global_notice', '').strip()
    db = load_db()
    with db_lock:
        db.setdefault("settings", {})["global_notice"] = msg
        save_db(db)
    return redirect('/admin')

@app.route('/admin/maintenance', methods=['POST'])
def admin_maintenance():
    if session.get('role') != 'admin': return redirect('/admin_login')
    dur = safe_int(request.form.get('duration', 0))
    unit = request.form.get('unit', 'h')
    db = load_db()
    with db_lock:
        if dur <= 0: db.setdefault("settings", {})["maintenance_until"] = 0
        else:
            mult = {"m": 60000, "h": 3600000, "d": 86400000}.get(unit, 3600000)
            db.setdefault("settings", {})["maintenance_until"] = int(time.time() * 1000) + (dur * mult)
        save_db(db)
    return redirect('/admin')

@app.route('/admin/ban_ip', methods=['POST'])
def web_ban_ip():
    if session.get('role') != 'admin': return redirect('/admin_login')
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
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    with db_lock:
        if ip in db.setdefault("banned_ips", []):
            db["banned_ips"].remove(ip)
            save_db(db)
    return redirect('/admin')

@app.route('/admin/action/<action>/<key>')
def key_actions(action, key):
    if session.get('role') != 'admin': return redirect('/admin_login')
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
            elif action == 'reset-dev':
                kd['devices'] = []
                kd['known_ips'] = {}
            save_db(db)
    return redirect('/admin')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/admin_login')

@app.route('/admin/tg_add', methods=['POST'])
def admin_tg_add():
    if session.get('role') != 'admin': return redirect('/admin_login')
    tid = request.form.get("tg_id", "").strip()
    tv = safe_int(request.form.get("time_val"))
    tu = request.form.get("time_unit")
    if not tid: return redirect('/admin')
    db = load_db()
    with db_lock:
        auths = db.setdefault("tg_auth_ids", {})
        if tid not in auths: auths[tid] = {"exp": 0, "banned_until": 0}
        
        if tu == "permanent": auths[tid]["exp"] = "permanent"
        elif tv > 0:
            mult = {"minutes": 60000, "hours": 3600000, "days": 86400000, "months": 2592000000}.get(tu, 86400000)
            ms_to_add = tv * mult
            now = int(time.time()*1000)
            if auths[tid]["exp"] == "permanent": pass
            else:
                curr_exp = max(auths[tid].get("exp", now), now)
                auths[tid]["exp"] = curr_exp + ms_to_add
        save_db(db)
    return redirect('/admin')

@app.route('/admin/tg_ban', methods=['POST'])
def admin_tg_ban():
    if session.get('role') != 'admin': return redirect('/admin_login')
    tid = request.form.get("tg_id", "").strip()
    tv = safe_int(request.form.get("ban_val"))
    tu = request.form.get("ban_unit")
    db = load_db()
    with db_lock:
        if tid in db.setdefault("tg_auth_ids", {}):
            if tu == "permanent": db["tg_auth_ids"][tid]["banned_until"] = "permanent"
            elif tv > 0:
                mult = {"minutes": 60000, "hours": 3600000, "days": 86400000, "months": 2592000000}.get(tu, 3600000)
                db["tg_auth_ids"][tid]["banned_until"] = int(time.time()*1000) + (tv * mult)
            save_db(db)
    return redirect('/admin')

@app.route('/admin/tg_del/<tid>')
def admin_tg_del(tid):
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    with db_lock:
        if tid in db.setdefault("tg_auth_ids", {}):
            del db["tg_auth_ids"][tid]
            save_db(db)
    return redirect('/admin')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
