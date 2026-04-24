import os
import json
import time
import random
import hashlib
import threading
import requests
import re
import shutil
from flask import Flask, request, jsonify, redirect, make_response

# --- ANTI-BUG / ANTI-TAMPER ---
try:
    with open(__file__, 'rb') as f:
        __original_hash__ = hashlib.md5(f.read()).hexdigest()
except:
    __original_hash__ = None

def __anti_tamper__():
    while True:
        time.sleep(5)
        try:
            with open(__file__, 'rb') as f:
                if hashlib.md5(f.read()).hexdigest() != __original_hash__:
                    os._exit(0) 
        except: pass

threading.Thread(target=__anti_tamper__, daemon=True).start()

app = Flask(__name__)
DB_FILE = './database.json'
DB_BACKUP = './database.backup.json'
ADMIN_PASSWORD = 'admin120510'

# ========================================================
# CẤU HÌNH BOT TELEGRAM
# ========================================================
TELEGRAM_BOT_TOKEN = "8621133442:AAEimlzP2LKIfWOLE18iQGoUUHS7pyXmDuw"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
WEB_URL = "https://app-tool-trlp.onrender.com"
# ========================================================

remote_unlocks = {}
logout_pins = set()
active_sessions = {} 

def parse_duration(duration_str):
    if duration_str.lower() in ['vv', 'vinhvien', 'permanent']: return 'permanent'
    match = re.match(r"(\d+)([a-zA-Z]+)", duration_str.strip())
    if not match: return 0
    amount, unit = int(match.group(1)), match.group(2).lower()
    multipliers = {'s': 1000, 'm': 60000, 'h': 3600000, 'd': 86400000, 'mo': 2592000000, 'y': 31536000000}
    return amount * multipliers.get(unit, 0)

multipliers_web = {'sec': 1000, 'min': 60000, 'hour': 3600000, 'day': 86400000, 'month': 2592000000, 'year': 31536000000}

# --- THREAD GIÁM SÁT & AUTO RECOVER ---
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
    try: requests.post(f"{TELEGRAM_API_URL}/setMyCommands", json={"commands": [{"command": "start", "description": "🏠 Menu Khách Hàng"}, {"command": "loaderkey", "description": "🔗 Kích Hoạt Tool Từ Xa"}, {"command": "admin", "description": "👑 Bảng Điều Khiển Server"}]})
    except: pass

    while True:
        time.sleep(180) # Ping mạng ngoài
        try: requests.get(WEB_URL)
        except: pass
        if os.path.exists(DB_FILE):
            try: shutil.copy2(DB_FILE, DB_BACKUP)
            except: pass

threading.Thread(target=session_monitor, daemon=True).start()
threading.Thread(target=keep_alive_and_backup, daemon=True).start()

# --- LUỒNG LIVE TIMER (TỰ ĐỘNG ĐẾM NGƯỢC TRÊN TELEGRAM) ---
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
                        if k in db["keys"]:
                            kData = db["keys"][k]
                            t_left = format_time_left(kData["exp"], now_ms)
                            txt = f"🟢 <b>ĐANG GIÁM SÁT TOOL</b>\n\n🔑 Key đang chạy: <code>{k}</code>\n⏳ Thời gian còn lại: <b>{t_left}</b>\n⚡ Trạng thái: Hoạt động bình thường"
                            markup = {"inline_keyboard": [[{"text": "❌ Ngắt Kết Nối Tool", "callback_data": "LOADER_DISCONNECT"}]]}
                            edit_telegram_message(uid, msg_id, txt, markup)
                    
                    elif m_type == "admin" and user.get("is_admin"):
                        adm_key = user.get("admin_key", "")
                        if adm_key in db["keys"]:
                            t_left = format_time_left(db["keys"][adm_key]["exp"], now_ms)
                            markup = {"inline_keyboard": [
                                [{"text": "➕ Tạo Key Tool", "callback_data": "ADM_W_CREATE"}, {"text": "💰 Nạp Tiền Bank", "callback_data": "ADM_W_BAL"}],
                                [{"text": "🔒 Khóa Nick OLM", "callback_data": "ADM_W_LOCK"}, {"text": "🚫 Chặn IP Máy", "callback_data": "ADM_W_BAN"}],
                                [{"text": "📢 TB Lên Tool", "callback_data": "ADM_W_NOTE"}, {"text": "💬 TB Vào Bot", "callback_data": "ADM_BOT_NOTE"}],
                                [{"text": "👤 Soi Info Khách", "callback_data": "ADM_USER"}, {"text": "🛠 Quản Lý Mọi Key", "callback_data": "ADM_MANAGE"}],
                                [{"text": "📜 Theo Dõi Radar", "callback_data": "ADM_LOGS"}],
                                [{"text": "❌ Hủy Quyền Admin", "callback_data": "ADM_LOGOUT"}]
                            ]}
                            txt = f"👑 <b>BẢNG ĐIỀU KHIỂN SERVER (SaaS)</b>\n\n⏳ <i>Hạn Admin còn: {t_left}</i>"
                            edit_telegram_message(uid, msg_id, txt, markup)
        except: pass

threading.Thread(target=live_timer_updater, daemon=True).start()

# ----------------------------------------------------

@app.after_request
def add_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

def load_db():
    if not os.path.exists(DB_FILE) and os.path.exists(DB_BACKUP): shutil.copy2(DB_BACKUP, DB_FILE)
    if not os.path.exists(DB_FILE): return {"keys": {}, "logs": [], "banned_ips": {}, "logout_pins": [], "global_notice": {}, "locked_olm": {}, "ip_strikes": {}, "bot_users": {}}
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            data.setdefault("bot_users", {}); data.setdefault("locked_olm", {}); data.setdefault("banned_ips", {}); data.setdefault("keys", {}); data.setdefault("logs", []); data.setdefault("logout_pins", [])
            if not isinstance(data.get("global_notice"), dict): data["global_notice"] = {"msg": "", "exp": "permanent"}
            for uid in data["bot_users"]:
                u = data["bot_users"][uid]
                u.setdefault("purchases", []); u.setdefault("notices", []); u.setdefault("loader_active", False)
                u.setdefault("loader_key", ""); u.setdefault("loader_pin", "")
                u.setdefault("live_msg_id", None); u.setdefault("live_msg_type", None)
                u.setdefault("main_menu_id", None)
            for k in data["keys"]:
                data["keys"][k].setdefault("bound_olm", "") 
            return data
        except: return {"keys": {}, "logs": [], "banned_ips": {}, "logout_pins": [], "global_notice": {}, "locked_olm": {}, "ip_strikes": {}, "bot_users": {}}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f: json.dump(db, f, indent=2, ensure_ascii=False)

def add_log(db, action, key, ip, device, olm_name="N/A"):
    db.setdefault("logs", []).insert(0, {"time": int(time.time()), "action": action, "key": key, "ip": ip, "device": device, "olm_name": olm_name})
    db["logs"] = db["logs"][:500] 

def get_real_ip():
    if request.headers.getlist("X-Forwarded-For"): return request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
    return request.remote_addr

def process_key_validation(db, key, deviceId, real_ip, target_app, expected_type, device_name="Unknown", olm_name="N/A"):
    current_time = int(time.time() * 1000)

    if real_ip in db["banned_ips"]:
        if db["banned_ips"][real_ip] == 'permanent' or current_time < db["banned_ips"][real_ip]: return False, {"status": "error", "message": "IP của bạn đã bị khóa!"}
        else: del db["banned_ips"][real_ip]

    if olm_name != "N/A" and olm_name in db["locked_olm"]:
        if db["locked_olm"][olm_name] == 'permanent' or current_time < db["locked_olm"][olm_name]: return False, {"status": "error", "message": f"Tài khoản OLM '{olm_name}' đang bị khóa!", "is_locked_olm": True, "lock_exp": db["locked_olm"][olm_name]}
        else: del db["locked_olm"][olm_name]

    if not key or key not in db["keys"]: return False, {"status": "error", "message": "Key không tồn tại!"}

    kData = db["keys"][key]
    if kData.get('target', 'tool') != target_app and target_app not in ["admin_bot", "telegram_loader"]:
        return False, {"status": "error", "message": "Sai hệ thống!"}

    if kData.get('status') == 'banned': return False, {"status": "error", "message": "Key bị khóa!"}
    if kData.get('exp') == 'pending': kData['exp'] = current_time + kData.get('durationMs', 0)
    if kData.get('exp') != 'permanent' and current_time > kData.get('exp', 0): return False, {"status": "error", "message": "Key hết hạn!"}

    # --- TÍNH NĂNG ĐỘC QUYỀN ACCOUNT OLM ---
    if target_app in ["olm", "telegram_loader"] and olm_name != "N/A":
        bound = kData.get("bound_olm", "")
        if bound and bound.lower() != olm_name.lower():
            return False, {"status": "error", "message": f"Cảnh báo: Key này ĐỘC QUYỀN chỉ hoạt động trên tài khoản OLM: {bound}"}

    if target_app != "telegram_loader" and deviceId not in kData.get('devices', []):
        if len(kData.get('devices', [])) >= kData.get('maxDevices', 1):
            return False, {"status": "error", "message": "Key đã đầy thiết bị!"}
        kData.setdefault('devices', []).append(deviceId)

    if target_app == "olm":
        active_sessions[deviceId] = {"ip": real_ip, "olm_name": olm_name, "key": key, "last_seen": time.time()}
        add_log(db, "TRUY CẬP OLM", key, real_ip, f"{device_name} ({deviceId})", olm_name)
    elif target_app == "admin_bot": pass
    elif target_app == "telegram_loader": add_log(db, "LOADER KẾT NỐI", key, real_ip, f"Telegram Loader", "N/A")
    else: add_log(db, "THÀNH CÔNG", key, real_ip, f"{device_name} ({deviceId})", olm_name)
    
    save_db(db)
    notice = db.get("global_notice", {})
    notice_msg = notice.get("msg", "") if (notice.get("exp") == "permanent" or current_time < notice.get("exp", 0)) else ""
    return True, {"status": "success", "exp": kData.get('exp'), "vip": kData.get('vip'), "notice": notice_msg}

# ====================================================================
# TELEGRAM BOT ENGINE
# ====================================================================
def send_telegram_message(chat_id, text, reply_markup=None):
    if not TELEGRAM_BOT_TOKEN: return None
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: payload["reply_markup"] = reply_markup
    try: 
        res = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload).json()
        return res.get("result", {}).get("message_id")
    except: return None

def edit_telegram_message(chat_id, message_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: payload["reply_markup"] = reply_markup
    try: requests.post(f"{TELEGRAM_API_URL}/editMessageText", json=payload)
    except: pass

def delete_telegram_message(chat_id, message_id):
    try: requests.post(f"{TELEGRAM_API_URL}/deleteMessage", json={"chat_id": chat_id, "message_id": message_id})
    except: pass

def get_user_id_by_username(db, username):
    username = username.strip().lower()
    for uid, info in db["bot_users"].items():
        if info.get("username", "").lower() == username: return uid
    return None

def format_time_left(exp_ms, now_ms):
    if exp_ms == "permanent": return "Vĩnh viễn"
    rem = exp_ms - now_ms
    if rem <= 0: return "Đã hết hạn"
    d = rem // 86400000; h = (rem % 86400000) // 3600000; m = (rem % 3600000) // 60000; s = (rem % 60000) // 1000
    if d > 0: return f"{d} ngày {h} giờ {m} phút"
    if h > 0: return f"{h} giờ {m} phút {s} giây"
    return f"{m} phút {s} giây"


@app.route('/webhook', methods=['GET', 'POST'])
def telegram_webhook():
    if request.method == 'GET': return "Webhook OK", 200

    try:
        data = request.json
        if not data: return "ok", 200
        
        chat_id = None; msg_text = ""; payload = ""; user_name = "Khách"; tg_username = ""; message_id = None
        if "message" in data:
            chat_id = str(data["message"]["chat"]["id"])
            message_id = data["message"]["message_id"]
            msg_text = data["message"].get("text", "").strip()
            user_name = data["message"]["from"].get("first_name", "Khách")
            tg_username = data["message"]["from"].get("username", "")
        elif "callback_query" in data:
            chat_id = str(data["callback_query"]["message"]["chat"]["id"])
            message_id = data["callback_query"]["message"]["message_id"]
            payload = data["callback_query"]["data"]
            user_name = data["callback_query"]["from"].get("first_name", "Khách")
            tg_username = data["callback_query"]["from"].get("username", "")
            try: requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": data["callback_query"]["id"]}, timeout=2)
            except: pass

        if not chat_id: return "ok", 200
        db = load_db()
        sid = chat_id
        safe_name = user_name.replace("<", "").replace(">", "")
        f_uname = f"@{tg_username}" if tg_username else ""
        now_ms = int(time.time() * 1000)
        
        is_new_user = False
        if sid not in db["bot_users"]:
            is_new_user = True
            db["bot_users"][sid] = {"name": safe_name, "username": f_uname, "balance": 0, "resets": 3, "state": "none", "is_admin": False, "purchases": [], "notices": [], "loader_active": False, "loader_key": "", "loader_pin": "", "main_menu_id": None, "live_msg_id": None, "live_msg_type": None}
        else: db["bot_users"][sid]["username"] = f_uname
        
        user = db["bot_users"][sid]

        if msg_text:
            delete_telegram_message(sid, message_id)

        if is_new_user:
            for uid, uinfo in db["bot_users"].items():
                if uinfo.get("is_admin"):
                    send_telegram_message(uid, f"🚨 <b>CÓ KHÁCH HÀNG MỚI!</b>\n👤 Tên: {safe_name} {f_uname}\n🆔 ID: <code>{sid}</code>\nVừa sử dụng Bot lần đầu tiên.")

        if msg_text.startswith("/"):
            user["state"] = "none"
            user["live_msg_type"] = None

        # ======= COMMANDS & MENUS =======
        if msg_text.upper() == "/START" or payload == "MENU_MAIN":
            active_notices = []
            valid_notices = []
            for n in user["notices"]:
                if n["exp"] == 'permanent' or n["exp"] > now_ms:
                    valid_notices.append(n); active_notices.append(n["msg"])
            user["notices"] = valid_notices; user["live_msg_type"] = None
            
            txt = "🎉 <b>Chào mừng bạn đến với autokey . admin @luongtuyen</b>\n➖➖➖➖➖➖➖➖\n\n"
            if active_notices: txt += "🔔 <b>THÔNG BÁO:</b>\n" + "\n".join([f"🔸 {m}" for m in active_notices]) + "\n\n"
            
            txt += f"👋 Chào mừng <b>{safe_name}</b>!\n\n💳 <b>THÔNG TIN TÀI KHOẢN:</b>\n├ 🆔 ID: <code>{sid}</code>\n├ 💰 Số dư: <b>{user['balance']}đ</b>\n└ 🔄 Lượt Reset Key: <b>{user['resets']}/3</b>\n\n👇 <i>Vui lòng chọn dịch vụ:</i>"
            markup = {"inline_keyboard": [
                [{"text": "🛒 Mua Key Mới", "callback_data": "BUY"}, {"text": "🔄 Reset Key", "callback_data": "RESET"}],
                [{"text": "🔗 Loader Tool (Nhập Key)", "callback_data": "LOADER_MENU"}]
            ]}
            
            if payload and user["main_menu_id"]:
                edit_telegram_message(sid, user["main_menu_id"], txt, markup)
            else:
                if user["main_menu_id"]: delete_telegram_message(sid, user["main_menu_id"])
                new_id = send_telegram_message(sid, txt, markup)
                user["main_menu_id"] = new_id
            save_db(db); return "ok", 200

        elif msg_text.upper() == "/LOADERKEY" or payload == "LOADER_MENU":
            user["state"] = "wait_loader_pin"; user["live_msg_type"] = None
            txt = "🔗 <b>KẾT NỐI TOOL / SCRIPT TỪ XA</b>\n\n🔢 Vui lòng nhập <b>Mã PIN (6 số)</b> hiển thị trên màn hình Tool OLM:"
            if payload and user["main_menu_id"]: edit_telegram_message(sid, user["main_menu_id"], txt)
            else:
                if user["main_menu_id"]: delete_telegram_message(sid, user["main_menu_id"])
                user["main_menu_id"] = send_telegram_message(sid, txt)
            save_db(db); return "ok", 200

        elif payload == "LOADER_DISCONNECT":
            pin = user.get("loader_pin", "")
            if pin and pin not in db.setdefault("logout_pins", []): db["logout_pins"].append(pin)
            user["loader_active"] = False; user["loader_key"] = ""; user["loader_pin"] = ""; user["live_msg_type"] = None
            edit_telegram_message(sid, user["main_menu_id"], "✅ <b>ĐÃ NGẮT KẾT NỐI BẢO MẬT.</b>\nLệnh xóa Key đã được gửi đi.", {"inline_keyboard": [[{"text": "🏠 Về Trang Chủ", "callback_data": "MENU_MAIN"}]]})
            save_db(db); return "ok", 200

        elif msg_text.upper() == "/ADMIN" or payload == "ADM_MENU":
            if user.get("is_admin"):
                adm_key = user.get("admin_key", "")
                success, _ = process_key_validation(db, adm_key, sid, "TELEGRAM", "admin_bot", "any")
                if not success:
                    user["is_admin"] = False; user["admin_key"] = ""; user["state"] = "none"; user["live_msg_type"] = None; save_db(db)
                    if user["main_menu_id"]: edit_telegram_message(sid, user["main_menu_id"], "⚠️ <b>Key Admin bị khóa hoặc hết hạn.</b> Đã tước quyền!")
                    return "ok", 200

                user["state"] = "none"; user["live_msg_type"] = "admin"
                exp_ms = db["keys"][adm_key]["exp"]
                t_left = format_time_left(exp_ms, now_ms)
                markup = {"inline_keyboard": [
                    [{"text": "➕ Tạo Key Tool", "callback_data": "ADM_W_CREATE"}, {"text": "💰 Nạp Tiền Bank", "callback_data": "ADM_W_BAL"}],
                    [{"text": "🔒 Khóa Nick OLM", "callback_data": "ADM_W_LOCK"}, {"text": "🚫 Chặn IP Máy", "callback_data": "ADM_W_BAN"}],
                    [{"text": "📢 TB Lên Tool", "callback_data": "ADM_W_NOTE"}, {"text": "💬 TB Vào Bot", "callback_data": "ADM_BOT_NOTE"}],
                    [{"text": "👤 Soi Info Khách", "callback_data": "ADM_USER"}, {"text": "🛠 Quản Lý Mọi Key", "callback_data": "ADM_MANAGE"}],
                    [{"text": "📜 Theo Dõi Radar", "callback_data": "ADM_LOGS"}],
                    [{"text": "❌ Hủy Quyền Admin", "callback_data": "ADM_LOGOUT"}]
                ]}
                txt = f"👑 <b>BẢNG ĐIỀU KHIỂN SERVER (SaaS)</b>\n\n⏳ <i>Hạn Admin còn: {t_left}</i>"
                if payload and user["main_menu_id"]:
                    user["live_msg_id"] = user["main_menu_id"]
                    edit_telegram_message(sid, user["main_menu_id"], txt, markup)
                else:
                    if user["main_menu_id"]: delete_telegram_message(sid, user["main_menu_id"])
                    new_id = send_telegram_message(sid, txt, markup)
                    user["main_menu_id"] = new_id; user["live_msg_id"] = new_id
            else:
                user["state"] = "wait_admin_key"; user["live_msg_type"] = None
                txt = "🔐 <b>BẢO MẬT SERVER</b>\nVui lòng nhập <code>Key Admin</code> để mở khóa:"
                if user["main_menu_id"]: edit_telegram_message(sid, user["main_menu_id"], txt)
                else: user["main_menu_id"] = send_telegram_message(sid, txt)
            save_db(db); return "ok", 200

        # ======= XỬ LÝ PAYLOADS (NÚT BẤM) =======
        if payload and user["main_menu_id"]:
            user["live_msg_type"] = None 
            if payload == "BUY":
                markup = {"inline_keyboard": [[{"text": "👑 Mua Key VIP", "callback_data": "BUY_VIP"}, {"text": "👤 Mua Key Thường", "callback_data": "BUY_NOR"}],[{"text": "🔙 Quay Lại", "callback_data": "MENU_MAIN"}]]}
                edit_telegram_message(sid, user["main_menu_id"], "💳 <b>CHỌN LOẠI KEY MUỐN MUA:</b>", markup)
            elif payload == "BUY_NOR":
                edit_telegram_message(sid, user["main_menu_id"], "🛠 <b>Tính năng Mua Key Thường đang bảo trì.</b>", {"inline_keyboard": [[{"text": "🔙 Quay Lại", "callback_data": "BUY"}]]})
            elif payload == "BUY_VIP":
                txt = "🛒 <b>BẢNG GIÁ KEY VIP:</b>\n🕒 1 Giờ: <b>7,000đ</b>\n📅 7 Ngày: <b>30,000đ</b>\n📆 30 Ngày: <b>85,000đ</b>\n🏆 1 Năm: <b>200,000đ</b>\n\n👇 Chọn gói:"
                markup = {"inline_keyboard": [[{"text": "🕒 1 Giờ", "callback_data": "V_1H"},{"text": "📅 7 Ngày", "callback_data": "V_7D"}], [{"text": "📆 30 Ngày", "callback_data": "V_30D"},{"text": "🏆 1 Năm", "callback_data": "V_1Y"}], [{"text": "🔙 Quay Lại", "callback_data": "BUY"}]]}
                edit_telegram_message(sid, user["main_menu_id"], txt, markup)
            elif payload.startswith("V_"):
                user["state"] = f"wait_qty_{payload}"
                edit_telegram_message(sid, user["main_menu_id"], "🔢 Vui lòng nhập <b>SỐ LƯỢNG</b> Key bạn muốn mua (Nhập số: 1, 2, 5...):")
            elif payload == "RESET":
                if user["resets"] <= 0: edit_telegram_message(sid, user["main_menu_id"], "❌ Bạn đã hết lượt Reset.", {"inline_keyboard": [[{"text": "🔙 Menu", "callback_data": "MENU_MAIN"}]]})
                else:
                    user["state"] = "wait_reset_key"
                    edit_telegram_message(sid, user["main_menu_id"], "📝 Gửi chính xác <code>Mã Key</code> cần Reset vào đây:")
            
            # --- ADMIN PAYLOADS ---
            elif user.get("is_admin"):
                if payload == "ADM_W_CREATE":
                    user["state"] = "adm_create"
                    edit_telegram_message(sid, user["main_menu_id"], "➕ <b>TẠO KEY TOOL</b>\nCú pháp: <code>Hệ Thời_gian Số_máy</code>\nVD: <code>OLM 30d 1</code>", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})
                elif payload == "ADM_W_BAL":
                    user["state"] = "adm_bal"
                    edit_telegram_message(sid, user["main_menu_id"], "💰 <b>NẠP TIỀN & RESET</b>\nCú pháp: <code>@user Tiền Số_Reset</code>\nVD: <code>@luongtuyen20 50k 3</code>", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})
                elif payload == "ADM_W_LOCK":
                    user["state"] = "adm_lock"
                    edit_telegram_message(sid, user["main_menu_id"], "🔒 <b>KHÓA TÊN OLM</b>\nCú pháp: <code>Thời_gian Tên_OLM</code>\nVD: <code>vv hp_abc</code>", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})
                elif payload == "ADM_W_BAN":
                    user["state"] = "adm_ban"
                    edit_telegram_message(sid, user["main_menu_id"], "🚫 <b>CHẶN IP MÁY</b>\nCú pháp: <code>Thời_gian IP</code>", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})
                elif payload == "ADM_W_NOTE":
                    user["state"] = "adm_note"
                    edit_telegram_message(sid, user["main_menu_id"], "📢 <b>TB LÊN TOOL</b>\nCú pháp: <code>Thời_gian Nội_dung</code>", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})
                elif payload == "ADM_BOT_NOTE":
                    markup = {"inline_keyboard": [[{"text": "📢 Gửi ALL Khách", "callback_data": "ADM_BN_ALL"}, {"text": "👤 Gửi 1 Khách Riêng", "callback_data": "ADM_BN_PRIV"}]]}
                    edit_telegram_message(sid, user["main_menu_id"], "💬 <b>TB VÀO BOT TELEGRAM</b>", markup)
                elif payload == "ADM_BN_ALL":
                    user["state"] = "adm_bn_all"
                    edit_telegram_message(sid, user["main_menu_id"], "💬 <b>GỬI TẤT CẢ KHÁCH</b>\nCú pháp: <code>Thời_gian Nội_dung</code>")
                elif payload == "ADM_BN_PRIV":
                    user["state"] = "adm_bn_priv"
                    edit_telegram_message(sid, user["main_menu_id"], "👤 <b>GỬI TIN RIÊNG</b>\nCú pháp: <code>@user Thời_gian Nội_dung</code>")
                elif payload == "ADM_USER":
                    user["state"] = "adm_check_user"
                    edit_telegram_message(sid, user["main_menu_id"], "👤 <b>SOI THÔNG TIN</b>\nNhập <code>@username</code> hoặc <code>ID Telegram</code>:")
                elif payload == "ADM_MANAGE":
                    user["state"] = "adm_manage_input"
                    edit_telegram_message(sid, user["main_menu_id"], "🛠 <b>QUẢN LÝ KEY / USER</b>\n\n📝 Nhập:\n- <b>Mã Key</b> (Sửa/xóa/Gia hạn/Ghim tài khoản)\n- <b>@username</b> (Xóa sạch mọi Key của khách đó)")
                elif payload == "ADM_LOGOUT":
                    user["is_admin"] = False; user["admin_key"] = ""
                    edit_telegram_message(sid, user["main_menu_id"], "👋 Đã đăng xuất Admin thành công!", {"inline_keyboard": [[{"text": "🏠 Về Trang Chủ", "callback_data": "MENU_MAIN"}]]})
                elif payload == "ADM_LOGS":
                    txt = "📜 <b>RADAR LOGS (10 HOẠT ĐỘNG MỚI NHẤT):</b>\n\n"
                    for l in db.get("logs", [])[:10]: txt += f"• {time.strftime('%H:%M', time.localtime(l['time']))} | <b>{l['action']}</b>\n  └ Key: <code>{l['key']}</code> | User: {l.get('olm_name','')}\n"
                    edit_telegram_message(sid, user["main_menu_id"], txt, {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                
                elif payload.startswith("K_RST_"):
                    k = payload.replace("K_RST_", "")
                    if k in db["keys"]:
                        db["keys"][k]["devices"] = []; db["keys"][k]["known_ips"] = []
                        edit_telegram_message(sid, user["main_menu_id"], f"✅ Đã Gỡ sạch TB/IP của Key: <code>{k}</code>", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                elif payload.startswith("K_DEL_"):
                    k = payload.replace("K_DEL_", "")
                    if k in db["keys"]:
                        del db["keys"][k]
                        edit_telegram_message(sid, user["main_menu_id"], f"✅ Đã XÓA Key: <code>{k}</code>", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                elif payload.startswith("K_VIP_"):
                    k = payload.replace("K_VIP_", "")
                    if k in db["keys"]:
                        db["keys"][k]["vip"] = not db["keys"][k].get("vip", False)
                        edit_telegram_message(sid, user["main_menu_id"], f"✅ Đổi VIP Key <code>{k}</code> thành: <b>{db['keys'][k]['vip']}</b>", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                elif payload.startswith("K_BAN_"):
                    k = payload.replace("K_BAN_", "")
                    if k in db["keys"]:
                        db["keys"][k]["status"] = "banned" if db["keys"][k]["status"] == "active" else "active"
                        edit_telegram_message(sid, user["main_menu_id"], f"✅ Đổi trạng thái Key <code>{k}</code> thành: <b>{db['keys'][k]['status']}</b>", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                elif payload.startswith("K_EXT_"):
                    k = payload.replace("K_EXT_", "")
                    user["state"] = f"adm_ext_{k}"
                    edit_telegram_message(sid, user["main_menu_id"], f"⏳ Nhập thời gian muốn gia hạn thêm cho Key <code>{k}</code> (VD: 30d):", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})
                elif payload.startswith("K_BND_"):
                    k = payload.replace("K_BND_", "")
                    user["state"] = f"adm_bnd_{k}"
                    edit_telegram_message(sid, user["main_menu_id"], f"🔐 Nhập <b>Tên Tài Khoản OLM</b> muốn Độc Quyền cho Key <code>{k}</code>:\n(Nhập XOA để gỡ ghim)", {"inline_keyboard": [[{"text": "🔙 Hủy", "callback_data": "ADM_MENU"}]]})

            save_db(db)
            return "ok", 200

        # ======= XỬ LÝ NHẬP VĂN BẢN =======
        if msg_text and user["main_menu_id"]:
            if user["state"] == "wait_loader_pin":
                user["temp_pin"] = msg_text; user["state"] = "wait_loader_key"
                edit_telegram_message(sid, user["main_menu_id"], "🔑 <b>NHẬP KEY KÍCH HOẠT</b>\n\nDán Key VIP/Thường của bạn vào đây:")
                save_db(db); return "ok", 200
                
            elif user["state"] == "wait_loader_key":
                pin = user.get("temp_pin", ""); key = msg_text
                success, res_data = process_key_validation(db, key, "Telegram_Loader", get_real_ip(), "telegram_loader", "any")
                if key in db["keys"] and success:
                    remote_unlocks[pin] = key
                    user["loader_active"] = True; user["loader_key"] = key; user["loader_pin"] = pin; user["state"] = "none"
                    user["live_msg_type"] = "loader"; user["live_msg_id"] = user["main_menu_id"]
                    save_db(db)
                    
                    t_left = format_time_left(db["keys"][key]["exp"], now_ms)
                    txt = f"✅ <b>KẾT NỐI THÀNH CÔNG! Tool sẽ đăng nhập sau 3s.</b>\n\n🟢 <b>ĐANG GIÁM SÁT TOOL</b>\n🔑 Key đang chạy: <code>{key}</code>\n⏳ Thời gian còn lại: <b>{t_left}</b>\n⚡ Trạng thái: Hoạt động bình thường"
                    edit_telegram_message(sid, user["main_menu_id"], txt, {"inline_keyboard": [[{"text": "❌ Ngắt Kết Nối Tool", "callback_data": "LOADER_DISCONNECT"}]]})
                else:
                    user["state"] = "none"; save_db(db)
                    msg_err = res_data.get("message", "Key không tồn tại hoặc sai!")
                    edit_telegram_message(sid, user["main_menu_id"], f"❌ <b>LỖI KẾT NỐI!</b>\n{msg_err}", {"inline_keyboard": [[{"text": "🔗 Thử Lại", "callback_data": "LOADER_MENU"}]]})
                return "ok", 200

            if user["state"].startswith("wait_qty_V_"):
                pkg = user["state"].replace("wait_qty_", "")
                if msg_text.isdigit() and int(msg_text) > 0:
                    qty = int(msg_text)
                    prices = {"V_1H": (7000, 3600000, "1H"), "V_7D": (30000, 604800000, "7D"), "V_30D": (85000, 2592000000, "30D"), "V_1Y": (200000, 31536000000, "1Y")}
                    cost, duration_ms, name = prices[pkg]
                    total_cost = cost * qty
                    if user["balance"] >= total_cost:
                        user["balance"] -= total_cost
                        gen_keys = []
                        for _ in range(qty):
                            nk = f"OLMVIP-{random.randint(1000000, 9999999)}"
                            db["keys"][nk] = {"exp": now_ms + duration_ms, "maxDevices": 1, "devices": [], "known_ips": [], "status": "active", "vip": True, "target": "olm", "bound_olm": ""}
                            user["purchases"].insert(0, {"key": nk, "type": f"VIP {name}", "time": now_ms})
                            add_log(db, "MUA KEY", nk, "Telegram", f"Khách: {safe_name}", "N/A")
                            gen_keys.append(nk)
                        user["state"] = "none"; save_db(db)
                        k_str = "\n\n".join([f"🔑 <code>{k}</code>" for k in gen_keys])
                        edit_telegram_message(sid, user["main_menu_id"], f"🎉 <b>THANH TOÁN THÀNH CÔNG!</b>\nBạn đã mua {qty} Key VIP {name}.\n\n{k_str}\n\n💸 Đã trừ: <b>{total_cost}đ</b>\n💳 Số dư: <b>{user['balance']}đ</b>", {"inline_keyboard": [[{"text": "🏠 Về Trang Chủ", "callback_data": "MENU_MAIN"}]]})
                    else:
                        user["state"] = "none"; save_db(db)
                        edit_telegram_message(sid, user["main_menu_id"], f"❌ <b>SỐ DƯ KHÔNG ĐỦ!</b>\nCần {total_cost}đ. Bạn có {user['balance']}đ.", {"inline_keyboard": [[{"text": "🔙 Về Trang Chủ", "callback_data": "MENU_MAIN"}]]})
                return "ok", 200

            if user["state"] == "wait_reset_key":
                if msg_text in db["keys"]:
                    db["keys"][msg_text]["devices"] = []; db["keys"][msg_text]["known_ips"] = []
                    user["resets"] -= 1; user["state"] = "none"; save_db(db)
                    edit_telegram_message(sid, user["main_menu_id"], f"✅ <b>Reset thành công!</b>\nKey <code>{msg_text}</code> đã được gỡ sạch.", {"inline_keyboard": [[{"text": "🏠 Về Trang Chủ", "callback_data": "MENU_MAIN"}]]})
                else: 
                    edit_telegram_message(sid, user["main_menu_id"], "❌ Key không tồn tại!", {"inline_keyboard": [[{"text": "🔙 Menu", "callback_data": "MENU_MAIN"}]]})
                return "ok", 200

            if user["state"] == "wait_admin_key":
                success, _ = process_key_validation(db, msg_text, sid, "TELEGRAM", "admin_bot", "any")
                if success:
                    user["is_admin"] = True; user["admin_key"] = msg_text; user["state"] = "none"; save_db(db)
                    edit_telegram_message(sid, user["main_menu_id"], "✅ <b>XÁC THỰC THÀNH CÔNG!</b> Bấm nút dưới để vào Admin.", {"inline_keyboard": [[{"text": "👑 Vào Bảng Admin", "callback_data": "ADM_MENU"}]]})
                else: 
                    edit_telegram_message(sid, user["main_menu_id"], "❌ Key Admin sai hoặc đã hết hạn!", {"inline_keyboard": [[{"text": "🏠 Về Menu Khách", "callback_data": "MENU_MAIN"}]]})
                return "ok", 200

            if user.get("is_admin") and user["state"].startswith("adm_"):
                try:
                    parts = msg_text.split()
                    if user["state"] == "adm_create":
                        sys_t, dur_str, devs = parts[0].upper(), parts[1], int(parts[2])
                        dur = parse_duration(dur_str)
                        nk = f"{sys_t}-{random.randint(1000,9999)}"
                        db["keys"][nk] = {"exp": "pending", "maxDevices": devs, "devices": [], "known_ips": [], "status": "active", "vip": True, "target": sys_t.lower(), "durationMs": dur, "bound_olm": ""}
                        edit_telegram_message(sid, user["main_menu_id"], f"✅ Đã tạo Key mới:\n<code>{nk}</code>", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                    
                    elif user["state"] == "adm_bal":
                        t_user, amt_str, rst = parts[0], parts[1], int(parts[2])
                        amt = int(amt_str.lower().replace("k", "000")) 
                        t_id = get_user_id_by_username(db, t_user) if t_user.startswith('@') else t_user
                        if t_id and t_id in db["bot_users"]:
                            db["bot_users"][t_id]["balance"] += amt; db["bot_users"][t_id]["resets"] += rst
                            edit_telegram_message(sid, user["main_menu_id"], f"✅ Đã nạp <b>{amt}đ</b> và <b>{rst}</b> reset cho {t_user}", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                            send_telegram_message(t_id, f"🎉 <b>Admin vừa nạp tiền!</b>\n💰 +{amt}đ | 🔄 +{rst} reset.")
                        else: edit_telegram_message(sid, user["main_menu_id"], "❌ Không tìm thấy User!", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})

                    elif user["state"] == "adm_lock":
                        dur_str, target = parts[0], parts[1]; dur = parse_duration(dur_str)
                        db["locked_olm"][target] = "permanent" if dur == 'permanent' else int(time.time()*1000) + dur
                        edit_telegram_message(sid, user["main_menu_id"], f"✅ Đã Khóa OLM: <b>{target}</b> ({dur_str})", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})

                    elif user["state"] == "adm_ban":
                        dur_str, target = parts[0], parts[1]; dur = parse_duration(dur_str)
                        db["banned_ips"][target] = "permanent" if dur == 'permanent' else int(time.time()*1000) + dur
                        edit_telegram_message(sid, user["main_menu_id"], f"✅ Đã Ban IP: <b>{target}</b> ({dur_str})", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})

                    elif user["state"] == "adm_note":
                        dur_str, msg = parts[0], msg_text.split(maxsplit=1)[1]; dur = parse_duration(dur_str)
                        db["global_notice"] = {"msg": msg, "exp": "permanent" if dur == 'permanent' else int(time.time()*1000) + dur}
                        edit_telegram_message(sid, user["main_menu_id"], f"✅ Đã cài TB Lên Tool: {msg}", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                    
                    elif user["state"] == "adm_bn_all":
                        dur_str, msg = parts[0], msg_text.split(maxsplit=1)[1]; dur = parse_duration(dur_str)
                        exp = "permanent" if dur == 'permanent' else int(time.time()*1000) + dur
                        for uid in db["bot_users"]: db["bot_users"][uid]["notices"].append({"msg": msg, "exp": exp}); send_telegram_message(uid, f"🔔 <b>TB TỪ ADMIN:</b>\n{msg}")
                        edit_telegram_message(sid, user["main_menu_id"], f"✅ Đã đẩy Thông Báo cho ALL Khách Hàng.", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                    
                    elif user["state"] == "adm_bn_priv":
                        parts = msg_text.split(maxsplit=2)
                        t_user, dur_str, msg = parts[0], parts[1], parts[2]
                        dur = parse_duration(dur_str)
                        t_id = get_user_id_by_username(db, t_user) if t_user.startswith('@') else t_user
                        if t_id and t_id in db["bot_users"]:
                            exp = "permanent" if dur == 'permanent' else int(time.time()*1000) + dur
                            db["bot_users"][t_id]["notices"].append({"msg": msg, "exp": exp})
                            send_telegram_message(t_id, f"🔔 <b>TB TỪ ADMIN:</b>\n{msg}")
                            edit_telegram_message(sid, user["main_menu_id"], f"✅ Đã gửi TB riêng cho {t_user}.", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                        else: edit_telegram_message(sid, user["main_menu_id"], "❌ Không tìm thấy User!", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})

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
                            edit_telegram_message(sid, user["main_menu_id"], txt, {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                        else: edit_telegram_message(sid, user["main_menu_id"], "❌ Khách không tồn tại!", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})

                    elif user["state"] == "adm_manage_input":
                        k = msg_text
                        if k.startswith('@') or k.isdigit():
                            t_id = get_user_id_by_username(db, k) if k.startswith('@') else k
                            if t_id and t_id in db["bot_users"]:
                                user_keys = [p["key"] for p in db["bot_users"][t_id].get("purchases", [])]
                                c = 0
                                for uk in user_keys:
                                    if uk in db["keys"]: del db["keys"][uk]; c += 1
                                db["bot_users"][t_id]["purchases"] = []
                                edit_telegram_message(sid, user["main_menu_id"], f"✅ Đã xóa sạch <b>{c}</b> Key của {k}.", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                            else: edit_telegram_message(sid, user["main_menu_id"], "❌ Không tìm thấy User!", {"inline_keyboard": [[{"text": "🔙", "callback_data": "ADM_MENU"}]]})
                        elif k in db["keys"]:
                            kd = db["keys"][k]
                            st = "Hoạt động" if kd['status']=='active' else "Bị Khóa"
                            is_vip = "VIP" if kd.get('vip') else "Thường"
                            exp = format_time_left(kd['exp'], now_ms) if kd['exp']!='pending' else 'Chờ kích hoạt'
                            bnd = kd.get('bound_olm', '')
                            bnd_str = f"Chỉ định: <b>{bnd}</b>" if bnd else "Chạy mọi acc"
                            txt = f"🔑 <b>BẢNG ĐIỀU KHIỂN KEY:</b> <code>{k}</code>\n\n📌 Hệ: {kd['target'].upper()} | 💎 {is_vip} | ⚡ {st}\n⏳ Hạn: {exp}\n📱 TB: {len(kd.get('devices',[]))}/{kd['maxDevices']}\n🔐 Khóa Account: {bnd_str}"
                            markup = {"inline_keyboard": [
                                [{"text": "🔄 Gỡ TB", "callback_data": f"K_RST_{k}"}, {"text": "🗑 Xóa", "callback_data": f"K_DEL_{k}"}],
                                [{"text": "🌟 Đổi VIP", "callback_data": f"K_VIP_{k}"}, {"text": "⏳ Gia Hạn", "callback_data": f"K_EXT_{k}"}],
                                [{"text": "🔒 Bật/Tắt Khóa Key", "callback_data": f"K_BAN_{k}"}],
                                [{"text": "🔐 Ghim Độc Quyền OLM", "callback_data": f"K_BND_{k}"}],
                                [{"text": "🔙 Về Menu Admin", "callback_data": "ADM_MENU"}]
                            ]}
                            edit_telegram_message(sid, user["main_menu_id"], txt, markup)
                        else: edit_telegram_message(sid, user["main_menu_id"], "❌ Mã Key sai!", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})

                    elif user["state"].startswith("adm_ext_"):
                        k = user["state"].replace("adm_ext_", "")
                        dur = parse_duration(msg_text)
                        if k in db["keys"]:
                            if db["keys"][k]['exp'] not in ['permanent', 'pending']:
                                db["keys"][k]['exp'] = max(db["keys"][k]['exp'], int(time.time()*1000)) + dur
                                edit_telegram_message(sid, user["main_menu_id"], f"✅ Đã gia hạn Key <code>{k}</code> thêm {msg_text}!", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                    
                    elif user["state"].startswith("adm_bnd_"):
                        k = user["state"].replace("adm_bnd_", "")
                        if k in db["keys"]:
                            if msg_text.upper() == "XOA": db["keys"][k]["bound_olm"] = ""
                            else: db["keys"][k]["bound_olm"] = msg_text.strip()
                            edit_telegram_message(sid, user["main_menu_id"], f"✅ Cập nhật độc quyền OLM cho Key <code>{k}</code> thành công!", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
                
                    save_db(db); user["state"] = "none"; save_db(db)
                except Exception as e: 
                    edit_telegram_message(sid, user["main_menu_id"], f"❌ Lỗi cú pháp! Vui lòng ấn nút để thao tác lại.", {"inline_keyboard": [[{"text": "🔙 Về Admin", "callback_data": "ADM_MENU"}]]})
            return "ok", 200

    except Exception as e: print("Webhook Error:", e)
    return "ok", 200


# ====================== KHÔI PHỤC HOÀN TOÀN WEB RENDER ======================
@app.route('/api/check', methods=['POST', 'OPTIONS'])
def check_key():
    if request.method == 'OPTIONS': return jsonify({}), 200
    data = request.get_json() or {}
    db = load_db()
    pin = data.get('pin')
    if pin and pin in db.get("logout_pins", []):
        db["logout_pins"].remove(pin); save_db(db)
        return jsonify({"status": "error", "message": "Phiên làm việc bị ngắt từ Bot Telegram!"})
    success, res = process_key_validation(db, data.get('key'), data.get('deviceId'), get_real_ip(), data.get('target_app', 'tool'), data.get('expected_type', 'normal'), data.get('device_name'), data.get('olm_name'))
    return jsonify(res)

@app.route('/api/remote_unlock', methods=['POST', 'OPTIONS'])
def remote_unlock():
    if request.method == 'OPTIONS': return jsonify({}), 200 
    data = request.get_json() or {}
    key, pin, deviceId = data.get('key'), data.get('pin'), data.get('deviceId', 'Unknown')
    target_app, expected_type = data.get('target_app', 'tool'), data.get('expected_type', 'normal')
    if not pin: return jsonify({"status": "error", "message": "Thiếu mã PIN!"})
    db = load_db()
    success, response = process_key_validation(db, key, deviceId, get_real_ip(), target_app, expected_type)
    if success:
        remote_unlocks[pin] = key 
        response['message'] = f"ĐÃ KÍCH HOẠT VÀO HỆ THỐNG {target_app.upper()}!"
    return jsonify(response)

@app.route('/api/poll_unlock', methods=['POST'])
def poll_unlock():
    pin = request.json.get('pin')
    if pin in remote_unlocks: return jsonify({"status": "success", "key": remote_unlocks.pop(pin)}) 
    return jsonify({"status": "pending"})

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
    dur, t, md, qty = request.form.get('duration'), request.form.get('type'), int(request.form.get('maxDevices', 1)), int(request.form.get('quantity', 1))
    vip, pfx = request.form.get('is_vip')=='on', request.form.get('prefix', '').strip()
    if not pfx: pfx = "LVT" if target_app == "tool" else ("OLM" if target_app == "olm" else "ADMIN")
    db = load_db()
    for _ in range(qty):
        nk = f"{pfx}-{random.randint(1000000, 9999999)}"
        db["keys"][nk] = {"exp": "permanent" if t == 'permanent' else "pending", "maxDevices": md, "devices": [], "known_ips": [], "status": "active", "vip": vip, "target": target_app, "bound_olm": ""}
        if t != 'permanent': db["keys"][nk]["durationMs"] = int(dur) * multipliers_web.get(t, 86400000)
    save_db(db); return redirect('/')

@app.route('/admin/ban-ip', methods=['POST'])
def ban_ip():
    ip, dur, t = request.form.get('ip').strip(), request.form.get('duration'), request.form.get('type')
    db = load_db()
    db.setdefault("banned_ips", {})[ip] = "permanent" if t == 'permanent' else int(time.time() * 1000) + int(dur) * multipliers_web.get(t, 86400000)
    save_db(db); return redirect('/')

@app.route('/admin/lock_olm', methods=['POST'])
def lock_olm():
    user, dur, t = request.form.get('user').strip(), request.form.get('duration'), request.form.get('type')
    db = load_db()
    db.setdefault("locked_olm", {})[user] = "permanent" if t == 'permanent' else int(time.time() * 1000) + int(dur) * multipliers_web.get(t, 86400000)
    save_db(db); return redirect('/')

@app.route('/admin/unlock_olm/<user>')
def unlock_olm(user):
    db = load_db()
    if user in db.get("locked_olm", {}): del db["locked_olm"][user]
    save_db(db); return redirect('/')

@app.route('/admin/notice', methods=['POST'])
def set_notice():
    msg = request.form.get('message', '').strip()
    dur, t = request.form.get('duration'), request.form.get('type')
    db = load_db()
    exp = "permanent" if t == 'permanent' else int(time.time() * 1000) + int(dur) * multipliers_web.get(t, 1000)
    db["global_notice"] = {"msg": msg, "exp": exp}
    save_db(db); return redirect('/')

@app.route('/admin/delete_all', methods=['POST'])
def delete_all_keys():
    db = load_db()
    db["keys"] = {}
    save_db(db); return redirect('/')

@app.route('/admin/unban-ip/<ip>')
def unban_ip(ip):
    db = load_db()
    if ip in db.get("banned_ips", {}): del db["banned_ips"][ip]
    if ip in db.get("ip_strikes", {}): del db["ip_strikes"][ip]
    save_db(db); return redirect(request.referrer or '/')

@app.route('/admin/extend', methods=['POST'])
def extend_key():
    key, dur, t = request.form.get('key'), request.form.get('duration'), request.form.get('type')
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
    target_id = None
    if target_user.startswith('@'):
        for uid, info in db["bot_users"].items():
            if info.get("username", "").lower() == target_user.lower(): target_id = uid; break
    else: target_id = target_user

    if target_id and target_id in db["bot_users"]:
        db["bot_users"][target_id]["balance"] += amount
        db["bot_users"][target_id]["resets"] += resets
        save_db(db)
        msg = f"🎉 <b>Admin vừa cập nhật tài khoản của bạn!</b>\n"
        if amount > 0: msg += f"💰 Nạp tiền: <b>+{amount}đ</b>\n"
        if resets > 0: msg += f"🔄 Lượt Reset: <b>+{resets} lượt</b>\n"
        msg += f"\n📊 Số dư mới: {db['bot_users'][target_id]['balance']}đ\n🔄 Reset hiện tại: {db['bot_users'][target_id]['resets']}"
        send_telegram_message(target_id, msg, {"inline_keyboard": [[{"text": "Về Menu Chính", "callback_data": "MENU_MAIN"}]]})
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
        elif action == 'reset-dev': db["keys"][key]['devices'] = []; db["keys"][key]['known_ips'] = []
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
    html_rows = ""
    for did, info in active_sessions.items():
        onl_time = time.strftime('%H:%M:%S', time.localtime(info["last_seen"]))
        html_rows += f"<tr><td>{info['ip']}</td><td class='text-warning'>{info['olm_name']}</td><td class='text-info'>{info['key']}</td><td>{did}</td><td>{onl_time}</td><td><a href='/admin/action/ban/{info['key']}' class='btn btn-sm btn-danger'>Khóa Key</a></td></tr>"
    return f'''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Giám Sát Online - LVT</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>body{{background:#0a0a12;color:white;}}</style></head><body class="p-4"><div class="container"><div class="d-flex justify-content-between mb-4"><h2>📡 RADAR GIÁM SÁT OLM ONLINE</h2><a href="/" class="btn btn-secondary">Quay lại Dashboard</a></div><div class="card bg-dark p-3"><table class="table table-dark table-hover"><thead><tr><th>IP Máy</th><th>Tên OLM</th><th>Key Đang Dùng</th><th>Mã TB</th><th>Tín Hiệu Cuối</th><th>Thao Tác</th></tr></thead><tbody>{html_rows if html_rows else "<tr><td colspan='6' class='text-center text-muted'>Hiện không có ai đang làm OLM.</td></tr>"}</tbody></table></div></div><script>setInterval(() => location.reload(), 10000);</script></body></html>'''

@app.route('/')
def dashboard():
    db = load_db()
    keys_html = ''
    for k, data in db["keys"].items():
        is_banned, is_vip, sys_target = data.get('status') == 'banned', data.get('vip', False), data.get('target', 'tool')
        status_badge = '<span class="badge bg-danger">BANNED</span>' if is_banned else ('<span class="badge bg-warning text-dark">VIP</span>' if is_vip else '<span class="badge bg-success">THƯỜNG</span>')
        
        if sys_target == 'tool': sys_badge = '<span class="badge bg-info">LVT Tool</span>'
        elif sys_target == 'admin_bot': sys_badge = '<span class="badge bg-dark border border-light">🤖 ADMIN BOT</span>'
        else: sys_badge = '<span class="badge bg-danger">OLM</span>'

        current_time, is_expired = int(time.time() * 1000), False
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
        if "THOÁT OLM" in log['action']: color = "secondary"
        elif "TRUY CẬP OLM" in log['action']: color = "info"
        elif "THÀNH CÔNG" in log['action']: color = "success"
        elif "ADMIN BOT" in log['action']: color = "dark border border-light"
        elif "LOADER" in log['action']: color = "primary"
        elif "BANNED" in log['action'] or "BỊ CHẶN" in log['action'] or "SAI" in log['action'] or "GIỚI HẠN" in log['action']: color = "danger"
        else: color = "warning"
        logs_html += f'<tr><td><small class="text-muted">{time.strftime("%H:%M:%S %d/%m", time.localtime(log["time"]))}</small></td><td><span class="badge bg-{color}">{log["action"]}</span></td><td class="text-info">{log["key"]}</td><td><span class="badge bg-secondary">{log["ip"]}</span><br><small class="text-muted">{log.get("olm_name","")}</small><br><small style="font-size:10px;">{log.get("device","")}</small></td></tr>'

    users_html = ''
    for uid, udata in db.get("bot_users", {}).items():
        uname = udata.get("username", "")
        uname_html = f'<span class="text-warning">{uname}</span>' if uname else ''
        users_html += f'<tr><td><strong class="text-info">{udata["name"]}</strong> {uname_html}<br><small class="text-muted">{uid}</small></td><td><span class="badge bg-success">{udata["balance"]}đ</span></td><td>{udata["resets"]} lần</td></tr>'

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
