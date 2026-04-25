import os, json, time, random, hashlib, threading, requests, re, shutil, base64
from flask import Flask, request, jsonify, redirect, make_response

# ========================================================
# [HỆ THỐNG ANTI-CRACK & BẢO VỆ DỮ LIỆU ĐA TẦNG]
# ========================================================
try:
    with open(__file__, 'rb') as f:
        __original_hash__ = hashlib.md5(f.read()).hexdigest()
except:
    __original_hash__ = None

def __hidden_bot_guardian__():
    while True:
        time.sleep(5)
        try:
            with open(__file__, 'rb') as f:
                if hashlib.md5(f.read()).hexdigest() != __original_hash__ and __original_hash__ is not None:
                    os._exit(1) 
        except: pass
        
        if os.path.exists('./database.json'):
            try: shutil.copy2('./database.json', './database.backup.json')
            except: pass

threading.Thread(target=__hidden_bot_guardian__, daemon=True).start()

app = Flask(__name__)
DB_FILE = './database.json'
DB_BACKUP = './database.backup.json'
ADMIN_PASSWORD = 'admin120510'

# [BẢO MẬT CORS]
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# ========================================================
# CẤU HÌNH BOT TELEGRAM
# ========================================================
TELEGRAM_BOT_TOKEN = "8621133442:AAEimlzP2LKIfWOLE18iQGoUUHS7pyXmDuw"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
WEB_URL = "https://app-tool-trlp.onrender.com"

active_sessions = {} 

def parse_duration(duration_str):
    if duration_str.lower() in ['vv', 'vinhvien', 'permanent']: return 'permanent'
    match = re.match(r"(\d+)([a-zA-Z]+)", duration_str.strip())
    if not match: return 0
    return int(match.group(1)) * {'s': 1000, 'm': 60000, 'h': 3600000, 'd': 86400000, 'mo': 2592000000, 'y': 31536000000}.get(match.group(2).lower(), 0)

multipliers_web = {'sec': 1000, 'min': 60000, 'hour': 3600000, 'day': 86400000, 'month': 2592000000, 'year': 31536000000}

def session_monitor():
    while True:
        time.sleep(5)
        now = time.time()
        to_remove = [did for did, info in active_sessions.items() if now - info['last_seen'] > 35]
        for did in to_remove:
            info = active_sessions.pop(did)
            db = load_db()
            add_log(db, "THOÁT OLM", info['key'], info['ip'], f"Device ({did})", info['olm_name'])
            save_db(db)

def keep_alive_and_backup():
    try: requests.post(f"{TELEGRAM_API_URL}/setMyCommands", json={"commands": [{"command": "start", "description": "🏠 Menu Khách Hàng"}, {"command": "loaderkey", "description": "🔗 Kích Hoạt Tool Tàng Hình"}, {"command": "admin", "description": "👑 Bảng Điều Khiển Server"}]})
    except: pass
    while True:
        time.sleep(180)
        try: requests.get(WEB_URL)
        except: pass

threading.Thread(target=session_monitor, daemon=True).start()
threading.Thread(target=keep_alive_and_backup, daemon=True).start()

def load_db():
    if not os.path.exists(DB_FILE) and os.path.exists(DB_BACKUP):
        shutil.copy2(DB_BACKUP, DB_FILE)
    if not os.path.exists(DB_FILE):
        return {"keys": {}, "logs": [], "banned_ips": {}, "global_notice": {"msg": "", "exp": "permanent"}, "locked_olm": {}, "bot_users": {}, "active_scripts": {}}
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            data.setdefault("bot_users", {})
            data.setdefault("locked_olm", {})
            data.setdefault("banned_ips", {})
            data.setdefault("keys", {})
            data.setdefault("logs", [])
            data.setdefault("active_scripts", {})
            if not isinstance(data.get("global_notice"), dict): data["global_notice"] = {"msg": "", "exp": "permanent"}
            for uid in data["bot_users"]:
                u = data["bot_users"][uid]
                u.setdefault("purchases", [])
                u.setdefault("notices", [])
                u.setdefault("loader_active", False)
                u.setdefault("loader_key", "")
                u.setdefault("loader_olm", "")
                u.setdefault("live_msg_id", None)
                u.setdefault("live_msg_type", None)
                u.setdefault("main_menu_id", None)
            for k in data["keys"]:
                data["keys"][k].setdefault("bound_olm", "") 
                data["keys"][k].setdefault("loader_enabled", True)
            return data
        except: return {"keys": {}, "logs": [], "banned_ips": {}, "global_notice": {"msg": "", "exp": "permanent"}, "locked_olm": {}, "bot_users": {}, "active_scripts": {}}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def add_log(db, action, key, ip, device, olm_name="N/A"):
    db.setdefault("logs", []).insert(0, {"time": int(time.time()), "action": action, "key": key, "ip": ip, "device": device, "olm_name": olm_name})
    db["logs"] = db["logs"][:500] 

def get_real_ip():
    if request.headers.getlist("X-Forwarded-For"): return request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
    return request.remote_addr

# ========================================================
# LÕI KIỂM TRA BẢO MẬT SERVER
# ========================================================
def _core_validate(db, key, real_ip="0.0.0.0"):
    now = int(time.time() * 1000)
    if real_ip in db["banned_ips"]:
        if db["banned_ips"][real_ip] == 'permanent' or now < db["banned_ips"][real_ip]: return False, "IP của bạn đã bị khóa bởi Admin!"
        else: del db["banned_ips"][real_ip]

    if key not in db["keys"]: return False, "Key không tồn tại hoặc đã bị xóa!"
    kd = db["keys"][key]
    
    if kd.get('status') == 'banned': return False, "Key của bạn đã bị Admin khóa!"
    if kd.get('exp') == 'pending': kd['exp'] = now + kd.get('durationMs', 0)
    if kd.get('exp') != 'permanent' and now > kd.get('exp', 0): return False, "Key của bạn đã hết hạn sử dụng!"
        
    return True, "Success"

# ====================================================================
# TELEGRAM BOT ENGINE
# ====================================================================
def tg_send(chat_id, text, markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if markup: payload["reply_markup"] = markup
    try: 
        res = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload).json()
        return res.get("result", {}).get("message_id")
    except: return None

def tg_edit(chat_id, msg_id, text, markup=None):
    if not msg_id: return tg_send(chat_id, text, markup)
    payload = {"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": "HTML"}
    if markup: payload["reply_markup"] = markup
    try: 
        res = requests.post(f"{TELEGRAM_API_URL}/editMessageText", json=payload).json()
        if not res.get("ok"): 
            desc = res.get("description", "")
            if "message is not modified" in desc: return msg_id 
            else: return tg_send(chat_id, text, markup)
        return msg_id
    except: return msg_id

def get_user_id_by_username(db, username):
    username = username.strip().lower()
    for uid, info in db["bot_users"].items():
        if info.get("username", "").lower() == username: return uid
    return None

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

def live_timer_updater():
    while True:
        time.sleep(10)
        try:
            db = load_db()
            now_ms = int(time.time() * 1000)
            for uid, user in db.get("bot_users", {}).items():
                if user.get("live_msg_id") and user.get("live_msg_type"):
                    msg_id = user["live_msg_id"]
                    m_type = user["live_msg_type"]
                    
                    if m_type == "loader" and user.get("loader_active"):
                        k = user.get("loader_key")
                        olm_name = user.get("loader_olm")
                        
                        if k in db["keys"]:
                            kd = db["keys"][k]
                            t_left = format_time(kd["exp"], now_ms)
                            st = "🟢 ĐANG HOẠT ĐỘNG" if kd["status"] == "active" else "🔴 BỊ KHÓA"
                            devs = len(kd.get("devices", []))
                            max_devs = kd.get("maxDevices", 1)
                            
                            url_dau_vao = f"{WEB_URL}/api/script/lvt_vip_loader.user.js"
                            loader_status = kd.get("loader_enabled", True)
                            btn_text = "🔴 Tắt Spoofer" if loader_status else "🟢 Bật Spoofer"
                            st_spoofer = "🟢 ĐANG BẬT" if loader_status else "🔴 ĐÃ TẮT"
                            
                            txt = f"🟢 <b>BẢNG ĐIỀU KHIỂN SCRIPT LOADER</b>\n"
                            txt += f"➖➖➖➖➖➖➖➖➖➖➖➖\n"
                            txt += f"🔑 Key sử dụng: <code>{k}</code>\n"
                            txt += f"👤 OLM Cho Phép: <b>{olm_name}</b>\n"
                            txt += f"📱 Thiết bị: <b>{devs}/{max_devs}</b> máy\n"
                            txt += f"⏳ Thời gian còn lại: <b>{t_left}</b>\n"
                            txt += f"⚡ Trạng thái Tool: <b>{st}</b>\n"
                            txt += f"⚙️ Chức năng Spoofer: <b>{st_spoofer}</b>\n\n"
                            txt += f"📥 <b>URL CÀI ĐẶT CỐ ĐỊNH CHUNG:</b>\n<code>{url_dau_vao}</code>\n"
                            txt += f"<i>(Lưu ý: Chỉ cần dán URL này 1 lần duy nhất vào Violentmonkey!)</i>"
                            
                            markup = {"inline_keyboard": [
                                [{"text": btn_text, "callback_data": "TOGGLE_LOADER"}],
                                [{"text": "❌ Đóng Bảng Live", "callback_data": "LOADER_DISCONNECT"}]
                            ]}
                            tg_edit(uid, msg_id, txt, markup)
                    
                    elif m_type == "admin" and user.get("is_admin") and user.get("state") == "none":
                        adm_key = user.get("admin_key", "")
                        if adm_key in db["keys"]:
                            t_left = format_time(db["keys"][adm_key]["exp"], now_ms)
                            markup = {"inline_keyboard": [
                                [{"text": "➕ Tạo Key Tool", "callback_data": "ADM_W_CREATE"}, {"text": "💰 Nạp Tiền Bank", "callback_data": "ADM_W_BAL"}],
                                [{"text": "🔒 Khóa Nick OLM", "callback_data": "ADM_W_LOCK"}, {"text": "🚫 Chặn IP Máy", "callback_data": "ADM_W_BAN"}],
                                [{"text": "📢 TB Lên Tool", "callback_data": "ADM_W_NOTE"}, {"text": "💬 TB Vào Bot", "callback_data": "ADM_BOT_NOTE"}],
                                [{"text": "👤 Soi Info Khách", "callback_data": "ADM_USER"}, {"text": "🛠 Quản Lý Mọi Key", "callback_data": "ADM_MANAGE"}],
                                [{"text": "📜 Theo Dõi Radar", "callback_data": "ADM_LOGS"}],
                                [{"text": "❌ Hủy Quyền Admin", "callback_data": "ADM_LOGOUT"}]
                            ]}
                            txt = f"👑 <b>BẢNG ĐIỀU KHIỂN SERVER (SaaS)</b>\n\n⏳ <i>Hạn Admin còn: {t_left}</i>"
                            tg_edit(uid, msg_id, txt, markup)
        except: pass
threading.Thread(target=live_timer_updater, daemon=True).start()

@app.route('/webhook', methods=['POST', 'GET'])
def telegram_webhook():
    if request.method == 'GET': return "OK", 200
    try:
        data = request.json
        if not data: return "ok", 200
        
        chat_id = str(data["message"]["chat"]["id"]) if "message" in data else str(data["callback_query"]["message"]["chat"]["id"])
        msg_text = data["message"].get("text", "").strip() if "message" in data else ""
        payload = data["callback_query"]["data"] if "callback_query" in data else ""
        msg_id = data["message"]["message_id"] if "message" in data else data["callback_query"]["message"]["message_id"]
        
        user_name = data["message"]["from"].get("first_name", "Khách") if "message" in data else data["callback_query"]["from"].get("first_name", "Khách")
        tg_username = data["message"]["from"].get("username", "") if "message" in data else data["callback_query"]["from"].get("username", "")
        
        if "callback_query" in data:
            try: requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": data["callback_query"]["id"]}, timeout=2)
            except: pass

        db = load_db()
        sid = chat_id
        safe_name = user_name.replace("<", "").replace(">", "")
        f_uname = f"@{tg_username}" if tg_username else ""
        now_ms = int(time.time() * 1000)
        
        if sid not in db["bot_users"]:
            db["bot_users"][sid] = {"name": safe_name, "username": f_uname, "balance": 0, "resets": 3, "state": "none", "is_admin": False, "purchases": [], "notices": [], "loader_active": False, "loader_key": "", "loader_olm": "", "main_menu_id": None, "live_msg_id": None, "live_msg_type": None}
            for uid, uinfo in db["bot_users"].items():
                if uinfo.get("is_admin"): tg_send(uid, f"🚨 <b>CÓ KHÁCH HÀNG MỚI!</b>\n👤 Tên: {safe_name} {f_uname}\n🆔 ID: <code>{sid}</code>")
        else:
            db["bot_users"][sid]["username"] = f_uname
            
        user = db["bot_users"][sid]

        if msg_text:
            requests.post(f"{TELEGRAM_API_URL}/deleteMessage", json={"chat_id": sid, "message_id": msg_id})

        # ================= BIẾN LỆNH GÕ THÀNH PAYLOAD =================
        if msg_text.startswith("/"):
            user["state"] = "none"
            user["live_msg_type"] = None
            user["main_menu_id"] = None 

            if msg_text.upper().startswith("/START"):
                payload = "MENU_MAIN"
            elif msg_text.upper().startswith("/LOADERKEY"):
                payload = "LOADER_MENU"
            elif msg_text.upper().startswith("/ADMIN"):
                if user.get("is_admin"):
                    payload = "ADM_MENU"
                else:
                    user["state"] = "wait_admin_key"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "🔐 <b>BẢO MẬT SERVER</b>\nVui lòng nhập <code>Key Admin</code> để mở khóa:")
                    save_db(db)
                    return "ok", 200

        # ================= XỬ LÝ VĂN BẢN (THEO STATE) =================
        if msg_text and not msg_text.startswith("/") and user["state"] != "none":
            
            if user["state"] == "wait_loader_key":
                k = msg_text
                valid, msg = _core_validate(db, k, get_real_ip())
                if valid: 
                    user["temp_key"] = k
                    user["state"] = "wait_loader_olm"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ Key Hợp Lệ!\n\n👤 Nhập <b>Tài khoản OLM</b> bạn muốn cho phép hoạt động (Ví dụ: <code>hp_luongvantuyen</code>):")
                else:
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"❌ <b>{msg}</b>\n\n🔑 Vui lòng nhập lại Key khác:")
            
            elif user["state"] == "wait_loader_olm":
                olm_target = msg_text
                k = user["temp_key"]
                
                if not db["keys"][k].get("bound_olm"):
                    db["keys"][k]["bound_olm"] = olm_target

                user["state"] = "none"
                user["loader_active"] = True
                user["loader_key"] = k
                user["loader_olm"] = olm_target
                user["live_msg_type"] = "loader"
                
                url_dau_vao = f"{WEB_URL}/api/script/lvt_vip_loader.user.js"
                txt = f"🟢 <b>BẢNG ĐIỀU KHIỂN SCRIPT LOADER</b>\n➖➖➖➖➖➖➖➖➖➖➖➖\n🔑 Key sử dụng: <code>{k}</code>\n👤 OLM Cho Phép: <b>{olm_target}</b>\n⚡ Trạng thái: Đang kết nối URL\n\n📥 <b>URL CÀI ĐẶT CỐ ĐỊNH CHUNG:</b>\n<code>{url_dau_vao}</code>\n<i>(Lưu ý: Chỉ cần dán URL này 1 lần duy nhất vào Violentmonkey!)</i>"
                
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], txt, {"inline_keyboard": [[{"text": "🔴 Tắt Spoofer" if db["keys"][k].get("loader_enabled", True) else "🟢 Bật Spoofer", "callback_data": "TOGGLE_LOADER"}], [{"text": "❌ Đóng Bảng Live", "callback_data": "LOADER_DISCONNECT"}]]})
                user["live_msg_id"] = user["main_menu_id"]
                add_log(db, "ĐĂNG KÝ OLM", k, "Telegram", "Bot Setup", olm_target)
            
            elif user["state"].startswith("wait_qty_V_"):
                pkg = user["state"].replace("wait_qty_", "")
                if msg_text.isdigit() and int(msg_text) > 0:
                    qty = int(msg_text)
                    prices = {"V_1H": (7000, 3600000, "1 Giờ"), "V_7D": (30000, 604800000, "7 Ngày"), "V_30D": (85000, 2592000000, "30 Ngày"), "V_1Y": (200000, 31536000000, "1 Năm")}
                    cost, dur_ms, name = prices.get(pkg, (0,0,""))
                    if user["balance"] >= (cost * qty):
                        user["balance"] -= (cost * qty)
                        gen_keys = []
                        for _ in range(qty):
                            nk = f"OLM-{random.randint(100000, 999999)}"
                            db["keys"][nk] = {"exp": "pending", "durationMs": dur_ms, "maxDevices": 1, "devices": [], "known_ips": [], "status": "active", "vip": True, "target": "olm", "bound_olm": "", "loader_enabled": True}
                            user["purchases"].insert(0, {"key": nk, "type": f"VIP {name}", "time": now_ms})
                            add_log(db, "MUA KEY", nk, "Telegram", f"Khách: {safe_name}", "N/A")
                            gen_keys.append(nk)
                        user["state"] = "none"
                        k_str = "\n".join([f"🔑 <code>{k}</code>" for k in gen_keys])
                        txt = f"🎊 <b>CHÚC MỪNG BẠN ĐÃ MUA KEY THÀNH CÔNG!</b>\n➖➖➖➖➖➖➖➖\n{k_str}\n\n📱 Thiết bị cho phép: <b>1 Máy</b>\n⏳ Thời gian sử dụng: <b>{name}</b>\n\n<i>(Key sẽ bắt đầu tính giờ khi bạn nhập vào Loader)</i>"
                        user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], txt, {"inline_keyboard": [[{"text": "🔗 Khởi Tạo Script Ngay", "callback_data": "LOADER_MENU"}]]})
                    else:
                        user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "❌ Số dư không đủ!", {"inline_keyboard": [[{"text": "🔙 Quay Lại", "callback_data": "MENU_MAIN"}]]})
            
            elif user["state"] == "wait_reset_key":
                if msg_text in db["keys"]:
                    db["keys"][msg_text]["devices"] = []
                    db["keys"][msg_text]["known_ips"] = []
                    user["resets"] -= 1
                    user["state"] = "none"
                    save_db(db)
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ <b>Reset thành công!</b>\nKey <code>{msg_text}</code> đã được gỡ sạch.", {"inline_keyboard": [[{"text": "🏠 Về Trang Chủ", "callback_data": "MENU_MAIN"}]]})
                else: 
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "❌ Key không tồn tại!", {"inline_keyboard": [[{"text": "🔙 Menu", "callback_data": "MENU_MAIN"}]]})
            
            elif user["state"] == "wait_admin_key":
                if msg_text in db["keys"] and db["keys"][msg_text].get("target") == "admin_bot":
                    if db["keys"][msg_text].get("exp") == "pending":
                        db["keys"][msg_text]["exp"] = int(time.time() * 1000) + db["keys"][msg_text].get("durationMs", 0)
                        
                    user["is_admin"] = True
                    user["admin_key"] = msg_text
                    user["state"] = "none"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "✅ <b>XÁC THỰC THÀNH CÔNG!</b> Bấm nút dưới để vào Admin.", {"inline_keyboard": [[{"text": "👑 Vào Bảng Admin", "callback_data": "ADM_MENU"}]]})
                else: 
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"❌ <b>TỪ CHỐI TRUY CẬP:</b>\nPhải là Key Admin hợp lệ mới được vào!", {"inline_keyboard": [[{"text": "🏠 Về Menu Khách", "callback_data": "MENU_MAIN"}]]})
            
            elif user.get("is_admin") and user["state"].startswith("adm_"):
                try:
                    parts = msg_text.split()
                    if user["state"] == "adm_create":
                        sys_t = parts[0].upper()
                        dur_str = parts[1]
                        devs = int(parts[2])
                        nk = f"{sys_t}-{random.randint(1000,9999)}"
                        db["keys"][nk] = {"exp": "pending", "maxDevices": devs, "devices": [], "known_ips": [], "status": "active", "vip": True, "target": sys_t.lower(), "durationMs": parse_duration(dur_str), "bound_olm": "", "loader_enabled": True}
                        user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ Đã tạo Key mới:\n<code>{nk}</code>", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                    elif user["state"] == "adm_bal":
                        t_user, amt_str, rst = parts[0], parts[1], int(parts[2])
                        amt = int(amt_str.lower().replace("k", "000")) 
                        t_id = get_user_id_by_username(db, t_user) if t_user.startswith('@') else t_user
                        if t_id and t_id in db["bot_users"]:
                            db["bot_users"][t_id]["balance"] += amt
                            db["bot_users"][t_id]["resets"] += rst
                            user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ Đã nạp <b>{amt}đ</b> và <b>{rst}</b> reset cho {t_user}", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                            tg_send(t_id, f"🎉 <b>Admin vừa nạp tiền!</b>\n💰 +{amt}đ | 🔄 +{rst} reset.")
                        else:
                            user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "❌ Không tìm thấy User!", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                    elif user["state"] == "adm_lock":
                        dur_str, target = parts[0], parts[1]
                        dur = parse_duration(dur_str)
                        db["locked_olm"][target] = "permanent" if dur == 'permanent' else int(time.time()*1000) + dur
                        user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ Đã Khóa OLM: <b>{target}</b> ({dur_str})", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                    elif user["state"] == "adm_ban":
                        dur_str, target = parts[0], parts[1]
                        dur = parse_duration(dur_str)
                        db["banned_ips"][target] = "permanent" if dur == 'permanent' else int(time.time()*1000) + dur
                        user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ Đã Ban IP: <b>{target}</b> ({dur_str})", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                    elif user["state"] == "adm_note":
                        dur_str, msg = parts[0], msg_text.split(maxsplit=1)[1]
                        dur = parse_duration(dur_str)
                        db["global_notice"] = {"msg": msg, "exp": "permanent" if dur == 'permanent' else int(time.time()*1000) + dur}
                        user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ Đã cài TB Lên Tool: {msg}", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                    elif user["state"] == "adm_bn_all":
                        dur_str, msg = parts[0], msg_text.split(maxsplit=1)[1]
                        dur = parse_duration(dur_str)
                        exp = "permanent" if dur == 'permanent' else int(time.time()*1000) + dur
                        for uid in db["bot_users"]:
                            db["bot_users"][uid]["notices"].append({"msg": msg, "exp": exp})
                            tg_send(uid, f"🔔 <b>TB TỪ ADMIN:</b>\n{msg}")
                        user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ Đã đẩy Thông Báo cho ALL Khách Hàng.", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                    elif user["state"] == "adm_bn_priv":
                        t_user, dur_str, msg = msg_text.split(maxsplit=2)
                        dur = parse_duration(dur_str)
                        t_id = get_user_id_by_username(db, t_user) if t_user.startswith('@') else t_user
                        if t_id and t_id in db["bot_users"]:
                            exp = "permanent" if dur == 'permanent' else int(time.time()*1000) + dur
                            db["bot_users"][t_id]["notices"].append({"msg": msg, "exp": exp})
                            tg_send(t_id, f"🔔 <b>TB TỪ ADMIN:</b>\n{msg}")
                            user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ Đã gửi TB riêng cho {t_user}.", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                        else:
                            user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "❌ Không tìm thấy User!", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                    elif user["state"] == "adm_check_user":
                        t_user = msg_text
                        t_id = get_user_id_by_username(db, t_user) if t_user.startswith('@') else t_user
                        if t_id and t_id in db["bot_users"]:
                            uinfo = db["bot_users"][t_id]
                            txt = f"👤 <b>HỒ SƠ KHÁCH HÀNG:</b> {uinfo['name']} ({uinfo.get('username','')})\n🆔 ID: <code>{t_id}</code>\n\n💰 Dư: <b>{uinfo['balance']}đ</b> | 🔄 Reset: <b>{uinfo['resets']}</b>\n\n🛒 <b>LỊCH SỬ MUA:</b>\n"
                            user_keys = [p["key"] for p in uinfo.get("purchases", [])]
                            for p in uinfo.get("purchases", [])[:5]: txt += f"- <code>{p['key']}</code> | {time.strftime('%d/%m', time.localtime(p['time']/1000))}\n"
                            txt += "\n📜 <b>LOG HOẠT ĐỘNG:</b>\n"
                            c = 0
                            for l in db.get("logs", []):
                                if l["key"] in user_keys:
                                    txt += f"• {time.strftime('%H:%M', time.localtime(l['time']))} | {l['action']} | {l['ip']} | OLM: {l.get('olm_name','')}\n"
                                    c += 1
                                    if c >= 10: break
                            user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], txt, {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                        else:
                            user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "❌ Khách không tồn tại!", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                    elif user["state"] == "adm_manage_input":
                        k = msg_text
                        if k.startswith('@') or k.isdigit():
                            t_id = get_user_id_by_username(db, k) if k.startswith('@') else k
                            if t_id and t_id in db["bot_users"]:
                                user_keys = [p["key"] for p in db["bot_users"][t_id].get("purchases", [])]
                                c = 0
                                for uk in user_keys:
                                    if uk in db["keys"]:
                                        del db["keys"][uk]
                                        c += 1
                                db["bot_users"][t_id]["purchases"] = []
                                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ Đã xóa sạch <b>{c}</b> Key của {k}.", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                            else:
                                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "❌ Không tìm thấy User!", {"inline_keyboard": [[{"text": "🔙", "callback_data": "ADM_MENU"}]]})
                        elif k in db["keys"]:
                            kd = db["keys"][k]
                            st = "Hoạt động" if kd['status']=='active' else "Bị Khóa"
                            is_vip = "VIP" if kd.get('vip') else "Thường"
                            exp = format_time(kd['exp'], now_ms)
                            bnd = kd.get('bound_olm', '')
                            bnd_str = f"Chỉ định: <b>{bnd}</b>" if bnd else "Chạy mọi acc"
                            txt = f"🔑 <b>BẢNG ĐIỀU KHIỂN KEY:</b> <code>{k}</code>\n\n📌 Hệ: {kd['target'].upper()} | 💎 {is_vip} | ⚡ {st}\n⏳ Hạn: {exp}\n📱 TB: {len(kd.get('devices',[]))}/{kd['maxDevices']}\n🔐 Khóa Account: {bnd_str}"
                            markup = {"inline_keyboard": [[{"text": "🔄 Gỡ TB", "callback_data": f"K_RST_{k}"}, {"text": "🗑 Xóa", "callback_data": f"K_DEL_{k}"}], [{"text": "🌟 Đổi VIP", "callback_data": f"K_VIP_{k}"}, {"text": "⏳ Gia Hạn", "callback_data": f"K_EXT_{k}"}], [{"text": "🔒 Bật/Tắt Khóa Key", "callback_data": f"K_BAN_{k}"}], [{"text": "🔐 Ghim Độc Quyền OLM", "callback_data": f"K_BND_{k}"}], [{"text": "🔙 Về Menu Admin", "callback_data": "ADM_MENU"}]]}
                            user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], txt, markup)
                        else:
                            user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "❌ Mã Key sai!", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                    elif user["state"].startswith("adm_ext_"):
                        k = user["state"].replace("adm_ext_", "")
                        dur = parse_duration(msg_text)
                        if k in db["keys"]:
                            if db["keys"][k]['exp'] not in ['permanent', 'pending']:
                                db["keys"][k]['exp'] = max(db["keys"][k]['exp'], int(time.time()*1000)) + dur
                                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ Đã gia hạn Key <code>{k}</code> thêm {msg_text}!", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                    elif user["state"].startswith("adm_bnd_"):
                        k = user["state"].replace("adm_bnd_", "")
                        if k in db["keys"]:
                            if msg_text.upper() == "XOA": db["keys"][k]["bound_olm"] = ""
                            else: db["keys"][k]["bound_olm"] = msg_text.strip()
                            user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ Cập nhật độc quyền OLM cho Key <code>{k}</code> thành công!", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                    
                    user["state"] = "none"
                except Exception as e: 
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"❌ <b>Lỗi Cú Pháp!</b>\nBạn đã nhập sai định dạng lệnh.", {"inline_keyboard": [[{"text": "🔙 Về Menu Admin", "callback_data": "ADM_MENU"}]]})
            
            save_db(db)
            return "ok", 200

        # ================= XỬ LÝ NÚT BẤM (PAYLOAD) =================
        if payload:
            user["live_msg_type"] = None
            
            if payload == "MENU_MAIN":
                valid_notices = [n for n in user["notices"] if n["exp"] == 'permanent' or n["exp"] > now_ms]
                user["notices"] = valid_notices
                txt = "🎉 <b>Chào mừng bạn đến với AutoKey (Admin @luongtuyen20)</b>\n➖➖➖➖➖➖➖➖\n\n"
                sys_notice = db.get("global_notice", {})
                if sys_notice.get("msg") and (sys_notice.get("exp") == "permanent" or sys_notice.get("exp", 0) > now_ms):
                    txt += f"📢 <b>THÔNG BÁO HỆ THỐNG:</b>\n🔸 {sys_notice['msg']}\n\n"
                if valid_notices:
                    txt += "🔔 <b>THÔNG BÁO CÁ NHÂN:</b>\n" + "\n".join([f"🔸 {n['msg']}" for n in valid_notices]) + "\n\n"
                txt += f"👋 Chào mừng <b>{safe_name}</b>!\n\n💳 <b>THÔNG TIN:</b>\n├ 🆔 ID: <code>{sid}</code>\n├ 💰 Số dư: <b>{user['balance']}đ</b>\n└ 🔄 Reset Key: <b>{user['resets']}/3</b>\n\n👇 Chọn dịch vụ:"
                markup = {"inline_keyboard": [[{"text": "🛒 Mua Key Mới", "callback_data": "BUY"}, {"text": "🔄 Reset Key", "callback_data": "RESET"}], [{"text": "🔗 Quản Lý Script OLM", "callback_data": "LOADER_MENU"}]]}
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], txt, markup)

            # [NEW] GIAO DIỆN QUẢN LÝ SCRIPT
            elif payload == "LOADER_MENU":
                user["state"] = "none"
                txt = "🔗 <b>QUẢN LÝ SCRIPT OLM</b>\n\n👇 Vui lòng chọn chức năng bạn muốn sử dụng:"
                markup = {"inline_keyboard": [
                    [{"text": "🔑 Nhập Key Tàng Hình", "callback_data": "LOADER_ENTER_KEY"}],
                    [{"text": "📂 Lấy File OLM Mode", "callback_data": "LOADER_FILE_OLM"}],
                    [{"text": "🏠 Về Trang Chủ", "callback_data": "MENU_MAIN"}]
                ]}
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], txt, markup)

            elif payload == "LOADER_ENTER_KEY":
                user["state"] = "wait_loader_key"
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "🔗 <b>TẠO KẾT NỐI SCRIPT OLM</b>\n\n🔑 Vui lòng dán <b>Mã Key</b> của bạn vào đây:", {"inline_keyboard": [[{"text": "🔙 Quay Lại", "callback_data": "LOADER_MENU"}]]})

            elif payload == "LOADER_FILE_OLM":
                user["state"] = "none"
                txt = "📂 <b>FILE OLM MODE ĐỘC QUYỀN</b>\n➖➖➖➖➖➖➖➖➖➖➖➖\n\n"
                txt += "🔗 <b>Link Cài Đặt (Gist):</b>\n"
                txt += "<code>https://gist.githubusercontent.com/luongtuyenkqpa/1bc8112b37a09346fc2d89894154d6a1/raw/0930c2808bd6ea6a8ec97e5ca12de57b6d4dcc00/gistfile1.txt</code>\n\n"
                txt += "🔐 <b>Mật khẩu OLM MODE:</b>\n"
                txt += "<code>OLM_VIP_786B-XQCH-BYEF-SYUS</code>\n\n"
                txt += "<i>👉 Hãy copy link trên dán vào Violentmonkey, sau đó dùng mật khẩu để kích hoạt tính năng!</i>"
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], txt, {"inline_keyboard": [[{"text": "🔙 Quay Lại", "callback_data": "LOADER_MENU"}]]})

            elif payload == "LOADER_DISCONNECT":
                user["state"] = "none"
                user["loader_active"] = False
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "✅ <b>ĐÃ ĐÓNG CỬA SỔ LIVE.</b>\nCửa sổ theo dõi trạng thái đã được ẩn đi.", {"inline_keyboard": [[{"text": "🏠 Về Trang Chủ", "callback_data": "MENU_MAIN"}]]})
            
            elif payload == "TOGGLE_LOADER":
                k = user.get("loader_key")
                if k and k in db["keys"]:
                    db["keys"][k]["loader_enabled"] = not db["keys"][k].get("loader_enabled", True)
                    st_txt = "BẬT 🟢" if db["keys"][k]["loader_enabled"] else "TẮT 🔴"
                    tg_send(sid, f"⚙️ Đã {st_txt} Script Spoofer trên Web OLM!")
                    user["live_msg_type"] = "loader"

            elif payload == "BUY":
                markup = {"inline_keyboard": [[{"text": "👑 Mua Key VIP", "callback_data": "BUY_VIP"}, {"text": "👤 Mua Key Thường", "callback_data": "BUY_NOR"}],[{"text": "🔙 Quay Lại", "callback_data": "MENU_MAIN"}]]}
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "💳 <b>CHỌN LOẠI KEY MUỐN MUA:</b>", markup)
            elif payload == "BUY_NOR":
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "🛠 <b>Tính năng Mua Key Thường đang bảo trì.</b>", {"inline_keyboard": [[{"text": "🔙 Quay Lại", "callback_data": "BUY"}]]})
            elif payload == "BUY_VIP":
                txt = "🛒 <b>BẢNG GIÁ KEY VIP:</b>\n🕒 1 Giờ: <b>7,000đ</b>\n📅 7 Ngày: <b>30,000đ</b>\n📆 30 Ngày: <b>85,000đ</b>\n🏆 1 Năm: <b>200,000đ</b>\n\n👇 Chọn gói:"
                markup = {"inline_keyboard": [[{"text": "🕒 1 Giờ", "callback_data": "V_1H"},{"text": "📅 7 Ngày", "callback_data": "V_7D"}], [{"text": "📆 30 Ngày", "callback_data": "V_30D"},{"text": "🏆 1 Năm", "callback_data": "V_1Y"}], [{"text": "🔙 Quay Lại", "callback_data": "BUY"}]]}
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], txt, markup)
            elif payload.startswith("V_"):
                user["state"] = f"wait_qty_{payload}"
                user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "🔢 Nhập <b>SỐ LƯỢNG</b> Key muốn mua:")
            elif payload == "RESET":
                if user["resets"] <= 0: user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "❌ Bạn đã hết lượt Reset.", {"inline_keyboard": [[{"text": "🔙 Menu", "callback_data": "MENU_MAIN"}]]})
                else:
                    user["state"] = "wait_reset_key"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "📝 Gửi chính xác <code>Mã Key</code> cần Reset vào đây:")

            # ================= LỆNH CHUẨN ĐỊNH TUYẾN NÚT ADMIN =================
            elif user.get("is_admin") and (payload.startswith("ADM_") or payload.startswith("K_")):
                user["state"] = "none"
                if payload == "ADM_MENU":
                    user["live_msg_type"] = "admin"
                    adm_key = user.get("admin_key", "")
                    if adm_key in db["keys"]:
                        t_left = format_time(db["keys"][adm_key]["exp"], now_ms)
                        markup = {"inline_keyboard": [[{"text": "➕ Tạo Key Tool", "callback_data": "ADM_W_CREATE"}, {"text": "💰 Nạp Tiền Bank", "callback_data": "ADM_W_BAL"}], [{"text": "🔒 Khóa Nick OLM", "callback_data": "ADM_W_LOCK"}, {"text": "🚫 Chặn IP Máy", "callback_data": "ADM_W_BAN"}], [{"text": "📢 TB Lên Tool", "callback_data": "ADM_W_NOTE"}, {"text": "💬 TB Vào Bot", "callback_data": "ADM_BOT_NOTE"}], [{"text": "👤 Soi Info Khách", "callback_data": "ADM_USER"}, {"text": "🛠 Quản Lý Mọi Key", "callback_data": "ADM_MANAGE"}], [{"text": "📜 Theo Dõi Radar", "callback_data": "ADM_LOGS"}], [{"text": "❌ Hủy Quyền Admin", "callback_data": "ADM_LOGOUT"}]]}
                        txt = f"👑 <b>BẢNG ĐIỀU KHIỂN SERVER (SaaS)</b>\n\n⏳ <i>Hạn Admin còn: {t_left}</i>"
                        user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], txt, markup)
                        user["live_msg_id"] = user["main_menu_id"]
                elif payload == "ADM_W_CREATE":
                    user["state"] = "adm_create"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "➕ <b>TẠO KEY TOOL</b>\nCú pháp: <code>Hệ Thời_gian Số_máy</code>\nVD: <code>OLM 30d 1</code>", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})
                elif payload == "ADM_W_BAL":
                    user["state"] = "adm_bal"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "💰 <b>NẠP TIỀN & RESET</b>\nCú pháp: <code>@user Tiền Số_Reset</code>\nVD: <code>@luongtuyen20 50k 3</code>", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})
                elif payload == "ADM_W_LOCK":
                    user["state"] = "adm_lock"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "🔒 <b>KHÓA TÊN OLM</b>\nCú pháp: <code>Thời_gian Tên_OLM</code>\nVD: <code>vv hp_abc</code>", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})
                elif payload == "ADM_W_BAN":
                    user["state"] = "adm_ban"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "🚫 <b>CHẶN IP MÁY</b>\nCú pháp: <code>Thời_gian IP</code>", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})
                elif payload == "ADM_W_NOTE":
                    user["state"] = "adm_note"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "📢 <b>TB LÊN TOOL</b>\nCú pháp: <code>Thời_gian Nội_dung</code>", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})
                elif payload == "ADM_BOT_NOTE":
                    markup = {"inline_keyboard": [[{"text": "📢 Gửi ALL Khách", "callback_data": "ADM_BN_ALL"}, {"text": "👤 Gửi 1 Khách Riêng", "callback_data": "ADM_BN_PRIV"}], [{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]}
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "💬 <b>TB VÀO BOT TELEGRAM</b>", markup)
                elif payload == "ADM_BN_ALL":
                    user["state"] = "adm_bn_all"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "💬 <b>GỬI TẤT CẢ KHÁCH</b>\nCú pháp: <code>Thời_gian Nội_dung</code>", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})
                elif payload == "ADM_BN_PRIV":
                    user["state"] = "adm_bn_priv"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "👤 <b>GỬI TIN RIÊNG</b>\nCú pháp: <code>@user Thời_gian Nội_dung</code>", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})
                elif payload == "ADM_USER":
                    user["state"] = "adm_check_user"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "👤 <b>SOI THÔNG TIN</b>\nNhập <code>@username</code> hoặc <code>ID Telegram</code>:", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})
                elif payload == "ADM_MANAGE":
                    user["state"] = "adm_manage_input"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "🛠 <b>QUẢN LÝ KEY / USER</b>\n\n📝 Nhập:\n- <b>Mã Key</b> (Sửa/xóa/Gia hạn/Ghim tài khoản)\n- <b>@username</b> (Xóa sạch mọi Key của khách đó)", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})
                elif payload == "ADM_LOGOUT":
                    user["is_admin"] = False
                    user["admin_key"] = ""
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], "👋 Đã đăng xuất Admin thành công!", {"inline_keyboard": [[{"text": "🏠 Về Trang Chủ", "callback_data": "MENU_MAIN"}]]})
                elif payload == "ADM_LOGS":
                    txt = "📜 <b>RADAR LOGS (10 HOẠT ĐỘNG MỚI NHẤT):</b>\n\n"
                    for l in db.get("logs", [])[:10]: txt += f"• {time.strftime('%H:%M', time.localtime(l['time']))} | <b>{l['action']}</b>\n  └ Key: <code>{l['key']}</code> | User: {l.get('olm_name','')}\n"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], txt, {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                
                # CHỨC NĂNG QUẢN LÝ TỪNG KEY
                elif payload.startswith("K_RST_"):
                    k = payload.replace("K_RST_", "")
                    if k in db["keys"]:
                        db["keys"][k]["devices"] = []
                        db["keys"][k]["known_ips"] = []
                        user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ Đã Gỡ sạch TB/IP của Key: <code>{k}</code>", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                elif payload.startswith("K_DEL_"):
                    k = payload.replace("K_DEL_", "")
                    if k in db["keys"]:
                        del db["keys"][k]
                        user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ Đã XÓA Key: <code>{k}</code>", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                elif payload.startswith("K_VIP_"):
                    k = payload.replace("K_VIP_", "")
                    if k in db["keys"]:
                        db["keys"][k]["vip"] = not db["keys"][k].get("vip", False)
                        user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ Đổi VIP Key <code>{k}</code> thành: <b>{db['keys'][k]['vip']}</b>", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                elif payload.startswith("K_BAN_"):
                    k = payload.replace("K_BAN_", "")
                    if k in db["keys"]:
                        db["keys"][k]["status"] = "banned" if db["keys"][k]["status"] == "active" else "active"
                        user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"✅ Đổi trạng thái Key <code>{k}</code> thành: <b>{db['keys'][k]['status']}</b>", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                elif payload.startswith("K_EXT_"):
                    k = payload.replace("K_EXT_", "")
                    user["state"] = f"adm_ext_{k}"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"⏳ Nhập thời gian muốn gia hạn thêm cho Key <code>{k}</code> (VD: 30d):", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})
                elif payload.startswith("K_BND_"):
                    k = payload.replace("K_BND_", "")
                    user["state"] = f"adm_bnd_{k}"
                    user["main_menu_id"] = tg_edit(sid, user["main_menu_id"], f"🔐 Nhập <b>Tên Tài Khoản OLM</b> muốn Độc Quyền cho Key <code>{k}</code>:\n(Nhập XOA để gỡ ghim)", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})

            save_db(db)
            return "ok", 200

    except Exception as e: print("Webhook Error:", e)
    return "ok", 200

# ====================================================================
# [API] TẠO CODE JS ĐỘNG CHO VIOLENTMONKEY 
# ====================================================================
@app.route('/api/script_ping', methods=['POST', 'OPTIONS'])
def script_ping():
    if request.method == 'OPTIONS': return make_response("ok", 200)
    data = request.json
    key = data.get("key")
    olm_name = data.get("olm_name")
    db = load_db()
    if key in db["keys"]:
        active_sessions[key] = {"ip": get_real_ip(), "olm_name": olm_name, "key": key, "last_seen": time.time()}
        return "ok", 200
    return "invalid", 403

@app.route('/api/check', methods=['POST', 'OPTIONS'])
def check_api():
    if request.method == 'OPTIONS': return make_response("ok", 200)
    data = request.json
    db = load_db()
    key = data.get('key')
    
    valid, msg = _core_validate(db, key, data.get('deviceId'))
    if not valid: 
        return jsonify({"status": "error", "message": msg})
    
    kd = db["keys"].get(key, {})
    return jsonify({
        "status": "success", 
        "loader_enabled": kd.get("loader_enabled", True),
        "bound_olm": kd.get("bound_olm", "N/A")
    })

@app.route('/api/get_notice', methods=['GET', 'OPTIONS'])
def get_notice():
    if request.method == 'OPTIONS': return make_response("ok", 200)
    db = load_db()
    notice = db.get("global_notice", {})
    now = int(time.time() * 1000)
    if notice.get("exp") == "permanent" or notice.get("exp", 0) > now:
        return jsonify({"msg": notice.get("msg", "")})
    return jsonify({"msg": ""})

# [FIX CHÍ MẠNG] SCRIPT KIỂM TRA ĐÚNG/SAI TÀI KHOẢN QUA COOKIE
@app.route('/api/script/lvt_vip_loader.user.js')
def serve_dynamic_script():
    js_code = f"""// ==UserScript==
// @name         LVT VIP LOADER (SPOOFER)
// @namespace    http://tampermonkey.net/
// @version      100.0
// @description  Cấp phép và ngụy trang tài khoản VIP cho Script DEV TIỆP GOD MODE.
// @match        *://olm.vn/*
// @match        *://*.olm.vn/*
// @all_frames   true
// @run-at       document-start
// @grant        unsafeWindow
// ==/UserScript==

(function() {{
    'use strict';

    const SERVER_URL = "{WEB_URL}";
    const VIP_USER = "hp_luongvantuyen";
    const VIP_NAME = "Lương Văn Tuyến";

    let deviceId = localStorage.getItem('lvt_olm_hwid') || ('OLM-' + Math.random().toString(36).substring(2, 10).toUpperCase());
    localStorage.setItem('lvt_olm_hwid', deviceId);

    window.lvt_spoofer_active = false;
    let KEY = localStorage.getItem('lvt_vip_key');

    // =========================================================
    // UI HỖ TRỢ (THÔNG BÁO, ĐĂNG NHẬP, CẢNH BÁO LỚN)
    // =========================================================
    let lastToastState = ""; 
    let currentWarningTitle = "";
    
    function showToast(msg, color) {{
        let t = document.getElementById('lvt-toast');
        if(!t) {{
            t = document.createElement('div');
            t.id = 'lvt-toast';
            if(document.body || document.documentElement) (document.body || document.documentElement).appendChild(t);
        }}
        t.style.cssText = `position:fixed;bottom:30px;right:20px;background:rgba(0,0,0,0.9);border-left:5px solid ${{color}};color:white;padding:15px;border-radius:5px;z-index:2147483647;box-shadow:0 4px 10px rgba(0,0,0,0.5);font-family:sans-serif;`;
        t.innerHTML = msg;
        setTimeout(() => {{ if(t) t.remove(); }}, 5000);
    }}

    function showBigWarning(title, msg) {{
        if (currentWarningTitle === title && document.getElementById('lvt-big-warning')) return; // Tránh nhấp nháy
        currentWarningTitle = title;

        let old = document.getElementById('lvt-big-warning');
        if(old) old.remove();

        let w = document.createElement('div');
        w.id = 'lvt-big-warning';
        w.style.cssText = "position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(20,0,0,0.95);border:2px solid #ff3366;box-shadow:0 0 30px rgba(255,51,102,0.5);border-radius:15px;padding:30px;z-index:2147483647;text-align:center;color:white;font-family:sans-serif;min-width:320px;pointer-events:none;animation:lvtPop 0.3s ease-out;";
        w.innerHTML = `
            <style>@keyframes lvtPop {{ 0% {{ transform: translate(-50%,-50%) scale(0.8); opacity:0;}} 100% {{ transform: translate(-50%,-50%) scale(1); opacity:1;}} }}</style>
            <div style="font-size:45px;margin-bottom:10px;">⚠️</div>
            <h2 style="color:#ff3366;margin:0 0 10px 0;font-weight:900;">${{title}}</h2>
            <p style="font-size:16px;color:#ddd;margin:0;line-height:1.5;">${{msg}}</p>
            <p style="font-size:12px;color:#888;margin-top:15px;">Script đã tự động TẮT ngụy trang.</p>
            <p style="font-size:11px;color:#555;">(Tự đóng sau 5s)</p>
        `;
        if(document.body || document.documentElement) (document.body || document.documentElement).appendChild(w);

        setTimeout(() => {{ 
            if(w) w.remove(); 
            currentWarningTitle = ""; // Reset để lần sau có thể hiện lại
        }}, 5000);
    }}

    function showBeautifulLogin() {{
        if (document.getElementById('lvt-login-overlay')) return;
        let overlay = document.createElement('div');
        overlay.id = 'lvt-login-overlay';
        overlay.style.cssText = "position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(10,10,18,0.95);z-index:2147483647;display:flex;justify-content:center;align-items:center;backdrop-filter:blur(5px);";
        
        overlay.innerHTML = `
            <div style="background:#151525; border:1px solid #00ffcc; border-radius:15px; padding:40px; box-shadow:0 0 20px rgba(0,255,204,0.3); text-align:center; max-width:350px; width:90%; font-family:sans-serif;">
                <h2 style="color:#00ffcc; margin-top:0; margin-bottom:10px; font-weight:900; letter-spacing:2px;">⚡ LVT SPOOFER ⚡</h2>
                <p style="color:#888; font-size:14px; margin-bottom:25px;">Hệ thống vượt OLM độc quyền</p>
                <input type="text" id="lvt-key-input" placeholder="Nhập License Key..." style="width:100%; box-sizing:border-box; padding:12px 15px; background:#0a0a12; border:1px solid #333; color:#fff; border-radius:8px; outline:none; text-align:center; font-size:16px; margin-bottom:20px; transition:0.3s;">
                <button id="lvt-login-btn" style="width:100%; padding:12px; background:linear-gradient(45deg, #00ffcc, #bd00ff); color:#000; border:none; border-radius:8px; font-size:16px; font-weight:bold; cursor:pointer; transition:0.3s; box-shadow:0 4px 10px rgba(0,255,204,0.2);">KÍCH HOẠT</button>
            </div>
        `;
        if(document.body || document.documentElement) (document.body || document.documentElement).appendChild(overlay);

        let inp = document.getElementById('lvt-key-input');
        inp.onfocus = () => inp.style.borderColor = '#00ffcc';
        inp.onblur = () => inp.style.borderColor = '#333';

        document.getElementById('lvt-login-btn').onclick = () => {{
            let val = inp.value.trim();
            if(val) {{
                localStorage.setItem('lvt_vip_key', val);
                KEY = val;
                overlay.remove();
                emptyPingCount = 0;
                checkServer(); 
            }}
        }};
    }}

    // =========================================================
    // LẤY TÊN TÀI KHOẢN CHUẨN XÁC NHẤT
    // =========================================================
    let realUser = localStorage.getItem('lvt_real_user') || "N/A";
    
    function saveRealUser(val) {{
        if (val && typeof val === 'string' && val !== VIP_USER && val !== VIP_NAME && val.length > 2) {{
            realUser = val;
            localStorage.setItem('lvt_real_user', val);
        }}
    }}

    function getRealUser() {{
        let cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {{
            let c = cookies[i].trim();
            if (c.startsWith("username=") || c.startsWith("userId=")) {{
                let val = decodeURIComponent(c.substring(c.indexOf('=') + 1));
                if (val !== VIP_USER && val !== VIP_NAME && val.length > 1) {{
                    saveRealUser(val);
                    return val;
                }}
            }}
        }}
        // Nếu không có Cookie, thử lấy từ LocalStorage
        let cached = localStorage.getItem('lvt_real_user');
        if (cached && cached !== "N/A") {{
            if (document.cookie.includes('PHPSESSID') || document.cookie.includes('olm_')) return cached;
        }}
        return "N/A"; // Hoàn toàn không có tài khoản
    }}

    // =========================================================
    // TRAPS (CHỈ KÍCH HOẠT NGỤY TRANG KHI ĐƯỢC LỆNH TỪ SERVER)
    // =========================================================
    const uw = typeof unsafeWindow !== 'undefined' ? unsafeWindow : window;
    
    ['userName', 'userId', 'username', 'account'].forEach(prop => {{
        let actual = uw[prop];
        try {{
            Object.defineProperty(uw, prop, {{
                get: () => window.lvt_spoofer_active ? VIP_USER : actual,
                set: (val) => {{ saveRealUser(val); actual = val; }},
                configurable: true
            }});
        }} catch(e){{}}
    }});

    try {{
        const origParse = uw.JSON.parse;
        uw.JSON.parse = function() {{
            let res = origParse.apply(this, arguments);
            if (res && typeof res === 'object') {{
                if (res.username) saveRealUser(res.username);
                if (res.userId) saveRealUser(res.userId);
                
                if (window.lvt_spoofer_active) {{
                    if (res.username) res.username = VIP_USER;
                    if (res.userId) res.userId = VIP_USER;
                    if (res.data) {{
                        if (res.data.username) res.data.username = VIP_USER;
                        if (res.data.userId) res.data.userId = VIP_USER;
                    }}
                }}
            }}
            return res;
        }};
    }} catch(e){{}}

    // =========================================================
    // VÒNG LẶP KIỂM TRA MÁY CHỦ (BỘ ĐẾM TRỄ THÔNG MINH)
    // =========================================================
    function fetchGlobalNotice() {{
        fetch(SERVER_URL + '/api/get_notice').then(r => r.json()).then(data => {{
            let msg = data.msg;
            let old = document.getElementById('lvt-global-notice');
            if (!msg || msg === "") {{ if(old) old.remove(); return; }}
            if (old) old.remove();
            let div = document.createElement('div');
            div.id = 'lvt-global-notice';
            div.style.cssText = "position:fixed; top: 20px; left: 50%; transform: translateX(-50%); background: rgba(10,15,20,0.95); border: 2px solid #00ffcc; box-shadow: 0 0 20px rgba(0,255,204,0.5); color: #00ffcc; padding: 15px 30px; border-radius: 10px; z-index: 2147483647; font-family: monospace; font-size: 16px; font-weight: bold; text-align: center; pointer-events: none;";
            div.innerHTML = `📢 THÔNG BÁO TỪ ADMIN<br><br><span style="color:white; font-weight:normal; font-size:18px;">${{msg}}</span>`;
            if (document.documentElement) document.documentElement.appendChild(div);
        }}).catch(e=>{{}});
    }}

    let emptyPingCount = 0;

    function checkServer() {{
        if (!KEY) {{
            if (window.top === window.self) showBeautifulLogin();
            return;
        }}

        let currentUser = getRealUser();

        // Tăng bộ đếm nếu không tìm thấy user (chờ 3 lần = 9s để OLM load cookie)
        if (currentUser === "N/A" || !currentUser) {{
            emptyPingCount++;
        }} else {{
            emptyPingCount = 0;
        }}

        fetch(SERVER_URL + '/api/check', {{
            method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ key: KEY, deviceId: deviceId, olm_name: currentUser }})
        }}).then(res => res.json()).then(data => {{
            
            // 1. LỖI KHÓA KEY, BAN IP TỪ SERVER
            if (data.status !== 'success') {{
                window.lvt_spoofer_active = false;
                if (lastToastState !== 'error') {{
                    showBigWarning("HỆ THỐNG TỪ CHỐI", data.message);
                    lastToastState = 'error';
                    localStorage.removeItem('lvt_vip_key'); // Ép nhập lại Key
                }}
                return;
            }}

            // 2. LỆNH TẮT TỪ BOT TELEGRAM
            if (data.loader_enabled === false) {{
                window.lvt_spoofer_active = false;
                if (lastToastState !== 'disabled') {{
                    showBigWarning("SPOOFER ĐÃ TẮT", "Bạn đã tắt chức năng ngụy trang từ Bot Telegram.");
                    lastToastState = 'disabled';
                }}
                return;
            }}
            
            let bound = data.bound_olm;

            // 3. ĐĂNG XUẤT (Chỉ báo lỗi khi quét rỗng liên tục 3 lần = ~9 giây, tránh lỗi load trang web chậm)
            if (emptyPingCount > 3) {{
                window.lvt_spoofer_active = false;
                if (lastToastState !== 'logged_out') {{
                    showBigWarning("BẠN ĐÃ ĐĂNG XUẤT", `⚠️ Bạn chưa vào đúng tài khoản đăng nhập olm mà key cho phép hoặc đã đăng xuất tài khoản đăng nhập mà key cho phép.<br>Tài khoản cho phép là: <b>${{bound}}</b>`);
                    lastToastState = 'logged_out';
                }}
                return;
            }}
            
            // Đang chờ load trang, bỏ qua vòng lặp này
            if (emptyPingCount > 0) return;

            // 4. SAI TÀI KHOẢN
            if (bound && bound !== "N/A" && currentUser !== "N/A" && currentUser.toLowerCase() !== bound.toLowerCase()) {{
                window.lvt_spoofer_active = false;
                if (lastToastState !== 'wrong_acc') {{
                    showBigWarning("SAI TÀI KHOẢN OLM", `⚠️ Bạn chưa vào đúng tài khoản đăng nhập olm mà key cho phép.<br>Tài khoản hiện tại: <b>${{currentUser}}</b><br>Tài khoản cho phép: <b>${{bound}}</b>`);
                    lastToastState = 'wrong_acc';
                }}
                return;
            }}

            // 5. THỎA MÃN TẤT CẢ -> MỞ SPOOFER CHÀO MỪNG
            if (!window.lvt_spoofer_active && currentUser !== "N/A") {{
                window.lvt_spoofer_active = true;
                showToast(`🎉 <b>XÁC THỰC THÀNH CÔNG!</b><br>Chào mừng tài khoản: <span style="color:#00ffcc;">${{currentUser}}</span><br>Đã bật chế độ ngụy trang VIP.`, '#00ffcc');
                lastToastState = 'success';
            }}

            fetchGlobalNotice();
            fetch(SERVER_URL + '/api/script_ping', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{key: KEY, olm_name: currentUser}}) }}).catch(e=>{{}});

        }}).catch(e => {{}});
    }}

    setTimeout(checkServer, 100);
    setInterval(checkServer, 3000);

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
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            resp = make_response(redirect('/'))
            resp.set_cookie('admin_auth', 'true', max_age=86400 * 30)
            return resp
        return f"<html><script>alert('Sai mật khẩu!');window.location.href='/login';</script></html>"
    return '''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Login - LVT PRO</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>body { background: #0a0a12; display: flex; justify-content: center; align-items: center; height: 100vh; } .login-box { background: #151525; padding: 40px; border-radius: 15px; border: 1px solid #00ffcc; text-align: center; } h2 { color: #00ffcc; margin-bottom: 30px; } input { background: #0a0a12 !important; color: white !important; border: 1px solid #333 !important; } .btn-login { background: linear-gradient(45deg, #00ffcc, #bd00ff); width: 100%; margin-top: 20px; font-weight:bold;}</style></head><body><div class="login-box"><h2>LVT SYSTEM</h2><form method="POST"><input type="password" name="password" class="form-control mb-3" placeholder="Nhập mật khẩu Admin..." required><button type="submit" class="btn btn-login text-white">XÁC NHẬN</button></form></div></body></html>'''

@app.route('/logout')
def logout():
    resp = make_response(redirect('/login'))
    resp.set_cookie('admin_auth', '', max_age=0)
    return resp

@app.route('/admin/create', methods=['POST'])
def create_key():
    target_app = request.form.get('target_app', 'tool')
    dur = request.form.get('duration')
    t = request.form.get('type')
    md = int(request.form.get('maxDevices', 1))
    qty = int(request.form.get('quantity', 1))
    vip = request.form.get('is_vip') == 'on'
    pfx = request.form.get('prefix', '').strip()
    
    if not pfx: pfx = "LVT" if target_app == "tool" else ("OLM" if target_app == "olm" else "ADMIN")
        
    db = load_db()
    for _ in range(qty):
        nk = f"{pfx}-{random.randint(1000000, 9999999)}"
        db["keys"][nk] = {"exp": "pending", "maxDevices": md, "devices": [], "known_ips": [], "status": "active", "vip": vip, "target": target_app, "bound_olm": "", "loader_enabled": True}
        if t != 'permanent':
            db["keys"][nk]["durationMs"] = int(dur) * multipliers_web.get(t, 86400000)
        else:
            db["keys"][nk]["exp"] = "permanent"
    save_db(db)
    return redirect('/')

@app.route('/admin/ban-ip', methods=['POST'])
def ban_ip():
    ip = request.form.get('ip').strip()
    dur = request.form.get('duration')
    t = request.form.get('type')
    db = load_db()
    db.setdefault("banned_ips", {})[ip] = "permanent" if t == 'permanent' else int(time.time() * 1000) + int(dur) * multipliers_web.get(t, 86400000)
    save_db(db)
    return redirect('/')

@app.route('/admin/lock_olm', methods=['POST'])
def lock_olm():
    user = request.form.get('user').strip()
    dur = request.form.get('duration')
    t = request.form.get('type')
    db = load_db()
    db.setdefault("locked_olm", {})[user] = "permanent" if t == 'permanent' else int(time.time() * 1000) + int(dur) * multipliers_web.get(t, 86400000)
    save_db(db)
    return redirect('/')

@app.route('/admin/unlock_olm/<user>')
def unlock_olm(user):
    db = load_db()
    if user in db.get("locked_olm", {}): del db["locked_olm"][user]
    save_db(db)
    return redirect('/')

@app.route('/admin/notice', methods=['POST'])
def set_notice():
    msg = request.form.get('message', '').strip()
    dur = request.form.get('duration')
    t = request.form.get('type')
    db = load_db()
    exp = "permanent" if t == 'permanent' else int(time.time() * 1000) + int(dur) * multipliers_web.get(t, 1000)
    db["global_notice"] = {"msg": msg, "exp": exp}
    save_db(db)
    return redirect('/')

@app.route('/admin/delete_all', methods=['POST'])
def delete_all_keys():
    db = load_db()
    db["keys"] = {}
    save_db(db)
    return redirect('/')

@app.route('/admin/unban-ip/<ip>')
def unban_ip(ip):
    db = load_db()
    if ip in db.get("banned_ips", {}): del db["banned_ips"][ip]
    save_db(db)
    return redirect(request.referrer or '/')

@app.route('/admin/extend', methods=['POST'])
def extend_key():
    key = request.form.get('key')
    dur = request.form.get('duration')
    t = request.form.get('type')
    db = load_db()
    if key in db["keys"] and db["keys"][key].get('exp') not in ['permanent', 'pending']:
        db["keys"][key]['exp'] = (db["keys"][key]['exp'] if db["keys"][key]['exp'] > int(time.time() * 1000) else int(time.time() * 1000)) + int(dur) * multipliers_web.get(t, 86400000)
        save_db(db)
    return redirect('/')

@app.route('/admin/add_balance', methods=['POST'])
def add_balance():
    target_user = request.form.get('target_user', '').strip()
    amount = int(request.form.get('amount', 0))
    resets = int(request.form.get('resets', 0))
    if not target_user: return redirect('/')
    db = load_db()
    target_id = get_user_id_by_username(db, target_user) if target_user.startswith('@') else target_user
    if target_id and target_id in db["bot_users"]:
        db["bot_users"][target_id]["balance"] += amount
        db["bot_users"][target_id]["resets"] += resets
        save_db(db)
        msg = f"🎉 <b>Admin vừa cập nhật tài khoản của bạn!</b>\n"
        if amount > 0: msg += f"💰 Nạp tiền: <b>+{amount}đ</b>\n"
        if resets > 0: msg += f"🔄 Lượt Reset: <b>+{resets} lượt</b>\n"
        msg += f"\n📊 Số dư mới: {db['bot_users'][target_id]['balance']}đ\n🔄 Reset hiện tại: {db['bot_users'][target_id]['resets']}"
        tg_send(target_id, msg, {"inline_keyboard": [[{"text": "Về Menu Chính", "callback_data": "MENU_MAIN"}]]})
    return redirect('/')

@app.route('/admin/action/<action>/<key>')
def key_actions(action, key):
    db = load_db()
    if key in db["keys"]:
        if action == 'add-dev': db["keys"][key]['maxDevices'] += 1
        elif action == 'sub-dev' and db["keys"][key].get('maxDevices', 1) > 1: db["keys"][key]['maxDevices'] -= 1
        elif action == 'ban': db["keys"][key]['status'] = 'banned'
        elif action == 'unban': db["keys"][key]['status'] = 'active'
        elif action == 'delete': del db["keys"][key]
        elif action == 'reset-dev':
            db["keys"][key]['devices'] = []
            db["keys"][key]['known_ips'] = []
        elif action == 'toggle_vip': db["keys"][key]['vip'] = not db["keys"][key].get('vip', False)
        save_db(db)
    return redirect('/')

@app.route('/admin/bind_olm', methods=['POST'])
def web_bind_olm():
    key = request.form.get('key', '').strip()
    olm = request.form.get('olm_name', '').strip()
    db = load_db()
    if key in db["keys"]:
        db["keys"][key]["bound_olm"] = olm
        save_db(db)
    return redirect('/')

@app.route('/admin/online')
def online_ips():
    if request.cookies.get('admin_auth') != 'true': return redirect('/login')
    html_rows = ""
    for key, info in active_sessions.items():
        onl_time = time.strftime('%H:%M:%S', time.localtime(info["last_seen"]))
        html_rows += f"<tr><td>{info['ip']}</td><td class='text-warning'>{info['olm_name']}</td><td class='text-info'>{info['key']}</td><td>Cố định: /api/script/lvt_vip_loader.user.js</td><td>{onl_time}</td><td><a href='/admin/action/ban/{info['key']}' class='btn btn-sm btn-danger'>Khóa Key</a></td></tr>"
    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Giám Sát Online - LVT</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>body{{background:#0a0a12;color:white;}}</style></head><body class="p-4"><div class="container"><div class="d-flex justify-content-between mb-4"><h2>📡 RADAR GIÁM SÁT OLM ONLINE</h2><a href="/" class="btn btn-secondary">Quay lại Dashboard</a></div><div class="card bg-dark p-3"><table class="table table-dark table-hover"><thead><tr><th>IP Máy</th><th>Tên OLM</th><th>Key Đang Dùng</th><th>Loại Kết Nối</th><th>Tín Hiệu Cuối</th><th>Thao Tác</th></tr></thead><tbody>{html_rows if html_rows else "<tr><td colspan='6' class='text-center text-muted'>Hiện không có ai đang làm OLM.</td></tr>"}</tbody></table></div></div><script>setInterval(() => location.reload(), 10000);</script></body></html>'''

@app.route('/')
def dashboard():
    if request.cookies.get('admin_auth') != 'true': return redirect('/login')
    db = load_db()
    keys_html = ''
    for k, data in db["keys"].items():
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
        bnd_html = f'<br><small class="text-warning">Chỉ định: {bnd}</small>' if bnd else ''

        keys_html += f'''
        <tr class="key-row" data-status="{ "banned" if is_banned else ("expired" if is_expired else "active") }">
            <td><div class="d-flex align-items-center"><strong class="me-2 text-info">{k}</strong><button class="btn btn-sm btn-outline-light copy-btn" onclick="copyText('{k}')" title="Sao chép">📋</button></div><div class="mt-1">{status_badge} {sys_badge}{bnd_html}</div></td>
            <td>{exp_text}</td><td><span class="badge bg-primary">{len(data.get('devices', []))}/{data.get('maxDevices', 1)}</span></td>
            <td><div class="btn-group btn-group-sm"><button class="btn btn-warning" onclick="openBindModal('{k}', '{bnd}')">🔐 Ghim</button><button class="btn btn-info" onclick="openExtendModal('{k}')">⏳</button><a href="/admin/action/add-dev/{k}" class="btn btn-success">+</a><a href="/admin/action/sub-dev/{k}" class="btn btn-secondary">-</a><a href="/admin/action/reset-dev/{k}" class="btn btn-primary">🔄</a><a href="/admin/action/{"unban" if is_banned else "ban"}/{k}" class="btn btn-{"light" if is_banned else "danger"}">{"Mở" if is_banned else "Khóa"}</a><a href="/admin/action/toggle_vip/{k}" class="btn btn-warning text-dark">VIP↕</a><a href="/admin/action/delete/{k}" class="btn btn-dark" onclick="return confirm('Xóa?')">🗑️</a></div></td>
        </tr>'''

    ips_html = ''
    for ip, exp in db.get("banned_ips", {}).items():
        exp_txt = "Vĩnh viễn" if exp == 'permanent' else time.strftime('%d/%m/%Y %H:%M', time.localtime(exp / 1000))
        ips_html += f'<tr><td>{ip}</td><td>{exp_txt}</td><td><a href="/admin/unban-ip/{ip}" class="btn btn-sm btn-success">Gỡ Ban</a></td></tr>'
        
    olm_html = ''
    for u, exp in db.get("locked_olm", {}).items():
        exp_txt = "Vĩnh viễn" if exp == 'permanent' else time.strftime('%d/%m/%Y %H:%M', time.localtime(exp / 1000))
        olm_html += f'<tr><td class="text-warning">{u}</td><td>{exp_txt}</td><td><a href="/admin/unlock_olm/{u}" class="btn btn-sm btn-success">Mở Khóa</a></td></tr>'

    logs_html = ''
    for log in db.get("logs", []):
        color = "warning"
        if "THOÁT OLM" in log['action']: color = "secondary"
        elif "TRUY CẬP OLM" in log['action']: color = "info"
        elif "URL SCRIPT" in log['action']: color = "success"
        elif "ADMIN BOT" in log['action']: color = "dark border border-light"
        elif "LOADER" in log['action']: color = "primary"
        elif "BANNED" in log['action'] or "BỊ CHẶN" in log['action'] or "SAI" in log['action'] or "GIỚI HẠN" in log['action']: color = "danger"
            
        logs_html += f'<tr><td><small class="text-muted">{time.strftime("%H:%M:%S %d/%m", time.localtime(log["time"]))}</small></td><td><span class="badge bg-{color}">{log["action"]}</span></td><td class="text-info">{log["key"]}</td><td><span class="badge bg-secondary">{log["ip"]}</span><br><small class="text-muted">{log.get("olm_name","")}</small><br><small style="font-size:10px;">{log.get("device","")}</small></td></tr>'

    users_html = ''
    for uid, udata in db.get("bot_users", {}).items():
        uname = udata.get("username", "")
        uname_html = f'<span class="text-warning">{uname}</span>' if uname else ''
        users_html += f'<tr><td><strong class="text-info">{udata["name"]}</strong> {uname_html}<br><small class="text-muted">{uid}</small></td><td><span class="badge bg-success">{udata["balance"]}</span></td><td>{udata["resets"]} lần</td></tr>'

    return f'''
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>LVT PRO - Admin</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>:root {{ --bg-main: #0a0a12; --bg-card: #151525; --neon-cyan: #00ffcc; --neon-purple: #bd00ff; }} body {{ background: var(--bg-main); color: #e0e0e0; font-family: 'Segoe UI', Tahoma, sans-serif; }} .card {{ background: var(--bg-card); border: 1px solid #2a2a40; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }} h1, h4 {{ color: var(--neon-cyan); font-weight: 800; }} .btn-primary {{ background: linear-gradient(45deg, var(--neon-purple), #7a00ff); border: none; font-weight: bold; }} .table-container {{ max-height: 500px; overflow-y: auto; }} tbody tr:hover {{ background-color: rgba(0, 255, 204, 0.05) !important; }} #toastBox {{ position: fixed; bottom: 20px; right: 20px; z-index: 9999; }}</style></head><body class="p-2 p-md-4"><div id="toastBox"></div><div class="container-fluid"><div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary"><h1 class="m-0">⚡ LVT ADMIN</h1><div><a href="/admin/online" class="btn btn-success me-2 fw-bold">📡 Giám Sát IP Online</a><a href="/logout" class="btn btn-outline-danger">Đăng xuất</a></div></div><div class="row g-4"><div class="col-lg-4">
    
    <div class="card p-3 mb-4" style="border-color: #00ffcc;"><h4><i class="fas fa-wrench"></i> Tạo Key LVT Tool</h4><form action="/admin/create" method="POST" class="row g-2"><input type="hidden" name="target_app" value="tool"><div class="col-6"><input type="text" name="prefix" class="form-control bg-dark text-light" placeholder="Prefix (Mặc định: LVT)"></div><div class="col-6"><input type="number" name="quantity" class="form-control bg-dark text-light" value="1"></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="min">Phút</option><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-6"><input type="number" name="maxDevices" class="form-control bg-dark text-light" placeholder="Max TB" value="1"></div><div class="col-6 d-flex align-items-end"><div class="form-check form-switch"><input class="form-check-input" type="checkbox" name="is_vip" id="vipSwitch1"><label class="form-check-label text-warning" for="vipSwitch1">Chế độ VIP</label></div></div><div class="col-12 mt-3"><button type="submit" class="btn btn-primary w-100" style="background: linear-gradient(45deg, #00ffcc, #0066ff); color:black;">TẠO KEY LVT</button></div></form></div>
    
    <div class="card p-3 mb-4" style="border-color: #ff3366;"><h4><i class="fas fa-crosshairs"></i> Tạo Key OLM</h4><form action="/admin/create" method="POST" class="row g-2"><input type="hidden" name="target_app" value="olm"><div class="col-6"><input type="text" name="prefix" class="form-control bg-dark text-light" placeholder="Prefix (Mặc định: OLM)"></div><div class="col-6"><input type="number" name="quantity" class="form-control bg-dark text-light" value="1"></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="min">Phút</option><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-6"><input type="number" name="maxDevices" class="form-control bg-dark text-light" placeholder="Max TB" value="1"></div><div class="col-6 d-flex align-items-end"><div class="form-check form-switch"><input class="form-check-input" type="checkbox" name="is_vip" id="vipSwitch2"><label class="form-check-label text-warning" for="vipSwitch2">Chế độ VIP</label></div></div><div class="col-12 mt-3"><button type="submit" class="btn btn-primary w-100" style="background: linear-gradient(45deg, #ff3366, #ff9900); color:white;">TẠO KEY OLM</button></div></form></div>
    
    <div class="card p-3 mb-4" style="border-color: #fff;"><h4><i class="fas fa-robot"></i> Tạo Key Admin Telegram</h4><form action="/admin/create" method="POST" class="row g-2"><input type="hidden" name="target_app" value="admin_bot"><input type="hidden" name="is_vip" value="on"><input type="hidden" name="quantity" value="1"><div class="col-12"><input type="text" name="prefix" class="form-control bg-dark text-light" placeholder="Tên Key (VD: ADMIN)"></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="day">Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-12"><input type="number" name="maxDevices" class="form-control bg-dark text-light" placeholder="Giới hạn số Telegram dùng chung" value="1"></div><div class="col-12 mt-2"><button type="submit" class="btn btn-light w-100 fw-bold text-dark">TẠO KEY ADMIN</button></div></form></div>
    
    <div class="card p-3 mb-4" style="border-color: #2AABEE;"><h4><i class="fab fa-telegram"></i> Quản Lý User Bot Telegram</h4>
    <form action="/admin/add_balance" method="POST" class="row g-2 mb-3">
        <div class="col-12"><input type="text" name="target_user" class="form-control bg-dark text-light" placeholder="Nhập @username hoặc ID khách..." required></div>
        <div class="col-5"><input type="number" name="amount" class="form-control bg-dark text-light" placeholder="Tiền (VD: 50000)" value="0" required></div>
        <div class="col-4"><input type="number" name="resets" class="form-control bg-dark text-light" placeholder="+ Lượt Reset" value="0" required></div>
        <div class="col-3"><button type="submit" class="btn w-100 fw-bold" style="background:#2AABEE; color:white;">Nạp</button></div>
    </form>
    <div class="table-container" style="max-height:150px;"><table class="table table-dark table-sm mb-0"><thead><tr><th>Tên (Username/ID)</th><th>Số Dư</th><th>Reset</th></tr></thead><tbody>{users_html}</tbody></table></div></div>
    
    </div><div class="col-lg-8">
    
    <div class="card p-3 mb-4"><h4 class="text-danger">🛡️ Block IP & Khóa Tên OLM</h4><div class="row g-3"><div class="col-md-6"><form action="/admin/ban-ip" method="POST" class="row g-2"><div class="col-12"><input type="text" name="ip" class="form-control bg-dark text-light" placeholder="Nhập IP..." required></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian"></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="hour">Giờ</option><option value="day">Ngày</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-12"><button type="submit" class="btn btn-danger w-100">Ban IP</button></div></form><div class="table-container mt-2" style="max-height:150px;"><table class="table table-dark table-sm mb-0"><thead><tr><th>IP</th><th>Hạn</th><th>Xóa</th></tr></thead><tbody>{ips_html}</tbody></table></div></div><div class="col-md-6"><form action="/admin/lock_olm" method="POST" class="row g-2"><div class="col-12"><input type="text" name="user" class="form-control bg-dark text-light" placeholder="Nhập Tên OLM (VD: hp_abc)" required></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian"></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="hour">Giờ</option><option value="day">Ngày</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-12"><button type="submit" class="btn btn-warning w-100 text-dark fw-bold">Khóa Tên OLM</button></div></form><div class="table-container mt-2" style="max-height:150px;"><table class="table table-dark table-sm mb-0"><thead><tr><th>Tên OLM</th><th>Hạn</th><th>Xóa</th></tr></thead><tbody>{olm_html}</tbody></table></div></div></div></div>
    
    <div class="card p-3 mb-4" style="border-color: #bd00ff;"><h4>📢 Thông Báo Toàn Cầu (Gửi đến Script/Tool)</h4><form action="/admin/notice" method="POST" class="row g-2"><div class="col-12"><input type="text" name="message" class="form-control bg-dark text-light" placeholder="Nhập thông báo hiện lên màn hình người dùng..." value="{db.get("global_notice", {}).get("msg", "")}"></div><div class="col-4"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian" required value="10"></div><div class="col-5"><select name="type" class="form-select bg-dark text-light"><option value="sec">Giây</option><option value="min">Phút</option><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option><option value="year">Năm</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-3"><button type="submit" class="btn btn-info w-100 fw-bold">Phát Loa</button></div></form></div>
    
    <div class="card p-3 mb-4"><div class="d-flex justify-content-between align-items-center mb-3"><h4>📋 Quản Lý Key</h4><div class="d-flex gap-2"><form action="/admin/delete_all" method="POST"><button class="btn btn-sm btn-danger fw-bold" onclick="return confirm('CHẮC CHẮN XÓA TOÀN BỘ KEY?')">Xóa ALL Key</button></form><select id="statusFilter" class="form-select form-select-sm bg-dark text-light" onchange="filterTable()"><option value="all">Tất cả</option><option value="active">Hoạt động</option><option value="expired">Hết hạn</option><option value="banned">Bị khóa</option></select><input type="text" id="searchInput" class="form-control form-control-sm bg-dark text-light" placeholder="Tìm Key..." onkeyup="filterTable()"></div></div><div class="table-container"><table class="table table-dark table-hover mb-0 align-middle"><thead><tr><th>Key</th><th>Hạn</th><th>Thiết bị</th><th>Điều Khiển</th></tr></thead><tbody id="keyTableBody">{keys_html}</tbody></table></div></div><div class="card p-3"><h4>📡 Lịch sử Logs (Chi tiết IP, TB, User)</h4><div class="table-container" style="max-height:400px;"><table class="table table-dark table-sm table-striped mb-0"><thead><tr><th>Time</th><th>Trạng thái</th><th>Key</th><th>Thông tin IP / Device / OLM</th></tr></thead><tbody>{logs_html}</tbody></table></div></div></div></div>
    
    <div class="modal fade" id="extendModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:var(--bg-card);"><div class="modal-header"><h5 class="modal-title">⏳ Gia hạn Key</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form action="/admin/extend" method="POST"><div class="modal-body"><input type="hidden" name="key" id="extendKeyInput"><p>Key: <strong id="extendKeyDisplay" class="text-info"></strong></p><div class="row g-2"><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option></select></div></div></div><div class="modal-footer"><button type="submit" class="btn btn-primary w-100">Gia hạn</button></div></form></div></div></div>
    <div class="modal fade" id="bindModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:var(--bg-card);"><div class="modal-header"><h5 class="modal-title">🔐 Ghim Độc Quyền Account</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form action="/admin/bind_olm" method="POST"><div class="modal-body"><input type="hidden" name="key" id="bindKeyInput"><p>Key: <strong id="bindKeyDisplay" class="text-info"></strong></p><div class="row g-2"><div class="col-12"><input type="text" name="olm_name" id="bindOlmInput" class="form-control bg-dark text-light" placeholder="Nhập tên OLM muốn ghim (bỏ trống để hủy ghim)"></div></div></div><div class="modal-footer"><button type="submit" class="btn btn-warning w-100">Lưu Chỉ Định</button></div></form></div></div></div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function copyText(text) {{ navigator.clipboard.writeText(text); alert("Đã copy: " + text); }} 
        function filterTable() {{ let s = document.getElementById('searchInput').value.toLowerCase(), f = document.getElementById('statusFilter').value; document.querySelectorAll('.key-row').forEach(r => {{ r.style.display = (r.innerText.toLowerCase().includes(s) && (f==='all' || r.dataset.status===f)) ? '' : 'none'; }}); }} 
        function openExtendModal(key) {{ document.getElementById('extendKeyInput').value = key; document.getElementById('extendKeyDisplay').innerText = key; new bootstrap.Modal(document.getElementById('extendModal')).show(); }}
        function openBindModal(key, current_olm) {{ document.getElementById('bindKeyInput').value = key; document.getElementById('bindKeyDisplay').innerText = key; document.getElementById('bindOlmInput').value = current_olm; new bootstrap.Modal(document.getElementById('bindModal')).show(); }}
        
        let reloadTimer = setTimeout(() => location.reload(), 15000);
        document.querySelectorAll('input, select').forEach(el => {{
            el.addEventListener('focus', () => clearTimeout(reloadTimer));
            el.addEventListener('blur', () => reloadTimer = setTimeout(() => location.reload(), 15000));
        }});
    </script></body></html>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
