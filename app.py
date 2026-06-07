import os, json, time, random, hashlib, threading, requests, shutil, base64, secrets, hmac, string, copy, traceback, ssl, re
import urllib.parse
from html import escape
from flask import Flask, request, jsonify, redirect, make_response, session, abort, send_file, url_for
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
.glass-panel { background: rgba(17, 17, 26, 0.7); backdrop-filter: blur(15px); border: 1px solid rgba(0, 255, 204, 0.3); border-radius: 15px; padding: 30px; box-shadow: 0 0 20px rgba(0, 255, 204, 0.2); text-align: center; }
.text-neon { color: #00ffcc; text-shadow: 0 0 10px rgba(0, 255, 204, 0.5); }
.btn-neon { background: linear-gradient(90deg, #00ffcc, #0099ff); border: none; color: #000; font-weight: bold; padding: 10px 20px; border-radius: 8px; width: 100%; transition: 0.3s; text-transform: uppercase; cursor: pointer; }
.btn-neon:hover { transform: scale(1.05); box-shadow: 0 0 15px rgba(0, 255, 204, 0.5); }
"""

# ========================================================
# HỆ THỐNG BOT TELEGRAM
# ========================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8714375866:AAG9r0aCCFOKtgR6B-LcFYBAnJ7x9yMs-8o")
TELEGRAM_CHAT_ID = "7363320876"
WEB_URL = "https://app-tool-trlp.onrender.com" 

def send_telegram_event(event_type, data):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    def _send():
        try:
            session_req = requests.Session()
            msg = ""
            if event_type == "create": msg = f"🌟 <b>KEY VỪA ĐƯỢC TẠO</b> 🌟\n\n🔑 <code>{escape(str(data.get('key')))}</code>\n⏳ Hạn: {escape(str(data.get('exp')))}\n📱 Thiết bị tối đa: {escape(str(data.get('max_dev')))}"
            elif event_type == "banned": msg = f"🚫 <b>CẢNH BÁO: KEY BỊ BAND</b> 🚫\n\n🔑 Key: <code>{escape(str(data.get('key')))}</code>\n🌐 IP Vi phạm: {escape(str(data.get('ip')))}"
            elif event_type == "expired": msg = f"⚠️ <b>THÔNG BÁO: KEY HẾT HẠN</b> ⚠️\n\n🔑 Key: <code>{escape(str(data.get('key')))}</code>\n🌐 IP Khách: {escape(str(data.get('ip')))}"
            elif event_type == "limit": msg = f"📵 <b>CẢNH BÁO: VƯỢT QUÁ THIẾT BỊ</b> 📵\n\n🔑 Key: <code>{escape(str(data.get('key')))}</code>\n🌐 IP Đăng nhập: {escape(str(data.get('ip')))}"
            elif event_type == "login": msg = f"✅ <b>ĐĂNG NHẬP THÀNH CÔNG</b> ✅\n\n🔑 Key: <code>{escape(str(data.get('key')))}</code>\n🌐 IP Máy Khách (Local IP): {escape(str(data.get('ip')))}\n📱 Tên Máy: {escape(str(data.get('device_name')))}\n🤖 Phiên bản: {escape(str(data.get('android_version')))}"
            if not msg: return
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
            headers = {"User-Agent": "LVT-Core-Encrypted-Server/3.0", "X-Security-Cipher": secrets.token_hex(32)}
            session_req.post(url, json=payload, headers=headers, timeout=15, verify=True)
        except Exception: pass
    threading.Thread(target=_send, daemon=True).start()

_needs_tg_backup = False
def tg_backup_worker():
    global _needs_tg_backup
    while True:
        time.sleep(10)
        if _needs_tg_backup:
            _needs_tg_backup = False
            if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: continue
            try:
                db = load_db()
                old_msg_id = db.get("settings", {}).get("last_tg_backup_msg_id")
                if old_msg_id:
                    try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage", json={"chat_id": TELEGRAM_CHAT_ID, "message_id": old_msg_id}, timeout=5)
                    except: pass
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
                if os.path.exists(DB_FILE):
                    with open(DB_FILE, 'rb') as f:
                        res = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"📦 BACKUP DATABASE LVT TOOL\nThời gian: {time.strftime('%d/%m/%Y %H:%M:%S')}"}, files={"document": f}, timeout=15).json()
                        if res.get("ok"):
                            new_msg_id = res["result"]["message_id"]
                            with db_lock:
                                GLOBAL_DB["settings"]["last_tg_backup_msg_id"] = new_msg_id
                                safe_db = copy.deepcopy(GLOBAL_DB)
                                with open(DB_FILE, 'w', encoding='utf-8') as fw: json.dump(safe_db, fw, indent=2, ensure_ascii=False)
            except Exception as e: print(f"Lỗi gửi telegram backup: {e}")

threading.Thread(target=tg_backup_worker, daemon=True).start()

def send_telegram_backup():
    global _needs_tg_backup
    _needs_tg_backup = True

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
                        user_first_name = msg.get("from", {}).get("first_name", "Khách")
                        if text.startswith("/start"):
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage", json={"chat_id": chat_id, "message_id": msg_id})
                            welcome = f"🌟 <b>HỆ THỐNG CẤP PROXY OLM TỰ ĐỘNG</b> 🌟\n\nXin chào <b>{escape(user_first_name)}</b>!"
                            keyboard = {"inline_keyboard": [[{"text": "🌐 MỞ TRANG KÍCH HOẠT PROXY", "web_app": {"url": f"{WEB_URL}/"}}]]}
                            requests.post(url_base + "/sendMessage", json={"chat_id": chat_id, "text": welcome, "parse_mode": "HTML", "reply_markup": keyboard})
        except Exception: pass
        time.sleep(2)

threading.Thread(target=telegram_polling, daemon=True).start()

def keep_awake():
    while True:
        time.sleep(14 * 60)
        try: requests.get(WEB_URL + '/ping', timeout=10)
        except: pass

threading.Thread(target=keep_awake, daemon=True).start()

@app.route('/ping')
def ping_server(): return "OK", 200

@app.route('/telegram_mini_app')
def old_mini_app_redirect(): return redirect('/')

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException): return e
    return f"""<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Server Updating</title><style>body {{ background: #05050A; color: #00ffcc; display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100vh; text-align: center; margin: 0; }} .loader {{ border: 5px solid rgba(0, 255, 204, 0.2); border-top: 5px solid #00ffcc; border-radius: 50%; width: 60px; height: 60px; animation: spin 1s linear infinite; margin-bottom: 20px; }} @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}</style></head><body><div class="loader"></div><h2>Đang update online server vui lòng đợi...</h2></body></html>""", 500

app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024 
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30

DB_FILE = './database.json'
DB_BACKUP = './database.backup.json'

db_lock = threading.RLock()
api_rate_lock = threading.Lock()
admin_login_lock = threading.Lock() 

active_sessions = {}
api_rate_cache = {}
used_signatures = {} 
admin_login_attempts = {}
pending_get_key = {} # Cache quản lý trạng thái Get Key vượt link

GLOBAL_DB = {}
_last_db_mtime = 0
_last_mtime_check = 0 

def safe_int(val, default=0):
    try: return int(val)
    except: return default

def hash_pwd(pwd): return hashlib.sha256(pwd.encode()).hexdigest()
def escape_swal(text): return str(text).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

def swal_redirect(title, text, icon, url):
    return f"""<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #05050A; }}</style></head><body><script>Swal.fire({{ title: {json.dumps(title)}, html: {json.dumps(text)}, icon: {json.dumps(icon)}, background: '#11111A', color: '#fff', confirmButtonColor: '#00ffcc', allowOutsideClick: false }}).then(() => {{ window.location.href = {json.dumps(url)}; }});</script></body></html>"""

def swal_back(title, text, icon):
    return f"""<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #05050A; }}</style></head><body><script>Swal.fire({{ title: {json.dumps(title)}, html: {json.dumps(text)}, icon: {json.dumps(icon)}, background: '#11111A', color: '#fff', confirmButtonColor: '#bd00ff', allowOutsideClick: false }}).then(() => {{ window.history.back(); }});</script></body></html>"""

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
                except Exception as e:
                    if os.path.exists(DB_BACKUP):
                        try:
                            with open(DB_BACKUP, 'r', encoding='utf-8') as f: data = json.load(f)
                        except: pass

            if not data: data = {}
            data.setdefault("users", {})
            data.setdefault("keys", {})
            data.setdefault("banned_ips", [])
            data.setdefault("settings", {})
            data.setdefault("games", {}) # Database mới cho Quản lý Game
            
            if "secret_key" not in data["settings"]: data["settings"]["secret_key"] = secrets.token_hex(32)
            if "script_tiem" not in data["settings"]: data["settings"]["script_tiem"] = ""
            if "vm_loader" not in data["settings"]: data["settings"]["vm_loader"] = ""
            if "app_webview_code" not in data["settings"]: data["settings"]["app_webview_code"] = ""
            if "tg_admins" not in data["settings"]: data["settings"]["tg_admins"] = [TELEGRAM_CHAT_ID]
            if "webview_maintenance" not in data["settings"]: data["settings"]["webview_maintenance"] = False
            if "layma_api" not in data["settings"]: data["settings"]["layma_api"] = ""
            
            if "admin" not in data["users"]: data["users"]["admin"] = {"password_hash": hash_pwd("120510@"), "role": "admin"}

            for k in data["keys"]:
                data["keys"][k].setdefault("owner", "admin")
                data["keys"][k].setdefault("devices", [])
                data["keys"][k].setdefault("maxDevices", 1)
                data["keys"][k].setdefault("bound_olm", "") 
                data["keys"][k].setdefault("vip", False)
                data["keys"][k].setdefault("ban_until", 0)
                data["keys"][k].setdefault("status", "active")
                data["keys"][k].setdefault("note", "") 

            GLOBAL_DB = data
            _last_db_mtime = current_mtime
        return GLOBAL_DB

def save_db(db=None):
    global _last_db_mtime
    if db is None: db = GLOBAL_DB
    with db_lock:
        try: 
            safe_db = copy.deepcopy(db)
            db_str = json.dumps(safe_db, indent=2, ensure_ascii=False)
            temp_file = DB_FILE + f'.{int(time.time() * 1000)}.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f: 
                f.write(db_str)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, DB_FILE)
            shutil.copy2(DB_FILE, DB_BACKUP)
            _last_db_mtime = os.path.getmtime(DB_FILE)
            send_telegram_backup()
        except: pass

def generate_proxy_key(prefix=""):
    random_str = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    return f"{prefix}_{random_str}" if prefix else random_str

def garbage_collector():
    while True:
        time.sleep(3600) 
        now_ms = int(time.time() * 1000)
        try:
            db = load_db()
            changed = False
            with db_lock:
                for k in list(db.get("keys", {}).keys()):
                    exp = db["keys"][k].get("exp")
                    if exp != "permanent" and exp != "pending":
                        if isinstance(exp, int) and (now_ms - exp) > 604800000:
                            del db["keys"][k]
                            changed = True
                
                # Clear pending_get_key cache
                now = time.time()
                for t in list(pending_get_key.keys()):
                    if now > pending_get_key[t].get('expire', 0):
                        del pending_get_key[t]

            if changed: save_db(db)
        except: pass

threading.Thread(target=garbage_collector, daemon=True).start()

def get_real_ip(): return request.remote_addr or "Unknown_IP"

@app.before_request
def firewall_and_csrf():
    try:
        db = load_db()
        banned_ips = set(db.get("banned_ips", []))
        ip = get_real_ip()
        
        if ip in banned_ips: return "⚠️ BẠN ĐÃ BỊ TỪ CHỐI TRUY CẬP BỞI HỆ THỐNG FIREWALL LVT.", 403

        ua = (request.headers.get('User-Agent') or '').lower()
        blocked_bots = ['curl', 'postman', 'python', 'nmap', 'sqlmap', 'masscan', 'zgrab', 'wget', 'urllib', 'nikto']
        if any(bot in ua for bot in blocked_bots): return "Firewall Blocked.", 403
            
        if request.path.startswith("/admin") and request.path not in ["/admin_login"]:
            if session.get('role') != 'admin': return redirect('/admin_login')
            if request.method == 'POST':
                if request.form.get("csrf_token") != session.get('csrf_token'): return "Lỗi CSRF Token", 403
            elif request.method == 'GET' and ('/admin/action/' in request.path or '/admin/unban_ip/' in request.path):
                if request.args.get("csrf_token") != session.get('csrf_token'): return "Lỗi CSRF Token", 403
    except: pass

@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN' 
    return response

# ========================================================
# KICK USER & GIAO DỊCH SCRIPT
# ========================================================
@app.route('/api/check_ban_status')
def check_ban_status():
    ip = get_real_ip()
    db = load_db()
    now = int(time.time() * 1000)
    if ip in db.get("banned_ips", []): return jsonify({"banned": True, "reason": "IP của bạn đã bị Firewall chặn đứt."})
    with db_lock:
        for k, v in db.get("keys", {}).items():
            if ip in v.get("connected_ips", []):
                if v.get("status") == "banned":
                    ban_until = v.get("ban_until", "permanent")
                    if ban_until == "permanent" or (isinstance(ban_until, int) and ban_until > now): return jsonify({"banned": True, "reason": "Key của bạn đã bị Admin khóa. Bạn đã bị kick khỏi hệ thống!", "ban_time": ban_until})
                    else:
                        v["status"] = "active"
                        save_db(db)
                        return jsonify({"banned": False})
    return jsonify({"banned": False})

@app.route('/api/get_script')
def serve_custom_script():
    db = load_db()
    user_script = db.get("settings", {}).get("script_tiem", "")
    kick_payload = f"""(function() {{ setInterval(function() {{ fetch('{WEB_URL}/api/check_ban_status', {{cache: 'no-store'}}).then(r => r.json()).then(d => {{ if(d.banned) {{ localStorage.removeItem('lvt_proxy_key'); alert("⚠️ LVT HỆ THỐNG: " + d.reason); window.location.href = "https://google.com"; }} }}).catch(e => {{}}); }}, 10000); }})();"""
    resp = make_response(kick_payload + "\n" + user_script)
    resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    return resp

@app.route('/api/vm_payload')
def get_vm_payload():
    db = load_db()
    resp = make_response(db.get("settings", {}).get("vm_loader", ""))
    resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    return resp

@app.route('/api/download_pak')
def download_pak():
    if not os.path.exists('./uploaded.pak'): return "File không tồn tại trên hệ thống", 404
    return send_file('./uploaded.pak', as_attachment=True, download_name='data.pak')

@app.route('/webview')
def serve_webview_app():
    db = load_db()
    is_maintenance = db.get("settings", {}).get("webview_maintenance", False)
    if is_maintenance: html_content = f"""<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>body {{ background: #05050A; color: #bd00ff; display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100vh; text-align: center; margin: 0; }}</style></head><body><h2>Đang bảo trì hệ thống</h2></body></html>"""
    else: html_content = db.get("settings", {}).get("app_webview_code", "<h1>Hệ thống chưa được nạp giao diện WebView.</h1>")
    resp = make_response(html_content)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp

@app.route('/api/verify_core', methods=['POST'])
def api_verify_core():
    public_ip = get_real_ip()
    now = int(time.time() * 1000)
    data = request.json or {}
    key = data.get('key', '').strip()
    current_olm = data.get('olm_name', '').strip()
    device_name = data.get('device_name', 'Không xác định')
    android_version = data.get('android_version', 'Không xác định')
    client_ip = data.get('local_ip') or public_ip
    
    db = load_db()
    with db_lock:
        if public_ip in db.get("banned_ips", []): return jsonify({"status": "error", "msg": "Thiết bị đã bị chặn!"})
        if key not in db.get("keys", {}): return jsonify({"status": "error", "msg": "Mã Key không tồn tại!"})
        kd = db["keys"][key]
        
        if kd.get("status") == "banned": return jsonify({"status": "banned", "msg": "Key bị khóa!"})
        if kd.get("exp") != "permanent" and kd.get("exp") != "pending" and kd.get("exp", 0) < now: return jsonify({"status": "error", "msg": "Key đã hết hạn!"})

        devices = kd.setdefault("devices", [])
        connected_ips = kd.setdefault("connected_ips", [])
        if client_ip not in connected_ips: connected_ips.append(client_ip)

        device_identifier = data.get('device_id', '') or f"{device_name} - {android_version}"
        for item in list(devices):
            if ('.' in item and len(item.split('.')) == 4) or (':' in item):
                try: devices.remove(item)
                except: pass
                
        if device_identifier not in devices:
            if len(devices) >= kd.get("maxDevices", 1): return jsonify({"status": "error", "msg": "Vượt quá thiết bị cho phép!"})
            devices.append(device_identifier)

        if kd.get("exp") == "pending":
            kd["exp"] = now + kd.get("durationMs", 0)
            
        bound_olm = kd.get("bound_olm", "")
        if bound_olm and current_olm and bound_olm.lower() != current_olm.lower():
            kd["status"] = "banned"; kd["ban_until"] = "permanent"; save_db(db)
            return jsonify({"status": "banned", "msg": "Sai tài khoản OLM!"})
            
        save_db(db)
        return jsonify({"status": "ok", "is_vip": kd.get("vip", False), "core": db.get("settings", {}).get("script_tiem", ""), "exp": kd["exp"], "devices": len(devices), "max_devs": kd.get("maxDevices", 1), "server_time": now, "note": kd.get("note", "")})

# ========================================================
# GIAO DIỆN GET KEY DÀNH CHO KHÁCH (TRANG CHỦ)
# ========================================================
@app.route('/')
def index_get_key():
    db = load_db()
    games = db.get("games", {})
    
    # Render danh sách game
    game_options = ""
    for g_id, g_data in games.items():
        game_options += f'<option value="{g_id}">🎮 {escape(g_data.get("name", "Game"))} ({g_data.get("duration_hours", 24)}h - Vượt {g_data.get("passes", 1)} Lần)</option>'
        
    if not game_options:
        game_options = '<option value="">Hệ thống chưa cấu hình Game nào</option>'

    return f'''
    <!DOCTYPE html><html lang="vi" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>LVT - Lấy Key Tự Động</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
            body {{ background: #05050A; font-family: 'Inter', sans-serif; color: #fff; min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; position: relative; overflow-x: hidden; }}
            .blob {{ position: absolute; filter: blur(80px); z-index: -1; opacity: 0.5; }}
            .blob-1 {{ top: -10%; left: -10%; width: 400px; height: 400px; background: #bd00ff; border-radius: 50%; }}
            .blob-2 {{ bottom: -10%; right: -10%; width: 300px; height: 300px; background: #00ffcc; border-radius: 50%; }}
            .glass-box {{ background: rgba(20, 20, 30, 0.6); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 20px; padding: 40px; width: 90%; max-width: 450px; box-shadow: 0 20px 40px rgba(0,0,0,0.4); text-align: center; position: relative; z-index: 10; }}
            .title-neon {{ font-weight: 800; font-size: 28px; background: linear-gradient(90deg, #00ffcc, #bd00ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 30px; }}
            .form-select {{ background: rgba(0,0,0,0.5) !important; border: 1px solid rgba(255,255,255,0.2) !important; color: #00ffcc !important; border-radius: 12px; padding: 15px; font-weight: 600; text-align: center; cursor: pointer; }}
            .form-select:focus {{ border-color: #bd00ff !important; box-shadow: 0 0 15px rgba(189,0,255,0.3) !important; }}
            .btn-getkey {{ background: linear-gradient(135deg, #00ffcc, #0099ff); border: none; color: #000; font-weight: 800; padding: 15px; border-radius: 12px; width: 100%; font-size: 18px; margin-top: 25px; cursor: pointer; transition: 0.3s; text-transform: uppercase; letter-spacing: 1px; }}
            .btn-getkey:hover {{ transform: translateY(-3px); box-shadow: 0 10px 20px rgba(0,255,204,0.4); }}
            .admin-btn {{ position: absolute; top: 20px; right: 20px; color: rgba(255,255,255,0.5); font-size: 24px; cursor: pointer; transition: 0.3s; z-index: 20; }}
            .admin-btn:hover {{ color: #00ffcc; }}
        </style>
    </head>
    <body>
        <div class="blob blob-1"></div><div class="blob blob-2"></div>
        <a href="/admin_login" class="admin-btn"><i class="fas fa-bars"></i></a>
        
        <div class="glass-box">
            <div class="title-neon">LVT HACK SYSTEM</div>
            <p class="text-secondary mb-4">Vui lòng chọn loại Game để tiếp tục vượt link lấy Key kích hoạt tự động.</p>
            
            <form action="/start_get_key" method="POST">
                <select name="game_id" class="form-select mb-3" required>
                    <option value="" disabled selected>-- CHỌN TRÒ CHƠI CỦA BẠN --</option>
                    {game_options}
                </select>
                <button type="submit" class="btn-getkey"><i class="fas fa-key"></i> BẮT ĐẦU LẤY KEY</button>
            </form>
        </div>
    </body>
    </html>
    '''

def create_layma_shortlink(destination_url):
    db = load_db()
    api_token = db.get("settings", {}).get("layma_api", "").strip()
    if not api_token: return destination_url 
    try:
        api_url = f"https://api.layma.net/api/admin/shortlink/quicklink?token={api_token}&url={urllib.parse.quote(destination_url)}"
        res = requests.get(api_url, timeout=8).text.strip()
        if res.startswith("http"): return res
        data = json.loads(res)
        return data.get("short_url") or data.get("shortenedUrl") or destination_url
    except: return destination_url

@app.route('/start_get_key', methods=['POST'])
def start_get_key():
    game_id = request.form.get('game_id')
    if not game_id: return redirect('/')
    
    db = load_db()
    games = db.get("games", {})
    if game_id not in games: return swal_back("Lỗi", "Game không tồn tại!", "error")
    
    g_data = games[game_id]
    
    # Check giới hạn key
    max_keys = safe_int(g_data.get('max_keys', 100))
    current_keys = sum(1 for k in db.get("keys", {}).values() if k.get("note") == f"Auto_{game_id}")
    if current_keys >= max_keys:
        return swal_back("Hết Key", "Số lượng Key cho game này đã đạt giới hạn tối đa. Vui lòng liên hệ Admin!", "warning")

    # Tạo phiên giao dịch
    session_token = secrets.token_hex(16)
    pending_get_key[session_token] = {
        "game_id": game_id,
        "step": 1,
        "ip": get_real_ip(),
        "expire": time.time() + 3600 # 1 tiếng hết hạn link
    }
    
    return redirect(url_for('process_step', token=session_token))

@app.route('/process_step')
def process_step():
    token = request.args.get('token')
    if not token or token not in pending_get_key: return swal_redirect("Lỗi", "Phiên lấy Key không hợp lệ hoặc đã hết hạn!", "error", "/")
    
    session_data = pending_get_key[token]
    db = load_db()
    g_data = db.get("games", {}).get(session_data["game_id"])
    if not g_data: return redirect('/')
    
    current_step = session_data["step"]
    total_passes = safe_int(g_data.get("passes", 1))
    
    if current_step <= total_passes:
        # Chuyển hướng sang web rút gọn
        callback_url = f"{request.host_url}verify_step?token={token}&step={current_step}"
        shortlink = create_layma_shortlink(callback_url)
        return redirect(shortlink)
    else:
        # Hoàn thành, cấp Key
        game_name = g_data.get("name", "GAME").replace(" ", "").upper()
        duration_h = safe_int(g_data.get("duration_hours", 24))
        
        # Format: Key_PUBG_24h_XXXXXX
        key_name = generate_proxy_key(f"Key_{game_name}_{duration_h}h")
        
        with db_lock:
            db["keys"][key_name] = {
                "exp": "pending", 
                "durationMs": duration_h * 3600000,
                "maxDevices": safe_int(g_data.get("devices", 1)), 
                "devices": [], 
                "vip": False, 
                "status": "active", 
                "bound_olm": "", 
                "note": f"Auto_{session_data['game_id']}"
            }
            save_db(db)
            send_telegram_event('create', {'key': key_name, 'exp': f"{duration_h} Giờ", 'max_dev': g_data.get("devices", 1)})
            
        del pending_get_key[token]
        
        # Giao diện trả Key
        return f'''
        <!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Nhận Key Thành Công</title><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>{CSS_GLASS} body{{background:#05050A;display:flex;justify-content:center;align-items:center;height:100vh;color:#fff;font-family:sans-serif;}} .key-box{{background:rgba(0,0,0,0.5);border:2px dashed #00ffcc;padding:20px;border-radius:12px;font-size:24px;font-weight:bold;color:#00ffcc;letter-spacing:2px;cursor:pointer;word-break:break-all;margin:20px 0;}} .key-box:hover{{background:rgba(0,255,204,0.1);}}</style></head><body>
            <div class="glass-panel" style="max-width:500px; width:90%;">
                <i class="fas fa-check-circle text-success" style="font-size:60px; margin-bottom:20px; text-shadow:0 0 20px #28a745;"></i>
                <h2 class="text-neon">XÁC THỰC THÀNH CÔNG!</h2>
                <p class="text-secondary">Nhấn vào mã Key bên dưới để sao chép</p>
                <div class="key-box" onclick="navigator.clipboard.writeText('{key_name}'); Swal.fire({{icon:'success', title:'Đã sao chép Key!', background:'#111', color:'#fff', showConfirmButton:false, timer:1500}});">{key_name}</div>
                <p style="color:#bd00ff; font-weight:bold;">Thời hạn: {duration_h} Giờ | Thiết bị: {g_data.get("devices", 1)}</p>
                <a href="/" class="btn-neon mt-3 text-decoration-none d-inline-block text-center" style="width:100%; box-sizing:border-box;">QUAY LẠI TRANG CHỦ</a>
            </div>
        </body></html>
        '''

@app.route('/verify_step')
def verify_step():
    token = request.args.get('token')
    step = safe_int(request.args.get('step', 1))
    
    if not token or token not in pending_get_key: return swal_redirect("Lỗi", "Phiên không hợp lệ!", "error", "/")
    
    # Tăng bước lên 1 và xử lý tiếp
    if pending_get_key[token]["step"] == step:
        pending_get_key[token]["step"] += 1
        
    return redirect(url_for('process_step', token=token))


# ========================================================
# GIAO DIỆN WEB ADMIN (TỐI ƯU HÓA RẤT GỌN)
# ========================================================
def render_admin_layout(title, active_tab, content, csrf_token):
    tabs = {
        'keys': {'url': '/admin', 'icon': 'fas fa-key', 'label': 'QUẢN LÝ KEY & FIREWALL', 'color': '#38bdf8'},
        'files': {'url': '/admin/files', 'icon': 'fas fa-cloud-upload-alt', 'label': 'NẠP FILE TRÊN MÂY', 'color': '#a855f7'},
        'games': {'url': '/admin/games', 'icon': 'fas fa-gamepad', 'label': 'QUẢN LÝ GAME & LINK', 'color': '#10b981'}
    }
    
    nav_html = ""
    for k, v in tabs.items():
        active = f"background: linear-gradient(135deg, {v['color']}, #3b82f6); color: #fff; border-color: transparent; box-shadow: 0 0 15px {v['color']}66;" if active_tab == k else ""
        nav_html += f'<a href="{v["url"]}" class="nav-btn" style="{active}"><i class="{v["icon"]}"></i> {v["label"]}</a>'

    return f'''
    <!DOCTYPE html><html lang="vi" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{title}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
            body {{ background: #0b0f19; font-family: 'Inter', sans-serif; color: #e2e8f0; }}
            .topbar {{ background: #131722; border-bottom: 1px solid #1e293b; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; }}
            .topbar-brand {{ font-size: 20px; font-weight: 800; color: #38bdf8; letter-spacing: 1px; display: flex; align-items: center; gap: 10px; }}
            .card {{ background: #131722; border: 1px solid #1e293b; border-radius: 12px; margin-bottom: 24px; }}
            .card-header {{ background: rgba(255,255,255,0.02); border-bottom: 1px solid #1e293b; padding: 15px 20px; font-weight: 700; text-transform: uppercase; }}
            .form-control, .form-select {{ background: #0b0f19 !important; border: 1px solid #334155 !important; color: #f8fafc !important; border-radius: 8px; }}
            .form-control:focus, .form-select:focus {{ border-color: #38bdf8 !important; box-shadow: none !important; }}
            .btn-custom {{ border: none; font-weight: 700; padding: 10px 20px; border-radius: 8px; transition: 0.3s; text-transform: uppercase; color:#fff; }}
            .btn-custom:hover {{ transform: translateY(-2px); }}
            .nav-tabs-custom {{ display: flex; gap: 15px; margin-bottom: 25px; border-bottom: 1px solid #1e293b; padding-bottom: 15px; overflow-x: auto; }}
            .nav-btn {{ padding: 12px 25px; border-radius: 8px; font-weight: 700; color: #94a3b8; text-decoration: none; border: 1px solid #1e293b; background: #0f172a; white-space: nowrap; }}
            .table thead th {{ background: #0f172a; border-bottom: 1px solid #1e293b; color: #94a3b8; text-transform: uppercase; font-size: 12px; }}
            .action-btn {{ background: rgba(255,255,255,0.05); color: #e2e8f0; border: 1px solid #334155; padding: 6px 10px; border-radius: 6px; text-decoration: none; display: inline-flex; transition: 0.2s; cursor: pointer; }}
            .action-btn:hover {{ background: rgba(255,255,255,0.1); color: #fff; }}
            .modal-content {{ background: #131722; border: 1px solid #334155; border-radius: 12px; }}
        </style>
    </head>
    <body>
        <div class="topbar">
            <div class="topbar-brand"><i class="fas fa-server"></i> LVT C-PANEL</div>
            <div>
                <a href="/" target="_blank" class="btn btn-outline-info btn-sm fw-bold px-3 py-2 me-2" style="border-radius: 8px;"><i class="fas fa-external-link-alt"></i> Xem Trang Khách</a>
                <a href="/logout" class="btn btn-outline-danger btn-sm fw-bold px-3 py-2" style="border-radius: 8px;"><i class="fas fa-sign-out-alt"></i> Đăng xuất</a>
            </div>
        </div>
        <div class="container-fluid py-4 px-lg-5">
            <div class="nav-tabs-custom">{nav_html}</div>
            {content}
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    '''

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    try:
        ip = get_real_ip()
        global admin_login_attempts
        now = time.time()
        with admin_login_lock:
            admin_login_attempts = {k: v for k, v in admin_login_attempts.items() if now - v['time'] < 300} 
            attempts = admin_login_attempts.get(ip, {'count': 0, 'time': now})
            if attempts['count'] >= 5: return swal_back("Bị Khóa", "Thử lại sau 5 phút!", "error")

            if request.method == 'POST':
                db = load_db()
                username = request.form.get('username', '').strip().lower()
                pwd = request.form.get('password', '').strip()
                u_data = db.get("users", {}).get(username)
                if u_data and u_data.get("role") == "admin" and hmac.compare_digest(u_data.get("password_hash"), hash_pwd(pwd)):
                    session['username'] = username
                    session['role'] = 'admin'
                    session['csrf_token'] = secrets.token_hex(16)
                    admin_login_attempts.pop(ip, None) 
                    return redirect('/admin')
                attempts['count'] += 1
                attempts['time'] = now
                admin_login_attempts[ip] = attempts
                return swal_back("Từ Chối", f"Sai mật khẩu! Bạn còn {5 - attempts['count']} lần thử.", "error")
            
        return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><title>Admin Đăng Nhập</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>{CSS_GLASS} .inp-neon {{ background: rgba(0,0,0,0.5); border: 1px solid rgba(0,255,204,0.3); color: #00ffcc; padding: 12px; border-radius: 8px; width: 100%; margin-bottom: 15px; text-align: center; }} .inp-neon:focus {{ border-color: #00ffcc; outline:none; }}</style></head><body style="background:#0b0f19; display:flex; justify-content:center; align-items:center; height:100vh;"><div class="glass-panel mx-auto" style="max-width:400px;"><h2 class="text-neon mb-4"><i class="fas fa-user-shield"></i> LVT ADMIN</h2><form method="POST"><input type="text" name="username" class="inp-neon" placeholder="Tài khoản" required><input type="password" name="password" class="inp-neon" placeholder="Mật Khẩu" required><button type="submit" class="btn-neon mt-2"><i class="fas fa-sign-in-alt"></i> VÀO HỆ THỐNG</button></form><a href="/" class="d-block mt-3 text-secondary text-decoration-none"><i class="fas fa-arrow-left"></i> Về trang khách</a></div></body></html>'''
    except Exception as e: return f"LỖI: {str(e)}", 200

# TRANG 1: QUẢN LÝ KEY
@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    token_url = session.get("csrf_token", "")
    csrf_input = f'<input type="hidden" name="csrf_token" value="{token_url}">'
    
    keys_items = list(db.get("keys", {}).items())
    now_ms = int(time.time() * 1000)
    keys_html = ''
    for k, data in sorted(keys_items, key=lambda x: x[1].get('exp', 0) if isinstance(x[1].get('exp'), int) else 9999999999999, reverse=True):
        st = data.get('status', 'active')
        ban_until = data.get("ban_until", 0)
        note = escape(data.get("note", ""))
        
        if st == "banned":
            if ban_until == "permanent" or (isinstance(ban_until, int) and ban_until > now_ms): is_banned = True
            else: is_banned = False; data["status"] = "active" 
        else: is_banned = False

        status_badge = '<span class="badge bg-danger">Khóa</span>' if is_banned else '<span class="badge bg-success">Sống</span>'
        ban_btn = f'<a href="/admin/action/unban/{escape(str(k))}?csrf_token={token_url}" class="action-btn text-success"><i class="fas fa-unlock"></i></a>' if is_banned else f'<button class="action-btn text-danger" onclick="openBanModal(\'{escape(str(k))}\')"><i class="fas fa-ban"></i></button>'
        vip_badge = '<span class="badge bg-warning text-dark"><i class="fas fa-crown"></i> VIP</span>' if data.get('vip') else ''
        
        if data.get('exp') == 'pending': exp_text = '<span class="badge bg-info text-dark">Chưa kích hoạt</span>'
        elif data.get('exp') == 'permanent': exp_text = '<span class="text-success fw-bold">Vĩnh Viễn</span>'
        else:
            is_expired = now_ms > data.get('exp', 0)
            exp_text = f'<span class="{"text-danger fw-bold" if is_expired else "text-light"}">{time.strftime("%d/%m/%y %H:%M", time.localtime(data.get("exp", 0) / 1000))}</span>'
        
        safe_k = escape(str(k))
        keys_html += f'''<tr class="key-row">
        <td><div class="fw-bold text-info font-monospace" style="cursor:pointer;" onclick="navigator.clipboard.writeText('{safe_k}'); alert('Copied!')">{safe_k}</div>{vip_badge} {status_badge}<br><small class="text-muted">{note}</small></td>
        <td>{exp_text}</td>
        <td><span class="badge bg-dark border p-2">{len(data.get('devices', []))}/{data.get('maxDevices', 1)}</span></td>
        <td>
            <div class="d-flex gap-1 justify-content-center">
                <button class="action-btn text-primary" onclick="openNoteModal('{safe_k}', '{note}')"><i class="fas fa-sticky-note"></i></button>
                <button class="action-btn text-info" onclick="openAddTimeModal('{safe_k}')"><i class="fas fa-clock"></i></button>
                <a href="/admin/action/reset_dev/{safe_k}?csrf_token={token_url}" class="action-btn text-warning" onclick="return confirm('Reset thiết bị?')"><i class="fas fa-sync-alt"></i></a>
                {ban_btn}
                <a href="/admin/action/delete/{safe_k}?csrf_token={token_url}" class="action-btn text-muted" onclick="return confirm('Xóa?')"><i class="fas fa-trash"></i></a>
            </div>
        </td></tr>'''

    content = f'''
    <div class="row g-4 mb-4">
        <div class="col-xl-4"><div class="card h-100" style="border-top:4px solid #22c55e;"><div class="card-header text-success">Tạo Key</div><div class="card-body">
            <form action="/admin/create" method="POST" class="row g-3">{csrf_input}
                <div class="col-12"><select name="gen_type" class="form-select" onchange="document.getElementById('manual_box').style.display=this.value==='manual'?'block':'none'"><option value="auto">Tạo Ngẫu Nhiên</option><option value="manual">Tự Nhập Tên</option></select></div>
                <div class="col-12" id="manual_box" style="display:none;"><input type="text" name="manual_key" class="form-control" placeholder="Nhập Key..."></div>
                <div class="col-6"><input type="number" name="quantity" class="form-control" placeholder="Số lượng" value="1"></div>
                <div class="col-6"><input type="number" name="devices" class="form-control" placeholder="Thiết bị" value="1"></div>
                <div class="col-6"><input type="number" name="duration" class="form-control" placeholder="Thời gian" value="1"></div>
                <div class="col-6"><select name="type" class="form-select"><option value="minute">Phút</option><option value="hour">Giờ</option><option value="day" selected>Ngày</option><option value="permanent">Vĩnh Viễn</option></select></div>
                <div class="col-12"><button type="submit" class="btn-custom w-100" style="background:#22c55e;">Sản xuất Key</button></div>
            </form>
        </div></div></div>
        
        <div class="col-xl-8"><div class="card h-100" style="border-top:4px solid #38bdf8;"><div class="card-header text-info">Kho Key</div>
            <div class="card-body p-0"><div class="table-responsive" style="max-height: 400px; overflow-y:auto;"><table class="table table-hover text-center align-middle mb-0"><thead style="position: sticky; top: 0; z-index: 1;"><tr><th>Tên Key</th><th>Hạn</th><th>Thiết bị</th><th>Thao tác</th></tr></thead><tbody>{keys_html or '<tr><td colspan="4">Trống</td></tr>'}</tbody></table></div></div>
        </div></div>
    </div>
    
    <div class="modal fade" id="noteModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog"><div class="modal-content"><form action="/admin/edit_note" method="POST">{csrf_input}<div class="modal-header"><h5 class="modal-title">Ghi Chú</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><input type="hidden" name="key" id="noteKeyInput"><textarea name="note_text" id="noteInput" class="form-control"></textarea></div><div class="modal-footer"><button class="btn btn-primary w-100">Lưu</button></div></form></div></div></div>
    <div class="modal fade" id="addTimeModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog"><div class="modal-content"><form action="/admin/add_time" method="POST">{csrf_input}<div class="modal-header"><h5 class="modal-title">Cộng Giờ</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><input type="hidden" name="key" id="addTimeKeyInput"><div class="d-flex gap-2"><input type="number" name="time_val" class="form-control"><select name="time_unit" class="form-select"><option value="hours">Giờ</option><option value="days" selected>Ngày</option></select></div></div><div class="modal-footer"><button class="btn btn-info w-100 text-dark">Cộng</button></div></form></div></div></div>
    <div class="modal fade" id="banModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog"><div class="modal-content"><form action="/admin/custom_ban" method="POST">{csrf_input}<div class="modal-header"><h5 class="modal-title text-danger">Khóa Key</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><input type="hidden" name="key" id="banKeyInput"><select name="time_unit" class="form-select"><option value="permanent" selected>Vĩnh Viễn</option></select></div><div class="modal-footer"><button class="btn btn-danger w-100">Khóa</button></div></form></div></div></div>
    
    <script>
        function openNoteModal(key, note) {{ document.getElementById('noteKeyInput').value = key; document.getElementById('noteInput').value = note; new bootstrap.Modal(document.getElementById('noteModal')).show(); }}
        function openAddTimeModal(key) {{ document.getElementById('addTimeKeyInput').value = key; new bootstrap.Modal(document.getElementById('addTimeModal')).show(); }}
        function openBanModal(key) {{ document.getElementById('banKeyInput').value = key; new bootstrap.Modal(document.getElementById('banModal')).show(); }}
    </script>
    '''
    return render_admin_layout("LVT - Quản Lý Key", "keys", content, token_url)

# TRANG 2: NẠP FILE
@app.route('/admin/files')
def admin_files():
    if session.get('role') != 'admin': return redirect('/admin_login')
    csrf_input = f'<input type="hidden" name="csrf_token" value="{session.get("csrf_token", "")}">'
    content = f'''
    <div class="row g-4">
        <div class="col-md-6"><div class="card h-100" style="border-top: 4px solid #a855f7;"><div class="card-header text-purple">Script Tiêm Gốc</div><div class="card-body d-flex flex-column"><form action="/admin/update_script_tiem" method="POST">{csrf_input}<textarea name="script_text" class="form-control mb-3 flex-grow-1" rows="5" placeholder="Dán mã script JS vào đây..."></textarea><button type="submit" class="btn-custom w-100" style="background:#a855f7;">Lưu Script</button></form></div></div></div>
        <div class="col-md-6"><div class="card h-100" style="border-top: 4px solid #00ffcc;"><div class="card-header text-info">App WebView (.HTML)</div><div class="card-body d-flex flex-column"><form action="/admin/update_webview" method="POST">{csrf_input}<textarea name="webview_text" class="form-control mb-3 flex-grow-1" rows="5" placeholder="Dán HTML vào đây..."></textarea><button type="submit" class="btn-custom w-100" style="background:#00ffcc; color:#000;">Lưu Giao Diện</button></form></div></div></div>
    </div>'''
    return render_admin_layout("LVT - Nạp File", "files", content, session.get("csrf_token", ""))

# TRANG 3: QUẢN LÝ GAME (TÍNH NĂNG MỚI THEO YÊU CẦU)
@app.route('/admin/games')
def admin_games():
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    token_url = session.get("csrf_token", "")
    csrf_input = f'<input type="hidden" name="csrf_token" value="{token_url}">'
    
    layma_token = db.get("settings", {}).get("layma_api", "")
    games = db.get("games", {})
    
    games_html = ""
    for g_id, g in games.items():
        games_html += f'''
        <tr>
            <td class="fw-bold text-success">{escape(g.get('name', ''))}</td>
            <td>{g.get('devices', 1)}</td>
            <td><span class="badge bg-warning text-dark">{g.get('passes', 1)} Lần</span></td>
            <td>{g.get('duration_hours', 24)}h</td>
            <td>{g.get('max_keys', 100)}</td>
            <td><a href="/admin/action_game/delete/{g_id}?csrf_token={token_url}" class="btn btn-sm btn-danger" onclick="return confirm('Xóa game này?')"><i class="fas fa-trash"></i></a></td>
        </tr>'''

    content = f'''
    <div class="row g-4 mb-4">
        <div class="col-12"><div class="card" style="border-top:4px solid #f59e0b;"><div class="card-header text-warning"><i class="fas fa-link"></i> API Rút Gọn Link (layma.net)</div><div class="card-body">
            <form action="/admin/save_layma_api" method="POST" class="d-flex gap-2">{csrf_input}
                <input type="text" name="layma_api" class="form-control" value="{escape(layma_token)}" placeholder="Nhập API Token lấy từ web rút gọn (Ví dụ: 4f62901315a7381...)">
                <button type="submit" class="btn-custom" style="background:#f59e0b; white-space:nowrap;">Lưu API</button>
            </form>
            <small class="text-muted mt-2 d-block">* API này để tự động tạo link rút gọn cho khách vượt. Nếu để trống hệ thống sẽ bỏ qua bước rút gọn.</small>
        </div></div></div>
    </div>
    
    <div class="row g-4">
        <div class="col-xl-4"><div class="card h-100" style="border-top:4px solid #10b981;"><div class="card-header text-success"><i class="fas fa-plus"></i> Thêm Cấu Hình Game Mới</div><div class="card-body">
            <form action="/admin/create_game" method="POST" class="row g-3">{csrf_input}
                <div class="col-12"><label class="small text-muted">Tên Game hiển thị</label><input type="text" name="name" class="form-control" placeholder="Ví dụ: PUBG MOBILE" required></div>
                <div class="col-6"><label class="small text-muted">Số Thiết Bị</label><input type="number" name="devices" class="form-control" value="1" min="1" required></div>
                <div class="col-6"><label class="small text-muted">Số Lần Vượt Rút Gọn</label><input type="number" name="passes" class="form-control" value="2" min="0" required></div>
                <div class="col-6"><label class="small text-muted">Hạn Key (Giờ)</label><input type="number" name="duration_hours" class="form-control" value="24" min="1" required></div>
                <div class="col-6"><label class="small text-muted">Giới Hạn Số Key Tối Đa</label><input type="number" name="max_keys" class="form-control" value="100" min="1" required></div>
                <div class="col-12"><button type="submit" class="btn-custom w-100" style="background:#10b981;">Lưu Cấu Hình Mới</button></div>
            </form>
        </div></div></div>
        
        <div class="col-xl-8"><div class="card h-100" style="border-top:4px solid #3b82f6;"><div class="card-header text-primary"><i class="fas fa-list"></i> Danh Sách Game Cho Phép Get Key</div>
            <div class="card-body p-0"><div class="table-responsive"><table class="table table-hover text-center align-middle mb-0">
                <thead><tr><th>Tên Game</th><th>Thiết Bị</th><th>Vượt Link</th><th>TG Key</th><th>Kho Key Tối Đa</th><th>Xóa</th></tr></thead>
                <tbody>{games_html or '<tr><td colspan="6" class="text-muted py-4">Chưa có Game nào. Vui lòng thêm bên trái!</td></tr>'}</tbody>
            </table></div></div>
        </div></div>
    </div>
    '''
    return render_admin_layout("LVT - Quản Lý Game", "games", content, token_url)

@app.route('/admin/save_layma_api', methods=['POST'])
def save_layma_api():
    if session.get('role') != 'admin': return redirect('/admin_login')
    api_val = request.form.get('layma_api', '').strip()
    db = load_db()
    with db_lock:
        db.setdefault("settings", {})["layma_api"] = api_val
        save_db(db)
    return redirect('/admin/games')

@app.route('/admin/create_game', methods=['POST'])
def create_game():
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    g_id = "g_" + secrets.token_hex(4)
    with db_lock:
        db.setdefault("games", {})[g_id] = {
            "name": request.form.get('name', 'Game').strip(),
            "devices": safe_int(request.form.get('devices', 1)),
            "passes": safe_int(request.form.get('passes', 1)),
            "duration_hours": safe_int(request.form.get('duration_hours', 24)),
            "max_keys": safe_int(request.form.get('max_keys', 100))
        }
        save_db(db)
    return redirect('/admin/games')

@app.route('/admin/action_game/delete/<game_id>')
def delete_game(game_id):
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    with db_lock:
        if game_id in db.get("games", {}):
            del db["games"][game_id]
            save_db(db)
    return redirect('/admin/games')

# Các API POST xử lý thao tác (Đã rút gọn giữ cốt lõi)
@app.route('/admin/create', methods=['POST'])
def admin_create():
    if session.get('role') != 'admin': return redirect('/admin_login')
    dur = safe_int(request.form.get('duration'))
    md = safe_int(request.form.get('devices'), 1)
    qty = safe_int(request.form.get('quantity'), 1)
    t = request.form.get('type')
    gen_type = request.form.get('gen_type', 'auto')
    manual_key = request.form.get('manual_key', '').strip()
    db = load_db()
    with db_lock:
        if gen_type == 'manual' and manual_key:
            db["keys"][manual_key] = {"exp": "pending", "maxDevices": md, "devices": [], "vip": False, "status": "active", "bound_olm": "", "ban_until": 0, "note": ""}
            if t != 'permanent': db["keys"][manual_key]["durationMs"] = dur * {"minute":60000, "hour":3600000, "day":86400000}.get(t, 60000)
            else: db["keys"][manual_key]["exp"] = "permanent"
        else:
            for _ in range(qty):
                nk = generate_proxy_key()
                db["keys"][nk] = {"exp": "pending", "maxDevices": md, "devices": [], "vip": False, "status": "active", "bound_olm": "", "ban_until": 0, "note": ""}
                if t != 'permanent': db["keys"][nk]["durationMs"] = dur * {"minute":60000, "hour":3600000, "day":86400000}.get(t, 60000)
                else: db["keys"][nk]["exp"] = "permanent"
        save_db(db)
    return redirect('/admin')

@app.route('/admin/edit_note', methods=['POST'])
def admin_edit_note():
    db = load_db()
    with db_lock:
        key = request.form.get('key', '')
        if key in db.get("keys", {}): db["keys"][key]["note"] = request.form.get('note_text', ''); save_db(db)
    return redirect('/admin')

@app.route('/admin/add_time', methods=['POST'])
def admin_add_time():
    db = load_db()
    with db_lock:
        key = request.form.get('key', '')
        t_val = safe_int(request.form.get('time_val', 0))
        t_unit = request.form.get('time_unit', 'days')
        if key in db.get("keys", {}):
            kd = db["keys"][key]
            if kd.get("exp") != "permanent":
                ms = t_val * (3600000 if t_unit == 'hours' else 86400000)
                if kd.get("exp") == "pending": kd["durationMs"] = kd.get("durationMs", 0) + ms
                else: kd["exp"] = max(kd.get("exp", int(time.time()*1000)), int(time.time()*1000)) + ms
                save_db(db)
    return redirect('/admin')

@app.route('/admin/custom_ban', methods=['POST'])
def admin_custom_ban():
    db = load_db()
    with db_lock:
        key = request.form.get('key', '')
        if key in db.get("keys", {}): db["keys"][key]["status"] = "banned"; db["keys"][key]["ban_until"] = "permanent"; save_db(db)
    return redirect('/admin')

@app.route('/admin/update_script_tiem', methods=['POST'])
def admin_update_script_tiem():
    db = load_db()
    with db_lock: db.setdefault("settings", {})["script_tiem"] = request.form.get('script_text', ''); save_db(db)
    return redirect('/admin/files')

@app.route('/admin/update_webview', methods=['POST'])
def admin_update_webview():
    db = load_db()
    with db_lock: db.setdefault("settings", {})["app_webview_code"] = request.form.get('webview_text', ''); save_db(db)
    return redirect('/admin/files')

@app.route('/admin/action/<action>/<key>')
def key_actions(action, key):
    db = load_db()
    with db_lock:
        if key in db.get("keys", {}):
            if action == 'delete': db["keys"].pop(key, None)
            elif action == 'unban': db["keys"][key]['status'] = 'active'; db["keys"][key]['ban_until'] = 0
            elif action == 'reset_dev': db["keys"][key]['devices'] = []
            save_db(db)
    return redirect('/admin')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/admin_login')

try:
    init_db = load_db()
    app.secret_key = os.environ.get('SECRET_KEY', init_db.get("settings", {}).get("secret_key", secrets.token_hex(32)))
except: app.secret_key = secrets.token_hex(32)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
