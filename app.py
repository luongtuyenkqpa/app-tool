import os, json, time, random, hashlib, threading, requests, shutil, base64, secrets, hmac, string, copy, traceback
import urllib.parse
from html import escape
from flask import Flask, request, jsonify, redirect, make_response, session, abort
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

# [VÁ LỖI LỆCH MÚI GIỜ CLOUD]
try:
    os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
    time.tzset()
except: pass

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

CSS_GLASS = """
.glass-panel { background: rgba(17, 17, 26, 0.7); backdrop-filter: blur(15px); border: 1px solid rgba(0, 255, 204, 0.3); border-radius: 15px; padding: 30px; box-shadow: 0 0 20px rgba(0, 255, 204, 0.2); max-width: 400px; margin: 50px auto; text-align: center; }
.text-neon { color: #00ffcc; text-shadow: 0 0 10px rgba(0, 255, 204, 0.5); }
.btn-neon { background: linear-gradient(90deg, #00ffcc, #0099ff); border: none; color: #000; font-weight: bold; padding: 10px 20px; border-radius: 8px; width: 100%; transition: 0.3s; }
.btn-neon:hover { transform: scale(1.05); box-shadow: 0 0 15px rgba(0, 255, 204, 0.5); }
"""

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8714375866:AAG9r0aCCFOKtgR6B-LcFYBAnJ7x9yMs-8o")
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
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"📦 BACKUP DATABASE PROXY\nThời gian: {time.strftime('%d/%m/%Y %H:%M:%S')}"}, files={"document": f}, timeout=10)
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
                            welcome = f"🌟 <b>HỆ THỐNG PROXY OLM TỰ ĐỘNG</b> 🌟\n\nXin chào <b>{user_first_name}</b>!\nNhấn vào nút bên dưới để Đăng nhập và Lấy cấu hình Proxy:"
                            keyboard = {"inline_keyboard": [
                                [{"text": "🛒 MỞ WEB KÍCH HOẠT PROXY", "web_app": {"url": f"{WEB_URL}/telegram_mini_app"}}]
                            ]}
                            requests.post(url_base + "/sendMessage", json={"chat_id": chat_id, "text": welcome, "parse_mode": "HTML", "reply_markup": keyboard})
        except Exception: pass
        time.sleep(2)

threading.Thread(target=telegram_polling, daemon=True).start()

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException): return e
    error_detail = traceback.format_exc()
    send_telegram_alert(f"<b>CRITICAL CRASH NGĂN CHẶN THÀNH CÔNG:</b>\n<pre>{error_detail[-300:]}</pre>")
    return "Hệ thống đang bảo trì.", 500

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
    return f"""<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #05050A; }}</style></head><body><script>Swal.fire({{ title: `{title}`, html: `{text}`, icon: '{icon}', background: '#11111A', color: '#fff', confirmButtonColor: '#00ffcc', allowOutsideClick: false, customClass: {{ popup: 'border border-info' }} }}).then(() => {{ window.location.href = '{url}'; }});</script></body></html>"""

def swal_back(title, text, icon):
    return f"""<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #05050A; }}</style></head><body><script>Swal.fire({{ title: `{title}`, html: `{text}`, icon: '{icon}', background: '#11111A', color: '#fff', confirmButtonColor: '#bd00ff', allowOutsideClick: false, customClass: {{ popup: 'border border-danger' }} }}).then(() => {{ window.history.back(); }});</script></body></html>"""

def render_template_string_safe(content):
    resp = make_response(content)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp

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
            if not data: data = {"users": {}, "keys": {}, "banned_ips": [], "admin_logs": [], "security_alerts": [], "settings": {}}
            try:
                data.setdefault("users", {})
                data.setdefault("keys", {})
                data.setdefault("banned_ips", [])
                data.setdefault("admin_logs", [])
                data.setdefault("security_alerts", []) 
                data.setdefault("settings", {})
                data.setdefault("tg_auth_ids", {str(TELEGRAM_CHAT_ID): {"exp": "permanent", "banned_until": 0}}) 
                
                if "secret_key" not in data["settings"]:
                    data["settings"]["secret_key"] = secrets.token_hex(32)

                if "maintenance_until" not in data["settings"]: data["settings"]["maintenance_until"] = 0
                if "global_notice" not in data["settings"]: data["settings"]["global_notice"] = ""
                if "tg_admins" not in data["settings"]: data["settings"]["tg_admins"] = [TELEGRAM_CHAT_ID]
                
                if "admin" not in data["users"]:
                    data["users"]["admin"] = {"password_hash": hash_pwd("120510@"), "role": "admin", "balance": 0, "created_at": int(time.time() * 1000), "ips": [], "banned_until": 0}

                for k in data["keys"]:
                    data["keys"][k].setdefault("owner", "admin")
                    data["keys"][k].setdefault("violations", 0)
                    data["keys"][k].setdefault("temp_ban_until", 0)
                    data["keys"][k].setdefault("devices", [])
                    data["keys"][k].setdefault("bound_olm", "") 
                    data["keys"][k].setdefault("vip", False)
                    data["keys"][k].setdefault("activated", False)
                    data["keys"][k].setdefault("tg_owner", "")
                    data["keys"][k].setdefault("proxy_host", "")
                    data["keys"][k].setdefault("proxy_port", 0)

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

# [NÂNG CẤP TẠO KEY] Auto gen 15 ký tự chữ thường
def generate_proxy_key():
    return ''.join(secrets.choice(string.ascii_lowercase) for _ in range(15))

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
                if len(used_signatures) > 10000:
                    expired_sigs = [s for s, t in used_signatures.items() if now_ms - t > 20000]
                    for s in expired_sigs: del used_signatures[s]
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
    return request.remote_addr or "Unknown_IP"

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
            return "Firewall Blocked Suspicious Bot/Scanner.", 403
            
        if request.path.startswith("/admin") and request.path not in ["/admin_login", "/telegram_mini_app"]:
            if session.get('role') != 'admin':
                return redirect('/admin_login')
            if request.method == 'POST':
                token = request.form.get("csrf_token")
                if not token or token != session.get('csrf_token'):
                    return "⚠️ BẢO MẬT LỚP 2: Lỗi xác thực CSRF Token. Vui lòng F5 lại trang!", 403
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

@app.route('/download-ca')
def download_ca():
    # Nội dung giả lập, bạn có thể đọc file CA.pem thật ở đây
    dummy_ca = "-----BEGIN CERTIFICATE-----\nMIIDzTCCArWgAwIBAgIQC... (Chứng chỉ mẫu)\n-----END CERTIFICATE-----"
    resp = make_response(dummy_ca)
    resp.headers['Content-Type'] = 'application/x-pem-file'
    resp.headers['Content-Disposition'] = 'attachment; filename="OLM_PROXY_CA.pem"'
    return resp

def is_tg_authorized(tg_id):
    db = load_db()
    auths = db.get("tg_auth_ids", {})
    allowed_admins = db.get("settings", {}).get("tg_admins", [TELEGRAM_CHAT_ID])
    if tg_id in allowed_admins or tg_id == str(TELEGRAM_CHAT_ID): return True
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
        allowed_admins = db.get("settings", {}).get("tg_admins", [TELEGRAM_CHAT_ID])
        is_admin = tg_id in allowed_admins or tg_id == str(TELEGRAM_CHAT_ID)
        exp = db["tg_auth_ids"][tg_id]["exp"] if tg_id in db.get("tg_auth_ids", {}) else "permanent"
        return jsonify({"status": "ok", "exp": exp, "banned": 0, "is_admin": is_admin})
    if status == "BANNED":
        db = load_db()
        return jsonify({"status": "banned", "banned_until": db["tg_auth_ids"][tg_id]["banned_until"]})
    return jsonify({"status": "error"})

@app.route('/api/tg/activate_proxy', methods=['POST'])
def tg_activate_proxy():
    data = request.json or {}
    tg_id = data.get("tg_id", "")
    key = data.get("key", "").strip()
    
    if is_tg_authorized(tg_id) != True: return jsonify({"status": "error", "msg": "ID Tele không hợp lệ!"})
    
    db = load_db()
    now = int(time.time() * 1000)
    with db_lock:
        if key not in db["keys"]: return jsonify({"status": "error", "msg": "Key không tồn tại!"})
        kd = db["keys"][key]
        
        if kd.get("status") == "banned": return jsonify({"status": "error", "msg": "Key đã bị Admin khóa vĩnh viễn!"})
        if kd.get("exp") != "permanent" and kd.get("exp") != "pending" and kd.get("exp", 0) < now:
            return jsonify({"status": "error", "msg": "Key đã hết hạn!"})

        if not kd.get("bound_olm"):
            return jsonify({"status": "error", "msg": "Lỗi: Key này chưa được Admin chỉ định tên tài khoản OLM. Hãy báo Admin ghim OLM trước!"})
        
        if not kd.get("proxy_host") or not kd.get("proxy_port"):
            return jsonify({"status": "error", "msg": "Admin chưa thiết lập Máy chủ và Cổng Proxy cho Key này!"})

        if not kd.get("activated"):
            kd["activated"] = True
            kd["tg_owner"] = tg_id
            if kd.get("exp") == "pending":
                kd["exp"] = now + kd.get("durationMs", 0)
            save_db(db)
            
    return jsonify({"status": "success", "msg": "Kích hoạt thành công!", "host": kd["proxy_host"], "port": kd["proxy_port"], "olm": kd["bound_olm"]})

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
            my_keys.append({"key": k, "exp": exp_str, "exp_ms": v["exp"], "olm": v.get("bound_olm",""), "host": v.get("proxy_host",""), "port": v.get("proxy_port",""), "status": v.get("status"), "devs": len(v.get("devices",[])), "vip": v.get("vip")})
    return jsonify({"status": "success", "keys": my_keys})

# ========================================================
# API C-PANEL TELEGRAM 
# ========================================================
def check_tg_admin_auth(req):
    tg_id = req.headers.get('X-Admin-ID', '')
    db = load_db()
    allowed = db.get("settings", {}).get("tg_admins", [TELEGRAM_CHAT_ID])
    return tg_id in allowed or tg_id == str(TELEGRAM_CHAT_ID)

@app.route('/api/tg_admin/create_keys', methods=['POST'])
def tg_admin_create_keys():
    if not check_tg_admin_auth(request): return jsonify({"status": "error", "msg": "Unauthorized"}), 403
    data = request.json or {}
    qty = safe_int(data.get('quantity'), 1)
    dur = safe_int(data.get('duration'), 1)
    unit = data.get('unit', 'day')
    dev = safe_int(data.get('devices'), 1)
    vip = data.get('is_vip', False)
    
    db = load_db()
    created = []
    with db_lock:
        for _ in range(qty):
            nk = generate_proxy_key()
            db.setdefault("keys", {})[nk] = {
                "exp": "pending", "maxDevices": dev, "devices": [], "known_ips": {},
                "status": "active", "vip": vip, "violations": 0, "temp_ban_until": 0, 
                "owner": "admin", "bound_olm": "", "activated": False, "tg_owner": "",
                "proxy_host": "", "proxy_port": 0
            }
            if unit != 'permanent': 
                db["keys"][nk]["durationMs"] = dur * {"minute":60000, "hour":3600000, "day":86400000, "month":2592000000}.get(unit, 60000)
            else: 
                db["keys"][nk]["exp"] = "permanent"
            created.append(nk)
        save_db(db)
    return jsonify({"status": "success", "keys": created})

@app.route('/api/tg_admin/setup_proxy', methods=['POST'])
def tg_admin_setup_proxy():
    if not check_tg_admin_auth(request): return jsonify({"status": "error"}), 403
    data = request.json or {}
    key = data.get("key", "").strip()
    host = data.get("host", "").strip()
    
    db = load_db()
    with db_lock:
        if key not in db.get("keys", {}):
            return jsonify({"status": "error", "msg": "Mã Key không tồn tại!"})
        if not db["keys"][key].get("bound_olm"):
            return jsonify({"status": "error", "msg": "Key này chưa được ghim tài khoản OLM. Hãy vào Quản Lý Kho Key ghim định danh trước!"})
        
        # Auto Random Cổng
        rand_port = random.randint(10000, 65000)
        db["keys"][key]["proxy_host"] = host
        db["keys"][key]["proxy_port"] = rand_port
        save_db(db)
        
    return jsonify({"status": "success", "msg": f"Đã ghim Host & Port thành công!\nMáy chủ: {host}\nCổng: {rand_port}"})

@app.route('/api/tg_admin/get_all_keys', methods=['POST'])
def tg_admin_get_keys():
    if not check_tg_admin_auth(request): return jsonify({"status": "error"}), 403
    db = load_db()
    now = int(time.time()*1000)
    keys_list = []
    for k, v in db.get("keys", {}).items():
        exp_str = "Vĩnh viễn" if v["exp"]=="permanent" else ("Chưa KH" if v["exp"]=="pending" else ("Hết hạn" if v["exp"]<now else time.strftime("%d/%m %H:%M", time.localtime(v["exp"]/1000))))
        keys_list.append({
            "key": k, "vip": v.get("vip", False), "status": v.get("status", "active"),
            "exp": exp_str, "exp_ms": v["exp"], "devs": len(v.get("devices", [])),
            "max_dev": v.get("maxDevices", 1), "olm": v.get("bound_olm", ""),
            "host": v.get("proxy_host", ""), "port": v.get("proxy_port", 0)
        })
    keys_list.sort(key=lambda x: x["exp_ms"] if isinstance(x["exp_ms"], int) else 9999999999999, reverse=True)
    return jsonify({"status": "success", "keys": keys_list})

@app.route('/api/tg_admin/action_key', methods=['POST'])
def tg_admin_action_key():
    if not check_tg_admin_auth(request): return jsonify({"status": "error"}), 403
    data = request.json or {}
    key = data.get("key", "")
    action = data.get("action", "")
    db = load_db()
    with db_lock:
        if key in db.get("keys", {}):
            kd = db["keys"][key]
            if action == 'ban': kd['status'] = 'banned'
            elif action == 'unban': kd['status'] = 'active'; kd['temp_ban_until'] = 0
            elif action == 'delete': del db["keys"][key]
            elif action == 'reset': kd['devices'] = []; kd['known_ips'] = {}; kd['activated'] = False
            save_db(db)
    return jsonify({"status": "success"})

@app.route('/api/tg_admin/add_time', methods=['POST'])
def tg_admin_add_time():
    if not check_tg_admin_auth(request): return jsonify({"status": "error"}), 403
    data = request.json or {}
    key = data.get("key", "")
    t_val = safe_int(data.get("val"), 0)
    t_unit = data.get("unit", "days")
    ms_to_add = t_val * {"minutes": 60000, "hours": 3600000, "days": 86400000, "months": 2592000000}.get(t_unit, 0)
    db = load_db()
    with db_lock:
        if key in db.get("keys", {}):
            kd = db["keys"][key]
            if kd.get("exp") != "permanent":
                if kd.get("exp") == "pending": kd["durationMs"] = kd.get("durationMs", 0) + ms_to_add
                else:
                    now = int(time.time() * 1000)
                    curr = max(kd.get("exp", now), now)
                    kd["exp"] = curr + ms_to_add
            save_db(db)
    return jsonify({"status": "success"})

@app.route('/api/tg_admin/bind_olm', methods=['POST'])
def tg_admin_bind_olm():
    if not check_tg_admin_auth(request): return jsonify({"status": "error"}), 403
    data = request.json or {}
    key = data.get("key", "")
    olm = data.get("olm_name", "")
    db = load_db()
    with db_lock:
        if key in db.get("keys", {}):
            db["keys"][key]["bound_olm"] = olm
            save_db(db)
    return jsonify({"status": "success"})

@app.route('/telegram_mini_app')
def telegram_mini_app():
    # Sửa lỗi ngoặc nhọn {} trong JS/CSS của Python String 
    # Bằng cách KHÔNG dùng f-string cho toàn bộ, chỉ dùng .replace()
    html_template = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Hệ Thống LVT Proxy</title>
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
            body { background: #0b0d14; color: #fff; font-family: 'Inter', sans-serif; margin: 0; padding: 0; height: 100vh; display: flex; flex-direction: column; overflow-x: hidden; }
            .screen { display: none; width: 100%; height: 100%; padding: 20px; box-sizing: border-box; overflow-y: auto; } .screen.active { display: block; }
            .title-top { text-align: center; color: #00ffcc; font-size: 18px; font-weight: 900; margin-top: 20px; margin-bottom: 25px; letter-spacing: 2px; text-transform: uppercase; text-shadow: 0 0 10px rgba(0,255,204,0.3); }
            .inp { width: 100%; box-sizing: border-box; background: rgba(26,28,38,0.8); border: 1px solid rgba(0,255,204,0.2); color: #00ffcc; padding: 15px; border-radius: 10px; font-size: 14px; margin-bottom: 15px; outline: none; font-weight:600; transition: 0.3s; }
            .inp:focus { border-color: #00ffcc; box-shadow: 0 0 10px rgba(0,255,204,0.1); }
            .btn-neon { background: linear-gradient(90deg, #00ffcc, #0099ff); border: none; width: 100%; padding: 15px; border-radius: 10px; color: #000; font-weight: 900; font-size: 14px; cursor: pointer; transition:0.2s; text-transform: uppercase; box-shadow: 0 5px 15px rgba(0,255,204,0.2); }
            .btn-neon:active { transform: scale(0.97); }
            .card { background: rgba(26,28,38,0.6); border: 1px solid rgba(255,255,255,0.05); padding: 16px; border-radius: 15px; margin-bottom: 15px; backdrop-filter: blur(10px); }
            .nav { display: flex; gap: 8px; margin-bottom: 20px; background: rgba(0,0,0,0.3); padding: 5px; border-radius: 12px; }
            .nav-btn { flex: 1; padding: 12px; text-align: center; border-radius: 10px; color: #8892b0; font-size: 13px; font-weight: 800; cursor: pointer; transition:0.3s; }
            .nav-btn.act { background: #00ffcc; color: #000; box-shadow: 0 0 15px rgba(0,255,204,0.3); }
            .header-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; }
            .btn-back { background: rgba(255,255,255,0.08); border: none; padding: 10px 18px; border-radius: 10px; color: #fff; font-weight: 600; cursor: pointer; }
            .select-btn { background: rgba(26,28,38,0.9); border: 1px solid rgba(255,255,255,0.05); border-radius: 14px; padding: 16px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; cursor: pointer; }
            .icon-box { width: 42px; height: 42px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0; }
            .swal2-popup { background: #1a1c26 !important; color: #fff !important; border: 1px solid #00ffcc !important; border-radius: 15px !important; }
            .swal2-input, .swal2-select { background: #0b0d14 !important; border: 1px solid #333 !important; color: #00ffcc !important; border-radius: 8px !important; }
            .action-btn { font-size:11px; font-weight:bold; padding:8px 12px; border-radius:6px; border:none; cursor:pointer; text-transform:uppercase; }
        </style>
    </head>
    <body>
        <div id="scr-auth" class="screen active">
            <div class="title-top"><i class="fas fa-fingerprint"></i> XÁC THỰC LVT PROXY</div>
            <input type="text" id="tg_id_inp" class="inp" placeholder="Nhập ID Telegram của bạn...">
            <button class="btn-neon" onclick="auth()"><i class="fas fa-sign-in-alt"></i> ĐĂNG NHẬP HỆ THỐNG</button>
        </div>
        
        <div id="scr-dash" class="screen">
            <div class="header-bar">
                <div style="font-weight:900; color:#00ffcc; background:rgba(0,255,204,0.1); padding:8px 15px; border-radius:20px; font-size:13px;">ID: <span id="display-id">...</span></div>
                <button id="btn-admin-panel" style="display:none; background:linear-gradient(90deg, #ffcc00, #ff6600); color:#000; border:none; padding:8px 18px; border-radius:20px; font-weight:900;" onclick="navTo('screen-admin-main')">C-PANEL</button>
            </div>
            <div class="nav">
                <div class="nav-btn act" onclick="switchT('act')">LẤY PROXY</div>
                <div class="nav-btn" onclick="switchT('mgr')">QUẢN LÝ</div>
            </div>
            
            <div id="tab-act" style="display:block;">
                <div class="card border-0" style="background:rgba(0,255,204,0.03);">
                    <p style="font-size:12px; color:#8892b0; margin-top:0;">Dán mã Key kích hoạt để lấy thông tin Proxy.</p>
                    <input type="text" id="k_inp" class="inp" placeholder="Dán mã Key bảo mật...">
                    <button class="btn-neon" onclick="actKey()"><i class="fas fa-bolt"></i> LẤY CẤU HÌNH PROXY</button>
                </div>
                
                <div class="card" id="proxy-result" style="display:none; border-color:#bd00ff;">
                    <h4 style="color:#bd00ff; margin-top:0;"><i class="fas fa-network-wired"></i> THÔNG TIN KẾT NỐI</h4>
                    <p style="font-size:13px; color:#ccc;">Tên máy chủ: <strong id="res-host" style="color:#00ffcc; user-select:all;"></strong></p>
                    <p style="font-size:13px; color:#ccc;">Cổng: <strong id="res-port" style="color:#00ffcc; user-select:all;"></strong></p>
                    <button class="btn-neon mt-3" style="background:linear-gradient(90deg, #a855f7, #6366f1);" onclick="window.location.href='/download-ca'"><i class="fas fa-download"></i> TẢI CHỨNG CHỈ BẢO MẬT</button>
                </div>
            </div>
            
            <div id="tab-mgr" style="display:none;">
                <h4 style="color:#00ffcc; margin-top:0; font-size:14px;"><i class="fas fa-wallet"></i> KHO PROXY CỦA TÔI</h4>
                <div id="k_list"></div>
            </div>
        </div>

        <div id="screen-admin-main" class="screen">
            <div class="header-bar">
                <button class="btn-back" onclick="navTo('scr-dash')"><i class="fas fa-arrow-left"></i> Quay lại</button>
                <div style="background:#ffcc00; color:#000; padding:6px 12px; border-radius:10px; font-weight:900; font-size:12px;">C-PANEL</div>
            </div>
            
            <div class="select-btn" onclick="navTo('screen-admin-keys')">
                <div class="select-btn-left" style="display:flex; align-items:center; gap:15px;">
                    <div class="icon-box" style="background:rgba(34, 197, 94, 0.15); color:#22c55e;"><i class="fas fa-magic"></i></div>
                    <div><div style="font-size:15px; font-weight:800; color:#fff;">Tạo Key Mới</div><div style="font-size:12px; color:#889;">Auto 15 ký tự thường</div></div>
                </div>
            </div>

            <div class="select-btn" onclick="navTo('screen-admin-setup-proxy')">
                <div class="select-btn-left" style="display:flex; align-items:center; gap:15px;">
                    <div class="icon-box" style="background:rgba(168, 85, 247, 0.15); color:#a855f7;"><i class="fas fa-network-wired"></i></div>
                    <div><div style="font-size:15px; font-weight:800; color:#fff;">Gán Host Proxy</div><div style="font-size:12px; color:#889;">Nhập Host & Random Port</div></div>
                </div>
            </div>
            
            <div class="select-btn" onclick="navTo('screen-admin-manage-keys'); loadAdminKeys();">
                <div class="select-btn-left" style="display:flex; align-items:center; gap:15px;">
                    <div class="icon-box" style="background:rgba(0, 153, 255, 0.15); color:#0099ff;"><i class="fas fa-tasks"></i></div>
                    <div><div style="font-size:15px; font-weight:800; color:#fff;">Quản Lý Kho Key</div><div style="font-size:12px; color:#889;">Ghim Định Danh, Bơm Giờ</div></div>
                </div>
            </div>
        </div>

        <div id="screen-admin-keys" class="screen">
            <button class="btn-back" onclick="navTo('screen-admin-main')"><i class="fas fa-arrow-left"></i> Trở về</button>
            <h3 style="margin-top:20px; color:#22c55e;"><i class="fas fa-key"></i> TẠO KEY BẢO MẬT</h3>
            <div class="card">
                <div style="display:flex; gap:10px;">
                    <input type="number" id="k-qty" class="inp" value="1" placeholder="Số lượng">
                    <input type="number" id="k-dur" class="inp" value="1" placeholder="Thời gian">
                </div>
                <div style="display:flex; gap:10px;">
                    <select id="k-unit" class="inp" style="background:#0b0d14;">
                        <option value="minute">Phút</option><option value="hour">Giờ</option><option value="day" selected>Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh Viễn</option>
                    </select>
                    <input type="number" id="k-dev" class="inp" value="1" placeholder="Số máy">
                </div>
                <div style="display:flex; align-items:center; gap:10px; margin-bottom:20px;">
                    <input type="checkbox" id="k-vip" style="width:20px; height:20px;">
                    <label for="k-vip" style="color:#ffcc00; font-weight:800;">Gắn mác VIP PRO</label>
                </div>
                <button class="btn-neon" style="background:#22c55e;" onclick="createKeys()"><i class="fas fa-cogs"></i> SẢN XUẤT KEY</button>
            </div>
        </div>

        <div id="screen-admin-setup-proxy" class="screen">
            <button class="btn-back" onclick="navTo('screen-admin-main')"><i class="fas fa-arrow-left"></i> Trở về</button>
            <h3 style="margin-top:20px; color:#a855f7;"><i class="fas fa-server"></i> GẮN SERVER PROXY</h3>
            <div class="card">
                <p style="font-size:12px; color:#ffcc00; margin-top:0;">⚠️ Phải vào Quản lý Key để ghim Tên OLM trước khi thiết lập Proxy.</p>
                <input type="text" id="p-key" class="inp" placeholder="Dán mã Key...">
                <input type="text" id="p-host" class="inp" placeholder="Tên máy chủ (VD: proxy1.lvt.com)">
                <button class="btn-neon" style="background:#a855f7;" onclick="setupProxy()"><i class="fas fa-save"></i> LƯU & RANDOM CỔNG</button>
            </div>
        </div>

        <div id="screen-admin-manage-keys" class="screen">
            <button class="btn-back" onclick="navTo('screen-admin-main')"><i class="fas fa-arrow-left"></i> Trở về</button>
            <h3 style="margin-top:20px; color:#0099ff;"><i class="fas fa-database"></i> TẤT CẢ KEY</h3>
            <input type="text" id="search-key-inp" class="inp" placeholder="🔍 Tìm key..." onkeyup="filterAdminKeys()">
            <div id="admin-key-list" style="margin-top:10px; padding-bottom:50px;"></div>
        </div>

        <script>
            let tgId = localStorage.getItem('lvt_tg_id');
            const Toast = Swal.mixin({ toast: true, position: 'top-end', showConfirmButton: false, timer: 2000, background: '#1a1c26', color: '#fff' });
            
            function api(path, body, cb) {
                let headers = {'Content-Type':'application/json'};
                if (tgId) headers['X-Admin-ID'] = tgId;
                fetch(path, {method:'POST', headers:headers, body:JSON.stringify(body)}).then(r=>r.json()).then(cb);
            }
            
            function auth() {
                let id = document.getElementById('tg_id_inp').value || tgId;
                if(!id) return;
                api('/api/tg/auth_check', {tg_id: id}, r => {
                    if(r.status==='ok') {
                        tgId = id; localStorage.setItem('lvt_tg_id', id);
                        document.getElementById('display-id').innerText = id;
                        if(r.is_admin) document.getElementById('btn-admin-panel').style.display = 'block';
                        navTo('scr-dash'); loadK();
                    } else Swal.fire('Từ Chối', 'ID không có quyền!', 'error');
                });
            }
            if(tgId) auth();
            
            function navTo(screenId) {
                document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
                document.getElementById(screenId).classList.add('active');
            }

            function switchT(t) {
                let actTab = 'tab-' + t;
                document.getElementById('tab-act').style.display = 'none';
                document.getElementById('tab-mgr').style.display = 'none';
                document.querySelector('.nav-btn:nth-child(1)').classList.remove('act');
                document.querySelector('.nav-btn:nth-child(2)').classList.remove('act');
                
                document.getElementById(actTab).style.display = 'block';
                if(t === 'act') document.querySelector('.nav-btn:nth-child(1)').classList.add('act');
                if(t === 'mgr') { document.querySelector('.nav-btn:nth-child(2)').classList.add('act'); loadK(); }
            }

            function actKey() {
                let k = document.getElementById('k_inp').value;
                if(!k) return Swal.fire('Lỗi','Vui lòng dán Key!','warning');
                api('/api/tg/activate_proxy', {tg_id:tgId, key:k}, r => {
                    if(r.status==='success') {
                        document.getElementById('proxy-result').style.display = 'block';
                        document.getElementById('res-host').innerText = r.host;
                        document.getElementById('res-port').innerText = r.port;
                        Swal.fire('Thành Công', r.msg, 'success');
                    } else Swal.fire('Lỗi', r.msg, 'error');
                });
            }

            function loadK() {
                api('/api/tg/my_keys', {tg_id:tgId}, r => {
                    if(r.status==='success') {
                        let h = '';
                        r.keys.forEach(k=>{
                            h+=`<div class="card">
                                <div style="display:flex;justify-content:space-between;">
                                    <b style="color:#00ffcc;">${k.key}</b>
                                    <span style="color:${k.vip?'#bd00ff':'#ffcc00'}; font-size:11px; font-weight:bold;">${k.vip?'VIP':'NOR'}</span>
                                </div>
                                <div style="color:#889; font-size:12px; margin-top:5px;">Tài khoản OLM: <span style="color:#fff;">${k.olm}</span></div>
                                <div style="color:#889; font-size:12px;">Máy chủ: <span style="color:#00ffcc; user-select:all;">${k.host}</span></div>
                                <div style="color:#889; font-size:12px;">Cổng: <span style="color:#00ffcc; user-select:all;">${k.port}</span></div>
                                <div style="color:#ff3366; font-size:12px; margin-top:5px; font-weight:bold;">Hết hạn: ${k.exp}</div>
                            </div>`;
                        });
                        document.getElementById('k_list').innerHTML = h || '<p style="color:#889;text-align:center;">Kho rỗng.</p>';
                    }
                });
            }

            function createKeys() {
                let q = document.getElementById('k-qty').value, d = document.getElementById('k-dur').value, u = document.getElementById('k-unit').value, dev = document.getElementById('k-dev').value, v = document.getElementById('k-vip').checked;
                api('/api/tg_admin/create_keys', {quantity: q, duration: d, unit: u, devices: dev, is_vip: v}, (res) => {
                    let kHtml = res.keys.map(k => `<div style="padding:10px; margin:5px 0; border:1px solid #333; color:#0ff; font-weight:bold;">${k}</div>`).join('');
                    Swal.fire({title: 'SẢN XUẤT THÀNH CÔNG', html: `<div style="max-height:200px;overflow-y:auto;">${kHtml}</div>`, background:'#1a1c26', color:'#fff'});
                });
            }

            function setupProxy() {
                let k = document.getElementById('p-key').value, h = document.getElementById('p-host').value;
                api('/api/tg_admin/setup_proxy', {key: k, host: h}, r => {
                    if(r.status === 'success') Swal.fire('Thành công', r.msg, 'success');
                    else Swal.fire('Lỗi', r.msg, 'error');
                });
            }

            function loadAdminKeys() {
                api('/api/tg_admin/get_all_keys', {}, r => {
                    if(r.status === 'success') {
                        let h = '';
                        r.keys.forEach(k => {
                            h += `<div class="card admin-key-item" data-key="${k.key}">
                                <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                    <strong style="color:#0ff; font-size:14px; user-select:all;">${k.key}</strong>
                                    <span style="font-size:10px; font-weight:bold; color:${k.vip?'#bd00ff':'#ffcc00'};">${k.vip?'VIP':'NOR'}</span>
                                </div>
                                <div style="font-size:12px; color:#889; line-height:1.6;">
                                    Định danh: <strong style="color:#ffcc00">${k.olm || 'Chưa ghim'}</strong><br>
                                    Thiết bị: <span style="color:#fff">${k.devs}/${k.max_dev}</span><br>
                                    Proxy: <span style="color:#00ffcc;">${k.host}:${k.port}</span><br>
                                    Hạn: <span style="color:#ff3366">${k.exp}</span>
                                </div>
                                <div style="margin-top:10px; display:flex; gap:5px; flex-wrap:wrap;">
                                    <button class="action-btn" style="background:rgba(255,204,0,0.2); color:#ffcc00;" onclick="bindOlmAdmin('${k.key}', '${k.olm}')">Ghim OLM</button>
                                    <button class="action-btn" style="background:rgba(0,153,255,0.2); color:#0099ff;" onclick="addTimeAdmin('${k.key}')">+ Giờ</button>
                                    <button class="action-btn" style="background:rgba(239,68,68,0.2); color:#ef4444;" onclick="api('/api/tg_admin/action_key', {key:'${k.key}', action:'delete'}, ()=>loadAdminKeys())">Xóa</button>
                                </div>
                            </div>`;
                        });
                        document.getElementById('admin-key-list').innerHTML = h;
                    }
                });
            }

            function filterAdminKeys() {
                let s = document.getElementById('search-key-inp').value.toLowerCase();
                document.querySelectorAll('.admin-key-item').forEach(el => { el.style.display = el.dataset.key.includes(s) ? 'block' : 'none'; });
            }

            function bindOlmAdmin(k, old) {
                Swal.fire({
                    title: 'GHIM ĐỊNH DANH', input: 'text', inputValue: old, placeholder:'Nhập tên OLM...',
                    showCancelButton: true, confirmButtonText:'Lưu', background: '#1a1c26', color: '#fff'
                }).then((r) => {
                    if(r.isConfirmed) api('/api/tg_admin/bind_olm', {key:k, olm_name:r.value}, ()=>loadAdminKeys());
                });
            }
            
            function addTimeAdmin(k) {
                Swal.fire({
                    title: 'THÊM THỜI GIAN',
                    html: `<input id="t-val" class="swal2-input" type="number" placeholder="Số lượng"><select id="t-unit" class="swal2-select"><option value="minutes">Phút</option><option value="hours">Giờ</option><option value="days" selected>Ngày</option><option value="months">Tháng</option></select>`,
                    showCancelButton: true, confirmButtonText: 'CỘNG', background: '#1a1c26', color: '#fff'
                }).then((r) => {
                    if(r.isConfirmed) {
                        let v = document.getElementById('t-val').value, u = document.getElementById('t-unit').value;
                        if(v) api('/api/tg_admin/add_time', {key:k, val:v, unit:u}, ()=>loadAdminKeys());
                    }
                });
            }
        </script>
    </body>
    </html>
    """
    return render_template_string_safe(html_template)

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    try:
        ip = get_real_ip()
        global admin_login_attempts
        now = time.time()
        admin_login_attempts = {k: v for k, v in admin_login_attempts.items() if now - v['time'] < 300} 
        attempts = admin_login_attempts.get(ip, {'count': 0, 'time': now})
        if attempts['count'] >= 5: return swal_back("Bị Khóa", "Thử lại sau 5 phút!", "error")

        if request.method == 'POST':
            db = load_db()
            username = request.form.get('username', '').strip().lower()
            pwd = request.form.get('password', '').strip()
            u_data = db.get("users", {}).get(username)
            if u_data and u_data.get("role") == "admin" and u_data.get("password_hash") == hash_pwd(pwd):
                session['username'] = username
                session['role'] = 'admin'
                session['csrf_token'] = secrets.token_hex(16)
                admin_login_attempts.pop(ip, None) 
                with db_lock: log_admin_action(db, f"Đăng nhập PC Admin: {ip}")
                save_db(db)
                return redirect('/admin')
            attempts['count'] += 1
            attempts['time'] = now
            admin_login_attempts[ip] = attempts
            return swal_back("Từ Chối", f"Sai thông tin! Còn {5 - attempts['count']} lần.", "error")
            
        return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><title>Admin Proxy</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>{CSS_GLASS}</style></head><body><div class="glass-panel"><h2 class="text-neon mb-4">🔐 PC ADMIN PROXY</h2><form method="POST"><input type="text" name="username" class="form-control" placeholder="Tên Admin" required><input type="password" name="password" class="form-control mt-2" placeholder="Mật Khẩu" required><button type="submit" class="btn-neon mt-3">ĐĂNG NHẬP VÀO TRUNG TÂM</button></form></div></body></html>'''
    except Exception as e: return f"LỖI: {str(e)}", 200

@app.route('/admin')
def admin_dashboard():
    try:
        if session.get('role') != 'admin': return redirect('/admin_login')
        db = load_db()
        csrf_input = f'<input type="hidden" name="csrf_token" value="{session.get("csrf_token", "")}">'
        
        with db_lock:
            keys_items = list(db.get("keys", {}).items())
            banned_ips = list(db.get("banned_ips", []))
            tg_admins = list(db.get("settings", {}).get("tg_admins", [TELEGRAM_CHAT_ID]))

        now_ms = int(time.time() * 1000)

        keys_html = ''
        for k, data in sorted(keys_items, key=lambda x: x[1].get('exp', 0) if isinstance(x[1].get('exp'), int) else 9999999999999, reverse=True):
            st = data.get('status', 'active')
            is_banned = (st == 'banned')
            status_badge = '<span class="badge bg-success">Hoạt động</span>' if not is_banned else '<span class="badge bg-danger">BỊ TRẢM</span>'
            vip_badge = '<span class="badge bg-warning text-dark">VIP</span>' if data.get('vip', False) else '<span class="badge bg-secondary">THƯỜNG</span>'
            
            is_expired = False
            if data.get('exp') == 'pending': exp_text = '<span class="text-info fw-bold">Chưa K.Hoạt</span>'
            elif data.get('exp') == 'permanent': exp_text = '<span class="text-success fw-bold">Vĩnh Viễn</span>'
            else:
                is_expired = now_ms > data.get('exp', 0)
                exp_text = f'<span class="{"text-danger fw-bold" if is_expired else "text-light"}">{time.strftime("%d/%m/%y %H:%M", time.localtime(data.get("exp", 0) / 1000))}</span>'
            
            if is_expired and not is_banned: status_badge = '<span class="badge bg-secondary">HẾT HẠN</span>'
            
            safe_k = escape(str(k))
            bound_olm = escape(data.get('bound_olm', ''))
            proxy_info = f"{data.get('proxy_host')}:{data.get('proxy_port')}" if data.get('proxy_host') else "Chưa gán"

            keys_html += f'''<tr class="align-middle text-nowrap">
            <td><strong class="text-info user-select-all">{safe_k}</strong><br>{vip_badge} {status_badge}</td>
            <td style="font-size:12px;">{exp_text}</td>
            <td style="font-size:12px;"><span class="text-warning fw-bold">{bound_olm or 'Chưa ghim'}</span><br><span class="text-success">{proxy_info}</span></td>
            <td><span class="badge bg-info text-dark">{len(data.get('devices', []))}/{data.get('maxDevices', 1)}</span></td>
            <td><div class="d-flex flex-wrap gap-1 justify-content-center">
            <button class="btn btn-warning btn-sm fw-bold text-dark" style="font-size:10px;" onclick="openBindModal('{safe_k}', '{bound_olm}')">Ghim OLM</button>
            <button class="btn btn-primary btn-sm fw-bold text-white" style="font-size:10px;" onclick="openProxyModal('{safe_k}')">Proxy</button>
            <button class="btn btn-info btn-sm fw-bold text-dark" style="font-size:10px;" onclick="openAddTimeModal('{safe_k}')">+ Giờ</button>
            <a href="/admin/action/reset-dev/{safe_k}" class="btn btn-secondary btn-sm" style="font-size:10px;">Reset Máy</a>
            <a href="/admin/action/delete/{safe_k}" class="btn btn-danger btn-sm" onclick="return confirm('Xóa vĩnh viễn Key?')" style="font-size:10px;">Xóa</a>
            </div></td></tr>'''

        blacklist_rows = "".join([f'<li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between">{escape(ip)} <a href="/admin/unban_ip/{escape(ip)}" class="btn btn-sm btn-danger p-0 px-2 rounded-pill">Gỡ</a></li>' for ip in banned_ips])
        tg_admin_rows = "".join([f'<li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between">ID: {escape(str(tid))} {"(Chủ Tịch)" if str(tid)==TELEGRAM_CHAT_ID else f"<a href='/admin/del_tg_admin/{escape(str(tid))}' class='btn btn-sm btn-danger p-0 px-2 rounded-pill'>Xóa</a>"}</li>' for tid in tg_admins])

        return f'''
        <!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>PC ADMIN DASHBOARD</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>{CSS_GLASS} h5{{font-weight:900;}}</style></head><body class="p-4">
        <div class="container-fluid">
            <div class="d-flex justify-content-between align-items-center mb-4 border-bottom border-secondary pb-3">
                <h3 class="text-neon fw-bold m-0"><i class="fas fa-server"></i> TRUNG TÂM QUẢN TRỊ PROXY</h3>
                <a href="/logout" class="btn btn-outline-danger fw-bold rounded-pill px-4">Đăng xuất</a>
            </div>
            
            <div class="row g-4">
                <div class="col-md-4">
                    <div class="card p-4 h-100" style="border-color:rgba(189,0,255,0.4);">
                        <h5 style="color:#bd00ff; margin-bottom:20px;"><i class="fas fa-key"></i> TẠO KEY PROXY</h5>
                        <form action="/admin/create" method="POST" class="row g-3">{csrf_input}
                            <div class="col-6"><input type="number" name="quantity" class="form-control" value="1" placeholder="Số lượng Key"></div>
                            <div class="col-6"><input type="number" name="devices" class="form-control" value="1" placeholder="Số thiết bị"></div>
                            <div class="col-6"><input type="number" name="duration" class="form-control" placeholder="Độ dài TG" required></div>
                            <div class="col-6"><select name="type" class="form-select"><option value="minute">Phút</option><option value="hour">Giờ</option><option value="day" selected>Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh Viễn</option></select></div>
                            <div class="col-12"><div class="form-check form-switch fs-5"><input class="form-check-input" type="checkbox" name="is_vip" id="vipSwitch"><label class="form-check-label text-warning fw-bold" for="vipSwitch" style="font-size:14px;">Gắn thẻ VIP PRO</label></div></div>
                            <div class="col-12"><button type="submit" class="btn fw-bold w-100" style="background:linear-gradient(45deg, #bd00ff, #3366ff);color:white;">SẢN XUẤT KEY</button></div>
                        </form>
                    </div>
                </div>

                <div class="col-md-4">
                    <div class="card p-4 h-100" style="border-color:rgba(0,255,204,0.4);">
                        <h5 style="color:#00ffcc; margin-bottom:20px;"><i class="fab fa-telegram"></i> ỦY QUYỀN TELEGRAM</h5>
                        <form action="/admin/add_tg_admin" method="POST" class="d-flex gap-2 mb-3">{csrf_input}
                            <input type="text" name="tg_id" class="form-control" placeholder="ID Telegram..." required>
                            <button type="submit" class="btn btn-info fw-bold">Cấp</button>
                        </form>
                        <ul class="list-group list-group-flush" style="max-height:150px; overflow-y:auto; border:1px solid #333;">{tg_admin_rows or '<li class="list-group-item bg-transparent text-muted">Trống</li>'}</ul>
                    </div>
                </div>

                <div class="col-md-4">
                    <div class="card p-4 h-100" style="border-color:rgba(255,51,102,0.4);">
                        <h5 class="text-danger mb-3"><i class="fas fa-shield-virus"></i> CHẶN IP XẤU (FIREWALL)</h5>
                        <form action="/admin/ban_ip" method="POST" class="d-flex gap-2 mb-3">{csrf_input}<input type="text" name="ip" class="form-control" placeholder="Nhập IP..." required><button type="submit" class="btn btn-danger fw-bold">Chặn</button></form>
                        <ul class="list-group list-group-flush" style="max-height:150px; overflow-y:auto; border:1px solid #333;">{blacklist_rows or '<li class="list-group-item bg-transparent text-muted">Sạch sẽ</li>'}</ul>
                    </div>
                </div>
                
                <div class="col-12">
                    <div class="card p-4" style="border-color:rgba(0,153,255,0.4);">
                        <h5 class="text-primary mb-3"><i class="fas fa-database"></i> KHO DỮ LIỆU KEY PROXY</h5>
                        <div class="table-responsive" style="max-height: 500px; overflow-y:auto;">
                            <table class="table table-dark table-hover text-center align-middle">
                                <thead class="table-active"><tr><th>🔑 Key / Trạng thái</th><th>⏳ Hạn</th><th>🎯 Ghim / Máy chủ</th><th>📱 Máy</th><th>⚙️ Hành động</th></tr></thead>
                                <tbody>{keys_html}</tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="modal fade" id="bindModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:rgba(17,17,26,0.95);border:1px solid #ffcc00;"><form action="/admin/bind_olm" method="POST">{csrf_input}<div class="modal-body text-center"><input type="hidden" name="key" id="bindKeyInput"><p class="text-white mb-2">Ghim Định Danh OLM:</p><strong id="bindKeyDisplay" class="text-info"></strong><input type="text" name="olm_name" id="bindOlmInput" class="form-control mt-3" placeholder="Tên OLM..."></div><div class="modal-footer"><button class="btn btn-warning w-100 fw-bold text-dark">Ghi Nhận</button></div></form></div></div></div>
        
        <div class="modal fade" id="addTimeModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:rgba(17,17,26,0.95);border:1px solid #00ffcc;"><form action="/admin/add_time" method="POST">{csrf_input}<div class="modal-body text-center"><input type="hidden" name="key" id="addTimeKeyInput"><p class="text-white mb-2">Bơm Giờ Cho Key:</p><strong id="addTimeKeyDisplay" class="text-info"></strong><input type="number" name="time_val" class="form-control mt-3" required><select name="time_unit" class="form-select mt-2"><option value="minutes">Phút</option><option value="hours">Giờ</option><option value="days" selected>Ngày</option><option value="months">Tháng</option></select></div><div class="modal-footer"><button class="btn btn-info w-100 fw-bold text-dark">CỘNG</button></div></form></div></div></div>
        
        <div class="modal fade" id="proxyModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-dialog-centered"><div class="modal-content" style="background:rgba(17,17,26,0.95);border:1px solid #a855f7;"><form action="/admin/setup_proxy" method="POST">{csrf_input}<div class="modal-body"><input type="hidden" name="key" id="proxyKeyInput"><h5 class="text-center" style="color:#a855f7;">GÁN MÁY CHỦ PROXY</h5><p class="text-center text-muted" style="font-size:12px;">Cổng Proxy sẽ được hệ thống Random tự động.</p><strong id="proxyKeyDisplay" class="text-info d-block text-center mb-3"></strong><input type="text" name="host" class="form-control" placeholder="Tên Máy Chủ (VD: sv1.proxy.com)" required></div><div class="modal-footer"><button class="btn fw-bold w-100" style="background:#a855f7; color:#fff;">LƯU CẤU HÌNH</button></div></form></div></div></div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            function openBindModal(key, old) {{ document.getElementById('bindKeyInput').value = key; document.getElementById('bindKeyDisplay').innerText = key; document.getElementById('bindOlmInput').value = old; new bootstrap.Modal(document.getElementById('bindModal')).show(); }}
            function openAddTimeModal(key) {{ document.getElementById('addTimeKeyInput').value = key; document.getElementById('addTimeKeyDisplay').innerText = key; new bootstrap.Modal(document.getElementById('addTimeModal')).show(); }}
            function openProxyModal(key) {{ document.getElementById('proxyKeyInput').value = key; document.getElementById('proxyKeyDisplay').innerText = key; new bootstrap.Modal(document.getElementById('proxyModal')).show(); }}
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
    return redirect('/admin')

@app.route('/admin/del_tg_admin/<path:tg_id>')
def del_tg_admin(tg_id):
    if session.get('role') != 'admin': return redirect('/login')
    if tg_id == TELEGRAM_CHAT_ID: return swal_back("Lỗi", "Chủ tịch không thể bị xóa!", "error")
    db = load_db()
    with db_lock:
        admins = db.setdefault("settings", {}).setdefault("tg_admins", [TELEGRAM_CHAT_ID])
        if tg_id in admins:
            admins.remove(tg_id)
            save_db(db)
    return redirect('/admin')

@app.route('/admin/create', methods=['POST'])
def create_key():
    if session.get('role') != 'admin': return redirect('/login')
    dur = safe_int(request.form.get('duration'))
    md = safe_int(request.form.get('devices'), 1)
    qty = safe_int(request.form.get('quantity'), 1)
    t = request.form.get('type')
    vip = request.form.get('is_vip') == 'on'
    db = load_db()
    with db_lock:
        for _ in range(qty):
            nk = generate_proxy_key()
            db["keys"][nk] = {"exp": "pending", "maxDevices": md, "devices": [], "known_ips": {}, "status": "active", "vip": vip, "violations": 0, "temp_ban_until": 0, "owner": "admin", "bound_olm": "", "activated": False, "proxy_host": "", "proxy_port": 0}
            if t != 'permanent': db["keys"][nk]["durationMs"] = dur * {"minute":60000, "hour":3600000, "day":86400000, "month":2592000000}.get(t, 60000)
            else: db["keys"][nk]["exp"] = "permanent"
        save_db(db)
    return redirect('/admin')

@app.route('/admin/setup_proxy', methods=['POST'])
def admin_setup_proxy():
    if session.get('role') != 'admin': return redirect('/login')
    key = request.form.get('key', '').strip()
    host = request.form.get('host', '').strip()
    db = load_db()
    with db_lock:
        if key in db.get("keys", {}):
            if not db["keys"][key].get("bound_olm"):
                return swal_back("Lỗi", "Key này chưa được ghim tài khoản OLM. Hãy Ghim OLM trước!", "error")
            db["keys"][key]["proxy_host"] = host
            db["keys"][key]["proxy_port"] = random.randint(10000, 65000)
            save_db(db)
    return redirect('/admin')

@app.route('/admin/add_time', methods=['POST'])
def admin_add_time():
    if session.get('role') != 'admin': return redirect('/login')
    key = request.form.get('key', '').strip()
    t_val = safe_int(request.form.get('time_val', 0))
    t_unit = request.form.get('time_unit', 'days')
    if t_val <= 0: return swal_back("Lỗi", "Số lượng > 0", "error")
    ms_to_add = t_val * {"minutes": 60000, "hours": 3600000, "days": 86400000, "months": 2592000000}.get(t_unit, 0)
    db = load_db()
    with db_lock:
        if key in db.get("keys", {}):
            kd = db["keys"][key]
            if kd.get("exp") == "permanent": return swal_back("Lỗi", "Key vĩnh viễn không cần cộng!", "error")
            now = int(time.time() * 1000)
            if kd.get("exp") == "pending": kd["durationMs"] = kd.get("durationMs", 0) + ms_to_add
            else:
                current_exp = max(kd.get("exp", now), now)
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
            elif action == 'unban': kd['status'] = 'active'; kd['temp_ban_until'] = 0; kd['violations'] = 0
            elif action == 'delete': db["keys"].pop(key, None)
            elif action == 'reset-dev': kd['devices'] = []; kd['known_ips'] = {}; kd['activated'] = False
            save_db(db)
    return redirect('/admin')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/admin_login')

try:
    init_db = load_db()
    app.secret_key = os.environ.get('SECRET_KEY', init_db.get("settings", {}).get("secret_key", secrets.token_hex(32)))
except Exception: pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
