import os, json, time, random, hashlib, threading, requests, re, shutil, base64, secrets, datetime, hmac
from concurrent.futures import ThreadPoolExecutor
from html import escape
from urllib.parse import urlparse
from flask import Flask, request, jsonify, redirect, make_response, session, abort

# [VÁ LỖI LỆCH MÚI GIỜ CLOUD]
try:
    os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
    time.tzset()
except: pass

# ========================================================
# [HỆ THỐNG ANTI-CRACK & BẢO VỆ DỮ LIỆU ĐA TẦNG]
# ========================================================
try:
    with open(__file__, 'rb') as f:
        __original_hash__ = hashlib.md5(f.read()).hexdigest()
except:
    __original_hash__ = None

app = Flask(__name__)

RAW_ADMIN_PASS = os.environ.get('ADMIN_PASSWORD', 'admin120510')
DEFAULT_ADMIN_PASSWORD_HASH = hashlib.sha256(RAW_ADMIN_PASS.encode()).hexdigest()
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', "LVT_SECURE_TOKEN_2026")

app.secret_key = os.environ.get('SECRET_KEY', hashlib.sha256(f"LVT_SECURE_{RAW_ADMIN_PASS}".encode()).hexdigest())

app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True 

DB_FILE = './database.json'
DB_BACKUP = './database.backup.json'

GITHUB_SCRIPT_URL = "https://gist.githubusercontent.com/luongtuyenkqpa/3d7cdb9e8607afc85a81a52041acd50c/raw/299ccb32bb1bcbc3a6e2538723844cca192ab5fa/olm-god-mode.user.js"
SCRIPT_PASSWORD = "OLM_VIP_786B-XQCH-BYEF-SYUS"

db_lock = threading.RLock()
anti_spam_lock = threading.Lock() 

active_sessions = {}
login_attempts = {}
anti_spam_cache = {} 
_sys_metrics_buffer = {} 

api_rate_lock = threading.Lock()
api_rate_cache = {}
bad_sig_cache = {} 
used_signatures = {} 

webhook_executor = ThreadPoolExecutor(max_workers=50)

GLOBAL_DB = {}
_last_db_mtime = 0
_last_mtime_check = 0 

# ========================================================
# [CẤU HÌNH BOT MESSENGER FACEBOOK] - THÊM MỚI
# ========================================================
FB_PAGE_TOKEN = os.environ.get('FB_PAGE_TOKEN', 'EAAVZBVODIGsYBRVhjcsp9PNaiCjMASMQRGQd20JEqPbxuEJ3WnrZBqtVY5DQ9xOZBj4wDwU6KwpHGOuJnHESEkXMKZAGUdCIzlFJAPUPUaDnJa8t3VnOhQxZBTxEum4NOXm9IKINCes2ES07u6Xg1TSxHH7FemiVPRRL4upPPT7vORRVpRPZBiUmZCZAd7CWZBxSHKTlINT1C5QZDZD')
FB_VERIFY_TOKEN = WEBHOOK_SECRET

# ========================================================
# HỆ THỐNG BẢO VỆ LAYER 7 & FIREWALL & IPS
# ========================================================
def get_real_ip():
    try:
        if request.headers.get("CF-Connecting-IP"): return request.headers.get("CF-Connecting-IP")
        if request.headers.getlist("X-Forwarded-For"): return request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
        return request.remote_addr
    except:
        return "Unknown_IP"

@app.before_request
def firewall_and_csrf():
    db = load_db()
    banned_ips = set(db.get("banned_ips", []))
    ip = get_real_ip()
    
    if ip in banned_ips:
        return "You have been banned by the Firewall (IPS).", 403

    ua = request.headers.get('User-Agent', '').lower()
    blocked_bots = ['curl', 'postman', 'python', 'nmap', 'sqlmap', 'masscan', 'zgrab', 'wget', 'urllib', 'nikto']
    if any(bot in ua for bot in blocked_bots) and not request.path.startswith("/webhook") and not request.path.startswith("/admin_webhook") and not request.path.startswith("/fb_webhook"):
        return "Firewall Blocked Suspicious Bot/Scanner.", 403
        
    if request.path.startswith("/admin/") or request.path == "/":
        if session.get('admin_auth'):
            if session.get('admin_ip') and session.get('admin_ip') != ip:
                session.clear()
                return redirect('/login')
                
    if request.method == "POST" and request.path.startswith("/admin/"):
        origin = request.headers.get("Origin")
        referer = request.headers.get("Referer")
        host = request.headers.get("Host")
        req_host = host.split(':')[0] if host else ""
        if origin:
            orig_host = urlparse(origin).netloc.split(':')[0]
            if orig_host != req_host: return "CSRF Blocked!", 403
        elif referer:
            ref_host = urlparse(referer).netloc.split(':')[0]
            if ref_host != req_host: return "CSRF Blocked!", 403
        else:
            return "CSRF Blocked!", 403

@app.errorhandler(404)
def not_found_trap(e):
    ip = get_real_ip()
    suspicious_paths = ['.env', 'wp-admin', 'wp-login.php', 'config.php', 'backup.zip', '.git', 'phpmyadmin']
    if any(s in request.path for s in suspicious_paths):
        report_bad_signature(ip)
    return "Not Found", 404

@app.route('/api/admin_login_bypass')
def honeypot_trap():
    ip = get_real_ip()
    db = load_db()
    with db_lock:
        if ip not in db.setdefault("banned_ips", []):
            db["banned_ips"].append(ip)
            save_db(db)
    return "Forbidden", 403

def report_bad_signature(ip):
    global bad_sig_cache
    if len(bad_sig_cache) > 5000: bad_sig_cache.clear()
    
    bad_sig_cache[ip] = bad_sig_cache.get(ip, 0) + 1
    if bad_sig_cache[ip] >= 3:
        db = load_db()
        with db_lock:
            if ip not in db.setdefault("banned_ips", []):
                db["banned_ips"].append(ip)
                db.setdefault("security_alerts", []).insert(0, {"time": int(time.time()*1000), "user": "Unknown Hacker/Scanner", "id": ip, "reason": "Spam API sai chữ ký/Dò thư mục ẩn"})
                save_db(db)

def notify_master_admin(db, message, actor_name="@luongtuyen20"):
    if "luongtuyen20" in actor_name.lower(): 
        return
        
    master_uid = None
    with db_lock:
        for uid, info in db["bot_users"].items():
            if info.get("username", "").lower() in ["@luongtuyen20", "luongtuyen20"]:
                master_uid = uid
                break
    if master_uid:
        webhook_executor.submit(admin_tg_send, master_uid, f"⚠️ <b>CẢNH BÁO KIỂM SOÁT NHÂN VIÊN</b>\n\n👮‍♂️ <b>Sub-Admin:</b> {actor_name}\n📌 <b>Hành động:</b> {message}\n⏰ <b>Thời gian:</b> {time.strftime('%H:%M:%S %d/%m/%Y')}")

def log_admin_action(db, action_text, actor_name="@luongtuyen20"):
    db.setdefault("admin_logs", []).insert(0, {
        "time": int(time.time() * 1000),
        "action": f"[{actor_name}] {action_text}"
    })
    db["admin_logs"] = db["admin_logs"][:100]
    notify_master_admin(db, action_text, actor_name)

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
            
            if not data and os.path.exists(DB_BACKUP):
                try:
                    with open(DB_BACKUP, 'r', encoding='utf-8') as f: data = json.load(f)
                except Exception: pass
                
            if not data:
                if os.path.exists(DB_FILE) and os.path.getsize(DB_FILE) > 0:
                    try: shutil.copy2(DB_FILE, DB_FILE + f".corrupted.{int(time.time())}.json")
                    except: pass
                data = {"keys": {}, "logs": [], "bot_users": {}, "active_scripts": {}, "shop": {}, "settings": {}, "security_alerts": [], "banned_ips": [], "revenue_logs": [], "admin_logs": []}
                
            try:
                data.setdefault("bot_users", {})
                data.setdefault("keys", {})
                data.setdefault("logs", [])
                data.setdefault("banned_ips", [])
                data.setdefault("revenue_logs", [])
                data.setdefault("admin_logs", [])
                data.setdefault("active_scripts", {})
                data.setdefault("security_alerts", []) 
                
                settings_data = data.setdefault("settings", {})
                settings_data.setdefault("max_users", 500)
                settings_data.setdefault("discord_webhook", "")
                settings_data.setdefault("maintenance_mode", False)
                settings_data.setdefault("admin_password_hash", DEFAULT_ADMIN_PASSWORD_HASH)
                
                shop_data = data.setdefault("shop", {})
                shop_data.setdefault("V_1H", {"price": 7000, "stock": 999, "dur_ms": 3600000, "name": "1 Giờ"})
                shop_data.setdefault("V_7D", {"price": 30000, "stock": 999, "dur_ms": 604800000, "name": "7 Ngày"})
                shop_data.setdefault("V_30D", {"price": 85000, "stock": 999, "dur_ms": 2592000000, "name": "30 Ngày"})
                shop_data.setdefault("V_1Y", {"price": 200000, "stock": 999, "dur_ms": 31536000000, "name": "1 Năm"})
                
                if "global_notice" in data: del data["global_notice"]
                for uid in list(data["bot_users"].keys()):
                    u = data["bot_users"][uid]
                    u.setdefault("purchases", [])
                    u.setdefault("gifts", {})
                    u.setdefault("notices", [])
                    u.setdefault("loader_active", False)
                    u.setdefault("loader_key", "")
                    u.setdefault("loader_olm", "")
                    u.setdefault("live_msg_id", None)
                    u.setdefault("live_msg_type", None)
                    u.setdefault("main_menu_id", None)
                    u.setdefault("is_admin", False)
                    u.setdefault("admin_exp", 0)
                    u.setdefault("admin_key", "")
                    u.setdefault("banned_until", 0)
                    u.setdefault("ban_reason", "")
                    u.setdefault("name", "Khách") 
                    u.setdefault("temp_key", "")
                    u.setdefault("referred_by", "")
                    u.setdefault("admin_state", "none")
                    
                    if "approved" not in u:
                        if u.get("is_admin") or u.get("balance", 0) > 0 or len(u.get("purchases", [])) > 0:
                            u["approved"] = True
                        else:
                            u["approved"] = False
                    u.setdefault("approval_time", 0)
                    
                for k in list(data["keys"].keys()):
                    data["keys"][k].setdefault("bound_olm", "") 
                    data["keys"][k].setdefault("loader_enabled", True)
                    data["keys"][k].setdefault("devices", [])
                GLOBAL_DB = data
                _last_db_mtime = current_mtime
            except Exception as e:
                pass
        return GLOBAL_DB

def save_db(db=None):
    global _last_db_mtime
    if db is None: db = GLOBAL_DB
    
    with db_lock:
        try: db_str = json.dumps(db, indent=2, ensure_ascii=False)
        except Exception: return 
        temp_file = DB_FILE + f'.{int(time.time() * 1000)}.tmp'
        try:
            with open(temp_file, 'w', encoding='utf-8') as f: f.write(db_str)
            os.replace(temp_file, DB_FILE)
            _last_db_mtime = os.path.getmtime(DB_FILE)
        except Exception as e: 
            if os.path.exists(temp_file): os.remove(temp_file)

def __hidden_bot_guardian__():
    while True:
        time.sleep(15)
        with db_lock:
            if os.path.exists(DB_FILE):
                try: shutil.copy2(DB_FILE, DB_BACKUP)
                except: pass

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

threading.Thread(target=__hidden_bot_guardian__, daemon=True).start()
threading.Thread(target=garbage_collector, daemon=True).start()

@app.after_request
def after_request(response):
    if request.path.startswith('/api/') and not request.path.startswith('/api/admin'):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'POST,OPTIONS')
    return response

# ========================================================
# CẤU HÌNH BOT TELEGRAM
# ========================================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', "8621133442:AAFhgCT-rpiR-Ahp1gXKZVjMwm-kfyoSIaE")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

ADMIN_BOT_TOKEN = os.environ.get('ADMIN_BOT_TOKEN', "8714375866:AAG9r0aCCFOKtgR6B-LcFYBAnJ7x9yMs-8o")
ADMIN_TELEGRAM_API_URL = f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}"

try:
    BOT_INFO = requests.get(f"{TELEGRAM_API_URL}/getMe").json()
    BOT_USERNAME = BOT_INFO.get("result", {}).get("username", "tool_bot")
except:
    BOT_USERNAME = "tool_bot"

try:
    ADMIN_BOT_INFO = requests.get(f"{ADMIN_TELEGRAM_API_URL}/getMe").json()
    ADMIN_BOT_USERNAME = ADMIN_BOT_INFO.get("result", {}).get("username", "admin_lvt_bot")
except:
    ADMIN_BOT_USERNAME = "admin_lvt_bot"

WEB_URL = "https://app-tool-trlp.onrender.com"

# ========================================================
# UTILS CHUNG & FACEBOOK API
# ========================================================
def send_discord_webhook(url, title, desc, color=5814783):
    if not url: return
    data = {"embeds": [{"title": title, "description": desc, "color": color}]}
    try: requests.post(url, json=data, timeout=3)
    except: pass

def is_vietnamese_or_english_letter(char):
    if 'a' <= char.lower() <= 'z': return True
    vi_chars = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
    if char.lower() in vi_chars: return True
    return False

def has_weird_name(name):
    has_alnum = False
    for char in name:
        if char.isalnum(): has_alnum = True
        if char.isalpha() and not is_vietnamese_or_english_letter(char): return True
    if not has_alnum and len(name.strip()) > 0: return True
    return False

multipliers_web = {'sec': 1000, 'min': 60000, 'hour': 3600000, 'day': 86400000, 'month': 2592000000, 'year': 31536000000}

# === CÁC HÀM GỬI TIN NHẮN MESSENGER ===
def fb_send_api(recipient_id, message_data):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_TOKEN}"
    payload = {"recipient": {"id": recipient_id}, "message": message_data}
    try: requests.post(url, json=payload, timeout=5)
    except Exception as e: print(f"Lỗi FB API: {e}")

def fb_get_user_name(psid):
    try:
        res = requests.get(f"https://graph.facebook.com/{psid}?fields=first_name,last_name&access_token={FB_PAGE_TOKEN}", timeout=3).json()
        return (res.get("last_name", "") + " " + res.get("first_name", "")).strip() or "Khách"
    except: return "Khách"

def fb_send_text(recipient_id, text):
    fb_send_api(recipient_id, {"text": text})

def fb_send_quick_replies(recipient_id, text, buttons):
    # buttons = [{"title": "Btn", "payload": "DATA"}]
    qr = [{"content_type": "text", "title": b["title"][:20], "payload": b["payload"]} for b in buttons[:13]]
    fb_send_api(recipient_id, {"text": text, "quick_replies": qr})

def fb_send_button_template(recipient_id, text, buttons):
    if not buttons: return fb_send_text(recipient_id, text)
    btn_arr = [{"type": "postback", "title": b["title"][:20], "payload": b["payload"]} for b in buttons[:3]]
    msg_data = {"attachment": {"type": "template", "payload": {"template_type": "button", "text": text[:640], "buttons": btn_arr}}}
    fb_send_api(recipient_id, msg_data)

def fb_send_shop(recipient_id, db_shop):
    elements = []
    for pkg, info in db_shop.items():
        elements.append({
            "title": f"🎁 Gói {info['name']}",
            "subtitle": f"💰 Giá: {info['price']:,}đ\n📦 Kho: {info['stock']} Key",
            "image_url": "https://images.unsplash.com/photo-1614064641913-a53b15c80764?w=500&q=80",
            "buttons": [{"type": "postback", "title": "💳 Mua Ngay", "payload": f"FB_BUY_{pkg}"}]
        })
    if elements:
        fb_send_api(recipient_id, {"attachment": {"type": "template", "payload": {"template_type": "generic", "elements": elements[:10]}}})
    else:
        fb_send_text(recipient_id, "Kho hiện đang trống!")

# ========================================================
# CORE FUNCTIONS
# ========================================================
def session_monitor():
    while True:
        time.sleep(15) 
        try:
            now = time.time()
            to_remove = [did for did, info in list(active_sessions.copy().items()) if now - info['last_seen'] > 35]
            if to_remove:
                db = load_db()
                for did in to_remove:
                    info = active_sessions.pop(did, None)
                    if info: add_log(db, "THOÁT OLM", info['key'], info['ip'], f"Device ({did})", info['olm_name'])
                save_db(db)
        except: pass

def keep_alive_and_backup():
    try: 
        requests.post(f"{TELEGRAM_API_URL}/setMyCommands", json={"commands": [{"command": "start", "description": "🏠 Menu Khách Hàng"}, {"command": "loaderkey", "description": "🔗 Kích Hoạt Tool Tàng Hình"}, {"command": "admin", "description": "👑 Chuyển Tới Quản Trị Server"}]}, timeout=5)
        requests.post(f"{TELEGRAM_API_URL}/setWebhook", json={"url": f"{WEB_URL}/webhook", "secret_token": WEBHOOK_SECRET}, timeout=5)
        
        requests.post(f"{ADMIN_TELEGRAM_API_URL}/setMyCommands", json={"commands": [{"command": "start", "description": "👑 Bảng Điều Khiển Admin"}]}, timeout=5)
        requests.post(f"{ADMIN_TELEGRAM_API_URL}/setWebhook", json={"url": f"{WEB_URL}/admin_webhook", "secret_token": WEBHOOK_SECRET}, timeout=5)
    except: pass
    while True:
        time.sleep(180)
        try: requests.get(WEB_URL, timeout=5)
        except: pass

threading.Thread(target=session_monitor, daemon=True).start()
threading.Thread(target=keep_alive_and_backup, daemon=True).start()

def add_log(db, action, key, ip, device, olm_name="N/A"):
    with db_lock:
        db.setdefault("logs", []).insert(0, {"time": int(time.time()), "action": action, "key": key, "ip": ip, "device": device, "olm_name": olm_name})
        db["logs"] = db["logs"][:500] 

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
        if kd.get('status') == 'banned': return False, "Key của bạn đã bị Admin khóa!"
        
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

def safe_tg_request(url, payload):
    for i in range(3):
        try:
            res = requests.post(url, json=payload, timeout=5)
            if res.status_code == 429: # Rate Limited
                time.sleep(int(res.headers.get("Retry-After", 1)))
                continue
            return res.json()
        except: time.sleep(1)
    return {}

def tg_send(chat_id, text, markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if markup: payload["reply_markup"] = markup
    res = safe_tg_request(f"{TELEGRAM_API_URL}/sendMessage", payload)
    return res.get("result", {}).get("message_id")

def tg_edit(chat_id, msg_id, text, markup=None):
    if not msg_id: return tg_send(chat_id, text, markup)
    payload = {"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": "HTML"}
    if markup: payload["reply_markup"] = markup
    res = safe_tg_request(f"{TELEGRAM_API_URL}/editMessageText", payload)
    if not res.get("ok") and "message is not modified" not in res.get("description", ""):
        return tg_send(chat_id, text, markup)
    return msg_id

def admin_tg_send(chat_id, text, markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if markup: payload["reply_markup"] = markup
    res = safe_tg_request(f"{ADMIN_TELEGRAM_API_URL}/sendMessage", payload)
    return res.get("result", {}).get("message_id")

def admin_tg_edit(chat_id, msg_id, text, markup=None):
    if not msg_id: return admin_tg_send(chat_id, text, markup)
    payload = {"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": "HTML"}
    if markup: payload["reply_markup"] = markup
    res = safe_tg_request(f"{ADMIN_TELEGRAM_API_URL}/editMessageText", payload)
    if not res.get("ok") and "message is not modified" not in res.get("description", ""):
        return admin_tg_send(chat_id, text, markup)
    return msg_id

def format_time(exp_ms, now_ms):
    if exp_ms == "permanent": return "Vĩnh viễn"
    if exp_ms == "pending": return "Chờ kích hoạt"
    try:
        rem = int(exp_ms) - now_ms
        if rem <= 0: return "Hết hạn"
        d, rem = divmod(rem, 86400000); h, rem = divmod(rem, 3600000); m, s = divmod(rem, 60000); s = s // 1000
        if d > 0: return f"{d} ngày {h} giờ"
        if h > 0: return f"{h} giờ {m} phút"
        return f"{m} phút {s} giây"
    except: return "Lỗi thời gian"

# ========================================================
# WEBHOOK ADMIN BOT TELEGRAM (GIỮ NGUYÊN)
# ========================================================
@app.route('/admin_webhook', methods=['POST', 'GET'])
def admin_telegram_webhook():
    if request.method == 'GET': return "OK", 200
    token = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if not hmac.compare_digest(token, WEBHOOK_SECRET):
        report_bad_signature(get_real_ip())
        return "Unauthorized", 401
    try:
        data = request.json
        if data:
            chat_id = str(data.get("message", {}).get("chat", {}).get("id", "")) or str(data.get("callback_query", {}).get("message", {}).get("chat", {}).get("id", ""))
            if chat_id:
                now_ms = int(time.time() * 1000)
                with anti_spam_lock:
                    if chat_id in anti_spam_cache and now_ms - anti_spam_cache[chat_id] < 500: return "OK", 200
                    anti_spam_cache[chat_id] = now_ms
            webhook_executor.submit(_async_process_admin_webhook, data)
    except: pass
    return "OK", 200

def _async_process_admin_webhook(data):
    try:
        if "message" in data:
            msg_obj = data["message"]
            from_obj = msg_obj.get("from", {})
        elif "callback_query" in data:
            msg_obj = data["callback_query"].get("message", {})
            from_obj = data["callback_query"].get("from", {})
        else: return 

        chat_id = str(msg_obj.get("chat", {}).get("id", ""))
        if not chat_id: return

        db = load_db()
        now_ms = int(time.time() * 1000)
        
        is_valid_admin = False
        with db_lock:
            if chat_id in db["bot_users"]:
                user = db["bot_users"][chat_id]
                if user.get("is_admin"):
                    exp = user.get("admin_exp", 0)
                    if exp == "permanent" or (isinstance(exp, int) and exp > now_ms): 
                        is_valid_admin = True
                    else:
                        user["is_admin"] = False
                        save_db(db)
        
        if not is_valid_admin:
            if "message" in data: admin_tg_send(chat_id, "🚫 <b>TỪ CHỐI TRUY CẬP</b>\nBạn không có quyền hoặc quyền Admin đã hết hạn ở Server này.")
            return

        msg_text = msg_obj.get("text", "").strip() if "message" in data else ""
        payload = data.get("callback_query", {}).get("data", "")
        msg_id = msg_obj.get("message_id")
        
        if "callback_query" in data:
            try: requests.post(f"{ADMIN_TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": data["callback_query"]["id"]}, timeout=2)
            except: pass

        if msg_text: safe_tg_request(f"{ADMIN_TELEGRAM_API_URL}/deleteMessage", {"chat_id": chat_id, "message_id": msg_id})

        with db_lock: user = db["bot_users"][chat_id]
        safe_name = escape(user.get("username", user.get("name", "Admin")))

        if msg_text.startswith("/"):
            with db_lock:
                user["admin_state"] = "none"
                user["main_menu_id"] = None
            if msg_text.upper().startswith("/START"): payload = "ADM_MAIN"

        with db_lock: adm_state = user.get("admin_state", "none")

        if msg_text and not msg_text.startswith("/") and adm_state != "none":
            if adm_state == "wait_create_key":
                parts = msg_text.split()
                if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
                    days = int(parts[0])
                    qty = int(parts[1])
                    pfx = parts[2].upper()
                    dur_ms = days * 86400000
                    gen_keys = []
                    with db_lock:
                        for _ in range(qty):
                            nk = f"{pfx}-{secrets.token_hex(4).upper()}"
                            db["keys"][nk] = {"exp": "pending", "durationMs": dur_ms, "maxDevices": 1, "devices": [], "known_ips": {}, "status": "active", "vip": True, "target": "olm", "bound_olm": "", "loader_enabled": True}
                            gen_keys.append(nk)
                        user["admin_state"] = "none"
                        log_admin_action(db, f"Tạo {qty} key {days} ngày ({pfx}) qua Bot", safe_name)
                        save_db(db)
                    k_str = "\n".join([f"<code>{k}</code>" for k in gen_keys])
                    user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], f"✅ <b>TẠO KEY THÀNH CÔNG</b>\n\n{k_str}", {"inline_keyboard": [[{"text": "🔙 Về Menu", "callback_data": "ADM_MAIN"}]]})
                else:
                    user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], "❌ Sai định dạng! Nhập lại (Ví dụ: <code>30 5 OLM</code>):", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MAIN"}]]})

            elif adm_state == "wait_add_bal":
                parts = msg_text.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    t_id = parts[0].strip()
                    amt = int(parts[1])
                    with db_lock:
                        if t_id in db["bot_users"]:
                            db["bot_users"][t_id]["balance"] = db["bot_users"][t_id].get("balance", 0) + amt
                            user["admin_state"] = "none"
                            log_admin_action(db, f"Nạp {amt}đ cho ID {t_id} qua Bot", safe_name)
                            save_db(db)
                            
                            # Cảnh báo nạp tiền: Dùng tg_send cho Tele, fb_send cho Messenger
                            is_fb = not t_id.isdigit()
                            if is_fb: fb_send_text(t_id, f"🎉 <b>Admin vừa nạp cho bạn +{amt:,}đ vào tài khoản!</b>")
                            else: tg_send(t_id, f"🎉 <b>Admin vừa nạp cho bạn +{amt:,}đ vào tài khoản!</b>")
                            
                            user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], f"✅ Nạp thành công <b>{amt:,}đ</b> cho <code>{t_id}</code>.", {"inline_keyboard": [[{"text": "🔙 Menu", "callback_data": "ADM_MAIN"}]]})
                        else:
                            user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], f"❌ ID {t_id} không tồn tại. Nhập lại:", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MAIN"}]]})

            elif adm_state == "wait_ban_user":
                t_id = msg_text.strip()
                with db_lock:
                    if t_id in db["bot_users"]:
                        db["bot_users"][t_id]["banned_until"] = "permanent"
                        db["bot_users"][t_id]["ban_reason"] = "Banned by Bot Admin"
                        for p in db["bot_users"][t_id].get("purchases", []):
                            if p["key"] in db.get("keys", {}): db["keys"][p["key"]]["status"] = "banned"
                        user["admin_state"] = "none"
                        log_admin_action(db, f"BAN vĩnh viễn {t_id} qua Bot", safe_name)
                        save_db(db)
                        
                        is_fb = not t_id.isdigit()
                        if is_fb: fb_send_text(t_id, "🚫 <b>TÀI KHOẢN BỊ KHÓA!</b>\nBạn đã bị Admin cấm vĩnh viễn khỏi hệ thống.")
                        else: tg_send(t_id, "🚫 <b>TÀI KHOẢN BỊ KHÓA!</b>\nBạn đã bị Admin cấm vĩnh viễn khỏi hệ thống.")
                        
                        user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], f"✅ Đã trảm ID <code>{t_id}</code> thành công.", {"inline_keyboard": [[{"text": "🔙 Menu", "callback_data": "ADM_MAIN"}]]})
                    else:
                        user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], "❌ ID không tồn tại. Nhập lại:", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MAIN"}]]})

            elif adm_state == "wait_chg_pass":
                new_pass = msg_text.strip()
                if len(new_pass) < 5:
                    user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], "❌ Mật khẩu phải > 5 ký tự. Nhập lại:", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MAIN"}]]})
                else:
                    with db_lock:
                        db["settings"]["admin_password_hash"] = hashlib.sha256(new_pass.encode()).hexdigest()
                        user["admin_state"] = "none"
                        log_admin_action(db, f"Đổi mật khẩu Web Admin qua Bot", safe_name)
                        save_db(db)
                    user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], f"✅ <b>ĐỔI MẬT KHẨU WEB ADMIN THÀNH CÔNG!</b>\nMật khẩu mới: <code>{new_pass}</code>", {"inline_keyboard": [[{"text": "🔙 Menu", "callback_data": "ADM_MAIN"}]]})

            elif adm_state == "wait_blacklist":
                ip = msg_text.strip()
                with db_lock:
                    if ip not in db.setdefault("banned_ips", []):
                        db["banned_ips"].append(ip)
                        user["admin_state"] = "none"
                        log_admin_action(db, f"Blacklist IP: {ip} qua Bot", safe_name)
                        save_db(db)
                        user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], f"✅ Đã ném IP <code>{ip}</code> vào Blacklist.", {"inline_keyboard": [[{"text": "🔙 Menu", "callback_data": "ADM_MAIN"}]]})
                    else:
                        user["admin_state"] = "none"
                        user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], f"⚠️ IP này đã bị chặn từ trước.", {"inline_keyboard": [[{"text": "🔙 Menu", "callback_data": "ADM_MAIN"}]]})

            elif adm_state == "wait_gift":
                parts = msg_text.split()
                if len(parts) >= 3 and parts[1].isdigit():
                    t_users = parts[0]
                    days = int(parts[1])
                    pfx = parts[2].upper()
                    dur_ms = days * 86400000
                    
                    target_ids = []
                    if t_users.upper() == 'ALL':
                        with db_lock: target_ids = list(db["bot_users"].keys())
                    else:
                        target_ids = t_users.split(',')
                    
                    for t_id in set(target_ids):
                        t_id = t_id.strip()
                        with db_lock:
                            if t_id in db["bot_users"]:
                                nk = f"{pfx}-{secrets.token_hex(4).upper()}"
                                gift_id = secrets.token_hex(6)
                                db["keys"][nk] = {"exp": "pending", "maxDevices": 1, "devices": [], "known_ips": {}, "status": "active", "vip": True, "target": "olm", "bound_olm": "", "loader_enabled": True, "durationMs": dur_ms}
                                db["bot_users"][t_id]["purchases"].insert(0, {"key": nk, "type": "🎁 Quà Tặng Admin", "time": now_ms})
                                db["bot_users"][t_id].setdefault("gifts", {})[gift_id] = {"key": nk, "name": f"Key VIP {days} Ngày"}
                                save_db(db)
                                
                                is_fb = not t_id.isdigit()
                                msg_gift = f"🎁 <b>BẠN VỪA NHẬN ĐƯỢC QUÀ TỪ ADMIN!</b>\nHãy nhấn nút bên dưới để mở hộp quà nhé."
                                if is_fb: fb_send_button_template(t_id, msg_gift, [{"title": "🎁 Mở Quà", "payload": f"OPEN_GIFT_{gift_id}"}])
                                else: tg_send(t_id, msg_gift, {"inline_keyboard": [[{"text": "🎁 Mở Quà Ngay", "callback_data": f"OPEN_GIFT_{gift_id}"}]]})
                    
                    with db_lock: 
                        user["admin_state"] = "none"
                        log_admin_action(db, f"Tặng quà cho {len(target_ids)} user ({days} ngày) qua Bot", safe_name)
                    user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], f"✅ Đã phát quà thành công!", {"inline_keyboard": [[{"text": "🔙 Menu", "callback_data": "ADM_MAIN"}]]})
                else:
                    user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], "❌ Sai định dạng! Nhập lại (Ví dụ: <code>ALL 30 GIFT</code>):", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MAIN"}]]})

        if payload:
            if payload == "ADM_MAIN":
                with db_lock: user["admin_state"] = "none"
                txt = "👑 <b>BẢNG ĐIỀU KHIỂN SERVER (ĐỘC QUYỀN)</b>\n➖➖➖➖➖➖➖➖➖➖\n\nChế độ quyền lực cao nhất. Hãy chọn chức năng:"
                markup = {
                    "inline_keyboard": [
                        [{"text": "📊 Thống Kê Server", "callback_data": "ADM_STATS"}],
                        [{"text": "🔑 Tạo Key Nhanh", "callback_data": "ADM_CREATE"}, {"text": "🎁 Phát Quà (Túi Đồ)", "callback_data": "ADM_GIFT"}],
                        [{"text": "💰 Nạp Tiền User", "callback_data": "ADM_ADD_BAL"}, {"text": "🚫 Trảm User (BAN)", "callback_data": "ADM_BAN"}],
                        [{"text": "⚙️ Đổi Pass Web Admin", "callback_data": "ADM_PASS"}],
                        [{"text": "🛑 Blacklist IP", "callback_data": "ADM_BLACKLIST"}, {"text": "☁️ Backup DB", "callback_data": "ADM_BACKUP"}]
                    ]
                }
                user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], txt, markup)
            
            elif payload == "ADM_STATS":
                with db_lock:
                    total_u = len(db.get("bot_users", {}))
                    total_k = len(db.get("keys", {}))
                    today_start = int(datetime.datetime.combine(datetime.date.today(), datetime.time.min).timestamp() * 1000)
                    rev_today = sum(item["amount"] for item in db.get("revenue_logs", []) if item["time"] >= today_start)
                    banned_ips_c = len(db.get("banned_ips", []))
                    
                txt = f"📊 <b>THỐNG KÊ MÁY CHỦ (LIVE)</b>\n➖➖➖➖➖➖➖➖\n👥 Tổng User: <b>{total_u}</b>\n🔑 Tổng Key: <b>{total_k}</b>\n💸 Doanh thu nay: <b>{rev_today:,}đ</b>\n🛡️ IP bị Firewall chặn: <b>{banned_ips_c}</b> IP"
                markup = {"inline_keyboard": [[{"text": "🔙 Quay Lại", "callback_data": "ADM_MAIN"}]]}
                user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], txt, markup)
                
            elif payload == "ADM_CREATE":
                with db_lock: user["admin_state"] = "wait_create_key"
                txt = "🔑 <b>TẠO KEY OLM VIP NHANH</b>\n\n📝 Nhập theo cú pháp: <code>Số_Ngày Số_Lượng Prefix</code>\n👉 Ví dụ tạo 5 key 30 ngày: <code>30 5 OLM</code>"
                user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], txt, {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MAIN"}]]})
            
            elif payload == "ADM_ADD_BAL":
                with db_lock: user["admin_state"] = "wait_add_bal"
                txt = "💰 <b>NẠP TIỀN CHO USER</b>\n\n📝 Nhập: <code>ID_Khách Số_Tiền</code>\n👉 Ví dụ: <code>61234567 50000</code>"
                user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], txt, {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MAIN"}]]})

            elif payload == "ADM_BAN":
                with db_lock: user["admin_state"] = "wait_ban_user"
                txt = "🚫 <b>TRẢM USER & HỦY TOÀN BỘ KEY</b>\n\n📝 Nhập chính xác <code>ID</code> của User cần khóa vĩnh viễn:"
                user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], txt, {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MAIN"}]]})
            
            elif payload == "ADM_GIFT":
                with db_lock: user["admin_state"] = "wait_gift"
                txt = "🎁 <b>PHÁT QUÀ VÀO TÚI ĐỒ</b>\n\n📝 Nhập: <code>ID(hoặc ALL) Số_Ngày Prefix_Key</code>\n👉 Gửi toàn Server key 7 ngày: <code>ALL 7 QUATANG</code>"
                user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], txt, {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MAIN"}]]})
            
            elif payload == "ADM_PASS":
                with db_lock: user["admin_state"] = "wait_chg_pass"
                txt = "⚙️ <b>ĐỔI MẬT KHẨU WEB ADMIN</b>\n\n📝 Hãy nhập mật khẩu mới mà bạn muốn thiết lập cho trang quản trị Web:"
                user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], txt, {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MAIN"}]]})
            
            elif payload == "ADM_BLACKLIST":
                with db_lock: user["admin_state"] = "wait_blacklist"
                txt = "🛑 <b>BLACKLIST IP</b>\n\n📝 Nhập IP của kẻ tấn công để chặn đứng mọi kết nối từ IP này đến Server:"
                user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], txt, {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MAIN"}]]})
            
            elif payload == "ADM_BACKUP":
                try:
                    with open(DB_FILE, 'rb') as f:
                        requests.post(
                            f"{ADMIN_TELEGRAM_API_URL}/sendDocument", 
                            data={"chat_id": chat_id, "caption": f"☁️ <b>BACKUP DATABASE</b>\nThời gian: {time.strftime('%Y-%m-%d %H:%M:%S')}", "parse_mode": "HTML"}, 
                            files={"document": ("database.json", f)},
                            timeout=10
                        )
                    with db_lock: log_admin_action(db, f"Đã kéo File Backup qua Bot", safe_name)
                except: pass
    except Exception as e: pass


# ========================================================
# WEBHOOK MESSENGER FACEBOOK MAIN BOT
# ========================================================
@app.route('/fb_webhook', methods=['POST', 'GET'])
def facebook_webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode and token:
            if mode == 'subscribe' and token == FB_VERIFY_TOKEN:
                return challenge, 200
            else:
                return 'Forbidden', 403
        return 'OK', 200
        
    if request.method == 'POST':
        data = request.json
        if data and data.get('object') == 'page':
            for entry in data.get('entry', []):
                for event in entry.get('messaging', []):
                    sender_id = event['sender']['id']
                    
                    now_ms = int(time.time() * 1000)
                    with anti_spam_lock:
                        if sender_id in anti_spam_cache and now_ms - anti_spam_cache[sender_id] < 500: continue
                        anti_spam_cache[sender_id] = now_ms

                    if event.get('message') and event['message'].get('text'):
                        webhook_executor.submit(_async_process_fb_webhook, sender_id, event['message']['text'], None)
                    elif event.get('postback') and event['postback'].get('payload'):
                        webhook_executor.submit(_async_process_fb_webhook, sender_id, "", event['postback']['payload'])
                    elif event.get('message') and event['message'].get('quick_reply'):
                        webhook_executor.submit(_async_process_fb_webhook, sender_id, "", event['message']['quick_reply']['payload'])
        return 'EVENT_RECEIVED', 200

def _async_process_fb_webhook(sender_id, msg_text, payload):
    try:
        global anti_spam_cache
        global _sys_metrics_buffer
        now_ms = int(time.time() * 1000)
        
        db = load_db()
        msg_text = msg_text.strip()
        cmd_lower = msg_text.lower()
        
        if db.get("settings", {}).get("maintenance_mode", False):
            is_admin = False
            with db_lock:
                if str(sender_id) in db["bot_users"] and db["bot_users"][str(sender_id)].get("is_admin"): is_admin = True
            if not is_admin:
                if msg_text: fb_send_text(sender_id, "⚙️ <b>HỆ THỐNG ĐANG BẢO TRÌ NÂNG CẤP!</b>\nVui lòng quay lại sau ít phút nữa nhé. Xin lỗi vì sự bất tiện này!")
                return
        
        with anti_spam_lock:
            if len(_sys_metrics_buffer) > 5000: _sys_metrics_buffer.clear()
            history = _sys_metrics_buffer.get(sender_id, [])
            history = [t for t in history if now_ms - t < 10000]
            history.append(now_ms)
            _sys_metrics_buffer[sender_id] = history
            trigger_auto_ban = len(history) > 6

        with db_lock: is_new_user = sender_id not in db["bot_users"]
            
        if is_new_user:
            safe_name = fb_get_user_name(sender_id)
            with db_lock:
                max_users = db.get("settings", {}).get("max_users", 500)
                if len(db["bot_users"]) >= max_users:
                    fb_send_text(sender_id, "🚫 <b>HỆ THỐNG ĐÓNG CỬA!</b>\nServer đã đạt giới hạn số lượng tài khoản. Vui lòng quay lại sau.")
                    return

                db["bot_users"][sender_id] = {"name": safe_name, "username": "", "balance": 0, "resets": 3, "state": "none", "is_admin": False, "purchases": [], "gifts": {}, "notices": [], "loader_active": False, "loader_key": "", "loader_olm": "", "main_menu_id": None, "live_msg_id": None, "live_msg_type": None, "admin_exp": 0, "admin_key": "", "banned_until": 0, "ban_reason": "", "approved": False, "approval_time": 0, "temp_key": "", "referred_by": "", "admin_state": "none"}
                admin_items = list(db["bot_users"].items())
                webhook_url = db.get("settings", {}).get("discord_webhook", "")
                save_db(db)
                
            webhook_executor.submit(send_discord_webhook, webhook_url, "Khách FB Mới 🎉", f"Tên: {safe_name}\nID: {sender_id}")
            for uid, uinfo in admin_items:
                if uinfo.get("is_admin"): admin_tg_send(uid, f"🚨 <b>CÓ KHÁCH FB MỚI (CHỜ DUYỆT)!</b>\n👤 Tên: {escape(safe_name)}\n🆔 ID: <code>{sender_id}</code>")
            
            fb_send_text(sender_id, "👋 <b>CHÀO MỪNG BẠN ĐẾN VỚI HỆ THỐNG AUTO OLM!</b>\n\nTài khoản của bạn đang chờ Admin duyệt hoặc bạn có thể mua Key để sử dụng ngay.\nHãy gõ lệnh /start để mở Menu nhé!")
            return

        with db_lock: user = db["bot_users"][sender_id]
        safe_name = user.get("name", "Khách")

        if trigger_auto_ban and not user.get("is_admin"):
            with db_lock:
                db["bot_users"][sender_id]["banned_until"] = "permanent"
                db["bot_users"][sender_id]["ban_reason"] = "Spam lệnh liên tục (Auto Ban FB)"
                save_db(db)
            return

        if not user.get("is_admin"):
            banned_until = user.get("banned_until", 0)
            if banned_until == "permanent" or (isinstance(banned_until, int) and banned_until > now_ms):
                if msg_text: fb_send_text(sender_id, f"🚫 <b>TÀI KHOẢN CỦA BẠN ĐÃ BỊ KHÓA!</b>\n📝 Lý do: {user.get('ban_reason', 'Vi phạm chính sách')}")
                return
            
            if not user.get("approved", False):
                if msg_text or payload:
                    appr_time = user.get("approval_time", 0)
                    if appr_time == 0: fb_send_text(sender_id, "⏳ <b>HỆ THỐNG BẢO MẬT ADMIN</b>\n\nTài khoản FB của bạn đang chờ duyệt. Vui lòng kiên nhẫn!")
                    elif appr_time > now_ms: fb_send_text(sender_id, f"⏳ <b>ĐANG CHỜ VÀO BOT</b>\nBạn sẽ được vào Bot sau: {format_time(appr_time, now_ms)}")
                    else:
                        with db_lock: user["approved"] = True
                        save_db(db)
                        fb_send_text(sender_id, "🎉 <b>PHÊ DUYỆT THÀNH CÔNG!</b>\nBạn đã có thể sử dụng Bot bình thường. Gõ /start để bắt đầu.")
                return 

        if cmd_lower in ['/start', 'menu', 'bắt đầu', 'hello', 'hi', 'get started']:
            payload = "MENU_MAIN"
            with db_lock: user["state"] = "none"

        if msg_text.startswith("/"):
            with db_lock: user["state"] = "none"

        with db_lock: user_state = user["state"]

        # XỬ LÝ NHẬP TEXT TỪ KHÁCH HÀNG FB
        if msg_text and not msg_text.startswith("/") and user_state != "none":
            if user_state == "wait_loader_key":
                k = msg_text
                valid, msg = _core_validate(db, k)
                if valid: 
                    with db_lock:
                        user["temp_key"] = k
                        user["state"] = "wait_loader_olm"
                        save_db(db)
                    fb_send_text(sender_id, f"✅ Key Hợp Lệ!\n\n👤 Nhập Tên OLM bạn muốn cho phép hoạt động (Ví dụ: hp_luongvantuyen):")
                else: 
                    fb_send_button_template(sender_id, f"❌ {msg}\n\n🔑 Vui lòng nhập lại Key khác hoặc thoát:", [{"title": "🔙 Quay Lại", "payload": "LOADER_MENU"}])
            
            elif user_state == "wait_loader_olm":
                olm_target = msg_text
                with db_lock:
                    k = user.get("temp_key")
                    if k and k in db["keys"] and not db["keys"][k].get("bound_olm"): db["keys"][k]["bound_olm"] = olm_target
                    user["state"] = "none"
                    save_db(db)
                fb_send_text(sender_id, f"🟢 ĐÃ GHIM THÀNH CÔNG!\nKey {k} hiện tại chỉ hoạt động trên OLM: {olm_target}.")
                add_log(db, "ĐĂNG KÝ OLM", k, "Messenger", f"Khách: {safe_name}", olm_target)
            
            elif user_state.startswith("wait_qty_V_"):
                pkg = user_state.replace("wait_qty_", "")
                if msg_text.isdigit() and int(msg_text) > 0:
                    qty = int(msg_text)
                    gen_keys = []
                    
                    with db_lock: 
                        shop_info = db["shop"].get(pkg, {"price": 0, "stock": 0, "dur_ms": 0, "name": ""})
                        cost = shop_info.get("price", 0)
                        dur_ms = shop_info.get("dur_ms", 0)
                        name = shop_info.get("name", "")
                        stock = shop_info.get("stock", 0)
                        total_cost = cost * qty
                        
                        if stock < qty: 
                            fb_send_button_template(sender_id, f"❌ Kho Key Không Đủ! Kho chỉ còn lại {stock} Key. Vui lòng mua ít hơn.", [{"title": "🔙 Mua Lại", "payload": "BUY_VIP"}])
                        elif db["bot_users"][sender_id].get("balance", 0) >= total_cost:
                            db["bot_users"][sender_id]["balance"] -= total_cost
                            db["shop"].setdefault(pkg, {"stock": stock})
                            db["shop"][pkg]["stock"] -= qty
                            db.setdefault("revenue_logs", []).append({"time": now_ms, "amount": total_cost})
                            
                            for _ in range(qty):
                                nk = f"OLM-{secrets.token_hex(4).upper()}"
                                db["keys"][nk] = {"exp": "pending", "durationMs": dur_ms, "maxDevices": 1, "devices": [], "known_ips": {}, "status": "active", "vip": True, "target": "olm", "bound_olm": "", "loader_enabled": True}
                                db["bot_users"][sender_id]["purchases"].insert(0, {"key": nk, "type": f"VIP {name}", "time": now_ms})
                                gen_keys.append(nk)
                            user["state"] = "none"
                            save_db(db)
                            
                            # Thông báo Admin Telegram
                            for u_id, u_info in db["bot_users"].items():
                                if u_info.get("username", "").lower() in ["@luongtuyen20", "luongtuyen20"]:
                                    webhook_executor.submit(admin_tg_send, u_id, f"💸 <b>CÓ ĐƠN FB MỚI!</b>\n👤 Khách: {safe_name}\n📦 SP: {qty} x {name}\n💰 Thu: <b>+{total_cost:,}đ</b>")
                                    break

                            k_str = "\n".join([f"🔑 {k}" for k in gen_keys])
                            fb_send_button_template(sender_id, f"🎊 MUA THÀNH CÔNG!\n{k_str}\n\nTB hỗ trợ: 1 Máy\nGói: {name}", [{"title": "🔗 Cài Đặt Spoofer", "payload": "LOADER_MENU"}])
                            for gk in gen_keys: add_log(db, "MUA KEY (FB)", gk, "Messenger", f"Khách: {safe_name}", "N/A")
                        else: 
                            fb_send_button_template(sender_id, "❌ Số dư không đủ! Vui lòng nạp thêm tiền.", [{"title": "🔙 Menu", "payload": "MENU_MAIN"}])
                else: 
                    fb_send_quick_replies(sender_id, "❌ Vui lòng nhập số lượng hợp lệ (1, 2, 3...)!", [{"title": "🔙 Hủy Mua", "payload": "BUY_VIP"}])
            
            elif user_state == "wait_reset_key":
                with db_lock:
                    rsts = user.get("resets", 0)
                    if msg_text in db["keys"] and rsts > 0:
                        db["keys"][msg_text]["devices"] = []
                        db["keys"][msg_text]["known_ips"] = {}
                        db["keys"][msg_text]["bound_olm"] = "" 
                        user["resets"] -= 1
                        user["state"] = "none"
                        save_db(db)
                        fb_send_button_template(sender_id, f"✅ Reset thành công! Key {msg_text} đã được gỡ sạch mọi Thiết Bị và liên kết OLM.", [{"title": "🏠 Trang Chủ", "payload": "MENU_MAIN"}])
                    elif rsts <= 0:
                        user["state"] = "none"
                        save_db(db)
                        fb_send_button_template(sender_id, "❌ Bạn đã hết lượt Reset.", [{"title": "🏠 Trang Chủ", "payload": "MENU_MAIN"}])
                    else:
                        fb_send_quick_replies(sender_id, "❌ Key không tồn tại! Vui lòng nhập lại:", [{"title": "🏠 Hủy", "payload": "MENU_MAIN"}])

        # XỬ LÝ PAYLOAD TỪ BUTTONS FB
        if payload:
            if payload.startswith("OPEN_GIFT_"):
                gift_id = payload.split("OPEN_GIFT_")[1]
                with db_lock:
                    gift = user.get("gifts", {}).pop(gift_id, None)
                    if gift:
                        fb_send_button_template(sender_id, f"🎉 BÙM! MỞ QUÀ THÀNH CÔNG!\nBạn nhận được: {gift['name']}\n🔑 Key của bạn: {gift['key']}", [{"title": "🏠 Menu Chính", "payload": "MENU_MAIN"}])
                        save_db(db)
                    else:
                        fb_send_button_template(sender_id, "❌ Hộp quà này đã mở hoặc không tồn tại!", [{"title": "🏠 Menu Chính", "payload": "MENU_MAIN"}])
                return

            if payload == "MENU_MAIN":
                with db_lock: 
                    bal = user.get('balance', 0)
                    rst = user.get('resets', 0)
                txt = f"👋 Chào mừng {safe_name}!\n\n💳 THÔNG TIN:\n🆔 ID FB: {sender_id}\n💰 Số dư: {bal:,}đ\n🔄 Reset Key: {rst}/3\n\n👇 Chọn dịch vụ:"
                qr_buttons = [
                    {"title": "🛒 Mua Key VIP", "payload": "BUY_VIP"},
                    {"title": "🔗 Cài Đặt Spoofer", "payload": "LOADER_MENU"},
                    {"title": "🔄 Reset Thiết Bị", "payload": "RESET"},
                    {"title": "🩺 Chẩn Đoán Lỗi", "payload": "DIAGNOSE"}
                ]
                fb_send_quick_replies(sender_id, txt, qr_buttons)

            elif payload == "DIAGNOSE":
                with db_lock:
                    user["state"] = "none"
                    k = user.get("loader_key") or (user.get("purchases")[0]["key"] if user.get("purchases") else None)
                    if not k: txt = "🩺 Bạn chưa nhập Key hoặc chưa mua Key nào để chẩn đoán."
                    else:
                        kd = db.get("keys", {}).get(k)
                        if not kd: txt = f"🩺 Key {k} không tồn tại."
                        else:
                            st = kd.get("status")
                            exp = kd.get("exp")
                            if st == "banned": txt = "🔴 Bệnh: Key đang bị KHÓA. Liên hệ Admin."
                            elif exp != "permanent" and exp != "pending" and int(exp) < now_ms: txt = "🔴 Bệnh: Key đã HẾT HẠN."
                            else: txt = "🟢 Khỏe mạnh: Key hoạt động bình thường trên Server."
                fb_send_button_template(sender_id, txt, [{"title": "🔙 Menu", "payload": "MENU_MAIN"}])

            elif payload == "LOADER_MENU":
                with db_lock: user["state"] = "none"
                fb_send_button_template(sender_id, "🔗 QUẢN LÝ SCRIPT OLM\n\nChọn chức năng:", [
                    {"title": "🔑 Nhập Key", "payload": "LOADER_ENTER_KEY"},
                    {"title": "🚀 Lấy File Script", "payload": "LOADER_FILE_OLM"},
                    {"title": "🏠 Menu", "payload": "MENU_MAIN"}
                ])

            elif payload == "LOADER_ENTER_KEY":
                with db_lock: user["state"] = "wait_loader_key"
                save_db(db)
                fb_send_text(sender_id, "🔗 KẾT NỐI SCRIPT OLM\n\n🔑 Vui lòng dán Mã Key của bạn vào đây để hệ thống nhận diện:")

            elif payload == "LOADER_FILE_OLM":
                txt = f"📂 CÀI ĐẶT SCRIPT\n\n📥 Link Script OLM:\n{GITHUB_SCRIPT_URL}\n\n🔐 Mật khẩu giải nén: {SCRIPT_PASSWORD}"
                fb_send_button_template(sender_id, txt, [{"title": "🔙 Menu", "payload": "MENU_MAIN"}])

            elif payload == "BUY_VIP":
                with db_lock: s = db.get("shop") or {}
                fb_send_text(sender_id, "🛒 BẢNG GIÁ KEY VIP: Lướt ngang để xem các gói và bấm Mua.")
                fb_send_shop(sender_id, s)

            elif payload.startswith("FB_BUY_V_"):
                pkg = payload.replace("FB_BUY_", "")
                with db_lock: user["state"] = f"wait_qty_{pkg}"
                save_db(db)
                fb_send_quick_replies(sender_id, "🔢 Vui lòng nhắn tin SỐ LƯỢNG bạn muốn mua (Ví dụ: 1 hoặc 2):", [{"title": "🔙 Hủy", "payload": "BUY_VIP"}])

            elif payload == "RESET":
                with db_lock: rsts = user.get("resets", 0)
                if rsts <= 0: fb_send_button_template(sender_id, "❌ Bạn đã hết lượt Reset.", [{"title": "🔙 Menu", "payload": "MENU_MAIN"}])
                else:
                    with db_lock: user["state"] = "wait_reset_key"
                    save_db(db)
                    fb_send_text(sender_id, "📝 Gửi chính xác Mã Key cần Reset thiết bị vào đây:")
    except Exception as e: pass

# ========================================================
# WEBHOOK MAIN BOT (TELEGRAM KHÁCH HÀNG GIỮ NGUYÊN)
# ========================================================
@app.route('/webhook', methods=['POST', 'GET'])
def telegram_webhook():
    if request.method == 'GET': return "OK", 200
    token = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if not hmac.compare_digest(token, WEBHOOK_SECRET):
        report_bad_signature(get_real_ip())
        return "Unauthorized", 401
    try:
        data = request.json
        if data:
            chat_id = str(data.get("message", {}).get("chat", {}).get("id", "")) or str(data.get("callback_query", {}).get("message", {}).get("chat", {}).get("id", ""))
            if chat_id:
                now_ms = int(time.time() * 1000)
                with anti_spam_lock:
                    if chat_id in anti_spam_cache and now_ms - anti_spam_cache[chat_id] < 500: return "OK", 200
                    anti_spam_cache[chat_id] = now_ms
            webhook_executor.submit(_async_process_webhook, data)
    except: pass
    return "OK", 200

def _async_process_webhook(data):
    try:
        if "message" in data:
            msg_obj = data["message"]
            from_obj = msg_obj.get("from", {})
        elif "callback_query" in data:
            msg_obj = data["callback_query"].get("message", {})
            from_obj = data["callback_query"].get("from", {})
        else: return 

        chat_id = str(msg_obj.get("chat", {}).get("id", ""))
        if not chat_id: return

        global anti_spam_cache
        global _sys_metrics_buffer
        now_ms = int(time.time() * 1000)
        trigger_auto_ban = False
        
        db = load_db()
        
        if db.get("settings", {}).get("maintenance_mode", False):
            is_admin = False
            with db_lock:
                if str(chat_id) in db["bot_users"] and db["bot_users"][str(chat_id)].get("is_admin"):
                    is_admin = True
            if not is_admin:
                if "message" in data:
                    tg_send(chat_id, "⚙️ <b>HỆ THỐNG ĐANG BẢO TRÌ NÂNG CẤP!</b>\nVui lòng quay lại sau ít phút nữa nhé. Xin lỗi vì sự bất tiện này!")
                return
        
        with anti_spam_lock:
            if len(_sys_metrics_buffer) > 5000: _sys_metrics_buffer.clear()
            history = _sys_metrics_buffer.get(chat_id, [])
            history = [t for t in history if now_ms - t < 10000]
            history.append(now_ms)
            _sys_metrics_buffer[chat_id] = history
            
            if len(history) > 6: trigger_auto_ban = True

        sid = chat_id
        msg_text = msg_obj.get("text", "").strip() if "message" in data else ""
        payload = data.get("callback_query", {}).get("data", "")
        msg_id = msg_obj.get("message_id")
        
        user_name = from_obj.get("first_name", "Khách")
        tg_username = from_obj.get("username", "")
        
        if "callback_query" in data:
            try: requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": data["callback_query"]["id"]}, timeout=2)
            except: pass

        safe_name = user_name.replace("<", "").replace(">", "")
        f_uname = f"@{tg_username}" if tg_username else ""
        
        ai_banned_reason = ""
        if has_weird_name(safe_name) or (tg_username and has_weird_name(tg_username)):
            trigger_auto_ban = True
            ai_banned_reason = "AI phát hiện Nick chứa ký tự nước ngoài/nick rác"
        elif trigger_auto_ban:
            ai_banned_reason = "Hệ thống ngầm phát hiện Tool Spam lệnh"

        if trigger_auto_ban:
            was_already_banned = False
            with db_lock:
                if sid in db["bot_users"]:
                    if str(db["bot_users"][sid].get("banned_until")) == "permanent":
                        was_already_banned = True
                    elif not db["bot_users"][sid].get("is_admin"):
                        db["bot_users"][sid]["banned_until"] = "permanent"
                        db["bot_users"][sid]["ban_reason"] = ai_banned_reason
                        for p in db["bot_users"][sid].get("purchases", []):
                            if p["key"] in db.setdefault("keys", {}): db["keys"][p["key"]]["status"] = "banned"
                else:
                    db["bot_users"][sid] = {"name": safe_name, "username": f_uname, "balance": 0, "resets": 3, "state": "none", "is_admin": False, "purchases": [], "gifts": {}, "notices": [], "loader_active": False, "loader_key": "", "loader_olm": "", "main_menu_id": None, "live_msg_id": None, "live_msg_type": None, "admin_exp": 0, "admin_key": "", "banned_until": "permanent", "ban_reason": ai_banned_reason, "approved": False, "approval_time": 0, "temp_key": "", "referred_by": "", "admin_state": "none"}
                
                if not was_already_banned:
                    db.setdefault("security_alerts", []).insert(0, {
                        "time": now_ms,
                        "user": f"{safe_name} {f_uname}",
                        "id": sid,
                        "reason": ai_banned_reason
                    })
                    db["security_alerts"] = db["security_alerts"][:50]
                save_db(db)
                
            if not was_already_banned:
                with db_lock: admin_uids = [u for u, i in db["bot_users"].items() if i.get("is_admin")]
                for a_id in admin_uids:
                    admin_tg_send(a_id, f"🚨 <b>AI VỪA TỬ HÌNH 1 HACKER!</b>\n👤 Tên: {escape(safe_name)} {escape(f_uname)}\n🆔 ID: <code>{sid}</code>\n📝 Lý do: {ai_banned_reason}")
            return
        
        with db_lock: is_new_user = sid not in db["bot_users"]
            
        if is_new_user:
            with db_lock:
                max_users = db.get("settings", {}).get("max_users", 500)
                curr_users_count = len(db["bot_users"])
                
            if curr_users_count >= max_users:
                with anti_spam_lock:
                    last_warn = _sys_metrics_buffer.get(f"warn_{sid}", 0)
                    should_warn = last_warn < now_ms - 60000
                    if should_warn: _sys_metrics_buffer[f"warn_{sid}"] = now_ms
                if should_warn: tg_send(sid, "🚫 <b>HỆ THỐNG ĐÓNG CỬA!</b>\nServer đã đạt giới hạn số lượng tài khoản tối đa. Vui lòng quay lại sau.")
                return

            ref_code = ""
            if msg_text.startswith("/start "): ref_code = msg_text.split(" ")[1]

            with db_lock:
                db["bot_users"][sid] = {"name": safe_name, "username": f_uname, "balance": 0, "resets": 3, "state": "none", "is_admin": False, "purchases": [], "gifts": {}, "notices": [], "loader_active": False, "loader_key": "", "loader_olm": "", "main_menu_id": None, "live_msg_id": None, "live_msg_type": None, "admin_exp": 0, "admin_key": "", "banned_until": 0, "ban_reason": "", "approved": False, "approval_time": 0, "temp_key": "", "referred_by": ref_code, "admin_state": "none"}
                admin_items = list(db["bot_users"].items())
                webhook_url = db.get("settings", {}).get("discord_webhook", "")
                save_db(db)
                
            webhook_executor.submit(send_discord_webhook, webhook_url, "Khách Hàng Mới 🎉", f"Tên: {safe_name}\nID: {sid}\nUsername: {f_uname}")
            
            for uid, uinfo in admin_items:
                if uinfo.get("is_admin"): admin_tg_send(uid, f"🚨 <b>CÓ KHÁCH MỚI (CHỜ DUYỆT)!</b>\n👤 Tên: {escape(safe_name)}\n🆔 ID: <code>{sid}</code>")
            
            tg_send(sid, "👋 <b>CHÀO MỪNG BẠN ĐẾN VỚI HỆ THỐNG AUTO OLM!</b>\n\nTài khoản của bạn đang chờ Admin duyệt hoặc bạn có thể mua Key để sử dụng ngay.\nHãy gõ lệnh /start để mở Menu nhé!")
        else:
            with db_lock:
                db["bot_users"][sid]["username"] = f_uname
                db["bot_users"][sid]["name"] = safe_name
            
        with db_lock: user = db["bot_users"][sid]

        if not user.get("is_admin"):
            banned_until = user.get("banned_until", 0)
            if banned_until == "permanent" or (isinstance(banned_until, int) and banned_until > now_ms):
                if msg_text: tg_send(sid, f"🚫 <b>TÀI KHOẢN CỦA BẠN ĐÃ BỊ KHÓA!</b>\n📝 Lý do: {escape(user.get('ban_reason', 'Vi phạm chính sách'))}\n⏳ Thời hạn: {'Vĩnh viễn' if banned_until == 'permanent' else format_time(banned_until, now_ms)}")
                return
            
            if not user.get("approved", False):
                if msg_text or "callback_query" in data:
                    appr_time = user.get("approval_time", 0)
                    if appr_time == 0: tg_send(sid, "⏳ <b>HỆ THỐNG BẢO MẬT ADMIN</b>\n\nTài khoản của bạn đang chờ Admin phê duyệt để sử dụng Bot.\n✅ Vui lòng kiên nhẫn chờ đợi, Admin sẽ xử lý sớm nhất!")
                    elif appr_time > now_ms:
                        rem_str = format_time(appr_time, now_ms)
                        tg_send(sid, f"⏳ <b>ĐANG CHỜ VÀO BOT</b>\n\nAdmin đã xác nhận. Bot đang tải tài nguyên. Bạn sẽ được truy cập vào Bot sau:\n👉 <b>{rem_str}</b>")
                    else:
                        with db_lock: user["approved"] = True
                        tg_send(sid, "🎉 <b>PHÊ DUYỆT THÀNH CÔNG!</b>\nBạn đã có thể sử dụng Bot bình thường. Hãy gõ /start để bắt đầu.")
                        save_db(db)
                return 

        if msg_text: safe_tg_request(f"{TELEGRAM_API_URL}/deleteMessage", {"chat_id": sid, "message_id": msg_id})

        if msg_text.startswith("/"):
            with db_lock:
                user["state"] = "none"
                user["live_msg_type"] = None
                user["main_menu_id"] = None 

            if msg_text.upper().startswith("/START"): payload = "MENU_MAIN"
            elif msg_text.upper().startswith("/LOADERKEY"): payload = "LOADER_MENU"
            elif msg_text.upper().startswith("/ADMIN"):
                is_valid_admin = False
                with db_lock:
                    if user.get("is_admin"):
                        exp = user.get("admin_exp", 0)
                        if exp == "permanent" or (isinstance(exp, int) and exp > now_ms): is_valid_admin = True
                
                if is_valid_admin: 
                    tg_send(sid, f"👑 <b>BẢNG ĐIỀU KHIỂN SERVER TỪ XA</b>\n\nHệ thống đã cấp cho bạn 1 Bot chuyên dụng để quản lý Server. Hãy truy cập ngay tại đây: @{ADMIN_BOT_USERNAME}")
                else:
                    with db_lock: user["state"] = "wait_admin_key"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "🔐 <b>BẢO MẬT SERVER</b>\nBạn chưa có quyền Admin. Vui lòng nhập <code>Key Admin</code> để mở khóa:")
                save_db(db)
                return

        with db_lock: user_state = user["state"]

        if msg_text and not msg_text.startswith("/") and user_state != "none":
            if user_state == "wait_loader_key":
                k = msg_text
                valid, msg = _core_validate(db, k)
                if valid: 
                    with db_lock:
                        user["temp_key"] = k
                        user["state"] = "wait_loader_olm"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ Key Hợp Lệ!\n\n👤 Nhập <b>Tài khoản OLM</b> bạn muốn cho phép hoạt động (Ví dụ: <code>hp_luongvantuyen</code>):")
                else: user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"❌ <b>{msg}</b>\n\n🔑 Vui lòng nhập lại Key khác:")
            
            elif user_state == "wait_loader_olm":
                olm_target = msg_text
                with db_lock:
                    k = user.get("temp_key")
                    if k and k in db["keys"] and not db["keys"][k].get("bound_olm"): db["keys"][k]["bound_olm"] = olm_target
                    user["state"] = "none"
                    user["loader_active"] = True
                    user["loader_key"] = k
                    user["loader_olm"] = olm_target
                    user["live_msg_type"] = "loader"
                
                txt = f"🟢 <b>BẢNG ĐIỀU KHIỂN SCRIPT LOADER</b>\n➖➖➖➖➖➖➖➖➖➖➖➖\n🔑 Key sử dụng: <code>{k}</code>\n👤 OLM Cho Phép: <b>{olm_target}</b>\n⚡ Trạng thái: Đang kết nối URL\n\n📥 <b>URL CÀI ĐẶT SCRIPT:</b>\n<code>{GITHUB_SCRIPT_URL}</code>\n🔐 <b>Mật khẩu:</b> <code>{SCRIPT_PASSWORD}</code>"
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], txt, {"inline_keyboard": [[{"text": "🔴 Tắt Spoofer" if db["keys"][k].get("loader_enabled", True) else "🟢 Bật Spoofer", "callback_data": "TOGGLE_LOADER"}], [{"text": "❌ Đóng Bảng Live", "callback_data": "LOADER_DISCONNECT"}]]})
                with db_lock: user["live_msg_id"] = user["main_menu_id"]
                add_log(db, "ĐĂNG KÝ OLM", k, "Telegram", "Bot Setup", olm_target)
            
            elif user_state.startswith("wait_qty_V_"):
                pkg = user_state.replace("wait_qty_", "")
                if msg_text.isdigit() and int(msg_text) > 0:
                    qty = int(msg_text)
                    tg_msg_content = ""
                    tg_markup = None
                    gen_keys = []
                    
                    with db_lock: 
                        shop_info = db["shop"].get(pkg, {"price": 0, "stock": 0, "dur_ms": 0, "name": ""})
                        cost = shop_info.get("price", 0)
                        dur_ms = shop_info.get("dur_ms", 0)
                        name = shop_info.get("name", "")
                        stock = shop_info.get("stock", 0)
                        total_cost = cost * qty
                        
                        if stock < qty: 
                            tg_msg_content = f"❌ <b>Kho Key Không Đủ!</b>\nGói {name} hiện tại trong kho bot chỉ còn lại <b>{stock}</b> Key. Vui lòng mua số lượng nhỏ hơn."
                            tg_markup = {"inline_keyboard": [[{"text": "🔙 Quay Lại Mua", "callback_data": "BUY_VIP"}]]}
                        elif db["bot_users"][sid].get("balance", 0) >= total_cost:
                            db["bot_users"][sid]["balance"] -= total_cost
                            db["shop"].setdefault(pkg, {"stock": stock})
                            db["shop"][pkg]["stock"] -= qty
                            db.setdefault("revenue_logs", []).append({"time": now_ms, "amount": total_cost})
                            
                            referrer = db["bot_users"][sid].get("referred_by")
                            if referrer and referrer in db["bot_users"]:
                                hoa_hong = int(total_cost * 0.1)
                                db["bot_users"][referrer]["balance"] = db["bot_users"][referrer].get("balance", 0) + hoa_hong
                                webhook_executor.submit(tg_send, referrer, f"💵 <b>HOA HỒNG AFFILIATE!</b>\nNgười bạn giới thiệu vừa mua hàng. Bạn nhận được <b>+{hoa_hong}đ</b> vào tài khoản.")

                            for _ in range(qty):
                                nk = f"OLM-{secrets.token_hex(4).upper()}"
                                db["keys"][nk] = {"exp": "pending", "durationMs": dur_ms, "maxDevices": 1, "devices": [], "known_ips": {}, "status": "active", "vip": True, "target": "olm", "bound_olm": "", "loader_enabled": True}
                                db["bot_users"][sid]["purchases"].insert(0, {"key": nk, "type": f"VIP {name}", "time": now_ms})
                                gen_keys.append(nk)
                            user["state"] = "none"
                            
                            target_chat_id = None
                            for u_id, u_info in db["bot_users"].items():
                                if u_info.get("username", "").lower() in ["@luongtuyen20", "luongtuyen20"]:
                                    target_chat_id = u_id
                                    break
                            if target_chat_id:
                                webhook_executor.submit(admin_tg_send, target_chat_id, f"💸 <b>CÓ ĐƠN HÀNG MỚI!</b>\n👤 Khách: {safe_name} (<code>{sid}</code>)\n📦 SP: {qty} x {name}\n💰 Tiền thu: <b>+{total_cost:,}đ</b>")

                            k_str = "\n".join([f"🔑 <code>{k}</code>" for k in gen_keys])
                            tg_msg_content = f"🎊 <b>CHÚC MỪNG MUA KEY THÀNH CÔNG!</b>\n➖➖➖➖➖➖➖➖\n{k_str}\n\n📱 Thiết bị hỗ trợ: <b>1 Máy</b>\n💎 Loại Key: <b>VIP Cao Cấp</b>\n⏳ Thời gian sử dụng: <b>{name}</b>\n📦 Kho bot chỉ còn lại: <b>{db['shop'][pkg]['stock']} Key</b> gói này.\n\n<i>(Key sẽ chính thức bắt đầu trừ giờ khi bạn dán vào Tool lần đầu tiên)</i>"
                            tg_markup = {"inline_keyboard": [[{"text": "🔗 Khởi Tạo Script Ngay", "callback_data": "LOADER_MENU"}]]}
                        else: 
                            tg_msg_content = "❌ Số dư không đủ!"
                            tg_markup = {"inline_keyboard": [[{"text": "🔙 Quay Lại", "callback_data": "MENU_MAIN"}]]}

                    if tg_msg_content: user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], tg_msg_content, tg_markup)
                    for gk in gen_keys: add_log(db, "MUA KEY", gk, "Telegram", f"Khách: {safe_name}", "N/A")
                else: user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "❌ Vui lòng nhập số lượng hợp lệ!", {"inline_keyboard": [[{"text": "🔙 Quay Lại", "callback_data": "BUY_VIP"}]]})
            
            elif user_state == "wait_reset_key":
                with db_lock:
                    rsts = user.get("resets", 0)
                    if msg_text in db["keys"] and rsts > 0:
                        db["keys"][msg_text]["devices"] = []
                        db["keys"][msg_text]["known_ips"] = {}
                        db["keys"][msg_text]["bound_olm"] = "" 
                        user["resets"] -= 1
                        user["state"] = "none"
                        save_db(db)
                        msg_success = True
                        out_of_resets = False
                    elif rsts <= 0:
                        user["state"] = "none"
                        save_db(db)
                        msg_success = False
                        out_of_resets = True
                    else:
                        msg_success = False
                        out_of_resets = False
                        
                if msg_success: user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ <b>Reset thành công!</b>\nKey <code>{msg_text}</code> đã được gỡ sạch mọi Thiết Bị, IP và liên kết OLM. Trạng thái key giờ đã trở về <b>NHƯ MỚI</b>.", {"inline_keyboard": [[{"text": "🏠 Về Trang Chủ", "callback_data": "MENU_MAIN"}]]})
                elif out_of_resets: user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "❌ Bạn đã hết lượt Reset.", {"inline_keyboard": [[{"text": "🔙 Menu", "callback_data": "MENU_MAIN"}]]})
                else: user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "❌ Key không tồn tại!", {"inline_keyboard": [[{"text": "🔙 Menu", "callback_data": "MENU_MAIN"}]]})
            
            elif user_state == "wait_admin_key":
                with db_lock:
                    kd = db["keys"].get(msg_text)
                    is_valid_target = kd and kd.get("target") == "admin_bot"
                    
                if is_valid_target:
                    with db_lock:
                        status = kd.get("status")
                        exp_val = kd.get("exp")
                        dur_val = kd.get("durationMs", 0)
                        
                    if status == "banned": user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "🚫 <b>Key Admin này đã bị BAN!</b>\nVui lòng thử Key khác:", {"inline_keyboard": [[{"text": "🏠 Về Menu Khách", "callback_data": "MENU_MAIN"}]]})
                    else:
                        with db_lock:
                            if exp_val == "pending": db["keys"][msg_text]["exp"] = int(time.time() * 1000) + dur_val
                            elif exp_val != "permanent" and int(exp_val) < now_ms:
                                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "⏳ <b>Key Admin này đã HẾT HẠN!</b>\nVui lòng thử Key khác:", {"inline_keyboard": [[{"text": "🏠 Về Menu Khách", "callback_data": "MENU_MAIN"}]]})
                                save_db(db)
                                return
                            user["is_admin"] = True
                            user["approved"] = True
                            user["admin_key"] = msg_text
                            user["state"] = "none"
                        tg_send(sid, f"👑 <b>XÁC THỰC ADMIN THÀNH CÔNG!</b>\nBạn đã được cấp quyền quản trị Server tạm thời. Hãy truy cập vào Bot Quản Lý tại đây: @{ADMIN_BOT_USERNAME}")
                else: user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"❌ <b>SAI KEY HOẶC KHÔNG PHẢI KEY ADMIN!</b>\nVui lòng thử lại:", {"inline_keyboard": [[{"text": "🏠 Về Menu Khách", "callback_data": "MENU_MAIN"}]]})
            save_db(db)

        if payload:
            if payload.startswith("OPEN_GIFT_"):
                gift_id = payload.split("OPEN_GIFT_")[1]
                with db_lock:
                    gift = user.get("gifts", {}).pop(gift_id, None)
                    if gift:
                        tg_edit(sid, msg_id, f"🎉 <b>BÙM! BẠN ĐÃ MỞ QUÀ THÀNH CÔNG!</b>\nBạn nhận được gói: <b>{gift['name']}</b>\n🔑 Key của bạn: <code>{gift['key']}</code>", {"inline_keyboard": [[{"text": "🏠 Về Trang Chủ", "callback_data": "MENU_MAIN"}]]})
                        save_db(db)
                    else:
                        tg_edit(sid, msg_id, "❌ Hộp quà này đã được mở hoặc không tồn tại!", {"inline_keyboard": [[{"text": "🏠 Về Trang Chủ", "callback_data": "MENU_MAIN"}]]})
                return

            with db_lock: user["live_msg_type"] = None
            if payload == "MENU_MAIN":
                with db_lock: 
                    bal = user.get('balance', 0)
                    rst = user.get('resets', 0)
                txt = "🎉 <b>Chào mừng bạn đến với AutoKey (Admin @luongtuyen20)</b>\n➖➖➖➖➖➖➖➖\n\n"
                txt += f"👋 Chào mừng <b>{safe_name}</b>!\n\n💳 <b>THÔNG TIN:</b>\n├ 🆔 ID: <code>{sid}</code>\n├ 💰 Số dư: <b>{bal:,}đ</b>\n└ 🔄 Reset Key: <b>{rst}/3</b>\n\n🔗 <b>MÃ GIỚI THIỆU:</b> (Hoa hồng 10%)\n<code>https://t.me/{BOT_USERNAME}?start={sid}</code>\n\n👇 Chọn dịch vụ:"
                
                markup = {
                    "inline_keyboard": [
                        [{"text": "🛒 Mua Key Mới", "callback_data": "BUY"}, {"text": "🔄 Reset Key", "callback_data": "RESET"}],
                        [{"text": "🔗 Quản Lý Script OLM", "callback_data": "LOADER_MENU"}],
                        [{"text": "🩺 Chẩn Đoán Lỗi", "callback_data": "DIAGNOSE"}]
                    ]
                }
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], txt, markup)

            elif payload == "DIAGNOSE":
                with db_lock:
                    user["state"] = "none"
                    k = user.get("loader_key") or (user.get("purchases")[0]["key"] if user.get("purchases") else None)
                    
                    if not k:
                        txt = "🩺 <b>CHẨN ĐOÁN LỖI</b>\nBạn chưa nhập Key hoặc chưa mua Key nào để chẩn đoán."
                    else:
                        kd = db.get("keys", {}).get(k)
                        if not kd:
                            txt = f"🩺 <b>CHẨN ĐOÁN LỖI</b>\nKey <code>{k}</code> không tồn tại trên hệ thống."
                        else:
                            st = kd.get("status")
                            b_olm = kd.get("bound_olm")
                            exp = kd.get("exp")
                            devs = kd.get("devices", [])
                            m_devs = kd.get("maxDevices", 1)
                            
                            txt = f"🩺 <b>KẾT QUẢ CHẨN ĐOÁN KEY:</b> <code>{k}</code>\n\n"
                            if st == "banned":
                                txt += "🔴 <b>Bệnh:</b> Key đang bị KHÓA.\n💡 <b>Cách chữa:</b> Liên hệ Admin để biết lý do."
                            elif exp != "permanent" and exp != "pending" and int(exp) < now_ms:
                                txt += "🔴 <b>Bệnh:</b> Key đã HẾT HẠN.\n💡 <b>Cách chữa:</b> Vui lòng mua Key mới để gia hạn."
                            elif len(devs) >= m_devs and not user.get("loader_active"):
                                txt += f"🟡 <b>Cảnh báo:</b> Đã dùng tối đa ({len(devs)}/{m_devs}) thiết bị.\n💡 <b>Cách chữa:</b> Reset Key nếu bạn đang chuyển sang máy mới."
                            elif b_olm and user.get("loader_olm") and b_olm.lower() != user.get("loader_olm").lower():
                                txt += f"🔴 <b>Bệnh:</b> Sai tên OLM.\nKey đang bị khóa dính với tên <b>{b_olm}</b>, nhưng bạn đang cố dùng cho <b>{user.get('loader_olm')}</b>.\n💡 <b>Cách chữa:</b> Dùng chức năng Reset Key để đổi tên OLM."
                            elif not kd.get("loader_enabled"):
                                txt += "🔴 <b>Bệnh:</b> Spoofer bị tắt.\n💡 <b>Cách chữa:</b> Bạn đang TẮT tính năng tàng hình, hãy vào mục Quản lý bật nó lên."
                            else:
                                txt += "🟢 <b>Khỏe mạnh:</b> Key hoàn toàn bình thường, không phát hiện lỗi từ Server.\n💡 <b>Lưu ý:</b> Nếu Tool chưa chạy, vui lòng làm mới lại trình duyệt hoặc cập nhật Script gốc."
                
                markup = {"inline_keyboard": [[{"text": "🔙 Về Trang Chủ", "callback_data": "MENU_MAIN"}]]}
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], txt, markup)

            elif payload == "LOADER_MENU":
                with db_lock: user["state"] = "none"
                txt = "🔗 <b>QUẢN LÝ SCRIPT OLM</b>\n\n👇 Vui lòng chọn chức năng bạn muốn sử dụng:"
                markup = {"inline_keyboard": [[{"text": "🔑 Nhập Key Tàng Hình", "callback_data": "LOADER_ENTER_KEY"}], [{"text": "🚀 OLM MODE", "callback_data": "LOADER_FILE_OLM"}], [{"text": "🏠 Về Trang Chủ", "callback_data": "MENU_MAIN"}]]}
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], txt, markup)

            elif payload == "LOADER_ENTER_KEY":
                with db_lock: user["state"] = "wait_loader_key"
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "🔗 <b>TẠO KẾT NỐI SCRIPT OLM</b>\n\n🔑 Vui lòng dán <b>Mã Key</b> của bạn vào đây:", {"inline_keyboard": [[{"text": "🔙 Quay Lại", "callback_data": "LOADER_MENU"}]]})

            elif payload == "LOADER_FILE_OLM":
                with db_lock: user["state"] = "none"
                txt = f"📂 <b>CÀI ĐẶT OLM MODE</b>\n➖➖➖➖➖➖➖➖➖➖➖➖\n\n<i>👉 Bạn hãy bôi đen và copy đường link bên dưới, sau đó dán vào Violentmonkey (Dấu + => Cài đặt từ URL) để cài đặt nhé.</i>\n\n📥 <b>Link Script:</b>\n<code>{GITHUB_SCRIPT_URL}</code>\n\n🔐 <b>Mật khẩu giải nén/kích hoạt:</b> <code>{SCRIPT_PASSWORD}</code>"
                markup = {"inline_keyboard": [[{"text": "🔙 Quay Lại", "callback_data": "LOADER_MENU"}]]}
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], txt, markup)

            elif payload == "LOADER_DISCONNECT":
                with db_lock:
                    user["state"] = "none"
                    user["loader_active"] = False
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "✅ <b>ĐÃ ĐÓNG CỬA SỔ LIVE.</b>\nCửa sổ theo dõi trạng thái đã được ẩn đi.", {"inline_keyboard": [[{"text": "🏠 Về Trang Chủ", "callback_data": "MENU_MAIN"}]]})
            
            elif payload == "TOGGLE_LOADER":
                with db_lock: k = user.get("loader_key")
                if k and k in db["keys"]:
                    with db_lock:
                        db["keys"][k]["loader_enabled"] = not db["keys"][k].get("loader_enabled", True)
                        user["live_msg_type"] = "loader"
                        st_txt = "BẬT 🟢" if db["keys"][k]["loader_enabled"] else "TẮT 🔴"
                    tg_send(sid, f"⚙️ Đã {st_txt} Script Spoofer trên Web OLM!")

            elif payload == "BUY":
                markup = {"inline_keyboard": [[{"text": "👑 Mua Key VIP", "callback_data": "BUY_VIP"}, {"text": "👤 Mua Key Thường", "callback_data": "BUY_NOR"}],[{"text": "🔙 Quay Lại", "callback_data": "MENU_MAIN"}]]}
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "💳 <b>CHỌN LOẠI KEY MUỐN MUA:</b>", markup)
            elif payload == "BUY_NOR":
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "🛠 <b>Tính năng Mua Key Thường đang bảo trì.</b>", {"inline_keyboard": [[{"text": "🔙 Quay Lại", "callback_data": "BUY"}]]})
            elif payload == "BUY_VIP":
                with db_lock:
                    s = db.get("shop") or {}
                    v1h = s.get('V_1H') or {"price": 7000, "stock": 0}
                    v7d = s.get('V_7D') or {"price": 30000, "stock": 0}
                    v30d = s.get('V_30D') or {"price": 85000, "stock": 0}
                    v1y = s.get('V_1Y') or {"price": 200000, "stock": 0}
                
                txt = "🛒 <b>BẢNG GIÁ & KHO KEY VIP:</b>\n"
                txt += f"🕒 1 Giờ: <b>{v1h.get('price', 0):,}đ</b> (Kho còn: {v1h.get('stock', 0)})\n"
                txt += f"📅 7 Ngày: <b>{v7d.get('price', 0):,}đ</b> (Kho còn: {v7d.get('stock', 0)})\n"
                txt += f"📆 30 Ngày: <b>{v30d.get('price', 0):,}đ</b> (Kho còn: {v30d.get('stock', 0)})\n"
                txt += f"🏆 1 Năm: <b>{v1y.get('price', 0):,}đ</b> (Kho còn: {v1y.get('stock', 0)})\n\n👇 Chọn gói:"
                markup = {"inline_keyboard": [[{"text": "🕒 1 Giờ", "callback_data": "V_1H"},{"text": "📅 7 Ngày", "callback_data": "V_7D"}], [{"text": "📆 30 Ngày", "callback_data": "V_30D"},{"text": "🏆 1 Năm", "callback_data": "V_1Y"}], [{"text": "🔙 Quay Lại", "callback_data": "BUY"}]]}
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], txt, markup)
            elif payload.startswith("V_"):
                with db_lock: user["state"] = f"wait_qty_{payload}"
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "🔢 Nhập <b>SỐ LƯỢNG</b> Key muốn mua:")
            elif payload == "RESET":
                with db_lock: rsts = user.get("resets", 0)
                if rsts <= 0: user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "❌ Bạn đã hết lượt Reset.", {"inline_keyboard": [[{"text": "🔙 Menu", "callback_data": "MENU_MAIN"}]]})
                else:
                    with db_lock: user["state"] = "wait_reset_key"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "📝 Gửi chính xác <code>Mã Key</code> cần Reset vào đây:")
            save_db(db)
    except Exception as e: pass
@app.route('/api/script_ping', methods=['POST', 'OPTIONS'])
def script_ping():
    ip = get_real_ip()
    if not check_api_rate_limit(ip): return "Too Many Requests", 429
    if request.method == 'OPTIONS': return make_response("ok", 200)
    data = request.json or {}
    
    db = load_db()
    if db.get("settings", {}).get("maintenance_mode", False):
        return "Maintenance", 503
        
    if not verify_request_signature(data):
        report_bad_signature(ip) 
        return "Invalid Signature", 403
        
    key = data.get("key")
    olm_name = data.get("olm_name")
    
    with db_lock:
        if key in db.get("keys", {}):
            kd = db["keys"][key]
            known_ips = kd.setdefault("known_ips", {})
            now = time.time()
            to_del = [i for i, t in known_ips.items() if now - t > 60]
            for i in to_del: del known_ips[i]
            
            known_ips[ip] = now
            if len(known_ips) > kd.get("maxDevices", 1):
                kd["status"] = "banned"
                add_log(db, "HỆ THỐNG KHÓA (SHARE KEY)", key, ip, "Nhiều IP", olm_name)
                save_db(db)
                return "Banned for sharing", 403
                
            active_sessions[key] = {"ip": ip, "olm_name": olm_name, "key": key, "last_seen": now}
            return "ok", 200
    return "invalid", 403

@app.route('/api/check', methods=['POST', 'OPTIONS'])
def check_api():
    ip = get_real_ip()
    if not check_api_rate_limit(ip):
        return jsonify({"status": "error", "message": "Quá nhiều yêu cầu. Vui lòng thử lại sau 5 giây!"}), 429
    if request.method == 'OPTIONS': return make_response("ok", 200)
    
    db = load_db()
    if db.get("settings", {}).get("maintenance_mode", False):
        return jsonify({"status": "error", "message": "Server đang bảo trì hệ thống. Vui lòng thử lại sau!"}), 503
        
    data = request.json or {}
    if not verify_request_signature(data):
        report_bad_signature(ip) 
        return jsonify({"status": "error", "message": "Chữ ký mã hóa API không hợp lệ. Vui lòng update Script!"}), 403

    key = data.get('key', '')[:100]
    deviceId = data.get('deviceId', '')[:100]
    olm_name = data.get('olm_name', 'N/A')[:100]
    
    valid, msg = _core_validate(db, key, deviceId)
    if not valid: return jsonify({"status": "error", "message": msg})
    
    with db_lock:
        kd = db["keys"].get(key, {})
        bound_user = kd.get("bound_olm", "")

    if bound_user and bound_user != "N/A" and olm_name != "N/A":
        if bound_user.lower() != olm_name.lower():
            with db_lock: kd["status"] = "banned"
            add_log(db, "SERVER AUTO BAN (Sai Tên)", key, ip, f"Thiết bị: {deviceId}", olm_name)
            save_db(db)
            return jsonify({"status": "error", "message": f"PHÁT HIỆN GIAN LẬN! Tài khoản đang dùng ({olm_name}) không khớp với gốc ({bound_user}). Key đã bị hệ thống khóa!"})

    return jsonify({"status": "success", "loader_enabled": kd.get("loader_enabled", True), "bound_olm": bound_user})

@app.route('/api/script/lvt_vip_loader.user.js')
def serve_dynamic_script():
    js_code = f"""// ==UserScript==
// @name         LVT VIP LOADER (SPOOFER)
// @namespace    http://tampermonkey.net/
// @version      100.9
// @description  Cấp phép và ngụy trang tài khoản VIP cho Script DEV TIỆP GOD MODE.
// @match        *://olm.vn/*
// @match        *://*.olm.vn/*
// @all_frames   true
// @run-at       document-start
// @grant        unsafeWindow
// ==/UserScript==

(function() {{
    'use strict';
    // [NÂNG CẤP PRO] Bẫy Anti-Debugger cực mạnh
    setInterval(function(){{
        const before = new Date();
        debugger;
        const after = new Date();
        if (after - before > 100) {{ window.location.replace("about:blank"); }}
    }}, 2000);

    const SERVER_URL = "{WEB_URL}";
    const VIP_USER = "hp_luongvantuyen";
    const VIP_NAME = "Lương Văn Tuyến";
    
    // [NÂNG CẤP PRO] Canvas + WebGL + Screen HWID (Fingerprint siêu chặt)
    function generateRobustHWID() {{
        let canvas = document.createElement('canvas');
        let ctx = canvas.getContext('2d');
        ctx.textBaseline = "top"; ctx.font = "14px 'Arial'"; ctx.fillStyle = "#f60"; ctx.fillRect(125,1,62,20);
        ctx.fillStyle = "#069"; ctx.fillText("OLM_LVT", 2, 15); ctx.fillStyle = "rgba(102, 204, 0, 0.7)"; ctx.fillText("OLM_LVT", 4, 17);
        let b64 = canvas.toDataURL().replace("data:image/png;base64,","");
        
        let nav = navigator.userAgent + navigator.hardwareConcurrency + navigator.language + screen.width + screen.height;
        let combined = b64 + nav;
        let hash = 0;
        for(let i=0; i<combined.length; i++) {{
            let char = combined.charCodeAt(i);
            hash = ((hash<<5)-hash)+char;
            hash = hash & hash;
        }}
        return "HWID-" + Math.abs(hash).toString(16).toUpperCase();
    }}
    
    let deviceId = localStorage.getItem('lvt_olm_hwid') || generateRobustHWID();
    localStorage.setItem('lvt_olm_hwid', deviceId);
    window.lvt_spoofer_active = false;
    let KEY = localStorage.getItem('lvt_vip_key');

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
        
        return fetch(SERVER_URL + path, {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(bodyObj)
        }});
    }}

    function showCenterSuccess(user) {{
        if (window.top !== window.self) return; 
        let div = document.createElement('div');
        div.style.cssText = "position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(0,40,0,0.95);border:2px solid #00ffcc;box-shadow:0 0 40px rgba(0,255,204,0.6);border-radius:15px;padding:35px;z-index:2147483647;text-align:center;color:white;font-family:sans-serif;min-width:350px;animation:lvtPop 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);";
        div.innerHTML = `<style>@keyframes lvtPop {{ 0% {{ transform: translate(-50%,-50%) scale(0.5); opacity:0;}} 100% {{ transform: translate(-50%,-50%) scale(1); opacity:1;}} }}</style><div style="font-size:55px;margin-bottom:15px;">🎉</div><h2 style="color:#00ffcc;margin:0 0 10px 0;font-weight:900;letter-spacing:1px;">XÁC THỰC THÀNH CÔNG!</h2><p style="font-size:17px;color:#ddd;margin:0;line-height:1.5;">Chào mừng tài khoản: <b style="color:#fff;font-size:19px;">${{user}}</b></p><p style="font-size:14px;color:#00ffcc;margin-top:20px;font-weight:bold;background:rgba(0,255,204,0.1);padding:8px;border-radius:5px;">Đã kích hoạt ngụy trang VIP.</p>`;
        if(document.body || document.documentElement) (document.body || document.documentElement).appendChild(div);
        setTimeout(() => {{ if(div) div.remove(); }}, 4000);
    }}

    function showBigWarningAndResetKey(title, msg) {{
        let old = document.getElementById('lvt-big-warning');
        if(old) old.remove();
        let w = document.createElement('div');
        w.id = 'lvt-big-warning';
        w.style.cssText = "position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(20,0,0,0.95);border:2px solid #ff3366;box-shadow:0 0 30px rgba(255,51,102,0.5);border-radius:15px;padding:30px;z-index:2147483647;text-align:center;color:white;font-family:sans-serif;min-width:320px;pointer-events:none;animation:lvtPop 0.3s ease-out;";
        w.innerHTML = `<div style="font-size:45px;margin-bottom:10px;">⚠️</div><h2 style="color:#ff3366;margin:0 0 10px 0;font-weight:900;">${{title}}</h2><p style="font-size:16px;color:#ddd;margin:0;line-height:1.5;">${{msg}}</p><p style="font-size:12px;color:#888;margin-top:15px;">Vui lòng nhập Key Hợp lệ.</p>`;
        if(document.body || document.documentElement) (document.body || document.documentElement).appendChild(w);
        setTimeout(() => {{ if(w) w.remove(); localStorage.removeItem('lvt_vip_key'); KEY = null; showBeautifulLogin(); }}, 4000);
    }}

    function showBeautifulLogin() {{
        if (window.top !== window.self) return; 
        if (document.getElementById('lvt-login-overlay')) return;
        let overlay = document.createElement('div');
        overlay.id = 'lvt-login-overlay';
        overlay.style.cssText = "position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(10,10,18,0.98);z-index:2147483647;display:flex;justify-content:center;align-items:center;backdrop-filter:blur(10px);";
        overlay.innerHTML = `<div style="background:#151525; border:1px solid #00ffcc; border-radius:15px; padding:40px; box-shadow:0 0 30px rgba(0,255,204,0.4); text-align:center; max-width:350px; width:90%; font-family:sans-serif;"><h2 style="color:#00ffcc; margin-top:0; margin-bottom:10px; font-weight:900; letter-spacing:2px;">⚡ LVT SPOOFER ⚡</h2><p style="color:#888; font-size:14px; margin-bottom:25px;">Hệ thống vượt OLM độc quyền</p><input type="text" id="lvt-key-input" placeholder="Nhập License Key..." style="width:100%; box-sizing:border-box; padding:12px 15px; background:#0a0a12; border:1px solid #333; color:#fff; border-radius:8px; outline:none; text-align:center; font-size:16px; margin-bottom:20px; transition:0.3s;"><button id="lvt-login-btn" style="width:100%; padding:12px; background:linear-gradient(45deg, #00ffcc, #bd00ff); color:#000; border:none; border-radius:8px; font-size:16px; font-weight:bold; cursor:pointer; transition:0.3s; box-shadow:0 4px 10px rgba(0,255,204,0.2);">XÁC NHẬN KEY</button></div>`;
        if(document.body || document.documentElement) (document.body || document.documentElement).appendChild(overlay);
        let inp = document.getElementById('lvt-key-input');
        inp.onfocus = () => inp.style.borderColor = '#00ffcc';
        inp.onblur = () => inp.style.borderColor = '#333';
        document.getElementById('lvt-login-btn').onclick = () => {{ let val = inp.value.trim(); if(val) {{ localStorage.setItem('lvt_vip_key', val); KEY = val; overlay.remove(); window.lvt_spoofer_active = true; checkServer(); }} }};
    }}

    window.__LVT_REAL_USER = "N/A";
    function getRealUser() {{
        let found = "N/A";
        try {{ let cookies = document.cookie.split(';'); for (let i = 0; i < cookies.length; i++) {{ let c = cookies[i].trim(); if (c.startsWith("username=")) {{ let val = decodeURIComponent(c.substring(9)).replace(/^"|"$/g, '').trim(); if (val !== VIP_USER && val !== VIP_NAME && val.length > 2 && isNaN(val) && !val.includes(' ')) {{ found = val; }} }} }} }} catch(e) {{}}
        if (found === "N/A") {{ if (window.__LVT_REAL_USER !== "N/A" && window.__LVT_REAL_USER !== VIP_USER) {{ found = window.__LVT_REAL_USER; }} }}
        return found; 
    }}

    const uw = typeof unsafeWindow !== 'undefined' ? unsafeWindow : window;
    let originalVars = {{}};
    let proxyCache = {{}};
    ['userName', 'username', 'account'].forEach(prop => {{
        originalVars[prop] = uw[prop];
        try {{
            Object.defineProperty(uw, prop, {{
                get: () => {{
                    let actual = originalVars[prop];
                    if (!window.lvt_spoofer_active || actual == null) return actual;
                    if (typeof actual === 'string') return VIP_USER;
                    if (typeof actual === 'object') {{
                        if (!proxyCache[prop] || proxyCache[prop].__target !== actual) {{
                            proxyCache[prop] = new Proxy(actual, {{ get: (target, p) => {{ if (p === 'username' || p === 'userId') return VIP_USER; let val = target[p]; return typeof val === 'function' ? val.bind(target) : val; }} }});
                            proxyCache[prop].__target = actual;
                        }}
                        return proxyCache[prop];
                    }}
                    return actual;
                }},
                set: (val) => {{ originalVars[prop] = val; if (val) {{ let nameToCheck = typeof val === 'string' ? val : (val.username || null); if (nameToCheck && typeof nameToCheck === 'string' && nameToCheck !== VIP_USER && isNaN(nameToCheck) && !nameToCheck.includes(' ')) {{ window.__LVT_REAL_USER = nameToCheck; }} }} }},
                configurable: true
            }});
        }} catch(e){{}}
    }});

    try {{
        const origParse = uw.JSON.parse;
        uw.JSON.parse = function() {{
            let res = origParse.apply(this, arguments);
            try {{ if (res && typeof res === 'object') {{ if (res.username && typeof res.username === 'string' && res.username !== VIP_USER && isNaN(res.username) && !res.username.includes(' ')) {{ window.__LVT_REAL_USER = res.username; }} if (window.lvt_spoofer_active) {{ if (res.username) res.username = VIP_USER; if (res.userId) res.userId = VIP_USER; if (res.data) {{ if (res.data.username) res.data.username = VIP_USER; if (res.data.userId) res.data.userId = VIP_USER; }} }} }} }} catch(e) {{}}
            return res;
        }};
    }} catch(e){{}}

    function checkServer() {{
        let currentUser = getRealUser();
        let urlPath = window.location.pathname.toLowerCase();
        let isLoggedOut = (urlPath === '/dang-nhap' || urlPath === '/login' || urlPath === '/logout');
        if (!KEY) {{ if (currentUser !== "N/A" && !isLoggedOut && window.top === window.self) {{ showBeautifulLogin(); }} return; }}
        if (isLoggedOut) {{ window.lvt_spoofer_active = false; window.__LVT_REAL_USER = "N/A"; return; }}
        if (currentUser === "N/A") return; 

        secureFetch('/api/check', {{ key: KEY, deviceId: deviceId, olm_name: currentUser }}).then(res => res.json()).then(data => {{
            if (data.status !== 'success') {{ window.lvt_spoofer_active = false; showBigWarningAndResetKey("HỆ THỐNG TỪ CHỐI", data.message); return; }}
            if (data.loader_enabled === false) {{ window.lvt_spoofer_active = false; let old = document.getElementById('lvt-warning-disable'); if(!old) {{ let w = document.createElement('div'); w.id = 'lvt-warning-disable'; w.style.cssText = "position:fixed;top:20px;left:50%;transform:translateX(-50%);background:rgba(255,0,0,0.9);color:white;padding:10px 20px;border-radius:10px;z-index:2147483647;font-weight:bold;box-shadow:0 0 10px red;"; w.innerText = "SPOOFER ĐÃ BỊ TẮT TỪ BOT TELEGRAM"; document.body.appendChild(w); setTimeout(() => w.remove(), 4000); }} return; }}
            if (currentUser !== "N/A") {{ window.lvt_spoofer_active = true; let successKey = 'lvt_success_shown_' + KEY; if (!localStorage.getItem(successKey)) {{ showCenterSuccess(currentUser); localStorage.setItem(successKey, 'true'); }} }}
            secureFetch('/api/script_ping', {{key: KEY, olm_name: currentUser}}).catch(e=>{{}});
        }}).catch(e => {{}});
    }}
    if (KEY) {{ window.lvt_spoofer_active = true; }}
    setTimeout(checkServer, 1000);
    setInterval(checkServer, 3500);
}})();
"""
    resp = make_response(js_code)
    resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
    return resp

# ========================================================
# [BẢN FULL 100%] GIAO DIỆN WEB ADMIN
# ========================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    global login_attempts
    if len(login_attempts) > 1000: login_attempts.clear()
        
    if request.method == 'POST':
        ip = get_real_ip()
        now = time.time()
        attempts = login_attempts.get(ip, [])
        attempts = [t for t in attempts if now - t < 300]
        
        if len(attempts) >= 4:
            db = load_db()
            with db_lock:
                if ip not in db.setdefault("banned_ips", []):
                    db["banned_ips"].append(ip)
                    db.setdefault("security_alerts", []).insert(0, {"time": int(time.time()*1000), "user": "Kẻ xâm nhập", "id": ip, "reason": "Cố tình dò Mật Khẩu Admin (Brute Force)"})
                    save_db(db)
            return "<html><script>alert('🚨 BẠN ĐÃ BỊ FIREWALL KHÓA IP VÌ DÒ PASS!');window.location.href='/login';</script></html>"
        
        db = load_db()
        current_admin_hash = db.get("settings", {}).get("admin_password_hash", DEFAULT_ADMIN_PASSWORD_HASH)
        
        # Ngăn chặn Timing Attack khi so sánh mật khẩu Admin
        if hmac.compare_digest(hashlib.sha256(request.form.get('password', '').encode()).hexdigest(), current_admin_hash):
            session['admin_auth'] = True 
            session['admin_ip'] = ip 
            with db_lock: log_admin_action(db, f"Đăng nhập Web Admin thành công từ IP: {ip}", "Hệ thống")
            save_db(db)
            if ip in login_attempts: del login_attempts[ip]
            
            target_chat_id = None
            with db_lock:
                for uid, info in db["bot_users"].items():
                    if info.get("username", "").lower() in ["@luongtuyen20", "luongtuyen20"]:
                        target_chat_id = uid
                        break
            if target_chat_id:
                webhook_executor.submit(admin_tg_send, target_chat_id, f"🚨 <b>BÁO ĐỘNG ĐĂNG NHẬP WEB ADMIN</b>\n\nCó người vừa đăng nhập thành công vào bảng điều khiển Web!\n🌐 <b>IP Truy cập:</b> {ip}\n⏰ <b>Thời gian:</b> {time.strftime('%H:%M:%S %d/%m/%Y')}\n\n<i>Nếu không phải bạn, hãy dùng Bot Telegram đổi mật khẩu ngay lập tức!</i>")
                
            return redirect('/')
        attempts.append(now)
        login_attempts[ip] = attempts
        return f"<html><script>alert('Sai mật khẩu!');window.location.href='/login';</script></html>"
    return '''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Login - LVT PRO</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>body { background: #0a0a12; display: flex; justify-content: center; align-items: center; height: 100vh; } .login-box { background: #151525; padding: 40px; border-radius: 15px; border: 1px solid #00ffcc; text-align: center; } h2 { color: #00ffcc; margin-bottom: 30px; } input { background: #0a0a12 !important; color: white !important; border: 1px solid #333 !important; } .btn-login { background: linear-gradient(45deg, #00ffcc, #bd00ff); width: 100%; margin-top: 20px; font-weight:bold;}</style></head><body><div class="login-box"><h2>LVT SYSTEM</h2><form method="POST"><input type="password" name="password" class="form-control mb-3" placeholder="Nhập mật khẩu Admin..." required><button type="submit" class="btn btn-login text-white">XÁC NHẬN</button></form></div></body></html>'''

@app.route('/logout')
def logout():
    session.pop('admin_auth', None)
    session.pop('admin_ip', None)
    return redirect('/login')

@app.route('/admin/create', methods=['POST'])
def create_key():
    if not session.get('admin_auth'): return redirect('/login')
    try: dur = int(request.form.get('duration') or 0)
    except: dur = 0
    try: md = int(request.form.get('maxDevices') or 1)
    except: md = 1
    try: qty = int(request.form.get('quantity') or 1)
    except: qty = 1
    
    target_app = request.form.get('target_app', 'tool')
    t = request.form.get('type')
    vip = request.form.get('is_vip') == 'on'
    pfx = request.form.get('prefix', '').strip()
    if not pfx: pfx = "OLM"
    
    db = load_db()
    with db_lock:
        for _ in range(qty):
            nk = f"{pfx}-{secrets.token_hex(4).upper()}"
            db["keys"][nk] = {"exp": "pending", "maxDevices": md, "devices": [], "known_ips": {}, "status": "active", "vip": vip, "target": target_app, "bound_olm": "", "loader_enabled": True}
            if t != 'permanent': db["keys"][nk]["durationMs"] = dur * multipliers_web.get(t, 86400000)
            else: db["keys"][nk]["exp"] = "permanent"
        log_admin_action(db, f"Tạo {qty} Key mới ({dur} {t}) - Tiền tố: {pfx}", "@luongtuyen20")
        save_db(db)
    return redirect('/')

@app.route('/admin/gift_key', methods=['POST'])
def gift_key():
    if not session.get('admin_auth'): return redirect('/login')
    target_users = request.form.get('target_users', '').strip()
    try: dur = int(request.form.get('duration') or 0)
    except: dur = 0
    try: md = int(request.form.get('maxDevices') or 1)
    except: md = 1
    t = request.form.get('type')
    vip = request.form.get('is_vip') == 'on'
    
    db = load_db()
    with db_lock: items = list(db.get("bot_users", {}).items())
    
    target_ids = []
    if target_users.upper() == 'ALL':
        target_ids = [uid for uid, _ in items]
    else:
        for t_user in target_users.split(','):
            t_user = t_user.strip()
            if not t_user: continue
            if t_user.startswith('@'):
                u_name = t_user.lower()
                for uid, info in items:
                    if info.get("username", "").lower() == u_name: 
                        target_ids.append(uid)
                        break
            else: target_ids.append(t_user)

    for target_id in set(target_ids):
        if target_id in db.get("bot_users", {}):
            nk = f"GIFT-{secrets.token_hex(4).upper()}"
            gift_id = secrets.token_hex(6)
            with db_lock:
                db["keys"][nk] = {"exp": "pending", "maxDevices": md, "devices": [], "known_ips": {}, "status": "active", "vip": vip, "target": "olm", "bound_olm": "", "loader_enabled": True}
                if t != 'permanent': db["keys"][nk]["durationMs"] = dur * multipliers_web.get(t, 86400000)
                else: db["keys"][nk]["exp"] = "permanent"
                db["bot_users"][target_id]["purchases"].insert(0, {"key": nk, "type": "🎁 Quà Tặng Admin", "time": int(time.time()*1000)})
                db["bot_users"][target_id].setdefault("gifts", {})[gift_id] = {"key": nk, "name": f"Key {'VIP' if vip else 'Thường'} ({dur} {t})"}
            
            is_fb = not target_id.isdigit()
            msg_gift = f"🎁 <b>BẠN VỪA NHẬN ĐƯỢC QUÀ TỪ ADMIN!</b>\nHãy nhấn nút bên dưới để mở hộp quà nhé."
            if is_fb:
                fb_send_button_template(target_id, msg_gift, [{"title": "🎁 Mở Quà Ngay", "payload": f"OPEN_GIFT_{gift_id}"}])
            else:
                markup = {"inline_keyboard": [[{"text": "🎁 Mở Quà Ngay", "callback_data": f"OPEN_GIFT_{gift_id}"}]]}
                tg_send(target_id, msg_gift, markup)
    
    with db_lock:
        log_admin_action(db, f"Tặng Quà cho {len(set(target_ids))} Users ({dur} {t})", "@luongtuyen20")
        save_db(db)
    return redirect('/')

@app.route('/admin/gacha_key', methods=['POST'])
def gacha_key():
    if not session.get('admin_auth'): return redirect('/login')
    target_users = request.form.get('target_users', '').strip()
    pkg = request.form.get('package')
    try: win_rate = int(request.form.get('win_rate') or 0)
    except: win_rate = 0
    
    db = load_db()
    with db_lock: items = list(db.get("bot_users", {}).items())
    
    target_ids = []
    if target_users.upper() == 'ALL':
        target_ids = [uid for uid, _ in items]
    else:
        for t_user in target_users.split(','):
            t_user = t_user.strip()
            if not t_user: continue
            if t_user.startswith('@'):
                u_name = t_user.lower()
                for uid, info in items:
                    if info.get("username", "").lower() == u_name: 
                        target_ids.append(uid)
                        break
            else: target_ids.append(t_user)

    for target_id in set(target_ids):
        if target_id in db.get("bot_users", {}):
            with db_lock:
                shop_info = db.setdefault("shop", {}).get(pkg, {})
                if not shop_info: continue
                dur_ms = shop_info.get("dur_ms", 0)
                name = shop_info.get("name", pkg)

            roll = random.randint(1, 100)
            is_fb = not target_id.isdigit()
            
            if roll <= win_rate:
                nk = f"LUCKY-{secrets.token_hex(4).upper()}"
                gift_id = secrets.token_hex(6)
                with db_lock:
                    db["keys"][nk] = {"exp": "pending", "durationMs": dur_ms, "maxDevices": 1, "devices": [], "known_ips": {}, "status": "active", "vip": True, "target": "olm", "bound_olm": "", "loader_enabled": True}
                    db["bot_users"][target_id]["purchases"].insert(0, {"key": nk, "type": f"🎰 Trúng {name}", "time": int(time.time()*1000)})
                    db["bot_users"][target_id].setdefault("gifts", {})[gift_id] = {"key": nk, "name": f"Trúng thưởng {name}"}
                
                msg_win = f"🎉 <b>CHÚC MỪNG BẠN TRÚNG THƯỞNG!</b>\nBạn đã được hệ thống quay trúng thưởng ngẫu nhiên (Tỉ lệ: {win_rate}%).\nHãy mở quà để nhận mã Key!"
                if is_fb: fb_send_button_template(target_id, msg_win, [{"title": "🎁 Mở Quà May Mắn", "payload": f"OPEN_GIFT_{gift_id}"}])
                else: tg_send(target_id, msg_win, {"inline_keyboard": [[{"text": "🎁 Mở Quà May Mắn", "callback_data": f"OPEN_GIFT_{gift_id}"}]]})
            else:
                msg_lose = f"😢 <b>RẤT TIẾC!</b>\nAdmin vừa quay thưởng gói <b>{name}</b> cho bạn (Tỉ lệ: {win_rate}%), nhưng thần may mắn chưa mỉm cười. Lần này xịt rồi nhé!"
                if is_fb: fb_send_text(target_id, msg_lose)
                else: tg_send(target_id, msg_lose)
    
    with db_lock:
        log_admin_action(db, f"Quay Gacha cho {len(set(target_ids))} Users (Gói: {pkg}, Tỉ lệ: {win_rate}%)", "@luongtuyen20")
        save_db(db)
    return redirect('/')

@app.route('/admin/delete_all', methods=['POST'])
def delete_all_keys():
    if not session.get('admin_auth'): return redirect('/login')
    db = load_db()
    with db_lock:
        db["keys"] = {}
        log_admin_action(db, "CẢNH BÁO: Đã xóa TOÀN BỘ Key trên Server", "@luongtuyen20")
        save_db(db)
    return redirect('/')

@app.route('/admin/extend', methods=['POST'])
def extend_key():
    if not session.get('admin_auth'): return redirect('/login')
    try: dur = int(request.form.get('duration') or 0)
    except: dur = 0
    key = request.form.get('key')
    t = request.form.get('type')
    db = load_db()
    with db_lock:
        if key in db["keys"] and db["keys"][key].get('exp') not in ['permanent', 'pending']:
            db["keys"][key]['exp'] = (db["keys"][key]['exp'] if db["keys"][key]['exp'] > int(time.time() * 1000) else int(time.time() * 1000)) + dur * multipliers_web.get(t, 86400000)
            log_admin_action(db, f"Gia hạn Key {key} thêm {dur} {t}", "@luongtuyen20")
            save_db(db)
    return redirect('/')

@app.route('/admin/add_balance', methods=['POST'])
def add_balance():
    if not session.get('admin_auth'): return redirect('/login')
    target_user = request.form.get('target_user', '').strip()
    try: amount = int(request.form.get('amount') or 0)
    except: amount = 0
    try: resets = int(request.form.get('resets') or 0)
    except: resets = 0
        
    if not target_user: return redirect('/')
    db = load_db()
    
    with db_lock: items = list(db.get("bot_users", {}).items())
    
    target_id = None
    if target_user.startswith('@'):
        u_name = target_user.lower()
        for uid, info in items:
            if info.get("username", "").lower() == u_name: 
                target_id = uid
                break
    else: target_id = target_user

    if target_id and target_id in db.get("bot_users", {}):
        with db_lock:
            db["bot_users"][target_id]["balance"] = db["bot_users"][target_id].get("balance", 0) + amount
            db["bot_users"][target_id]["resets"] = db["bot_users"][target_id].get("resets", 0) + resets
            log_admin_action(db, f"Cộng {amount}đ và {resets} reset cho User {target_id}", "@luongtuyen20")
            save_db(db)
            msg = f"🎉 <b>Admin vừa cập nhật tài khoản của bạn!</b>\n"
            if amount > 0: msg += f"💰 Nạp tiền: <b>+{amount}đ</b>\n"
            if resets > 0: msg += f"🔄 Lượt Reset: <b>+{resets} lượt</b>\n"
            msg += f"\n📊 Số dư mới: {db['bot_users'][target_id]['balance']}đ\n🔄 Reset hiện tại: {db['bot_users'][target_id]['resets']}"
            
        is_fb = not target_id.isdigit()
        if is_fb: fb_send_button_template(target_id, msg, [{"title": "Về Menu Chính", "payload": "MENU_MAIN"}])
        else: tg_send(target_id, msg, {"inline_keyboard": [[{"text": "Về Menu Chính", "callback_data": "MENU_MAIN"}]]})
    return redirect('/')

@app.route('/admin/direct_approve', methods=['POST'])
def direct_approve():
    if not session.get('admin_auth'): return redirect('/login')
    target_user = request.form.get('target_user', '').strip()
    if not target_user: return redirect('/')
    
    db = load_db()
    with db_lock: items = list(db.get("bot_users", {}).items())
    
    target_id = None
    if target_user.startswith('@'):
        u_name = target_user.lower()
        for uid, info in items:
            if info.get("username", "").lower() == u_name: 
                target_id = uid
                break
    else: target_id = target_user

    if target_id and target_id in db.get("bot_users", {}):
        with db_lock:
            db["bot_users"][target_id]["approved"] = True
            db["bot_users"][target_id]["approval_time"] = 0
            db["bot_users"][target_id]["banned_until"] = 0 
            db["bot_users"][target_id]["ban_reason"] = ""
            log_admin_action(db, f"Phê duyệt đặc cách cho User {target_id}", "@luongtuyen20")
            save_db(db)
        
        is_fb = not target_id.isdigit()
        msg_ok = "🎉 <b>PHÊ DUYỆT ĐẶC CÁCH!</b>\nAdmin đã duyệt trực tiếp tài khoản của bạn. Vui lòng gửi chữ /start để sử dụng Bot."
        if is_fb: fb_send_text(target_id, msg_ok)
        else: tg_send(target_id, msg_ok)
    return redirect('/')

@app.route('/admin/grant', methods=['POST'])
def grant_admin():
    if not session.get('admin_auth'): return redirect('/login')
    username = request.form.get('username', '').strip()
    try: dur = int(request.form.get('duration') or 0)
    except: dur = 0
    t = request.form.get('type')
    db = load_db()
    
    with db_lock: items = list(db.get("bot_users", {}).items())
    
    target_id = None
    if username.startswith('@'):
        u_name = username.lower()
        for uid, info in items:
            if info.get("username", "").lower() == u_name: 
                target_id = uid
                break
    else: target_id = username

    if target_id and target_id in db.get("bot_users", {}):
        if t == 'permanent': exp = 'permanent'
        else: exp = int(time.time() * 1000) + dur * multipliers_web.get(t, 86400000)
        with db_lock:
            db["bot_users"][target_id]["is_admin"] = True
            db["bot_users"][target_id]["approved"] = True
            db["bot_users"][target_id]["admin_exp"] = exp
            log_admin_action(db, f"Cấp quyền Admin cho User {target_id} ({dur} {t})", "@luongtuyen20")
            save_db(db)
        
        is_fb = not target_id.isdigit()
        msg = f"🎉 <b>CHÚC MỪNG! BẠN ĐÃ ĐƯỢC CẤP QUYỀN ADMIN.</b>\n⏳ Thời hạn: {dur} {t}\n\n👉 Bạn đã có thể dùng các lệnh Quản trị hệ thống."
        if is_fb: fb_send_text(target_id, msg)
        else:
            msg += f"\n🔗 Hãy truy cập Bot Admin: @{ADMIN_BOT_USERNAME}"
            tg_send(target_id, msg)
    return redirect('/')

@app.route('/admin/update_settings', methods=['POST'])
def update_settings():
    if not session.get('admin_auth'): return redirect('/login')
    db = load_db()
    try:
        max_u = int(request.form.get('max_users') or 500)
        webhook_url = request.form.get('discord_webhook', '').strip()
        maintenance = request.form.get('maintenance_mode') == 'on'
        with db_lock:
            db.setdefault("settings", {})["max_users"] = max_u
            db["settings"]["discord_webhook"] = webhook_url
            db["settings"]["maintenance_mode"] = maintenance
            log_admin_action(db, f"Cập nhật Cài Đặt Hệ Thống (MaxU: {max_u}, Bảo Trì: {maintenance})", "@luongtuyen20")
            save_db(db)
    except: pass
    return redirect('/')

@app.route('/admin/backup_db', methods=['POST'])
def backup_database():
    if not session.get('admin_auth'): return redirect('/login')
    db = load_db()
    
    target_chat_id = None
    with db_lock:
        for uid, info in db["bot_users"].items():
            if info.get("username", "").lower() in ["@luongtuyen20", "luongtuyen20"]:
                target_chat_id = uid
                break
    try:
        with open(DB_FILE, 'rb') as f:
            if target_chat_id:
                requests.post(
                    f"{ADMIN_TELEGRAM_API_URL}/sendDocument", 
                    data={"chat_id": target_chat_id, "caption": f"☁️ <b>BACKUP DATABASE</b>\nThời gian: {time.strftime('%Y-%m-%d %H:%M:%S')}\n✅ File Database mới nhất của Server.", "parse_mode": "HTML"}, 
                    files={"document": ("database.json", f)},
                    timeout=10
                )
            else:
                admin_uids = [u for u, i in db["bot_users"].items() if i.get("is_admin")]
                for admin_id in admin_uids:
                    f.seek(0)
                    requests.post(
                        f"{ADMIN_TELEGRAM_API_URL}/sendDocument", 
                        data={"chat_id": admin_id, "caption": f"☁️ <b>BACKUP DATABASE</b>\nThời gian: {time.strftime('%Y-%m-%d %H:%M:%S')}\n✅ Nhấn vào file để tải xuống an toàn.", "parse_mode": "HTML"}, 
                        files={"document": ("database.json", f)},
                        timeout=10
                    )
        with db_lock:
            log_admin_action(db, f"Thực hiện Sao lưu File Database lên Telegram ({'@luongtuyen20' if target_chat_id else 'All Admins'})", "@luongtuyen20")
            save_db(db)
    except: pass
    return redirect('/')

@app.route('/admin/ban_ip', methods=['POST'])
def web_ban_ip():
    if not session.get('admin_auth'): return redirect('/login')
    ip = request.form.get('ip', '').strip()
    if ip:
        db = load_db()
        with db_lock:
            if ip not in db.setdefault("banned_ips", []):
                db["banned_ips"].append(ip)
                log_admin_action(db, f"Đưa IP {ip} vào danh sách Đen (Blacklist)", "@luongtuyen20")
                save_db(db)
    return redirect('/')

@app.route('/admin/unban_ip/<ip>')
def unban_ip(ip):
    if not session.get('admin_auth'): return redirect('/login')
    db = load_db()
    with db_lock:
        if ip in db.setdefault("banned_ips", []):
            db["banned_ips"].remove(ip)
            log_admin_action(db, f"Gỡ IP {ip} khỏi danh sách Đen", "@luongtuyen20")
            save_db(db)
    return redirect('/')

@app.route('/admin/approve', methods=['POST'])
def approve_user():
    if not session.get('admin_auth'): return redirect('/login')
    uid = request.form.get('uid')
    try: dur = int(request.form.get('duration') or 0)
    except: dur = 0
    t = request.form.get('type')
    db = load_db()
    with db_lock:
        if uid in db.get("bot_users", {}):
            is_fb = not uid.isdigit()
            if not dur or dur == 0:
                db["bot_users"][uid]["approved"] = True
                db["bot_users"][uid]["approval_time"] = 0
                log_admin_action(db, f"Phê duyệt trực tiếp User {uid}", "@luongtuyen20")
                msg_ok = "🎉 <b>PHÊ DUYỆT THÀNH CÔNG!</b>\nAdmin đã phê duyệt tài khoản của bạn. Vui lòng gõ /start để sử dụng."
                if is_fb: fb_send_text(uid, msg_ok)
                else: tg_send(uid, msg_ok)
            else:
                dur_ms = dur * multipliers_web.get(t, 60000)
                db["bot_users"][uid]["approval_time"] = int(time.time() * 1000) + dur_ms
                db["bot_users"][uid]["approved"] = False
                log_admin_action(db, f"Hẹn giờ duyệt User {uid} sau {dur} {t}", "@luongtuyen20")
                msg_wait = f"⏳ <b>THÔNG BÁO TỪ ADMIN:</b>\nTài khoản của bạn đã được nhận diện. Bạn sẽ được truy cập Bot sau: <b>{dur} {t}</b> nữa."
                if is_fb: fb_send_text(uid, msg_wait)
                else: tg_send(uid, msg_wait)
            save_db(db)
    return redirect('/')

@app.route('/admin/unapprove_user/<uid>')
def unapprove_user(uid):
    if not session.get('admin_auth'): return redirect('/login')
    db = load_db()
    with db_lock:
        if uid in db.get("bot_users", {}):
            db["bot_users"][uid]["approved"] = False
            db["bot_users"][uid]["approval_time"] = 0
            log_admin_action(db, f"Hủy phê duyệt User {uid}", "@luongtuyen20")
            save_db(db)
            
            is_fb = not uid.isdigit()
            msg_un = "🚫 <b>Tài khoản của bạn đã bị Admin thu hồi quyền truy cập Bot.</b>"
            if is_fb: fb_send_text(uid, msg_un)
            else: tg_send(uid, msg_un)
    return redirect('/')

@app.route('/admin/update_shop', methods=['POST'])
def update_shop():
    if not session.get('admin_auth'): return redirect('/login')
    pkg = request.form.get('package')
    try: price = int(request.form.get('price') or 0)
    except: price = 0
    try: stock = int(request.form.get('stock') or 0)
    except: stock = 0
    
    db = load_db()
    if pkg in db.setdefault("shop", {}):
        with db_lock:
            db["shop"][pkg]["price"] = price
            db["shop"][pkg]["stock"] = stock
            pkg_name = db["shop"][pkg].get("name", pkg)
            log_admin_action(db, f"Cập nhật Shop {pkg_name}: Giá {price}, Tồn {stock}", "@luongtuyen20")
            save_db(db)
            admin_uids = [u for u, i in db["bot_users"].items() if i.get("is_admin")]
            
        msg = f"🛒 <b>CẬP NHẬT SHOP THÀNH CÔNG!</b>\nĐã cập nhật gói <b>{pkg_name}</b>:\n💰 Giá mới: <b>{price:,}đ</b>\n📦 Số lượng kho: <b>{stock}</b> Key"
        try:
            for admin_id in admin_uids: admin_tg_send(admin_id, msg)
        except: pass
                
    return redirect('/')

@app.route('/admin/ban_user', methods=['POST'])
def web_ban_user():
    if not session.get('admin_auth'): return redirect('/login')
    target_user = request.form.get('target_user', '').strip()
    try: dur = int(request.form.get('duration') or 0)
    except: dur = 0
    t = request.form.get('type')
    
    raw_reason = request.form.get('reason', 'Vi phạm chính sách').strip()[:200]
    reason = escape(raw_reason) 
    
    db = load_db()
    
    with db_lock: items = list(db.get("bot_users", {}).items())
    
    target_id = None
    if target_user.startswith('@'):
        u_name = target_user.lower()
        for uid, info in items:
            if info.get("username", "").lower() == u_name: 
                target_id = uid
                break
    else: target_id = target_user

    with db_lock:
        if target_id and target_id in db.get("bot_users", {}):
            if t == 'permanent': exp = 'permanent'
            else: exp = int(time.time() * 1000) + dur * multipliers_web.get(t, 86400000)
            
            db["bot_users"][target_id]["banned_until"] = exp
            db["bot_users"][target_id]["ban_reason"] = raw_reason 
            for p in db["bot_users"][target_id].get("purchases", []):
                if p["key"] in db.get("keys", {}): db["keys"][p["key"]]["status"] = "banned"
            log_admin_action(db, f"Ban User {target_id} - Lý do: {raw_reason}", "@luongtuyen20")
            save_db(db)
            
            is_fb = not target_id.isdigit()
            msg_ban = f"🚫 <b>TÀI KHOẢN CỦA BẠN ĐÃ BỊ KHÓA!</b>\n📝 Lý do: {reason}\n<i>Toàn bộ kết nối của bạn đã bị ngắt.</i>"
            if is_fb: fb_send_text(target_id, msg_ban)
            else: tg_send(target_id, msg_ban)
    return redirect('/')

@app.route('/admin/unban_user/<uid>')
def unban_user(uid):
    if not session.get('admin_auth'): return redirect('/login')
    db = load_db()
    with db_lock:
        if uid in db.get("bot_users", {}):
            db["bot_users"][uid]["banned_until"] = 0
            db["bot_users"][uid]["ban_reason"] = ""
            for p in db["bot_users"][uid].get("purchases", []):
                if p["key"] in db.get("keys", {}) and db["keys"][p["key"]].get("status") == "banned":
                    db["keys"][p["key"]]["status"] = "active"
            log_admin_action(db, f"Mở khóa User {uid}", "@luongtuyen20")
            save_db(db)
            
            is_fb = not uid.isdigit()
            msg_unban = f"✅ <b>Tài khoản của bạn đã được Admin mở khóa!</b>"
            if is_fb: fb_send_text(uid, msg_unban)
            else: tg_send(uid, msg_unban)
    return redirect('/')

@app.route('/admin/delete_user/<uid>')
def delete_user(uid):
    if not session.get('admin_auth'): return redirect('/login')
    db = load_db()
    with db_lock:
        if uid in db.get("bot_users", {}):
            purchases = db["bot_users"][uid].get("purchases", [])
            for p in purchases:
                db.get("keys", {}).pop(p["key"], None)
            db["bot_users"].pop(uid, None)
            log_admin_action(db, f"Xóa vĩnh viễn User {uid} và các Key liên quan", "@luongtuyen20")
            save_db(db)
    return redirect('/')

@app.route('/admin/revoke_user/<uid>')
def revoke_user(uid):
    if not session.get('admin_auth'): return redirect('/login')
    db = load_db()
    with db_lock:
        if uid in db.get("bot_users", {}):
            db["bot_users"][uid]["is_admin"] = False
            db["bot_users"][uid]["admin_key"] = ""
            db["bot_users"][uid]["admin_exp"] = 0
            log_admin_action(db, f"Thu hồi quyền Admin của User {uid}", "@luongtuyen20")
            save_db(db)
    return redirect('/')

@app.route('/admin/action/<action>/<key>')
def key_actions(action, key):
    if not session.get('admin_auth'): return redirect('/login')
    db = load_db()
    with db_lock:
        if key in db.get("keys", {}):
            if action == 'add-dev': db["keys"][key]['maxDevices'] = db["keys"][key].get('maxDevices', 1) + 1
            elif action == 'sub-dev' and db["keys"][key].get('maxDevices', 1) > 1: db["keys"][key]['maxDevices'] -= 1
            elif action == 'ban': db["keys"][key]['status'] = 'banned'
            elif action == 'unban': db["keys"][key]['status'] = 'active'
            elif action == 'delete': db["keys"].pop(key, None)
            elif action == 'reset-dev':
                db["keys"][key]['devices'] = []
                db["keys"][key]['known_ips'] = {}
                db["keys"][key]["bound_olm"] = ""
            elif action == 'toggle_vip': db["keys"][key]['vip'] = not db["keys"][key].get('vip', False)
            log_admin_action(db, f"Action [{action}] thực hiện trên Key {key}", "@luongtuyen20")
            save_db(db)
    return redirect('/')

@app.route('/admin/bind_olm', methods=['POST'])
def web_bind_olm():
    if not session.get('admin_auth'): return redirect('/login')
    key = request.form.get('key', '').strip()
    olm = request.form.get('olm_name', '').strip()
    db = load_db()
    with db_lock:
        if key in db.get("keys", {}):
            db["keys"][key]["bound_olm"] = olm
            log_admin_action(db, f"Ghim OLM {olm} cho Key {key}", "@luongtuyen20")
            save_db(db)
    return redirect('/')

@app.route('/admin/online')
def online_ips():
    if not session.get('admin_auth'): return redirect('/login')
    html_rows = ""
    for k_id, info in list(active_sessions.copy().items()):
        onl_time = time.strftime('%H:%M:%S', time.localtime(info["last_seen"]))
        safe_ip = escape(str(info.get('ip', '')))
        safe_name = escape(str(info.get('olm_name', '')))
        safe_key = escape(str(info.get('key', '')))
        html_rows += f"<tr><td>{safe_ip}</td><td class='text-warning'>{safe_name}</td><td class='text-info'>{safe_key}</td><td>OLM MODE (Github)</td><td>{onl_time}</td><td><a href='/admin/action/ban/{safe_key}' class='btn btn-sm btn-danger'>Khóa Key</a></td></tr>"
    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Giám Sát Online - LVT</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>body{{background:#0a0a12;color:white;}}</style></head><body class="p-4"><div class="container"><div class="d-flex justify-content-between mb-4"><h2>📡 RADAR GIÁM SÁT OLM ONLINE</h2><a href="/" class="btn btn-secondary">Quay lại Dashboard</a></div><div class="card bg-dark p-3"><table class="table table-dark table-hover"><thead><tr><th>IP Máy</th><th>Tên OLM</th><th>Key Đang Dùng</th><th>Loại Kết Nối</th><th>Tín Hiệu Cuối</th><th>Thao Tác</th></tr></thead><tbody>{html_rows if html_rows else "<tr><td colspan='6' class='text-center text-muted'>Hiện không có ai đang làm OLM.</td></tr>"}</tbody></table></div></div><script>setInterval(() => location.reload(), 10000);</script></body></html>'''

@app.route('/')
def dashboard():
    if not session.get('admin_auth'): return redirect('/login')
    db = load_db()
    
    with db_lock:
        s = db.get("shop", {}).copy()
        settings = db.get("settings", {}).copy()
        keys_items = list(db.get("keys", {}).items())
        users_items = list(db.get("bot_users", {}).items())
        logs_list = list(db.get("logs", []))
        security_alerts = list(db.get("security_alerts", []))
        banned_ips = list(db.get("banned_ips", []))
        revenue_logs = list(db.get("revenue_logs", []))
        admin_logs = list(db.get("admin_logs", []))

    v1h = s.get("V_1H") or {"price": 7000, "stock": 999}
    v7d = s.get("V_7D") or {"price": 30000, "stock": 999}
    v30d = s.get("V_30D") or {"price": 85000, "stock": 999}
    v1y = s.get("V_1Y") or {"price": 200000, "stock": 999}

    import datetime
    chart_labels = []
    chart_data = []
    today = datetime.date.today()
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        chart_labels.append(day.strftime("%d/%m"))
        day_start = datetime.datetime.combine(day, datetime.time.min).timestamp() * 1000
        day_end = datetime.datetime.combine(day, datetime.time.max).timestamp() * 1000
        daily_total = sum(item["amount"] for item in revenue_logs if day_start <= item["time"] <= day_end)
        chart_data.append(daily_total)

    shop_status = f"""
    <ul class="list-group list-group-flush mb-2" style="font-size:12px;">
      <li class="list-group-item bg-dark text-light border-secondary p-1">🕒 1 Giờ: <b class="text-warning">{v1h.get('price', 0):,}đ</b> | Kho: <b class="text-info">{v1h.get('stock', 0)}</b></li>
      <li class="list-group-item bg-dark text-light border-secondary p-1">📅 7 Ngày: <b class="text-warning">{v7d.get('price', 0):,}đ</b> | Kho: <b class="text-info">{v7d.get('stock', 0)}</b></li>
      <li class="list-group-item bg-dark text-light border-secondary p-1">📆 30 Ngày: <b class="text-warning">{v30d.get('price', 0):,}đ</b> | Kho: <b class="text-info">{v30d.get('stock', 0)}</b></li>
      <li class="list-group-item bg-dark text-light border-secondary p-1">🏆 1 Năm: <b class="text-warning">{v1y.get('price', 0):,}đ</b> | Kho: <b class="text-info">{v1y.get('stock', 0)}</b></li>
    </ul>
    """

    max_u = settings.get("max_users", 500)
    curr_u = len(users_items)
    discord_webhook = escape(settings.get("discord_webhook", ""))
    is_maintenance = settings.get("maintenance_mode", False)
    
    anti_spam_html = f'''
    <div class="card p-3 mb-4" style="border-color: #00ffcc;">
        <h4><i class="fas fa-shield-alt"></i> Cài Đặt Hệ Thống</h4>
        
        <form action="/admin/backup_db" method="POST" class="mb-3 border-bottom border-secondary pb-3">
            <button type="submit" class="btn btn-outline-info w-100 fw-bold"><i class="fas fa-cloud-download-alt"></i> GỬI BACKUP QUA TELEGRAM</button>
            <small class="text-muted d-block mt-1 text-center" style="font-size:11px;">Gửi file Database gốc về tin nhắn Telegram của @luongtuyen20</small>
        </form>

        <form action="/admin/update_settings" method="POST" class="row g-2">
            <div class="col-12 d-flex justify-content-between align-items-center bg-dark p-2 rounded mb-2 border border-warning">
                <span class="text-warning fw-bold"><i class="fas fa-tools"></i> Chế Độ Bảo Trì</span>
                <div class="form-check form-switch m-0">
                    <input class="form-check-input" type="checkbox" name="maintenance_mode" id="maintenanceMode" {'checked' if is_maintenance else ''}>
                </div>
            </div>
            <div class="col-12">
                <label class="text-info" style="font-size:12px;">Đã dùng: <b>{curr_u} / {max_u}</b> tài khoản</label>
                <input type="number" name="max_users" class="form-control bg-dark text-light border-info mt-1" value="{max_u}" placeholder="Số lượng user tối đa">
            </div>
            <div class="col-12 mt-2">
                <label class="text-warning" style="font-size:12px;"><i class="fab fa-discord"></i> Discord Webhook (Thông báo User mới)</label>
                <input type="text" name="discord_webhook" class="form-control bg-dark text-light border-warning mt-1" value="{discord_webhook}" placeholder="URL Webhook Discord">
            </div>
            <div class="col-12 mt-2"><button type="submit" class="btn btn-info w-100 fw-bold text-dark p-1">LƯU CÀI ĐẶT</button></div>
        </form>
    </div>
    '''

    alerts_html = ""
    for al in security_alerts[:5]:
        al_time = time.strftime('%H:%M %d/%m', time.localtime(al.get('time', 0)/1000))
        alerts_html += f'<li class="list-group-item bg-dark text-light border-danger p-2 mb-1 rounded" style="font-size:12px;"><span class="text-danger fw-bold">[{al_time}]</span><br>Bắn hạ: <b class="text-info">{escape(al.get("user", ""))}</b> ({al.get("id", "")})<br><span class="text-muted">Lý do: {escape(al.get("reason", ""))}</span></li>'
    
    if not alerts_html:
        alerts_html = '<li class="list-group-item bg-dark text-success border-success p-2 rounded" style="font-size:12px;">✅ Không có mối đe dọa nào gần đây.</li>'

    ai_radar_html = f'''
    <div class="card p-3 mb-4" style="border-color: #dc3545;">
        <h4 class="text-danger"><i class="fas fa-user-secret"></i> AI Báo Cáo Bảo Mật</h4>
        <ul class="list-group list-group-flush mt-2">
            {alerts_html}
        </ul>
    </div>
    '''

    blacklist_rows = ""
    for ip in banned_ips:
        blacklist_rows += f'<li class="list-group-item bg-dark text-light d-flex justify-content-between align-items-center" style="font-size:13px;">{escape(ip)} <a href="/admin/unban_ip/{escape(ip)}" class="btn btn-sm btn-danger p-0 px-2">Xóa</a></li>'
    if not blacklist_rows: blacklist_rows = '<li class="list-group-item bg-dark text-muted text-center" style="font-size:13px;">Chưa có IP bị chặn</li>'
    
    blacklist_html = f'''
    <div class="card p-3 mb-4" style="border-color: #ff0000;">
        <h4 class="text-danger"><i class="fas fa-ban"></i> Blacklist IP</h4>
        <form action="/admin/ban_ip" method="POST" class="d-flex gap-2 mb-2">
            <input type="text" name="ip" class="form-control form-control-sm bg-dark text-light" placeholder="Nhập IP..." required>
            <button type="submit" class="btn btn-sm btn-danger">Chặn</button>
        </form>
        <ul class="list-group list-group-flush" style="max-height:150px; overflow-y:auto;">
            {blacklist_rows}
        </ul>
    </div>
    '''

    admin_logs_html = ""
    for alog in admin_logs[:10]:
        l_time = time.strftime('%H:%M %d/%m', time.localtime(alog.get('time', 0)/1000))
        admin_logs_html += f'<li class="list-group-item bg-dark text-light border-secondary p-2 mb-1 rounded" style="font-size:11px;"><span class="text-warning">[{l_time}]</span> {escape(alog.get("action", ""))}</li>'
    if not admin_logs_html:
        admin_logs_html = '<li class="list-group-item bg-dark text-muted text-center" style="font-size:12px;">Chưa có hoạt động</li>'
    
    admin_logs_panel = f'''
    <div class="card p-3 mb-4" style="border-color: #f39c12;">
        <h4 class="text-warning"><i class="fas fa-clipboard-list"></i> Nhật Ký Quản Trị</h4>
        <ul class="list-group list-group-flush mt-2" style="max-height:200px; overflow-y:auto;">
            {admin_logs_html}
        </ul>
    </div>
    '''

    gacha_html = f'''
    <div class="card p-3 mb-4" style="border-color: #ff00ff;">
        <h4 style="color:#ff00ff;"><i class="fas fa-gift"></i> Tặng & Quay Key (Hộp Quà)</h4>
        
        <form action="/admin/gift_key" method="POST" class="row g-2 mt-1">
            <p class="text-info m-0" style="font-size:13px; font-weight:bold;">1. Tặng Trực Tiếp</p>
            <div class="col-12"><textarea name="target_users" class="form-control form-control-sm bg-dark text-light" rows="2" placeholder="Nhập ID/@user (cách nhau dấu phẩy) hoặc nhập ALL để gửi toàn Server" required></textarea></div>
            <div class="col-4"><input type="number" name="duration" class="form-control form-control-sm bg-dark text-light" placeholder="Hạn" required></div>
            <div class="col-4"><select name="type" class="form-select form-select-sm bg-dark text-light"><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option><option value="permanent">V.Viễn</option></select></div>
            <div class="col-4"><input type="number" name="maxDevices" class="form-control form-control-sm bg-dark text-light" value="1" placeholder="Máy"></div>
            <div class="col-6 d-flex align-items-center">
                <div class="form-check form-switch m-0"><input class="form-check-input" type="checkbox" name="is_vip" id="giftVip" checked><label class="form-check-label text-warning" style="font-size:12px;" for="giftVip">VIP</label></div>
            </div>
            <div class="col-6"><button type="submit" class="btn btn-sm w-100 fw-bold" style="background:#ff00ff; color:white;">TẶNG VÀO TÚI ĐỒ</button></div>
        </form>
        
        <hr class="border-secondary my-3">
        
        <form action="/admin/gacha_key" method="POST" class="row g-2">
            <p class="text-warning m-0" style="font-size:13px; font-weight:bold;">2. Vòng Quay May Mắn (%)</p>
            <div class="col-12"><textarea name="target_users" class="form-control form-control-sm bg-dark text-light border-warning" rows="2" placeholder="Nhập ID/@user (cách nhau dấu phẩy) hoặc nhập ALL để quay toàn Server" required></textarea></div>
            <div class="col-6"><select name="package" class="form-select form-select-sm bg-dark text-light"><option value="V_1H">Gói 1 Giờ</option><option value="V_7D">Gói 7 Ngày</option><option value="V_30D">Gói 30 Ngày</option><option value="V_1Y">Gói 1 Năm</option></select></div>
            <div class="col-6"><input type="number" name="win_rate" class="form-control form-control-sm bg-dark text-light border-warning" placeholder="Tỉ lệ trúng (1-100)" required min="1" max="100"></div>
            <div class="col-12"><button type="submit" class="btn btn-sm btn-warning w-100 fw-bold text-dark">QUAY THƯỞNG</button></div>
        </form>
    </div>
    '''

    keys_html = ''
    for k, data in keys_items:
        is_banned = data.get('status') == 'banned'
        is_vip = data.get('vip', False)
        sys_target = data.get('target', 'tool')
        status_badge = '<span class="badge bg-danger">BANNED</span>' if is_banned else ('<span class="badge bg-warning text-dark">VIP</span>' if is_vip else '<span class="badge bg-success">THƯỜNG</span>')
        
        if sys_target == 'tool': sys_badge = '<span class="badge bg-info">LVT Tool</span>'
        elif sys_target == 'admin_bot': sys_badge = '<span class="badge bg-dark border border-light">🤖 ADMIN BOT</span>'
        else: sys_badge = '<span class="badge bg-danger">OLM</span>'

        current_time = int(time.time() * 1000)
        is_expired = False
        if data.get('exp') == 'pending': exp_text = '<span class="text-info">Chờ kích hoạt</span>'
        elif data.get('exp') == 'permanent': exp_text = '<span class="text-success fw-bold">Vĩnh viễn</span>'
        else:
            is_expired = current_time > data.get('exp', 0)
            exp_text = f'<span class="{"text-danger fw-bold" if is_expired else "text-light"}">{time.strftime("%d/%m/%Y %H:%M", time.localtime(data.get("exp", 0) / 1000))}</span>'
            
        if is_expired: status_badge = '<span class="badge bg-secondary">HẾT HẠN</span>'
        
        bnd = data.get('bound_olm', '')
        safe_bnd = escape(str(bnd))
        safe_k = escape(str(k))
        bnd_html = f'<br><small class="text-warning">Chỉ định: {safe_bnd}</small>' if safe_bnd else ''

        keys_html += f'''
        <tr class="key-row" data-status="{ "banned" if is_banned else ("expired" if is_expired else "active") }">
            <td><div class="d-flex align-items-center"><strong class="me-2 text-info">{safe_k}</strong><button class="btn btn-sm btn-outline-light copy-btn" onclick="copyText('{safe_k}')" title="Sao chép">📋</button></div><div class="mt-1">{status_badge} {sys_badge}{bnd_html}</div></td>
            <td>{exp_text}</td><td><span class="badge bg-primary">{len(data.get('devices', []))}/{data.get('maxDevices', 1)}</span></td>
            <td><div class="btn-group btn-group-sm"><button class="btn btn-warning" onclick="openBindModal('{safe_k}', '{safe_bnd}')">🔐 Ghim</button><button class="btn btn-info" onclick="openExtendModal('{safe_k}')">⏳</button><a href="/admin/action/add-dev/{safe_k}" class="btn btn-success">+</a><a href="/admin/action/sub-dev/{safe_k}" class="btn btn-secondary">-</a><a href="/admin/action/reset-dev/{safe_k}" class="btn btn-primary">🔄</a><a href="/admin/action/{"unban" if is_banned else "ban"}/{safe_k}" class="btn btn-{"light" if is_banned else "danger"}">{"Mở" if is_banned else "Khóa"}</a><a href="/admin/action/toggle_vip/{safe_k}" class="btn btn-warning text-dark">VIP↕</a><a href="/admin/action/delete/{safe_k}" class="btn btn-dark" onclick="return confirm('Xóa?')">🗑️</a></div></td>
        </tr>'''

    users_html = ''
    now_ms = int(time.time() * 1000)
    for uid, udata in users_items:
        uname = udata.get("username", "")
        safe_uname = escape(str(uname)) if uname else ""
        safe_name = escape(str(udata.get("name", "Khách")))
        uname_html = f'<span class="text-warning">{safe_uname}</span>' if safe_uname else ''
        is_adm = udata.get("is_admin", False)
        adm_badge = '<span class="badge bg-danger mt-1">Admin Bot</span>' if is_adm else ''
        
        banned_until = udata.get("banned_until", 0)
        is_banned_user = banned_until == "permanent" or (isinstance(banned_until, int) and banned_until > now_ms)
        banned_badge = f'<span class="badge bg-danger mt-1" title="{escape(str(udata.get("ban_reason", "")))}">BỊ KHÓA</span>' if is_banned_user else ''
        
        is_approved = udata.get("approved", False)
        appr_badge = '<span class="badge bg-success mt-1">Đã Duyệt</span>' if is_approved else '<span class="badge bg-warning text-dark mt-1 border border-warning">Chờ Cấp Phép</span>'
        
        row_status = "banned" if is_banned_user else ("approved" if is_approved else "pending")

        revoke_btn = f'<a href="/admin/revoke_user/{escape(str(uid))}" class="btn btn-sm btn-outline-danger mt-1" style="font-size:12px;">Thu hồi Admin</a>' if is_adm else ''
        if is_banned_user:
            revoke_btn += f'<a href="/admin/unban_user/{escape(str(uid))}" class="btn btn-sm btn-success mt-1 ms-1" style="font-size:12px;">Mở Khóa User</a>'
        else:
            revoke_btn += f'<button type="button" class="btn btn-sm btn-danger mt-1 ms-1" style="font-size:12px;" onclick="openBanModal(\'{escape(str(uid))}\', \'{safe_name}\')">Khóa</button>'
        
        revoke_btn += f'<a href="/admin/delete_user/{escape(str(uid))}" class="btn btn-sm btn-outline-light mt-1 ms-1" style="font-size:12px;" onclick="return confirm(\'Xóa vĩnh viễn user này khỏi DB?\')">🗑️ Xóa User</a>'

        appr_ui = ""
        if not is_approved:
            appr_ui = f'''<div class="mt-2 p-1 border border-secondary rounded" style="background:#1e1e2d;"><form action="/admin/approve" method="POST" class="d-flex flex-wrap gap-1 align-items-center"><input type="hidden" name="uid" value="{escape(str(uid))}"><input type="number" name="duration" class="form-control form-control-sm bg-dark text-light border-secondary" style="width:50px; font-size:11px; padding:2px;" placeholder="Số" required><select name="type" class="form-select form-select-sm bg-dark text-light border-secondary" style="width:65px; font-size:11px; padding:2px;"><option value="min">Phút</option><option value="hour">Giờ</option><option value="day">Ngày</option></select><button type="submit" class="btn btn-sm btn-success" style="font-size:11px; padding:2px 5px;">Hẹn Giờ Duyệt</button></form><form action="/admin/approve" method="POST" class="mt-1"><input type="hidden" name="uid" value="{escape(str(uid))}"><input type="hidden" name="duration" value="0"><button type="submit" class="btn btn-sm btn-primary w-100 fw-bold" style="font-size:11px; padding:2px;">DUYỆT NGAY LẬP TỨC</button></form></div>'''
        else:
            appr_ui = f'<a href="/admin/unapprove_user/{escape(str(uid))}" class="btn btn-sm btn-outline-warning mt-1" style="font-size:11px; padding:2px 5px;">Hủy Duyệt</a>'

        owned_keys = [p["key"] for p in udata.get("purchases", [])]
        user_ips = set()
        user_logs = []
        for l in logs_list:
            if l.get("key") in owned_keys:
                user_ips.add(l.get("ip", "N/A"))
                user_logs.append(f"{time.strftime('%d/%m %H:%M', time.localtime(l.get('time', 0)))}: {escape(str(l.get('action', '')))} ({escape(str(l.get('olm_name','')))})")
        
        ips_str = "<br>".join([escape(str(i)) for i in user_ips]) if user_ips else "<span class='text-muted'>Chưa có IP</span>"
        keys_str = "<br>".join([escape(str(k)) for k in owned_keys]) if owned_keys else "<span class='text-muted'>Chưa mua Key</span>"
        logs_str = "<br>".join(user_logs[:3]) + ("<br>..." if len(user_logs)>3 else "") if user_logs else "<span class='text-muted'>Chưa có HĐ</span>"

        users_html += f'''
        <tr class="user-row" data-status="{row_status}">
            <td><strong class="text-info" style="cursor:pointer;" onclick="copyText('{safe_name}')" title="Sao chép tên">{safe_name}</strong> {uname_html}<br><small class="text-muted" style="cursor:pointer;" onclick="copyText('{escape(str(uid))}')" title="Sao chép ID">{escape(str(uid))}</small><br>{appr_badge} {adm_badge} {banned_badge}<br>{revoke_btn}</td>
            <td style="width:160px;">{appr_ui}</td>
            <td><span class="badge bg-success">{udata.get("balance", 0):,}đ</span><br><small>Reset: {udata.get("resets", 0)}</small></td>
            <td>{keys_str}</td>
            <td style="font-size:12px;">{logs_str}</td>
            <td style="font-size:12px;" class="text-secondary">{ips_str}</td>
        </tr>'''

    user_filter_html = '''
    <div class="d-flex justify-content-between align-items-center mb-2">
        <select id="statusUserFilter" class="form-select form-select-sm bg-dark text-light border-info w-auto" onchange="filterUsers()">
            <option value="all">👁️ Xem Tất Cả User</option>
            <option value="pending">⏳ Đang Chờ Duyệt</option>
            <option value="approved">✅ Đã Phê Duyệt</option>
            <option value="banned">🚫 Bị Khóa (Ban)</option>
        </select>
        <input type="text" id="searchUser" class="form-control form-control-sm bg-dark text-light border-info w-50" placeholder="🔍 Tìm kiếm Tên/ID..." onkeyup="filterUsers()">
    </div>
    '''

    return f'''
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>LVT PRO - Admin</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><script src="https://cdn.jsdelivr.net/npm/chart.js"></script><style>:root {{ --bg-main: #0a0a12; --bg-card: #151525; --neon-cyan: #00ffcc; --neon-purple: #bd00ff; }} body {{ background: var(--bg-main); color: #e0e0e0; font-family: 'Segoe UI', Tahoma, sans-serif; }} .card {{ background: var(--bg-card); border: 1px solid #2a2a40; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }} h1, h4 {{ color: var(--neon-cyan); font-weight: 800; }} .btn-primary {{ background: linear-gradient(45deg, var(--neon-purple), #7a00ff); border: none; font-weight: bold; }} .table-container {{ max-height: 500px; overflow-y: auto; }} tbody tr:hover {{ background-color: rgba(0, 255, 204, 0.05) !important; }} #toastBox {{ position: fixed; bottom: 20px; right: 20px; z-index: 9999; }}</style></head><body class="p-2 p-md-4"><div id="toastBox"></div><div class="container-fluid"><div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary"><h1 class="m-0">⚡ LVT ADMIN</h1><div><a href="/admin/online" class="btn btn-success me-2 fw-bold">📡 Giám Sát IP Online</a><a href="/logout" class="btn btn-outline-danger">Đăng xuất</a></div></div><div class="row g-4"><div class="col-lg-3">
    
    <div class="card p-3 mb-4" style="border-color: #00ffcc;">
        <h4><i class="fas fa-chart-line"></i> Doanh Thu 7 Ngày</h4>
        <canvas id="revenueChart" style="height: 200px; width: 100%;"></canvas>
    </div>
    
    {admin_logs_panel}
    {ai_radar_html}
    {blacklist_html}
    {gacha_html}
    {anti_spam_html}
    
    <div class="card p-3 mb-4" style="border-color: #ff3366;"><h4><i class="fas fa-crosshairs"></i> Tạo Key OLM</h4><form action="/admin/create" method="POST" class="row g-2"><input type="hidden" name="target_app" value="olm"><div class="col-6"><input type="text" name="prefix" class="form-control bg-dark text-light" placeholder="Prefix (Mặc định: OLM)"></div><div class="col-6"><input type="number" name="quantity" class="form-control bg-dark text-light" value="1"></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="min">Phút</option><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-6"><input type="number" name="maxDevices" class="form-control bg-dark text-light" placeholder="Max TB" value="1"></div><div class="col-6 d-flex align-items-end"><div class="form-check form-switch"><input class="form-check-input" type="checkbox" name="is_vip" id="vipSwitch2"><label class="form-check-label text-warning" for="vipSwitch2">Chế độ VIP</label></div></div><div class="col-12 mt-3"><button type="submit" class="btn btn-primary w-100" style="background: linear-gradient(45deg, #ff3366, #ff9900); color:white;">TẠO KEY OLM</button></div></form></div>
    
    <div class="card p-3 mb-4" style="border-color: #fff;"><h4><i class="fas fa-robot"></i> Cấp Quyền Admin Bot</h4><form action="/admin/grant" method="POST" class="row g-2"><div class="col-12"><input type="text" name="username" class="form-control bg-dark text-light" placeholder="Nhập @username hoặc ID khách..." required></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="sec">Giây</option><option value="min">Phút</option><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option><option value="year">Năm</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-12 mt-2"><button type="submit" class="btn btn-light w-100 fw-bold text-dark">CẤP QUYỀN ADMIN</button></div></form></div>

    <div class="card p-3 mb-4" style="border-color: #ff9900;"><h4><i class="fas fa-store"></i> Quản Lý Kho & Giá</h4>{shop_status}<form action="/admin/update_shop" method="POST" class="row g-2"><div class="col-12"><select name="package" class="form-select bg-dark text-light"><option value="V_1H">Gói 1 Giờ</option><option value="V_7D">Gói 7 Ngày</option><option value="V_30D">Gói 30 Ngày</option><option value="V_1Y">Gói 1 Năm</option></select></div><div class="col-6"><input type="number" name="price" class="form-control bg-dark text-light" placeholder="Giá tiền (VNĐ)" required></div><div class="col-6"><input type="number" name="stock" class="form-control bg-dark text-light" placeholder="Số lượng kho" required></div><div class="col-12 mt-2"><button type="submit" class="btn btn-warning w-100 fw-bold">LƯU CẬP NHẬT SHOP</button></div></form></div>
    
    </div><div class="col-lg-9">
    
    <div class="card p-3 mb-4" style="border-color: #2AABEE;">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h4><i class="fab fa-telegram"></i> Quản Lý User & Cấp Phép Cổng Chào Bot</h4>
        </div>
        <form action="/admin/direct_approve" method="POST" class="row g-2 mb-3 border-bottom pb-3 border-secondary">
            <div class="col-9"><input type="text" name="target_user" class="form-control bg-dark text-light border-success" placeholder="Nhập @username / ID để duyệt đặc cách vào thẳng Bot..." required></div>
            <div class="col-3"><button type="submit" class="btn btn-success w-100 fw-bold">Vào Bot Luôn</button></div>
        </form>
        <form action="/admin/add_balance" method="POST" class="row g-2 mb-3 border-bottom pb-3 border-secondary">
            <div class="col-3"><input type="text" name="target_user" class="form-control bg-dark text-light" placeholder="Nhập @username / ID..." required></div>
            <div class="col-3"><input type="number" name="amount" class="form-control bg-dark text-light" placeholder="Tiền (VD: 50000)" value="0" required></div>
            <div class="col-3"><input type="number" name="resets" class="form-control bg-dark text-light" placeholder="+ Lượt Reset" value="0" required></div>
            <div class="col-3"><button type="submit" class="btn w-100 fw-bold" style="background:#2AABEE; color:white;">Nạp Tiền Nhanh</button></div>
        </form>
        {user_filter_html}
        <div class="table-container" style="max-height:400px;">
            <table class="table table-dark table-sm table-bordered mb-0 align-middle">
                <thead class="table-active">
                    <tr>
                        <th>Người Dùng</th>
                        <th>Phê Duyệt Vào Bot</th>
                        <th>Số Dư</th>
                        <th>Các Key Sở Hữu</th>
                        <th>Lịch Sử Gần Đây</th>
                        <th>IP Truy Cập</th>
                    </tr>
                </thead>
                <tbody id="userTableBody">{users_html}</tbody>
            </table>
        </div>
    </div>
    
    <div class="card p-3 mb-4"><div class="d-flex justify-content-between align-items-center mb-3"><h4>📋 Quản Lý Key</h4><div class="d-flex gap-2"><form action="/admin/delete_all" method="POST"><button class="btn btn-sm btn-danger fw-bold" onclick="return confirm('CHẮC CHẮN XÓA TOÀN BỘ KEY?')">Xóa ALL Key</button></form><select id="statusFilter" class="form-select form-select-sm bg-dark text-light" onchange="filterTable()"><option value="all">Tất cả</option><option value="active">Hoạt động</option><option value="expired">Hết hạn</option><option value="banned">Bị khóa</option></select><input type="text" id="searchInput" class="form-control form-control-sm bg-dark text-light" placeholder="Tìm Key..." onkeyup="filterTable()"></div></div><div class="table-container"><table class="table table-dark table-hover mb-0 align-middle"><thead><tr><th>Key</th><th>Hạn</th><th>Thiết bị</th><th>Điều Khiển</th></tr></thead><tbody id="keyTableBody">{keys_html}</tbody></table></div></div>
    
    </div></div>
    
    <div class="modal fade" id="extendModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:var(--bg-card);"><div class="modal-header"><h5 class="modal-title">⏳ Gia hạn Key</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form action="/admin/extend" method="POST"><div class="modal-body"><input type="hidden" name="key" id="extendKeyInput"><p>Key: <strong id="extendKeyDisplay" class="text-info"></strong></p><div class="row g-2"><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option></select></div></div></div><div class="modal-footer"><button type="submit" class="btn btn-primary w-100">Gia hạn</button></div></form></div></div></div>
    <div class="modal fade" id="bindModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:var(--bg-card);"><div class="modal-header"><h5 class="modal-title">🔐 Ghim Độc Quyền Account</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form action="/admin/bind_olm" method="POST"><div class="modal-body"><input type="hidden" name="key" id="bindKeyInput"><p>Key: <strong id="bindKeyDisplay" class="text-info"></strong></p><div class="row g-2"><div class="col-12"><input type="text" name="olm_name" id="bindOlmInput" class="form-control bg-dark text-light" placeholder="Nhập tên OLM muốn ghim (bỏ trống để hủy ghim)"></div></div></div><div class="modal-footer"><button type="submit" class="btn btn-warning w-100">Lưu Chỉ Định</button></div></form></div></div></div>
    
    <div class="modal fade" id="banModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:var(--bg-card);"><div class="modal-header"><h5 class="modal-title text-danger">🚫 Khóa Trừng Phạt User</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form action="/admin/ban_user" method="POST"><div class="modal-body"><input type="hidden" name="target_user" id="banTargetInput"><p>Tài khoản: <strong id="banTargetDisplay" class="text-info"></strong></p><p class="text-muted" style="font-size:12px;">Thao tác này sẽ cấm user dùng Bot và Tự Động Khóa toàn bộ các Key của người này để triệt tiêu Script OLM.</p><div class="row g-2"><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="min">Phút</option><option value="hour">Giờ</option><option value="day">Ngày</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-12"><input type="text" name="reason" class="form-control bg-dark text-light" placeholder="Lý do khóa (VD: Hack Spam)"></div></div></div><div class="modal-footer"><button type="submit" class="btn btn-danger w-100">KHÓA TÀI KHOẢN NÀY</button></div></form></div></div></div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const ctx = document.getElementById('revenueChart').getContext('2d');
        const revenueChart = new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(chart_labels)},
                datasets: [{{
                    label: 'Doanh thu (VNĐ)',
                    data: {json.dumps(chart_data)},
                    backgroundColor: 'rgba(0, 255, 204, 0.6)',
                    borderColor: 'rgba(0, 255, 204, 1)',
                    borderWidth: 1
                }}]
            }},
            options: {{ scales: {{ y: {{ beginAtZero: true, ticks: {{ color: '#ccc' }} }}, x: {{ ticks: {{ color: '#ccc' }} }} }}, plugins: {{ legend: {{ labels: {{ color: '#fff' }} }} }} }}
        }});

        function copyText(text) {{ navigator.clipboard.writeText(text); alert("Đã copy: " + text); }} 
        function filterTable() {{ let s = document.getElementById('searchInput').value.toLowerCase(), f = document.getElementById('statusFilter').value; document.querySelectorAll('.key-row').forEach(r => {{ r.style.display = (r.innerText.toLowerCase().includes(s) && (f==='all' || r.dataset.status===f)) ? '' : 'none'; }}); }} 
        
        function filterUsers() {{
            let s = document.getElementById('searchUser').value.toLowerCase();
            let f = document.getElementById('statusUserFilter').value;
            document.querySelectorAll('.user-row').forEach(r => {{
                r.style.display = (r.innerText.toLowerCase().includes(s) && (f === 'all' || r.dataset.status === f)) ? '' : 'none';
            }});
        }}

        function openExtendModal(key) {{ document.getElementById('extendKeyInput').value = key; document.getElementById('extendKeyDisplay').innerText = key; new bootstrap.Modal(document.getElementById('extendModal')).show(); }}
        function openBindModal(key, current_olm) {{ document.getElementById('bindKeyInput').value = key; document.getElementById('bindKeyDisplay').innerText = key; document.getElementById('bindOlmInput').value = current_olm; new bootstrap.Modal(document.getElementById('bindModal')).show(); }}
        function openBanModal(uid, name) {{ document.getElementById('banTargetInput').value = uid; document.getElementById('banTargetDisplay').innerText = name + ' (' + uid + ')'; new bootstrap.Modal(document.getElementById('banModal')).show(); }}

        let reloadTimer = setTimeout(() => location.reload(), 20000);
        document.querySelectorAll('input, select, textarea').forEach(el => {{
            el.addEventListener('focus', () => clearTimeout(reloadTimer));
            el.addEventListener('blur', () => reloadTimer = setTimeout(() => location.reload(), 20000));
        }});
    </script></body></html>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)

