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
login_attempts = {}
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
    "1H": {"name": "1 Giờ", "price": 10000, "dur_ms": 3600000},
    "7D": {"name": "7 Ngày", "price": 30000, "dur_ms": 604800000},
    "30D": {"name": "1 Tháng", "price": 100000, "dur_ms": 2592000000},
    "1Y": {"name": "1 Năm Học", "price": 150000, "dur_ms": 31536000000}
}

# ========================================================
# CÔNG CỤ TẠO THÔNG BÁO POPUP SIÊU ĐẸP (SWEETALERT2)
# ========================================================
def swal_redirect(title, text, icon, url):
    return f"""
    <!DOCTYPE html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <style>body {{ background: #05050A; }}</style>
    </head><body><script>
        Swal.fire({{
            title: `{title}`, html: `{text}`, icon: '{icon}',
            background: '#11111A', color: '#fff', confirmButtonColor: '#00ffcc',
            allowOutsideClick: false
        }}).then(() => {{ window.location.href = '{url}'; }});
    </script></body></html>
    """

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
    
    if ip in banned_ips:
        return "⚠️ BẠN ĐÃ BỊ TỪ CHỐI TRUY CẬP BỞI HỆ THỐNG FIREWALL (IPS LVT-SECURE).", 403

    ua = request.headers.get('User-Agent', '').lower()
    blocked_bots = ['curl', 'postman', 'python', 'nmap', 'sqlmap', 'masscan', 'zgrab', 'wget', 'urllib', 'nikto']
    if any(bot in ua for bot in blocked_bots):
        return "Firewall Blocked Suspicious Bot/Scanner.", 403
        
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
                db.setdefault("security_alerts", []).insert(0, {"time": int(time.time()*1000), "id": ip, "reason": "Dò mật khẩu / Quét thư mục / Sai chữ ký API"})
                save_db(db)

def log_admin_action(db, action_text):
    db.setdefault("admin_logs", []).insert(0, {
        "time": int(time.time() * 1000),
        "action": action_text
    })
    db["admin_logs"] = db["admin_logs"][:100]

def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

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
        else:
            current_mtime = _last_db_mtime

        if current_mtime > _last_db_mtime or not GLOBAL_DB:
            if not os.path.exists(DB_FILE) and os.path.exists(DB_BACKUP):
                shutil.copy2(DB_BACKUP, DB_FILE)
            data = None
            if os.path.exists(DB_FILE):
                try:
                    with open(DB_FILE, 'r', encoding='utf-8') as f: data = json.load(f)
                except Exception: pass
            if not data:
                data = {"users": {}, "keys": {}, "banned_ips": [], "admin_logs": [], "security_alerts": []}
            
            try:
                data.setdefault("users", {})
                data.setdefault("keys", {})
                data.setdefault("banned_ips", [])
                data.setdefault("admin_logs", [])
                data.setdefault("security_alerts", []) 
                
                # TẠO TÀI KHOẢN ADMIN MẶC ĐỊNH
                if "admin" not in data["users"]:
                    data["users"]["admin"] = {
                        "password_hash": hash_pwd("120510@"),
                        "role": "admin",
                        "balance": 0,
                        "created_at": int(time.time() * 1000),
                        "ips": [],
                        "purchased_keys": [],
                        "notices": [],
                        "custom_script": 'console.log("HELLO OLM BY LVT");\n// Dán code hack gốc vào đây...'
                    }
                
                for u in data["users"]:
                    data["users"][u].setdefault("notices", [])
                    data["users"][u].setdefault("custom_script", "")

                for k in data["keys"]:
                    data["keys"][k].setdefault("owner", "admin")
                    data["keys"][k].setdefault("violations", 0)
                    data["keys"][k].setdefault("temp_ban_until", 0)
                    data["keys"][k].setdefault("loader_enabled", True)
                    data["keys"][k].setdefault("devices", [])
                GLOBAL_DB = data
                _last_db_mtime = current_mtime
            except Exception as e: pass
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
        except Exception as e: 
            if os.path.exists(temp_file): os.remove(temp_file)

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
                        if isinstance(exp, int) and (now_ms - exp) > 604800000: # Xóa sau 7 ngày hết hạn
                            del db["keys"][k]
                            changed = True
                if len(db.get("security_alerts", [])) > 100:
                    db["security_alerts"] = db["security_alerts"][:50]
                    changed = True
            if changed: save_db(db)
        except: pass

threading.Thread(target=garbage_collector, daemon=True).start()

def generate_secure_key(prefix=""):
    chars = string.ascii_letters + string.digits
    safe_chars = ''.join([c for c in chars if c not in 'IlO0'])
    rand_str = ''.join(secrets.choice(safe_chars) for _ in range(14))
    if prefix: return f"{prefix}-{rand_str}"
    return rand_str

# ========================================================
# API TÀNG HÌNH (SPOOFER & CẤP PHÉP BƠM CODE)
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

def _core_validate(db, key, deviceId=None):
    now = int(time.time() * 1000)
    with db_lock:
        if key not in db["keys"]: return False, "Key không tồn tại hoặc đã bị xóa!"
        kd = db["keys"][key]
        if kd.get('status') == 'banned': return False, "Key của bạn đã bị Admin khóa vĩnh viễn!"
        
        temp_ban = kd.get("temp_ban_until", 0)
        if temp_ban > now:
            rem = (temp_ban - now) // 60000
            return False, f"Key đang bị phạt do Share Key! Vui lòng thử lại sau {rem} phút."

        db_changed = False
        if kd.get('exp') == 'pending': 
            kd['exp'] = now + kd.get('durationMs', 0)
            db_changed = True
            
        if kd.get('exp') != 'permanent' and now > kd.get('exp', 0): 
            return False, "Key của bạn đã hết hạn sử dụng!"
        
        if deviceId:
            devices = kd.setdefault("devices", [])
            if deviceId not in devices:
                if len(devices) >= kd.get("maxDevices", 1): return False, "Key đã đạt giới hạn thiết bị tối đa!"
                devices.append(deviceId)
                db_changed = True
        
        if db_changed: save_db(db)
        return True, "Success"

@app.route('/api/check', methods=['POST', 'OPTIONS'])
def check_api():
    ip = get_real_ip()
    if not check_api_rate_limit(ip): return jsonify({"status": "error", "message": "Spam API!"}), 429
    if request.method == 'OPTIONS': return make_response("ok", 200)
    
    data = request.json or {}
    if not verify_request_signature(data):
        report_bad_signature(ip) 
        return jsonify({"status": "error", "message": "Chữ ký mã hóa API không hợp lệ. Vui lòng tải lại Script!"}), 403

    key = data.get('key', '')[:100]
    deviceId = data.get('deviceId', '')[:100]
    
    db = load_db()
    valid, msg = _core_validate(db, key, deviceId)
    if not valid: return jsonify({"status": "error", "message": msg}), 400

    with db_lock:
        active_sessions[key] = {"ip": ip, "key": key, "last_seen": time.time()}
        if ip not in db["keys"][key].get("known_ips", {}):
            db["keys"][key].setdefault("known_ips", {})[ip] = time.time()
            save_db(db)

    return jsonify({"status": "success", "loader_enabled": db["keys"][key].get("loader_enabled", True)})

@app.route('/api/core', methods=['POST', 'OPTIONS'])
def serve_core_payload():
    """TRẢ VỀ SCRIPT TÙY CHỈNH CỦA NGƯỜI DÙNG TỪ CƠ SỞ DỮ LIỆU"""
    ip = get_real_ip()
    if not check_api_rate_limit(ip): return jsonify({"status": "error"}), 429
    if request.method == 'OPTIONS': return make_response("ok", 200)

    data = request.json or {}
    if not verify_request_signature(data): return jsonify({"status": "error"}), 403
    
    key = data.get('key', '')
    deviceId = data.get('deviceId', '')
    
    db = load_db()
    valid, _ = _core_validate(db, key, deviceId)
    if not valid: return jsonify({"status": "error"}), 403

    # Kéo code tùy chỉnh của chủ sở hữu Key
    owner = db["keys"][key].get("owner", "admin")
    custom_script = db["users"].get(owner, {}).get("custom_script", "")
    
    if not custom_script.strip():
        # Lấy script của admin nếu user chưa cài
        custom_script = db["users"].get("admin", {}).get("custom_script", "")
        if not custom_script.strip():
            custom_script = 'console.log("⚠️ CHƯA CÓ MÃ NGUỒN NÀO ĐƯỢC THIẾT LẬP Ở WEB ADMIN!");'

    # MÃ HÓA NGƯỢC
    encoded_core = base64.b64encode(custom_script.encode('utf-8')).decode('utf-8')
    reversed_core = encoded_core[::-1]
    return jsonify({"status": "success", "payload": reversed_core})

@app.route('/api/script_ping', methods=['POST', 'OPTIONS'])
def script_ping():
    ip = get_real_ip()
    if not check_api_rate_limit(ip): return "Too Many Requests", 429
    if request.method == 'OPTIONS': return make_response("ok", 200)
    
    data = request.json or {}
    if not verify_request_signature(data): return "Invalid Signature", 403
        
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
                v_count = kd["violations"]
                if v_count == 1:
                    kd["temp_ban_until"] = now + (30 * 60 * 1000)
                    log_admin_action(db, f"CẢNH CÁO 1 (30 Phút) Key {key} vì Share IP")
                elif v_count == 2:
                    kd["temp_ban_until"] = now + (12 * 3600 * 1000)
                    log_admin_action(db, f"CẢNH CÁO 2 (12 Giờ) Key {key} vì Share IP")
                else:
                    kd["status"] = "banned"
                    log_admin_action(db, f"TỬ HÌNH Vĩnh Viễn Key {key} vì Share IP")
                kd["known_ips"] = {}
                save_db(db)
                return "Banned for sharing", 403
            active_sessions[key] = {"ip": ip, "key": key, "last_seen": time.time()}
            return "ok", 200
    return "invalid", 403

# ========================================================
# LOADER DYNAMIC (CÀI 1 LẦN VÀO VIOLENTMONKEY)
# ========================================================
@app.route('/api/script/lvt_vip_loader.user.js')
def serve_dynamic_script():
    js_code = f"""// ==UserScript==
// @name         LVT TOOL VIP LOADER (SECURE MODE)
// @namespace    http://tampermonkey.net/
// @version      2.0
// @description  Hệ thống cầu nối tải ngầm Script VIP LVT.
// @author       DEV.TIỆP
// @match        *://*/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @run-at       document-start
// ==/UserScript==

(function() {{
    'use strict';
    const SERVER_URL = "{WEB_URL}"; 
    let savedKey = GM_getValue('lvt_tool_key', '');
    
    function generateHWID() {{
        let n = navigator.userAgent + screen.width + screen.height;
        let hash = 0;
        for(let i=0; i<n.length; i++) {{ hash = ((hash<<5)-hash)+n.charCodeAt(i); hash = hash & hash; }}
        return "HW-" + Math.abs(hash).toString(16).toUpperCase();
    }}
    let deviceId = localStorage.getItem('lvt_dev_id') || generateHWID();
    localStorage.setItem('lvt_dev_id', deviceId);

    async function secureFetch(path, bodyObj) {{
        let ts = Date.now();
        let msg = bodyObj.key + ts + bodyObj.key;
        let encoder = new TextEncoder();
        let data = encoder.encode(msg);
        let hashBuffer = await crypto.subtle.digest('SHA-256', data);
        let hashArray = Array.from(new Uint8Array(hashBuffer));
        let sig = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        bodyObj.timestamp = ts; bodyObj.signature = sig;
        return new Promise((resolve, reject) => {{
            GM_xmlhttpRequest({{
                method: 'POST', url: SERVER_URL + path, headers: {{ 'Content-Type': 'application/json' }},
                data: JSON.stringify(bodyObj), onload: (r) => resolve(JSON.parse(r.responseText)), onerror: (e) => reject(e)
            }});
        }});
    }}

    function showAuthUI(errorMsg = "") {{
        if(document.getElementById('lvt-auth-box')) return;
        const box = document.createElement('div'); box.id = 'lvt-auth-box';
        box.style.cssText = "position:fixed;inset:0;background:rgba(0,5,10,0.95);z-index:9999999;display:flex;align-items:center;justify-content:center;font-family:monospace;";
        box.innerHTML = `
            <div style="background:#0a0a1a;border:2px solid #00ffcc;padding:40px;border-radius:15px;text-align:center;box-shadow:0 0 40px rgba(0,255,204,0.3);width:350px;">
                <h2 style="color:#00ffcc;margin-top:0;">⚡ LVT TOOL VIP ⚡</h2>
                <p style="color:#aaa;font-size:13px;margin-bottom:20px;">Hệ thống bảo mật chống Crack</p>
                <input type="text" id="lvt-inp" placeholder="NHẬP LICENSE KEY..." style="width:100%;padding:15px;background:#000;border:1px solid #00ffcc;color:#fff;text-align:center;margin-bottom:15px;border-radius:8px;outline:none;">
                <button id="lvt-btn" style="width:100%;padding:15px;background:#00ffcc;color:#000;font-weight:bold;font-size:16px;border:none;border-radius:8px;cursor:pointer;">KÍCH HOẠT HỆ THỐNG</button>
                <div id="lvt-err" style="color:#ff4444;margin-top:15px;font-weight:bold;">${{errorMsg}}</div>
            </div>`;
        document.documentElement.appendChild(box);
        document.getElementById('lvt-btn').onclick = async function() {{
            const k = document.getElementById('lvt-inp').value.trim();
            if(!k) return;
            this.innerText = "ĐANG XÁC THỰC..."; this.disabled = true;
            try {{
                let res = await secureFetch('/api/check', {{ key: k, deviceId: deviceId }});
                if(res.status === 'success') {{
                    GM_setValue('lvt_tool_key', k); box.remove(); loadCore(k);
                }} else {{
                    document.getElementById('lvt-err').innerText = "❌ " + res.message;
                    this.innerText = "KÍCH HOẠT HỆ THỐNG"; this.disabled = false;
                }}
            }} catch(e) {{
                document.getElementById('lvt-err').innerText = "❌ Lỗi kết nối Server!";
                this.innerText = "KÍCH HOẠT HỆ THỐNG"; this.disabled = false;
            }}
        }};
    }}

    async function loadCore(key) {{
        try {{
            let res = await secureFetch('/api/core', {{ key: key, deviceId: deviceId }});
            if(res.status === 'success' && res.payload) {{
                let reversed = res.payload.split('').reverse().join('');
                let decodedCore = decodeURIComponent(escape(window.atob(reversed)));
                // TIÊM SCRIPT CỦA USER VÀO TRANG
                let s = document.createElement('script'); s.textContent = decodedCore;
                document.documentElement.appendChild(s); s.remove();
                setInterval(() => {{ secureFetch('/api/script_ping', {{ key: key }}); }}, 30000);
            }} else {{ showAuthUI("Lỗi kéo dữ liệu Core!"); }}
        }} catch(e) {{ showAuthUI("Không thể tải Core Module!"); }}
    }}

    if(!savedKey) {{ window.addEventListener('DOMContentLoaded', () => showAuthUI()); }} 
    else {{
        secureFetch('/api/check', {{ key: savedKey, deviceId: deviceId }}).then(res => {{
            if(res.status === 'success') {{ if(res.loader_enabled) loadCore(savedKey); }} 
            else {{ GM_setValue('lvt_tool_key', ''); window.addEventListener('DOMContentLoaded', () => showAuthUI(res.message)); }}
        }}).catch(e => console.log(e));
    }}
}})();
"""
    resp = make_response(js_code)
    resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    return resp

# ========================================================
# GIAO DIỆN KHÁCH HÀNG (TRANG CHỦ / SHOP)
# ========================================================
CSS_GLASS = """
body { background: #05050A; color: #fff; font-family: 'Segoe UI', Tahoma, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin:0;}
.glass-panel { background: rgba(20, 25, 35, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(0, 255, 204, 0.3); border-radius: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.8); padding: 40px; text-align: center; width: 100%; max-width: 400px; }
h2 { color: #00ffcc; font-weight: 900; letter-spacing: 1px; margin-bottom: 30px; text-shadow: 0 0 15px rgba(0,255,204,0.5); }
.form-control { background: rgba(0,0,0,0.5) !important; border: 1px solid #333 !important; color: #fff !important; padding: 12px; border-radius: 8px; margin-bottom: 15px; }
.form-control:focus { border-color: #00ffcc !important; box-shadow: 0 0 10px rgba(0,255,204,0.3) !important; }
.btn-neon { background: linear-gradient(45deg, #00ffcc, #bd00ff); border: none; color: #000; font-weight: bold; width: 100%; padding: 12px; border-radius: 8px; transition: 0.3s; margin-top: 10px; }
.btn-neon:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(0,255,204,0.4); }
a.link-neon { color: #bd00ff; text-decoration: none; font-weight: bold; transition: 0.3s; }
a.link-neon:hover { color: #00ffcc; text-shadow: 0 0 10px #00ffcc; }
"""

@app.route('/')
def home():
    shop_html = ""
    for pkg_id, pkg in SHOP_PACKAGES.items():
        if pkg_id == "30D":
            shop_html += f'<div class="col-md-3"><div class="pkg-card" style="border-color:#bd00ff;box-shadow:0 0 20px rgba(189,0,255,0.2);"><div class="badge bg-danger mb-2">HOT NHẤT</div><h3 class="text-white">{pkg["name"]}</h3><div class="price text-info">{pkg["price"]:,}đ</div><p class="text-secondary">Chiến game dài hạn<br>Hỗ trợ 1 thiết bị</p><a href="/login" class="btn btn-info w-100 mt-3 fw-bold">MUA NGAY</a></div></div>'
        else:
            shop_html += f'<div class="col-md-3"><div class="pkg-card"><h3 class="text-white">{pkg["name"]}</h3><div class="price">{pkg["price"]:,}đ</div><p class="text-secondary">Bảo mật đa tầng<br>Hỗ trợ 1 thiết bị</p><a href="/login" class="btn btn-outline-light w-100 mt-3">MUA NGAY</a></div></div>'

    return f'''
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>LVT TOOL - Trang Chủ</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>body{{background:#05050A;color:#fff;font-family:'Segoe UI',sans-serif;}} .hero{{background:linear-gradient(135deg,#000,#0a192f);padding:100px 0;text-align:center;border-bottom:1px solid #00ffcc;}} .neon-text{{color:#00ffcc;text-shadow:0 0 10px #00ffcc;}} .pkg-card{{background:#11111A;border:1px solid #333;border-radius:15px;padding:30px;text-align:center;transition:0.3s;height:100%;}} .pkg-card:hover{{border-color:#00ffcc;box-shadow:0 0 20px rgba(0,255,204,0.2);transform:translateY(-10px);}} .price{{font-size:35px;font-weight:900;color:#bd00ff;margin:20px 0;}}</style></head><body>
    <div class="hero">
        <h1 class="neon-text fw-bold mb-3">⚡ HỆ THỐNG LVT TOOL VIP ⚡</h1>
        <p class="text-secondary fs-5 mb-4">Công cụ tự động hóa thông minh - Bảo mật đa tầng - Tự chỉnh Script theo ý muốn</p>
        <a href="#shop" class="btn btn-lg fw-bold" style="background:#00ffcc;color:#000;">XEM BẢNG GIÁ</a>
        <a href="/login" class="btn btn-outline-info btn-lg fw-bold ms-2">ĐĂNG NHẬP</a>
    </div>
    <div class="container py-5" id="shop">
        <h2 class="text-center neon-text fw-bold mb-5">BẢNG GIÁ DỊCH VỤ</h2>
        <div class="row g-4 justify-content-center">{shop_html}</div>
    </div>
    <footer class="text-center text-secondary py-4 border-top border-dark">© 2026 LVT SECURE SYSTEM. Chạy ngầm đỉnh cao.</footer>
    </body></html>
    '''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session: 
        if session.get('role') == 'admin': return redirect('/admin')
        return redirect('/dashboard')
    
    global login_attempts
    ip = get_real_ip()
    now = time.time()
    attempts = [t for t in login_attempts.get(ip, []) if now - t < 600]
    
    if len(attempts) >= 5:
        db = load_db()
        with db_lock:
            if ip not in db.setdefault("banned_ips", []):
                db["banned_ips"].append(ip)
                report_bad_signature(ip)
                save_db(db)
        return swal_redirect("FIREWALL CẢNH BÁO", "Bạn đã bị khóa IP vì dò mật khẩu quá 5 lần!", "error", "/")

    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '').strip()
        
        db = load_db()
        user_data = db.get("users", {}).get(username)
        
        if user_data and user_data.get("password_hash") == hash_pwd(password):
            session['username'] = username
            session['role'] = user_data.get("role", "user")
            
            with db_lock:
                if ip not in db["users"][username].setdefault("ips", []):
                    db["users"][username]["ips"].append(ip)
                save_db(db)
                
            if ip in login_attempts: del login_attempts[ip]
            return swal_redirect("Đăng nhập thành công!", f"Chào mừng {username.upper()} quay trở lại.", "success", "/dashboard" if session['role'] != 'admin' else "/admin")
        else:
            attempts.append(now)
            login_attempts[ip] = attempts
            return swal_redirect("Đăng nhập thất bại!", f"Sai tài khoản hoặc mật khẩu.<br><small>Cảnh cáo: Lần thứ {len(attempts)}/5</small>", "error", "/login")

    return f'''
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Đăng Nhập</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>{CSS_GLASS}</style></head>
    <body><div class="glass-panel"><h2>⚡ ĐĂNG NHẬP</h2>
    <form method="POST">
        <input type="text" name="username" class="form-control" placeholder="Tên đăng nhập" required>
        <input type="password" name="password" class="form-control" placeholder="Mật khẩu" required>
        <button type="submit" class="btn btn-neon">VÀO BẢNG ĐIỀU KHIỂN</button>
    </form>
    <div class="mt-4"><p class="text-secondary">Chưa có tài khoản? <a href="/register" class="link-neon">Đăng ký ngay</a></p></div>
    </div></body></html>
    '''

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session: return redirect('/')
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '').strip()
        
        if not username.isalnum() or len(username) < 4:
            return swal_redirect("Lỗi Đăng Ký", "Tên đăng nhập phải > 4 ký tự và không có dấu!", "warning", "/register")
        if len(password) < 6:
            return swal_redirect("Lỗi Đăng Ký", "Mật khẩu phải từ 6 ký tự trở lên!", "warning", "/register")

        db = load_db()
        with db_lock:
            if username in db.setdefault("users", {}):
                return swal_redirect("Lỗi Đăng Ký", "Tên đăng nhập này đã có người sử dụng!", "error", "/register")
            
            db["users"][username] = {
                "password_hash": hash_pwd(password), "role": "user", "balance": 0,
                "created_at": int(time.time() * 1000), "ips": [get_real_ip()],
                "purchased_keys": [], "notices": [], "custom_script": ""
            }
            save_db(db)
        return swal_redirect("Tuyệt vời!", "Tạo tài khoản thành công. Hãy đăng nhập!", "success", "/login")

    return f'''
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Đăng Ký</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>{CSS_GLASS}</style></head>
    <body><div class="glass-panel"><h2>⚡ TẠO TÀI KHOẢN</h2>
    <form method="POST">
        <input type="text" name="username" class="form-control" placeholder="Tên đăng nhập (viết liền không dấu)" required>
        <input type="password" name="password" class="form-control" placeholder="Mật khẩu (Tối thiểu 6 ký tự)" required>
        <button type="submit" class="btn btn-neon">ĐĂNG KÝ NGAY</button>
    </form>
    <div class="mt-4"><p class="text-secondary">Đã có tài khoản? <a href="/login" class="link-neon">Đăng nhập</a></p></div>
    </div></body></html>
    '''

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ========================================================
# GIAO DIỆN USER (MUA KEY + QUẢN LÝ KEY + ĐỔI SCRIPT)
# ========================================================
@app.route('/dashboard')
def user_dashboard():
    if 'username' not in session or session.get('role') != 'user': return redirect('/login')
    
    username = session['username']
    db = load_db()
    user_data = db["users"].get(username, {})
    balance = user_data.get("balance", 0)
    owned_keys = user_data.get("purchased_keys", [])
    user_script = user_data.get("custom_script", "")
    
    # Xử lý thông báo (Notice) từ Admin
    notices = user_data.get("notices", [])
    swal_scripts = ""
    if notices:
        msg = "<br>".join(notices)
        swal_scripts = f"Swal.fire({{title: 'TING TING 💰', html: '{msg}', icon: 'success', background: '#11111A', color: '#00ffcc'}});"
        with db_lock:
            db["users"][username]["notices"] = []
            save_db(db)

    keys_html = ""
    if not owned_keys:
        keys_html = "<tr><td colspan='4' class='text-center text-muted py-3'>Bạn chưa mua Key nào. Hãy mua ngay ở Cửa Hàng!</td></tr>"
    else:
        for k_obj in owned_keys:
            k = k_obj["key"]
            kd = db["keys"].get(k)
            if not kd: continue
            
            status = kd.get("status")
            badge = '<span class="badge bg-success">Hoạt động</span>'
            if status == "banned": badge = '<span class="badge bg-danger">Bị Khóa</span>'
            
            exp_time = kd.get("exp", 0)
            if exp_time == "pending": exp_str = "Chưa kích hoạt"
            elif exp_time == "permanent": exp_str = "Vĩnh viễn"
            else:
                if int(time.time()*1000) > exp_time: badge = '<span class="badge bg-secondary">Hết hạn</span>'
                exp_str = time.strftime("%H:%M %d/%m/%Y", time.localtime(exp_time/1000))
            
            devs = len(kd.get("devices", []))
            max_devs = kd.get("maxDevices", 1)
            
            keys_html += f"<tr><td><strong class='text-info'>{k}</strong> <button class='btn btn-sm btn-outline-info border-0' onclick='copyText(\"{k}\")'>📋</button></td><td>{badge}</td><td>{exp_str}</td><td>{devs}/{max_devs}</td></tr>"

    shop_html = ""
    for pkg_id, pkg in SHOP_PACKAGES.items():
        shop_html += f'''
        <div class="col-md-3 col-6">
            <div class="card bg-dark border-secondary text-center p-3 h-100" style="transition:0.3s;" onmouseover="this.style.borderColor='#00ffcc'" onmouseout="this.style.borderColor='#6c757d'">
                <h5 class="text-white fw-bold">{pkg['name']}</h5>
                <h4 style="color:#bd00ff; font-weight:900;">{pkg['price']:,}đ</h4>
                <form action="/buy" method="POST" class="mt-auto pt-3">
                    <input type="hidden" name="pkg_id" value="{pkg_id}">
                    <button type="submit" class="btn btn-sm w-100 fw-bold" style="background:#00ffcc; color:#000;">MUA NGAY</button>
                </form>
            </div>
        </div>'''

    return f'''
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Dashboard - User</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <style>body{{background:#05050A;color:#e0e0e0;font-family:'Segoe UI',sans-serif;}} .card{{background:#11111A;border-radius:15px;}}</style></head>
    <body class="p-3">
    <div class="container" style="max-width:1100px;">
        <div class="d-flex justify-content-between align-items-center mb-4 border-bottom border-secondary pb-3">
            <h2 style="color:#00ffcc; font-weight:900;">⚡ LVT VIP DASHBOARD</h2>
            <div><span class="me-3">Xin chào, <b class="text-info">{username.upper()}</b></span> <a href="/logout" class="btn btn-sm btn-outline-danger">Thoát</a></div>
        </div>
        
        <div class="row g-4">
            <div class="col-md-4">
                <div class="card p-4 text-center border-info h-100">
                    <h5 class="text-secondary">SỐ DƯ CỦA BẠN</h5>
                    <h2 style="color:#00ffcc; font-weight:900; font-size:40px;">{balance:,}<small style="font-size:20px;">đ</small></h2>
                    <hr class="border-secondary">
                    <p class="text-warning mb-1" style="font-size:14px;"><i class="fas fa-university"></i> <b>CÁCH NẠP TIỀN AUTO</b></p>
                    <p class="text-muted" style="font-size:12px;">Vui lòng chuyển khoản với nội dung:<br><strong class="text-white fs-6">NAP {username.upper()}</strong></p>
                    <a href="https://zalo.me/123456789" target="_blank" class="btn btn-outline-info btn-sm fw-bold">Liên hệ Admin (Zalo)</a>
                </div>
            </div>
            
            <div class="col-md-8">
                <div class="card p-4 border-info h-100">
                    <h4 class="text-info fw-bold mb-3"><i class="fas fa-rocket"></i> TRUNG TÂM KÍCH HOẠT HACK</h4>
                    <p class="text-muted mb-2" style="font-size:12px;">*Chú ý: Bạn cần <a href="/api/script/lvt_vip_loader.user.js" class="text-warning fw-bold">Cài đặt Loader Cầu Nối</a> vào Violentmonkey 1 lần duy nhất trước khi dùng.</p>
                    <div class="row g-3 h-100">
                        <div class="col-md-6">
                            <div class="p-3 border border-secondary rounded text-center h-100 d-flex flex-column justify-content-center">
                                <h5 class="text-warning fw-bold">NÚT 1: TÙY CHỈNH SCRIPT</h5>
                                <p class="text-muted" style="font-size:12px;">Chèn Script Hack OLM của riêng bạn vào hệ thống Server.</p>
                                <button class="btn btn-warning fw-bold w-100 mt-auto text-dark" data-bs-toggle="modal" data-bs-target="#scriptModal"><i class="fas fa-code"></i> SỬA ĐỔI SCRIPT CỦA TÔI</button>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="p-3 border border-success rounded text-center h-100 d-flex flex-column justify-content-center">
                                <h5 class="text-success fw-bold">NÚT 2: VÀO HACK NGAY</h5>
                                <p class="text-muted" style="font-size:12px;">Hệ thống sẽ tự động chuyển sang OLM và bơm thẳng Script mà bạn đã cài ở Nút 1.</p>
                                <a href="https://olm.vn" target="_blank" class="btn btn-success fw-bold w-100 mt-auto"><i class="fas fa-play"></i> MỞ OLM & AUTO BƠM SCRIPT</a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-12">
                <div class="card p-4 border-secondary">
                    <h4 style="color:#bd00ff; font-weight:900; margin-bottom:20px;"><i class="fas fa-shopping-cart"></i> MUA KEY TỰ ĐỘNG</h4>
                    <div class="row g-3">{shop_html}</div>
                </div>
            </div>
            
            <div class="col-12">
                <div class="card p-4 border-success">
                    <h4 style="color:#00ffcc; font-weight:900; margin-bottom:20px;"><i class="fas fa-key"></i> DANH SÁCH KEY ĐÃ MUA</h4>
                    <div class="table-responsive">
                        <table class="table table-dark table-hover table-sm align-middle text-center">
                            <thead class="table-active"><tr><th>🔑 Mã Key (Copy)</th><th>Trạng thái</th><th>Hạn Sử Dụng</th><th>Máy / Tối đa</th></tr></thead>
                            <tbody>{keys_html}</tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="scriptModal" tabindex="-1" data-bs-theme="dark">
      <div class="modal-dialog modal-lg modal-dialog-centered">
        <div class="modal-content" style="background:#11111A; border:1px solid #00ffcc;">
          <div class="modal-header border-secondary">
            <h5 class="modal-title" style="color:#00ffcc;font-weight:bold;">🛠️ TÙY CHỈNH MÃ NGUỒN SCRIPT</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <form action="/update_script" method="POST">
              <div class="modal-body">
                <p class="text-muted" style="font-size:13px;">Hãy dán đoạn code Javascript (Hack OLM) của bạn vào đây. Khi bạn bấm Nút 2, Server sẽ lập tức băm nhuyễn và truyền ngầm đoạn code này thẳng vào OLM.</p>
                <textarea name="script_content" class="form-control bg-dark text-light border-info" rows="12" style="font-family:monospace; font-size:12px;" placeholder="Dán mã Script OLM vào đây...">{escape(user_script)}</textarea>
              </div>
              <div class="modal-footer border-secondary">
                <button type="submit" class="btn btn-info fw-bold w-100 text-dark">💾 LƯU SCRIPT LÊN ĐÁM MÂY</button>
              </div>
          </form>
        </div>
      </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        {swal_scripts}
        function copyText(text) {{
            navigator.clipboard.writeText(text);
            Swal.fire({{toast:true, position:'top-end', icon:'success', title:'Đã copy: '+text, showConfirmButton:false, timer:2000, background:'#111', color:'#fff'}});
        }}
    </script>
    </body></html>
    '''

@app.route('/update_script', methods=['POST'])
def update_user_script():
    if 'username' not in session: return redirect('/login')
    new_script = request.form.get('script_content', '')
    
    db = load_db()
    with db_lock:
        if session['username'] in db["users"]:
            db["users"][session['username']]["custom_script"] = new_script
            save_db(db)
            
    return swal_redirect("Đã lưu Script!", "Hệ thống sẽ tự động bơm script này khi bạn vào OLM.", "success", "/dashboard")

@app.route('/buy', methods=['POST'])
def buy_key():
    if 'username' not in session or session.get('role') != 'user': return redirect('/login')
    username = session['username']
    pkg_id = request.form.get('pkg_id')
    
    if pkg_id not in SHOP_PACKAGES: return swal_redirect("Lỗi Hệ Thống", "Gói này không tồn tại!", "error", "/dashboard")
    
    pkg = SHOP_PACKAGES[pkg_id]
    price = pkg['price']
    
    db = load_db()
    with db_lock:
        user_data = db["users"].get(username)
        if user_data['balance'] < price:
            return swal_redirect("Số Dư Không Đủ!", "Bạn cần nạp thêm tiền để mua gói này.", "warning", "/dashboard")
        
        # Trừ tiền
        user_data['balance'] -= price
        
        # Tạo key siêu bảo mật gắn với Tên Chủ Sở Hữu (owner)
        nk = generate_secure_key("TOOL")
        db["keys"][nk] = {
            "exp": "pending", "durationMs": pkg['dur_ms'], "maxDevices": 1, 
            "devices": [], "known_ips": {}, "status": "active", "vip": True, 
            "loader_enabled": True, "violations": 0, "temp_ban_until": 0,
            "owner": username
        }
        
        # Thêm vào túi đồ user
        user_data.setdefault("purchased_keys", []).insert(0, {
            "key": nk, "package_name": pkg['name'], "buy_time": int(time.time() * 1000)
        })
        save_db(db)
        
    html_msg = f"""
    <div style='text-align:left; font-size:15px;'>
        <p>Gói: <b style='color:#bd00ff'>{pkg['name']}</b></p>
        <p>Mã Key của bạn:</p>
        <div style='background:#000; padding:10px; border:1px dashed #00ffcc; border-radius:5px; text-align:center; font-family:monospace; font-size:18px; color:#00ffcc; margin-bottom:15px;'>
            {nk}
        </div>
        <p style='color:#aaa; font-size:12px;'>*Ghi nhớ mã Key. Key sẽ tự động kích hoạt trừ giờ vào lần đầu tiên bạn sử dụng Spoofer.</p>
    </div>
    """
    return swal_redirect("🎉 MUA KEY THÀNH CÔNG!", html_msg, "success", "/dashboard")

# ========================================================
# GIAO DIỆN WEB ADMIN QUẢN LÝ
# ========================================================
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    global login_attempts
    if request.method == 'POST':
        ip = get_real_ip()
        now = time.time()
        attempts = [t for t in login_attempts.get(ip, []) if now - t < 600] 
        
        if len(attempts) >= 4: 
            db = load_db()
            with db_lock:
                if ip not in db.setdefault("banned_ips", []):
                    db["banned_ips"].append(ip)
                    report_bad_signature(ip) 
                    save_db(db)
            return swal_redirect("FIREWALL BLOCK", "IP này đã bị khóa do cố tình xâm nhập Admin!", "error", "/")
        
        db = load_db()
        username = request.form.get('username', '').strip().lower()
        pwd = request.form.get('password', '').strip()
        
        u_data = db.get("users", {}).get(username)
        if u_data and u_data.get("role") == "admin" and u_data.get("password_hash") == hash_pwd(pwd):
            session['username'] = username
            session['role'] = 'admin'
            session['admin_auth'] = True 
            session['admin_ip'] = ip 
            with db_lock: log_admin_action(db, f"Đăng nhập Admin thành công từ IP: {ip}")
            save_db(db)
            if ip in login_attempts: del login_attempts[ip]
            return redirect('/admin')
            
        attempts.append(now)
        login_attempts[ip] = attempts
        return swal_redirect("Từ Chối Truy Cập", f"Thông tin Admin không chính xác!<br>Cảnh cáo: {len(attempts)}/5", "error", "/admin_login")
    
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
        ips = "<br>".join(udata.get("ips", [])) or "Chưa có"
        keys_count = len(udata.get("purchased_keys", []))
        created = time.strftime("%d/%m/%y", time.localtime(udata.get("created_at", 0)/1000))
        
        users_html += f'''
        <tr>
            <td><strong class="text-warning">{escape(uname)}</strong><br><small class="text-muted">{created}</small></td>
            <td><span class="badge bg-success" style="font-size:13px;">{bal:,}đ</span></td>
            <td><span class="badge bg-info text-dark">{keys_count} Keys</span></td>
            <td style="font-size:10px; color:#aaa;">{ips}</td>
            <td>
                <form action="/admin/add_balance" method="POST" class="d-flex gap-1">
                    <input type="hidden" name="username" value="{escape(uname)}">
                    <input type="number" name="amount" class="form-control form-control-sm bg-dark text-light border-secondary px-1" style="width:75px;font-size:12px;" placeholder="± Tiền" required>
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

        keys_html += f'''
        <tr class="key-row">
            <td><strong class="text-info" style="font-size:13px;">{safe_k}</strong><br>{vip_badge} {status_badge}<br><small class="text-warning">Chủ: {owner}</small></td>
            <td style="font-size:12px;">{exp_text}</td>
            <td><span class="badge bg-info text-dark">{len(devs)}/{data.get('maxDevices', 1)}</span></td>
            <td>
                <div class="btn-group btn-group-sm">
                    <a href="/admin/action/reset-dev/{safe_k}" class="btn btn-primary" style="font-size:10px;">🔄 HWID</a>
                    <a href="/admin/action/unban_temp/{safe_k}" class="btn btn-success" style="font-size:10px;">Gỡ Phạt</a>
                    <a href="/admin/action/{"unban" if is_banned else "ban"}/{safe_k}" class="btn btn-{"light" if is_banned else "danger"}" style="font-size:10px;">{"Cứu" if is_banned else "Trảm"}</a>
                    <a href="/admin/action/delete/{safe_k}" class="btn btn-dark" onclick="return confirm('Xóa vĩnh viễn Key này?')" style="font-size:10px;">🗑️</a>
                </div>
            </td>
        </tr>'''

    blacklist_rows = "".join([f'<li class="list-group-item bg-dark text-light d-flex justify-content-between align-items-center" style="font-size:12px;">{escape(ip)} <a href="/admin/unban_ip/{escape(ip)}" class="btn btn-sm btn-danger p-0 px-2">Gỡ</a></li>' for ip in banned_ips])
    if not blacklist_rows: blacklist_rows = '<li class="list-group-item bg-dark text-muted text-center" style="font-size:12px;">Sạch sẽ</li>'
    
    logs_html = "".join([f'<li class="list-group-item bg-dark text-light border-secondary p-1 mb-1 rounded" style="font-size:11px;"><span class="text-warning">[{time.strftime("%H:%M", time.localtime(alog.get("time", 0)/1000))}]</span> {escape(alog.get("action", ""))}</li>' for alog in admin_logs[:15]])

    return f'''
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ADMIN DASHBOARD</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>body{{background:#05050A;color:#e0e0e0;font-family:'Segoe UI',sans-serif;font-size:14px;}} .card{{background:#11111A;border:1px solid #333;border-radius:12px;}} h5{{color:#00ffcc;font-weight:900;}} .table-container{{max-height:450px;overflow-y:auto;}} tbody tr:hover{{background:rgba(0,255,204,0.05)!important;}}</style>
    </head><body class="p-2">
    <div class="container-fluid">
        <div class="d-flex justify-content-between align-items-center mb-3 border-bottom border-secondary pb-2">
            <h3 class="m-0" style="color:#00ffcc; font-weight:900;">⚡ LVT SECURE ADMIN</h3>
            <div><span class="me-3 d-none d-md-inline">Admin: <b>{session.get('username','').upper()}</b></span><a href="/logout" class="btn btn-outline-danger btn-sm fw-bold">Thoát</a></div>
        </div>
        
        <div class="row g-3">
            <div class="col-lg-6">
                <div class="card p-3 h-100" style="border-color:#3366ff;">
                    <h5 style="color:#3366ff;"><i class="fas fa-users"></i> DANH SÁCH NGƯỜI DÙNG</h5>
                    <div class="table-container">
                        <table class="table table-dark table-hover table-sm align-middle mb-0 text-center">
                            <thead class="table-active"><tr><th>Tài Khoản</th><th>Số Dư</th><th>Tài sản</th><th>IP Log</th><th>Nạp Tiền</th></tr></thead>
                            <tbody>{users_html}</tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="col-lg-6">
                <div class="row g-3 h-100">
                    <div class="col-md-6">
                        <div class="card p-3 h-100" style="border-color:#bd00ff;">
                            <h5 style="color:#bd00ff;"><i class="fas fa-key"></i> TẠO KEY MỚI</h5>
                            <form action="/admin/create" method="POST" class="row g-2 mt-1">
                                <div class="col-6"><input type="text" name="prefix" class="form-control form-control-sm bg-dark text-light border-secondary" placeholder="Tiền tố (T)"></div>
                                <div class="col-6"><input type="number" name="quantity" class="form-control form-control-sm bg-dark text-light border-secondary" value="1" placeholder="Số Lượng"></div>
                                <div class="col-6"><input type="number" name="duration" class="form-control form-control-sm bg-dark text-light border-secondary" placeholder="Độ dài" required></div>
                                <div class="col-6"><select name="type" class="form-select form-select-sm bg-dark text-light border-secondary"><option value="hour">Giờ</option><option value="day" selected>Ngày</option><option value="month">Tháng</option><option value="permanent">V.Viễn</option></select></div>
                                <div class="col-12 mt-2"><button type="submit" class="btn btn-sm w-100 fw-bold" style="background:#bd00ff;color:white;">🚀 TẠO NGAY</button></div>
                            </form>
                            
                            <hr class="border-secondary my-3">
                            <h5 style="color:#ff9900;"><i class="fas fa-code"></i> SET MÃ NGUỒN CHUNG</h5>
                            <button class="btn btn-sm btn-outline-warning w-100 fw-bold" data-bs-toggle="modal" data-bs-target="#adminScriptModal">Sửa Code Mặc Định</button>
                        </div>
                    </div>
                    <div class="col-md-6">
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
                        <h5 class="m-0"><i class="fas fa-database"></i> TẤT CẢ MÃ KEY</h5>
                        <input type="text" id="searchInput" class="form-control form-control-sm bg-dark text-light border-info" style="width:200px;" placeholder="🔍 Tìm mã Key / Tên..." onkeyup="let s=this.value.toLowerCase();document.querySelectorAll('.key-row').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(s)?'':'none');">
                    </div>
                    <div class="table-container">
                        <table class="table table-dark table-sm align-middle table-hover text-center">
                            <thead class="table-active"><tr><th>🔑 Mã Key / Chủ</th><th>⏳ Hạn Dùng</th><th>💻 Thiết bị</th><th>⚙️ Thao tác</th></tr></thead>
                            <tbody>{keys_html}</tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="adminScriptModal" tabindex="-1" data-bs-theme="dark">
      <div class="modal-dialog modal-lg modal-dialog-centered">
        <div class="modal-content" style="background:#11111A; border:1px solid #ff9900;">
          <div class="modal-header border-secondary">
            <h5 class="modal-title" style="color:#ff9900;font-weight:bold;">TÙY CHỈNH MÃ NGUỒN CHUNG (FALLBACK)</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <form action="/update_script" method="POST">
              <div class="modal-body">
                <p class="text-muted" style="font-size:13px;">Đoạn script này sẽ được tự động tiêm cho những khách hàng <b>không tự thiết lập Script riêng</b>.</p>
                <textarea name="script_content" class="form-control bg-dark text-light border-warning" rows="12" style="font-family:monospace; font-size:12px;">{escape(db.get("users", {{}}).get("admin", {{}}).get("custom_script", ""))}</textarea>
              </div>
              <div class="modal-footer border-secondary">
                <button type="submit" class="btn btn-warning fw-bold w-100 text-dark">LƯU CÀI ĐẶT</button>
              </div>
          </form>
        </div>
      </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body></html>
    '''

# ========================================================
# CÁC ROUTE CHỨC NĂNG CỦA ADMIN
# ========================================================
@app.route('/admin/add_balance', methods=['POST'])
def add_balance():
    if session.get('role') != 'admin': return redirect('/login')
    username = request.form.get('username')
    try: amt = int(request.form.get('amount', 0))
    except: amt = 0
    
    db = load_db()
    with db_lock:
        if username in db.get("users", {}):
            db["users"][username]["balance"] += amt
            if db["users"][username]["balance"] < 0: db["users"][username]["balance"] = 0
            
            # Gửi Notification cho user
            if amt > 0: db["users"][username].setdefault("notices", []).append(f"Admin vừa nạp cho bạn +{amt:,}đ")
            elif amt < 0: db["users"][username].setdefault("notices", []).append(f"Admin vừa trừ của bạn {amt:,}đ")
            
            log_admin_action(db, f"Cộng/Trừ {amt}đ cho tài khoản {username}")
            save_db(db)
    return redirect('/admin')

@app.route('/admin/create', methods=['POST'])
def create_key():
    if session.get('role') != 'admin': return redirect('/login')
    dur = int(request.form.get('duration', 0))
    md = int(request.form.get('maxDevices', 1))
    qty = int(request.form.get('quantity', 1))
    t = request.form.get('type')
    vip = request.form.get('is_vip') == 'on'
    pfx = request.form.get('prefix', '').strip()
    
    db = load_db()
    with db_lock:
        for _ in range(qty):
            nk = generate_secure_key(pfx)
            db["keys"][nk] = {
                "exp": "pending", "maxDevices": md, "devices": [], 
                "known_ips": {}, "status": "active", "vip": vip, 
                "loader_enabled": True, "violations": 0, "temp_ban_until": 0,
                "owner": "admin"
            }
            if t != 'permanent': db["keys"][nk]["durationMs"] = dur * {"hour":3600000, "day":86400000, "month":2592000000}.get(t, 60000)
            else: db["keys"][nk]["exp"] = "permanent"
        log_admin_action(db, f"Tạo {qty} Key Tool mới ({dur} {t}) - Mác VIP: {vip}")
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
                log_admin_action(db, f"Chặn IP thủ công: {ip}")
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
