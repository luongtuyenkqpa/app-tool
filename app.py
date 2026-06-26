import os, json, time, random, hashlib, threading, requests, shutil, base64, secrets, hmac, string, copy, traceback, ssl, re
import urllib.parse
from html import escape
from flask import Flask, request, jsonify, redirect, make_response, session, abort, send_file, render_template_string
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

try:
    os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
    time.tzset()
except: pass

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

CSS_GLASS = """
body { background: #f4f6f9; color: #1e293b; font-family: 'Inter', sans-serif; }
.glass-panel { background: rgba(255, 255, 255, 0.85); backdrop-filter: blur(15px); border: 1px solid rgba(255, 255, 255, 0.6); border-radius: 16px; padding: 35px; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05); text-align: center; }
.text-neon { color: #0f172a; font-weight: 800; text-shadow: none; }
.btn-neon { background: linear-gradient(135deg, #1e293b, #0f172a); border: none; color: #ffffff; font-weight: bold; padding: 14px 20px; border-radius: 10px; width: 100%; transition: 0.3s; text-transform: uppercase; cursor: pointer; letter-spacing: 0.5px; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.15); }
.btn-neon:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(15, 23, 42, 0.25); background: linear-gradient(135deg, #334155, #1e293b); }
"""

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8714375866:AAG9r0aCCFOKtgR6B-LcFYBAnJ7x9yMs-8o")
TELEGRAM_CHAT_ID = "7363320876"
WEB_URL = "https://app-tool-trlp.onrender.com" 

def send_telegram_event(event_type, data):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    def _send():
        try:
            session_req = requests.Session()
            msg = ""
            
            if event_type == "create":
                msg = f"🌟 <b>KEY VỪA ĐƯỢC TẠO</b> 🌟\n\n🔑 <code>{escape(str(data.get('key')))}</code>\n⏳ Hạn: {escape(str(data.get('exp')))}\n📱 Thiết bị tối đa: {escape(str(data.get('max_dev')))}"
            elif event_type == "banned":
                msg = f"🚫 <b>CẢNH BÁO: KEY BỊ BAND</b> 🚫\n\n🔑 Key: <code>{escape(str(data.get('key')))}</code>\n🌐 IP Vi phạm: {escape(str(data.get('ip')))}"
            elif event_type == "expired":
                msg = f"⚠️ <b>THÔNG BÁO: KEY HẾT HẠN</b> ⚠️\n\n🔑 Key: <code>{escape(str(data.get('key')))}</code>\n🌐 IP Khách: {escape(str(data.get('ip')))}"
            elif event_type == "limit":
                msg = f"📵 <b>CẢNH BÁO: VƯỢT QUÁ THIẾT BỊ</b> 📵\n\n🔑 Key: <code>{escape(str(data.get('key')))}</code>\n🌐 IP Đăng nhập: {escape(str(data.get('ip')))}"
            elif event_type == "login":
                msg = f"✅ <b>ĐĂNG NHẬP THÀNH CÔNG</b> ✅\n\n🔑 Key: <code>{escape(str(data.get('key')))}</code>\n🌐 IP Máy Khách: {escape(str(data.get('ip')))}\n📱 Tên Máy: {escape(str(data.get('device_name')))}\n🤖 Phiên bản: {escape(str(data.get('android_version')))}"
            elif event_type == "bypass_success":
                msg = f"🎉 <b>KHÁCH VỪA VƯỢT LINK THÀNH CÔNG</b> 🎉\n\n🎮 Game: {escape(str(data.get('game')))}\n🔑 Key VIP: <code>{escape(str(data.get('key')))}</code>\n⏱️ Thời hạn: {escape(str(data.get('hours')))}\n🌐 IP: {escape(str(data.get('ip')))}"

            if not msg: return
            
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
            headers = {"User-Agent": "LVT-Core-Encrypted-Server/3.0", "X-Security-Cipher": secrets.token_hex(32)}
            session_req.post(url, json=payload, headers=headers, timeout=15, verify=True)
        except Exception: pass
    threading.Thread(target=_send, daemon=True).start()

def send_telegram_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    def _send_alert():
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": f"🚨 <b>[GIÁM SÁT HỆ THỐNG]</b> 🚨\n\n{message}", "parse_mode": "HTML"}
            requests.post(url, json=payload, timeout=10)
        except Exception: pass
    threading.Thread(target=_send_alert, daemon=True).start()

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
                    except Exception: pass
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
                if os.path.exists(DB_FILE):
                    with open(DB_FILE, 'rb') as f:
                        res = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"📦 BACKUP DATABASE LVT TOOL\nThời gian: {time.strftime('%d/%m/%Y %H:%M:%S')}\n\nLưu ý: Dùng file này để Khôi Phục Dữ Liệu trên Web Admin nếu Server bị tắt ngang."}, files={"document": f}, timeout=15).json()
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
                        user_first_name = msg.get("from", {}).get("first_name", "Khách hàng")
                        if text.startswith("/start"):
                            if re.search(r'[\u0400-\u04FF\u0500-\u052F\u0600-\u06FF\u0750-\u077F]', user_first_name):
                                try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage", json={"chat_id": chat_id, "message_id": msg_id})
                                except: pass
                                continue
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage", json={"chat_id": chat_id, "message_id": msg_id})
                            welcome = f"🌟 <b>HỆ THỐNG CẤP PROXY OLM TỰ ĐỘNG</b> 🌟\n\nXin chào <b>{escape(user_first_name)}</b>!\nTruy cập Link Web để tự động cấu hình Proxy & Script:"
                            keyboard = {"inline_keyboard": [[{"text": "🚀 MỞ MINI APP QUẢN LÝ PROXY", "web_app": {"url": f"{WEB_URL}/proxy"}}]]}
                            requests.post(url_base + "/sendMessage", json={"chat_id": chat_id, "text": welcome, "parse_mode": "HTML", "reply_markup": keyboard})
        except Exception: pass
        time.sleep(2)

threading.Thread(target=telegram_polling, daemon=True).start()

def keep_awake():
    time.sleep(10)
    send_telegram_alert("🟢 <b>Hệ thống giám sát bảo mật liên tục 24/7 đã kích hoạt thành công!</b>")
    while True:
        try:
            headers = {"User-Agent": "LVT-Core-KeepAlive/3.0"}
            requests.get(f"http://127.0.0.1:{os.environ.get('PORT', 5000)}/ping", headers=headers, timeout=5)
            requests.get(WEB_URL, headers=headers, timeout=10)
        except Exception as e:
            pass
        time.sleep(5 * 60)

threading.Thread(target=keep_awake, daemon=True).start()

@app.route('/ping')
def ping_server(): return "OK", 200

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException): return e
    err_trace = traceback.format_exc()
    send_telegram_alert(f"⚠️ <b>SERVER PHÁT SINH LỖI NỘI BỘ (ANTI-CRASH CỨU NGUY):</b>\n<code>{escape(str(e))}</code>\n\n<b>Chi tiết lỗi:</b>\n<code>{escape(err_trace[:500])}</code>")
    return f"""<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Server Updating</title><style>body {{ background: #f8fafc; color: #0f172a; display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100vh; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; margin: 0; }} .loader {{ border: 5px solid rgba(15, 23, 42, 0.1); border-top: 5px solid #0f172a; border-radius: 50%; width: 60px; height: 60px; animation: spin 1s linear infinite; margin-bottom: 20px; box-shadow: 0 0 15px rgba(0,0,0,0.05); }} @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }} h2 {{ letter-spacing: 1px; }}</style></head><body><div class="loader"></div><h2>Đang update online server vui lòng đợi...</h2></body></html>""", 500

app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024 
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True      
app.config['SESSION_COOKIE_HTTPONLY'] = True    

DB_FILE = './database.json'
DB_BACKUP = './database.backup.json'

db_lock = threading.RLock()
api_rate_lock = threading.Lock()
admin_login_lock = threading.Lock() 

active_sessions = {}
api_rate_cache = {}
used_signatures = {} 
admin_login_attempts = {}

bypass_sessions = {}

GLOBAL_DB = {}
_last_db_mtime = 0
_last_mtime_check = 0 

def safe_int(val, default=0):
    try: return int(val)
    except: return default

def hash_pwd(pwd): return hashlib.sha256(pwd.encode()).hexdigest()
def escape_swal(text): return str(text).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

def swal_redirect(title, text, icon, url):
    return f"""<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #f4f6f9; }}</style></head><body><script>Swal.fire({{ title: {json.dumps(title)}, html: {json.dumps(text)}, icon: {json.dumps(icon)}, background: '#ffffff', color: '#1e293b', confirmButtonColor: '#0f172a', allowOutsideClick: false }}).then(() => {{ window.location.href = {json.dumps(url)}; }});</script></body></html>"""

def swal_back(title, text, icon):
    return f"""<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #f4f6f9; }}</style></head><body><script>Swal.fire({{ title: {json.dumps(title)}, html: {json.dumps(text)}, icon: {json.dumps(icon)}, background: '#ffffff', color: '#1e293b', confirmButtonColor: '#0f172a', allowOutsideClick: false }}).then(() => {{ window.history.back(); }});</script></body></html>"""

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
                    print(f"Cảnh báo: File DB chính bị hỏng ({e}). Tự động phục hồi từ Backup!")
                    if os.path.exists(DB_BACKUP):
                        try:
                            with open(DB_BACKUP, 'r', encoding='utf-8') as f: data = json.load(f)
                        except Exception: pass

            if not data: data = {"users": {}, "keys": {}, "banned_ips": [], "settings": {}}
            try:
                data.setdefault("users", {})
                data.setdefault("keys", {})
                data.setdefault("banned_ips", [])
                data.setdefault("settings", {})
                
                if "secret_key" not in data["settings"]: data["settings"]["secret_key"] = secrets.token_hex(32)
                if "termux_script" not in data["settings"]: data["settings"]["termux_script"] = ""
                if "script_tiem" not in data["settings"]: data["settings"]["script_tiem"] = ""
                if "vm_loader" not in data["settings"]: data["settings"]["vm_loader"] = ""
                if "app_webview_code" not in data["settings"]: data["settings"]["app_webview_code"] = ""
                if "tg_admins" not in data["settings"]: data["settings"]["tg_admins"] = [TELEGRAM_CHAT_ID]
                if "webview_maintenance" not in data["settings"]: data["settings"]["webview_maintenance"] = False
                
                if "games_list" not in data["settings"]: data["settings"]["games_list"] = "PUBG, LIENQUAN, FREEFIRE"
                if "shortlink_api_url" not in data["settings"]: data["settings"]["shortlink_api_url"] = "https://api.layma.net/api/admin/shortlink/quicklink"
                if "shortlink_api_token" not in data["settings"]: data["settings"]["shortlink_api_token"] = "4f62901315a7381c321f76bc988ff0e3"

                if "proxy_yaml" not in data["settings"]: data["settings"]["proxy_yaml"] = ""
                if "msg_login" not in data["settings"]: data["settings"]["msg_login"] = "VUI LÒNG KÍCH HOẠT KEY ĐỂ VÀO GAME!"
                if "msg_ingame" not in data["settings"]: data["settings"]["msg_ingame"] = "SẴN SÀNG CHIẾN ĐẤU - KEY ĐANG HOẠT ĐỘNG"

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
            except Exception: pass
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
        except Exception as e: print(f"Lỗi lưu Database: {e}") 

def generate_proxy_key():
    return ''.join(secrets.choice(string.ascii_lowercase) for _ in range(15))

def garbage_collector():
    global bypass_sessions
    while True:
        time.sleep(3600) 
        now_ms = int(time.time() * 1000)
        now_sec = time.time()
        try:
            stale_sessions = [k for k, v in bypass_sessions.items() if now_sec - v.get("time", 0) > 3600]
            for k in stale_sessions: bypass_sessions.pop(k, None)

            db = load_db()
            changed = False
            with db_lock:
                for k in list(db.get("keys", {}).keys()):
                    exp = db["keys"][k].get("exp")
                    if exp != "permanent" and exp != "pending":
                        if isinstance(exp, int) and (now_ms - exp) > 604800000:
                            del db["keys"][k]
                            changed = True
            if changed: save_db(db)
        except Exception: pass

threading.Thread(target=garbage_collector, daemon=True).start()

def get_real_ip(): return request.headers.get('CF-Connecting-IP') or request.remote_addr or "Unknown_IP"

@app.before_request
def firewall_and_csrf():
    try:
        db = load_db()
        banned_ips = set(db.get("banned_ips", []))
        ip = get_real_ip()
        if ip in banned_ips: return "⚠️ BẠN ĐÃ BỊ TỪ CHỐI TRUY CẬP BỞI HỆ THỐNG FIREWALL LVT.", 403
        
        if request.path == '/ping' or ip == '127.0.0.1' or ip == 'localhost':
            return

        ua = (request.headers.get('User-Agent') or '').lower()
        
        if 'lvt-core-keepalive' in ua:
            return

        blocked_bots = ['curl', 'postman', 'python', 'nmap', 'sqlmap', 'masscan', 'zgrab', 'wget', 'urllib', 'nikto']
        if any(bot in ua for bot in blocked_bots): 
            send_telegram_alert(f"🛡️ <b>Tường lửa chặn công cụ quét độc hại!</b>\n🌐 IP: <code>{ip}</code>\n🤖 User-Agent: <code>{escape(ua)}</code>")
            return "Firewall Blocked.", 403
            
        if request.path.startswith("/admin") and request.path not in ["/admin_login"]:
            if session.get('role') != 'admin': return redirect('/admin_login')
            if request.method == 'POST':
                if request.form.get("csrf_token") != session.get('csrf_token'): return "Lỗi CSRF Token (POST)", 403
            elif request.method == 'GET' and ('/admin/action/' in request.path or '/admin/unban_ip/' in request.path):
                if request.args.get("csrf_token") != session.get('csrf_token'): return "Lỗi CSRF Token (GET Action bị chặn)", 403
    except: pass

@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN' 
    return response

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
                    if ban_until == "permanent" or (isinstance(ban_until, int) and ban_until > now):
                        return jsonify({"banned": True, "reason": "Key của bạn đã bị Admin khóa. Bạn đã bị kick khỏi hệ thống!", "ban_time": ban_until})
                    else:
                        v["status"] = "active"
                        save_db(db)
                        return jsonify({"banned": False})
    return jsonify({"banned": False})

@app.route('/api/proxy/status', methods=['GET', 'POST'])
def check_proxy_status():
    key = request.values.get('key', '').strip()
    db = load_db()
    now = int(time.time() * 1000)
    
    settings = db.get("settings", {})
    msg_login = settings.get("msg_login", "VUI LÒNG KÍCH HOẠT KEY ĐỂ VÀO GAME!")
    msg_ingame = settings.get("msg_ingame", "SẴN SÀNG CHIẾN ĐẤU - KEY ĐANG HOẠT ĐỘNG")
    
    if not key or key not in db.get("keys", {}):
        return jsonify({"status": "invalid", "message": msg_login, "ingame_message": ""})
        
    kd = db["keys"][key]
    
    duration_ms = kd.get("durationMs", 0)
    exp_val = kd.get("exp")
    
    if kd.get("status") == "banned":
        ban_until = kd.get("ban_until", "permanent")
        if ban_until == "permanent" or (isinstance(ban_until, int) and ban_until > now): 
            return jsonify({"status": "banned", "message": "Key đã bị cấm!", "ingame_message": "", "exp": exp_val, "durationMs": duration_ms})
        
    if kd.get("exp") != "permanent" and kd.get("exp") != "pending" and kd.get("exp", 0) < now: 
        return jsonify({"status": "expired", "message": msg_login, "ingame_message": "", "exp": exp_val, "durationMs": duration_ms})
        
    return jsonify({
        "status": "active", 
        "message": msg_login, 
        "ingame_message": msg_ingame,
        "yaml_url": f"{WEB_URL}/api/proxy.yaml?key={key}",
        "exp": exp_val,
        "durationMs": duration_ms
    })

@app.route('/api/proxy.yaml')
def download_proxy_yaml():
    key = request.args.get('key', '').strip()
    db = load_db()
    now = int(time.time() * 1000)
    
    blocker_yaml = "port: 7890\nsocks-port: 7891\nallow-lan: true\nmode: rule\nlog-level: info\nproxies: []\nproxy-groups: []\nrules:\n  - MATCH, REJECT\n"
    
    if not key or key not in db.get("keys", {}):
        resp = make_response(f"# CẢNH BÁO: KEY KHÔNG HỢP LỆ VUI LÒNG KIỂM TRA LẠI\n{blocker_yaml}")
        resp.headers['Content-Type'] = 'text/yaml; charset=utf-8'
        return resp
        
    kd = db["keys"][key]
    if kd.get("status") == "banned":
        resp = make_response(f"# CẢNH BÁO: KEY NÀY ĐÃ BỊ ADMIN KHÓA\n{blocker_yaml}")
        resp.headers['Content-Type'] = 'text/yaml; charset=utf-8'
        return resp
        
    if kd.get("exp") != "permanent" and kd.get("exp") != "pending" and kd.get("exp", 0) < now: 
        resp = make_response(f"# CẢNH BÁO: KEY ĐÃ HẾT HẠN\n{blocker_yaml}")
        resp.headers['Content-Type'] = 'text/yaml; charset=utf-8'
        return resp
        
    yaml_content = db.get("settings", {}).get("proxy_yaml", "")
    yaml_content = yaml_content.replace("{KEY}", key)
    
    resp = make_response(yaml_content)
    resp.headers['Content-Type'] = 'text/yaml; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename="LVT_{key}.yaml"'
    return resp

@app.route('/api/termux')
def get_termux_script():
    key = request.args.get('key', '').strip()
    db = load_db()
    script = db.get("settings", {}).get("termux_script", "")
    
    # Hỗ trợ replace các placeholder tự động
    script = script.replace("{WEB_URL}", WEB_URL).replace("{KEY}", key)
    
    resp = make_response(script)
    resp.headers['Content-Type'] = 'text/plain; charset=utf-8'
    return resp

@app.route('/api/get_script')
def serve_custom_script():
    db = load_db()
    user_script = db.get("settings", {}).get("script_tiem", "")
    kick_payload = f"""
    (function() {{
        setInterval(function() {{
            fetch('{WEB_URL}/api/check_ban_status', {{cache: 'no-store'}})
            .then(r => r.json())
            .then(d => {{
                if(d.banned) {{
                    localStorage.removeItem('lvt_proxy_key');
                    alert("⚠️ LVT HỆ THỐNG: " + d.reason);
                    window.location.href = "https://google.com";
                }}
            }}).catch(e => {{}});
        }}, 10000); 
    }})();
    """
    resp = make_response(kick_payload + "\n" + user_script)
    resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    return resp

@app.route('/api/vm_payload')
def get_vm_payload():
    db = load_db()
    script = db.get("settings", {}).get("vm_loader", "")
    resp = make_response(script)
    resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    return resp

@app.route('/api/download_pak')
def download_pak():
    pak_path = './uploaded.pak'
    if not os.path.exists(pak_path): return "File không tồn tại trên hệ thống", 404
    return send_file(pak_path, as_attachment=True, download_name='data.pak')

@app.route('/webview')
def serve_webview_app():
    db = load_db()
    is_maintenance = db.get("settings", {}).get("webview_maintenance", False)
    
    if is_maintenance:
        html_content = f"""<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>App Maintenance</title><style>body {{ background: #f8fafc; color: #0f172a; display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100vh; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; margin: 0; }} .pulse {{ width: 70px; height: 70px; background: #0f172a; border-radius: 50%; animation: pulse-anim 2s infinite; margin-bottom: 20px; box-shadow: 0 0 20px rgba(15, 23, 42, 0.2); }} @keyframes pulse-anim {{ 0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(15, 23, 42, 0.4); }} 70% {{ transform: scale(1); box-shadow: 0 0 0 20px rgba(15, 23, 42, 0); }} 100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(15, 23, 42, 0); }} }} h2 {{ letter-spacing: 1px; }} p {{ color: #64748b; font-size: 14px; margin-top: 5px; }}</style></head><body><div class="pulse"></div><h2>Đang update online app</h2><p>Hệ thống đang được nâng cấp, vui lòng quay lại sau!</p></body></html>"""
    else:
        html_content = db.get("settings", {}).get("app_webview_code", "<h1>Hệ thống chưa được nạp giao diện WebView. Vui lòng liên hệ Admin!</h1>")
        
        auto_check_script = f"""
        <script>
            (function() {{
                const checkInterval = 8000;
                let isLobbyLocked = false;
                let errorCount = 0;
                
                function createLobbyOverlay(msg) {{
                    if(document.getElementById('lvt-lobby-lock')) return;
                    let overlay = document.createElement('div');
                    overlay.id = 'lvt-lobby-lock';
                    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);z-index:999999;display:flex;flex-direction:column;justify-content:center;align-items:center;color:#fff;font-family:sans-serif;text-align:center;padding:20px;backdrop-filter:blur(10px);';
                    overlay.innerHTML = '<h2 style="color:#ef4444;margin-bottom:15px;text-transform:uppercase;">CẢNH BÁO HỆ THỐNG</h2><p style="font-size:18px;line-height:1.5;" id="lvt-msg-content">' + msg + '</p><button onclick="window.location.reload()" style="margin-top:20px;padding:10px 20px;background:#ef4444;color:#fff;border:none;border-radius:8px;font-weight:bold;cursor:pointer;">TẢI LẠI TRANG</button>';
                    document.body.appendChild(overlay);
                    isLobbyLocked = true;
                }}
                
                function removeLobbyOverlay() {{
                    let overlay = document.getElementById('lvt-lobby-lock');
                    if(overlay) overlay.remove();
                    isLobbyLocked = false;
                }}
                
                setInterval(function() {{
                    let key = localStorage.getItem('lvt_proxy_key') || '';
                    if(!key) {{
                        let urlParams = new URLSearchParams(window.location.search);
                        key = urlParams.get('key') || '';
                    }}
                    
                    if(!key) return; 
                    
                    fetch('{WEB_URL}/api/proxy/status?key=' + key)
                    .then(r => r.json())
                    .then(d => {{
                        if(d.status !== 'active') {{
                            createLobbyOverlay(d.message);
                        }} else {{
                            if(isLobbyLocked) removeLobbyOverlay();
                            errorCount = 0;
                        }}
                    }}).catch(e => {{
                        errorCount++;
                        if(errorCount > 3 && isLobbyLocked) {{
                            document.getElementById('lvt-msg-content').innerText = "Mất kết nối máy chủ. Đang thử lại...";
                        }}
                    }});
                }}, checkInterval);
            }})();
        </script>
        """
        if "</body>" in html_content.lower():
            html_content = re.sub(r'</body>', auto_check_script + '\n</body>', html_content, flags=re.IGNORECASE)
        else:
            html_content += auto_check_script

    resp = make_response(html_content)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp

@app.route('/')
def get_key_portal():
    db = load_db()
    games_raw = db.get("settings", {}).get("games_list", "PUBG, LIENQUAN, FREEFIRE")
    games = [g.strip() for g in games_raw.split(',') if g.strip()]
    options_html = "".join([f'<option value="{escape(g)}">{escape(g)}</option>' for g in games])
    
    return f'''
    <!DOCTYPE html><html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
        <title>HELY - Hệ Thống GetKey</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
            html, body {{ background-color: #f5f5f5; font-family: 'Roboto', sans-serif; margin: 0; padding: 0; height: 100vh; width: 100vw; overflow-x: hidden; overflow-y: auto; position: relative; }}
            .navbar-custom {{ background-color: #0066ff; padding: 12px 16px; display: flex; flex-direction: column; position: relative; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .navbar-top {{ display: flex; justify-content: space-between; align-items: center; width: 100%; }}
            .brand-title {{ color: #ffffff; font-size: 22px; font-weight: 700; display: flex; align-items: center; gap: 8px; text-decoration: none; }}
            .brand-title img, .brand-title i {{ font-size: 22px; color: #ffffff; }}
            .menu-toggle-btn {{ background: transparent; border: 2px solid rgba(255,255,255,0.6); border-radius: 8px; padding: 6px 12px; color: white; font-size: 18px; cursor: pointer; }}
            .navbar-links {{ display: flex; flex-direction: column; gap: 12px; margin-top: 14px; padding-bottom: 5px; }}
            .nav-item-link {{ color: #ffffff; text-decoration: none; font-weight: 500; font-size: 15px; display: flex; align-items: center; gap: 8px; opacity: 0.95; }}
            .nav-item-link:hover {{ opacity: 1; }}
            .welcome-box {{ background-color: #e9e9e9; border-radius: 4px; padding: 14px 16px; margin: 16px; display: flex; justify-content: space-between; align-items: center; color: #333333; font-size: 15px; border: 1px solid #dddddd; }}
            .welcome-close {{ background: transparent; border: none; font-size: 18px; color: #666666; cursor: pointer; }}
            .search-box-container {{ margin: 0 16px 16px 16px; display: flex; justify-content: flex-end; align-items: center; gap: 6px; color: #666666; font-size: 14px; cursor: pointer; }}
            .getkey-card {{ background: #ffffff; border-radius: 0px; border: 1px solid #dddddd; margin: 0 16px 20px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
            .getkey-card-header {{ padding: 12px 16px; font-weight: 700; font-size: 16px; color: #111111; border-bottom: 1px solid #eeeeee; display: flex; align-items: center; gap: 8px; text-transform: uppercase; }}
            .getkey-card-body {{ padding: 20px 16px; }}
            .input-group-custom {{ display: flex; width: 100%; border: 1px solid #cccccc; border-radius: 6px; margin-bottom: 14px; background-color: #ffffff; overflow: hidden; }}
            .input-icon-prefix {{ background-color: #f0f0f0; width: 46px; display: flex; justify-content: center; align-items: center; color: #444444; border-right: 1px solid #cccccc; font-size: 16px; }}
            .select-custom, .control-custom {{ flex: 1; border: none !important; background: transparent !important; padding: 10px 12px; font-size: 15px; color: #111111; outline: none; font-weight: 400; }}
            .control-custom:disabled {{ background-color: #f8f8f8 !important; color: #555555; }}
            .input-device-text {{ background-color: #f0f0f0; padding: 0 16px; display: flex; align-items: center; color: #222222; font-weight: 400; font-size: 14px; border-left: 1px solid #cccccc; }}
            .action-buttons-group {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 20px; }}
            .btn-guide {{ background-color: #ffffff; color: #0066cc; border: 1px solid #0066cc; border-radius: 6px; padding: 10px; font-weight: 500; font-size: 14px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-decoration: none; line-height: 1.3; }}
            .btn-generate {{ background-color: #0055ff; color: #ffffff; border: none; border-radius: 6px; padding: 10px; font-weight: 500; font-size: 14px; display: flex; flex-direction: column; align-items: center; justify-content: center; box-shadow: 0 2px 4px rgba(0,85,255,0.2); cursor: pointer; }}
            .btn-generate span, .btn-guide span {{ font-size: 14px; }}
            .info-notice {{ font-size: 12px; color: #777777; text-align: center; margin: 15px 16px; line-height: 1.5; }}
            .footer-copyright {{ text-align: center; color: #777777; font-size: 13px; padding: 16px 0; border-top: 1px solid #e0e0e0; background-color: #f5f5f5; margin-top: auto; width: 100%; }}
        </style>
    </head>
    <body>

        <div class="navbar-custom">
            <div class="navbar-top">
                <a href="/" class="brand-title">
                    <i class="fas fa-layer-group"></i> HELY
                </a>
                <button class="menu-toggle-btn" onclick="toggleMenu()"><i class="fas fa-bars"></i></button>
            </div>
            <div class="navbar-links" id="navbarMenuLinks">
                <a href="/" class="nav-item-link"><i class="fas fa-gift"></i> Get Free Key</a>
                <a href="/proxy" class="nav-item-link"><i class="fas fa-rocket"></i> App Quản Lý Proxy (Cosmic)</a>
                <a href="/admin_login" class="nav-item-link"><i class="fas fa-sign-in-alt"></i> Login</a>
                <a href="#" class="nav-item-link"><i class="fas fa-user-plus"></i> Register</a>
            </div>
        </div>

        <div class="welcome-box" id="welcomeStrangerBox">
            <span>Welcome Stranger</span>
            <button class="welcome-close" onclick="closeWelcome()">&times;</button>
        </div>

        <div class="search-box-container">
            <i class="fas fa-search"></i> <span>Tra cứu đơn hàng VIP</span>
        </div>

        <div class="getkey-card">
            <div class="getkey-card-header">
                <i class="fas fa-gift"></i> Hệ thống GetKey
            </div>
            <div class="getkey-card-body">
                <form action="/start_bypass" method="POST">
                    
                    <div class="input-group-custom">
                        <div class="input-icon-prefix"><i class="fas fa-gamepad"></i></div>
                        <select name="game" class="select-custom" required>
                            <option value="" disabled selected>-- Chọn game --</option>
                            {options_html}
                        </select>
                    </div>

                    <div class="input-group-custom">
                        <div class="input-icon-prefix"><i class="fas fa-mobile-alt"></i></div>
                        <input type="text" class="control-custom" value="1" disabled>
                        <div class="input-device-text">Thiết bị</div>
                    </div>

                    <div class="input-group-custom">
                        <div class="input-icon-prefix"><i class="far fa-calendar-alt"></i></div>
                        <input type="text" class="control-custom" value="Bảo lưu tự động" disabled>
                    </div>

                    <div class="input-group-custom">
                        <div class="input-icon-prefix"><i class="far fa-gem"></i></div>
                        <select name="steps" class="select-custom" required>
                            <option value="1">FREE (Vượt quảng cáo gói 12H)</option>
                            <option value="2">FREE (Vượt quảng cáo gói 24H)</option>
                        </select>
                    </div>

                    <div class="action-buttons-group">
                        <a href="#" class="btn-guide">
                            <i class="far fa-question-circle mb-1" style="font-size: 16px;"></i>
                            <span>Hướng dẫn<br>GetKey</span>
                        </a>
                        <button type="submit" class="btn-generate">
                            <i class="fas fa-sign-in-alt mb-1" style="font-size: 16px;"></i>
                            <span>Generate</span>
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <div class="info-notice">
            <i class="fas fa-info-circle"></i> Chọn game và nhấn Generate để bắt đầu.<br>
            Thiết bị tối đa cho mỗi Key vượt link là 1 máy.
        </div>

        <div class="footer-copyright">
            &copy; 2026 - Hely.dev
        </div>

        <script>
            function toggleMenu() {{
                var menu = document.getElementById("navbarMenuLinks");
                if (menu.style.display === "none" || menu.style.display === "") {{
                    menu.style.display = "flex";
                }} else {{
                    menu.style.display = "none";
                }}
            }}
            function closeWelcome() {{
                document.getElementById("welcomeStrangerBox").style.display = "none";
            }}
        </script>
    </body>
    </html>
    '''

@app.route('/proxy')
def proxy_client_portal():
    return f'''
    <!DOCTYPE html><html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
        <title>HELY - Cosmic Proxy</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@500;700&display=swap');
            :root {{
                --neon-cyan: #00f3ff;
                --neon-purple: #bf00ff;
                --dark-space: #0b0f19;
                --glass-bg: rgba(20, 25, 45, 0.4);
            }}

            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            
            body {{
                background: radial-gradient(circle at 50% 50%, #1a233a 0%, var(--dark-space) 100%);
                color: #fff;
                font-family: 'Rajdhani', sans-serif;
                min-height: 100vh;
                overflow-x: hidden;
                position: relative;
            }}

            .stars {{
                position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 0;
            }}
            .star {{ position: absolute; background: #fff; border-radius: 50%; animation: twinkle linear infinite; }}
            @keyframes twinkle {{
                0% {{ opacity: 0.2; transform: scale(0.8); }}
                50% {{ opacity: 1; transform: scale(1.2); box-shadow: 0 0 10px #fff, 0 0 20px var(--neon-cyan); }}
                100% {{ opacity: 0.2; transform: scale(0.8); }}
            }}

            .app-container {{ position: relative; z-index: 10; padding: 20px; max-width: 500px; margin: 0 auto; min-height: 100vh; display: flex; flex-direction: column; }}

            .header-title {{ text-align: center; font-family: 'Orbitron', sans-serif; font-size: 28px; font-weight: 700; margin-bottom: 25px; margin-top: 10px; text-transform: uppercase; background: linear-gradient(90deg, var(--neon-cyan), var(--neon-purple)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-shadow: 0 0 20px rgba(0, 243, 255, 0.3); }}

            .tabs {{ display: flex; background: rgba(0,0,0,0.5); border-radius: 12px; padding: 5px; margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.1); }}
            .tab-btn {{ flex: 1; padding: 12px; text-align: center; font-family: 'Orbitron', sans-serif; font-size: 14px; color: #8892b0; cursor: pointer; border-radius: 8px; transition: 0.3s; font-weight: 700; }}
            .tab-btn.active {{ background: linear-gradient(135deg, rgba(0, 243, 255, 0.2), rgba(191, 0, 255, 0.2)); color: #fff; border: 1px solid var(--neon-cyan); box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.2); }}
            .tab-content {{ display: none; animation: fadeIn 0.4s ease; }}
            .tab-content.active {{ display: block; }}
            @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}

            .glass-card {{ background: var(--glass-bg); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 20px; padding: 25px 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.4); margin-bottom: 20px; }}

            .input-cosmic {{ width: 100%; background: rgba(0,0,0,0.3); border: 1px solid rgba(0, 243, 255, 0.3); color: var(--neon-cyan); padding: 16px; border-radius: 12px; font-family: 'Orbitron', sans-serif; font-size: 16px; text-align: center; outline: none; transition: 0.3s; letter-spacing: 2px; }}
            .input-cosmic:focus {{ border-color: var(--neon-cyan); box-shadow: 0 0 15px rgba(0, 243, 255, 0.4); }}
            .input-cosmic::placeholder {{ color: rgba(255,255,255,0.3); letter-spacing: 0; }}

            .btn-action {{ width: 100%; padding: 15px; border-radius: 12px; border: none; font-family: 'Orbitron', sans-serif; font-weight: 700; font-size: 16px; color: #fff; cursor: pointer; transition: 0.3s; text-transform: uppercase; margin-top: 15px; display: flex; justify-content: center; align-items: center; gap: 10px; text-decoration: none; }}
            .btn-activate {{ background: linear-gradient(45deg, #00d2ff 0%, #3a7bd5 100%); box-shadow: 0 5px 20px rgba(0, 210, 255, 0.4); }}
            .btn-activate:hover {{ transform: scale(1.02); box-shadow: 0 5px 25px rgba(0, 210, 255, 0.6); }}
            
            .btn-clash {{ background: linear-gradient(45deg, #f12711 0%, #f5af19 100%); box-shadow: 0 5px 20px rgba(241, 39, 17, 0.4); display: none; }}
            .btn-clash:hover {{ transform: scale(1.02); box-shadow: 0 5px 25px rgba(241, 39, 17, 0.6); }}

            .result-box {{ display: none; margin-top: 20px; padding: 20px; background: rgba(10, 20, 30, 0.6); border-left: 4px solid var(--neon-cyan); border-radius: 0 12px 12px 0; }}
            .status-badge {{ display: inline-block; padding: 5px 12px; border-radius: 20px; font-weight: bold; font-size: 14px; text-transform: uppercase; margin-bottom: 10px; }}
            .badge-active {{ background: rgba(0, 255, 136, 0.2); color: #00ff88; border: 1px solid #00ff88; }}
            .badge-error {{ background: rgba(255, 0, 85, 0.2); color: #ff0055; border: 1px solid #ff0055; }}
            
            .key-info-item {{ background: rgba(0,0,0,0.4); padding: 15px; border-radius: 12px; margin-bottom: 15px; border: 1px solid rgba(255,255,255,0.05); position: relative; overflow: hidden; }}
            .key-info-item::before {{ content: ''; position: absolute; left: 0; top: 0; width: 4px; height: 100%; background: var(--neon-purple); box-shadow: 0 0 10px var(--neon-purple); }}
            .info-label {{ font-size: 14px; color: #8892b0; margin-bottom: 5px; text-transform: uppercase; }}
            .info-value {{ font-size: 18px; font-weight: bold; color: #fff; font-family: 'Orbitron', sans-serif; }}
            
            .floating-logo {{ font-size: 50px; text-align: center; margin-bottom: 10px; animation: float 3s ease-in-out infinite; }}
            @keyframes float {{ 0% {{ transform: translateY(0px); }} 50% {{ transform: translateY(-10px); }} 100% {{ transform: translateY(0px); }} }}
            
            div:where(.swal2-container) div:where(.swal2-popup) {{ background: #0b0f19 !important; border: 1px solid var(--neon-cyan); color: #fff; border-radius: 16px; box-shadow: 0 0 30px rgba(0, 243, 255, 0.2); }}
            div:where(.swal2-container) h2:where(.swal2-title) {{ color: #fff; font-family: 'Orbitron'; }}
        </style>
    </head>
    <body>
        <div class="stars" id="stars-container"></div>
        
        <div class="app-container">
            <div class="floating-logo">🚀</div>
            <h1 class="header-title">COSMIC PROXY</h1>

            <div class="tabs">
                <div class="tab-btn active" onclick="switchTab(1)">Nhập Key</div>
                <div class="tab-btn" onclick="switchTab(2)">Quản Lý Key</div>
            </div>

            <div id="tab1" class="tab-content active">
                <div class="glass-card">
                    <input type="text" id="proxyKey" class="input-cosmic" placeholder="Nhập Key VIP..." autocomplete="off">
                    <button class="btn-action btn-activate" onclick="checkKey()">
                        <i class="fas fa-bolt"></i> KÍCH HOẠT HỆ THỐNG
                    </button>
                    
                    <div id="resultBox" class="result-box">
                        <div id="statusBadge" class="status-badge"></div>
                        <p style="color: #8892b0; font-size: 15px; margin-bottom: 5px;"><i class="fas fa-shield-alt"></i> Sảnh Chờ: <span id="lobbyMsg" style="color: #fff; font-weight: bold;"></span></p>
                        <p style="color: #8892b0; font-size: 15px;"><i class="fas fa-gamepad"></i> Trong Game: <span id="ingameMsg" style="color: #00ff88; font-weight: bold;"></span></p>
                    </div>
                    
                    <a id="clashBtn" href="#" class="btn-action btn-clash">
                        <i class="fas fa-download"></i> NẠP FILE .YAML CLASH META
                    </a>
                </div>
            </div>

            <div id="tab2" class="tab-content">
                <div class="glass-card" id="manageContent">
                    <div style="text-align:center; padding: 20px; color: #8892b0;">
                        <i class="fas fa-key" style="font-size: 40px; margin-bottom: 15px; opacity: 0.5;"></i><br>
                        Vui lòng kích hoạt Key ở Tab 1 trước.
                    </div>
                </div>
            </div>
        </div>

        <script>
            if (window.Telegram && window.Telegram.WebApp) {{
                window.Telegram.WebApp.expand();
            }}

            const starsContainer = document.getElementById('stars-container');
            for(let i=0; i<50; i++) {{
                let star = document.createElement('div');
                star.className = 'star';
                let size = Math.random() * 3 + 1;
                star.style.width = size + 'px';
                star.style.height = size + 'px';
                star.style.left = Math.random() * 100 + '%';
                star.style.top = Math.random() * 100 + '%';
                star.style.animationDuration = (Math.random() * 3 + 2) + 's';
                star.style.animationDelay = Math.random() * 2 + 's';
                starsContainer.appendChild(star);
            }}

            function switchTab(tabId) {{
                document.querySelectorAll('.tab-btn').forEach((btn, idx) => {{
                    btn.classList.toggle('active', idx + 1 === tabId);
                }});
                document.querySelectorAll('.tab-content').forEach((content, idx) => {{
                    content.classList.toggle('active', idx + 1 === tabId);
                }});
                if(tabId === 2) updateManageTab();
            }}

            function formatTime(ms) {{
                if(!ms || ms === 'permanent') return 'VĨNH VIỄN';
                if(ms === 'pending') return 'CHƯA KÍCH HOẠT';
                let d = new Date(ms);
                return d.toLocaleString('vi-VN');
            }}

            function checkKey() {{
                var key = document.getElementById('proxyKey').value.trim();
                if(!key) {{ 
                    Swal.fire({{ title: 'Cảnh Báo', text: 'Thiếu Dữ Liệu! Vui lòng nhập Key.', icon: 'warning', confirmButtonColor: '#00f3ff' }});
                    return; 
                }}
                
                Swal.fire({{
                    title: 'ĐANG ĐỒNG BỘ...',
                    html: 'Hệ thống đang kết nối với vệ tinh LVT',
                    allowOutsideClick: false,
                    didOpen: () => {{ Swal.showLoading(); }}
                }});
                fetch('{WEB_URL}/api/proxy/status?key=' + key)
                .then(r => r.json())
                .then(d => {{
                    Swal.close();
                    var box = document.getElementById('resultBox');
                    box.style.display = 'block';
                    
                    if(d.status === 'active') {{
                        document.getElementById('statusBadge').className = 'status-badge badge-active';
                        document.getElementById('statusBadge').innerHTML = '<i class="fas fa-check-circle"></i> ĐÃ KÍCH HOẠT (ACTIVE)';
                        document.getElementById('lobbyMsg').innerText = d.message;
                        document.getElementById('ingameMsg').innerText = d.ingame_message;
                        
                        var clashUrl = "clash://install-config?url=" + encodeURIComponent(d.yaml_url) + "&name=" + encodeURIComponent("Cosmic_" + key);
                        document.getElementById('clashBtn').href = clashUrl;
                        document.getElementById('clashBtn').style.display = 'flex';
                        
                        localStorage.setItem('lvt_saved_key', key);
                        localStorage.setItem('lvt_saved_data', JSON.stringify(d));
                        
                        Swal.fire({{toast: true, position: 'top-end', icon: 'success', title: 'Kích hoạt hoàn tất!', showConfirmButton: false, timer: 2000, background: '#0b0f19', color: '#fff'}});
                    }} else {{
                        document.getElementById('statusBadge').className = 'status-badge badge-error';
                        document.getElementById('statusBadge').innerHTML = '<i class="fas fa-times-circle"></i> LỖI BẢO MẬT (BLOCK)';
                        document.getElementById('lobbyMsg').innerText = d.message;
                        document.getElementById('ingameMsg').innerText = "KẾT NỐI BỊ TỪ CHỐI";
                        document.getElementById('clashBtn').style.display = 'none';
                        
                        Swal.fire({{ title: 'Thất Bại', text: d.message, icon: 'error', confirmButtonColor: '#ff0055' }});
                    }}
                }}).catch(e => {{ 
                    Swal.fire('Lỗi', 'Mất kết nối không gian! Vui lòng thử lại.', 'error'); 
                }});
            }}

            function updateManageTab() {{
                let key = localStorage.getItem('lvt_saved_key');
                let dataStr = localStorage.getItem('lvt_saved_data');
                let content = document.getElementById('manageContent');
                
                if(!key || !dataStr) return;
                let d = JSON.parse(dataStr);
                
                let expTime = d.exp;
                let activeTime = (typeof expTime === 'number') ? (expTime - d.durationMs) : 'Vĩnh viễn';
                content.innerHTML = `
                    <div class="key-info-item">
                        <div class="info-label">Current Key</div>
                        <div class="info-value" style="color: var(--neon-cyan)">${{key}}</div>
                    </div>
                    <div class="key-info-item" style="border-left-color: #00ff88;">
                        <div class="info-label">Thời gian bắt đầu</div>
                        <div class="info-value">${{formatTime(activeTime)}}</div>
                    </div>
                    <div class="key-info-item" style="border-left-color: #ff0055;">
                        <div class="info-label">Thời gian hết hạn</div>
                        <div class="info-value">${{formatTime(expTime)}}</div>
                    </div>
                    <button class="btn-action" style="background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); font-size: 14px;" onclick="localStorage.removeItem('lvt_saved_key'); location.reload();">XÓA DỮ LIỆU KEY</button>
                `;
            }}
            
            window.onload = () => {{
                let savedKey = localStorage.getItem('lvt_saved_key');
                if(savedKey) {{
                    document.getElementById('proxyKey').value = savedKey;
                }}
            }}
        </script>
    </body>
    </html>
    '''

def call_shortlink_api(url_to_shorten):
    db = load_db()
    api_token = db.get("settings", {}).get("shortlink_api_token", "4f62901315a7381c321f76bc988ff0e3").strip()
    
    try:
        full_url = f"https://api.layma.net/api/admin/shortlink/quicklink?tokenUser={api_token}&format=json&url={urllib.parse.quote(url_to_shorten)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(full_url, headers=headers, timeout=12).json()
        
        if res.get("success") is True or res.get("status") == "success":
            short_link = res.get("html") or res.get("shortenedUrl") or res.get("short_url") or res.get("link")
            if short_link:
                return short_link
    except Exception as e:
        print("Lỗi tạo shortlink:", e)
        
    return f"https://google.com/search?q=Hệ+Thống+Vượt+Link+Đang+Bảo+Trì"

@app.route('/start_bypass', methods=['POST'])
def start_bypass():
    game = request.form.get('game', 'GAME')
    steps = safe_int(request.form.get('steps', 1))
    if steps not in [1, 2]: steps = 1
    
    session_id = secrets.token_hex(12)
    bypass_sessions[session_id] = {
        "game": game,
        "steps": steps,
        "current_step": 1,
        "time": time.time(),
        "ip": get_real_ip()
    }
    
    return_url = f"{WEB_URL}/verify_bypass?session={session_id}"
    short_url = call_shortlink_api(return_url)
    return redirect(short_url)

@app.route('/verify_bypass')
def verify_bypass():
    session_id = request.args.get('session')
    if not session_id or session_id not in bypass_sessions:
        return swal_redirect("Lỗi Vượt Link", "Phiên vượt link đã hết hạn hoặc không hợp lệ. Vui lòng làm lại từ đầu!", "error", "/")
        
    s_data = bypass_sessions[session_id]
    
    if s_data["current_step"] < s_data["steps"]:
        s_data["current_step"] += 1
        return_url = f"{WEB_URL}/verify_bypass?session={session_id}"
        short_url = call_shortlink_api(return_url)
        return redirect(short_url)
        
    game_clean = re.sub(r'[^A-Z0-9_]', '', str(s_data["game"]).upper()[:10])
    hours = "12H" if s_data["steps"] == 1 else "24H"
    random_str = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(5))
    key_name = f"KEY_{game_clean}_{hours}_{random_str}"
    
    db = load_db()
    with db_lock:
        db["keys"][key_name] = {
            "exp": "pending",
            "maxDevices": 1,
            "devices": [],
            "vip": True,
            "status": "active",
            "bound_olm": "",
            "proxy_host": "",
            "proxy_port": 8080,
            "ban_until": 0,
            "note": f"Key Vượt Link {hours}",
            "durationMs": (12 if hours == "12H" else 24) * 3600000
        }
        save_db(db)
        
    send_telegram_event('bypass_success', {'key': key_name, 'game': game_clean, 'hours': hours, 'ip': get_real_ip()})
    del bypass_sessions[session_id]
    
    return f'''
    <!DOCTYPE html><html lang="vi">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>NHẬN KEY THÀNH CÔNG</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
            body {{ background-color: #f3f4f6; font-family: 'Inter', sans-serif; color: #1f2937; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
            .result-box {{ background: rgba(255, 255, 255, 0.85); backdrop-filter: blur(20px); border: 1px solid #10b981; border-radius: 24px; padding: 40px 30px; width: 100%; max-width: 440px; text-align: center; box-shadow: 0 10px 40px rgba(16, 185, 129, 0.08); }}
            .key-display {{ background: #f0fdf4; padding: 16px; font-size: 20px; font-family: monospace; font-weight: 700; color: #15803d; border-radius: 12px; border: 1px dashed #10b981; margin: 24px 0; letter-spacing: 0.5px; word-break: break-all; }}
            .btn-copy {{ background: #10b981; color: #ffffff; font-weight: 700; padding: 13px; border-radius: 12px; width: 100%; border: none; transition: all 0.2s; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2); }}
            .btn-copy:hover {{ background: #059669; transform: translateY(-1px); box-shadow: 0 6px 20px rgba(16, 185, 129, 0.3); }}
            .btn-home {{ background: transparent; color: #4b5563; border: 1px solid #d1d5db; padding: 11px; border-radius: 12px; width: 100%; font-weight: 600; text-decoration: none; display: inline-block; font-size: 14px; transition: 0.2s; }}
            .btn-home:hover {{ background: #f9fafb; color: #111827; }}
        </style>
    </head>
    <body>
        <div class="container d-flex justify-content-center">
            <div class="result-box">
                <i class="fas fa-check-circle mb-3" style="font-size: 48px; color: #10b981;"></i>
                <h4 class="fw-bold text-dark" style="letter-spacing: -0.5px;">VƯỢT LINK THÀNH CÔNG</h4>
                <p class="text-muted small">Bạn đã nhận được KEY VIP. Vui lòng copy và dán mã bên dưới vào ứng dụng để sử dụng.</p>
                
                <div class="key-display" id="myKey">{key_name}</div>
                
                <button class="btn-copy" onclick="copyKey()"><i class="far fa-copy me-1"></i> Copy Key Ngay</button>
                <a href="/" class="btn-home"><i class="fas fa-home me-1"></i> Trở về trang chủ</a>
            </div>
        </div>
        <script>
            function copyKey() {{
                navigator.clipboard.writeText(document.getElementById("myKey").innerText);
                Swal.fire({{toast: true, position: 'top-end', icon: 'success', title: 'Đã copy Key!', showConfirmButton: false, timer: 2000, background: '#ffffff', color: '#1f2937'}});
            }}
        </script>
    </body>
    </html>
    '''

@app.route('/api/verify_core', methods=['POST'])
def api_verify_core():
    public_ip = get_real_ip()
    now = int(time.time() * 1000)

    with api_rate_lock:
        if len(api_rate_cache) > 5000:
            stale_ips = [k for k, v in api_rate_cache.items() if not v or now - v[-1] > 60000]
            for k in stale_ips: api_rate_cache.pop(k, None)
        reqs = api_rate_cache.get(public_ip, [])
        reqs = [t for t in reqs if now - t < 60000]
        
        if len(reqs) >= 30: 
            db = load_db()
            with db_lock:
                if public_ip not in db.setdefault("banned_ips", []):
                    db["banned_ips"].append(public_ip)
                    save_db(db)
            send_telegram_alert(f"🚫 <b>ANTI-SPAM DDOS KÍCH HOẠT:</b> Auto ban IP <code>{public_ip}</code> do spam API liên tục vượt giới hạn.")
            return jsonify({"status": "error", "msg": "Phát hiện lạm dụng API (Spam)! Thiết bị của bạn đã bị đưa vào danh sách đen."})
        reqs.append(now)
        api_rate_cache[public_ip] = reqs

    data = request.json or {}
    key = data.get('key', '').strip()
    current_olm = data.get('olm_name', '').strip()
    device_name = data.get('device_name', '')
    android_version = data.get('android_version', '')
    client_ip = data.get('local_ip') or data.get('real_ip') or public_ip
    ua_string = request.headers.get('User-Agent', '')
    
    if not android_version or android_version == 'Không rõ bản Android':
        a_match = re.search(r'Android\s+([0-9\.]+)', ua_string)
        android_version = f"Android {a_match.group(1)}" if a_match else "Không xác định"
    if not device_name or device_name == 'Không rõ máy':
        d_match = re.search(r'Android\s+[0-9\.]+;\s+([^;]+)\s+Build', ua_string)
        device_name = d_match.group(1).strip() if d_match else "Không xác định"
    
    db = load_db()
    with db_lock:
        if public_ip in db.get("banned_ips", []): return jsonify({"status": "error", "msg": "Thiết bị của bạn đã bị chặn bởi tường lửa!"})
        if key not in db.get("keys", {}): return jsonify({"status": "error", "msg": "Mã Key không tồn tại hoặc sai định dạng!"})
        kd = db["keys"][key]
        
        if kd.get("status") == "banned":
            ban_until = kd.get("ban_until", "permanent")
            if ban_until == "permanent" or (isinstance(ban_until, int) and ban_until > now): 
                send_telegram_event('banned', {'key': key, 'ip': client_ip})
                return jsonify({"status": "banned", "msg": "Key của bạn đang bị Admin khóa!", "ban_time": ban_until, "server_time": now})
            else: kd["status"] = "active"
            
        if kd.get("exp") != "permanent" and kd.get("exp") != "pending" and kd.get("exp", 0) < now: 
            send_telegram_event('expired', {'key': key, 'ip': client_ip})
            return jsonify({"status": "error", "msg": "Key đã hết hạn sử dụng!"})

        devices = kd.setdefault("devices", [])
        connected_ips = kd.setdefault("connected_ips", [])
        if client_ip not in connected_ips:
            connected_ips.append(client_ip)
            if len(connected_ips) > 10: connected_ips.pop(0)

        device_identifier = data.get('device_id', '') or data.get('uuid', '')
        if not device_identifier: device_identifier = f"{device_name} - {android_version}"
            
        for item in list(devices):
            if ('.' in item and len(item.split('.')) == 4) or (':' in item):
                try: devices.remove(item)
                except: pass
                
        if device_identifier not in devices:
            if len(devices) >= kd.get("maxDevices", 1): 
                send_telegram_event('limit', {'key': key, 'ip': client_ip})
                return jsonify({"status": "error", "msg": "Key này đã vượt quá số lượng thiết bị cho phép!"})
            devices.append(device_identifier)

        if kd.get("exp") == "pending":
            kd["exp"] = now + kd.get("durationMs", 0)
            kd["activated"] = True
            
        bound_olm = kd.get("bound_olm", "")
        if bound_olm and current_olm and bound_olm.lower() != current_olm.lower():
            kd["status"] = "banned"
            kd["ban_until"] = "permanent"
            save_db(db)
            send_telegram_event('banned', {'key': key, 'ip': client_ip})
            return jsonify({"status": "banned", "msg": f"⚠️ CẢNH BÁO: Phát hiện sai tài khoản OLM! Key của bạn đã bị Hệ thống khóa vĩnh viễn!", "ban_time": "permanent"})
            
        save_db(db)
        send_telegram_event('login', {'key': key, 'ip': client_ip, 'device_name': device_name, 'android_version': android_version})
        
        is_vip = kd.get("vip", False)
        core_code = db.get("settings", {}).get("script_tiem", "")
        note_msg = kd.get("note", "") 
          
        return jsonify({"status": "ok", "is_vip": is_vip, "core": core_code, "exp": kd["exp"], "devices": len(devices), "max_devs": kd.get("maxDevices", 1), "server_time": now, "note": note_msg})

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    try:
        ip = get_real_ip()
        global admin_login_attempts
        now = time.time()
        
        with admin_login_lock:
            admin_login_attempts = {k: v for k, v in admin_login_attempts.items() if now - v['time'] < 300} 
            attempts = admin_login_attempts.get(ip, {'count': 0, 'time': now})
            if attempts['count'] >= 5: 
                db = load_db()
                with db_lock:
                    if ip not in db.setdefault("banned_ips", []):
                        db["banned_ips"].append(ip)
                        save_db(db)
                send_telegram_alert(f"💥 <b>CẢNH BÁO BRUTEFORCE:</b> IP <code>{ip}</code> cố tình dò mật khẩu Admin sai 5 lần. Hệ thống tự động BAN IP vĩnh viễn!")
                return swal_back("Bị Khóa", "Bạn đã bị chặn vĩnh viễn do cố tình dò mật khẩu!", "error")

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
            
        return f'''<!DOCTYPE html><html lang="vi"><head><title>C-Panel Admin Đăng Nhập</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>{CSS_GLASS} .inp-neon {{ background: #ffffff; border: 1px solid #cbd5e1; color: #1e293b; padding: 12px; border-radius: 8px; width: 100%; margin-bottom: 15px; outline: none; transition: 0.3s; text-align: center; }} .inp-neon:focus {{ border-color: #0f172a; box-shadow: 0 0 10px rgba(0,0,0,0.05); }}</style></head><body style="background:#f1f5f9; display:flex; justify-content:center; align-items:center; height:100vh;"><div class="container"><div class="glass-panel mx-auto" style="max-width:400px; background:#ffffff;"><h2 class="text-neon mb-4"><i class="fas fa-user-shield"></i> LVT C-PANEL</h2><form method="POST"><input type="text" name="username" class="inp-neon" placeholder="Tài khoản Quản Trị" required><input type="password" name="password" class="inp-neon" placeholder="Mật Khẩu" required><button type="submit" class="btn-neon mt-2"><i class="fas fa-sign-in-alt"></i> TRUY CẬP HỆ THỐNG</button></form></div></div></body></html>'''
    except Exception as e: return f"LỖI: {str(e)}", 200

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    token_url = session.get("csrf_token", "")
    csrf_input = f'<input type="hidden" name="csrf_token" value="{token_url}">'
    
    with db_lock:
        keys_items = list(db.get("keys", {}).items())
        banned_ips = list(db.get("banned_ips", []))

    now_ms = int(time.time() * 1000)
    keys_html = ''
    for k, data in sorted(keys_items, key=lambda x: x[1].get('exp', 0) if isinstance(x[1].get('exp'), int) else 9999999999999, reverse=True):
        if "Key Vượt Link" in data.get("note", ""): continue
        st = data.get('status', 'active')
        ban_until = data.get("ban_until", 0)
        note = escape(data.get("note", ""))
        
        if st == "banned":
            if ban_until == "permanent" or (isinstance(ban_until, int) and ban_until > now_ms): is_banned = True
            else: is_banned = False; data["status"] = "active" 
        else: is_banned = False

        if is_banned:
            status_badge = '<span class="badge badge-custom text-bg-danger"><i class="fas fa-ban"></i> Bị Khóa</span>'
            ban_btn = f'<a href="/admin/action/unban/{escape(str(k))}?csrf_token={token_url}" class="action-btn text-success" title="Mở khóa Key"><i class="fas fa-unlock"></i></a>'
        else:
            status_badge = '<span class="badge badge-custom text-bg-success"><i class="fas fa-check-circle"></i> Sống</span>'
            ban_btn = f'<button class="action-btn action-btn-danger" data-key="{escape(str(k))}" onclick="openBanModal(this.getAttribute(\'data-key\'))" title="Khóa (Kick)"><i class="fas fa-ban"></i></button>'

        vip_badge = '<span class="badge badge-custom" style="background:#0f172a; color:#fff;"><i class="fas fa-crown"></i> VIP</span>' if data.get('vip', False) else '<span class="badge badge-custom bg-secondary text-white">Thường</span>'
        
        is_expired = False
        if data.get('exp') == 'pending': exp_text = '<span class="badge badge-custom bg-info text-dark">Chưa kích hoạt</span>'
        elif data.get('exp') == 'permanent': exp_text = '<span class="text-success fw-bold">Vĩnh Viễn</span>'
        else:
            is_expired = now_ms > data.get('exp', 0)
            exp_text = f'<span class="{"text-danger fw-bold" if is_expired else "text-dark font-weight-bold"}">{time.strftime("%d/%m/%y %H:%M", time.localtime(data.get("exp", 0) / 1000))}</span>'
        
        if is_expired and not is_banned: status_badge = '<span class="badge badge-custom bg-secondary text-white">Hết hạn</span>'
        
        safe_k = escape(str(k))
        bound_olm = escape(data.get('bound_olm', ''))

        keys_html += f'''<tr class="key-row">
        <td>
            <div class="fw-bold text-dark font-monospace mb-1" style="font-size:15px; cursor:pointer;" onclick="copyToClipboard('{safe_k}')">{safe_k} <i class="far fa-copy text-muted small"></i></div>
            <div class="d-flex gap-1 justify-content-center">{vip_badge} {status_badge}</div>
        </td>
        <td>{exp_text}</td>
        <td class="text-center"><span class="text-dark fw-bold">{bound_olm or '---'}</span></td>
        <td><span class="badge bg-light border border-secondary p-2 fs-6 text-dark">{len(data.get('devices', []))}/{data.get('maxDevices', 1)}</span></td>
        <td>
            <div class="d-flex flex-wrap gap-2 justify-content-center">
                <button class="action-btn text-dark" style="background: rgba(0,0,0,0.05);" data-key="{safe_k}" data-note="{note}" onclick="openNoteModal(this.getAttribute('data-key'), this.getAttribute('data-note'))" title="Ghi Chú"><i class="fas fa-sticky-note"></i></button>
                <button class="action-btn text-dark" data-key="{safe_k}" data-olm="{bound_olm}" onclick="openBindModal(this.getAttribute('data-key'), this.getAttribute('data-olm'))" title="Ghim Tên"><i class="fas fa-user-tag"></i></button>
                <button class="action-btn text-dark" data-key="{safe_k}" onclick="openAddTimeModal(this.getAttribute('data-key'))" title="Bơm Giờ"><i class="fas fa-clock"></i></button>
                <a href="/admin/action/reset_dev/{safe_k}?csrf_token={token_url}" class="action-btn text-dark" onclick="return confirm('Xóa sạch lịch sử thiết bị của Key này?')" title="Reset Thiết Bị"><i class="fas fa-sync-alt"></i></a>
                <button class="action-btn text-dark" data-key="{safe_k}" data-max="{data.get('maxDevices', 1)}" onclick="openMaxDevModal(this.getAttribute('data-key'), this.getAttribute('data-max'))" title="Giới Hạn Máy"><i class="fas fa-mobile-alt"></i></button>
                {ban_btn}
                <a href="/admin/action/delete/{safe_k}?csrf_token={token_url}" class="action-btn text-muted" onclick="return confirm('Xóa vĩnh viễn Key này?')" title="Xóa"><i class="fas fa-trash"></i></a>
            </div>
        </td>
        </tr>'''

    blacklist_rows = "".join([f'<li class="list-group-item d-flex justify-content-between align-items-center" style="background:#fff;"><span class="font-monospace text-danger">{escape(ip)}</span> <a href="/admin/unban_ip/{escape(ip)}?csrf_token={token_url}" class="action-btn action-btn-danger px-3">Gỡ</a></li>' for ip in banned_ips])

    return f'''
    <!DOCTYPE html><html lang="vi">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>LVT C-Panel</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
            body {{ background: #f8fafc; font-family: 'Inter', sans-serif; color: #334155; }}
            .topbar {{ background: #ffffff; border-bottom: 1px solid #e2e8f0; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
            .topbar-brand {{ font-size: 20px; font-weight: 800; color: #0f172a; letter-spacing: 0.5px; display: flex; align-items: center; gap: 10px; }}
            .card {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.02); }}
            .card-header {{ background: #fafafa; border-bottom: 1px solid #e2e8f0; padding: 15px 20px; font-weight: 700; font-size: 14px; text-transform: uppercase; color: #0f172a; display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
            .card-body {{ padding: 20px; }}
            .form-control, .form-select {{ background: #ffffff !important; border: 1px solid #cbd5e1 !important; color: #1e293b !important; border-radius: 8px; padding: 10px 15px; font-size: 14px; transition: 0.2s; }}
            .form-control:focus, .form-select:focus {{ border-color: #0f172a !important; box-shadow: 0 0 0 3px rgba(15,23,42,0.08) !important; outline: none; }}
            .btn-primary-custom {{ background: linear-gradient(135deg, #1e293b, #0f172a); border: none; color: #fff; font-weight: 700; padding: 12px 20px; border-radius: 8px; transition: 0.3s; text-transform: uppercase; width: 100%; cursor:pointer; }}
            .btn-primary-custom:hover {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
            .btn-success-custom {{ background: #0f172a; color:#fff; border: 1px solid #0f172a; }}
            .table {{ color: #334155; font-size: 14px; margin-bottom: 0; }}
            .table thead th {{ background: #f1f5f9; border-bottom: 1px solid #e2e8f0; color: #475569; font-weight: 600; padding: 15px; text-transform: uppercase; font-size: 12px; }}
            .table tbody td {{ border-bottom: 1px solid #e2e8f0; padding: 15px; vertical-align: middle; background: #fff; }}
            .badge-custom {{ padding: 6px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; text-transform: uppercase; display: inline-flex; align-items: center; gap: 4px; }}
            .action-btn {{ background: #f8fafc; color: #334155; border: 1px solid #e2e8f0; padding: 8px 12px; border-radius: 6px; font-size: 13px; font-weight: 600; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; transition: 0.2s; cursor: pointer; }}
            .action-btn:hover {{ background: #f1f5f9; color: #0f172a; }}
            .action-btn-danger {{ color: #ef4444; border-color: #fca5a5; background: #fef2f2; }}
            .action-btn-danger:hover {{ background: #ef4444; color: #fff; border-color: #ef4444; }}
            .list-group-item {{ background: #fff; border-color: #e2e8f0; color: #334155; padding: 12px 15px; }}
            .modal-content {{ background: #ffffff; border: 1px solid #cbd5e1; border-radius: 12px; color: #1e293b; }}
            .modal-header h5 {{ color: #0f172a !important; }}
            .nav-tabs-custom {{ display: flex; gap: 15px; margin-bottom: 25px; border-bottom: 1px solid #e2e8f0; padding-bottom: 15px; }}
            .nav-btn {{ padding: 12px 25px; border-radius: 8px; font-weight: 700; color: #475569; text-decoration: none; border: 1px solid #e2e8f0; background: #ffffff; transition: 0.3s; display: inline-flex; align-items: center; gap: 8px; }}
            .nav-btn:hover {{ color: #0f172a; background: #f8fafc; }}
            .nav-btn.active {{ background: #0f172a; color: #fff; border-color: #0f172a; box-shadow: 0 4px 12px rgba(15,23,42,0.15); }}
        </style>
    </head>
    <body>
        <div class="topbar">
            <div class="topbar-brand"><i class="fas fa-server"></i> LVT C-PANEL</div>
            <a href="/logout" class="btn btn-outline-danger btn-sm fw-bold px-3 py-2" style="border-radius: 8px;"><i class="fas fa-sign-out-alt"></i> Đăng xuất</a>
        </div>
        
        <div class="container-fluid py-4 px-lg-5">
            <div class="nav-tabs-custom">
                <a href="/admin" class="nav-btn active"><i class="fas fa-key"></i> QUẢN LÝ KEY & FIREWALL</a>
                <a href="/admin/getkey" class="nav-btn"><i class="fas fa-link"></i> QUẢN LÝ VƯỢT LINK (GET KEY)</a>
                <a href="/admin/files" class="nav-btn"><i class="fas fa-cloud-upload-alt"></i> AUTO NẠP FILE TRÊN MÂY</a>
                <a href="/admin/termux" class="nav-btn"><i class="fas fa-terminal"></i> GIAO DIỆN TERMUX</a>
            </div>

            <div class="row g-4 mb-4">
                <div class="col-xl-5 col-lg-12">
                    <div class="card h-100" style="border-top: 3px solid #0f172a;">
                        <div class="card-header"><div><i class="fas fa-magic"></i> Tạo Mới Key Kích Hoạt</div></div>
                        <div class="card-body">
                            <form action="/admin/create" method="POST" class="row g-3">{csrf_input}
                                <div class="col-12 mb-1">
                                    <label class="text-muted small fw-bold mb-1">Chế Độ Tạo</label>
                                    <select name="gen_type" class="form-select text-dark fw-bold" onchange="document.getElementById('manual_box').style.display = this.value === 'manual' ? 'block' : 'none'; document.getElementById('qty_box').style.display = this.value === 'auto' ? 'block' : 'none';">
                                        <option value="auto">Auto Ngẫu Nhiên (Mặc định)</option>
                                        <option value="manual">Thủ Công (Tự Chọn Tên Key)</option>
                                    </select>
                                </div>
                                <div class="col-12" id="manual_box" style="display:none;">
                                    <label class="text-muted small fw-bold mb-1">Nhập Key Thủ Công</label>
                                    <input type="text" name="manual_key" class="form-control" placeholder="Nhập key tùy ý (Ví dụ: MY_KEY@123!)">
                                </div>
                                <div class="col-6" id="qty_box"><label class="text-muted small fw-bold mb-1">Số lượng</label><input type="number" name="quantity" class="form-control" value="1"></div>
                               
                                <div class="col-6"><label class="text-muted small fw-bold mb-1">Số máy/Key</label><input type="number" name="devices" class="form-control" value="1" required></div>
                                <div class="col-6"><label class="text-muted small fw-bold mb-1">Độ dài TG</label><input type="number" name="duration" class="form-control" value="1" required></div>
                                <div class="col-6"><label class="text-muted small fw-bold mb-1">Đơn vị</label><select name="type" class="form-select"><option value="minute">Phút</option><option value="hour">Giờ</option><option value="day" selected>Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh Viễn</option></select></div>
                                <div class="col-12 mt-3"><div class="form-check form-switch fs-6 p-3 rounded" style="background: #f8fafc; border: 1px solid #cbd5e1;"><input class="form-check-input ms-0 mt-1" type="checkbox" name="is_vip"><label class="text-dark fw-bold ms-3" style="line-height:24px;">VIP PRO</label></div></div>
                                <div class="col-12 mt-4"><button type="submit" class="btn-primary-custom btn-success-custom"><i class="fas fa-cogs"></i> Sản xuất Key</button></div>
                            </form>
                        </div>
                    </div>
                </div>

                <div class="col-xl-7 col-lg-12">
                    <div class="card h-100" style="border-top: 3px solid #64748b;">
                        <div class="card-header"><div><i class="fas fa-shield-virus"></i> Firewall (Danh Sách Đen IP)</div></div>
                        <div class="card-body">
                            <form action="/admin/ban_ip" method="POST" class="d-flex gap-2 mb-3">{csrf_input}
                                <input type="text" name="ip" class="form-control" placeholder="Nhập IP cần khoá..." required>
                                <button type="submit" class="action-btn action-btn-danger" style="white-space:nowrap;"><i class="fas fa-ban"></i> Chặn Cửa</button>
                            </form>
                            <ul class="list-group" style="max-height:300px; overflow-y:auto;">
                                {blacklist_rows or '<li class="list-group-item text-center text-muted border-0 py-4" style="background:#fff;"><i class="fas fa-check-circle fs-4 mb-2 d-block"></i> Không có IP nào bị khoá.</li>'}
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card mb-5" style="border-top: 3px solid #0f172a;">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <div><i class="fas fa-database"></i> Quản Lý Kho Key Cấp Phát</div>
                    <div class="input-group" style="width:300px;">
                        <span class="input-group-text bg-transparent border-end-0" style="border-color:#cbd5e1; color:#64748b;"><i class="fas fa-search"></i></span>
                        <input type="text" class="form-control border-start-0 ps-0" placeholder="Tìm kiếm nhanh..." onkeyup="let s=this.value.toLowerCase();document.querySelectorAll('.key-row').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(s)?'':'none');" style="box-shadow:none !important;">
                    </div>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive" style="max-height: 700px; overflow-y:auto;">
                        <table class="table table-hover text-center align-middle mb-0">
                            <thead style="position: sticky; top: 0; z-index: 1;">
                                <tr><th>Cụm Key Kích Hoạt</th><th>Thời Hạn</th><th>Định Định OLM</th><th>Thiết bị</th><th>Thao Tác Quản Trị</th></tr>
                            </thead>
                            <tbody>
                                {keys_html or '<tr><td colspan="5" class="py-5 text-muted" style="background:#fff;">Chưa có dữ liệu.</td></tr>'}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="modal fade" id="noteModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered"><div class="modal-content"><form action="/admin/edit_note" method="POST">{csrf_input}<div class="modal-header"><h5 class="modal-title fw-bold text-dark"><i class="fas fa-sticky-note"></i> GHI CHÚ KEY</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body p-4 text-center"><input type="hidden" name="key" id="noteKeyInput"><h4 id="noteKeyDisplay" class="text-dark font-monospace d-block mb-4 fw-bold"></h4><textarea name="note_text" id="noteInput" class="form-control form-control-lg text-center" rows="3" placeholder="Nhập văn bản thông báo..."></textarea></div><div class="modal-footer p-3"><button class="btn-primary-custom w-100">LƯU GHI CHÚ</button></div></form></div></div>
        </div>

        <div class="modal fade" id="bindModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered"><div class="modal-content"><form action="/admin/bind_olm" method="POST">{csrf_input}<div class="modal-header"><h5 class="modal-title fw-bold text-dark"><i class="fas fa-user-tag"></i> GHIM TÀI KHOẢN OLM</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body p-4 text-center"><input type="hidden" name="key" id="bindKeyInput"><h4 id="bindKeyDisplay" class="text-dark font-monospace d-block mb-4 fw-bold"></h4><input type="text" name="olm_name" id="bindOlmInput" class="form-control form-control-lg text-center" placeholder="Nhập tên tài khoản OLM cần ghim..." required></div><div class="modal-footer p-3"><button class="btn-primary-custom w-100">LƯU ĐỊNH DANH</button></div></form></div></div>
        </div>

        <div class="modal fade" id="addTimeModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered"><div class="modal-content"><form action="/admin/add_time" method="POST">{csrf_input}<div class="modal-header"><h5 class="modal-title fw-bold text-dark"><i class="fas fa-clock"></i> CỘNG THÊM GIỜ</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body p-4 text-center"><input type="hidden" name="key" id="addTimeKeyInput"><h4 id="addTimeKeyDisplay" class="text-dark font-monospace d-block mb-4 fw-bold"></h4><div class="row g-2"><div class="col-8"><input type="number" name="time_val" class="form-control form-control-lg text-center" placeholder="Số lượng" required></div><div class="col-4"><select name="time_unit" class="form-select form-select-lg"><option value="minutes">Phút</option><option value="hours">Giờ</option><option value="days" selected>Ngày</option><option value="months">Tháng</option></select></div></div></div><div class="modal-footer p-3"><button class="btn-primary-custom w-100">XÁC NHẬN CỘNG</button></div></form></div></div>
        </div>

        <div class="modal fade" id="maxDevModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered"><div class="modal-content"><form action="/admin/edit_max_dev" method="POST">{csrf_input}<div class="modal-header"><h5 class="modal-title fw-bold text-dark"><i class="fas fa-mobile-alt"></i> TÙY CHỈNH GIỚI HẠN THIẾT BỊ</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body p-4 text-center"><input type="hidden" name="key" id="maxDevKeyInput"><h4 id="maxDevKeyDisplay" class="text-dark font-monospace d-block mb-4 fw-bold"></h4><input type="number" name="max_dev" id="maxDevInput" class="form-control form-control-lg text-center" placeholder="Nhập số thiết bị..." required min="1"></div><div class="modal-footer p-3"><button class="btn-primary-custom w-100">CẬP NHẬT THIẾT BỊ</button></div></form></div></div>
        </div>

        <div class="modal fade" id="banModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered"><div class="modal-content"><form action="/admin/custom_ban" method="POST">{csrf_input}<div class="modal-header"><h5 class="modal-title fw-bold text-danger"><i class="fas fa-ban"></i> KHÓA KEY (KICK KHÁCH)</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body p-4 text-center"><input type="hidden" name="key" id="banKeyInput"><h4 id="banKeyDisplay" class="text-dark font-monospace d-block mb-4 fw-bold"></h4><div class="row g-2"><div class="col-6"><input type="number" name="time_val" class="form-control form-control-lg text-center" placeholder="Thời gian"></div><div class="col-6"><select name="time_unit" class="form-select form-select-lg"><option value="minutes">Phút</option><option value="hours">Giờ</option><option value="days">Ngày</option><option value="months">Tháng</option><option value="permanent" selected>Vĩnh Viễn</option></select></div></div></div><div class="modal-footer p-3"><button type="submit" class="btn-primary-custom action-btn-danger w-100 border-0">XÁC NHẬN KHÓA</button></div></form></div></div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            function openNoteModal(key, note) {{ document.getElementById('noteKeyInput').value = key; document.getElementById('noteKeyDisplay').innerText = key; document.getElementById('noteInput').value = note; bootstrap.Modal.getOrCreateInstance(document.getElementById('noteModal')).show(); }}
            function openBindModal(key, old) {{ document.getElementById('bindKeyInput').value = key; document.getElementById('bindKeyDisplay').innerText = key; document.getElementById('bindOlmInput').value = old; bootstrap.Modal.getOrCreateInstance(document.getElementById('bindModal')).show(); }}
            function openAddTimeModal(key) {{ document.getElementById('addTimeKeyInput').value = key; document.getElementById('addTimeKeyDisplay').innerText = key; bootstrap.Modal.getOrCreateInstance(document.getElementById('addTimeModal')).show(); }}
            function openMaxDevModal(key, max) {{ document.getElementById('maxDevKeyInput').value = key; document.getElementById('maxDevKeyDisplay').innerText = key; document.getElementById('maxDevInput').value = max; bootstrap.Modal.getOrCreateInstance(document.getElementById('maxDevModal')).show(); }}
            function openBanModal(key) {{ document.getElementById('banKeyInput').value = key; document.getElementById('banKeyDisplay').innerText = key; bootstrap.Modal.getOrCreateInstance(document.getElementById('banModal')).show(); }}
            function copyToClipboard(text) {{ navigator.clipboard.writeText(text); Swal.fire({{toast: true, position: 'top-end', icon: 'success', title: 'Đã copy Key!', showConfirmButton: false, timer: 1500, background: '#ffffff', color: '#1e293b'}}); }}
        </script>
    </body>
    </html>
    '''

@app.route('/admin/getkey')
def admin_getkey_dashboard():
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    csrf_input = f'<input type="hidden" name="csrf_token" value="{session.get("csrf_token", "")}">'
    
    settings = db.get("settings", {})
    api_url = escape(settings.get("shortlink_api_url", "https://api.layma.net/api/admin/shortlink/quicklink"))
    api_token = escape(settings.get("shortlink_api_token", "4f62901315a7381c321f76bc988ff0e3"))
    games_list = escape(settings.get("games_list", "PUBG, LIENQUAN, FREEFIRE"))
    
    keys_html = ''
    now_ms = int(time.time() * 1000)
    
    with db_lock:
        keys_items = list(db.get("keys", {}).items())
        
    for k, data in sorted(keys_items, key=lambda x: x[1].get('exp', 0) if isinstance(x[1].get('exp'), int) else 9999999999999, reverse=True):
        if "Key Vượt Link" not in data.get("note", ""): continue
        
        is_expired = False
        if data.get('exp') == 'pending': exp_text = '<span class="badge bg-info text-dark">Chưa kích hoạt</span>'
        else:
            is_expired = now_ms > data.get('exp', 0)
            exp_text = f'<span class="{"text-danger fw-bold" if is_expired else "text-success fw-bold"}">{time.strftime("%d/%m/%y %H:%M", time.localtime(data.get("exp", 0) / 1000))}</span>'
            
        safe_k = escape(str(k))
        keys_html += f'''<tr>
            <td><div class="fw-bold text-dark font-monospace mb-1">{safe_k}</div></td>
            <td><span class="badge bg-light text-dark border fw-bold">{escape(data.get("note", ""))}</span></td>
            <td>{exp_text}</td>
            <td><span class="badge bg-light border p-2 text-dark">{len(data.get('devices', []))}/1</span></td>
            <td><a href="/admin/action/delete/{safe_k}?csrf_token={session.get('csrf_token')}" class="btn btn-sm btn-outline-danger" onclick="return confirm('Xóa key này?')" title="Xóa"><i class="fas fa-trash"></i> Xóa</a></td>
        </tr>'''

    return f'''
    <!DOCTYPE html><html lang="vi">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>LVT C-Panel - Get Key</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
            body {{ background: #f8fafc; font-family: 'Inter', sans-serif; color: #334155; }}
            .topbar {{ background: #ffffff; border-bottom: 1px solid #e2e8f0; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
            .topbar-brand {{ font-size: 20px; font-weight: 800; color: #0f172a; letter-spacing: 0.5px; display: flex; align-items: center; gap: 10px; }}
            .card {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.02); }}
            .card-header {{ background: #fafafa; border-bottom: 1px solid #e2e8f0; padding: 15px 20px; font-weight: 700; font-size: 14px; text-transform: uppercase; color: #0f172a; display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
            .card-body {{ padding: 20px; }}
            .form-control {{ background: #ffffff !important; border: 1px solid #cbd5e1 !important; color: #1e293b !important; border-radius: 8px; padding: 10px 15px; font-size: 14px; transition: 0.2s; }}
            .form-control:focus {{ border-color: #0f172a !important; box-shadow: 0 0 0 3px rgba(15,23,42,0.08) !important; outline: none; }}
            .btn-primary-custom {{ background: linear-gradient(135deg, #1e293b, #0f172a); border: none; color: #fff; font-weight: 700; padding: 12px 20px; border-radius: 8px; transition: 0.3s; text-transform: uppercase; width: 100%; cursor:pointer; }}
            .btn-primary-custom:hover {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
            .nav-tabs-custom {{ display: flex; gap: 15px; margin-bottom: 25px; border-bottom: 1px solid #e2e8f0; padding-bottom: 15px; }}
            .nav-btn {{ padding: 12px 25px; border-radius: 8px; font-weight: 700; color: #475569; text-decoration: none; border: 1px solid #e2e8f0; background: #ffffff; transition: 0.3s; display: inline-flex; align-items: center; gap: 8px; }}
            .nav-btn:hover {{ color: #0f172a; background: #f8fafc; }}
            .nav-btn.active {{ background: #0f172a; color: #fff; border-color: #0f172a; box-shadow: 0 4px 12px rgba(15,23,42,0.15); }}
            .table {{ color: #334155; font-size: 14px; margin-bottom: 0; }}
            .table thead th {{ background: #f1f5f9; border-bottom: 1px solid #e2e8f0; color: #475569; font-weight: 600; padding: 15px; text-transform: uppercase; font-size: 12px; }}
            .table tbody td {{ border-bottom: 1px solid #e2e8f0; padding: 15px; vertical-align: middle; background: #fff; }}
        </style>
    </head>
    <body>
        <div class="topbar">
            <div class="topbar-brand"><i class="fas fa-server"></i> LVT C-PANEL</div>
            <a href="/logout" class="btn btn-outline-danger btn-sm fw-bold px-3 py-2" style="border-radius: 8px;"><i class="fas fa-sign-out-alt"></i> Đăng xuất</a>
        </div>
        
        <div class="container-fluid py-4 px-lg-5">
            <div class="nav-tabs-custom">
                <a href="/admin" class="nav-btn"><i class="fas fa-key"></i> QUẢN LÝ KEY & FIREWALL</a>
                <a href="/admin/getkey" class="nav-btn active"><i class="fas fa-link"></i> QUẢN LÝ VƯỢT LINK (GET KEY)</a>
                <a href="/admin/files" class="nav-btn"><i class="fas fa-cloud-upload-alt"></i> AUTO NẠP FILE TRÊN MÂY</a>
                <a href="/admin/termux" class="nav-btn"><i class="fas fa-terminal"></i> GIAO DIỆN TERMUX</a>
            </div>

            <div class="row g-4">
                <div class="col-xl-4 col-lg-12">
                    <div class="card h-100" style="border-top: 3px solid #0f172a;">
                        <div class="card-header"><div><i class="fas fa-cogs"></i> Cài Đặt API Vượt Link</div></div>
                        <div class="card-body">
                            <form action="/admin/update_getkey_settings" method="POST">{csrf_input}
                                <div class="mb-3">
                                    <label class="text-muted small fw-bold mb-1">Tên Tựa Game (Ngăn cách bằng dấu phẩy)</label>
                                    <textarea name="games_list" class="form-control" rows="2">{games_list}</textarea>
                                </div>
                                <div class="mb-3">
                                    <label class="text-muted small fw-bold mb-1">URL API Rút Gọn Link</label>
                                    <input type="text" name="shortlink_api_url" class="form-control" value="{api_url}" placeholder="Ví dụ: https://api.layma.net/api/admin/shortlink/quicklink">
                                    <small class="text-dark">* Format chuẩn: <code>https://api.layma.net/api/admin/shortlink/quicklink</code></small>
                                </div>
                                <div class="mb-4">
                                    <label class="text-muted small fw-bold mb-1">API Token Bí Mật</label>
                                    <input type="text" name="shortlink_api_token" class="form-control" value="{api_token}" placeholder="Dán token API rút gọn của bạn vào đây">
                                </div>
                                <button type="submit" class="btn-primary-custom"><i class="fas fa-save"></i> LƯU CẤU HÌNH</button>
                            </form>
                        </div>
                    </div>
                </div>

                <div class="col-xl-8 col-lg-12">
                    <div class="card h-100" style="border-top: 3px solid #22c55e;">
                        <div class="card-header text-dark"><div><i class="fas fa-list-alt"></i> Danh Sách Key Vượt Link Đã Tạo</div></div>
                        <div class="card-body p-0">
                            <div class="table-responsive" style="max-height: 500px; overflow-y:auto;">
                                <table class="table table-hover text-center align-middle mb-0">
                                    <thead style="position: sticky; top: 0; z-index: 1;">
                                        <tr><th>Cụm Key</th><th>Loại Vượt Link</th><th>Thời Hạn</th><th>Thiết Bị</th><th>Thao Tác</th></tr>
                                    </thead>
                                    <tbody>
                                        {keys_html or '<tr><td colspan="5" class="py-5 text-muted" style="background:#fff;">Chưa có khách nào vượt link lấy key.</td></tr>'}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/admin/update_getkey_settings', methods=['POST'])
def admin_update_getkey_settings():
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    with db_lock:
        s = db.setdefault("settings", {})
        s["games_list"] = request.form.get("games_list", "").strip()
        s["shortlink_api_url"] = request.form.get("shortlink_api_url", "").strip()
        s["shortlink_api_token"] = request.form.get("shortlink_api_token", "").strip()
        save_db(db)
    return swal_redirect("Thành Công", "Cập nhật cài đặt API Vượt Link thành công!", "success", "/admin/getkey")

@app.route('/admin/files')
def admin_files_dashboard():
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    csrf_input = f'<input type="hidden" name="csrf_token" value="{session.get("csrf_token", "")}">'
    
    with db_lock:
        current_webview_len = len(db.get("settings", {}).get("app_webview_code", ""))
        if current_webview_len > 10: webview_status = f'<span class="text-success fw-bold"><i class="fas fa-check-circle"></i> Đã nạp Giao Diện ({current_webview_len} bytes)</span>'
        else: webview_status = '<span class="text-danger fw-bold"><i class="fas fa-times-circle"></i> Chưa có Giao Diện App!</span>'

        pak_path = './uploaded.pak'
        if os.path.exists(pak_path):
            pak_size = os.path.getsize(pak_path)
            pak_status = f'<span class="text-success fw-bold"><i class="fas fa-check-circle"></i> Đã nạp File .PAK ({pak_size} bytes)</span>'
        else:
            pak_status = '<span class="text-danger fw-bold"><i class="fas fa-times-circle"></i> Chưa có File .PAK!</span>'
            
        is_maintenance = db.get("settings", {}).get("webview_maintenance", False)
        maint_btn_text = "TẮT BẢO TRÌ WEBVIEW" if is_maintenance else "BẬT BẢO TRÌ WEBVIEW"
        maint_btn_class = "btn-danger text-white" if is_maintenance else "btn-light text-dark"
        maint_status_badge = '<span class="badge bg-danger ms-2">Đang Bảo Trì</span>' if is_maintenance else '<span class="badge bg-success ms-2">Online</span>'

    return f'''
    <!DOCTYPE html><html lang="vi">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>LVT C-Panel - Auto Nạp File</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
            body {{ background: #f8fafc; font-family: 'Inter', sans-serif; color: #334155; }}
            .topbar {{ background: #ffffff; border-bottom: 1px solid #e2e8f0; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
            .topbar-brand {{ font-size: 20px; font-weight: 800; color: #0f172a; letter-spacing: 0.5px; display: flex; align-items: center; gap: 10px; }}
            .card {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.02); }}
            .card-header {{ background: #fafafa; border-bottom: 1px solid #e2e8f0; padding: 15px 20px; font-weight: 700; font-size: 14px; text-transform: uppercase; color: #0f172a; display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
            .card-body {{ padding: 20px; }}
            .form-control {{ background: #ffffff !important; border: 1px solid #cbd5e1 !important; color: #1e293b !important; border-radius: 8px; padding: 10px 15px; font-size: 14px; transition: 0.2s; }}
            .form-control:focus {{ border-color: #0f172a !important; box-shadow: 0 0 0 3px rgba(15,23,42,0.08) !important; outline: none; }}
            .btn-primary-custom {{ background: linear-gradient(135deg, #1e293b, #0f172a); border: none; color: #fff; font-weight: 700; padding: 12px 20px; border-radius: 8px; transition: 0.3s; text-transform: uppercase; width: 100%; cursor:pointer; }}
            .btn-primary-custom:hover {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
            .nav-tabs-custom {{ display: flex; gap: 15px; margin-bottom: 25px; border-bottom: 1px solid #e2e8f0; padding-bottom: 15px; }}
            .nav-btn {{ padding: 12px 25px; border-radius: 8px; font-weight: 700; color: #475569; text-decoration: none; border: 1px solid #e2e8f0; background: #ffffff; transition: 0.3s; display: inline-flex; align-items: center; gap: 8px; }}
            .nav-btn:hover {{ color: #0f172a; background: #f8fafc; }}
            .nav-btn.active {{ background: #0f172a; color: #fff; border-color: #0f172a; box-shadow: 0 4px 12px rgba(15,23,42,0.15); }}
        </style>
    </head>
    <body>
        <div class="topbar">
            <div class="topbar-brand"><i class="fas fa-server"></i> LVT C-PANEL</div>
            <a href="/logout" class="btn btn-outline-danger btn-sm fw-bold px-3 py-2" style="border-radius: 8px;"><i class="fas fa-sign-out-alt"></i> Đăng xuất</a>
        </div>
        
        <div class="container-fluid py-4 px-lg-5">
            <div class="nav-tabs-custom">
                <a href="/admin" class="nav-btn"><i class="fas fa-key"></i> QUẢN LÝ KEY & FIREWALL</a>
                <a href="/admin/getkey" class="nav-btn"><i class="fas fa-link"></i> QUẢN LÝ VƯỢT LINK (GET KEY)</a>
                <a href="/admin/files" class="nav-btn active"><i class="fas fa-cloud-upload-alt"></i> AUTO NẠP FILE TRÊN MÂY</a>
                <a href="/admin/termux" class="nav-btn"><i class="fas fa-terminal"></i> GIAO DIỆN TERMUX</a>
            </div>
            
            <div class="card mb-4" style="border-top: 3px solid #10b981;">
                <div class="card-header text-dark"><div><i class="fas fa-history"></i> KHÔI PHỤC DỮ LIỆU TỪ BACKUP TELEGRAM</div></div>
                <div class="card-body">
                    <form action="/admin/restore_db" method="POST" enctype="multipart/form-data" class="d-flex align-items-center gap-3">{csrf_input}
                        <input type="file" name="db_file" class="form-control w-50" accept=".json" required>
                        <button type="submit" class="btn-primary-custom" style="width:auto; border: 1px solid #0f172a;"><i class="fas fa-upload"></i> KHÔI PHỤC NGAY</button>
                    </form>
                </div>
            </div>

            <div class="row g-4">
                <div class="col-xl-6 col-lg-6">
                    <div class="card h-100" style="border-top: 3px solid #0f172a;">
                        <div class="card-header">
                            <div><i class="fas fa-mobile-alt"></i> NẠP GIAO DIỆN WEBVIEW APP (.HTML)</div>
                            <div>{maint_status_badge}</div>
                        </div>
                        <div class="card-body d-flex flex-column">
                            <form action="/admin/toggle_maintenance" method="POST" class="mb-3">{csrf_input}
                                <button type="submit" class="btn {maint_btn_class} w-100 fw-bold btn-sm py-2 border"><i class="fas fa-tools"></i> {maint_btn_text}</button>
                            </form>
                            <form action="/admin/update_webview" method="POST" enctype="multipart/form-data" class="h-100 d-flex flex-column">{csrf_input}
                                <div class="mb-3 p-3 text-center" style="background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px;">{webview_status}</div>
                                <input type="file" name="webview_file" class="form-control mb-2" accept=".html,.js,.txt">
                                <textarea name="webview_text" class="form-control mb-3 flex-grow-1" rows="4" placeholder="Hoặc dán trực tiếp mã nguồn Webview vào đây..."></textarea>
                                <button type="submit" class="btn-primary-custom mt-auto"><i class="fas fa-cloud-upload-alt"></i> NẠP GIAO DIỆN APP</button>
                            </form>
                        </div>
                    </div>
                </div>

                <div class="col-xl-6 col-lg-6">
                    <div class="card h-100" style="border-top: 3px solid #0f172a;">
                        <div class="card-header"><div><i class="fas fa-file-archive"></i> NẠP FILE .PAK (DATA)</div></div>
                        <div class="card-body d-flex flex-column">
                            <form id="pakUploadForm" action="/admin/update_pak" method="POST" enctype="multipart/form-data" class="h-100 d-flex flex-column">{csrf_input}
                                <div class="mb-3 p-3 text-center" style="background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px;">{pak_status}</div>
                                <input type="file" name="pak_file" class="form-control mb-2" accept=".pak">
                                <input type="url" name="pak_url" class="form-control mb-3" placeholder="Hoặc dán Link trực tiếp tải file .pak (Direct URL)...">
                                <div class="progress mb-3 d-none" id="pakUploadProgressContainer" style="height: 22px; border-radius: 8px;">
                                    <div id="pakUploadProgressBar" class="progress-bar progress-bar-striped progress-bar-animated bg-success fw-bold" role="progressbar" style="width: 0%;">0%</div>
                                </div>
                                <div id="pakUploadStatusText" class="text-center small mb-2 text-primary fw-bold"></div>
                                <button type="submit" class="btn-primary-custom mt-auto"><i class="fas fa-cloud-upload-alt"></i> NẠP FILE .PAK</button>
                            </form>
                            <script>
                                document.getElementById('pakUploadForm').addEventListener('submit', function(e) {{
                                    var fileInput = this.querySelector('input[name="pak_file"]');
                                    var urlInput = this.querySelector('input[name="pak_url"]');
                                    if (urlInput.value.trim() !== "") {{
                                        return;
                                    }}
                                    if (!fileInput.files || fileInput.files.length === 0) {{
                                        return;
                                    }}
                                    e.preventDefault();
                                    var formData = new FormData(this);
                                    var xhr = new XMLHttpRequest();
                                    var pContainer = document.getElementById('pakUploadProgressContainer');
                                    var pBar = document.getElementById('pakUploadProgressBar');
                                    var pStatus = document.getElementById('pakUploadStatusText');
                                    var btn = this.querySelector('button[type="submit"]');
                                    
                                    pContainer.classList.remove('d-none');
                                    btn.disabled = true;
                                    xhr.upload.addEventListener('progress', function(e) {{
                                        if (e.lengthComputable) {{
                                            var percent = Math.round((e.loaded / e.total) * 100);
                                            pBar.style.width = percent + '%';
                                            pBar.innerText = percent + '%';
                                            pStatus.innerText = "Đang nạp dữ liệu: " + (e.loaded / (1024*1024)).toFixed(1) + "MB / " + (e.total / (1024*1024)).toFixed(1) + "MB";
                                        }}
                                    }});
                                    xhr.onreadystatechange = function() {{
                                        if (xhr.readyState === 4) {{
                                            btn.disabled = false;
                                            if (xhr.status === 200) {{
                                                try {{
                                                    var res = JSON.parse(xhr.responseText);
                                                    if (res.status === 'success') {{
                                                        Swal.fire({{ title: 'Thành Công', html: res.message, icon: 'success', confirmButtonColor: '#0f172a' }}).then(() => {{ window.location.reload(); }});
                                                    }} else {{
                                                        Swal.fire({{ title: 'Lỗi', html: res.message, icon: 'error', confirmButtonColor: '#0f172a' }});
                                                    }}
                                                }} catch(err) {{
                                                    window.location.reload();
                                                }}
                                            }} else {{
                                                Swal.fire({{ title: 'Lỗi', html: 'Lỗi kết nối server hoặc kích thước quá giới hạn!', icon: 'error', confirmButtonColor: '#0f172a' }});
                                            }}
                                        }}
                                    }};
                                    xhr.open('POST', '/admin/update_pak', true);
                                    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
                                    xhr.send(formData);
                                }});
                            </script>
                        </div>
                    </div>
                </div>

            </div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    '''

@app.route('/admin/termux')
def admin_termux_dashboard():
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    csrf_input = f'<input type="hidden" name="csrf_token" value="{session.get("csrf_token", "")}">'
    settings = db.get("settings", {})
    termux_script = escape(settings.get("termux_script", ""))
    
    return f'''
    <!DOCTYPE html><html lang="vi">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>LVT C-Panel - Giao Diện Termux</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
            body {{ background: #f8fafc; font-family: 'Inter', sans-serif; color: #334155; }}
            .topbar {{ background: #ffffff; border-bottom: 1px solid #e2e8f0; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
            .topbar-brand {{ font-size: 20px; font-weight: 800; color: #0f172a; letter-spacing: 0.5px; display: flex; align-items: center; gap: 10px; }}
            .card {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.02); }}
            .card-header {{ background: #fafafa; border-bottom: 1px solid #e2e8f0; padding: 15px 20px; font-weight: 700; font-size: 14px; text-transform: uppercase; color: #0f172a; display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
            .card-body {{ padding: 20px; }}
            .form-control {{ background: #ffffff !important; border: 1px solid #cbd5e1 !important; color: #1e293b !important; border-radius: 8px; padding: 10px 15px; font-size: 14px; transition: 0.2s; }}
            .form-control:focus {{ border-color: #0f172a !important; box-shadow: 0 0 0 3px rgba(15,23,42,0.08) !important; outline: none; }}
            .btn-primary-custom {{ background: linear-gradient(135deg, #1e293b, #0f172a); border: none; color: #fff; font-weight: 700; padding: 12px 20px; border-radius: 8px; transition: 0.3s; text-transform: uppercase; width: 100%; cursor:pointer; }}
            .btn-primary-custom:hover {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
            .nav-tabs-custom {{ display: flex; gap: 15px; margin-bottom: 25px; border-bottom: 1px solid #e2e8f0; padding-bottom: 15px; }}
            .nav-btn {{ padding: 12px 25px; border-radius: 8px; font-weight: 700; color: #475569; text-decoration: none; border: 1px solid #e2e8f0; background: #ffffff; transition: 0.3s; display: inline-flex; align-items: center; gap: 8px; }}
            .nav-btn:hover {{ color: #0f172a; background: #f8fafc; }}
            .nav-btn.active {{ background: #0f172a; color: #fff; border-color: #0f172a; box-shadow: 0 4px 12px rgba(15,23,42,0.15); }}
        </style>
    </head>
    <body>
        <div class="topbar">
            <div class="topbar-brand"><i class="fas fa-server"></i> LVT C-PANEL</div>
            <a href="/logout" class="btn btn-outline-danger btn-sm fw-bold px-3 py-2" style="border-radius: 8px;"><i class="fas fa-sign-out-alt"></i> Đăng xuất</a>
        </div>
        
        <div class="container-fluid py-4 px-lg-5">
            <div class="nav-tabs-custom">
                <a href="/admin" class="nav-btn"><i class="fas fa-key"></i> QUẢN LÝ KEY & FIREWALL</a>
                <a href="/admin/getkey" class="nav-btn"><i class="fas fa-link"></i> QUẢN LÝ VƯỢT LINK (GET KEY)</a>
                <a href="/admin/files" class="nav-btn"><i class="fas fa-cloud-upload-alt"></i> AUTO NẠP FILE TRÊN MÂY</a>
                <a href="/admin/termux" class="nav-btn active"><i class="fas fa-terminal"></i> GIAO DIỆN TERMUX</a>
            </div>

            <div class="row g-4">
                <div class="col-xl-6 col-lg-12">
                    <div class="card h-100" style="border-top: 3px solid #10b981;">
                        <div class="card-header"><div><i class="fas fa-file-code"></i> Nạp File Code Termux Cấu Hình Động</div></div>
                        <div class="card-body">
                            <form action="/admin/update_termux" method="POST" enctype="multipart/form-data">{csrf_input}
                                <div class="mb-3">
                                    <label class="text-muted small fw-bold mb-1">Tải file (.py, .sh, .txt) lên</label>
                                    <input type="file" name="termux_file" class="form-control" accept=".py,.sh,.txt">
                                </div>
                                <div class="mb-3">
                                    <label class="text-muted small fw-bold mb-1">Hoặc dán trực tiếp mã nguồn script Termux</label>
                                    <textarea name="termux_text" class="form-control font-monospace" rows="14" placeholder="Dán nội dung script của bạn vào đây. Các biến hỗ trợ sẽ tự động được thay thế...">{termux_script}</textarea>
                                </div>
                                <button type="submit" class="btn-primary-custom"><i class="fas fa-save"></i> LƯU MÃ NGUỒN TERMUX</button>
                            </form>
                        </div>
                    </div>
                </div>

                <div class="col-xl-6 col-lg-12">
                    <div class="card h-100" style="border-top: 3px solid #0f172a;">
                        <div class="card-header text-dark"><div><i class="fas fa-info-circle"></i> Trạng Thái Auto Thay Đổi Chức Năng</div></div>
                        <div class="card-body">
                            <h5 class="text-dark fw-bold mb-3">Mô Tả Chức Năng:</h5>
                            <p class="text-muted"><i class="fas fa-check text-success"></i> <b>Cấu Hình Động:</b> File mã nguồn này sẽ được phân phối qua API tự động. Khi khách hàng tải file từ hệ thống, dữ liệu chức năng, tên game và các thông tin khác sẽ được tự thay đổi cho phù hợp.</p>
                            <p class="text-muted"><i class="fas fa-check text-success"></i> <b>Cập Nhật Tức Thời:</b> Mọi thay đổi tại đây sẽ được đẩy thẳng xuống toàn bộ người dùng đang tải code từ hệ thống.</p>
                        
                            <hr>
                            <div class="p-3 mt-3" style="background:#f1f5f9; border-radius:8px;">
                                <h6 class="fw-bold mb-2">Các Biến Hỗ Trợ (Placeholder):</h6>
                                <p class="small text-dark mb-1">Bạn có thể chèn các đoạn mã sau trực tiếp vào script, server sẽ <b>tự động thay thế</b> chúng trước khi trả code về máy khách:</p>
                                <ul class="small text-dark mb-0">
                                    <li><code>{{KEY}}</code> - Sẽ tự động lấy Mã Key của khách hàng truyền vào.</li>
                                    <li><code>{{WEB_URL}}</code> - Sẽ tự động đổi thành tên miền URL hiện tại của Server (vd: {WEB_URL}).</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/admin/update_termux', methods=['POST'])
def admin_update_termux():
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    
    script_content = request.form.get('termux_text', '').strip()
    if 'termux_file' in request.files and request.files['termux_file'].filename != '':
        try: script_content = request.files['termux_file'].read().decode('utf-8')
        except: return swal_back("Lỗi", "File không hợp lệ", "error")
        
    with db_lock:
        s = db.setdefault("settings", {})
        s["termux_script"] = script_content
        save_db(db)
        
    return swal_redirect("Thành Công", "Đã nạp file Termux thành công!", "success", "/admin/termux")

@app.route('/admin/toggle_maintenance', methods=['POST'])
def admin_toggle_maintenance():
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    with db_lock:
        current_status = db.setdefault("settings", {}).get("webview_maintenance", False)
        db["settings"]["webview_maintenance"] = not current_status
        save_db(db)
    return redirect('/admin/files')

@app.route('/admin/create', methods=['POST'])
def create_key():
    if session.get('role') != 'admin': return redirect('/admin_login')
    dur = safe_int(request.form.get('duration'))
    md = safe_int(request.form.get('devices'), 1)
    qty = safe_int(request.form.get('quantity'), 1)
    t = request.form.get('type')
    vip = request.form.get('is_vip') == 'on'
    gen_type = request.form.get('gen_type', 'auto')
    manual_key = request.form.get('manual_key', '').strip()

    db = load_db()
    with db_lock:
        if gen_type == 'manual' and manual_key:
            if manual_key in db.get("keys", {}):
                return swal_back("Lỗi", "Key thủ công này đã tồn tại trong hệ thống!", "error")
            nk = manual_key
            db["keys"][nk] = {"exp": "pending", "maxDevices": md, "devices": [], "vip": vip, "status": "active", "bound_olm": "", "proxy_host": "", "proxy_port": 8080, "ban_until": 0, "note": ""}
            if t != 'permanent': db["keys"][nk]["durationMs"] = dur * {"minute":60000, "hour":3600000, "day":86400000, "month":2592000000}.get(t, 60000)
            else: db["keys"][nk]["exp"] = "permanent"
            exp_text = "Vĩnh viễn" if t == "permanent" else f"{dur} {'Phút' if t=='minute' else 'Giờ' if t=='hour' else 'Ngày' if t=='day' else 'Tháng'}"
            send_telegram_event('create', {'key': nk, 'exp': exp_text, 'max_dev': md})
        else:
            for _ in range(qty):
                nk = generate_proxy_key()
                db["keys"][nk] = {"exp": "pending", "maxDevices": md, "devices": [], "vip": vip, "status": "active", "bound_olm": "", "proxy_host": "", "proxy_port": 8080, "ban_until": 0, "note": ""}
                if t != 'permanent': db["keys"][nk]["durationMs"] = dur * {"minute":60000, "hour":3600000, "day":86400000, "month":2592000000}.get(t, 60000)
                else: db["keys"][nk]["exp"] = "permanent"
                exp_text = "Vĩnh viễn" if t == "permanent" else f"{dur} {'Phút' if t=='minute' else 'Giờ' if t=='hour' else 'Ngày' if t=='day' else 'Tháng'}"
                send_telegram_event('create', {'key': nk, 'exp': exp_text, 'max_dev': md})
        save_db(db)
    return redirect('/admin')

@app.route('/admin/edit_note', methods=['POST'])
def admin_edit_note():
    if session.get('role') != 'admin': return redirect('/admin_login')
    key = request.form.get('key', '').strip()
    note = request.form.get('note_text', '').strip()
    db = load_db()
    with db_lock:
        if key in db.get("keys", {}):
            db["keys"][key]["note"] = note
            save_db(db)
    return redirect('/admin')

@app.route('/admin/add_time', methods=['POST'])
def admin_add_time():
    if session.get('role') != 'admin': return redirect('/admin_login')
    key = request.form.get('key', '').strip()
    t_val = safe_int(request.form.get('time_val', 0))
    t_unit = request.form.get('time_unit', 'days')
    if t_val <= 0: return redirect('/admin')
    ms_to_add = t_val * {"minutes": 60000, "hours": 3600000, "days": 86400000, "months": 2592000000}.get(t_unit, 0)
    db = load_db()
    with db_lock:
        if key in db.get("keys", {}):
            kd = db["keys"][key]
            if kd.get("exp") == "permanent": return swal_back("Lỗi", "Key vĩnh viễn không cần cộng!", "error")
            now = int(time.time() * 1000)
            if kd.get("exp") == "pending": kd["durationMs"] = kd.get("durationMs", 0) + ms_to_add
            else: kd["exp"] = max(kd.get("exp", now), now) + ms_to_add
            save_db(db)
    return redirect('/admin')

@app.route('/admin/edit_max_dev', methods=['POST'])
def admin_edit_max_dev():
    if session.get('role') != 'admin': return redirect('/admin_login')
    key = request.form.get('key', '').strip()
    max_dev = safe_int(request.form.get('max_dev'), 1)
    db = load_db()
    with db_lock:
        if key in db.get("keys", {}):
            db["keys"][key]["maxDevices"] = max_dev
            save_db(db)
    return redirect('/admin')

@app.route('/admin/custom_ban', methods=['POST'])
def admin_custom_ban():
    if session.get('role') != 'admin': return redirect('/admin_login')
    key = request.form.get('key', '').strip()
    t_val = safe_int(request.form.get('time_val', 0))
    t_unit = request.form.get('time_unit', 'permanent')
    db = load_db()
    with db_lock:
        if key in db.get("keys", {}):
            kd = db["keys"][key]
            kd["status"] = "banned"
            if t_unit == 'permanent': kd["ban_until"] = "permanent"
            else:
                ms_to_add = t_val * {"minutes": 60000, "hours": 3600000, "days": 86400000, "months": 2592000000}.get(t_unit, 0)
                kd["ban_until"] = int(time.time() * 1000) + ms_to_add
            save_db(db)
    return redirect('/admin')

@app.route('/admin/bind_olm', methods=['POST'])
def admin_bind_olm():
    if session.get('role') != 'admin': return redirect('/admin_login')
    key = request.form.get('key', '').strip()
    olm = request.form.get('olm_name', '').strip()
    if not olm: return swal_back("Lỗi", "Vui lòng nhập tên định danh OLM!", "error")
    db = load_db()
    with db_lock:
        if key in db.get("keys", {}):
            db["keys"][key]["bound_olm"] = olm
            save_db(db)
    return redirect('/admin')

@app.route('/admin/restore_db', methods=['POST'])
def admin_restore_db():
    if session.get('role') != 'admin': return redirect('/admin_login')
    if 'db_file' not in request.files: return swal_back("Lỗi", "Chưa chọn file database.json!", "error")
    file = request.files['db_file']
    if file.filename == '': return swal_back("Lỗi", "Chưa chọn file!", "error")
    try:
        content = file.read().decode('utf-8')
        json_data = json.loads(content)
        with db_lock:
            temp_file = DB_FILE + '.restore.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(json.dumps(json_data, indent=2, ensure_ascii=False))
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, DB_FILE)
            global GLOBAL_DB, _last_db_mtime, _last_mtime_check
            GLOBAL_DB = json_data
            _last_db_mtime = os.path.getmtime(DB_FILE)
            _last_mtime_check = time.time()
    except Exception as e: return swal_back("Lỗi", f"Định dạng file không hợp lệ hoặc lỗi khôi phục: {escape_swal(str(e))}", "error")
    return swal_redirect("Khôi Phục Thành Công", "Đã khôi phục toàn bộ Key và Dữ Liệu gốc thành công!", "success", "/admin")

@app.route('/admin/update_webview', methods=['POST'])
def admin_update_webview():
    if session.get('role') != 'admin': return redirect('/admin_login')
    script_content = request.form.get('webview_text', '').strip()
    if not script_content and 'webview_file' in request.files and request.files['webview_file'].filename != '':
        try: script_content = request.files['webview_file'].read().decode('utf-8')
        except: return swal_back("Lỗi", "File không hợp lệ (.html/.txt)", "error")
    if not script_content: return swal_back("Lỗi", "Vui lòng chọn File hoặc dán Mã Nguồn!", "error")
    db = load_db()
    with db_lock:
        db.setdefault("settings", {})["app_webview_code"] = script_content
        save_db(db)
    return swal_redirect("Thành Công", "Đã nạp Giao diện WebView thành công!", "success", "/admin/files")

@app.route('/admin/update_pak', methods=['POST'])
def admin_update_pak():
    if session.get('role') != 'admin':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"status": "error", "message": "Hết phiên làm việc!"}), 401
        return redirect('/admin_login')
        
    pak_url = request.form.get('pak_url', '').strip()
    pak_path = './uploaded.pak'
    temp_pak_path = './uploaded.pak.tmp'
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    try:
        if pak_url:
            r = requests.get(pak_url, stream=True, timeout=30)
            r.raise_for_status()
            with open(temp_pak_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            os.replace(temp_pak_path, pak_path)
        else:
            if 'pak_file' not in request.files or request.files['pak_file'].filename == '':
                if is_ajax: return jsonify({"status": "error", "message": "Chưa chọn file hoặc dán Link URL!"})
                return swal_back("Lỗi", "Chưa chọn file hoặc dán Link URL!", "error")
            
            file = request.files['pak_file']
            with open(temp_pak_path, 'wb') as f:
                while True:
                    chunk = file.stream.read(64 * 1024) 
                    if not chunk: break
                    f.write(chunk)
            os.replace(temp_pak_path, pak_path)
            
        db = load_db()
        save_db(db)
        
        if is_ajax: 
            return jsonify({"status": "success", "message": "Đã nạp file .PAK thành công!"})
    except Exception as e:
        if os.path.exists(temp_pak_path):
            try: os.remove(temp_pak_path)
            except: pass
        err_msg = f"Không thể lưu file .pak: {escape_swal(str(e))}"
        if is_ajax: return jsonify({"status": "error", "message": err_msg})
        return swal_back("Lỗi", err_msg, "error")
        
    return swal_redirect("Thành Công", "Đã nạp file .PAK thành công!", "success", "/admin/files")

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
except Exception: app.secret_key = secrets.token_hex(32)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
