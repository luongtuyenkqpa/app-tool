import os, json, time, random, hashlib, threading, requests, shutil, base64, secrets, hmac, string
from urllib.parse import urlparse
from flask import Flask, request, jsonify, redirect, make_response, session, render_template_string

# [VÁ LỖI LỆCH MÚI GIỜ CLOUD]
try:
    os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
    time.tzset()
except: pass

app = Flask(__name__)

RAW_ADMIN_PASS = os.environ.get('ADMIN_PASSWORD', 'admin120510')
DEFAULT_ADMIN_PASSWORD_HASH = hashlib.sha256(RAW_ADMIN_PASS.encode()).hexdigest()

app.secret_key = os.environ.get('SECRET_KEY', hashlib.sha256(f"LVT_SECURE_{RAW_ADMIN_PASS}".encode()).hexdigest())

app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True

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
# [MÃ NGUỒN TOOL GỐC ĐƯỢC GIẤU TRÊN SERVER]
# ========================================================
# Bạn viết Code Tool (Hack) thực sự của bạn vào biến này.
# Nó sẽ được Server mã hoá và gửi ngầm cho khách khi kiểm tra Key thành công.
TOOL_CORE_SCRIPT = """
console.log("🔥 [LVT SPOOFER] KẾT NỐI SERVER THÀNH CÔNG!");
console.log("🔥 MÃ NGUỒN CHÍNH ĐÃ ĐƯỢC GIẢI MÃ VÀ TIÊM VÀO TRANG.");

// VIẾT CODE HACK/TOOL CỦA BẠN Ở ĐÂY...
// Ví dụ:
// document.body.style.background = 'black';
// alert("TOOL VIP KÍCH HOẠT!");
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
        if session.get('admin_auth'):
            if session.get('admin_ip') and session.get('admin_ip') != ip:
                session.clear()
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

# ========================================================
# DATABASE CORE
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
                data = {"keys": {}, "settings": {}, "security_alerts": [], "banned_ips": [], "admin_logs": []}
            try:
                data.setdefault("keys", {})
                data.setdefault("banned_ips", [])
                data.setdefault("admin_logs", [])
                data.setdefault("security_alerts", []) 
                data.setdefault("settings", {})["admin_password_hash"] = data.get("settings", {}).get("admin_password_hash", DEFAULT_ADMIN_PASSWORD_HASH)
                
                # Cập nhật cấu trúc key mới
                for k in data["keys"]:
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
            shutil.copy2(DB_FILE, DB_BACKUP) # Lưu luôn backup
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
    # Random 14 ký tự bảo mật, bỏ các ký tự dễ nhầm lẫn như I, l, O, 0
    safe_chars = ''.join([c for c in chars if c not in 'IlO0'])
    rand_str = ''.join(secrets.choice(safe_chars) for _ in range(14))
    if prefix: return f"{prefix}-{rand_str}"
    return rand_str

# ========================================================
# API TÀNG HÌNH (SPOOFER & CẤP PHÉP KEY TOOL)
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
        
        # Check Temp Ban (Phạt Share Key)
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

    # Nếu check thành công, cập nhật Last_seen
    with db_lock:
        active_sessions[key] = {"ip": ip, "key": key, "last_seen": time.time()}

    return jsonify({"status": "success", "loader_enabled": db["keys"][key].get("loader_enabled", True)})

@app.route('/api/core', methods=['POST', 'OPTIONS'])
def serve_core_payload():
    """Trả về MÃ NGUỒN CHÍNH (Đã bị băm nát và mã hoá) nếu có Key hợp lệ"""
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

    # MÃ HOÁ NGƯỢC CHUỖI BASE64 ĐỂ GỬI XUỐNG MÁY KHÁCH
    encoded_core = base64.b64encode(TOOL_CORE_SCRIPT.encode('utf-8')).decode('utf-8')
    reversed_core = encoded_core[::-1]

    return jsonify({"status": "success", "payload": reversed_core})

@app.route('/api/script_ping', methods=['POST', 'OPTIONS'])
def script_ping():
    """Nhịp tim từ Script gửi về để check Share Key (Spam IP)"""
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
            
            # Lọc IP cũ (Sau 2 phút không ping coi như offline)
            to_del = [i for i, t in known_ips.items() if now - t > 120000]
            for i in to_del: del known_ips[i]
            
            known_ips[ip] = now
            
            # --- LOGIC AUTO BAN THEO SỐ LẦN VI PHẠM ---
            if len(known_ips) > kd.get("maxDevices", 1):
                kd["violations"] = kd.get("violations", 0) + 1
                v_count = kd["violations"]
                
                if v_count == 1:
                    kd["temp_ban_until"] = now + (30 * 60 * 1000) # Khóa 30 phút
                    log_admin_action(db, f"CẢNH CÁO 1 (30 Phút) Key {key} vì chia sẻ (Quá IP)")
                elif v_count == 2:
                    kd["temp_ban_until"] = now + (12 * 3600 * 1000) # Khóa 12 tiếng
                    log_admin_action(db, f"CẢNH CÁO 2 (12 Giờ) Key {key} vì chia sẻ (Quá IP)")
                else:
                    kd["status"] = "banned" # Lần 3 Khóa Vĩnh Viễn
                    log_admin_action(db, f"TỬ HÌNH Vĩnh Viễn Key {key} vì chia sẻ nhiều lần")
                
                kd["known_ips"] = {} # Xóa list IP để tránh trigger liên tục
                save_db(db)
                return "Banned for sharing", 403
                
            active_sessions[key] = {"ip": ip, "key": key, "last_seen": time.time()}
            return "ok", 200
    return "invalid", 403

# ========================================================
# GIAO DIỆN LOADER DYNAMIC (SCRIPT CHO KHÁCH CÀI ĐẶT)
# ========================================================
@app.route('/api/script/lvt_vip_loader.user.js')
def serve_dynamic_script():
    js_code = f"""// ==UserScript==
// @name         LVT TOOL VIP LOADER (SECURE MODE)
// @namespace    http://tampermonkey.net/
// @version      2.0
// @description  Hệ thống bảo vệ và cấp phép tải ngầm Tool VIP LVT.
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
        
        bodyObj.timestamp = ts;
        bodyObj.signature = sig;
        
        return new Promise((resolve, reject) => {{
            GM_xmlhttpRequest({{
                method: 'POST',
                url: SERVER_URL + path,
                headers: {{ 'Content-Type': 'application/json' }},
                data: JSON.stringify(bodyObj),
                onload: (response) => resolve(JSON.parse(response.responseText)),
                onerror: (e) => reject(e)
            }});
        }});
    }}

    function showAuthUI(errorMsg = "") {{
        if(document.getElementById('lvt-auth-box')) return;
        const box = document.createElement('div');
        box.id = 'lvt-auth-box';
        box.style.cssText = "position:fixed;inset:0;background:rgba(0,5,10,0.95);z-index:9999999;display:flex;align-items:center;justify-content:center;font-family:monospace;";
        box.innerHTML = `
            <div style="background:#0a0a1a;border:2px solid #00ffcc;padding:40px;border-radius:15px;text-align:center;box-shadow:0 0 40px rgba(0,255,204,0.3);width:350px;">
                <h2 style="color:#00ffcc;margin-top:0;">⚡ LVT TOOL VIP ⚡</h2>
                <p style="color:#aaa;font-size:13px;margin-bottom:20px;">Hệ thống bảo mật chống Crack</p>
                <input type="text" id="lvt-inp" placeholder="NHẬP LICENSE KEY..." style="width:100%;padding:15px;background:#000;border:1px solid #00ffcc;color:#fff;text-align:center;margin-bottom:15px;border-radius:8px;outline:none;">
                <button id="lvt-btn" style="width:100%;padding:15px;background:#00ffcc;color:#000;font-weight:bold;font-size:16px;border:none;border-radius:8px;cursor:pointer;">KÍCH HOẠT HỆ THỐNG</button>
                <div id="lvt-err" style="color:#ff4444;margin-top:15px;font-weight:bold;">${{errorMsg}}</div>
            </div>
        `;
        document.documentElement.appendChild(box);
        
        document.getElementById('lvt-btn').onclick = async function() {{
            const k = document.getElementById('lvt-inp').value.trim();
            if(!k) return;
            this.innerText = "ĐANG XÁC THỰC...";
            this.disabled = true;
            try {{
                let res = await secureFetch('/api/check', {{ key: k, deviceId: deviceId }});
                if(res.status === 'success') {{
                    GM_setValue('lvt_tool_key', k);
                    box.remove();
                    loadCore(k);
                }} else {{
                    document.getElementById('lvt-err').innerText = "❌ " + res.message;
                    this.innerText = "KÍCH HOẠT HỆ THỐNG";
                    this.disabled = false;
                }}
            }} catch(e) {{
                document.getElementById('lvt-err').innerText = "❌ Lỗi kết nối Server!";
                this.innerText = "KÍCH HOẠT HỆ THỐNG";
                this.disabled = false;
            }}
        }};
    }}

    async function loadCore(key) {{
        try {{
            // Rút mã nguồn chính từ Server
            let res = await secureFetch('/api/core', {{ key: key, deviceId: deviceId }});
            if(res.status === 'success' && res.payload) {{
                // Kỹ thuật giải mã Code ngầm định
                let reversed = res.payload.split('').reverse().join('');
                let decodedCore = decodeURIComponent(escape(window.atob(reversed)));
                
                // Tiêm vào DOM
                let s = document.createElement('script');
                s.textContent = decodedCore;
                document.documentElement.appendChild(s);
                s.remove();

                // Bắt đầu gửi nhịp tim chống Share Key
                setInterval(() => {{
                    secureFetch('/api/script_ping', {{ key: key }});
                }}, 30000);
            }} else {{
                showAuthUI("Lỗi kéo dữ liệu Core!");
            }}
        }} catch(e) {{
            showAuthUI("Không thể tải Core Module!");
        }}
    }}

    if(!savedKey) {{
        window.addEventListener('DOMContentLoaded', () => showAuthUI());
    }} else {{
        // Check ngầm
        secureFetch('/api/check', {{ key: savedKey, deviceId: deviceId }}).then(res => {{
            if(res.status === 'success') {{
                if(res.loader_enabled) loadCore(savedKey);
                else console.log("SPOOFER BỊ TẮT TỪ ADMIN");
            }} else {{
                GM_setValue('lvt_tool_key', '');
                window.addEventListener('DOMContentLoaded', () => showAuthUI(res.message));
            }}
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
@app.route('/')
def home_shop():
    return '''
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>LVT TOOL - Trang Chủ</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>body{background:#05050A;color:#fff;font-family:'Segoe UI',sans-serif;} .hero{background:linear-gradient(135deg,#000,#0a192f);padding:100px 0;text-align:center;border-bottom:1px solid #00ffcc;} .neon-text{color:#00ffcc;text-shadow:0 0 10px #00ffcc;} .pkg-card{background:#11111A;border:1px solid #333;border-radius:15px;padding:30px;text-align:center;transition:0.3s;} .pkg-card:hover{border-color:#00ffcc;box-shadow:0 0 20px rgba(0,255,204,0.2);transform:translateY(-10px);} .price{font-size:35px;font-weight:900;color:#bd00ff;margin:20px 0;}</style></head><body>
    <div class="hero">
        <h1 class="neon-text fw-bold mb-3">⚡ HỆ THỐNG LVT TOOL VIP ⚡</h1>
        <p class="text-secondary fs-5 mb-4">Công cụ tự động hóa thông minh - Bảo mật đa tầng - Chống phát hiện</p>
        <a href="#shop" class="btn btn-lg fw-bold" style="background:#00ffcc;color:#000;">XEM BẢNG GIÁ</a>
        <a href="/api/script/lvt_vip_loader.user.js" class="btn btn-outline-info btn-lg fw-bold ms-2">CÀI ĐẶT LOADER</a>
    </div>
    <div class="container py-5" id="shop">
        <h2 class="text-center neon-text fw-bold mb-5">BẢNG GIÁ DỊCH VỤ</h2>
        <div class="row g-4">
            <div class="col-md-4"><div class="pkg-card"><h3 class="text-white">GÓI 7 NGÀY</h3><div class="price">30,000đ</div><p class="text-secondary">Trải nghiệm ngắn hạn<br>Hỗ trợ 1 thiết bị<br>Update miễn phí</p><a href="https://zalo.me/your_zalo_here" class="btn btn-outline-light w-100 mt-3" target="_blank"><i class="fas fa-shopping-cart"></i> Liên hệ Zalo Mua Ngay</a></div></div>
            <div class="col-md-4"><div class="pkg-card" style="border-color:#bd00ff;box-shadow:0 0 20px rgba(189,0,255,0.2);"><div class="badge bg-danger mb-2">BÁN CHẠY NHẤT</div><h3 class="text-white">GÓI 30 NGÀY</h3><div class="price text-info">85,000đ</div><p class="text-secondary">Chiến game dài hạn<br>Hỗ trợ 1 thiết bị<br>Chống văng Anti-Cheat</p><a href="https://zalo.me/your_zalo_here" class="btn btn-info w-100 mt-3 fw-bold" target="_blank"><i class="fas fa-shopping-cart"></i> Liên hệ Zalo Mua Ngay</a></div></div>
            <div class="col-md-4"><div class="pkg-card"><h3 class="text-white">GÓI 1 NĂM</h3><div class="price">200,000đ</div><p class="text-secondary">Dùng thoải mái<br>Hỗ trợ 2 thiết bị<br>Chăm sóc đặc biệt</p><a href="https://zalo.me/your_zalo_here" class="btn btn-outline-light w-100 mt-3" target="_blank"><i class="fas fa-shopping-cart"></i> Liên hệ Zalo Mua Ngay</a></div></div>
        </div>
    </div>
    <footer class="text-center text-secondary py-4 border-top border-dark">© 2026 LVT SECURE SYSTEM. Chạy ngầm đỉnh cao.</footer>
    </body></html>
    '''

# ========================================================
# GIAO DIỆN WEB ADMIN QUẢN LÝ
# ========================================================
@app.route('/admin_login', methods=['GET', 'POST'])
def login():
    global login_attempts
    if len(login_attempts) > 1000: login_attempts.clear()
        
    if request.method == 'POST':
        ip = get_real_ip()
        now = time.time()
        attempts = login_attempts.get(ip, [])
        attempts = [t for t in attempts if now - t < 600] # Theo dõi trong 10 phút
        
        # NẾU SAI 5 LẦN TRONG 10 PHÚT -> KHÓA VĨNH VIỄN IP
        if len(attempts) >= 4: # Lần này là lần thứ 5 (đã có 4 lần sai trước)
            db = load_db()
            with db_lock:
                if ip not in db.setdefault("banned_ips", []):
                    db["banned_ips"].append(ip)
                    report_bad_signature(ip) # Lưu log alert
                    save_db(db)
            return "<html><script>alert('🚨 BẠN ĐÃ BỊ FIREWALL KHÓA IP VÌ CỐ TÌNH DÒ PASS 5 LẦN!');window.location.href='/admin_login';</script></html>"
        
        db = load_db()
        current_admin_hash = db.get("settings", {}).get("admin_password_hash", DEFAULT_ADMIN_PASSWORD_HASH)
        
        if hmac.compare_digest(hashlib.sha256(request.form.get('password', '').encode()).hexdigest(), current_admin_hash):
            session['admin_auth'] = True 
            session['admin_ip'] = ip 
            with db_lock: log_admin_action(db, f"Đăng nhập Web Admin thành công từ IP: {ip}")
            save_db(db)
            if ip in login_attempts: del login_attempts[ip]
            return redirect('/admin')
            
        attempts.append(now)
        login_attempts[ip] = attempts
        return f"<html><script>alert('Sai mật khẩu! Cảnh cáo {len(attempts)}/5 lần.');window.location.href='/admin_login';</script></html>"
    
    return '''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Admin Login</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>body { background: #05050A; display: flex; justify-content: center; align-items: center; height: 100vh; } .login-box { background: #11111A; padding: 40px; border-radius: 15px; border: 1px solid #00ffcc; text-align: center; width: 350px;} h2 { color: #00ffcc; margin-bottom: 30px; font-weight:900;} input { background: #05050A !important; color: white !important; border: 1px solid #333 !important; } .btn-login { background: linear-gradient(45deg, #00ffcc, #bd00ff); width: 100%; margin-top: 20px; font-weight:bold; color:black;}</style></head><body><div class="login-box"><h2>CONTROL PANEL</h2><form method="POST"><input type="password" name="password" class="form-control mb-3" placeholder="Nhập Mật Khẩu Chống Lũ..." required><button type="submit" class="btn btn-login">MỞ KHÓA TÊN LỬA</button></form></div></body></html>'''

@app.route('/admin_logout')
def logout():
    session.pop('admin_auth', None)
    session.pop('admin_ip', None)
    return redirect('/')

@app.route('/admin')
def dashboard():
    if not session.get('admin_auth'): return redirect('/admin_login')
    db = load_db()
    with db_lock:
        keys_items = list(db.get("keys", {}).items())
        banned_ips = list(db.get("banned_ips", []))
        admin_logs = list(db.get("admin_logs", []))

    # XỬ LÝ HTML CHO BẢNG KEY
    keys_html = ''
    now_ms = int(time.time() * 1000)
    for k, data in sorted(keys_items, key=lambda x: x[1].get('exp', 0) if isinstance(x[1].get('exp'), int) else 9999999999999, reverse=True):
        st = data.get('status', 'active')
        is_banned = (st == 'banned')
        is_vip = data.get('vip', False)
        violation_count = data.get('violations', 0)
        temp_ban = data.get('temp_ban_until', 0)
        
        status_badge = '<span class="badge bg-success">Hoạt động</span>'
        if is_banned: status_badge = '<span class="badge bg-dark border border-danger text-danger">TỬ HÌNH</span>'
        elif temp_ban > now_ms: status_badge = f'<span class="badge bg-warning text-dark">Phạt Share ({ (temp_ban - now_ms)//60000 }p)</span>'

        vip_badge = '<span class="badge bg-primary">VIP</span>' if is_vip else '<span class="badge bg-secondary">THƯỜNG</span>'
        
        is_expired = False
        if data.get('exp') == 'pending': exp_text = '<span class="text-info">Chưa kích hoạt</span>'
        elif data.get('exp') == 'permanent': exp_text = '<span class="text-success fw-bold">V.Viễn</span>'
        else:
            is_expired = now_ms > data.get('exp', 0)
            exp_text = f'<span class="{"text-danger fw-bold" if is_expired else "text-light"}">{time.strftime("%d/%m/%Y %H:%M", time.localtime(data.get("exp", 0) / 1000))}</span>'
        
        if is_expired and not is_banned: status_badge = '<span class="badge bg-secondary">HẾT HẠN</span>'

        devs = data.get('devices', [])
        max_devs = data.get('maxDevices', 1)
        safe_k = escape(str(k))

        keys_html += f'''
        <tr>
            <td><strong class="text-info">{safe_k}</strong><br>{vip_badge} {status_badge}</td>
            <td>{exp_text}</td>
            <td><span class="badge bg-info text-dark">{len(devs)}/{max_devs}</span> <small class="text-muted">(Lỗi: {violation_count})</small></td>
            <td>
                <div class="btn-group btn-group-sm">
                    <a href="/admin/action/reset-dev/{safe_k}" class="btn btn-primary" title="Reset Máy">🔄</a>
                    <a href="/admin/action/unban_temp/{safe_k}" class="btn btn-success" title="Gỡ phạt Share">Gỡ Phạt</a>
                    <a href="/admin/action/{"unban" if is_banned else "ban"}/{safe_k}" class="btn btn-{"light" if is_banned else "danger"}" title="Tử hình">{"Cứu Sống" if is_banned else "Trảm"}</a>
                    <a href="/admin/action/delete/{safe_k}" class="btn btn-dark" onclick="return confirm('Xóa vĩnh viễn Key này?')" title="Xóa thùng rác">🗑️</a>
                </div>
            </td>
        </tr>'''

    # LOGS IP & LỊCH SỬ
    blacklist_rows = ""
    for ip in banned_ips:
        blacklist_rows += f'<li class="list-group-item bg-dark text-light d-flex justify-content-between align-items-center" style="font-size:13px;">{escape(ip)} <a href="/admin/unban_ip/{escape(ip)}" class="btn btn-sm btn-danger p-0 px-2">Gỡ</a></li>'
    if not blacklist_rows: blacklist_rows = '<li class="list-group-item bg-dark text-muted text-center" style="font-size:13px;">Sạch sẽ</li>'
    
    logs_html = ""
    for alog in admin_logs[:15]:
        l_time = time.strftime('%H:%M %d/%m', time.localtime(alog.get('time', 0)/1000))
        logs_html += f'<li class="list-group-item bg-dark text-light border-secondary p-2 mb-1 rounded" style="font-size:11px;"><span class="text-warning">[{l_time}]</span> {escape(alog.get("action", ""))}</li>'

    # TRẢ VỀ GIAO DIỆN ADMIN CHÍNH
    return f'''
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ADMIN - LVT TOOL</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>body{{background:#05050A;color:#e0e0e0;font-family:'Segoe UI',sans-serif;}} .card{{background:#11111A;border:1px solid #333;border-radius:12px;}} h4{{color:#00ffcc;font-weight:900;}} .table-container{{max-height:600px;overflow-y:auto;}} tbody tr:hover{{background:rgba(0,255,204,0.05)!important;}}</style></head><body class="p-3">
    <div class="container-fluid">
        <div class="d-flex justify-content-between align-items-center mb-4 border-bottom border-secondary pb-2">
            <h2 class="m-0" style="color:#00ffcc; font-weight:900;">⚡ BẢNG ĐIỀU KHIỂN BẢO MẬT</h2>
            <a href="/admin_logout" class="btn btn-outline-danger btn-sm">Thoát</a>
        </div>
        
        <div class="row g-4">
            <div class="col-lg-4">
                <div class="card p-3 mb-4" style="border-color:#bd00ff;">
                    <h4 style="color:#bd00ff;"><i class="fas fa-key"></i> TẠO KEY TOOL MỚI</h4>
                    <form action="/admin/create" method="POST" class="row g-2 mt-2">
                        <div class="col-6"><input type="text" name="prefix" class="form-control bg-dark text-light border-secondary" placeholder="Tiền tố (Tùy chọn)"></div>
                        <div class="col-6"><input type="number" name="quantity" class="form-control bg-dark text-light border-secondary" value="1" placeholder="Số Lượng"></div>
                        <div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light border-secondary" placeholder="Độ dài hạn" required></div>
                        <div class="col-6"><select name="type" class="form-select bg-dark text-light border-secondary"><option value="hour">Giờ</option><option value="day" selected>Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh viễn</option></select></div>
                        <div class="col-6"><input type="number" name="maxDevices" class="form-control bg-dark text-light border-secondary" placeholder="Max Thiết bị" value="1"></div>
                        <div class="col-6 d-flex align-items-center"><div class="form-check form-switch m-0"><input class="form-check-input" type="checkbox" name="is_vip" id="vipSw" checked><label class="form-check-label text-warning" for="vipSw">Gắn mác VIP</label></div></div>
                        <div class="col-12 mt-3"><button type="submit" class="btn w-100 fw-bold" style="background:#bd00ff;color:white;">🚀 TẠO NGAY</button></div>
                    </form>
                </div>
                
                <div class="card p-3 mb-4" style="border-color:#ff3366;">
                    <h4 class="text-danger"><i class="fas fa-shield-virus"></i> FIREWALL (IP BANNED)</h4>
                    <form action="/admin/ban_ip" method="POST" class="d-flex gap-2 mb-2">
                        <input type="text" name="ip" class="form-control form-control-sm bg-dark text-light border-secondary" placeholder="Nhập IP thủ công..." required>
                        <button type="submit" class="btn btn-sm btn-danger fw-bold">Chặn</button>
                    </form>
                    <ul class="list-group list-group-flush" style="max-height:150px;overflow-y:auto;">{blacklist_rows}</ul>
                </div>
                
                <div class="card p-3" style="border-color:#888;">
                    <h4 class="text-secondary"><i class="fas fa-list-ul"></i> LOGS HOẠT ĐỘNG</h4>
                    <ul class="list-group list-group-flush" style="max-height:200px;overflow-y:auto;">{logs_html}</ul>
                </div>
            </div>
            
            <div class="col-lg-8">
                <div class="card p-3 h-100" style="border-color:#00ffcc;">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h4><i class="fas fa-database"></i> KHO KEY ĐÃ TẠO</h4>
                        <div class="d-flex gap-2">
                            <input type="text" id="searchInput" class="form-control form-control-sm bg-dark text-light border-info" style="width:200px;" placeholder="Tìm nhanh mã Key..." onkeyup="let s=this.value.toLowerCase();document.querySelectorAll('#kBody tr').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(s)?'':'none');">
                        </div>
                    </div>
                    <div class="table-container">
                        <table class="table table-dark table-sm align-middle">
                            <thead class="table-active"><tr><th>🔑 Mã Key</th><th>⏳ Hạn Dùng</th><th>💻 Thông số</th><th>⚙️ Thao tác</th></tr></thead>
                            <tbody id="kBody">{keys_html}</tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
    </body></html>
    '''

# ========================================================
# CÁC ROUTE CHỨC NĂNG CỦA ADMIN
# ========================================================
@app.route('/admin/create', methods=['POST'])
def create_key():
    if not session.get('admin_auth'): return redirect('/admin_login')
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
                "loader_enabled": True, "violations": 0, "temp_ban_until": 0
            }
            if t != 'permanent': db["keys"][nk]["durationMs"] = dur * {"hour":3600000, "day":86400000, "month":2592000000}.get(t, 60000)
            else: db["keys"][nk]["exp"] = "permanent"
        log_admin_action(db, f"Tạo {qty} Key mới ({dur} {t}) - Mác VIP: {vip}")
        save_db(db)
    return redirect('/admin')

@app.route('/admin/ban_ip', methods=['POST'])
def web_ban_ip():
    if not session.get('admin_auth'): return redirect('/admin_login')
    ip = request.form.get('ip', '').strip()
    if ip:
        db = load_db()
        with db_lock:
            if ip not in db.setdefault("banned_ips", []):
                db["banned_ips"].append(ip)
                log_admin_action(db, f"Chặn IP thủ công: {ip}")
                save_db(db)
    return redirect('/admin')

@app.route('/admin/unban_ip/<ip>')
def unban_ip(ip):
    if not session.get('admin_auth'): return redirect('/admin_login')
    db = load_db()
    with db_lock:
        if ip in db.setdefault("banned_ips", []):
            db["banned_ips"].remove(ip)
            log_admin_action(db, f"Gỡ Firewall cho IP: {ip}")
            save_db(db)
    return redirect('/admin')

@app.route('/admin/action/<action>/<key>')
def key_actions(action, key):
    if not session.get('admin_auth'): return redirect('/admin_login')
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
            elif action == 'delete': db["keys"].pop(key, None)
            elif action == 'reset-dev':
                kd['devices'] = []
                kd['known_ips'] = {}
            log_admin_action(db, f"Lệnh [{action}] trên Key {key}")
            save_db(db)
    return redirect('/admin')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
