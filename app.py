import os, json, time, random, hashlib, threading, requests, shutil, base64, secrets, hmac, string
from urllib.parse import urlparse
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
# CẤU HÌNH SHOP KEY MỚI NHẤT
# ========================================================
SHOP_PACKAGES = {
    "1H": {"name": "1 Giờ", "price": 10000, "dur_ms": 3600000, "vip": False},
    "7D": {"name": "7 Ngày", "price": 30000, "dur_ms": 604800000, "vip": True},
    "30D": {"name": "1 Tháng", "price": 100000, "dur_ms": 2592000000, "vip": True},
    "1Y": {"name": "1 Năm Học", "price": 150000, "dur_ms": 31536000000, "vip": True}
}

# Hàm chuyển đổi an toàn tránh lỗi 500
def safe_int(val, default=0):
    try: return int(val)
    except: return default

def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def swal_redirect(title, text, icon, url):
    return f"""<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #05050A; }}</style></head><body><script>
        Swal.fire({{ title: `{title}`, html: `{text}`, icon: '{icon}', background: '#11111A', color: '#fff', confirmButtonColor: '#00ffcc', allowOutsideClick: false, customClass: {{ popup: 'border border-info' }}
        }}).then(() => {{ window.location.href = '{url}'; }});
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
                
                # ADMIN MẶC ĐỊNH
                if "admin" not in data["users"]:
                    data["users"]["admin"] = {"password_hash": hash_pwd("120510@"), "role": "admin", "balance": 0, "created_at": int(time.time() * 1000), "ips": [], "purchased_keys": [], "notices": [], "custom_script": 'console.log("HELLO OLM BY LVT");\n// Dán code hack gốc vào đây...'}
                
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
        with api_rate_lock:
            to_del_sig = [s for s, t in used_signatures.items() if now_ms - t > 20000]
            for s in to_del_sig: del used_signatures[s]
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
    db = load_db()
    banned_ips = set(db.get("banned_ips", []))
    ip = get_real_ip()
    if ip in banned_ips: return "⚠️ IP BỊ KHÓA BỞI LVT FIREWALL.", 403

    ua = request.headers.get('User-Agent', '').lower()
    blocked_bots = ['curl', 'postman', 'python', 'nmap', 'sqlmap', 'masscan', 'zgrab', 'wget', 'urllib', 'nikto']
    if any(bot in ua for bot in blocked_bots): return "Firewall Blocked Suspicious Bot/Scanner.", 403
        
    if request.path.startswith("/admin") and request.path != "/admin_login":
        if session.get('role') != 'admin':
            return redirect('/admin_login')
                
    if request.method == "POST" and request.path.startswith("/admin/"):
        origin = request.headers.get("Origin")
        req_host = request.headers.get("Host", "").split(':')[0]
        if origin:
            if urlparse(origin).netloc.split(':')[0] != req_host: return "CSRF Blocked!", 403

@app.errorhandler(404)
def not_found_trap(e):
    ip = get_real_ip()
    suspicious_paths = ['.env', 'wp-admin', 'wp-login.php', 'config.php', 'backup.zip', '.git', 'phpmyadmin']
    if any(s in request.path for s in suspicious_paths):
        report_bad_signature(ip)
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
                db.setdefault("security_alerts", []).insert(0, {"time": int(time.time()*1000), "id": ip, "reason": "Tấn công mạng / Quét thư mục ẩn"})
                save_db(db)

# ========================================================
# API SPOOFER & CẤP PHÉP BƠM CODE (CÓ CHẶN GHIM OLM)
# ========================================================
def check_api_rate_limit(ip):
    now = time.time()
    with api_rate_lock:
        if len(api_rate_cache) > 5000: api_rate_cache.clear()
        history = api_rate_cache.get(ip, [])
        history = [t for t in history if now - t < 5] 
        if len(history) >= 15: return False
        history.append(now)
        api_rate_cache[ip] = history
        return True

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
        if key not in db["keys"]: return False, "Key không tồn tại hoặc đã bị xóa!"
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
        
        # LOGIC GHIM OLM CỰC CHẶT
        bound_olm = kd.get("bound_olm", "").strip()
        if bound_olm and req_olm_name != "N/A":
            if bound_olm.lower() != req_olm_name.lower():
                kd["status"] = "banned" # TỬ HÌNH LUÔN
                db.setdefault("security_alerts", []).insert(0, {"time": now, "id": ip, "user": req_olm_name, "reason": f"Sử dụng Key ({key}) sai tài khoản chỉ định ({bound_olm})"})
                save_db(db)
                return False, f"GIAN LẬN: Key này chỉ dành cho tài khoản [{bound_olm}]. Bạn dùng cho [{req_olm_name}] -> Key đã bị KHÓA VĨNH VIỄN!"

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
    ip = get_real_ip()
    if request.method == 'OPTIONS': return make_response("ok", 200)
    data = request.json or {}
    key = data.get('key', '')
    deviceId = data.get('deviceId', '')
    olm_name = data.get('olm_name', 'N/A')
    
    db = load_db()
    valid, msg = _core_validate(db, key, deviceId, olm_name, ip)
    if not valid: return jsonify({"status": "error", "message": msg}), 400

    return jsonify({"status": "success", "loader_enabled": db["keys"][key].get("loader_enabled", True)})

@app.route('/api/core', methods=['POST', 'OPTIONS'])
def serve_core_payload():
    ip = get_real_ip()
    if request.method == 'OPTIONS': return make_response("ok", 200)
    data = request.json or {}
    key = data.get('key', '')
    deviceId = data.get('deviceId', '')
    olm_name = data.get('olm_name', 'N/A')
    
    db = load_db()
    valid, _ = _core_validate(db, key, deviceId, olm_name, ip)
    if not valid: return jsonify({"status": "error"}), 403

    # Giao lại việc thiết lập script duy nhất cho Admin
    custom_script = db["users"].get("admin", {}).get("custom_script", "")

    encoded_core = base64.b64encode(custom_script.encode('utf-8')).decode('utf-8')
    reversed_core = encoded_core[::-1]
    return jsonify({"status": "success", "payload": reversed_core})

@app.route('/api/script_ping', methods=['POST'])
def script_ping():
    ip = get_real_ip()
    if not check_api_rate_limit(ip): return "Too Many Requests", 429
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

# ========================================================
# TÍNH NĂNG V2.0: MÔI TRƯỜNG ẢO HÓA (AUTO BƠM SCRIPT)
# ========================================================
@app.route('/play_hack/<key>')
def play_hack(key):
    if 'username' not in session: return redirect('/login')
    db = load_db()
    ip = get_real_ip()
    
    valid, msg = _core_validate(db, key, deviceId=None, req_olm_name="N/A", ip=ip)
    if not valid:
        session.pop('active_key', None)
        return swal_redirect("TRỤC XUẤT", msg, "error", "/key_dashboard")

    custom_script = db["users"].get("admin", {}).get("custom_script", "")

    return f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
        <title>LVT HACK - OLM.VN</title>
        <style>
            body, html {{ margin: 0; padding: 0; width: 100vw; height: 100vh; overflow: hidden; background: #000; }}
            #olm-frame {{ width: 100%; height: 100%; border: none; position: absolute; top: 0; left: 0; z-index: 1; }}
            #lvt-overlay-ui {{ position: absolute; top:0; left:0; width:100%; height:100%; pointer-events: none; z-index: 99999; }}
        </style>
    </head>
    <body>
        <iframe id="olm-frame" src="https://olm.vn"></iframe>
        <div id="lvt-overlay-ui"></div>
        <script>
            try {{
                {custom_script}
            }} catch(e) {{ console.error("Lỗi Script:", e); }}
            
            setInterval(() => {{
                fetch('/api/script_ping', {{
                    method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{key: "{key}"}})
                }}).then(r=>r.text()).then(res => {{
                    if(res === "Banned for sharing") {{
                        alert("⚠️ HỆ THỐNG: Phát hiện Share Key hoặc vi phạm. Bạn đã bị đá về Web!"); 
                        window.top.location.href = "/key_dashboard";
                    }}
                }});
            }}, 30000);
        </script>
    </body>
    </html>
    """

# ========================================================
# GIAO DIỆN KHÁCH HÀNG (TRANG CHỦ / SHOP)
# ========================================================
CSS_GLASS = """
body { background: #05050A; color: #fff; font-family: 'Segoe UI', Tahoma, sans-serif; min-height: 100vh; margin:0;}
.glass-panel { background: rgba(20, 25, 35, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(0, 255, 204, 0.3); border-radius: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.8); padding: 40px; text-align: center; width: 100%; max-width: 400px; margin: 50px auto; }
h2 { color: #00ffcc; font-weight: 900; letter-spacing: 1px; margin-bottom: 30px; text-shadow: 0 0 15px rgba(0,255,204,0.5); }
.form-control { background: rgba(0,0,0,0.5) !important; border: 1px solid #333 !important; color: #fff !important; padding: 12px; border-radius: 8px; margin-bottom: 15px; }
.form-control:focus { border-color: #00ffcc !important; box-shadow: 0 0 10px rgba(0,255,204,0.3) !important; }
.btn-neon { background: linear-gradient(45deg, #00ffcc, #bd00ff); border: none; color: #000; font-weight: bold; width: 100%; padding: 12px; border-radius: 8px; transition: 0.3s; margin-top: 10px; cursor: pointer; }
.btn-neon:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(0,255,204,0.4); }
a.link-neon { color: #bd00ff; text-decoration: none; font-weight: bold; transition: 0.3s; }
"""

@app.route('/')
def home():
    shop_html = ""
    for pkg_id, pkg in SHOP_PACKAGES.items():
        vip_tag = '<div class="badge bg-danger mb-2">🔥 VIP PRO</div>' if pkg["vip"] else '<div class="badge bg-secondary mb-2">THƯỜNG</div>'
        shop_html += f'''
        <div class="col-md-3 col-6 mb-3">
            <div class="card bg-dark border-secondary p-3 h-100 text-center" style="transition:0.3s;border-radius:15px;" onmouseover="this.style.borderColor='#00ffcc';this.style.transform='translateY(-5px)';" onmouseout="this.style.borderColor='#6c757d';this.style.transform='translateY(0)';">
                {vip_tag}
                <h4 class="text-white fw-bold">{pkg["name"]}</h4>
                <div style="font-size:24px;font-weight:900;color:#bd00ff;margin:10px 0;">{pkg["price"]:,}đ</div>
                <a href="/login" class="btn btn-outline-info w-100 mt-auto fw-bold">MUA NGAY</a>
            </div>
        </div>'''

    welcome_script = ""
    if not session.get('welcomed'):
        session['welcomed'] = True
        welcome_script = "Swal.fire({ title: 'CHÀO MỪNG ĐẾN VỚI LVT TOOL!', html: 'Hệ thống tự động hóa và bảo mật đỉnh cao.<br><b style=\"color:#00ffcc\">Khám phá ngay!</b>', icon: 'info', background: '#11111A', color: '#fff', confirmButtonColor: '#bd00ff' });"

    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>LVT TOOL - Trang Chủ</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body{{background:#05050A;color:#fff;font-family:'Segoe UI',sans-serif;overflow-x:hidden;}} .hero{{background:linear-gradient(135deg,#000,#0a192f);padding:80px 20px;text-align:center;border-bottom:1px solid #00ffcc;}}</style></head><body>
    <div class="hero"><h1 style="color:#00ffcc;font-weight:900;text-shadow:0 0 15px #00ffcc;">⚡ HỆ THỐNG LVT TOOL VIP ⚡</h1><p class="text-secondary fs-5 mb-4">Tự động hóa thông minh - Bảo mật đa tầng - Kích hoạt trên di động dễ dàng</p><a href="#shop" class="btn btn-lg fw-bold mb-2" style="background:#00ffcc;color:#000;">XEM BẢNG GIÁ</a> <a href="/login" class="btn btn-outline-info btn-lg fw-bold ms-md-2 mb-2">ĐĂNG NHẬP</a></div>
    <div class="container py-5" id="shop"><h2 class="text-center fw-bold mb-5" style="color:#00ffcc;">BẢNG GIÁ DỊCH VỤ</h2><div class="row justify-content-center">{shop_html}</div></div><script>{welcome_script}</script></body></html>'''

@app.route('/login', methods=['GET', 'POST'])
def login():
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
            return swal_redirect("Thất bại!", f"Sai tài khoản hoặc mật khẩu.", "error", "/login")

    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Đăng Nhập</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>{CSS_GLASS}</style></head><body><div class="glass-panel"><h2>⚡ ĐĂNG NHẬP</h2><form method="POST"><input type="text" name="username" class="form-control" placeholder="Tên đăng nhập" required><input type="password" name="password" class="form-control" placeholder="Mật khẩu" required><button type="submit" class="btn-neon">VÀO HỆ THỐNG</button></form><div class="mt-4"><p class="text-secondary">Chưa có tài khoản? <a href="/register" class="link-neon">Đăng ký ngay</a></p></div></div></body></html>'''

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session: return redirect('/')
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '').strip()
        if not username.isalnum() or len(username) < 4: return swal_redirect("Lỗi", "Tên đăng nhập > 4 ký tự và không có dấu!", "warning", "/register")
        if len(password) < 6: return swal_redirect("Lỗi", "Mật khẩu từ 6 ký tự trở lên!", "warning", "/register")

        db = load_db()
        with db_lock:
            if username in db.setdefault("users", {}): return swal_redirect("Lỗi", "Tên đăng nhập đã tồn tại!", "error", "/register")
            db["users"][username] = {"password_hash": hash_pwd(password), "role": "user", "balance": 0, "created_at": int(time.time() * 1000), "ips": [get_real_ip()], "purchased_keys": [], "notices": [], "custom_script": ""}
            save_db(db)
        return swal_redirect("Tuyệt vời!", "Đăng ký thành công. Hãy đăng nhập!", "success", "/login")

    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Đăng Ký</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>{CSS_GLASS}</style></head><body><div class="glass-panel"><h2>⚡ TẠO TÀI KHOẢN</h2><form method="POST"><input type="text" name="username" class="form-control" placeholder="Tên đăng nhập (liền không dấu)" required><input type="password" name="password" class="form-control" placeholder="Mật khẩu (Tối thiểu 6 ký tự)" required><button type="submit" class="btn-neon">ĐĂNG KÝ NGAY</button></form><div class="mt-4"><p class="text-secondary">Đã có tài khoản? <a href="/login" class="link-neon">Đăng nhập</a></p></div></div></body></html>'''

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ========================================================
# GIAO DIỆN USER & SHOP MUA KEY CHÍNH THỨC
# ========================================================
@app.route('/dashboard')
def user_dashboard():
    if 'username' not in session or session.get('role') != 'user': return redirect('/login')
    
    username = session['username']
    db = load_db()
    user_data = db["users"].get(username, {})
    balance = user_data.get("balance", 0)
    owned_keys = user_data.get("purchased_keys", [])
    
    # Check Thông Báo Nạp Tiền
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
        shop_html += f'''
        <div class="col-lg-3 col-6">
            <div class="card bg-dark border-secondary text-center p-3 h-100" style="transition:0.3s; border-radius:15px;" onmouseover="this.style.borderColor='#00ffcc'" onmouseout="this.style.borderColor='#6c757d'">
                {vip_tag}
                <h6 class="text-white fw-bold">{pkg['name']}</h6>
                <h4 style="color:#bd00ff; font-weight:900;">{pkg['price']:,}đ</h4>
                <button class="btn btn-sm w-100 fw-bold mt-auto" style="background:#00ffcc; color:#000;" onclick="confirmBuy('{pkg_id}', '{pkg['name']}', {pkg['price']})">MUA NGAY</button>
            </div>
        </div>'''

    has_keys = len(owned_keys) > 0
    if has_keys:
        key_btn = f'<a href="/key_login" class="btn fw-bold w-100 mt-2" style="background:linear-gradient(45deg,#00ffcc,#0099ff);color:#000;padding:12px;">ĐI TỚI BẢNG ĐIỀU KHIỂN KEY CỦA BẠN <i class="fas fa-arrow-right"></i></a>'
    else:
        key_btn = "<p class='text-danger fw-bold mt-2'>Bạn cần mua ít nhất 1 Key để vào phòng này!</p>"

    return f'''
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Dashboard - User</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <style>body{{background:#05050A;color:#e0e0e0;font-family:'Segoe UI',sans-serif;}} .card{{background:#11111A;border-radius:15px;border:1px solid #333;box-shadow:0 5px 15px rgba(0,0,0,0.5);}}</style></head>
    <body class="p-2 p-md-4">
    <div class="container" style="max-width:1100px;">
        <div class="d-flex flex-column flex-md-row justify-content-between align-items-center mb-4 border-bottom border-secondary pb-3">
            <h2 style="color:#00ffcc; font-weight:900;" class="mb-3 mb-md-0">⚡ LVT SHOP CÁ NHÂN</h2>
            <div><span class="me-3">Xin chào, <b class="text-info">{username.upper()}</b></span> <a href="/logout" class="btn btn-sm btn-outline-danger">Thoát</a></div>
        </div>
        <div class="row g-4">
            <div class="col-md-4">
                <div class="card p-4 text-center border-info h-100">
                    <h5 class="text-secondary">SỐ DƯ CỦA BẠN</h5>
                    <h2 style="color:#00ffcc; font-weight:900; font-size:40px;">{balance:,}<small style="font-size:20px;">đ</small></h2>
                    <hr class="border-secondary">
                    <p class="text-warning mb-1" style="font-size:14px;"><i class="fas fa-university"></i> <b>CÁCH NẠP TIỀN AUTO</b></p>
                    <p class="text-muted" style="font-size:12px;">Chuyển khoản với nội dung:<br><strong class="text-white fs-6">NAP {username.upper()}</strong></p>
                    <a href="https://zalo.me/123456789" target="_blank" class="btn btn-outline-info btn-sm fw-bold">Liên hệ Admin (Zalo)</a>
                </div>
            </div>
            <div class="col-md-8">
                <div class="card p-4 border-secondary h-100">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h4 style="color:#bd00ff; font-weight:900; margin:0;"><i class="fas fa-shopping-cart"></i> MUA MÃ KEY MỚI</h4>
                    </div>
                    <div class="row g-3">{shop_html}</div>
                </div>
            </div>
            <div class="col-12">
                <div class="card p-4 border-success text-center">
                    <h4 style="color:#00ffcc; font-weight:900; margin-bottom:10px;"><i class="fas fa-rocket"></i> VÀO PHÒNG ĐIỀU KHIỂN HACK</h4>
                    <p class="text-muted">Nơi Quản lý Key, lấy mã kích hoạt và bơm thẳng vào OLM.</p>
                    {key_btn}
                </div>
            </div>
        </div>
    </div>
    <form id="buyForm" action="/buy" method="POST"><input type="hidden" name="pkg_id" id="pkgInput"><input type="hidden" name="os_type" id="osInput"><input type="hidden" name="olm_name" id="olmInput"></form>
    <script>
        {swal_scripts}
        function confirmBuy(id, name, price) {{
            Swal.fire({{
                title: 'CHỈ ĐỊNH TÀI KHOẢN OLM',
                html: `<p>Gói <b>${{name}}</b> (${{price.toLocaleString()}}đ)</p>
                       <input type="text" id="swal-olm" class="swal2-input" placeholder="Nhập nick OLM (Ví dụ: hp_luongvantuyen)" style="width: 80%; background: #000; color: #00ffcc; border: 1px solid #00ffcc;">
                       <div style="margin-top: 15px; font-size: 14px;">
                           <b>CHỌN HỆ ĐIỀU HÀNH:</b><br>
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

@app.route('/buy', methods=['POST'])
def buy_key():
    if 'username' not in session or session.get('role') != 'user': return redirect('/login')
    username = session['username']
    pkg_id = request.form.get('pkg_id')
    os_type = request.form.get('os_type', 'android')
    olm_name = request.form.get('olm_name', '').strip()
    
    if pkg_id not in SHOP_PACKAGES: return swal_redirect("Lỗi", "Gói không tồn tại!", "error", "/dashboard")
    pkg = SHOP_PACKAGES[pkg_id]
    price = pkg['price']
    
    db = load_db()
    with db_lock:
        user_data = db["users"].get(username)
        if user_data['balance'] < price: return swal_redirect("Số Dư Không Đủ!", "Hãy nạp thêm tiền.", "warning", "/dashboard")
        
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
        
    html_msg = f"""<div style='text-align:left; font-size:14px;'><p>Gói mua: <b style='color:#bd00ff'>{pkg['name']}</b> ({'iOS' if os_type=='ios' else 'Android/PC'})</p><p>Ghim Định Danh: <b style='color:#ff3366'>{olm_name}</b></p><p>Mã Key của bạn là:</p>
        <div style='background:#000; padding:10px; border:1px dashed #00ffcc; border-radius:5px; text-align:center; font-family:monospace; font-size:18px; color:#00ffcc; margin-bottom:15px; cursor:pointer;' onclick='navigator.clipboard.writeText("{nk}");Swal.showValidationMessage("Đã copy!");'>{nk}</div></div>"""
    return swal_redirect("🎉 MUA KEY THÀNH CÔNG!", html_msg, "success", "/key_dashboard")


# ========================================================
# HỆ THỐNG ĐĂNG NHẬP KEY & KÍCH HOẠT HACK (KEY DASHBOARD)
# ========================================================
@app.route('/key_login', methods=['GET', 'POST'])
def key_login():
    if 'username' not in session or session.get('role') != 'user': return redirect('/login')
    
    if request.method == 'POST':
        k = request.form.get('key_input', '').strip()
        db = load_db()
        if k in db.get("keys", {}):
            session['active_key'] = k
            return swal_redirect("Chấp nhận mã Key!", "Đang đưa bạn vào Khoang Lái...", "success", "/key_dashboard")
        return swal_redirect("Thất bại", "Mã Key không tồn tại trong hệ thống!", "error", "/key_login")

    return f'''
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Kích Hoạt Key</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>{CSS_GLASS}</style></head>
    <body><div class="glass-panel"><h2>🔑 KHỞI ĐỘNG KEY SỬ DỤNG</h2>
    <form method="POST"><input type="text" name="key_input" class="form-control" placeholder="Dán mã Key của bạn vào đây..." required><button type="submit" class="btn-neon">ĐĂNG NHẬP KEY</button></form>
    <div class="mt-4"><a href="/dashboard" class="link-neon">⬅ Trở về Quầy Shop</a></div>
    </div></body></html>
    '''

@app.route('/key_dashboard')
def key_dashboard():
    if 'username' not in session: return redirect('/login')
    
    # Auto Set Active Key if only 1 key exists and not set
    db = load_db()
    if not session.get('active_key'):
        purchased = db["users"].get(session['username'], {}).get("purchased_keys", [])
        if len(purchased) > 0:
            session['active_key'] = purchased[0]["key"]
        else:
            return redirect('/key_login')

    active_key = session.get('active_key')
    kd = db.get("keys", {}).get(active_key)
    if not kd: 
        session.pop('active_key', None)
        return swal_redirect("Lỗi", "Key đã bị xóa khỏi hệ thống!", "error", "/key_login")

    now = int(time.time() * 1000)
    
    # KHIÊN CHẶN ĐÁ VĂNG
    if kd.get("status") == "banned":
        session.pop('active_key', None)
        return swal_redirect("BỊ KHÓA TỬ HÌNH", "Key của bạn đã bị BAN vĩnh viễn do vi phạm (Sai OLM chỉ định hoặc Spam IP)!", "error", "/dashboard")
    if kd.get("temp_ban_until", 0) > now:
        rem = (kd["temp_ban_until"] - now) // 60000
        session.pop('active_key', None)
        return swal_redirect("PHẠT TẠM THỜI", f"Key bị khóa tạm thời do Share Máy. Thử lại sau {rem} phút.", "warning", "/dashboard")
    if kd.get("exp") != "pending" and kd.get("exp") != "permanent" and kd.get("exp") < now:
        session.pop('active_key', None)
        return swal_redirect("HẾT HẠN", "Key của bạn đã hết thời gian sử dụng. Vui lòng mua mới!", "info", "/dashboard")

    is_vip = kd.get("vip", False)
    vip_color = "#bd00ff" if is_vip else "#00ffcc"
    vip_text = "VIP PRO" if is_vip else "THƯỜNG"
    
    exp = kd.get("exp")
    if exp == "pending": exp_str = "Sẽ kích hoạt trừ giờ khi dùng"
    elif exp == "permanent": exp_str = "Vĩnh viễn"
    else: exp_str = time.strftime("%H:%M:%S %d/%m/%Y", time.localtime(exp/1000))
    
    rc = kd.get("reset_count", 0)
    reset_txt = "Miễn phí (Lần 1)" if rc == 0 else "Trừ 10,000đ"

    bm_code = f"javascript:(function(){{let s=document.createElement('script');s.src='{WEB_URL}/api/script/lvt_vip_loader.user.js?k={active_key}';document.head.appendChild(s);}})();"

    return f'''
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Phòng Điều Khiển</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <style>body{{background:#05050A;color:#e0e0e0;font-family:'Segoe UI',sans-serif;}} .card-vip{{background:#11111A;border:2px solid {vip_color};border-radius:15px;box-shadow:0 0 20px {vip_color}44;}}</style></head>
    <body class="p-3">
    <div class="container" style="max-width:800px;">
        <div class="d-flex justify-content-between align-items-center mb-4 border-bottom border-secondary pb-2">
            <h3 style="color:{vip_color};font-weight:900;margin:0;">⚡ KHOANG LÁI HACK</h3>
            <a href="/dashboard" class="btn btn-outline-light btn-sm">Về Shop</a>
        </div>
        
        <div class="card-vip p-4 text-center mb-4">
            <div class="badge mb-3" style="background:{vip_color}; font-size:16px;">{vip_text}</div>
            <h2 class="text-white mb-2" style="font-family:monospace;letter-spacing:2px;cursor:pointer;" onclick="copyT('{active_key}')">{active_key} <i class="fas fa-copy" style="font-size:14px;color:#888;"></i></h2>
            <p class="text-muted mb-0">Hạn dùng: <b class="text-white">{exp_str}</b></p>
            <p class="text-danger mt-2 mb-0" style="font-size:12px;">Định danh: <b>{kd.get("bound_olm", "N/A")}</b></p>
            <div class="d-flex justify-content-center gap-5 mt-3 pt-3 border-top border-secondary">
                <div><small class="text-secondary">Thiết Bị</small><br><b class="fs-4 text-info">{len(kd.get('devices', []))}/{kd.get('maxDevices', 1)}</b></div>
                <div><small class="text-secondary">Đã Reset</small><br><b class="fs-4 text-warning">{rc} Lần</b></div>
            </div>
        </div>
        
        <div class="row g-3">
            <div class="col-md-12">
                <div class="p-3 bg-dark border border-info rounded h-100 text-center">
                    <h5 class="text-info fw-bold"><i class="fas fa-sync-alt"></i> RESET HWID (ĐỔI MÁY / ĐỔI OLM)</h5>
                    <p class="text-muted" style="font-size:13px;">Phí reset: <b class="text-white">{reset_txt}</b></p>
                    <form action="/user_reset_hwid" method="POST" onsubmit="return confirm('Chắc chắn muốn Reset thiết bị & định danh OLM cho Key này?')"><button class="btn btn-info w-100 fw-bold mt-2 text-dark">THỰC HIỆN RESET</button></form>
                </div>
            </div>
            <div class="col-12 mt-4">
                <button class="btn w-100 p-3 fw-bold fs-5" style="background:linear-gradient(45deg,#00ffcc,#0099ff);color:#000;box-shadow:0 0 20px rgba(0,255,204,0.4);" onclick="activateHackAuto('{active_key}')">🚀 KÍCH HOẠT HACK V2.0 (VÀO OLM NGAY)</button>
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function copyT(t){{ navigator.clipboard.writeText(t); Swal.fire({{toast:true,position:'top-end',icon:'success',title:'Đã sao chép Key!',showConfirmButton:false,timer:1500,background:'#111',color:'#fff'}}); }}
        
        function activateHackAuto(key) {{
            Swal.fire({{
                title: 'ĐANG KHỞI TẠO MÔI TRƯỜNG...',
                html: 'Hệ thống đang chuẩn bị Bơm Mã vào <b>OLM.VN</b>. Vui lòng chờ...',
                icon: 'info', background: '#11111A', color: '#fff', allowOutsideClick: false,
                didOpen: () => {{
                    Swal.showLoading();
                    setTimeout(() => {{ window.location.href = '/play_hack/' + key; }}, 1500);
                }}
            }});
        }}
    </script></body></html>
    '''

@app.route('/user_reset_hwid', methods=['POST'])
def user_reset_hwid():
    if 'username' not in session: return redirect('/login')
    active_key = session.get('active_key')
    if not active_key: return redirect('/key_login')
    
    db = load_db()
    with db_lock:
        u = db["users"].get(session['username'])
        kd = db["keys"].get(active_key)
        if not kd: return redirect('/key_login')
        
        rc = kd.get("reset_count", 0)
        if rc == 0:
            kd["devices"] = []
            kd["known_ips"] = {}
            kd["bound_olm"] = "" # Reset cả định danh
            kd["reset_count"] += 1
            save_db(db)
            return swal_redirect("Reset Thành Công!", "Đã gỡ thiết bị và xóa định danh OLM miễn phí (Lần 1).", "success", "/key_dashboard")
        else:
            if u["balance"] < 10000:
                return swal_redirect("Thất bại!", "Bạn cần 10,000đ để Reset từ lần thứ 2 trở đi.", "error", "/key_dashboard")
            u["balance"] -= 10000
            kd["devices"] = []
            kd["known_ips"] = {}
            kd["bound_olm"] = ""
            kd["reset_count"] += 1
            save_db(db)
            return swal_redirect("Reset Thành Công!", "Đã trừ 10,000đ và gỡ thiết bị thành công.", "success", "/key_dashboard")

# ========================================================
# GIAO DIỆN WEB ADMIN QUẢN LÝ TỔNG TÀI KHOẢN VÀ KEY
# ========================================================
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
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
            
        return swal_redirect("Từ Chối Truy Cập", f"Thông tin sai!", "error", "/admin_login")
    
    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Admin Login</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>{CSS_GLASS}</style></head><body><div class="glass-panel"><h2>🔐 QUẢN TRỊ VIÊN</h2><form method="POST"><input type="text" name="username" class="form-control" placeholder="Tên Admin" required><input type="password" name="password" class="form-control" placeholder="Mật Khẩu" required><button type="submit" class="btn btn-neon">VÀO PHÒNG ĐIỀU KHIỂN</button></form></div></body></html>'''

@app.route('/admin')
def admin_dashboard():
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
        keys_count = len(udata.get("purchased_keys", []))
        created = time.strftime("%d/%m/%y", time.localtime(udata.get("created_at", 0)/1000))
        
        users_html += f'''
        <tr>
            <td><strong class="text-warning">{escape(uname)}</strong><br><small class="text-muted">{created}</small></td>
            <td><span class="badge bg-success" style="font-size:13px;">{bal:,}đ</span></td>
            <td><span class="badge bg-info text-dark">{keys_count} Keys</span></td>
            <td>
                <form action="/admin/add_balance" method="POST" class="d-flex gap-1 justify-content-center">
                    <input type="hidden" name="username" value="{escape(uname)}">
                    <input type="number" name="amount" class="form-control form-control-sm bg-dark text-light border-secondary px-1 text-center" style="width:70px;font-size:12px;" placeholder="± Tiền" required>
                    <button type="submit" class="btn btn-sm btn-primary fw-bold" style="font-size:11px;">CỘNG</button>
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

        vip_badge = '<span class="badge bg-primary">VIP</span>' if data.get('vip', False) else '<span class="badge bg-secondary">THƯỜNG</span>'
        
        is_expired = False
        if data.get('exp') == 'pending': exp_text = '<span class="text-info">Chưa KH</span>'
        elif data.get('exp') == 'permanent': exp_text = '<span class="text-success fw-bold">V.Viễn</span>'
        else:
            is_expired = now_ms > data.get('exp', 0)
            exp_text = f'<span class="{"text-danger fw-bold" if is_expired else "text-light"}">{time.strftime("%d/%m/%y %H:%M", time.localtime(data.get("exp", 0) / 1000))}</span>'
        
        if is_expired and not is_banned: status_badge = '<span class="badge bg-secondary">HẾT HẠN</span>'

        devs = data.get('devices', [])
        safe_k = escape(str(k))
        owner = escape(data.get('owner', 'Admin'))
        b_olm = escape(data.get('bound_olm', ''))
        bnd_html = f"<br><small class='text-danger'>Ghim: {b_olm}</small>" if b_olm else ""

        keys_html += f'''
        <tr class="key-row">
            <td><strong class="text-info" style="font-size:12px;">{safe_k}</strong><br>{vip_badge} {status_badge}<br><small class="text-warning">Chủ: {owner}</small>{bnd_html}</td>
            <td style="font-size:11px;">{exp_text}</td>
            <td><span class="badge bg-info text-dark">{len(devs)}/{data.get('maxDevices', 1)}</span><br><small class="text-muted">RS: {data.get('reset_count',0)}</small></td>
            <td>
                <div class="d-flex flex-wrap gap-1 justify-content-center">
                    <button class="btn btn-warning btn-sm" style="font-size:10px;" onclick="openBindModal('{safe_k}', '{b_olm}')">Ghim OLM</button>
                    <a href="/admin/action/reset-dev/{safe_k}" class="btn btn-primary btn-sm" style="font-size:10px;">🔄 Máy</a>
                    <a href="/admin/action/unban_temp/{safe_k}" class="btn btn-success btn-sm" style="font-size:10px;">Gỡ Phạt</a>
                    <a href="/admin/action/{"unban" if is_banned else "ban"}/{safe_k}" class="btn btn-{"light" if is_banned else "danger"} btn-sm" style="font-size:10px;">{"Cứu" if is_banned else "Trảm"}</a>
                    <a href="/admin/action/delete/{safe_k}" class="btn btn-dark btn-sm" onclick="return confirm('Xóa vĩnh viễn Key này?')" style="font-size:10px;">🗑️</a>
                </div>
            </td>
        </tr>'''

    blacklist_rows = "".join([f'<li class="list-group-item bg-dark text-light d-flex justify-content-between align-items-center" style="font-size:12px;">{escape(ip)} <a href="/admin/unban_ip/{escape(ip)}" class="btn btn-sm btn-danger p-0 px-2">Gỡ</a></li>' for ip in banned_ips])
    if not blacklist_rows: blacklist_rows = '<li class="list-group-item bg-dark text-muted text-center" style="font-size:12px;">Sạch sẽ</li>'
    
    logs_html = "".join([f'<li class="list-group-item bg-dark text-light border-secondary p-1 mb-1 rounded" style="font-size:11px;"><span class="text-warning">[{time.strftime("%H:%M", time.localtime(alog.get("time", 0)/1000))}]</span> {escape(alog.get("action", ""))}</li>' for alog in admin_logs[:15]])

    return f'''
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ADMIN DASHBOARD</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>body{{background:#05050A;color:#e0e0e0;font-family:'Segoe UI',sans-serif;font-size:13px;}} .card{{background:#11111A;border:1px solid #333;border-radius:12px;}} h5{{color:#00ffcc;font-weight:900;}} .table-container{{max-height:450px;overflow-y:auto;}} tbody tr:hover{{background:rgba(0,255,204,0.05)!important;}}</style>
    </head><body class="p-2 p-md-4">
    <div class="container-fluid">
        <div class="d-flex justify-content-between align-items-center mb-3 border-bottom border-secondary pb-2">
            <h3 class="m-0" style="color:#00ffcc; font-weight:900;">⚡ LVT SECURE ADMIN</h3>
            <div><a href="/logout" class="btn btn-outline-danger btn-sm fw-bold">Thoát</a></div>
        </div>
        
        <div class="row g-3">
            <div class="col-lg-6">
                <div class="row g-3 h-100">
                    <div class="col-md-6">
                        <div class="card p-3 h-100" style="border-color:#3366ff;">
                            <h5 style="color:#3366ff;"><i class="fas fa-users"></i> DANH SÁCH USER</h5>
                            <div class="table-container">
                                <table class="table table-dark table-hover table-sm align-middle mb-0 text-center">
                                    <thead class="table-active"><tr><th>Tài Khoản</th><th>Số Dư</th><th>Tài sản</th><th>Nạp Tiền</th></tr></thead>
                                    <tbody>{users_html}</tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card p-3 h-100" style="border-color:#bd00ff;">
                            <h5 style="color:#bd00ff;"><i class="fas fa-key"></i> TẠO KEY (TẶNG KHÁCH)</h5>
                            <form action="/admin/create" method="POST" class="row g-2 mt-1">
                                <div class="col-6"><input type="text" name="prefix" class="form-control form-control-sm bg-dark text-light border-secondary" placeholder="Mã (T)"></div>
                                <div class="col-6"><input type="number" name="quantity" class="form-control form-control-sm bg-dark text-light border-secondary" value="1" placeholder="SL"></div>
                                <div class="col-6"><input type="number" name="duration" class="form-control form-control-sm bg-dark text-light border-secondary" placeholder="Độ dài" required></div>
                                <div class="col-6"><select name="type" class="form-select form-select-sm bg-dark text-light border-secondary"><option value="hour">Giờ</option><option value="day" selected>Ngày</option><option value="month">Tháng</option><option value="permanent">V.Viễn</option></select></div>
                                <div class="col-12 mt-2"><button type="submit" class="btn btn-sm w-100 fw-bold" style="background:#bd00ff;color:white;">🚀 TẠO NGAY</button></div>
                            </form>
                            <hr class="border-secondary my-3">
                            <h5 style="color:#ff9900;"><i class="fas fa-code"></i> SET SCRIPT MẶC ĐỊNH</h5>
                            <button class="btn btn-sm btn-outline-warning w-100 fw-bold" data-bs-toggle="modal" data-bs-target="#adminScriptModal">Sửa Code Fallback</button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-lg-6">
                <div class="card p-3 h-100" style="border-color:#00ffcc;">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h5 class="m-0"><i class="fas fa-database"></i> TẤT CẢ MÃ KEY</h5>
                        <input type="text" class="form-control form-control-sm bg-dark text-light border-info" style="width:160px;" placeholder="🔍 Tìm Key / Tên..." onkeyup="let s=this.value.toLowerCase();document.querySelectorAll('.key-row').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(s)?'':'none');">
                    </div>
                    <div class="table-container">
                        <table class="table table-dark table-sm align-middle table-hover text-center mb-0">
                            <thead class="table-active"><tr><th>🔑 Key / Chủ / OLM</th><th>⏳ Hạn Dùng</th><th>💻 IP</th><th>⚙️ Thao tác</th></tr></thead>
                            <tbody>{keys_html}</tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <div class="col-lg-12">
                <div class="row g-3">
                    <div class="col-md-6">
                        <div class="card p-3 h-100" style="border-color:#ff3366;">
                            <h5 class="text-danger"><i class="fas fa-shield-virus"></i> FIREWALL BANS IP</h5>
                            <form action="/admin/ban_ip" method="POST" class="d-flex gap-2 mb-2">
                                <input type="text" name="ip" class="form-control form-control-sm bg-dark text-light border-secondary" placeholder="Nhập IP..." required>
                                <button type="submit" class="btn btn-sm btn-danger fw-bold">Chặn</button>
                            </form>
                            <ul class="list-group list-group-flush" style="max-height:100px;overflow-y:auto;">{blacklist_rows}</ul>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card p-3 h-100" style="border-color:#888;">
                            <h5 class="text-secondary"><i class="fas fa-list-ul"></i> LOGS HOẠT ĐỘNG SERVER</h5>
                            <ul class="list-group list-group-flush" style="max-height:100px;overflow-y:auto;">{logs_html}</ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="adminScriptModal" tabindex="-1" data-bs-theme="dark">
      <div class="modal-dialog modal-lg modal-dialog-centered">
        <div class="modal-content" style="background:#11111A; border:1px solid #ff9900;">
          <form action="/admin/update_script" method="POST">
              <div class="modal-header border-secondary"><h5 class="modal-title" style="color:#ff9900;font-weight:bold;">MÃ NGUỒN CHUNG (SƠ CUA)</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
              <div class="modal-body"><textarea name="script_content" class="form-control bg-dark text-light border-warning" rows="12" style="font-family:monospace; font-size:12px;">{escape(db.get("users", {{}}).get("admin", {{}}).get("custom_script", ""))}</textarea></div>
              <div class="modal-footer border-secondary"><button type="submit" class="btn btn-warning fw-bold w-100 text-dark">LƯU CÀI ĐẶT</button></div>
          </form>
        </div>
      </div>
    </div>
    
    <div class="modal fade" id="bindModal" tabindex="-1" data-bs-theme="dark">
      <div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:#111;border:1px solid #ffcc00;"><form action="/admin/bind_olm" method="POST"><div class="modal-body"><input type="hidden" name="key" id="bindKeyInput"><p>Ghim Định Danh OLM cho Key: <strong id="bindKeyDisplay" class="text-info"></strong></p><input type="text" name="olm_name" id="bindOlmInput" class="form-control bg-dark text-light" placeholder="Tên nick OLM khách (để trống: hủy)"></div><div class="modal-footer"><button type="submit" class="btn btn-warning w-100">Ghim Chặt Cứng</button></div></form></div></div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function openBindModal(key, current_olm) {{ document.getElementById('bindKeyInput').value = key; document.getElementById('bindKeyDisplay').innerText = key; document.getElementById('bindOlmInput').value = current_olm; new bootstrap.Modal(document.getElementById('bindModal')).show(); }}
    </script>
    </body></html>
    '''

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
            log_admin_action(db, f"Cộng/Trừ {amt}đ cho tài khoản {username}")
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
        log_admin_action(db, f"Tạo {qty} Key Tool mới ({dur} {t}) - Mác VIP: {vip}")
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
            log_admin_action(db, f"Ghim OLM {olm} cho Key {key}")
            save_db(db)
    return redirect('/admin')

@app.route('/admin/update_script', methods=['POST'])
def admin_update_script():
    if session.get('role') != 'admin': return redirect('/login')
    ns = request.form.get('script_content', '')
    db = load_db()
    with db_lock:
        db["users"]["admin"]["custom_script"] = ns
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
                log_admin_action(db, f"Chặn IP: {ip}")
                save_db(db)
    return redirect('/admin')

@app.route('/admin/unban_ip/<path:ip>')
def unban_ip(ip):
    if session.get('role') != 'admin': return redirect('/login')
    db = load_db()
    with db_lock:
        if ip in db.setdefault("banned_ips", []):
            db["banned_ips"].remove(ip)
            log_admin_action(db, f"Gỡ Firewall cho IP: {ip}")
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
                for u in db["users"]:
                    db["users"][u]["purchased_keys"] = [pk for pk in db["users"][u].get("purchased_keys", []) if pk["key"] != key]
            elif action == 'reset-dev':
                kd['devices'] = []
                kd['known_ips'] = {}
            log_admin_action(db, f"Lệnh [{action}] trên Key {key}")
            save_db(db)
    return redirect('/admin')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
