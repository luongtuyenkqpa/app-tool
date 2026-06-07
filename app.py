import os, json, time, random, hashlib, threading, requests, shutil, base64, secrets, hmac, string, copy, traceback, ssl, re
import urllib.parse
from html import escape
from flask import Flask, request, jsonify, redirect, make_response, session, abort, send_file, render_template_string
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

# [VÁ LỖI LỆCH MÚI GIỜ CLOUD]
try:
    os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
    time.tzset()
except: pass

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# ========================================================
# GIAO DIỆN HIỆU ỨNG TRẮNG (WHITE THEME)
# ========================================================
CSS_GLASS = """
.glass-panel { background: rgba(20, 20, 25, 0.8); backdrop-filter: blur(15px); border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 15px; padding: 30px; box-shadow: 0 0 20px rgba(255, 255, 255, 0.15); text-align: center; }
.text-neon { color: #ffffff; text-shadow: 0 0 15px rgba(255, 255, 255, 0.6); }
.btn-neon { background: linear-gradient(90deg, #ffffff, #d1d5db); border: none; color: #000; font-weight: bold; padding: 12px 20px; border-radius: 8px; width: 100%; transition: 0.3s; text-transform: uppercase; cursor: pointer; }
.btn-neon:hover { transform: scale(1.05); box-shadow: 0 0 20px rgba(255, 255, 255, 0.4); }
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

def send_telegram_alert(message): pass 

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
                            keyboard = {"inline_keyboard": [[{"text": "🌐 MỞ TRANG LẤY KEY VÀ PROXY", "web_app": {"url": f"{WEB_URL}/"}}]]}
                            requests.post(url_base + "/sendMessage", json={"chat_id": chat_id, "text": welcome, "parse_mode": "HTML", "reply_markup": keyboard})
        except Exception: pass
        time.sleep(2)

threading.Thread(target=telegram_polling, daemon=True).start()

def keep_awake():
    while True:
        time.sleep(14 * 60)
        try: requests.get(WEB_URL, timeout=10)
        except Exception: pass

threading.Thread(target=keep_awake, daemon=True).start()

@app.route('/ping')
def ping_server(): return "OK", 200

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException): return e
    return f"""<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Server Updating</title><style>body {{ background: #05050A; color: #ffffff; display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100vh; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; margin: 0; }} .loader {{ border: 5px solid rgba(255, 255, 255, 0.2); border-top: 5px solid #ffffff; border-radius: 50%; width: 60px; height: 60px; animation: spin 1s linear infinite; margin-bottom: 20px; box-shadow: 0 0 15px rgba(255, 255, 255, 0.5); }} @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }} h2 {{ text-shadow: 0 0 10px rgba(255, 255, 255, 0.5); letter-spacing: 1px; }}</style></head><body><div class="loader"></div><h2>Đang update online server vui lòng đợi...</h2></body></html>""", 500

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

# Hệ thống lưu session vượt link tạm thời
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
    return f"""<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #05050A; }}</style></head><body><script>Swal.fire({{ title: {json.dumps(title)}, html: {json.dumps(text)}, icon: {json.dumps(icon)}, background: '#11111A', color: '#fff', confirmButtonColor: '#ffffff', allowOutsideClick: false }}).then(() => {{ window.location.href = {json.dumps(url)}; }});</script></body></html>"""

def swal_back(title, text, icon):
    return f"""<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #05050A; }}</style></head><body><script>Swal.fire({{ title: {json.dumps(title)}, html: {json.dumps(text)}, icon: {json.dumps(icon)}, background: '#11111A', color: '#fff', confirmButtonColor: '#ffffff', allowOutsideClick: false }}).then(() => {{ window.history.back(); }});</script></body></html>"""

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
                if "script_tiem" not in data["settings"]: data["settings"]["script_tiem"] = ""
                if "vm_loader" not in data["settings"]: data["settings"]["vm_loader"] = ""
                if "app_webview_code" not in data["settings"]: data["settings"]["app_webview_code"] = ""
                if "tg_admins" not in data["settings"]: data["settings"]["tg_admins"] = [TELEGRAM_CHAT_ID]
                if "webview_maintenance" not in data["settings"]: data["settings"]["webview_maintenance"] = False
                
                # Biến dùng cho Trang 3: Get Key Vượt Link
                if "games_list" not in data["settings"]: data["settings"]["games_list"] = "PUBG, LIENQUAN, FREEFIRE"
                if "shortlink_api_url" not in data["settings"]: data["settings"]["shortlink_api_url"] = "https://link1s.com/api"
                if "shortlink_api_token" not in data["settings"]: data["settings"]["shortlink_api_token"] = ""

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
            # Xoá session vượt link quá 1 tiếng
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
        ua = (request.headers.get('User-Agent') or '').lower()
        blocked_bots = ['curl', 'postman', 'python', 'nmap', 'sqlmap', 'masscan', 'zgrab', 'wget', 'urllib', 'nikto']
        if any(bot in ua for bot in blocked_bots): return "Firewall Blocked.", 403
            
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
                    if ban_until == "permanent" or (isinstance(ban_until, int) and ban_until > now):
                        return jsonify({"banned": True, "reason": "Key của bạn đã bị Admin khóa. Bạn đã bị kick khỏi hệ thống!", "ban_time": ban_until})
                    else:
                        v["status"] = "active"
                        save_db(db)
                        return jsonify({"banned": False})
    return jsonify({"banned": False})

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
                    localStorage.removeItem('lvt_proxy_key'); // Xóa key lưu ẩn
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
        html_content = f"""<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>App Maintenance</title><style>body {{ background: #05050A; color: #ffffff; display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100vh; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; margin: 0; }} .pulse {{ width: 70px; height: 70px; background: #ffffff; border-radius: 50%; animation: pulse-anim 2s infinite; margin-bottom: 20px; box-shadow: 0 0 20px rgba(255, 255, 255, 0.6); }} @keyframes pulse-anim {{ 0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.7); }} 70% {{ transform: scale(1); box-shadow: 0 0 0 20px rgba(255, 255, 255, 0); }} 100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(255, 255, 255, 0); }} }} h2 {{ text-shadow: 0 0 10px rgba(255, 255, 255, 0.5); letter-spacing: 1px; }} p {{ color: #a1a1aa; font-size: 14px; margin-top: 5px; }}</style></head><body><div class="pulse"></div><h2>Đang update online app</h2><p>Hệ thống đang được nâng cấp, vui lòng quay lại sau!</p></body></html>"""
    else:
        html_content = db.get("settings", {}).get("app_webview_code", "<h1>Hệ thống chưa được nạp giao diện WebView. Vui lòng liên hệ Admin!</h1>")
    resp = make_response(html_content)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp

# ========================================================
# TRANG CHỦ MỚI: GIAO DIỆN GET KEY VƯỢT LINK
# ========================================================
@app.route('/')
def get_key_portal():
    db = load_db()
    games_raw = db.get("settings", {}).get("games_list", "PUBG, LIENQUAN, FREEFIRE")
    games = [g.strip() for g in games_raw.split(',') if g.strip()]
    options_html = "".join([f'<option value="{escape(g)}">{escape(g)}</option>' for g in games])
    
    return f'''
    <!DOCTYPE html><html lang="vi" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>GET KEY VIP - HỆ THỐNG AUTO</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
            body {{ background: #0a0a0c; font-family: 'Inter', sans-serif; color: #e2e8f0; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
            .get-key-box {{ background: rgba(20, 20, 25, 0.9); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 16px; padding: 30px; width: 100%; max-width: 450px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); text-align: center; }}
            .logo-icon {{ font-size: 40px; color: #ffffff; text-shadow: 0 0 15px rgba(255,255,255,0.4); margin-bottom: 10px; }}
            .form-select, .form-control {{ background: rgba(0,0,0,0.4) !important; border: 1px solid rgba(255,255,255,0.2) !important; color: #fff !important; padding: 12px; border-radius: 8px; text-align: center; font-weight: 600; margin-bottom: 15px; }}
            .form-select:focus {{ border-color: #ffffff !important; box-shadow: 0 0 10px rgba(255,255,255,0.2) !important; }}
            .btn-getkey {{ background: #ffffff; color: #000; font-weight: 800; padding: 14px; border-radius: 8px; width: 100%; border: none; transition: 0.3s; text-transform: uppercase; font-size: 16px; letter-spacing: 1px; margin-top: 10px; box-shadow: 0 0 15px rgba(255,255,255,0.2); }}
            .btn-getkey:hover {{ transform: translateY(-2px); box-shadow: 0 0 25px rgba(255,255,255,0.4); background: #f8fafc; }}
            .footer-text {{ font-size: 12px; color: #64748b; margin-top: 20px; }}
            label {{ font-size: 13px; text-transform: uppercase; letter-spacing: 1px; color: #94a3b8; margin-bottom: 5px; display: block; font-weight: 600; text-align: left; }}
        </style>
    </head>
    <body>
        <div class="container d-flex justify-content-center">
            <div class="get-key-box">
                <i class="fas fa-key logo-icon"></i>
                <h3 class="fw-bold mb-4" style="color: #ffffff;">NHẬN KEY VIP SERVER</h3>
                <form action="/start_bypass" method="POST">
                    <label><i class="fas fa-gamepad"></i> Chọn Tựa Game</label>
                    <select name="game" class="form-select" required>
                        {options_html}
                    </select>
                    
                    <label><i class="fas fa-link"></i> Chọn Mức Độ (Gói Thời Gian)</label>
                    <select name="steps" class="form-select" required>
                        <option value="1">Vượt 1 Lần Link ➔ Key 12H VIP</option>
                        <option value="2">Vượt 2 Lần Link ➔ Key 24H VIP</option>
                    </select>

                    <button type="submit" class="btn-getkey"><i class="fas fa-rocket"></i> BẮT ĐẦU VƯỢT LINK</button>
                </form>
                <div class="footer-text">
                    Lưu ý: Thiết bị tối đa cho mỗi Key vượt link là 1 máy.<br>Hoàn thành vượt link Key sẽ tự động hiển thị để Copy.
                </div>
            </div>
        </div>
    </body>
    </html>
    '''

def call_shortlink_api(url_to_shorten):
    db = load_db()
    api_url = db.get("settings", {}).get("shortlink_api_url", "").strip()
    api_token = db.get("settings", {}).get("shortlink_api_token", "").strip()
    
    if not api_url or not api_token: return url_to_shorten 
    
    try:
        # API Thường dùng cho các site link rút gọn VN (Link1s, MegaUrl...)
        # Format: domain.com/api?api=TOKEN&url=URL
        full_url = f"{api_url}?api={api_token}&url={urllib.parse.quote(url_to_shorten)}"
        res = requests.get(full_url, timeout=10).json()
        if res.get("status") == "success" or res.get("status") == 200:
            return res.get("shortenedUrl") or res.get("short_url", url_to_shorten)
    except Exception as e:
        print("Lỗi tạo shortlink:", e)
    return url_to_shorten

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
    
    # Nếu chọn gói vượt 2 lần link (24H) mà mới xong bước 1
    if s_data["current_step"] < s_data["steps"]:
        s_data["current_step"] += 1
        return_url = f"{WEB_URL}/verify_bypass?session={session_id}"
        short_url = call_shortlink_api(return_url)
        return redirect(short_url)
        
    # Hoàn thành đủ bước -> Sinh Key
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
    del bypass_sessions[session_id] # Xoá session an toàn
    
    return f'''
    <!DOCTYPE html><html lang="vi" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>NHẬN KEY THÀNH CÔNG</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
            body {{ background: #0a0a0c; font-family: 'Inter', sans-serif; color: #e2e8f0; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
            .result-box {{ background: rgba(20, 20, 25, 0.9); border: 1px solid #22c55e; border-radius: 16px; padding: 40px 30px; width: 100%; max-width: 450px; text-align: center; box-shadow: 0 0 30px rgba(34, 197, 94, 0.2); }}
            .key-display {{ background: rgba(0,0,0,0.5); padding: 15px; font-size: 22px; font-family: monospace; font-weight: bold; color: #22c55e; border-radius: 8px; border: 1px dashed #22c55e; margin: 20px 0; letter-spacing: 1px; word-break: break-all; }}
            .btn-copy {{ background: #22c55e; color: #000; font-weight: 800; padding: 12px; border-radius: 8px; width: 100%; border: none; transition: 0.3s; margin-bottom: 15px; }}
            .btn-copy:hover {{ background: #16a34a; transform: translateY(-2px); }}
            .btn-home {{ background: transparent; color: #94a3b8; border: 1px solid #475569; padding: 10px; border-radius: 8px; width: 100%; font-weight: 600; text-decoration: none; display: inline-block; }}
        </style>
    </head>
    <body>
        <div class="container d-flex justify-content-center">
            <div class="result-box">
                <i class="fas fa-check-circle mb-3" style="font-size: 50px; color: #22c55e;"></i>
                <h3 class="fw-bold text-white">VƯỢT LINK THÀNH CÔNG</h3>
                <p class="text-muted">Bạn đã nhận được KEY VIP. Vui lòng copy và dán vào tool/app để sử dụng.</p>
                
                <div class="key-display" id="myKey">{key_name}</div>
                
                <button class="btn-copy" onclick="copyKey()"><i class="far fa-copy"></i> COPY KEY NGAY</button>
                <a href="/" class="btn-home"><i class="fas fa-home"></i> TRỞ VỀ TRANG CHỦ</a>
            </div>
        </div>
        <script>
            function copyKey() {{
                navigator.clipboard.writeText(document.getElementById("myKey").innerText);
                Swal.fire({{toast: true, position: 'top-end', icon: 'success', title: 'Đã copy Key!', showConfirmButton: false, timer: 2000, background: '#1e293b', color: '#fff'}});
            }}
        </script>
    </body>
    </html>
    '''

# ========================================================
# XÁC THỰC LÕI HACK / CHECK KEY APP
# ========================================================
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
        if len(reqs) >= 30: return jsonify({"status": "error", "msg": "Phát hiện lạm dụng API (Spam)! Vui lòng thử lại sau 1 phút."})
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

# ========================================================
# GIAO DIỆN WEB ADMIN (PC C-PANEL) - WHITE/MINIMAL THEME
# ========================================================
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
            
        return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><title>C-Panel Admin Đăng Nhập</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>{CSS_GLASS} .inp-neon {{ background: rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.3); color: #fff; padding: 12px; border-radius: 8px; width: 100%; margin-bottom: 15px; outline: none; transition: 0.3s; text-align: center; }} .inp-neon:focus {{ border-color: #ffffff; box-shadow: 0 0 10px rgba(255,255,255,0.2); }}</style></head><body style="background:#0b0f19; display:flex; justify-content:center; align-items:center; height:100vh;"><div class="container"><div class="glass-panel mx-auto" style="max-width:400px; background:#131722;"><h2 class="text-neon mb-4"><i class="fas fa-user-shield"></i> LVT C-PANEL</h2><form method="POST"><input type="text" name="username" class="inp-neon" placeholder="Tài khoản Quản Trị" required><input type="password" name="password" class="inp-neon" placeholder="Mật Khẩu" required><button type="submit" class="btn-neon mt-2"><i class="fas fa-sign-in-alt"></i> TRUY CẬP HỆ THỐNG</button></form></div></div></body></html>'''
    except Exception as e: return f"LỖI: {str(e)}", 200

# [TRANG 1: QUẢN LÝ KEY VÀ FIREWALL]
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

        vip_badge = '<span class="badge badge-custom" style="background:#e2e8f0; color:#000;"><i class="fas fa-crown"></i> VIP</span>' if data.get('vip', False) else '<span class="badge badge-custom bg-secondary">Thường</span>'
        
        is_expired = False
        if data.get('exp') == 'pending': exp_text = '<span class="badge badge-custom bg-info text-dark">Chưa kích hoạt</span>'
        elif data.get('exp') == 'permanent': exp_text = '<span class="text-success fw-bold">Vĩnh Viễn</span>'
        else:
            is_expired = now_ms > data.get('exp', 0)
            exp_text = f'<span class="{"text-danger fw-bold" if is_expired else "text-light"}">{time.strftime("%d/%m/%y %H:%M", time.localtime(data.get("exp", 0) / 1000))}</span>'
        
        if is_expired and not is_banned: status_badge = '<span class="badge badge-custom bg-secondary">Hết hạn</span>'
        
        safe_k = escape(str(k))
        bound_olm = escape(data.get('bound_olm', ''))

        keys_html += f'''<tr class="key-row">
        <td>
            <div class="fw-bold text-white font-monospace mb-1" style="font-size:15px; cursor:pointer;" onclick="copyToClipboard('{safe_k}')">{safe_k} <i class="far fa-copy text-muted small"></i></div>
            <div class="d-flex gap-1 justify-content-center">{vip_badge} {status_badge}</div>
        </td>
        <td>{exp_text}</td>
        <td class="text-center"><span class="text-white fw-bold">{bound_olm or '---'}</span></td>
        <td><span class="badge bg-dark border border-secondary p-2 fs-6 text-white">{len(data.get('devices', []))}/{data.get('maxDevices', 1)}</span></td>
        <td>
            <div class="d-flex flex-wrap gap-2 justify-content-center">
                <button class="action-btn text-light" style="background: rgba(255,255,255,0.1);" data-key="{safe_k}" data-note="{note}" onclick="openNoteModal(this.getAttribute('data-key'), this.getAttribute('data-note'))" title="Ghi Chú"><i class="fas fa-sticky-note"></i></button>
                <button class="action-btn text-white" data-key="{safe_k}" data-olm="{bound_olm}" onclick="openBindModal(this.getAttribute('data-key'), this.getAttribute('data-olm'))" title="Ghim Tên"><i class="fas fa-user-tag"></i></button>
                <button class="action-btn text-white" data-key="{safe_k}" onclick="openAddTimeModal(this.getAttribute('data-key'))" title="Bơm Giờ"><i class="fas fa-clock"></i></button>
                <a href="/admin/action/reset_dev/{safe_k}?csrf_token={token_url}" class="action-btn text-white" onclick="return confirm('Xóa sạch lịch sử thiết bị của Key này?')" title="Reset Thiết Bị"><i class="fas fa-sync-alt"></i></a>
                <button class="action-btn text-white" data-key="{safe_k}" data-max="{data.get('maxDevices', 1)}" onclick="openMaxDevModal(this.getAttribute('data-key'), this.getAttribute('data-max'))" title="Giới Hạn Máy"><i class="fas fa-mobile-alt"></i></button>
                {ban_btn}
                <a href="/admin/action/delete/{safe_k}?csrf_token={token_url}" class="action-btn text-muted" onclick="return confirm('Xóa vĩnh viễn Key này?')" title="Xóa"><i class="fas fa-trash"></i></a>
            </div>
        </td>
        </tr>'''

    blacklist_rows = "".join([f'<li class="list-group-item d-flex justify-content-between align-items-center"><span class="font-monospace text-danger">{escape(ip)}</span> <a href="/admin/unban_ip/{escape(ip)}?csrf_token={token_url}" class="action-btn action-btn-danger px-3">Gỡ</a></li>' for ip in banned_ips])

    return f'''
    <!DOCTYPE html><html lang="vi" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>LVT C-Panel</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
            body {{ background: #0b0f19; font-family: 'Inter', sans-serif; color: #e2e8f0; }}
            .topbar {{ background: #131722; border-bottom: 1px solid #1e293b; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }}
            .topbar-brand {{ font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: 1px; display: flex; align-items: center; gap: 10px; }}
            .card {{ background: #131722; border: 1px solid #1e293b; border-radius: 12px; margin-bottom: 24px; box-shadow: 0 4px 6px rgba(0,0,0,0.2); }}
            .card-header {{ background: rgba(255,255,255,0.02); border-bottom: 1px solid #1e293b; padding: 15px 20px; font-weight: 700; font-size: 14px; text-transform: uppercase; display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
            .card-body {{ padding: 20px; }}
            .form-control, .form-select {{ background: #0b0f19 !important; border: 1px solid #334155 !important; color: #f8fafc !important; border-radius: 8px; padding: 10px 15px; font-size: 14px; transition: 0.2s; }}
            .form-control:focus, .form-select:focus {{ border-color: #ffffff !important; box-shadow: 0 0 0 3px rgba(255,255,255,0.1) !important; outline: none; }}
            .btn-primary-custom {{ background: linear-gradient(135deg, #ffffff, #e2e8f0); border: none; color: #000; font-weight: 800; padding: 12px 20px; border-radius: 8px; transition: 0.3s; text-transform: uppercase; width: 100%; cursor:pointer; }}
            .btn-primary-custom:hover {{ transform: translateY(-2px); box-shadow: 0 0 15px rgba(255,255,255,0.3); }}
            .btn-success-custom {{ background: linear-gradient(135deg, #ffffff, #cbd5e1); color:#000; border: 1px solid #e2e8f0; }}
            .table {{ color: #cbd5e1; font-size: 14px; margin-bottom: 0; }}
            .table thead th {{ background: #0f172a; border-bottom: 1px solid #1e293b; color: #94a3b8; font-weight: 600; padding: 15px; text-transform: uppercase; font-size: 12px; }}
            .table tbody td {{ border-bottom: 1px solid #1e293b; padding: 15px; vertical-align: middle; }}
            .badge-custom {{ padding: 6px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; text-transform: uppercase; display: inline-flex; align-items: center; gap: 4px; }}
            .action-btn {{ background: rgba(255,255,255,0.05); color: #e2e8f0; border: 1px solid #334155; padding: 8px 12px; border-radius: 6px; font-size: 13px; font-weight: 600; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; transition: 0.2s; cursor: pointer; }}
            .action-btn:hover {{ background: rgba(255,255,255,0.2); color: #fff; }}
            .action-btn-danger {{ color: #f87171; border-color: rgba(248,113,113,0.3); background: rgba(248,113,113,0.05); }}
            .action-btn-danger:hover {{ background: #f87171; color: #fff; border-color: #f87171; }}
            .list-group-item {{ background: transparent; border-color: #1e293b; color: #cbd5e1; padding: 12px 15px; }}
            .modal-content {{ background: #131722; border: 1px solid #334155; border-radius: 12px; }}
            .nav-tabs-custom {{ display: flex; gap: 15px; margin-bottom: 25px; border-bottom: 1px solid #1e293b; padding-bottom: 15px; }}
            .nav-btn {{ padding: 12px 25px; border-radius: 8px; font-weight: 700; color: #94a3b8; text-decoration: none; border: 1px solid #1e293b; background: #0f172a; transition: 0.3s; display: inline-flex; align-items: center; gap: 8px; }}
            .nav-btn:hover {{ color: #fff; background: rgba(255,255,255,0.1); }}
            .nav-btn.active {{ background: #ffffff; color: #000; border-color: #ffffff; box-shadow: 0 0 15px rgba(255, 255, 255, 0.4); }}
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
            </div>

            <div class="row g-4 mb-4">
                <div class="col-xl-5 col-lg-12">
                    <div class="card h-100" style="border-top: 3px solid #ffffff;">
                        <div class="card-header text-white"><div><i class="fas fa-magic"></i> Tạo Mới Key Kích Hoạt</div></div>
                        <div class="card-body">
                            <form action="/admin/create" method="POST" class="row g-3">{csrf_input}
                                <div class="col-12 mb-1">
                                    <label class="text-muted small fw-bold mb-1">Chế Độ Tạo</label>
                                    <select name="gen_type" class="form-select border-light text-white fw-bold" onchange="document.getElementById('manual_box').style.display = this.value === 'manual' ? 'block' : 'none'; document.getElementById('qty_box').style.display = this.value === 'auto' ? 'block' : 'none';">
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
                                <div class="col-12 mt-3"><div class="form-check form-switch fs-6 p-3 rounded" style="background: rgba(255,255,255,0.05); border: 1px solid #334155;"><input class="form-check-input ms-0 mt-1" type="checkbox" name="is_vip"><label class="text-white fw-bold ms-3" style="line-height:24px;">VIP PRO</label></div></div>
                                <div class="col-12 mt-4"><button type="submit" class="btn-primary-custom btn-success-custom"><i class="fas fa-cogs"></i> Sản xuất Key</button></div>
                            </form>
                        </div>
                    </div>
                </div>

                <div class="col-xl-7 col-lg-12">
                    <div class="card h-100" style="border-top: 3px solid #64748b;">
                        <div class="card-header text-white"><div><i class="fas fa-shield-virus"></i> Firewall (Danh Sách Đen IP)</div></div>
                        <div class="card-body">
                            <form action="/admin/ban_ip" method="POST" class="d-flex gap-2 mb-3">{csrf_input}
                                <input type="text" name="ip" class="form-control" placeholder="Nhập IP cần khoá..." required>
                                <button type="submit" class="action-btn action-btn-danger" style="white-space:nowrap;"><i class="fas fa-ban"></i> Chặn Cửa</button>
                            </form>
                            <ul class="list-group" style="max-height:300px; overflow-y:auto;">
                                {blacklist_rows or '<li class="list-group-item text-center text-muted border-0 py-4"><i class="fas fa-check-circle fs-4 mb-2 d-block"></i> Không có IP nào bị khoá.</li>'}
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card mb-5" style="border-top: 3px solid #ffffff;">
                <div class="card-header text-white d-flex justify-content-between align-items-center">
                    <div><i class="fas fa-database"></i> Quản Lý Kho Key Cấp Phát</div>
                    <div class="input-group" style="width:300px;">
                        <span class="input-group-text bg-transparent border-end-0" style="border-color:#1e293b; color:#64748b;"><i class="fas fa-search"></i></span>
                        <input type="text" class="form-control border-start-0 ps-0" placeholder="Tìm kiếm nhanh..." onkeyup="let s=this.value.toLowerCase();document.querySelectorAll('.key-row').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(s)?'':'none');" style="box-shadow:none !important;">
                    </div>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive" style="max-height: 700px; overflow-y:auto;">
                        <table class="table table-hover text-center align-middle mb-0">
                            <thead style="position: sticky; top: 0; z-index: 1;">
                                <tr><th>Cụm Key Kích Hoạt</th><th>Thời Hạn</th><th>Định Danh OLM</th><th>Thiết bị</th><th>Thao Tác Quản Trị</th></tr>
                            </thead>
                            <tbody>
                                {keys_html or '<tr><td colspan="5" class="py-5 text-muted">Chưa có dữ liệu.</td></tr>'}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="modal fade" id="noteModal" tabindex="-1" data-bs-theme="dark">
            <div class="modal-dialog modal-dialog-centered"><div class="modal-content"><form action="/admin/edit_note" method="POST">{csrf_input}<div class="modal-header"><h5 class="modal-title fw-bold text-white"><i class="fas fa-sticky-note"></i> GHI CHÚ KEY</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body p-4 text-center"><input type="hidden" name="key" id="noteKeyInput"><h4 id="noteKeyDisplay" class="text-white font-monospace d-block mb-4 fw-bold"></h4><textarea name="note_text" id="noteInput" class="form-control form-control-lg text-center" rows="3" placeholder="Nhập văn bản thông báo..."></textarea></div><div class="modal-footer p-3"><button class="btn-primary-custom w-100">LƯU GHI CHÚ</button></div></form></div></div>
        </div>

        <div class="modal fade" id="bindModal" tabindex="-1" data-bs-theme="dark">
            <div class="modal-dialog modal-dialog-centered"><div class="modal-content"><form action="/admin/bind_olm" method="POST">{csrf_input}<div class="modal-header"><h5 class="modal-title fw-bold text-white"><i class="fas fa-user-tag"></i> GHIM TÀI KHOẢN OLM</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body p-4 text-center"><input type="hidden" name="key" id="bindKeyInput"><h4 id="bindKeyDisplay" class="text-white font-monospace d-block mb-4 fw-bold"></h4><input type="text" name="olm_name" id="bindOlmInput" class="form-control form-control-lg text-center" placeholder="Nhập tên tài khoản OLM cần ghim..." required></div><div class="modal-footer p-3"><button class="btn-primary-custom w-100">LƯU ĐỊNH DANH</button></div></form></div></div>
        </div>

        <div class="modal fade" id="addTimeModal" tabindex="-1" data-bs-theme="dark">
            <div class="modal-dialog modal-dialog-centered"><div class="modal-content"><form action="/admin/add_time" method="POST">{csrf_input}<div class="modal-header"><h5 class="modal-title fw-bold text-white"><i class="fas fa-clock"></i> CỘNG THÊM GIỜ</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body p-4 text-center"><input type="hidden" name="key" id="addTimeKeyInput"><h4 id="addTimeKeyDisplay" class="text-white font-monospace d-block mb-4 fw-bold"></h4><div class="row g-2"><div class="col-8"><input type="number" name="time_val" class="form-control form-control-lg text-center" placeholder="Số lượng" required></div><div class="col-4"><select name="time_unit" class="form-select form-select-lg"><option value="minutes">Phút</option><option value="hours">Giờ</option><option value="days" selected>Ngày</option><option value="months">Tháng</option></select></div></div></div><div class="modal-footer p-3"><button class="btn-primary-custom w-100">XÁC NHẬN CỘNG</button></div></form></div></div>
        </div>

        <div class="modal fade" id="maxDevModal" tabindex="-1" data-bs-theme="dark">
            <div class="modal-dialog modal-dialog-centered"><div class="modal-content"><form action="/admin/edit_max_dev" method="POST">{csrf_input}<div class="modal-header"><h5 class="modal-title fw-bold text-white"><i class="fas fa-mobile-alt"></i> TÙY CHỈNH GIỚI HẠN THIẾT BỊ</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body p-4 text-center"><input type="hidden" name="key" id="maxDevKeyInput"><h4 id="maxDevKeyDisplay" class="text-white font-monospace d-block mb-4 fw-bold"></h4><input type="number" name="max_dev" id="maxDevInput" class="form-control form-control-lg text-center" placeholder="Nhập số thiết bị..." required min="1"></div><div class="modal-footer p-3"><button class="btn-primary-custom w-100">CẬP NHẬT THIẾT BỊ</button></div></form></div></div>
        </div>

        <div class="modal fade" id="banModal" tabindex="-1" data-bs-theme="dark">
            <div class="modal-dialog modal-dialog-centered"><div class="modal-content"><form action="/admin/custom_ban" method="POST">{csrf_input}<div class="modal-header"><h5 class="modal-title fw-bold text-danger"><i class="fas fa-ban"></i> KHÓA KEY (KICK KHÁCH)</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body p-4 text-center"><input type="hidden" name="key" id="banKeyInput"><h4 id="banKeyDisplay" class="text-white font-monospace d-block mb-4 fw-bold"></h4><div class="row g-2"><div class="col-6"><input type="number" name="time_val" class="form-control form-control-lg text-center" placeholder="Thời gian"></div><div class="col-6"><select name="time_unit" class="form-select form-select-lg"><option value="minutes">Phút</option><option value="hours">Giờ</option><option value="days">Ngày</option><option value="months">Tháng</option><option value="permanent" selected>Vĩnh Viễn</option></select></div></div></div><div class="modal-footer p-3"><button type="submit" class="btn-primary-custom action-btn-danger w-100 border-0">XÁC NHẬN KHÓA</button></div></form></div></div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            function openNoteModal(key, note) {{ document.getElementById('noteKeyInput').value = key; document.getElementById('noteKeyDisplay').innerText = key; document.getElementById('noteInput').value = note; bootstrap.Modal.getOrCreateInstance(document.getElementById('noteModal')).show(); }}
            function openBindModal(key, old) {{ document.getElementById('bindKeyInput').value = key; document.getElementById('bindKeyDisplay').innerText = key; document.getElementById('bindOlmInput').value = old; bootstrap.Modal.getOrCreateInstance(document.getElementById('bindModal')).show(); }}
            function openAddTimeModal(key) {{ document.getElementById('addTimeKeyInput').value = key; document.getElementById('addTimeKeyDisplay').innerText = key; bootstrap.Modal.getOrCreateInstance(document.getElementById('addTimeModal')).show(); }}
            function openMaxDevModal(key, max) {{ document.getElementById('maxDevKeyInput').value = key; document.getElementById('maxDevKeyDisplay').innerText = key; document.getElementById('maxDevInput').value = max; bootstrap.Modal.getOrCreateInstance(document.getElementById('maxDevModal')).show(); }}
            function openBanModal(key) {{ document.getElementById('banKeyInput').value = key; document.getElementById('banKeyDisplay').innerText = key; bootstrap.Modal.getOrCreateInstance(document.getElementById('banModal')).show(); }}
            function copyToClipboard(text) {{ navigator.clipboard.writeText(text); Swal.fire({{toast: true, position: 'top-end', icon: 'success', title: 'Đã copy Key!', showConfirmButton: false, timer: 1500, background: '#1e293b', color: '#fff'}}); }}
        </script>
    </body>
    </html>
    '''

# [TRANG MỚI: TRANG QUẢN LÝ VƯỢT LINK GET KEY]
@app.route('/admin/getkey')
def admin_getkey_dashboard():
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    csrf_input = f'<input type="hidden" name="csrf_token" value="{session.get("csrf_token", "")}">'
    
    settings = db.get("settings", {})
    api_url = escape(settings.get("shortlink_api_url", "https://link1s.com/api"))
    api_token = escape(settings.get("shortlink_api_token", ""))
    games_list = escape(settings.get("games_list", "PUBG, LIENQUAN, FREEFIRE"))
    
    # Lọc danh sách các key do hệ thống vượt link tạo ra
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
            exp_text = f'<span class="{"text-danger fw-bold" if is_expired else "text-success"}">{time.strftime("%d/%m/%y %H:%M", time.localtime(data.get("exp", 0) / 1000))}</span>'
            
        safe_k = escape(str(k))
        keys_html += f'''<tr>
            <td><div class="fw-bold text-white font-monospace mb-1">{safe_k}</div></td>
            <td><span class="badge bg-light text-dark fw-bold">{escape(data.get("note", ""))}</span></td>
            <td>{exp_text}</td>
            <td><span class="badge bg-dark border p-2 text-white">{len(data.get('devices', []))}/1</span></td>
            <td><a href="/admin/action/delete/{safe_k}?csrf_token={session.get('csrf_token')}" class="btn btn-sm btn-outline-danger" onclick="return confirm('Xóa key này?')" title="Xóa"><i class="fas fa-trash"></i> Xóa</a></td>
        </tr>'''

    return f'''
    <!DOCTYPE html><html lang="vi" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>LVT C-Panel - Get Key</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
            body {{ background: #0b0f19; font-family: 'Inter', sans-serif; color: #e2e8f0; }}
            .topbar {{ background: #131722; border-bottom: 1px solid #1e293b; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }}
            .topbar-brand {{ font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: 1px; display: flex; align-items: center; gap: 10px; }}
            .card {{ background: #131722; border: 1px solid #1e293b; border-radius: 12px; margin-bottom: 24px; box-shadow: 0 4px 6px rgba(0,0,0,0.2); }}
            .card-header {{ background: rgba(255,255,255,0.02); border-bottom: 1px solid #1e293b; padding: 15px 20px; font-weight: 700; font-size: 14px; text-transform: uppercase; display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
            .card-body {{ padding: 20px; }}
            .form-control {{ background: #0b0f19 !important; border: 1px solid #334155 !important; color: #f8fafc !important; border-radius: 8px; padding: 10px 15px; font-size: 14px; transition: 0.2s; }}
            .form-control:focus {{ border-color: #ffffff !important; box-shadow: 0 0 0 3px rgba(255,255,255,0.1) !important; outline: none; }}
            .btn-primary-custom {{ background: linear-gradient(135deg, #ffffff, #e2e8f0); border: none; color: #000; font-weight: 800; padding: 12px 20px; border-radius: 8px; transition: 0.3s; text-transform: uppercase; width: 100%; cursor:pointer; }}
            .btn-primary-custom:hover {{ transform: translateY(-2px); box-shadow: 0 0 15px rgba(255,255,255,0.3); }}
            .nav-tabs-custom {{ display: flex; gap: 15px; margin-bottom: 25px; border-bottom: 1px solid #1e293b; padding-bottom: 15px; }}
            .nav-btn {{ padding: 12px 25px; border-radius: 8px; font-weight: 700; color: #94a3b8; text-decoration: none; border: 1px solid #1e293b; background: #0f172a; transition: 0.3s; display: inline-flex; align-items: center; gap: 8px; }}
            .nav-btn:hover {{ color: #fff; background: rgba(255,255,255,0.1); }}
            .nav-btn.active {{ background: #ffffff; color: #000; border-color: #ffffff; box-shadow: 0 0 15px rgba(255, 255, 255, 0.4); }}
            .table {{ color: #cbd5e1; font-size: 14px; margin-bottom: 0; }}
            .table thead th {{ background: #0f172a; border-bottom: 1px solid #1e293b; color: #94a3b8; font-weight: 600; padding: 15px; text-transform: uppercase; font-size: 12px; }}
            .table tbody td {{ border-bottom: 1px solid #1e293b; padding: 15px; vertical-align: middle; }}
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
            </div>

            <div class="row g-4">
                <div class="col-xl-4 col-lg-12">
                    <div class="card h-100" style="border-top: 3px solid #ffffff;">
                        <div class="card-header text-white"><div><i class="fas fa-cogs"></i> Cài Đặt API Vượt Link</div></div>
                        <div class="card-body">
                            <form action="/admin/update_getkey_settings" method="POST">{csrf_input}
                                <div class="mb-3">
                                    <label class="text-muted small fw-bold mb-1">Tên Tựa Game (Ngăn cách bằng dấu phẩy)</label>
                                    <textarea name="games_list" class="form-control" rows="2">{games_list}</textarea>
                                </div>
                                <div class="mb-3">
                                    <label class="text-muted small fw-bold mb-1">URL API Rút Gọn Link</label>
                                    <input type="text" name="shortlink_api_url" class="form-control" value="{api_url}" placeholder="Ví dụ: https://link1s.com/api">
                                    <small class="text-info">* Hỗ trợ chuẩn API link1s, droplink, megaurl...</small>
                                </div>
                                <div class="mb-4">
                                    <label class="text-muted small fw-bold mb-1">API Token Bí Mật</label>
                                    <input type="text" name="shortlink_api_token" class="form-control" value="{api_token}" placeholder="Dán token API rút gọn link vào đây">
                                </div>
                                <button type="submit" class="btn-primary-custom"><i class="fas fa-save"></i> LƯU CẤU HÌNH</button>
                            </form>
                        </div>
                    </div>
                </div>

                <div class="col-xl-8 col-lg-12">
                    <div class="card h-100" style="border-top: 3px solid #22c55e;">
                        <div class="card-header text-success"><div><i class="fas fa-list-alt"></i> Danh Sách Key Vượt Link Đã Tạo</div></div>
                        <div class="card-body p-0">
                            <div class="table-responsive" style="max-height: 500px; overflow-y:auto;">
                                <table class="table table-hover text-center align-middle mb-0">
                                    <thead style="position: sticky; top: 0; z-index: 1;">
                                        <tr><th>Cụm Key</th><th>Loại Vượt Link</th><th>Thời Hạn</th><th>Thiết Bị</th><th>Thao Tác</th></tr>
                                    </thead>
                                    <tbody>
                                        {keys_html or '<tr><td colspan="5" class="py-5 text-muted">Chưa có khách nào vượt link lấy key.</td></tr>'}
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

# [TRANG 2: TRANG AUTO NẠP FILE MÂY]
@app.route('/admin/files')
def admin_files_dashboard():
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    csrf_input = f'<input type="hidden" name="csrf_token" value="{session.get("csrf_token", "")}">'
    
    with db_lock:
        current_tiem_len = len(db.get("settings", {}).get("script_tiem", ""))
        if current_tiem_len > 10: tiem_status = f'<span class="text-success fw-bold"><i class="fas fa-check-circle"></i> Đã nạp File Tiêm (Dung lượng: {current_tiem_len} bytes)</span>'
        else: tiem_status = '<span class="text-danger fw-bold"><i class="fas fa-times-circle"></i> Chưa có Script Tiêm!</span>'

        current_loader_len = len(db.get("settings", {}).get("vm_loader", ""))
        if current_loader_len > 10: loader_status = f'<span class="text-success fw-bold"><i class="fas fa-check-circle"></i> Đã nạp Script (Dung lượng: {current_loader_len} bytes)</span>'
        else: loader_status = '<span class="text-danger fw-bold"><i class="fas fa-times-circle"></i> Chưa có Script Violentmonkey!</span>'

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
        maint_btn_class = "btn-danger" if is_maintenance else "btn-light text-dark"
        maint_status_badge = '<span class="badge bg-danger ms-2">Đang Bảo Trì</span>' if is_maintenance else '<span class="badge bg-success ms-2">Online</span>'

    return f'''
    <!DOCTYPE html><html lang="vi" data-bs-theme="dark">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>LVT C-Panel - Auto Nạp File</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
            body {{ background: #0b0f19; font-family: 'Inter', sans-serif; color: #e2e8f0; }}
            .topbar {{ background: #131722; border-bottom: 1px solid #1e293b; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }}
            .topbar-brand {{ font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: 1px; display: flex; align-items: center; gap: 10px; }}
            .card {{ background: #131722; border: 1px solid #1e293b; border-radius: 12px; margin-bottom: 24px; box-shadow: 0 4px 6px rgba(0,0,0,0.2); }}
            .card-header {{ background: rgba(255,255,255,0.02); border-bottom: 1px solid #1e293b; padding: 15px 20px; font-weight: 700; font-size: 14px; text-transform: uppercase; display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
            .card-body {{ padding: 20px; }}
            .form-control {{ background: #0b0f19 !important; border: 1px solid #334155 !important; color: #f8fafc !important; border-radius: 8px; padding: 10px 15px; font-size: 14px; transition: 0.2s; }}
            .form-control:focus {{ border-color: #ffffff !important; box-shadow: 0 0 0 3px rgba(255,255,255,0.1) !important; outline: none; }}
            .btn-primary-custom {{ background: linear-gradient(135deg, #ffffff, #e2e8f0); border: none; color: #000; font-weight: 800; padding: 12px 20px; border-radius: 8px; transition: 0.3s; text-transform: uppercase; width: 100%; cursor:pointer; }}
            .btn-primary-custom:hover {{ transform: translateY(-2px); box-shadow: 0 0 15px rgba(255,255,255,0.3); }}
            .nav-tabs-custom {{ display: flex; gap: 15px; margin-bottom: 25px; border-bottom: 1px solid #1e293b; padding-bottom: 15px; }}
            .nav-btn {{ padding: 12px 25px; border-radius: 8px; font-weight: 700; color: #94a3b8; text-decoration: none; border: 1px solid #1e293b; background: #0f172a; transition: 0.3s; display: inline-flex; align-items: center; gap: 8px; }}
            .nav-btn:hover {{ color: #fff; background: rgba(255,255,255,0.1); }}
            .nav-btn.active {{ background: #ffffff; color: #000; border-color: #ffffff; box-shadow: 0 0 15px rgba(255, 255, 255, 0.4); }}
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
            </div>
            
            <div class="card mb-4" style="border-top: 3px solid #10b981;">
                <div class="card-header text-success"><div><i class="fas fa-history"></i> KHÔI PHỤC DỮ LIỆU TỪ BACKUP TELEGRAM</div></div>
                <div class="card-body">
                    <form action="/admin/restore_db" method="POST" enctype="multipart/form-data" class="d-flex align-items-center gap-3">{csrf_input}
                        <input type="file" name="db_file" class="form-control w-50" accept=".json" required>
                        <button type="submit" class="btn-primary-custom" style="width:auto; border: 1px solid #10b981;"><i class="fas fa-upload"></i> KHÔI PHỤC NGAY</button>
                    </form>
                </div>
            </div>

            <div class="row g-4">
                <div class="col-xl-6 col-lg-6">
                    <div class="card h-100" style="border-top: 3px solid #ffffff;">
                        <div class="card-header text-white"><div><i class="fas fa-code"></i> NẠP SCRIPT TIÊM GỐC</div></div>
                        <div class="card-body d-flex flex-column">
                            <form action="/admin/update_script_tiem" method="POST" enctype="multipart/form-data" class="h-100 d-flex flex-column">{csrf_input}
                                <div class="mb-3 p-3 text-center" style="background: rgba(255,255,255,0.02); border: 1px dashed #475569; border-radius: 8px;">{tiem_status}</div>
                                <input type="file" name="script_file" class="form-control mb-2" accept=".js,.txt">
                                <textarea name="script_text" class="form-control mb-3 flex-grow-1" rows="4" placeholder="Hoặc dán trực tiếp mã nguồn vào đây..."></textarea>
                                <button type="submit" class="btn-primary-custom mt-auto"><i class="fas fa-cloud-upload-alt"></i> NẠP FILE SCRIPT TIÊM</button>
                            </form>
                        </div>
                    </div>
                </div>

                <div class="col-xl-6 col-lg-6">
                    <div class="card h-100" style="border-top: 3px solid #ffffff;">
                        <div class="card-header text-white"><div><i class="fas fa-certificate"></i> NẠP SCRIPT VIOLENTMONKEY LOADER</div></div>
                        <div class="card-body d-flex flex-column">
                            <form action="/admin/update_vm_loader" method="POST" enctype="multipart/form-data" class="h-100 d-flex flex-column">{csrf_input}
                                <div class="mb-3 p-3 text-center" style="background: rgba(255,255,255,0.02); border: 1px dashed #475569; border-radius: 8px;">{loader_status}</div>
                                <input type="file" name="loader_file" class="form-control mb-2" accept=".js,.txt">
                                <textarea name="loader_text" class="form-control mb-3 flex-grow-1" rows="4" placeholder="Hoặc dán trực tiếp mã nguồn vào đây..."></textarea>
                                <button type="submit" class="btn-primary-custom mt-auto"><i class="fas fa-cloud-upload-alt"></i> NẠP SCRIPT LOADER</button>
                            </form>
                        </div>
                    </div>
                </div>
                
                <div class="col-xl-6 col-lg-6">
                    <div class="card h-100" style="border-top: 3px solid #ffffff;">
                        <div class="card-header text-white">
                            <div><i class="fas fa-mobile-alt"></i> NẠP GIAO DIỆN WEBVIEW APP (.HTML)</div>
                            <div>{maint_status_badge}</div>
                        </div>
                        <div class="card-body d-flex flex-column">
                            <form action="/admin/toggle_maintenance" method="POST" class="mb-3">{csrf_input}
                                <button type="submit" class="btn {maint_btn_class} w-100 fw-bold btn-sm py-2 border"><i class="fas fa-tools"></i> {maint_btn_text}</button>
                            </form>
                            <form action="/admin/update_webview" method="POST" enctype="multipart/form-data" class="h-100 d-flex flex-column">{csrf_input}
                                <div class="mb-3 p-3 text-center" style="background: rgba(255,255,255,0.02); border: 1px dashed #475569; border-radius: 8px;">{webview_status}</div>
                                <input type="file" name="webview_file" class="form-control mb-2" accept=".html,.js,.txt">
                                <textarea name="webview_text" class="form-control mb-3 flex-grow-1" rows="4" placeholder="Hoặc dán trực tiếp mã nguồn Webview vào đây..."></textarea>
                                <button type="submit" class="btn-primary-custom mt-auto"><i class="fas fa-cloud-upload-alt"></i> NẠP GIAO DIỆN APP</button>
                            </form>
                        </div>
                    </div>
                </div>

                <div class="col-xl-6 col-lg-6">
                    <div class="card h-100" style="border-top: 3px solid #ffffff;">
                        <div class="card-header text-white"><div><i class="fas fa-file-archive"></i> NẠP FILE .PAK (DATA)</div></div>
                        <div class="card-body d-flex flex-column">
                            <form action="/admin/update_pak" method="POST" enctype="multipart/form-data" class="h-100 d-flex flex-column">{csrf_input}
                                <div class="mb-3 p-3 text-center" style="background: rgba(255,255,255,0.02); border: 1px dashed #475569; border-radius: 8px;">{pak_status}</div>
                                <input type="file" name="pak_file" class="form-control mb-2" accept=".pak">
                                <input type="url" name="pak_url" class="form-control mb-3" placeholder="Hoặc dán Link trực tiếp tải file .pak (Direct URL)...">
                                <button type="submit" class="btn-primary-custom mt-auto"><i class="fas fa-cloud-upload-alt"></i> NẠP FILE .PAK</button>
                            </form>
                        </div>
                    </div>
                </div>

            </div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    '''

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

@app.route('/admin/update_script_tiem', methods=['POST'])
def admin_update_script_tiem():
    if session.get('role') != 'admin': return redirect('/admin_login')
    script_content = request.form.get('script_text', '').strip()
    if not script_content and 'script_file' in request.files and request.files['script_file'].filename != '':
        try: script_content = request.files['script_file'].read().decode('utf-8')
        except: return swal_back("Lỗi", "File không hợp lệ (.js/.txt)", "error")
    if not script_content: return swal_back("Lỗi", "Vui lòng chọn File hoặc dán Mã Nguồn!", "error")
    db = load_db()
    with db_lock:
        db.setdefault("settings", {})["script_tiem"] = script_content
        save_db(db)
    return swal_redirect("Thành Công", "Đã nạp Script Tiêm thành công!", "success", "/admin/files")

@app.route('/admin/update_vm_loader', methods=['POST'])
def admin_update_vm_loader():
    if session.get('role') != 'admin': return redirect('/admin_login')
    script_content = request.form.get('loader_text', '').strip()
    if not script_content and 'loader_file' in request.files and request.files['loader_file'].filename != '':
        try: script_content = request.files['loader_file'].read().decode('utf-8')
        except: return swal_back("Lỗi", "File không hợp lệ (.js/.txt)", "error")
    if not script_content: return swal_back("Lỗi", "Vui lòng chọn File hoặc dán Mã Nguồn!", "error")
    db = load_db()
    with db_lock:
        db.setdefault("settings", {})["vm_loader"] = script_content
        save_db(db)
    return swal_redirect("Thành Công", "Đã nạp Script Loader thành công!", "success", "/admin/files")

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
    if session.get('role') != 'admin': return redirect('/admin_login')
    pak_url = request.form.get('pak_url', '').strip()
    pak_path = './uploaded.pak'
    temp_pak_path = './uploaded.pak.tmp'
    try:
        if pak_url:
            r = requests.get(pak_url, stream=True, timeout=30)
            r.raise_for_status()
            with open(temp_pak_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            os.replace(temp_pak_path, pak_path)
        else:
            if 'pak_file' not in request.files or request.files['pak_file'].filename == '': return swal_back("Lỗi", "Chưa chọn file hoặc dán Link URL!", "error")
            file = request.files['pak_file']
            with open(temp_pak_path, 'wb') as f:
                while True:
                    chunk = file.stream.read(64 * 1024) 
                    if not chunk: break
                    f.write(chunk)
            os.replace(temp_pak_path, pak_path)
        db = load_db()
        save_db(db)
    except Exception as e:
        if os.path.exists(temp_pak_path):
            try: os.remove(temp_pak_path)
            except: pass
        return swal_back("Lỗi", f"Không thể lưu file .pak: {escape_swal(str(e))}", "error")
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
