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
.glass-panel { background: rgba(17, 17, 26, 0.7); backdrop-filter: blur(15px); border: 1px solid rgba(0, 255, 204, 0.3); border-radius: 15px; padding: 30px; box-shadow: 0 0 20px rgba(0, 255, 204, 0.2); text-align: center; }
.text-neon { color: #00ffcc; text-shadow: 0 0 10px rgba(0, 255, 204, 0.5); }
.btn-neon { background: linear-gradient(90deg, #00ffcc, #0099ff); border: none; color: #000; font-weight: bold; padding: 10px 20px; border-radius: 8px; width: 100%; transition: 0.3s; text-transform: uppercase; cursor: pointer; }
.btn-neon:hover { transform: scale(1.05); box-shadow: 0 0 15px rgba(0, 255, 204, 0.5); }
"""

# ========================================================
# HỆ THỐNG BOT TELEGRAM & GIỮ NGUYÊN LÕI CŨ
# ========================================================
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
                            welcome = f"🌟 <b>HỆ THỐNG CẤP PROXY OLM TỰ ĐỘNG</b> 🌟\n\nXin chào <b>{user_first_name}</b>!\nTruy cập Link Web để tự động cấu hình Proxy & Script:"
                            keyboard = {"inline_keyboard": [[{"text": "🌐 MỞ TRANG KÍCH HOẠT PROXY", "web_app": {"url": f"{WEB_URL}/"}}]]}
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

@app.route('/telegram_mini_app')
def old_mini_app_redirect(): return redirect('/')

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException): return e
    return "Hệ thống đang bảo trì.", 500

app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 # Nâng giới hạn file lên 10MB
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

def hash_pwd(pwd): return hashlib.sha256(pwd.encode()).hexdigest()

def swal_redirect(title, text, icon, url):
    return f"""<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #05050A; }}</style></head><body><script>Swal.fire({{ title: `{title}`, html: `{text}`, icon: '{icon}', background: '#11111A', color: '#fff', confirmButtonColor: '#00ffcc', allowOutsideClick: false }}).then(() => {{ window.location.href = '{url}'; }});</script></body></html>"""

def swal_back(title, text, icon):
    return f"""<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #05050A; }}</style></head><body><script>Swal.fire({{ title: `{title}`, html: `{text}`, icon: '{icon}', background: '#11111A', color: '#fff', confirmButtonColor: '#bd00ff', allowOutsideClick: false }}).then(() => {{ window.history.back(); }});</script></body></html>"""

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
            if not data: data = {"users": {}, "keys": {}, "banned_ips": [], "settings": {}}
            try:
                data.setdefault("users", {})
                data.setdefault("keys", {})
                data.setdefault("banned_ips", [])
                data.setdefault("settings", {})
                
                if "secret_key" not in data["settings"]: data["settings"]["secret_key"] = secrets.token_hex(32)
                if "maintenance_until" not in data["settings"]: data["settings"]["maintenance_until"] = 0
                if "custom_script" not in data["settings"]: data["settings"]["custom_script"] = ""
                if "ca_cert" not in data["settings"]: data["settings"]["ca_cert"] = ""
                if "tg_admins" not in data["settings"]: data["settings"]["tg_admins"] = [TELEGRAM_CHAT_ID]
                
                if "admin" not in data["users"]:
                    data["users"]["admin"] = {"password_hash": hash_pwd("120510@"), "role": "admin"}

                for k in data["keys"]:
                    data["keys"][k].setdefault("owner", "admin")
                    data["keys"][k].setdefault("devices", [])
                    data["keys"][k].setdefault("maxDevices", 1)
                    data["keys"][k].setdefault("bound_olm", "") 
                    data["keys"][k].setdefault("vip", False)
                    data["keys"][k].setdefault("proxy_host", "")
                    data["keys"][k].setdefault("proxy_port", 0)
                    data["keys"][k].setdefault("ban_until", 0)
                    data["keys"][k].setdefault("status", "active")

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
        except Exception: pass

def generate_proxy_key():
    return ''.join(secrets.choice(string.ascii_lowercase) for _ in range(15))

def log_admin_action(db, action_text):
    db.setdefault("admin_logs", []).insert(0, {"time": int(time.time() * 1000), "action": action_text})
    db["admin_logs"] = db["admin_logs"][:100]

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
            if changed: save_db(db)
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
        if any(bot in ua for bot in blocked_bots): return "Firewall Blocked.", 403
            
        if request.path.startswith("/admin") and request.path not in ["/admin_login"]:
            if session.get('role') != 'admin': return redirect('/admin_login')
            if request.method == 'POST':
                if request.form.get("csrf_token") != session.get('csrf_token'): return "Lỗi CSRF Token", 403
    except: pass

@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN' 
    return response

# ========================================================
# HỆ THỐNG ĐĂNG KÝ / ĐĂNG NHẬP NGƯỜI DÙNG
# ========================================================
@app.route('/register', methods=['POST'])
def user_register():
    username = request.form.get('username', '').strip().lower()
    pwd = request.form.get('password', '').strip()
    if not username or not pwd: return swal_back("Lỗi", "Vui lòng nhập đủ thông tin!", "warning")
    db = load_db()
    with db_lock:
        if username in db["users"]: return swal_back("Lỗi", "Tài khoản này đã tồn tại!", "error")
        db["users"][username] = {"password_hash": hash_pwd(pwd), "role": "user", "created_at": int(time.time() * 1000)}
        save_db(db)
    return swal_redirect("Thành công", "Đăng ký thành công! Vui lòng tiến hành Đăng Nhập.", "success", "/")

@app.route('/login', methods=['POST'])
def user_login():
    username = request.form.get('username', '').strip().lower()
    pwd = request.form.get('password', '').strip()
    db = load_db()
    u_data = db.get("users", {}).get(username)
    if u_data and u_data.get("password_hash") == hash_pwd(pwd):
        session['username'] = username
        session['role'] = u_data.get('role', 'user')
        session['csrf_token'] = secrets.token_hex(16)
        if session['role'] == 'admin': return redirect('/admin') 
        return redirect('/')
    return swal_back("Từ chối", "Sai tài khoản hoặc mật khẩu!", "error")

@app.route('/user_logout')
def user_logout():
    session.clear()
    return redirect('/')

# ========================================================
# KICK USER & GIAO DỊCH SCRIPT (THÊM AUTO THÔNG BÁO UI)
# ========================================================
@app.route('/api/check_ban_status')
def check_ban_status():
    ip = get_real_ip()
    db = load_db()
    now = int(time.time() * 1000)
    if ip in db.get("banned_ips", []): return jsonify({"banned": True, "reason": "IP của bạn đã bị Firewall chặn đứt."})
    for k, v in db.get("keys", {}).items():
        if ip in v.get("devices", []):
            if v.get("status") == "banned":
                ban_until = v.get("ban_until", "permanent")
                if ban_until == "permanent" or (isinstance(ban_until, int) and ban_until > now):
                    return jsonify({"banned": True, "reason": "Key của bạn đã bị Admin khóa. Bạn đã bị kick khỏi hệ thống!"})
                else:
                    v["status"] = "active"
                    save_db(db)
                    return jsonify({"banned": False})
    return jsonify({"banned": False})

@app.route('/api/get_script')
def serve_custom_script():
    db = load_db()
    user_script = db.get("settings", {}).get("custom_script", "")
    
    # Payload gộp 2 chức năng:
    # 1. Kick User nếu bị Khóa Key.
    # 2. Bật Thông báo Mạng riêng tư (Chỉ hiện 1 lần)
    logic_payload = f"""
    (function() {{
        // Auto Notification
        if (!sessionStorage.getItem('lvt_proxy_connected')) {{
            var toast = document.createElement('div');
            toast.innerHTML = '✅ LVT PROXY: Kết nối thành công mạng riêng tư! Chúc bạn sử dụng OLM vui vẻ.';
            toast.style.cssText = 'position:fixed; bottom:20px; right:20px; background:#00ffcc; color:#000; padding:15px 20px; border-radius:10px; z-index:9999999; font-weight:bold; box-shadow:0 0 20px rgba(0,255,204,0.6); font-family:sans-serif; transition: 0.5s; opacity: 1;';
            document.body.appendChild(toast);
            setTimeout(function(){{ toast.style.opacity = '0'; setTimeout(()=>toast.remove(), 500); }}, 5000);
            sessionStorage.setItem('lvt_proxy_connected', 'true');
        }}

        // Check Ban (Kick)
        setInterval(function() {{
            fetch('{WEB_URL}/api/check_ban_status')
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
    
    resp = make_response(logic_payload + "\n" + user_script)
    resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp

@app.route('/download-ca')
def download_ca():
    db = load_db()
    ca_data = db.get("settings", {}).get("ca_cert", "")
    if not ca_data.strip(): return "⚠️ Admin chưa nạp Chứng chỉ CA của Termux lên hệ thống! Vui lòng báo Admin nạp vào C-Panel.", 404
        
    resp = make_response(ca_data)
    resp.headers['Content-Type'] = 'application/x-x509-ca-cert'
    resp.headers['Content-Disposition'] = 'attachment; filename="LVT_PROXY_CA.crt"'
    return resp

@app.route('/proxy_config/<key>.pac')
def generate_pac_file(key):
    db = load_db()
    with db_lock:
        kd = db.get("keys", {}).get(key)
        now = int(time.time() * 1000)
        
        if not kd or not kd.get("proxy_host"): return "Trạng thái Key không hợp lệ.", 403
        if kd.get("status") == "banned":
            ban_until = kd.get("ban_until", "permanent")
            if ban_until == "permanent" or (isinstance(ban_until, int) and ban_until > now): return "Key đã bị khóa.", 403
            
        host = kd.get("proxy_host")
        port = kd.get("proxy_port")
        
        pac_script = f"""
        function FindProxyForURL(url, host) {{
            if (shExpMatch(host, "*.olm.vn") || host === "olm.vn" || host === "mitm.it") {{
                return "PROXY 127.0.0.1:8080; PROXY {host}:{port}; DIRECT";
            }}
            return "DIRECT";
        }}
        """
        resp = make_response(pac_script)
        resp.headers['Content-Type'] = 'application/x-ns-proxy-autoconfig'
        return resp

# ========================================================
# GIAO DIỆN WEB NGƯỜI DÙNG
# ========================================================
@app.route('/')
def user_proxy_portal():
    if not session.get('username'):
        html = f"""
        <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>LVT - Chào mừng đến Proxy LVT</title><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');body {{ background: #05050a; color: #fff; font-family: 'Inter', sans-serif; margin: 0; padding: 20px; display: flex; justify-content: center; align-items: center; min-height: 100vh; flex-direction:column; }}{CSS_GLASS}.inp-neon {{ background: rgba(0,0,0,0.5); border: 1px solid rgba(0,255,204,0.3); color: #00ffcc; padding: 15px; border-radius: 8px; width: 100%; margin-bottom: 15px; outline: none; transition: 0.3s; font-family: monospace; font-size: 15px; text-align: center; font-weight:bold; box-sizing:border-box; }}.inp-neon:focus {{ border-color: #00ffcc; box-shadow: 0 0 10px rgba(0,255,204,0.2); }}.nav {{ display: flex; gap: 8px; margin-bottom: 20px; background: rgba(0,0,0,0.3); padding: 5px; border-radius: 12px; }}.nav-btn {{ flex: 1; padding: 12px; text-align: center; border-radius: 10px; color: #8892b0; font-size: 13px; font-weight: 800; cursor: pointer; transition:0.3s; }}.nav-btn.act {{ background: #00ffcc; color: #000; box-shadow: 0 0 15px rgba(0,255,204,0.3); }}</style></head><body><div class="glass-panel" style="max-width: 450px; width: 100%;"><h2 class="text-neon mb-2" style="margin-top:0;"><i class="fas fa-globe"></i> CHÀO MỪNG BẠN ĐẾN PROXY CỦA CHÚNG TÔI</h2><p style="color:#889; font-size:13px; margin-bottom:25px; line-height:1.5;">Hệ thống định tuyến thông minh. Vui lòng đăng nhập hoặc tạo tài khoản để sử dụng dịch vụ.</p><div class="nav"><div class="nav-btn act" onclick="switchT('login')">ĐĂNG NHẬP</div><div class="nav-btn" onclick="switchT('register')">ĐĂNG KÝ</div></div><div id="tab-login" style="display:block;"><form action="/login" method="POST"><input type="text" name="username" class="inp-neon" placeholder="Tên tài khoản" required><input type="password" name="password" class="inp-neon" placeholder="Mật khẩu" required><button type="submit" class="btn-neon"><i class="fas fa-sign-in-alt"></i> VÀO HỆ THỐNG</button></form></div><div id="tab-register" style="display:none;"><form action="/register" method="POST"><input type="text" name="username" class="inp-neon" placeholder="Tạo tên tài khoản mới" required><input type="password" name="password" class="inp-neon" placeholder="Tạo mật khẩu" required><button type="submit" class="btn-neon" style="background:linear-gradient(90deg, #a855f7, #6366f1);"><i class="fas fa-user-plus"></i> ĐĂNG KÝ NGAY</button></form></div></div><script>function switchT(t) {{ document.getElementById('tab-login').style.display = 'none'; document.getElementById('tab-register').style.display = 'none'; document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('act')); document.getElementById('tab-'+t).style.display = 'block'; if(t === 'login') document.querySelector('.nav-btn:nth-child(1)').classList.add('act'); else document.querySelector('.nav-btn:nth-child(2)').classList.add('act'); }}</script></body></html>
        """
        return render_template_string_safe(html)

    username = session.get('username')
    html = f"""
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>LVT - Kích Hoạt Định Tuyến</title><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');body {{ background: #05050a; color: #fff; font-family: 'Inter', sans-serif; margin: 0; padding: 20px; display: flex; justify-content: center; align-items: center; min-height: 100vh; flex-direction:column; }}{CSS_GLASS}.info-box {{ background: rgba(0,0,0,0.6); border: 1px dashed #00ffcc; padding: 20px; border-radius: 10px; margin-top: 20px; display: none; text-align: left; position: relative; }}.step-title {{ color: #00ffcc; font-weight: 900; margin-top: 15px; margin-bottom: 5px; font-size: 15px; border-bottom: 1px solid rgba(0,255,204,0.3); padding-bottom: 5px; text-transform:uppercase; }}.step-text {{ font-size: 13px; color: #ccc; line-height: 1.6; margin: 8px 0; }}.highlight {{ color: #00ffcc; font-weight: bold; font-family: monospace; font-size: 14px; user-select: all; padding: 6px 10px; background: rgba(0,255,204,0.1); border-radius: 5px; word-break: break-all; display: flex; align-items: center; justify-content: space-between; width: 100%; box-sizing: border-box; }}.cert-btn {{ background: linear-gradient(90deg, #a855f7, #6366f1); color: #fff; text-decoration: none; padding: 12px; border-radius: 8px; display: block; text-align: center; font-weight: 900; margin-top: 20px; transition: 0.3s; text-transform:uppercase; border:none; width:100%; cursor:pointer; }}.cert-btn:hover {{ transform: scale(1.02); box-shadow: 0 0 15px rgba(168,85,247,0.5); }}.inp-neon {{ background: rgba(0,0,0,0.5); border: 1px solid rgba(0,255,204,0.3); color: #00ffcc; padding: 15px; border-radius: 8px; width: 100%; margin-bottom: 15px; outline: none; transition: 0.3s; font-family: monospace; font-size: 16px; text-align: center; font-weight:bold; box-sizing:border-box; text-transform:lowercase; }}.inp-neon:focus {{ border-color: #00ffcc; box-shadow: 0 0 10px rgba(0,255,204,0.2); }}.user-badge {{ position:absolute; top:20px; right:20px; background:rgba(0,255,204,0.1); color:#00ffcc; padding:8px 15px; border-radius:20px; font-weight:bold; font-size:12px; display:flex; align-items:center; gap:10px; border:1px solid rgba(0,255,204,0.3); z-index: 10; }}.logout-btn {{ color:#ff3366; text-decoration:none; background:rgba(255,51,102,0.1); padding:4px 10px; border-radius:15px; border:1px solid rgba(255,51,102,0.3); transition:0.3s; cursor:pointer; }}.logout-btn:hover {{ background:#ff3366; color:#fff; }}.btn-copy-pac {{ background: none; border: none; color: #fff; cursor: pointer; padding: 0 5px; }}</style></head><body><div class="user-badge"><i class="fas fa-user-circle"></i> {escape(username)} <a href="/user_logout" class="logout-btn"><i class="fas fa-sign-out-alt"></i> Thoát Web</a></div><div class="glass-panel" style="max-width: 550px; width: 100%; margin-top: 50px;"><h2 class="text-neon mb-2" style="margin-top:0;"><i class="fas fa-route"></i> ĐỊNH TUYẾN PROXY LVT</h2><p style="color:#889; font-size:13px; margin-bottom:25px;">Chỉ can thiệp vào OLM. Các trang web khác hoạt động tốc độ cao bình thường.</p><input type="text" id="k_inp" class="inp-neon" placeholder="dán mã key 15 ký tự vào đây..."><button id="btn_activate" class="btn-neon" onclick="actKey()"><i class="fas fa-bolt"></i> LẤY CẤU HÌNH LIÊN KẾT</button><div id="proxy-result" class="info-box"><div style="display:flex; justify-content:space-between; align-items:center; border-bottom: 1px dashed #333; padding-bottom: 10px; margin-bottom: 15px;"><h4 style="color:#00ffcc; margin:0; font-size:16px;">THÔNG TIN KẾT NỐI</h4><button class="logout-btn" style="border-radius: 8px; font-size: 11px;" onclick="logoutKey()"><i class="fas fa-eject"></i> Đăng xuất Key</button></div><div style="margin-bottom:12px;"><div style="color:#889; font-size:12px; margin-bottom:4px;">👤 Định danh OLM hợp lệ:</div><div class="highlight" style="color:#ffcc00; background:rgba(255,204,0,0.1); justify-content:center;" id="res-olm"></div></div><div style="margin-bottom:12px;"><div style="color:#889; font-size:12px; margin-bottom:4px;"><i class="fas fa-link"></i> Link Cấu Hình Tự Động (PAC URL):</div><div class="highlight" id="res-pac-container"></div><p style="font-size:11px; color:#ff3366; margin-top:5px; margin-bottom:0;"><i>* Copy link này dán vào "URL PAC" trong cài đặt Wifi.</i></p></div><div style="display:flex; gap:10px; margin-bottom:12px; margin-top:15px;"><div style="flex:1; background:rgba(255,255,255,0.05); padding:10px; border-radius:8px; text-align:center;"><div style="color:#889; font-size:12px; margin-bottom:4px;"><i class="fas fa-mobile-alt"></i> Thiết bị:</div><div id="res-dev" style="font-size:14px; font-weight:bold; color:#fff;"></div></div><div style="flex:1; background:rgba(255,255,255,0.05); padding:10px; border-radius:8px; text-align:center;"><div style="color:#889; font-size:12px; margin-bottom:4px;"><i class="fas fa-clock"></i> Hạn dùng (EXP):</div><div id="res-exp" style="font-size:14px; font-weight:bold; color:#ff3366;"></div></div></div><a href="/download-ca" class="cert-btn" download><i class="fas fa-shield-alt"></i> TẢI CHỨNG CHỈ BẢO MẬT (CA)</a><div style="margin-top:25px; border-top: 1px dashed #555; padding-top: 15px;"><h4 style="color:#00ffcc; text-align:center; margin-top:0;">HƯỚNG DẪN CÀI ĐẶT</h4><div class="step-title"><i class="fab fa-android"></i> DÀNH CHO ANDROID</div><p class="step-text"><b>Bước 1:</b> Mở Cài đặt Wifi, ấn vào chữ <b>(i)</b> cạnh Wifi đang dùng.</p><p class="step-text"><b>Bước 2:</b> Tìm phần <b>Proxy</b>, đổi thành <b>Tự động cấu hình (Auto-Config)</b>.</p><p class="step-text"><b>Bước 3:</b> Dán đường link PAC màu xanh ở trên vào ô <b>Địa chỉ web PAC / URL</b> và Lưu lại.</p><p class="step-text"><b>Bước 4:</b> Bấm tải Chứng Chỉ màu tím ở trên. Cài đặt vào máy (Cài đặt -> Chứng chỉ -> Chọn VPN và Ứng dụng).</p><div class="step-title"><i class="fab fa-apple"></i> DÀNH CHO iOS (IPHONE/IPAD)</div><p class="step-text"><b>Bước 1:</b> Cài đặt Wifi -> Bấm chữ <b>(i)</b> -> Định cấu hình Proxy -> Đổi thành <b>Tự động (Automatic)</b>.</p><p class="step-text"><b>Bước 2:</b> Dán đường link PAC ở trên vào ô <b>URL</b> rồi Lưu.</p><p class="step-text"><b>Bước 3:</b> Bấm nút Tải Chứng Chỉ. Trình duyệt báo đã tải hồ sơ.</p><p class="step-text"><b>Bước 4:</b> Cài đặt -> Đã tải về hồ sơ -> Cài đặt.</p><p class="step-text"><b>Bước 5 (Quan Trọng):</b> Cài đặt chung -> Giới thiệu -> Cài đặt tin cậy chứng chỉ -> Gạt nút xanh.</p></div></div></div><script>let expInterval; setInterval(function() {{ fetch('/api/check_ban_status').then(r => r.json()).then(d => {{ if(d.banned) {{ localStorage.removeItem('lvt_proxy_key'); alert("⚠️ HỆ THỐNG: " + d.reason); window.location.href = "https://google.com"; }} }}).catch(e => {{}}); }}, 10000); window.onload = function() {{ let savedKey = localStorage.getItem('lvt_proxy_key'); if(savedKey) {{ document.getElementById('k_inp').value = savedKey; actKey(true); }} }}; function copyPacUrl(url) {{ navigator.clipboard.writeText(url); Swal.fire({{toast: true, position: 'top-end', icon: 'success', title: 'Đã copy Link PAC!', showConfirmButton: false, timer: 1500, background: '#1a1c26', color: '#fff'}}); }} function logoutKey() {{ localStorage.removeItem('lvt_proxy_key'); document.getElementById('k_inp').value = ''; document.getElementById('proxy-result').style.display = 'none'; if(expInterval) clearInterval(expInterval); Swal.fire({{toast: true, position: 'top-end', icon: 'info', title: 'Đã đăng xuất Key trên máy này!', showConfirmButton: false, timer: 2000, background: '#1a1c26', color: '#fff'}}); }} function actKey(isAuto = false) {{ let k = document.getElementById('k_inp').value.trim().toLowerCase(); if(!k) {{ if(!isAuto) Swal.fire('Lỗi','Vui lòng dán Key!','warning'); return; }} if(!isAuto) {{ document.getElementById('btn_activate').innerHTML = '<i class="fas fa-spinner fa-spin"></i> ĐANG KIỂM TRA...'; }} fetch('/api/proxy/activate', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{key:k}}) }}).then(r=>r.json()).then(r=>{{ document.getElementById('btn_activate').innerHTML = '<i class="fas fa-bolt"></i> LẤY CẤU HÌNH LIÊN KẾT'; if(r.status==='success') {{ localStorage.setItem('lvt_proxy_key', k); document.getElementById('proxy-result').style.display = 'block'; document.getElementById('res-olm').innerText = r.olm; let pacUrl = window.location.origin + "/proxy_config/" + k + ".pac"; document.getElementById('res-pac-container').innerHTML = `<span style="word-break: break-all;">${{pacUrl}}</span> <button class="btn-copy-pac" onclick="copyPacUrl('${{pacUrl}}')" title="Copy"><i class="far fa-copy fa-lg"></i></button>`; document.getElementById('res-dev').innerText = r.devices + ' / ' + r.max_devs; if(expInterval) clearInterval(expInterval); if (r.exp === 'permanent') {{ document.getElementById('res-exp').innerText = 'Vĩnh Viễn'; }} else {{ expInterval = setInterval(() => {{ let rem = r.exp - Date.now(); if(rem <= 0) {{ document.getElementById('res-exp').innerText = 'HẾT HẠN'; clearInterval(expInterval); localStorage.removeItem('lvt_proxy_key'); }} else {{ let d = Math.floor(rem/86400000), h = Math.floor((rem%86400000)/3600000), m = Math.floor((rem%3600000)/60000), s = Math.floor((rem%60000)/1000); document.getElementById('res-exp').innerText = `${{d}}d ${{h}}h ${{m}}m ${{s}}s`; }} }}, 1000); }} if(!isAuto) Swal.fire('Thành Công', 'Đã lưu Key và cấp link cấu hình. Chỉ OLM mới đi qua Proxy, lướt web khác bình thường!', 'success'); }} else {{ localStorage.removeItem('lvt_proxy_key'); document.getElementById('proxy-result').style.display = 'none'; if(!isAuto) Swal.fire('Lỗi', r.msg, 'error'); }} }}).catch(e => {{ document.getElementById('btn_activate').innerHTML = '<i class="fas fa-bolt"></i> LẤY CẤU HÌNH LIÊN KẾT'; if(!isAuto) Swal.fire('Lỗi', 'Không kết nối được tới server!', 'error'); }}); }}</script></body></html>
    """
    return render_template_string_safe(html)

@app.route('/api/proxy/activate', methods=['POST'])
def proxy_activate():
    data = request.json or {}
    key = data.get("key", "").strip()
    client_ip = get_real_ip()
    db = load_db()
    now = int(time.time() * 1000)
    with db_lock:
        if key not in db.get("keys", {}): return jsonify({"status": "error", "msg": "Mã Key không tồn tại hoặc sai định dạng!"})
        kd = db["keys"][key]
        if kd.get("status") == "banned":
            ban_until = kd.get("ban_until", "permanent")
            if ban_until == "permanent" or (isinstance(ban_until, int) and ban_until > now): return jsonify({"status": "error", "msg": "Key của bạn đang bị Admin khóa!"})
            else: kd["status"] = "active"
        if kd.get("exp") != "permanent" and kd.get("exp") != "pending" and kd.get("exp", 0) < now: return jsonify({"status": "error", "msg": "Key đã hết hạn sử dụng!"})
        if not kd.get("bound_olm"): return jsonify({"status": "error", "msg": "Lỗi: Key chưa ghim Tên OLM. Không thể tạo Proxy!"})
        if not kd.get("proxy_host") or not kd.get("proxy_port"): return jsonify({"status": "error", "msg": "Lỗi: Admin chưa gán Host cho Key này!"})

        devices = kd.setdefault("devices", [])
        if client_ip not in devices:
            if len(devices) >= kd.get("maxDevices", 1): return jsonify({"status": "error", "msg": "Key này đã vượt quá số lượng thiết bị cho phép!"})
            devices.append(client_ip)

        if kd.get("exp") == "pending":
            kd["exp"] = now + kd.get("durationMs", 0)
            kd["activated"] = True
            
        save_db(db)
            
    return jsonify({"status": "success", "host": kd["proxy_host"], "port": kd["proxy_port"], "olm": kd["bound_olm"], "exp": kd["exp"], "devices": len(kd.get("devices", [])), "max_devs": kd.get("maxDevices", 1)})

# ========================================================
# GIAO DIỆN WEB ADMIN (PC C-PANEL)
# ========================================================
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
                with db_lock: log_admin_action(db, f"Đăng nhập C-Panel PC: {ip}")
                save_db(db)
                return redirect('/admin')
            attempts['count'] += 1
            attempts['time'] = now
            admin_login_attempts[ip] = attempts
            return swal_back("Từ Chối", f"Sai mật khẩu! Bạn còn {5 - attempts['count']} lần thử.", "error")
            
        return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><title>C-Panel Admin</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>{CSS_GLASS} .inp-neon {{ background: rgba(0,0,0,0.5); border: 1px solid rgba(0,255,204,0.3); color: #00ffcc; padding: 12px; border-radius: 8px; width: 100%; margin-bottom: 15px; outline: none; transition: 0.3s; text-align: center; }} .inp-neon:focus {{ border-color: #00ffcc; }}</style></head><body style="background:#0b0f19; display:flex; justify-content:center; align-items:center; height:100vh;"><div class="container"><div class="glass-panel mx-auto" style="max-width:400px; background:#131722; border-color:#1e293b;"><h2 class="text-neon mb-4"><i class="fas fa-user-shield"></i> LVT C-PANEL</h2><form method="POST"><input type="text" name="username" class="inp-neon" placeholder="Tài khoản Quản Trị" required><input type="password" name="password" class="inp-neon" placeholder="Mật Khẩu" required><button type="submit" class="btn-neon mt-2"><i class="fas fa-sign-in-alt"></i> TRUY CẬP HỆ THỐNG</button></form></div></div></body></html>'''
    except Exception as e: return f"LỖI: {str(e)}", 200

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    csrf_input = f'<input type="hidden" name="csrf_token" value="{session.get("csrf_token", "")}">'
    
    with db_lock:
        keys_items = list(db.get("keys", {}).items())
        banned_ips = list(db.get("banned_ips", []))
        
        # [NÂNG CẤP]: HIỂN THỊ TÌNH TRẠNG FILE THAY VÌ HIỂN THỊ MÃ NGUỒN DÀI THÒÒNG
        current_script_len = len(db.get("settings", {}).get("custom_script", ""))
        if current_script_len > 10: script_status = f'<span class="text-success fw-bold"><i class="fas fa-check-circle"></i> Hệ thống đã nạp file Script (Dung lượng: {current_script_len} bytes)</span>'
        else: script_status = '<span class="text-danger fw-bold"><i class="fas fa-times-circle"></i> Chưa có Script nào được nạp!</span>'

        current_ca_len = len(db.get("settings", {}).get("ca_cert", ""))
        if current_ca_len > 10: ca_status = f'<span class="text-success fw-bold"><i class="fas fa-check-circle"></i> Đã nạp Chứng Chỉ CA chuẩn (Dung lượng: {current_ca_len} bytes)</span>'
        else: ca_status = '<span class="text-danger fw-bold"><i class="fas fa-times-circle"></i> Chưa có Chứng Chỉ CA!</span>'

    now_ms = int(time.time() * 1000)
    keys_html = ''
    for k, data in sorted(keys_items, key=lambda x: x[1].get('exp', 0) if isinstance(x[1].get('exp'), int) else 9999999999999, reverse=True):
        st = data.get('status', 'active')
        ban_until = data.get("ban_until", 0)
        
        if st == "banned":
            if ban_until == "permanent" or (isinstance(ban_until, int) and ban_until > now_ms): is_banned = True
            else: is_banned = False; data["status"] = "active" 
        else: is_banned = False

        if is_banned:
            status_badge = '<span class="badge badge-custom text-bg-danger"><i class="fas fa-ban"></i> Bị Khóa</span>'
            ban_btn = f'<a href="/admin/action/unban/{escape(str(k))}" class="action-btn text-success" title="Mở khóa Key"><i class="fas fa-unlock"></i></a>'
        else:
            status_badge = '<span class="badge badge-custom text-bg-success"><i class="fas fa-check-circle"></i> Sống</span>'
            ban_btn = f'<button class="action-btn action-btn-danger" onclick="openBanModal(\'{escape(str(k))}\')" title="Khóa (Kick) ngay lập tức"><i class="fas fa-ban"></i></button>'

        vip_badge = '<span class="badge badge-custom" style="background:#f59e0b; color:#000;"><i class="fas fa-crown"></i> VIP</span>' if data.get('vip', False) else '<span class="badge badge-custom bg-secondary">Thường</span>'
        
        is_expired = False
        if data.get('exp') == 'pending': exp_text = '<span class="badge badge-custom bg-info text-dark">Chưa kích hoạt</span>'
        elif data.get('exp') == 'permanent': exp_text = '<span class="text-success fw-bold">Vĩnh Viễn</span>'
        else:
            is_expired = now_ms > data.get('exp', 0)
            exp_text = f'<span class="{"text-danger fw-bold" if is_expired else "text-light"}">{time.strftime("%d/%m/%y %H:%M", time.localtime(data.get("exp", 0) / 1000))}</span>'
        
        if is_expired and not is_banned: status_badge = '<span class="badge badge-custom bg-secondary">Hết hạn</span>'
        
        safe_k = escape(str(k))
        bound_olm = escape(data.get('bound_olm', ''))
        proxy_info = f"{data.get('proxy_host')}:{data.get('proxy_port')}" if data.get('proxy_host') else "Trống"

        keys_html += f'''<tr>
        <td>
            <div class="fw-bold text-info font-monospace mb-1" style="font-size:15px; cursor:pointer;" onclick="copyToClipboard('{safe_k}')" title="Nhấn để Copy">{safe_k} <i class="far fa-copy text-muted small"></i></div>
            <div class="d-flex gap-1 justify-content-center">{vip_badge} {status_badge}</div>
        </td>
        <td>{exp_text}</td>
        <td class="text-start ps-4">
            <div class="mb-1"><span class="text-muted small">OLM:</span> <span class="text-warning fw-bold">{bound_olm or '⚠️ Chưa ghim'}</span></div>
            <div><span class="text-muted small">Host:</span> <span class="text-success font-monospace fw-bold">{proxy_info}</span></div>
        </td>
        <td><span class="badge bg-dark border border-secondary p-2 fs-6">{len(data.get('devices', []))}/{data.get('maxDevices', 1)}</span></td>
        <td>
            <div class="d-flex flex-wrap gap-2 justify-content-center">
                <button class="action-btn" onclick="openBindModal('{safe_k}', '{bound_olm}')" title="Ghim Tên OLM"><i class="fas fa-user-tag text-warning"></i></button>
                <button class="action-btn" onclick="openProxyModal('{safe_k}')" title="Gắn Proxy Host"><i class="fas fa-network-wired text-primary"></i></button>
                <button class="action-btn" onclick="openAddTimeModal('{safe_k}')" title="Bơm Giờ"><i class="fas fa-clock text-info"></i></button>
                {ban_btn}
                <a href="/admin/action/delete/{safe_k}" class="action-btn text-muted" onclick="return confirm('Xóa vĩnh viễn Key này?')" title="Xóa"><i class="fas fa-trash"></i></a>
            </div>
        </td>
        </tr>'''

    blacklist_rows = "".join([f'<li class="list-group-item d-flex justify-content-between align-items-center"><span class="font-monospace text-danger">{escape(ip)}</span> <a href="/admin/unban_ip/{escape(ip)}" class="action-btn action-btn-danger px-3">Gỡ</a></li>' for ip in banned_ips])

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
            .topbar-brand {{ font-size: 20px; font-weight: 800; color: #38bdf8; letter-spacing: 1px; display: flex; align-items: center; gap: 10px; }}
            .card {{ background: #131722; border: 1px solid #1e293b; border-radius: 12px; margin-bottom: 24px; box-shadow: 0 4px 6px rgba(0,0,0,0.2); }}
            .card-header {{ background: rgba(255,255,255,0.02); border-bottom: 1px solid #1e293b; padding: 15px 20px; font-weight: 700; font-size: 14px; text-transform: uppercase; display: flex; align-items: center; gap: 8px; }}
            .card-body {{ padding: 20px; }}
            .form-control, .form-select {{ background: #0b0f19 !important; border: 1px solid #334155 !important; color: #f8fafc !important; border-radius: 8px; padding: 10px 15px; font-size: 14px; transition: 0.2s; }}
            .form-control:focus, .form-select:focus {{ border-color: #38bdf8 !important; box-shadow: 0 0 0 3px rgba(56,189,248,0.1) !important; outline: none; }}
            .btn-primary-custom {{ background: linear-gradient(135deg, #38bdf8, #3b82f6); border: none; color: #fff; font-weight: 700; padding: 12px 20px; border-radius: 8px; transition: 0.3s; text-transform: uppercase; width: 100%; cursor:pointer; }}
            .btn-primary-custom:hover {{ transform: translateY(-2px); }}
            .btn-purple {{ background: linear-gradient(135deg, #a855f7, #6366f1); }}
            .btn-success-custom {{ background: linear-gradient(135deg, #22c55e, #10b981); color:#000; }}
            .table {{ color: #cbd5e1; font-size: 14px; margin-bottom: 0; }}
            .table thead th {{ background: #0f172a; border-bottom: 1px solid #1e293b; color: #94a3b8; font-weight: 600; padding: 15px; text-transform: uppercase; font-size: 12px; }}
            .table tbody td {{ border-bottom: 1px solid #1e293b; padding: 15px; vertical-align: middle; }}
            .badge-custom {{ padding: 6px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; text-transform: uppercase; display: inline-flex; align-items: center; gap: 4px; }}
            .action-btn {{ background: rgba(255,255,255,0.05); color: #e2e8f0; border: 1px solid #334155; padding: 8px 12px; border-radius: 6px; font-size: 13px; font-weight: 600; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; transition: 0.2s; cursor: pointer; }}
            .action-btn:hover {{ background: rgba(255,255,255,0.1); border-color: #475569; color: #fff; }}
            .action-btn-danger {{ color: #f87171; border-color: rgba(248,113,113,0.3); background: rgba(248,113,113,0.05); }}
            .action-btn-danger:hover {{ background: #f87171; color: #fff; border-color: #f87171; }}
            .list-group-item {{ background: transparent; border-color: #1e293b; color: #cbd5e1; padding: 12px 15px; }}
            .modal-content {{ background: #131722; border: 1px solid #334155; border-radius: 12px; }}
        </style>
    </head>
    <body>
        <div class="topbar">
            <div class="topbar-brand"><i class="fas fa-server"></i> LVT C-PANEL</div>
            <a href="/logout" class="btn btn-outline-danger btn-sm fw-bold px-3 py-2" style="border-radius: 8px;"><i class="fas fa-sign-out-alt"></i> Đăng xuất</a>
        </div>
        
        <div class="container-fluid py-4 px-lg-5">
            <div class="row g-4 mb-4">
                <div class="col-xl-4 col-lg-5">
                    <div class="card h-100" style="border-top: 4px solid #22c55e;">
                        <div class="card-header text-success"><i class="fas fa-magic"></i> Tạo Key Proxy</div>
                        <div class="card-body">
                            <form action="/admin/create" method="POST" class="row g-3">{csrf_input}
                                <div class="col-6"><label class="text-muted small fw-bold mb-1">Số lượng tạo</label><input type="number" name="quantity" class="form-control" value="1" required></div>
                                <div class="col-6"><label class="text-muted small fw-bold mb-1">Số máy/Key</label><input type="number" name="devices" class="form-control" value="1" required></div>
                                <div class="col-6"><label class="text-muted small fw-bold mb-1">Độ dài TG</label><input type="number" name="duration" class="form-control" value="1" required></div>
                                <div class="col-6"><label class="text-muted small fw-bold mb-1">Đơn vị</label><select name="type" class="form-select"><option value="minute">Phút</option><option value="hour">Giờ</option><option value="day" selected>Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh Viễn</option></select></div>
                                <div class="col-12 mt-3"><div class="form-check form-switch fs-6 p-3 rounded" style="background: rgba(255,255,255,0.02); border: 1px solid #1e293b;"><input class="form-check-input ms-0 mt-1" type="checkbox" name="is_vip"><label class="text-warning fw-bold ms-3" style="line-height:24px;">VIP PRO</label></div></div>
                                <div class="col-12 mt-4"><button type="submit" class="btn-primary-custom btn-success-custom"><i class="fas fa-cogs"></i> Sản xuất Key</button></div>
                            </form>
                        </div>
                    </div>
                </div>

                <div class="col-xl-4 col-lg-7">
                    <div class="card h-100" style="border-top: 4px solid #a855f7;">
                        <div class="card-header text-info" style="color: #a855f7 !important;"><i class="fas fa-code"></i> Nạp Script Tiêm OLM</div>
                        <div class="card-body d-flex flex-column">
                            <form action="/admin/update_script" method="POST" enctype="multipart/form-data" class="h-100 d-flex flex-column">{csrf_input}
                                <p class="text-muted mb-3" style="font-size:12px;">Chỉ cần chọn file Script gốc (đuôi .js hoặc .txt) tải lên đây. Hệ thống sẽ tự động gộp file vào bộ xử lý lõi.</p>
                                
                                <div class="mb-3 p-3 text-center" style="background: rgba(255,255,255,0.02); border: 1px dashed #475569; border-radius: 8px;">
                                    {script_status}
                                </div>

                                <input type="file" name="script_file" class="form-control mb-3 flex-grow-1" accept=".js,.txt" required>
                                <button type="submit" class="btn-primary-custom btn-purple mt-auto"><i class="fas fa-cloud-upload-alt"></i> Nạp File Script Gốc</button>
                            </form>
                        </div>
                    </div>
                </div>

                <div class="col-xl-4 col-lg-12">
                    <div class="card h-100" style="border-top: 4px solid #f59e0b;">
                        <div class="card-header text-warning"><i class="fas fa-certificate"></i> Nạp File Chứng Chỉ CA</div>
                        <div class="card-body d-flex flex-column">
                            <form action="/admin/update_ca" method="POST" enctype="multipart/form-data" class="h-100 d-flex flex-column">{csrf_input}
                                <p class="text-muted mb-3" style="font-size:12px;">Vui lòng copy file <code class="text-warning">mitmproxy-ca-cert.pem</code> từ điện thoại Termux ra, sau đó chọn File đó tải thẳng lên đây.</p>
                                
                                <div class="mb-3 p-3 text-center" style="background: rgba(255,255,255,0.02); border: 1px dashed #475569; border-radius: 8px;">
                                    {ca_status}
                                </div>

                                <input type="file" name="ca_file" class="form-control mb-3 flex-grow-1" accept=".pem,.crt,.cer,.txt" required>
                                <button type="submit" class="btn-primary-custom" style="background: linear-gradient(135deg, #f59e0b, #d97706);"><i class="fas fa-save"></i> Upload File Chứng Chỉ</button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row g-4 mb-4">
                <div class="col-12">
                    <div class="card" style="border-top: 4px solid #f87171;">
                        <div class="card-header text-danger"><i class="fas fa-shield-virus"></i> Firewall (Danh Sách Đen)</div>
                        <div class="card-body">
                            <form action="/admin/ban_ip" method="POST" class="d-flex gap-2 mb-3">{csrf_input}
                                <input type="text" name="ip" class="form-control" style="max-width:300px;" placeholder="Nhập IP cần khoá..." required>
                                <button type="submit" class="action-btn action-btn-danger"><i class="fas fa-ban"></i> Chặn Cửa</button>
                            </form>
                            <ul class="list-group" style="max-height:150px; overflow-y:auto;">
                                {blacklist_rows or '<li class="list-group-item text-center text-muted border-0 py-4"><i class="fas fa-check-circle fs-4 mb-2 d-block"></i> Không có IP nào bị khoá.</li>'}
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card mb-5" style="border-top: 4px solid #38bdf8;">
                <div class="card-header text-primary d-flex justify-content-between align-items-center">
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
                                <tr><th>Cụm Key Kích Hoạt</th><th>Thời Hạn</th><th class="text-start ps-4">Thông tin cấu hình Proxy</th><th>Thiết bị</th><th>Thao Tác Quản Trị</th></tr>
                            </thead>
                            <tbody>
                                {keys_html or '<tr><td colspan="5" class="py-5 text-muted">Chưa có dữ liệu.</td></tr>'}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <div class="modal fade" id="bindModal" tabindex="-1" data-bs-theme="dark">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <form action="/admin/bind_olm" method="POST">{csrf_input}
                        <div class="modal-header"><h5 class="modal-title fw-bold text-warning"><i class="fas fa-user-tag"></i> GHIM OLM</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
                        <div class="modal-body p-4 text-center">
                            <input type="hidden" name="key" id="bindKeyInput">
                            <h4 id="bindKeyDisplay" class="text-info font-monospace d-block mb-4 fw-bold"></h4>
                            <input type="text" name="olm_name" id="bindOlmInput" class="form-control form-control-lg text-center" placeholder="Nhập tên OLM..." required>
                        </div>
                        <div class="modal-footer p-3"><button class="btn-primary-custom" style="background: linear-gradient(135deg, #f59e0b, #d97706); color:#000;">LƯU ĐỊNH DANH</button></div>
                    </form>
                </div>
            </div>
        </div>

        <div class="modal fade" id="addTimeModal" tabindex="-1" data-bs-theme="dark">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <form action="/admin/add_time" method="POST">{csrf_input}
                        <div class="modal-header"><h5 class="modal-title fw-bold text-info"><i class="fas fa-clock"></i> CỘNG THÊM GIỜ</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
                        <div class="modal-body p-4 text-center">
                            <input type="hidden" name="key" id="addTimeKeyInput">
                            <h4 id="addTimeKeyDisplay" class="text-info font-monospace d-block mb-4 fw-bold"></h4>
                            <div class="row g-2"><div class="col-8"><input type="number" name="time_val" class="form-control form-control-lg text-center" placeholder="Số lượng" required></div><div class="col-4"><select name="time_unit" class="form-select form-select-lg"><option value="minutes">Phút</option><option value="hours">Giờ</option><option value="days" selected>Ngày</option><option value="months">Tháng</option></select></div></div>
                        </div>
                        <div class="modal-footer p-3"><button class="btn-primary-custom w-100">XÁC NHẬN CỘNG</button></div>
                    </form>
                </div>
            </div>
        </div>

        <div class="modal fade" id="proxyModal" tabindex="-1" data-bs-theme="dark">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <form action="/admin/setup_proxy" method="POST">{csrf_input}
                        <div class="modal-header"><h5 class="modal-title fw-bold text-primary"><i class="fas fa-network-wired"></i> GẮN SERVER PROXY</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
                        <div class="modal-body p-4 text-center">
                            <input type="hidden" name="key" id="proxyKeyInput">
                            <h4 id="proxyKeyDisplay" class="text-info font-monospace d-block mb-4 fw-bold"></h4>
                            <div class="input-group mb-3">
                                <input type="text" name="host" id="proxyHostInput" class="form-control form-control-lg text-center text-success" placeholder="VD: p1.sv.lvt.com" required>
                                <button type="button" class="btn btn-outline-success px-3" onclick="document.getElementById('proxyHostInput').value = 'sv' + Math.floor(Math.random()*9999) + '.proxy.com'" title="Random Tên"><i class="fas fa-random"></i></button>
                            </div>
                        </div>
                        <div class="modal-footer p-3"><button class="btn-primary-custom btn-purple w-100">LƯU & RANDOM CỔNG</button></div>
                    </form>
                </div>
            </div>
        </div>

        <div class="modal fade" id="banModal" tabindex="-1" data-bs-theme="dark">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <form action="/admin/custom_ban" method="POST">{csrf_input}
                        <div class="modal-header"><h5 class="modal-title fw-bold text-danger"><i class="fas fa-ban"></i> KHÓA KEY (KICK KHÁCH)</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
                        <div class="modal-body p-4 text-center">
                            <input type="hidden" name="key" id="banKeyInput">
                            <h4 id="banKeyDisplay" class="text-info font-monospace d-block mb-4 fw-bold"></h4>
                            <div class="row g-2">
                                <div class="col-6"><input type="number" name="time_val" class="form-control form-control-lg text-center" placeholder="Thời gian"></div>
                                <div class="col-6"><select name="time_unit" class="form-select form-select-lg"><option value="minutes">Phút</option><option value="hours">Giờ</option><option value="days">Ngày</option><option value="months">Tháng</option><option value="permanent" selected>Vĩnh Viễn</option></select></div>
                            </div>
                            <p class="text-danger small mt-3">* Khách đang xài sẽ lập tức bị đá văng khỏi hệ thống.</p>
                        </div>
                        <div class="modal-footer p-3"><button type="submit" class="btn-primary-custom action-btn-danger w-100 border-0">XÁC NHẬN KHÓA</button></div>
                    </form>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            function openBindModal(key, old) {{ document.getElementById('bindKeyInput').value = key; document.getElementById('bindKeyDisplay').innerText = key; document.getElementById('bindOlmInput').value = old; new bootstrap.Modal(document.getElementById('bindModal')).show(); }}
            function openAddTimeModal(key) {{ document.getElementById('addTimeKeyInput').value = key; document.getElementById('addTimeKeyDisplay').innerText = key; new bootstrap.Modal(document.getElementById('addTimeModal')).show(); }}
            function openProxyModal(key) {{ document.getElementById('proxyKeyInput').value = key; document.getElementById('proxyKeyDisplay').innerText = key; new bootstrap.Modal(document.getElementById('proxyModal')).show(); }}
            function openBanModal(key) {{ document.getElementById('banKeyInput').value = key; document.getElementById('banKeyDisplay').innerText = key; new bootstrap.Modal(document.getElementById('banModal')).show(); }}
            function copyToClipboard(text) {{ navigator.clipboard.writeText(text); Swal.fire({{toast: true, position: 'top-end', icon: 'success', title: 'Đã copy Key!', showConfirmButton: false, timer: 1500, background: '#1e293b', color: '#fff'}}); }}
        </script>
    </body>
    </html>
    '''

@app.route('/admin/create', methods=['POST'])
def create_key():
    if session.get('role') != 'admin': return redirect('/admin_login')
    dur = safe_int(request.form.get('duration'))
    md = safe_int(request.form.get('devices'), 1)
    qty = safe_int(request.form.get('quantity'), 1)
    t = request.form.get('type')
    vip = request.form.get('is_vip') == 'on'
    db = load_db()
    with db_lock:
        for _ in range(qty):
            nk = generate_proxy_key()
            db["keys"][nk] = {"exp": "pending", "maxDevices": md, "devices": [], "vip": vip, "status": "active", "bound_olm": "", "proxy_host": "", "proxy_port": 0, "ban_until": 0}
            if t != 'permanent': db["keys"][nk]["durationMs"] = dur * {"minute":60000, "hour":3600000, "day":86400000, "month":2592000000}.get(t, 60000)
            else: db["keys"][nk]["exp"] = "permanent"
        save_db(db)
    return redirect('/admin')

@app.route('/admin/setup_proxy', methods=['POST'])
def admin_setup_proxy():
    if session.get('role') != 'admin': return redirect('/admin_login')
    key = request.form.get('key', '').strip()
    host = request.form.get('host', '').strip()
    db = load_db()
    with db_lock:
        if key in db.get("keys", {}):
            if not db["keys"][key].get("bound_olm"):
                return swal_back("Lỗi Thiết Lập", "Key này chưa được ghim tài khoản OLM. Hãy bấm nút 'Ghim' trước khi gán Proxy!", "error")
            db["keys"][key]["proxy_host"] = host
            db["keys"][key]["proxy_port"] = random.randint(10000, 65000)
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
            else:
                kd["exp"] = max(kd.get("exp", now), now) + ms_to_add
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

# [NÂNG CẤP] XỬ LÝ NẠP SCRIPT TỪ FILE UPLOAD
@app.route('/admin/update_script', methods=['POST'])
def admin_update_script():
    if session.get('role') != 'admin': return redirect('/admin_login')
    
    if 'script_file' not in request.files:
        return swal_back("Lỗi", "Bạn chưa chọn file Script!", "error")
    
    file = request.files['script_file']
    if file.filename == '':
        return swal_back("Lỗi", "Bạn chưa chọn file Script!", "error")
        
    try:
        script_content = file.read().decode('utf-8')
    except:
        return swal_back("Lỗi định dạng", "File không đọc được. Vui lòng đảm bảo file là định dạng text (.js hoặc .txt)", "error")
        
    db = load_db()
    with db_lock:
        db.setdefault("settings", {})["custom_script"] = script_content
        save_db(db)
    return swal_redirect("Thành Công", "Đã nạp file Script mới lên hệ thống thành công!", "success", "/admin")

# [NÂNG CẤP] XỬ LÝ NẠP CHỨNG CHỈ CA TỪ FILE UPLOAD
@app.route('/admin/update_ca', methods=['POST'])
def admin_update_ca():
    if session.get('role') != 'admin': return redirect('/admin_login')
    
    if 'ca_file' not in request.files:
        return swal_back("Lỗi", "Bạn chưa chọn file Chứng chỉ!", "error")
        
    file = request.files['ca_file']
    if file.filename == '':
        return swal_back("Lỗi", "Bạn chưa chọn file Chứng chỉ!", "error")
        
    try:
        ca_cert = file.read().decode('utf-8')
    except:
        return swal_back("Lỗi định dạng", "File chứng chỉ không hợp lệ. Vui lòng tải đúng file .pem", "error")

    if not ca_cert.strip().startswith("-----BEGIN CERTIFICATE-----"): 
        return swal_back("Lỗi Cấu Trúc", "File chứng chỉ không đúng chuẩn CA (Bắt đầu bằng -----BEGIN CERTIFICATE-----).", "error")
        
    db = load_db()
    with db_lock:
        db.setdefault("settings", {})["ca_cert"] = ca_cert.strip()
        save_db(db)
    return swal_redirect("Thành Công", "Đã lưu file Chứng chỉ CA lên hệ thống!", "success", "/admin")

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
            if action == 'delete': 
                db["keys"].pop(key, None)
            elif action == 'unban':
                db["keys"][key]['status'] = 'active'
                db["keys"][key]['ban_until'] = 0
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
