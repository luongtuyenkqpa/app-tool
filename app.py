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
                            keyboard = {"inline_keyboard": [
                                [{"text": "🌐 MỞ TRANG KÍCH HOẠT PROXY", "url": f"{WEB_URL}/"}]
                            ]}
                            requests.post(url_base + "/sendMessage", json={"chat_id": chat_id, "text": welcome, "parse_mode": "HTML", "reply_markup": keyboard})
                        
                        elif text.startswith("// ==UserScript==") and chat_id == TELEGRAM_CHAT_ID:
                            db = load_db()
                            with db_lock:
                                db.setdefault("settings", {})["custom_script"] = text
                                log_admin_action(db, "TeleBot: Cập nhật Script Gốc")
                                save_db(db)
                            send_telegram_alert("✅ Đã cập nhật Code Violentmonkey Gốc vào hệ thống Proxy!")
        except Exception: pass
        time.sleep(2)

threading.Thread(target=telegram_polling, daemon=True).start()

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException): return e
    error_detail = traceback.format_exc()
    send_telegram_alert(f"<b>CRITICAL CRASH BẮT ĐƯỢC:</b>\n<pre>{error_detail[-300:]}</pre>")
    return "Hệ thống đang bảo trì.", 500

app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
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
    return f"""<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #05050A; }}</style></head><body><script>
        Swal.fire({{ title: `{title}`, html: `{text}`, icon: '{icon}', background: '#11111A', color: '#fff', confirmButtonColor: '#00ffcc', allowOutsideClick: false
        }}).then(() => {{ window.location.href = '{url}'; }});
    </script></body></html>"""

def swal_back(title, text, icon):
    return f"""<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #05050A; }}</style></head><body><script>
        Swal.fire({{ title: `{title}`, html: `{text}`, icon: '{icon}', background: '#11111A', color: '#fff', confirmButtonColor: '#bd00ff', allowOutsideClick: false
        }}).then(() => {{ window.history.back(); }});
    </script></body></html>"""

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
                data.setdefault("game_keys", {}) # Giữ nguyên cấu trúc cũ
                data.setdefault("tg_auth_ids", {str(TELEGRAM_CHAT_ID): {"exp": "permanent", "banned_until": 0}}) 
                
                if "secret_key" not in data["settings"]: data["settings"]["secret_key"] = secrets.token_hex(32)
                if "maintenance_until" not in data["settings"]: data["settings"]["maintenance_until"] = 0
                if "global_notice" not in data["settings"]: data["settings"]["global_notice"] = ""
                if "custom_script" not in data["settings"]: data["settings"]["custom_script"] = ""
                if "tg_admins" not in data["settings"]: data["settings"]["tg_admins"] = [TELEGRAM_CHAT_ID]
                
                if "admin" not in data["users"]:
                    data["users"]["admin"] = {"password_hash": hash_pwd("120510@"), "role": "admin", "balance": 0, "created_at": int(time.time() * 1000), "ips": [], "banned_until": 0}

                for k in data["keys"]:
                    data["keys"][k].setdefault("owner", "admin")
                    data["keys"][k].setdefault("violations", 0)
                    data["keys"][k].setdefault("temp_ban_until", 0)
                    data["keys"][k].setdefault("devices", [])
                    data["keys"][k].setdefault("maxDevices", 1)
                    data["keys"][k].setdefault("bound_olm", "") 
                    data["keys"][k].setdefault("vip", False)
                    data["keys"][k].setdefault("activated", False)
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
            send_telegram_alert(f"LỖI GHI FILE DB: {str(e)}")
            if os.path.exists(temp_file): os.remove(temp_file)

# [TÍNH NĂNG MỚI] Auto Key 15 Ký Tự Random
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
            
        if request.path.startswith("/admin") and request.path not in ["/admin_login"]:
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

# ========================================================
# API TẢI SCRIPT GỐC CHO PROXY (PYTHON MITMPROXY GỌI VÀO ĐÂY)
# ========================================================
@app.route('/api/get_script')
def serve_custom_script():
    db = load_db()
    script = db.get("settings", {}).get("custom_script", "")
    resp = make_response(script)
    resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp

# ========================================================
# CHỨC NĂNG TẢI CHỨNG CHỈ (DÀNH CHO CLIENT)
# ========================================================
@app.route('/download-ca')
def download_ca():
    # Bạn thay thư mục chứng chỉ thật của bạn ở máy chủ vào đây hoặc giữ giả lập này để test
    dummy_ca = "-----BEGIN CERTIFICATE-----\nMIIDzTCCArWgAwIBAgIQC... (Tự chèn CA của bạn ở Mitmproxy)\n-----END CERTIFICATE-----"
    resp = make_response(dummy_ca)
    resp.headers['Content-Type'] = 'application/x-pem-file'
    resp.headers['Content-Disposition'] = 'attachment; filename="OLM_PROXY_CA.pem"'
    return resp

# ========================================================
# GIAO DIỆN WEB NGƯỜI DÙNG KÍCH HOẠT PROXY (KHÔNG ADMIN, KHÔNG TELE)
# ========================================================
@app.route('/')
def user_proxy_portal():
    html = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>LVT - Kích Hoạt Proxy Web</title>
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
            body {{ background: #05050a; color: #fff; font-family: 'Inter', sans-serif; margin: 0; padding: 20px; display: flex; justify-content: center; align-items: center; min-height: 100vh; }}
            {CSS_GLASS}
            .info-box {{ background: rgba(0,0,0,0.6); border: 1px dashed #a855f7; padding: 20px; border-radius: 10px; margin-top: 20px; display: none; text-align: left; }}
            .step-title {{ color: #a855f7; font-weight: 900; margin-top: 15px; margin-bottom: 5px; font-size: 15px; border-bottom: 1px solid rgba(168,85,247,0.3); padding-bottom: 5px; text-transform:uppercase; }}
            .step-text {{ font-size: 13px; color: #ccc; line-height: 1.6; margin: 8px 0; }}
            .highlight {{ color: #00ffcc; font-weight: bold; font-family: monospace; font-size: 16px; user-select: all; }}
            .cert-btn {{ background: linear-gradient(90deg, #a855f7, #6366f1); color: #fff; text-decoration: none; padding: 12px; border-radius: 8px; display: block; text-align: center; font-weight: 900; margin-top: 20px; transition: 0.3s; text-transform:uppercase; border:none; width:100%; cursor:pointer; }}
            .cert-btn:hover {{ transform: scale(1.02); box-shadow: 0 0 15px rgba(168,85,247,0.5); }}
            .inp-neon {{ background: rgba(0,0,0,0.5); border: 1px solid rgba(0,255,204,0.3); color: #00ffcc; padding: 15px; border-radius: 8px; width: 100%; margin-bottom: 15px; outline: none; transition: 0.3s; font-family: monospace; font-size: 16px; text-align: center; font-weight:bold; box-sizing:border-box; }}
            .inp-neon:focus {{ border-color: #00ffcc; box-shadow: 0 0 10px rgba(0,255,204,0.2); }}
        </style>
    </head>
    <body>
        <div class="glass-panel" style="max-width: 550px; width: 100%;">
            <h2 class="text-neon mb-2" style="margin-top:0;"><i class="fas fa-network-wired"></i> KÍCH HOẠT PROXY LVT</h2>
            <p style="color:#889; font-size:13px; margin-bottom:25px;">Nhập Key kích hoạt do Admin cấp để nhận Cấu hình Máy Chủ riêng biệt.</p>
            
            <input type="text" id="k_inp" class="inp-neon" placeholder="Dán mã Key 15 ký tự vào đây...">
            <button class="btn-neon" onclick="actKey()"><i class="fas fa-bolt"></i> KIỂM TRA VÀ LẤY CẤU HÌNH</button>

            <div id="proxy-result" class="info-box">
                <h4 style="color:#00ffcc; text-align:center; margin-top:0; font-size:18px;">THÔNG TIN KẾT NỐI TƯ NHÂN</h4>
                <div style="margin-bottom:12px; background:rgba(255,255,255,0.05); padding:10px; border-radius:8px;">
                    <div style="color:#889; font-size:12px; margin-bottom:4px;">👤 Định danh OLM hợp lệ:</div>
                    <div id="res-olm" class="highlight" style="color:#ffcc00;"></div>
                </div>
                <div style="margin-bottom:12px; background:rgba(255,255,255,0.05); padding:10px; border-radius:8px;">
                    <div style="color:#889; font-size:12px; margin-bottom:4px;">🌐 Tên Máy Chủ (Host):</div>
                    <div id="res-host" class="highlight"></div>
                </div>
                <div style="margin-bottom:12px; background:rgba(255,255,255,0.05); padding:10px; border-radius:8px;">
                    <div style="color:#889; font-size:12px; margin-bottom:4px;">🔌 Số Cổng (Port):</div>
                    <div id="res-port" class="highlight" style="color:#ff3366;"></div>
                </div>
                
                <button class="cert-btn" onclick="window.location.href='/download-ca'"><i class="fas fa-download"></i> TẢI CHỨNG CHỈ BẢO MẬT (CA)</button>

                <div style="margin-top:25px; border-top: 1px dashed #555; padding-top: 15px;">
                    <h4 style="color:#ff3366; text-align:center; margin-top:0;">HƯỚNG DẪN CÀI ĐẶT BẮT BUỘC</h4>
                    
                    <div class="step-title"><i class="fab fa-android"></i> DÀNH CHO ANDROID</div>
                    <p class="step-text"><b>Bước 1:</b> Mở Cài đặt Wifi, ấn vào chữ <b>(i)</b> hoặc Mũi tên cạnh Wifi đang kết nối.</p>
                    <p class="step-text"><b>Bước 2:</b> Tìm phần <b>Proxy</b>, đổi thành <b>Thủ Công</b>.</p>
                    <p class="step-text"><b>Bước 3:</b> Nhập chính xác <b>Tên máy chủ</b> và <b>Cổng</b> đã lấy ở trên vào ô trống và Lưu lại.</p>
                    <p class="step-text"><b>Bước 4:</b> Bấm nút Tải Chứng Chỉ màu tím ở trên. Sau đó vào Cài đặt điện thoại -> Tìm kiếm "Chứng chỉ" -> Chọn <b>Cài đặt chứng chỉ</b> -> Chọn loại: <b>Chứng chỉ VPN và ứng dụng</b> (đối với máy yêu cầu chọn). Chọn file vừa tải về và đặt tên là "LVT Proxy".</p>
                    <p class="step-text"><b>Bước 5:</b> Mở Chrome/Safari, vào thẳng <b>olm.vn</b> và Script sẽ tự động hiện lên góc màn hình!</p>

                    <div class="step-title"><i class="fab fa-apple"></i> DÀNH CHO iOS (IPHONE/IPAD)</div>
                    <p class="step-text"><b>Bước 1:</b> Cài đặt Wifi -> Bấm chữ <b>(i)</b> -> Định cấu hình Proxy -> Đổi thành <b>Thủ công</b> -> Nhập Máy chủ và Cổng.</p>
                    <p class="step-text"><b>Bước 2:</b> Bấm nút Tải Chứng Chỉ ở trên. Safari sẽ báo Đã tải hồ sơ.</p>
                    <p class="step-text"><b>Bước 3:</b> Mở Cài đặt máy -> <b>Đã tải về hồ sơ</b> -> Cài đặt.</p>
                    <p class="step-text"><b>Bước 4: (Rất Quan Trọng)</b> Vào Cài đặt chung -> Giới thiệu -> Kéo xuống dưới cùng chọn <b>Cài đặt tin cậy chứng chỉ</b> -> Gạt nút xanh cho chứng chỉ vừa cài.</p>
                </div>
            </div>
        </div>

        <script>
            function actKey() {{
                let k = document.getElementById('k_inp').value.trim();
                if(!k) return Swal.fire('Lỗi','Vui lòng dán Key!','warning');
                fetch('/api/proxy/activate', {{
                    method:'POST', headers:{{'Content-Type':'application/json'}},
                    body:JSON.stringify({{key:k}})
                }}).then(r=>r.json()).then(r=>{{
                    if(r.status==='success') {{
                        document.getElementById('proxy-result').style.display = 'block';
                        document.getElementById('res-olm').innerText = r.olm;
                        document.getElementById('res-host').innerText = r.host;
                        document.getElementById('res-port').innerText = r.port;
                        Swal.fire('Thành Công', 'Xác thực thành công. Vui lòng cài đặt Proxy theo hướng dẫn!', 'success');
                    }} else Swal.fire('Lỗi', r.msg, 'error');
                }}).catch(e=>Swal.fire('Lỗi', 'Không thể kết nối đến Máy chủ!', 'error'));
            }}
        </script>
    </body>
    </html>
    """
    return render_template_string_safe(html)

@app.route('/api/proxy/activate', methods=['POST'])
def proxy_activate():
    data = request.json or {}
    key = data.get("key", "").strip()
    db = load_db()
    now = int(time.time() * 1000)
    with db_lock:
        if key not in db.get("keys", {}): return jsonify({"status": "error", "msg": "Mã Key không tồn tại hoặc sai định dạng!"})
        kd = db["keys"][key]
        
        if kd.get("status") == "banned": return jsonify({"status": "error", "msg": "Key của bạn đã bị Admin khóa vĩnh viễn!"})
        if kd.get("exp") != "permanent" and kd.get("exp") != "pending" and kd.get("exp", 0) < now:
            return jsonify({"status": "error", "msg": "Key đã hết hạn sử dụng. Hãy liên hệ Admin gia hạn!"})

        if not kd.get("bound_olm"):
            return jsonify({"status": "error", "msg": "Lỗi: Key này chưa được Admin ghim Tên OLM. Không thể trả Proxy!"})
        
        if not kd.get("proxy_host") or not kd.get("proxy_port"):
            return jsonify({"status": "error", "msg": "Lỗi: Admin chưa thiết lập Tên máy chủ cho Key này. Hãy báo Admin cấu hình trước!"})

        if kd.get("exp") == "pending":
            kd["exp"] = now + kd.get("durationMs", 0)
            kd["activated"] = True
            save_db(db)
            
    return jsonify({"status": "success", "host": kd["proxy_host"], "port": kd["proxy_port"], "olm": kd["bound_olm"]})

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
            
        return f'''<!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><title>C-Panel Proxy Admin</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>{CSS_GLASS} .inp-neon {{ background: rgba(0,0,0,0.5); border: 1px solid rgba(0,255,204,0.3); color: #00ffcc; padding: 12px; border-radius: 8px; width: 100%; margin-bottom: 15px; outline: none; transition: 0.3s; text-align: center; }} .inp-neon:focus {{ border-color: #00ffcc; }}</style></head><body style="background:#05050a; display:flex; justify-content:center; align-items:center; height:100vh;"><div class="container"><div class="glass-panel mx-auto" style="max-width:400px;"><h2 class="text-neon mb-4"><i class="fas fa-user-shield"></i> LVT C-PANEL</h2><form method="POST"><input type="text" name="username" class="inp-neon" placeholder="Tài khoản Quản Trị" required><input type="password" name="password" class="inp-neon" placeholder="Mật Khẩu" required><button type="submit" class="btn-neon mt-2"><i class="fas fa-sign-in-alt"></i> TRUY CẬP</button></form></div></div></body></html>'''
    except Exception as e: return f"LỖI: {str(e)}", 200

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect('/admin_login')
    db = load_db()
    csrf_input = f'<input type="hidden" name="csrf_token" value="{session.get("csrf_token", "")}">'
    
    with db_lock:
        keys_items = list(db.get("keys", {}).items())
        banned_ips = list(db.get("banned_ips", []))
        current_script = escape(db.get("settings", {}).get("custom_script", ""))

    now_ms = int(time.time() * 1000)
    keys_html = ''
    for k, data in sorted(keys_items, key=lambda x: x[1].get('exp', 0) if isinstance(x[1].get('exp'), int) else 9999999999999, reverse=True):
        st = data.get('status', 'active')
        is_banned = (st == 'banned')
        status_badge = '<span class="badge bg-success">Hoạt động</span>' if not is_banned else '<span class="badge bg-danger">BỊ TRẢM</span>'
        vip_badge = '<span class="badge bg-warning text-dark fw-bold">VIP PRO</span>' if data.get('vip', False) else '<span class="badge bg-secondary">THƯỜNG</span>'
        
        is_expired = False
        if data.get('exp') == 'pending': exp_text = '<span class="text-info fw-bold">Chưa K.Hoạt</span>'
        elif data.get('exp') == 'permanent': exp_text = '<span class="text-success fw-bold">Vĩnh Viễn</span>'
        else:
            is_expired = now_ms > data.get('exp', 0)
            exp_text = f'<span class="{"text-danger fw-bold" if is_expired else "text-light"}">{time.strftime("%d/%m/%y %H:%M", time.localtime(data.get("exp", 0) / 1000))}</span>'
        
        if is_expired and not is_banned: status_badge = '<span class="badge bg-secondary">HẾT HẠN</span>'
        
        safe_k = escape(str(k))
        bound_olm = escape(data.get('bound_olm', ''))
        proxy_info = f"{data.get('proxy_host')}:{data.get('proxy_port')}" if data.get('proxy_host') else "Chưa gán máy chủ"

        keys_html += f'''<tr class="align-middle text-nowrap">
        <td><strong class="text-info font-monospace" style="font-size:16px;">{safe_k}</strong><br>{vip_badge} {status_badge}</td>
        <td style="font-size:14px;">{exp_text}</td>
        <td style="font-size:14px;"><span class="text-warning fw-bold">{bound_olm or '⚠️ Bắt buộc ghim OLM'}</span><br><span class="text-success font-monospace fw-bold">{proxy_info}</span></td>
        <td style="font-size:14px;"><span class="badge bg-info text-dark">{len(data.get('devices', []))}/{data.get('maxDevices', 1)}</span></td>
        <td><div class="d-flex flex-wrap gap-2 justify-content-center">
        <button class="btn btn-warning btn-sm fw-bold text-dark" style="font-size:12px;" onclick="openBindModal('{safe_k}', '{bound_olm}')"><i class="fas fa-link"></i> Ghim</button>
        <button class="btn btn-primary btn-sm fw-bold text-white" style="font-size:12px;" onclick="openProxyModal('{safe_k}')"><i class="fas fa-network-wired"></i> Gán Proxy</button>
        <button class="btn btn-info btn-sm fw-bold text-dark" style="font-size:12px;" onclick="openAddTimeModal('{safe_k}')"><i class="fas fa-clock"></i> C.Giờ</button>
        <a href="/admin/action/delete/{safe_k}" class="btn btn-danger btn-sm" onclick="return confirm('Bạn có chắc chắn muốn xóa vĩnh viễn Key này?')" style="font-size:12px;"><i class="fas fa-trash"></i></a>
        </div></td></tr>'''

    blacklist_rows = "".join([f'<li class="list-group-item bg-transparent text-light border-secondary d-flex justify-content-between font-monospace align-items-center py-2">{escape(ip)} <a href="/admin/unban_ip/{escape(ip)}" class="btn btn-sm btn-danger px-3 rounded-pill fw-bold">Gỡ</a></li>' for ip in banned_ips])

    return f'''
    <!DOCTYPE html><html lang="vi" data-bs-theme="dark"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>C-Panel Proxy LVT</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><style>body {{ background: #0b0d14; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }} .card {{ background: rgba(26,28,38,0.8); border: 1px solid rgba(255,255,255,0.05); box-shadow: 0 5px 15px rgba(0,0,0,0.5); }} h5{{font-weight:900; letter-spacing: 1px; text-transform: uppercase;}} .form-control, .form-select {{ background: rgba(0,0,0,0.5) !important; color: #00ffcc !important; border: 1px solid #333 !important; font-weight:bold; }} .form-control:focus {{ border-color: #00ffcc !important; box-shadow: 0 0 5px rgba(0,255,204,0.3) !important; }}</style></head><body class="p-3 p-md-4">
    <div class="container-fluid">
        <div class="d-flex justify-content-between align-items-center mb-4 border-bottom border-secondary pb-3">
            <h2 class="fw-bold m-0" style="color:#00ffcc; text-shadow: 0 0 15px rgba(0,255,204,0.5);"><i class="fas fa-server"></i> C-PANEL PROXY LVT</h2>
            <a href="/logout" class="btn btn-outline-danger fw-bold rounded-pill px-4"><i class="fas fa-power-off"></i> Thoát C-Panel</a>
        </div>
        
        <div class="row g-4 mb-4">
            <div class="col-md-5 col-lg-4">
                <div class="card p-4 h-100" style="border-top: 4px solid #22c55e;">
                    <h5 style="color:#22c55e; margin-bottom:20px;"><i class="fas fa-magic"></i> TẠO KEY PROXY (AUTO 15 KÝ TỰ)</h5>
                    <form action="/admin/create" method="POST" class="row g-3">{csrf_input}
                        <div class="col-6"><label class="text-muted small fw-bold">Số lượng tạo</label><input type="number" name="quantity" class="form-control" value="1" placeholder="Số lượng" required></div>
                        <div class="col-6"><label class="text-muted small fw-bold">Số máy cho phép</label><input type="number" name="devices" class="form-control" value="1" placeholder="Số thiết bị" required></div>
                        <div class="col-6"><label class="text-muted small fw-bold">Thời gian</label><input type="number" name="duration" class="form-control" value="1" required></div>
                        <div class="col-6"><label class="text-muted small fw-bold">Đơn vị</label><select name="type" class="form-select"><option value="minute">Phút</option><option value="hour">Giờ</option><option value="day" selected>Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh Viễn</option></select></div>
                        <div class="col-12 mt-4"><div class="form-check form-switch fs-5"><input class="form-check-input" type="checkbox" name="is_vip" id="vipSwitch"><label class="form-check-label text-warning fw-bold ms-2" for="vipSwitch">BẬT CHẾ ĐỘ VIP PRO</label></div></div>
                        <div class="col-12 mt-3"><button type="submit" class="btn fw-bold w-100 text-dark py-2" style="background:linear-gradient(90deg, #22c55e, #10b981); font-size:16px;"><i class="fas fa-cogs"></i> SẢN XUẤT KEY</button></div>
                    </form>
                </div>
            </div>

            <div class="col-md-7 col-lg-8">
                <div class="card p-4 h-100" style="border-top: 4px solid #a855f7;">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h5 style="color:#a855f7; margin:0;"><i class="fas fa-laptop-code"></i> NẠP SCRIPT VIOLENTMONKEY GỐC TÙY CHỈNH</h5>
                        <span class="badge bg-secondary">API Auto Inject Proxy</span>
                    </div>
                    <form action="/admin/update_script" method="POST" class="h-100 d-flex flex-column">{csrf_input}
                        <p class="text-muted" style="font-size:13px; line-height:1.5;">Dán toàn bộ mã nguồn Script chức năng Violentmonkey vào đây. Hệ thống Proxy sẽ tự động tiêm Script này vào trang web OLM.vn khi người dùng kết nối thành công mà không cần cài extension.</p>
                        <textarea name="script_content" class="form-control mb-3 flex-grow-1" style="font-family:Consolas, monospace; font-size:13px; min-height: 200px; background:#000 !important; color:#0f0 !important;" required placeholder="// ==UserScript==...">{current_script}</textarea>
                        <button type="submit" class="btn fw-bold text-white mt-auto py-2" style="background:linear-gradient(90deg, #a855f7, #6366f1); font-size:15px;"><i class="fas fa-cloud-upload-alt"></i> LƯU MÃ NGUỒN VÀ XUẤT BẢN LÊN HỆ THỐNG PROXY</button>
                    </form>
                </div>
            </div>
        </div>
        
        <div class="row g-4 mb-4">
            <div class="col-12">
                <div class="card p-4" style="border-top: 4px solid #ef4444;">
                    <h5 class="text-danger mb-3"><i class="fas fa-shield-virus"></i> CHẶN IP XẤU (FIREWALL)</h5>
                    <form action="/admin/ban_ip" method="POST" class="d-flex gap-2 mb-3">{csrf_input}<input type="text" name="ip" class="form-control" placeholder="Nhập địa chỉ IP cần chặn đứt..." required><button type="submit" class="btn btn-danger fw-bold px-4"><i class="fas fa-ban"></i> Chặn IP</button></form>
                    <ul class="list-group list-group-flush" style="max-height:200px; overflow-y:auto; border:1px solid rgba(255,255,255,0.1); border-radius:10px;">{blacklist_rows or '<li class="list-group-item bg-transparent text-muted text-center py-3">Hệ thống sạch sẽ, không có IP xấu.</li>'}</ul>
                </div>
            </div>
        </div>

        <div class="card p-4" style="border-top: 4px solid #0099ff;">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h5 class="text-primary m-0"><i class="fas fa-database"></i> KHO QUẢN LÝ KEY PROXY</h5>
                <div class="input-group" style="width:300px;">
                    <span class="input-group-text bg-dark border-secondary text-info"><i class="fas fa-search"></i></span>
                    <input type="text" class="form-control border-secondary" placeholder="Tìm kiếm Key hoặc Tên OLM..." onkeyup="let s=this.value.toLowerCase();document.querySelectorAll('.key-row').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(s)?'':'none');">
                </div>
            </div>
            <div class="table-responsive" style="max-height: 600px; overflow-y:auto; border: 1px solid rgba(255,255,255,0.1); border-radius:10px;">
                <table class="table table-dark table-hover table-striped text-center align-middle mb-0">
                    <thead style="position: sticky; top: 0; background: #1a1c26; z-index: 1;"><tr><th>🔑 Cụm Key 15 Ký Tự</th><th>⏳ Thời hạn cấp phép</th><th>🎯 Thiết lập Proxy Server</th><th>📱 Thiết bị</th><th>⚙️ Thao tác nhanh</th></tr></thead>
                    <tbody>
                        {keys_html}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="bindModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-dialog-centered"><div class="modal-content" style="background:#111;border:1px solid #ffcc00; box-shadow: 0 0 30px rgba(255,204,0,0.3);"><form action="/admin/bind_olm" method="POST">{csrf_input}<div class="modal-header border-secondary"><h5 class="modal-title text-warning fw-bold"><i class="fas fa-user-tag"></i> GHIM ĐỊNH DANH OLM</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body p-4 text-center"><input type="hidden" name="key" id="bindKeyInput"><p class="text-muted mb-2">Đang thao tác ghim tên OLM cho Key:</p><h4 id="bindKeyDisplay" class="text-info font-monospace d-block mb-4 fw-bold"></h4><input type="text" name="olm_name" id="bindOlmInput" class="form-control form-control-lg text-center fw-bold" placeholder="Nhập tên tài khoản OLM của khách..." required></div><div class="modal-footer border-secondary p-3"><button class="btn btn-warning w-100 fw-bold text-dark py-2 fs-5">CHỐT LƯU ĐỊNH DANH</button></div></form></div></div></div>
    
    <div class="modal fade" id="addTimeModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-dialog-centered"><div class="modal-content" style="background:#111;border:1px solid #00ffcc; box-shadow: 0 0 30px rgba(0,255,204,0.3);"><form action="/admin/add_time" method="POST">{csrf_input}<div class="modal-header border-secondary"><h5 class="modal-title text-info fw-bold"><i class="fas fa-clock"></i> BƠM THỜI GIAN</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body p-4 text-center"><input type="hidden" name="key" id="addTimeKeyInput"><p class="text-muted mb-2">Đang bơm giờ cho Key:</p><h4 id="addTimeKeyDisplay" class="text-info font-monospace d-block mb-4 fw-bold"></h4><input type="number" name="time_val" class="form-control form-control-lg text-center fw-bold mb-3" placeholder="Nhập số lượng (VD: 30)" required><select name="time_unit" class="form-select form-select-lg text-center fw-bold"><option value="minutes">Phút</option><option value="hours">Giờ</option><option value="days" selected>Ngày</option><option value="months">Tháng</option></select></div><div class="modal-footer border-secondary p-3"><button class="btn btn-info w-100 fw-bold text-dark py-2 fs-5">XÁC NHẬN CỘNG GIỜ</button></div></form></div></div></div>
    
    <div class="modal fade" id="proxyModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-dialog-centered"><div class="modal-content" style="background:#111;border:1px solid #a855f7; box-shadow: 0 0 30px rgba(168,85,247,0.3);"><form action="/admin/setup_proxy" method="POST">{csrf_input}<div class="modal-header border-secondary"><h5 class="modal-title fw-bold" style="color:#a855f7;"><i class="fas fa-network-wired"></i> GÁN MÁY CHỦ PROXY ĐỘC LẬP</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body p-4 text-center"><input type="hidden" name="key" id="proxyKeyInput"><p class="text-warning fw-bold mb-2 small"><i class="fas fa-exclamation-triangle"></i> LƯU Ý: Phải Ghim OLM trước mới được Gán Host!</p><h4 id="proxyKeyDisplay" class="text-info font-monospace d-block mb-4 fw-bold"></h4><p class="text-muted" style="font-size:13px;">Chỉ cần nhập tên Máy Chủ. Cổng Proxy sẽ được Hệ thống Auto Random.</p><input type="text" name="host" class="form-control form-control-lg text-center fw-bold text-success" placeholder="VD: p1.sv.lvt.com" required></div><div class="modal-footer border-secondary p-3"><button class="btn fw-bold w-100 text-white py-2 fs-5" style="background:linear-gradient(90deg, #a855f7, #6366f1);">LƯU VÀ RANDOM CỔNG</button></div></form></div></div></div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function openBindModal(key, old) {{ document.getElementById('bindKeyInput').value = key; document.getElementById('bindKeyDisplay').innerText = key; document.getElementById('bindOlmInput').value = old; new bootstrap.Modal(document.getElementById('bindModal')).show(); }}
        function openAddTimeModal(key) {{ document.getElementById('addTimeKeyInput').value = key; document.getElementById('addTimeKeyDisplay').innerText = key; new bootstrap.Modal(document.getElementById('addTimeModal')).show(); }}
        function openProxyModal(key) {{ document.getElementById('proxyKeyInput').value = key; document.getElementById('proxyKeyDisplay').innerText = key; new bootstrap.Modal(document.getElementById('proxyModal')).show(); }}
    </script>
    </body></html>
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
            db["keys"][nk] = {"exp": "pending", "maxDevices": md, "devices": [], "vip": vip, "status": "active", "bound_olm": "", "proxy_host": "", "proxy_port": 0}
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
                return swal_back("Lỗi Thiết Lập", "Key này chưa được ghim tài khoản OLM. Hãy bấm nút 'Ghim OLM' trước khi gán Proxy!", "error")
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

@app.route('/admin/update_script', methods=['POST'])
def admin_update_script():
    if session.get('role') != 'admin': return redirect('/admin_login')
    script_content = request.form.get('script_content', '')
    if not script_content.strip(): return swal_back("Lỗi", "Mã nguồn Script không được để trống!", "error")
    db = load_db()
    with db_lock:
        db.setdefault("settings", {})["custom_script"] = script_content
        save_db(db)
    return swal_redirect("Thành Công", "Đã lưu và xuất bản Script Gốc. Proxy sẽ tự động gọi mã nguồn mới nhất này để cấp cho khách!", "success", "/admin")

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
