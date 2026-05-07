import os, json, time, random, hashlib, threading, requests, re, shutil, base64, secrets, datetime, hmac, string
from concurrent.futures import ThreadPoolExecutor
from html import escape
from urllib.parse import urlparse
from flask import Flask, request, jsonify, redirect, make_response, session, abort

try:
    os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
    time.tzset()
except: pass

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

FB_PAGE_TOKEN = os.environ.get('FB_PAGE_TOKEN', 'EAAVZBVODIGsYBRVhjcsp9PNaiCjMASMQRGQd20JEqPbxuEJ3WnrZBqtVY5DQ9xOZBj4wDwU6KwpHGOuJnHESEkXMKZAGUdCIzlFJAPUPUaDnJa8t3VnOhQxZBTxEum4NOXm9IKINCes2ES07u6Xg1TSxHH7FemiVPRRL4upPPT7vORRVpRPZBiUmZCZAd7CWZBxSHKTlINT1C5QZDZD')
FB_VERIFY_TOKEN = WEBHOOK_SECRET

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
    if any(bot in ua for bot in blocked_bots) and not request.path.startswith("/admin_webhook") and not request.path.startswith("/fb_webhook"):
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
                data = {"keys": {}, "logs": [], "bot_users": {}, "active_scripts": {}, "settings": {}, "security_alerts": [], "banned_ips": [], "admin_logs": []}
                
            try:
                data.setdefault("bot_users", {})
                data.setdefault("keys", {})
                data.setdefault("logs", [])
                data.setdefault("banned_ips", [])
                data.setdefault("admin_logs", [])
                data.setdefault("security_alerts", []) 
                
                settings_data = data.setdefault("settings", {})
                settings_data.setdefault("maintenance_mode", False)
                settings_data.setdefault("admin_password_hash", DEFAULT_ADMIN_PASSWORD_HASH)
                
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
    if request.path.startswith('/api/') or request.path.startswith('/check'):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

ADMIN_BOT_TOKEN = os.environ.get('ADMIN_BOT_TOKEN', "8714375866:AAG9r0aCCFOKtgR6B-LcFYBAnJ7x9yMs-8o")
ADMIN_TELEGRAM_API_URL = f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}"

try:
    ADMIN_BOT_INFO = requests.get(f"{ADMIN_TELEGRAM_API_URL}/getMe").json()
    ADMIN_BOT_USERNAME = ADMIN_BOT_INFO.get("result", {}).get("username", "admin_lvt_bot")
except:
    ADMIN_BOT_USERNAME = "admin_lvt_bot"

WEB_URL = "https://app-tool-trlp.onrender.com"

multipliers_web = {'sec': 1000, 'min': 60000, 'hour': 3600000, 'day': 86400000, 'month': 2592000000, 'year': 31536000000}

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
            if res.status_code == 429:
                time.sleep(int(res.headers.get("Retry-After", 1)))
                continue
            return res.json()
        except: time.sleep(1)
    return {}

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

        if msg_text and msg_text.lower().startswith('/start'):
            safe_tg_request(f"{ADMIN_TELEGRAM_API_URL}/deleteMessage", {"chat_id": chat_id, "message_id": msg_id})

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
                            chars = string.ascii_letters + string.digits
                            rand_part = ''.join(random.choices(chars, k=14))
                            nk = f"{pfx}{rand_part}"
                            db["keys"][nk] = {"exp": "pending", "durationMs": dur_ms, "maxDevices": 1, "devices": [], "known_ips": {}, "status": "active", "vip": True, "target": "olm", "bound_olm": "", "loader_enabled": True}
                            gen_keys.append(nk)
                        user["admin_state"] = "none"
                        log_admin_action(db, f"Tạo {qty} key {days} ngày ({pfx}) qua Bot", safe_name)
                        save_db(db)
                    k_str = "\n".join([f"<code>{k}</code>" for k in gen_keys])
                    user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], f"✅ <b>TẠO KEY THÀNH CÔNG</b>\n\n{k_str}", {"inline_keyboard": [[{"text": "🔙 Về Menu", "callback_data": "ADM_MAIN"}]]})
                else:
                    user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], "❌ Sai định dạng! Nhập lại (Ví dụ: <code>30 5 T</code>):", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MAIN"}]]})

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

        if payload:
            if payload == "ADM_MAIN":
                with db_lock: user["admin_state"] = "none"
                txt = "👑 <b>BẢNG ĐIỀU KHIỂN SERVER (ĐỘC QUYỀN)</b>\n➖➖➖➖➖➖➖➖➖➖\n\nChế độ quyền lực cao nhất. Hãy chọn chức năng:"
                markup = {
                    "inline_keyboard": [
                        [{"text": "📊 Thống Kê Server", "callback_data": "ADM_STATS"}],
                        [{"text": "🔑 Tạo Key Nhanh", "callback_data": "ADM_CREATE"}],
                        [{"text": "⚙️ Đổi Pass Web Admin", "callback_data": "ADM_PASS"}],
                        [{"text": "🛑 Blacklist IP", "callback_data": "ADM_BLACKLIST"}, {"text": "☁️ Backup DB", "callback_data": "ADM_BACKUP"}]
                    ]
                }
                user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], txt, markup)
            
            elif payload == "ADM_STATS":
                with db_lock:
                    total_k = len(db.get("keys", {}))
                    banned_ips_c = len(db.get("banned_ips", []))
                    
                txt = f"📊 <b>THỐNG KÊ MÁY CHỦ (LIVE)</b>\n➖➖➖➖➖➖➖➖\n🔑 Tổng Key: <b>{total_k}</b>\n🛡️ IP bị Firewall chặn: <b>{banned_ips_c}</b> IP"
                markup = {"inline_keyboard": [[{"text": "🔙 Quay Lại", "callback_data": "ADM_MAIN"}]]}
                user["main_menu_id"] = admin_tg_edit(chat_id, user["main_menu_id"], txt, markup)
                
            elif payload == "ADM_CREATE":
                with db_lock: user["admin_state"] = "wait_create_key"
                txt = "🔑 <b>TẠO KEY TOOL VIP NHANH</b>\n\n📝 Nhập theo cú pháp: <code>Số_Ngày Số_Lượng Prefix</code>\n👉 Ví dụ tạo 5 key 30 ngày: <code>30 5 T</code>"
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
# API TÀNG HÌNH (SPOOFER & CẤP PHÉP KEY TOOL)
# ========================================================
@app.route('/check', methods=['GET', 'OPTIONS'])
def check_license_get():
    ip = get_real_ip()
    if request.method == 'OPTIONS': return make_response("ok", 200)
    
    db = load_db()
    if db.get("settings", {}).get("maintenance_mode", False):
        return jsonify({"status": "error", "message": "Server đang bảo trì hệ thống. Vui lòng thử lại sau!"}), 503
        
    key = request.args.get('key', '').strip()
    if not key:
        return jsonify({"status": "error", "message": "Vui lòng nhập mã Key!"}), 400
        
    valid, msg = _core_validate(db, key)
    if not valid: return jsonify({"status": "error", "message": msg}), 400
    
    return jsonify({"status": "success", "message": "Xác thực thành công!"}), 200

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

# ========================================================
# GIAO DIỆN WEB ADMIN CHÍNH
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
        
        if hmac.compare_digest(hashlib.sha256(request.form.get('password', '').encode()).hexdigest(), current_admin_hash):
            session['admin_auth'] = True 
            session['admin_ip'] = ip 
            with db_lock: log_admin_action(db, f"Đăng nhập Web Admin thành công từ IP: {ip}", "Hệ thống")
            save_db(db)
            if ip in login_attempts: del login_attempts[ip]
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
    
    db = load_db()
    with db_lock:
        for _ in range(qty):
            chars = string.ascii_letters + string.digits
            rand_part = ''.join(random.choices(chars, k=14))
            nk = f"{pfx}{rand_part}" if pfx else rand_part
            
            db["keys"][nk] = {"exp": "pending", "maxDevices": md, "devices": [], "known_ips": {}, "status": "active", "vip": vip, "target": target_app, "bound_olm": "", "loader_enabled": True}
            if t != 'permanent': db["keys"][nk]["durationMs"] = dur * multipliers_web.get(t, 86400000)
            else: db["keys"][nk]["exp"] = "permanent"
        log_admin_action(db, f"Tạo {qty} Key Tool mới ({dur} {t})", "@luongtuyen20")
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

@app.route('/admin/update_settings', methods=['POST'])
def update_settings():
    if not session.get('admin_auth'): return redirect('/login')
    db = load_db()
    try:
        maintenance = request.form.get('maintenance_mode') == 'on'
        with db_lock:
            db.setdefault("settings", {})["maintenance_mode"] = maintenance
            log_admin_action(db, f"Cập nhật Bảo Trì: {maintenance}", "@luongtuyen20")
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
            log_admin_action(db, f"Thực hiện Sao lưu File Database lên Telegram", "@luongtuyen20")
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
        html_rows += f"<tr><td>{safe_ip}</td><td class='text-warning'>{safe_name}</td><td class='text-info'>{safe_key}</td><td>Violentmonkey</td><td>{onl_time}</td><td><a href='/admin/action/ban/{safe_key}' class='btn btn-sm btn-danger'>Khóa Key</a></td></tr>"
    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Giám Sát Online - LVT</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>body{{background:#0a0a12;color:white;}}</style></head><body class="p-4"><div class="container"><div class="d-flex justify-content-between mb-4"><h2>📡 RADAR GIÁM SÁT ONLINE</h2><a href="/" class="btn btn-secondary">Quay lại Dashboard</a></div><div class="card bg-dark p-3"><table class="table table-dark table-hover"><thead><tr><th>IP Máy</th><th>Target Info</th><th>Key Đang Dùng</th><th>Loại Kết Nối</th><th>Tín Hiệu Cuối</th><th>Thao Tác</th></tr></thead><tbody>{html_rows if html_rows else "<tr><td colspan='6' class='text-center text-muted'>Hiện không có thiết bị kết nối.</td></tr>"}</tbody></table></div></div><script>setInterval(() => location.reload(), 10000);</script></body></html>'''

@app.route('/')
def dashboard():
    if not session.get('admin_auth'): return redirect('/login')
    db = load_db()
    
    with db_lock:
        settings = db.get("settings", {}).copy()
        keys_items = list(db.get("keys", {}).items())
        security_alerts = list(db.get("security_alerts", []))
        banned_ips = list(db.get("banned_ips", []))
        admin_logs = list(db.get("admin_logs", []))

    is_maintenance = settings.get("maintenance_mode", False)
    
    anti_spam_html = f'''
    <div class="card p-3 mb-4" style="border-color: #00ffcc;">
        <h4><i class="fas fa-shield-alt"></i> Cài Đặt Hệ Thống</h4>
        
        <form action="/admin/backup_db" method="POST" class="mb-3 border-bottom border-secondary pb-3">
            <button type="submit" class="btn btn-outline-info w-100 fw-bold"><i class="fas fa-cloud-download-alt"></i> GỬI BACKUP QUA TELEGRAM</button>
        </form>

        <form action="/admin/update_settings" method="POST" class="row g-2">
            <div class="col-12 d-flex justify-content-between align-items-center bg-dark p-2 rounded mb-2 border border-warning">
                <span class="text-warning fw-bold"><i class="fas fa-tools"></i> Chế Độ Bảo Trì</span>
                <div class="form-check form-switch m-0">
                    <input class="form-check-input" type="checkbox" name="maintenance_mode" id="maintenanceMode" {'checked' if is_maintenance else ''}>
                </div>
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

    keys_html = ''
    for k, data in keys_items:
        is_banned = data.get('status') == 'banned'
        is_vip = data.get('vip', False)
        sys_target = data.get('target', 'tool')
        status_badge = '<span class="badge bg-danger">BANNED</span>' if is_banned else ('<span class="badge bg-warning text-dark">VIP</span>' if is_vip else '<span class="badge bg-success">THƯỜNG</span>')
        
        sys_badge = '<span class="badge bg-info">LVT Tool</span>'

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

    return f'''
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>LVT PRO - Admin</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>:root {{ --bg-main: #0a0a12; --bg-card: #151525; --neon-cyan: #00ffcc; --neon-purple: #bd00ff; }} body {{ background: var(--bg-main); color: #e0e0e0; font-family: 'Segoe UI', Tahoma, sans-serif; }} .card {{ background: var(--bg-card); border: 1px solid #2a2a40; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }} h1, h4 {{ color: var(--neon-cyan); font-weight: 800; }} .btn-primary {{ background: linear-gradient(45deg, var(--neon-purple), #7a00ff); border: none; font-weight: bold; }} .table-container {{ max-height: 500px; overflow-y: auto; }} tbody tr:hover {{ background-color: rgba(0, 255, 204, 0.05) !important; }} #toastBox {{ position: fixed; bottom: 20px; right: 20px; z-index: 9999; }}</style></head><body class="p-2 p-md-4"><div id="toastBox"></div><div class="container-fluid"><div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary"><h1 class="m-0">⚡ LVT ADMIN (SERVER TOOL)</h1><div><a href="/admin/online" class="btn btn-success me-2 fw-bold">📡 Giám Sát IP Online</a><a href="/logout" class="btn btn-outline-danger">Đăng xuất</a></div></div><div class="row g-4"><div class="col-lg-3">
    
    {admin_logs_panel}
    {ai_radar_html}
    {blacklist_html}
    {anti_spam_html}
    
    <div class="card p-3 mb-4" style="border-color: #ff3366;"><h4><i class="fas fa-crosshairs"></i> Tạo Key Tool</h4><form action="/admin/create" method="POST" class="row g-2"><input type="hidden" name="target_app" value="tool"><div class="col-6"><input type="text" name="prefix" class="form-control bg-dark text-light" placeholder="Tiền Tố (VD: T)"></div><div class="col-6"><input type="number" name="quantity" class="form-control bg-dark text-light" value="1" placeholder="Số Lượng"></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="min">Phút</option><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-6"><input type="number" name="maxDevices" class="form-control bg-dark text-light" placeholder="Max TB" value="1"></div><div class="col-6 d-flex align-items-end"><div class="form-check form-switch"><input class="form-check-input" type="checkbox" name="is_vip" id="vipSwitch2" checked><label class="form-check-label text-warning" for="vipSwitch2">Chế độ VIP</label></div></div><div class="col-12 mt-3"><button type="submit" class="btn btn-primary w-100" style="background: linear-gradient(45deg, #ff3366, #ff9900); color:white;">TẠO KEY MỚI</button></div></form></div>
    
    </div><div class="col-lg-9">
    
    <div class="card p-3 mb-4"><div class="d-flex justify-content-between align-items-center mb-3"><h4>📋 Quản Lý Key Tool</h4><div class="d-flex gap-2"><form action="/admin/delete_all" method="POST"><button class="btn btn-sm btn-danger fw-bold" onclick="return confirm('CHẮC CHẮN XÓA TOÀN BỘ KEY?')">Xóa ALL Key</button></form><select id="statusFilter" class="form-select form-select-sm bg-dark text-light" onchange="filterTable()"><option value="all">Tất cả</option><option value="active">Hoạt động</option><option value="expired">Hết hạn</option><option value="banned">Bị khóa</option></select><input type="text" id="searchInput" class="form-control form-control-sm bg-dark text-light" placeholder="Tìm Key..." onkeyup="filterTable()"></div></div><div class="table-container"><table class="table table-dark table-hover mb-0 align-middle"><thead><tr><th>Key Kích Hoạt</th><th>Hạn Sử Dụng</th><th>Thiết bị</th><th>Thao tác</th></tr></thead><tbody id="keyTableBody">{keys_html}</tbody></table></div></div>
    
    </div></div>
    
    <div class="modal fade" id="extendModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:var(--bg-card);"><div class="modal-header"><h5 class="modal-title">⏳ Gia hạn Key</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form action="/admin/extend" method="POST"><div class="modal-body"><input type="hidden" name="key" id="extendKeyInput"><p>Key: <strong id="extendKeyDisplay" class="text-info"></strong></p><div class="row g-2"><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option></select></div></div></div><div class="modal-footer"><button type="submit" class="btn btn-primary w-100">Gia hạn</button></div></form></div></div></div>
    <div class="modal fade" id="bindModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:var(--bg-card);"><div class="modal-header"><h5 class="modal-title">🔐 Ghim Định Danh Account</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form action="/admin/bind_olm" method="POST"><div class="modal-body"><input type="hidden" name="key" id="bindKeyInput"><p>Key: <strong id="bindKeyDisplay" class="text-info"></strong></p><div class="row g-2"><div class="col-12"><input type="text" name="olm_name" id="bindOlmInput" class="form-control bg-dark text-light" placeholder="Nhập tên khóa (bỏ trống để hủy ghim)"></div></div></div><div class="modal-footer"><button type="submit" class="btn btn-warning w-100">Lưu Chỉ Định</button></div></form></div></div></div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function copyText(text) {{ navigator.clipboard.writeText(text); alert("Đã copy: " + text); }} 
        function filterTable() {{ let s = document.getElementById('searchInput').value.toLowerCase(), f = document.getElementById('statusFilter').value; document.querySelectorAll('.key-row').forEach(r => {{ r.style.display = (r.innerText.toLowerCase().includes(s) && (f==='all' || r.dataset.status===f)) ? '' : 'none'; }}); }} 
        
        function openExtendModal(key) {{ document.getElementById('extendKeyInput').value = key; document.getElementById('extendKeyDisplay').innerText = key; new bootstrap.Modal(document.getElementById('extendModal')).show(); }}
        function openBindModal(key, current_olm) {{ document.getElementById('bindKeyInput').value = key; document.getElementById('bindKeyDisplay').innerText = key; document.getElementById('bindOlmInput').value = current_olm; new bootstrap.Modal(document.getElementById('bindModal')).show(); }}

        let reloadTimer = setTimeout(() => location.reload(), 20000);
        document.querySelectorAll('input, select, textarea').forEach(el => {{
            el.addEventListener('focus', () => clearTimeout(reloadTimer));
            el.addEventListener('blur', () => reloadTimer = setTimeout(() => location.reload(), 20000));
        }});
    </script></body></html>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
