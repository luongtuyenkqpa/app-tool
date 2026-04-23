import os
import json
import time
import random
import secrets
import hashlib
import threading
import sys
import requests
from flask import Flask, request, jsonify, redirect, make_response

# --- ANTI-BUG / ANTI-TAMPER (TỰ SẬP KHI SỬA CODE SAU KHI CHẠY) ---
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
# ----------------------------------------------------------------

app = Flask(__name__)
DB_FILE = './database.json'
ADMIN_PASSWORD = 'admin120510'

# ========================================================
# CẤU HÌNH BOT TELEGRAM
# ========================================================
TELEGRAM_BOT_TOKEN = "8621133442:AAEimlzP2LKIfWOLE18iQGoUUHS7pyXmDuw"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
# ========================================================

remote_unlocks = {}
logout_pins = set()
multipliers = {'sec': 1000, 'min': 60000, 'hour': 3600000, 'day': 86400000, 'month': 2592000000, 'year': 31536000000}

active_sessions = {} 

def session_monitor():
    while True:
        time.sleep(5)
        now = time.time()
        to_remove = []
        for did, info in active_sessions.items():
            if now - info['last_seen'] > 35:
                to_remove.append(did)
        
        for did in to_remove:
            info = active_sessions.pop(did)
            db = load_db()
            add_log(db, "THOÁT OLM", info['key'], info['ip'], f"Device ({did})", info['olm_name'])
            save_db(db)

threading.Thread(target=session_monitor, daemon=True).start()

@app.after_request
def add_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

def load_db():
    if not os.path.exists(DB_FILE): 
        return {"keys": {}, "logs": [], "banned_ips": {}, "logout_pins": [], "global_notice": {}, "locked_olm": {}, "ip_strikes": {}, "bot_users": {}}
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            data.setdefault("keys", {})
            data.setdefault("logs", [])
            data.setdefault("banned_ips", {})
            data.setdefault("logout_pins", [])
            data.setdefault("locked_olm", {})
            data.setdefault("ip_strikes", {})
            data.setdefault("bot_users", {})
            if not isinstance(data.get("global_notice"), dict):
                data["global_notice"] = {"msg": str(data.get("global_notice", "")), "exp": "permanent"}
            return data
        except: 
            return {"keys": {}, "logs": [], "banned_ips": {}, "logout_pins": [], "global_notice": {}, "locked_olm": {}, "ip_strikes": {}, "bot_users": {}}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f: 
        json.dump(db, f, indent=2, ensure_ascii=False)

def add_log(db, action, key, ip, device, olm_name="N/A"):
    db.setdefault("logs", []).insert(0, {
        "time": int(time.time()), 
        "action": action, 
        "key": key, 
        "ip": ip, 
        "device": device,
        "olm_name": olm_name
    })
    db["logs"] = db["logs"][:300] 

def get_real_ip():
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
    return request.remote_addr

@app.before_request
def check_auth():
    if request.path in ['/login', '/api/check', '/api/remote_unlock', '/api/poll_unlock', '/api/trigger_logout', '/webhook'] or request.path.startswith('/static'): return
    if request.method == 'OPTIONS': return 
    if request.cookies.get('admin_auth') != 'true': return redirect('/login')

def process_key_validation(key, deviceId, real_ip, target_app, expected_type, device_name="Unknown", olm_name="N/A"):
    db = load_db()
    current_time = int(time.time() * 1000)

    if real_ip in db.get("banned_ips", {}):
        ban_exp = db["banned_ips"][real_ip]
        if ban_exp == 'permanent' or current_time < ban_exp:
            add_log(db, "BỊ CHẶN IP", key or "N/A", real_ip, f"{device_name} ({deviceId})", olm_name)
            save_db(db)
            return False, {"status": "error", "message": "IP của bạn đã bị khóa hệ thống!"}
        else: 
            del db["banned_ips"][real_ip]

    if olm_name != "N/A" and olm_name in db.get("locked_olm", {}):
        olm_exp = db["locked_olm"][olm_name]
        if olm_exp == 'permanent' or current_time < olm_exp:
            add_log(db, "OLM BỊ KHÓA", key or "N/A", real_ip, f"{device_name} ({deviceId})", olm_name)
            save_db(db)
            return False, {"status": "error", "message": f"Tài khoản OLM '{olm_name}' đang bị khóa hệ thống!", "is_locked_olm": True, "lock_exp": olm_exp}
        else:
            del db["locked_olm"][olm_name]

    if not key or key not in db["keys"]:
        add_log(db, "SAI KEY", key or "Trống", real_ip, f"{device_name} ({deviceId})", olm_name)
        save_db(db)
        return False, {"status": "error", "message": "Key không tồn tại!"}

    keyData = db["keys"][key]
    
    actual_target = keyData.get('target', 'tool')
    if actual_target != target_app:
        add_log(db, "SAI HỆ THỐNG", key, real_ip, f"{device_name} ({deviceId})", olm_name)
        save_db(db)
        sys_name = "LVT Tool" if actual_target == "tool" else ("OLM" if actual_target == "olm" else "Admin Bot")
        return False, {"status": "error", "message": f"LỖI: Key này là của hệ thống {sys_name}!"}

    is_key_vip = keyData.get('vip', False)
    is_expect_vip = (expected_type == 'vip')
    if is_expect_vip and not is_key_vip:
        return False, {"status": "error", "message": "Bạn đang dùng Key THƯỜNG. Hãy gạt công tắc sang 'Key Thường'!"}
    if not is_expect_vip and is_key_vip and expected_type != 'any':
        return False, {"status": "error", "message": "Bạn đang dùng Key VIP. Hãy gạt công tắc sang 'Key VIP'!"}

    if keyData.get('status') == 'banned':
        add_log(db, "KEY BỊ BANNED", key, real_ip, f"{device_name} ({deviceId})", olm_name)
        save_db(db)
        return False, {"status": "error", "message": "Key này đã bị khóa!"}

    if keyData.get('exp') == 'pending': 
        keyData['exp'] = current_time + keyData.get('durationMs', 0)
    
    if keyData.get('exp') != 'permanent' and current_time > keyData.get('exp', 0):
        add_log(db, "KEY HẾT HẠN", key, real_ip, f"{device_name} ({deviceId})", olm_name)
        save_db(db)
        return False, {"status": "error", "message": "Key đã hết hạn!"}

    known_ips = keyData.setdefault('known_ips', [])
    if real_ip not in known_ips and target_app != "admin_bot": # Admin bot bypasses strict IP ban
        if len(known_ips) >= keyData.get('maxDevices', 1):
            strikes = db.setdefault("ip_strikes", {})
            strike_info = strikes.get(real_ip, {"count": 0, "banned_until": 0})
            
            strike_info["count"] += 1
            c = strike_info["count"]
            
            if c <= 3:
                msg = f"CẢNH BÁO ({c}/3): Phát hiện chia sẻ Key! Vui lòng dừng lại nếu không sẽ bị BAN IP."
                strikes[real_ip] = strike_info; save_db(db)
                return False, {"status": "error", "message": msg}
            elif c == 4:
                strike_info["banned_until"] = current_time + 3600000 
                db["banned_ips"][real_ip] = strike_info["banned_until"]
            elif c == 5:
                strike_info["banned_until"] = current_time + 86400000 
                db["banned_ips"][real_ip] = strike_info["banned_until"]
            elif c == 6:
                strike_info["banned_until"] = current_time + 604800000 
                db["banned_ips"][real_ip] = strike_info["banned_until"]
            else:
                strike_info["banned_until"] = 'permanent'
                db["banned_ips"][real_ip] = 'permanent'
                
            strikes[real_ip] = strike_info; save_db(db)
            return False, {"status": "error", "message": "IP đã bị BAN do vi phạm chia sẻ Key!"}
        else:
            known_ips.append(real_ip)

    if deviceId not in keyData.get('devices', []):
        if len(keyData.get('devices', [])) >= keyData.get('maxDevices', 1):
            add_log(db, "QUÁ GIỚI HẠN TB", key, real_ip, f"{device_name} ({deviceId})", olm_name)
            save_db(db)
            return False, {"status": "error", "message": "Key đã đầy thiết bị!"}
        keyData.setdefault('devices', []).append(deviceId)

    if target_app == "olm":
        if deviceId not in active_sessions:
            add_log(db, "TRUY CẬP OLM", key, real_ip, f"{device_name} ({deviceId})", olm_name)
            save_db(db)
        active_sessions[deviceId] = {
            "ip": real_ip, "olm_name": olm_name, "key": key, "last_seen": time.time()
        }
    elif target_app == "admin_bot":
        add_log(db, "ADMIN BOT ĐĂNG NHẬP", key, real_ip, f"Telegram ({deviceId})", "N/A")
        save_db(db)
    else:
        add_log(db, "THÀNH CÔNG", key, real_ip, f"{device_name} ({deviceId})", olm_name)
        save_db(db)

    notice_data = db.get("global_notice", {})
    notice_msg = ""
    notice_exp = "permanent"
    
    if isinstance(notice_data, dict) and notice_data.get("msg"):
        if notice_data.get("exp") == "permanent" or current_time < notice_data.get("exp", 0):
            notice_msg = notice_data["msg"]
            notice_exp = notice_data["exp"]
        else:
            db["global_notice"] = {"msg": "", "exp": "permanent"}
            save_db(db)

    return True, {
        "status": "success", 
        "message": "Xác thực thành công!", 
        "exp": keyData.get('exp'), 
        "vip": is_key_vip, 
        "devices": f"{len(keyData.get('devices', []))}/{keyData.get('maxDevices', 1)}",
        "notice": notice_msg,
        "notice_exp": notice_exp 
    }


# ====================================================================
# TÍCH HỢP TELEGRAM BOT & ADMIN PANEL COMMANDS (THÊM LOGS HISTORY)
# ====================================================================
def send_telegram_message(chat_id, text, reply_markup=None):
    if not TELEGRAM_BOT_TOKEN: return
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: payload["reply_markup"] = reply_markup
    try: requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload)
    except: pass

@app.route('/webhook', methods=['GET', 'POST'])
def telegram_webhook():
    if request.method == 'GET': return "Webhook OK", 200

    data = request.json
    if not data: return "ok", 200
    
    chat_id = None; msg_text = ""; payload_data = ""; user_name = "Khách hàng"; tg_username = ""
    
    if "message" in data and "text" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        msg_text = data["message"]["text"].strip()
        user_name = data["message"]["from"].get("first_name", "Khách")
        tg_username = data["message"]["from"].get("username", "")
    elif "callback_query" in data:
        chat_id = data["callback_query"]["message"]["chat"]["id"]
        payload_data = data["callback_query"]["data"]
        user_name = data["callback_query"]["from"].get("first_name", "Khách")
        tg_username = data["callback_query"]["from"].get("username", "")
        requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": data["callback_query"]["id"]})

    if not chat_id: return "ok", 200

    db = load_db()
    sender_id = str(chat_id)
    safe_name = user_name.replace("<", "").replace(">", "").replace("&", "")
    formatted_username = f"@{tg_username}" if tg_username else ""
    
    if sender_id not in db["bot_users"]:
        db["bot_users"][sender_id] = {"name": safe_name, "username": formatted_username, "balance": 0, "resets": 3, "state": "none", "is_admin": False, "admin_key": ""}
        save_db(db)
    else:
        if db["bot_users"][sender_id].get("username") != formatted_username:
            db["bot_users"][sender_id]["username"] = formatted_username
            save_db(db)
    
    user = db["bot_users"][sender_id]
    
    # BẢO VỆ PHÂN QUYỀN ADMIN - Kiểm tra Key Admin ngầm
    if user.get("is_admin"):
        adm_key = user.get("admin_key", "")
        success, _ = process_key_validation(adm_key, sender_id, "TELEGRAM", "admin_bot", "any")
        if not success:
            user["is_admin"] = False
            user["admin_key"] = ""
            user["state"] = "none"
            save_db(db)
            send_telegram_message(chat_id, "⚠️ <b>Hệ thống:</b> Key Admin của bạn đã hết hạn hoặc bị khóa. Quyền Admin đã bị tước!")

    # ================== KHU VỰC LỆNH ADMIN ==================
    if msg_text.upper() == "/ADMIN" or (payload_data == "ADM_MAIN_MENU" and user.get("is_admin")):
        if user.get("is_admin"):
            user["state"] = "none"; save_db(db)
            markup = {"inline_keyboard": [
                [{"text": "➕ Tạo Key Nhanh", "callback_data": "ADM_CREATE"}, {"text": "💰 Nạp Tiền/Reset", "callback_data": "ADM_BAL"}],
                [{"text": "🔒 Khóa OLM", "callback_data": "ADM_LOCKOLM"}, {"text": "🚫 Ban IP", "callback_data": "ADM_BANIP"}],
                [{"text": "📢 Phát Thông Báo", "callback_data": "ADM_NOTICE"}, {"text": "🛠 Quản Lý Key", "callback_data": "ADM_MANAGE"}],
                [{"text": "📜 Xem Lịch Sử Logs & OLM Bị Khóa", "callback_data": "ADM_LOGS"}],
                [{"text": "❌ Đăng Xuất Admin", "callback_data": "ADM_LOGOUT"}]
            ]}
            send_telegram_message(chat_id, "👑 <b>BẢNG ĐIỀU KHIỂN SERVER (ADMIN)</b>\nBạn đang nắm toàn quyền kiểm soát hệ thống:", markup)
        else:
            user["state"] = "waiting_admin_key"; save_db(db)
            send_telegram_message(chat_id, "🔐 <b>Xác Thực Admin:</b>\nVui lòng nhập <code>Key Admin</code> để tiếp tục:")
        return "ok", 200

    if user["state"] == "waiting_admin_key":
        if msg_text:
            success, res = process_key_validation(msg_text, sender_id, "TELEGRAM", "admin_bot", "any")
            if success:
                user["is_admin"] = True
                user["admin_key"] = msg_text
                user["state"] = "none"
                save_db(db)
                send_telegram_message(chat_id, "✅ <b>ĐĂNG NHẬP ADMIN THÀNH CÔNG!</b>\nGõ lại /admin để mở Bảng Điều Khiển.")
            else:
                user["state"] = "none"; save_db(db)
                send_telegram_message(chat_id, f"❌ <b>Từ chối truy cập:</b> {res['message']}")
        return "ok", 200

    # Các nút bấm Admin Panel
    if user.get("is_admin"):
        if payload_data == "ADM_CREATE":
            user["state"] = "adm_w_create"; save_db(db)
            send_telegram_message(chat_id, "➕ <b>TẠO KEY NHANH</b>\nNhắn theo cú pháp:\n<code>Loại Ngày MaxTB</code>\n(Loại: OLM hoặc LVT)\n\n<i>Ví dụ tạo key OLM 30 ngày cho 1 máy:</i>\n<code>OLM 30 1</code>\n(Nhắn /cancel để hủy)")
            return "ok", 200
        elif payload_data == "ADM_BAL":
            user["state"] = "adm_w_bal"; save_db(db)
            send_telegram_message(chat_id, "💰 <b>NẠP TIỀN / LƯỢT RESET</b>\nNhắn theo cú pháp:\n<code>@user Tiền Lượt_Reset</code>\n\n<i>Ví dụ nạp 50k và 2 reset cho @lvt_vip:</i>\n<code>@lvt_vip 50000 2</code>\n(Nhắn /cancel để hủy)")
            return "ok", 200
        elif payload_data == "ADM_LOCKOLM":
            user["state"] = "adm_w_lockolm"; save_db(db)
            send_telegram_message(chat_id, "🔒 <b>KHÓA TÊN OLM</b>\nNhắn chính xác tên OLM cần khóa vĩnh viễn.\n<i>Ví dụ:</i> <code>hp_luongvantuyen</code>\n(Nhắn /cancel để hủy)")
            return "ok", 200
        elif payload_data == "ADM_BANIP":
            user["state"] = "adm_w_banip"; save_db(db)
            send_telegram_message(chat_id, "🚫 <b>BAN IP</b>\nNhắn chính xác IP cần chặn vĩnh viễn.\n<i>Ví dụ:</i> <code>1.1.1.1</code>\n(Nhắn /cancel để hủy)")
            return "ok", 200
        elif payload_data == "ADM_NOTICE":
            user["state"] = "adm_w_notice"; save_db(db)
            send_telegram_message(chat_id, "📢 <b>PHÁT LOA (10 PHÚT)</b>\nNhập nội dung muốn thông báo lên màn hình người dùng:\n(Nhắn /cancel để hủy)")
            return "ok", 200
        elif payload_data == "ADM_MANAGE":
            user["state"] = "adm_w_manage"; save_db(db)
            send_telegram_message(chat_id, "🛠 <b>QUẢN LÝ KEY</b>\nNhắn theo các cú pháp sau:\n1. <code>XOA Key</code> (Xóa vĩnh viễn)\n2. <code>RESET Key</code> (Gỡ mọi thiết bị/IP)\n3. <code>VIP Key</code> (Bật/Tắt VIP)\n4. <code>GIAHAN Key Ngày</code> (Cộng ngày)\n(Nhắn /cancel để hủy)")
            return "ok", 200
        elif payload_data == "ADM_LOGS":
            # --- CHỨC NĂNG XEM LOGS MỚI ---
            user["state"] = "none"; save_db(db)
            logs = db.get("logs", [])[:10] # Lấy 10 log mới nhất cho gọn
            log_msg = "📜 <b>LỊCH SỬ LOGS (10 mục gần nhất):</b>\n\n"
            for log in logs:
                t = time.strftime("%H:%M %d/%m", time.localtime(log["time"]))
                log_msg += f"🔹 <b>{t}</b> | {log['action']}\nKey: <code>{log['key']}</code> | IP: <code>{log['ip']}</code>\nTB: {log.get('device','N/A')} | OLM: {log.get('olm_name','N/A')}\n\n"
            if not logs: log_msg += "<i>Chưa có dữ liệu.</i>\n\n"
            
            olms = db.get("locked_olm", {})
            log_msg += "🔒 <b>TÊN OLM ĐANG BỊ KHÓA:</b>\n"
            if olms:
                for u in olms: log_msg += f"- <code>{u}</code>\n"
            else: log_msg += "- <i>Chưa có tài khoản nào bị khóa.</i>\n"
            
            markup = {"inline_keyboard": [[{"text": "🔙 Về Bảng Điều Khiển Admin", "callback_data": "ADM_MAIN_MENU"}]]}
            send_telegram_message(chat_id, log_msg, markup)
            return "ok", 200
            
        elif payload_data == "ADM_LOGOUT":
            user["is_admin"] = False; user["admin_key"] = ""; user["state"] = "none"; save_db(db)
            send_telegram_message(chat_id, "✅ Đã đăng xuất Admin an toàn.")
            return "ok", 200

    # Xử lý text nhập vào khi ở trạng thái Admin
    if user.get("is_admin") and user["state"].startswith("adm_w_"):
        if msg_text.upper() == "/CANCEL":
            user["state"] = "none"; save_db(db)
            send_telegram_message(chat_id, "Đã hủy thao tác. Gõ /admin để mở Menu.")
            return "ok", 200
            
        try:
            if user["state"] == "adm_w_create":
                parts = msg_text.split()
                if len(parts) == 3:
                    sys_type, days, devs = parts[0].upper(), int(parts[1]), int(parts[2])
                    nk = f"{sys_type}-{random.randint(1000000, 9999999)}"
                    db["keys"][nk] = {"exp": "pending", "maxDevices": devs, "devices": [], "known_ips": [], "status": "active", "vip": True, "target": sys_type.lower(), "durationMs": days * 86400000}
                    save_db(db)
                    send_telegram_message(chat_id, f"✅ Đã tạo thành công:\n<code>{nk}</code>\nHệ: {sys_type} VIP | {days} Ngày | {devs} Thiết bị")
                else: send_telegram_message(chat_id, "❌ Sai cú pháp!")
            
            elif user["state"] == "adm_w_bal":
                parts = msg_text.split()
                if len(parts) == 3:
                    t_user, amt, rst = parts[0], int(parts[1]), int(parts[2])
                    t_id = None
                    if t_user.startswith('@'):
                        for uid, info in db["bot_users"].items():
                            if info.get("username", "").lower() == t_user.lower(): t_id = uid; break
                    else: t_id = t_user

                    if t_id and t_id in db["bot_users"]:
                        db["bot_users"][t_id]["balance"] += amt
                        db["bot_users"][t_id]["resets"] += rst
                        save_db(db)
                        send_telegram_message(chat_id, f"✅ Đã cộng {amt}đ và {rst} reset cho {t_user}.")
                        send_telegram_message(t_id, f"🎉 <b>Admin vừa nạp tiền!</b>\n💰 +{amt}đ | 🔄 +{rst} reset.\nSố dư mới: {db['bot_users'][t_id]['balance']}đ")
                    else: send_telegram_message(chat_id, "❌ Không tìm thấy user này trong Bot!")
                else: send_telegram_message(chat_id, "❌ Sai cú pháp!")

            elif user["state"] == "adm_w_lockolm":
                db.setdefault("locked_olm", {})[msg_text] = "permanent"
                save_db(db); send_telegram_message(chat_id, f"✅ Đã KHÓA vĩnh viễn OLM: {msg_text}")

            elif user["state"] == "adm_w_banip":
                db.setdefault("banned_ips", {})[msg_text] = "permanent"
                save_db(db); send_telegram_message(chat_id, f"✅ Đã BAN IP: {msg_text}")

            elif user["state"] == "adm_w_notice":
                db["global_notice"] = {"msg": msg_text, "exp": int(time.time() * 1000) + 600000} # 10 phút
                save_db(db); send_telegram_message(chat_id, f"✅ Đã phát loa (10 phút):\n{msg_text}")

            elif user["state"] == "adm_w_manage":
                parts = msg_text.split()
                action = parts[0].upper()
                k = parts[1] if len(parts) > 1 else ""
                if k in db["keys"]:
                    if action == "XOA":
                        del db["keys"][k]; send_telegram_message(chat_id, f"✅ Đã xóa Key: {k}")
                    elif action == "RESET":
                        db["keys"][k]["devices"] = []; db["keys"][k]["known_ips"] = []
                        send_telegram_message(chat_id, f"✅ Đã gỡ mọi thiết bị/IP của Key: {k}")
                    elif action == "VIP":
                        db["keys"][k]["vip"] = not db["keys"][k].get("vip", False)
                        send_telegram_message(chat_id, f"✅ Chế độ VIP của Key {k} hiện tại là: {db['keys'][k]['vip']}")
                    elif action == "GIAHAN" and len(parts) == 3:
                        days = int(parts[2])
                        if db["keys"][k]['exp'] not in ['permanent', 'pending']:
                            db["keys"][k]['exp'] = max(db["keys"][k]['exp'], int(time.time()*1000)) + (days * 86400000)
                            send_telegram_message(chat_id, f"✅ Đã cộng thêm {days} ngày cho Key {k}")
                    save_db(db)
                else: send_telegram_message(chat_id, "❌ Không tìm thấy Key!")
        except:
            send_telegram_message(chat_id, "❌ Lỗi cú pháp! Gõ /admin để mở lại Menu.")
        
        user["state"] = "none"; save_db(db)
        return "ok", 200
    # ================== KẾT THÚC KHU VỰC ADMIN ==================


    # --- XỬ LÝ NHẬP KEY ĐỂ RESET CHO KHÁCH BÌNH THƯỜNG ---
    if user["state"] == "waiting_for_reset_key":
        if payload_data == "MENU_MAIN" or msg_text.upper() == "/CANCEL":
            user["state"] = "none"; save_db(db)
            cmd = "MENU_MAIN"
        elif msg_text:
            key_to_reset = msg_text
            if key_to_reset in db["keys"]:
                db["keys"][key_to_reset]["devices"] = []
                db["keys"][key_to_reset]["known_ips"] = []
                user["resets"] -= 1
                user["state"] = "none"
                save_db(db)
                markup = {"inline_keyboard": [[{"text": "🔙 Quay lại Menu", "callback_data": "MENU_MAIN"}]]}
                send_telegram_message(chat_id, f"✅ <b>Reset thành công Key:</b>\n<code>{key_to_reset}</code>\n\nTất cả thiết bị và IP đã được xóa sạch!", markup)
            else:
                markup = {"inline_keyboard": [[{"text": "🔙 Hủy Reset", "callback_data": "MENU_MAIN"}]]}
                send_telegram_message(chat_id, "❌ Key không tồn tại! Vui lòng kiểm tra lại hoặc bấm Hủy.", markup)
            return "ok", 200

    cmd = payload_data if payload_data else (msg_text.upper() if msg_text else "MENU_MAIN")
    
    if cmd in ["MENU_MAIN", "/START", "HI", "CHÀO"]:
        uname_str = f" ({formatted_username})" if formatted_username else ""
        txt = f"👋 Chào <b>{safe_name}</b>{uname_str}!\n🆔 ID của bạn: <code>{sender_id}</code>\n💰 Số dư: <b>{user['balance']}đ</b>\n🔄 Reset Key còn lại: <b>{user['resets']}/3</b>\n\nVui lòng chọn dịch vụ:"
        markup = {"inline_keyboard": [
            [{"text": "🔑 Mua Key", "callback_data": "MENU_BUY"}, {"text": "🔄 Reset Key", "callback_data": "MENU_RESET"}]
        ]}
        send_telegram_message(chat_id, txt, markup)
    
    elif cmd == "MENU_BUY":
        markup = {"inline_keyboard": [
            [{"text": "👑 Key VIP", "callback_data": "BUY_VIP"}, {"text": "👤 Key Thường", "callback_data": "BUY_NORMAL"}],
            [{"text": "🔙 Quay lại", "callback_data": "MENU_MAIN"}]
        ]}
        send_telegram_message(chat_id, "Bạn muốn mua loại Key nào?", markup)
    
    elif cmd == "BUY_NORMAL":
        markup = {"inline_keyboard": [[{"text": "🔙 Menu Chính", "callback_data": "MENU_MAIN"}]]}
        send_telegram_message(chat_id, "🛠 <b>Tính năng Mua Key Thường hiện đang bảo trì.</b>\n\nVui lòng quay lại sau hoặc dùng Key VIP nhé!", markup)
    
    elif cmd == "BUY_VIP":
        txt = "🛒 <b>BẢNG GIÁ KEY VIP OLM:</b>\n- 1 Giờ: 7,000đ\n- 7 Ngày: 30,000đ\n- 30 Ngày: 85,000đ\n- 1 Năm: 200,000đ\n\n<i>Chọn gói muốn mua:</i>"
        markup = {"inline_keyboard": [
            [{"text": "🕒 1 Giờ (7k)", "callback_data": "VIP_1H"}, {"text": "📅 7 Ngày (30k)", "callback_data": "VIP_7D"}],
            [{"text": "📆 30 Ngày (85k)", "callback_data": "VIP_30D"}, {"text": "🏆 1 Năm (200k)", "callback_data": "VIP_1Y"}],
            [{"text": "🔙 Quay lại", "callback_data": "MENU_BUY"}]
        ]}
        send_telegram_message(chat_id, txt, markup)
        
    elif cmd.startswith("VIP_"):
        prices = {"VIP_1H": (7000, 3600000), "VIP_7D": (30000, 604800000), "VIP_30D": (85000, 2592000000), "VIP_1Y": (200000, 31536000000)}
        if cmd in prices:
            cost, duration_ms = prices[cmd]
            if user["balance"] >= cost:
                user["balance"] -= cost
                nk = f"OLMVIP-{random.randint(1000000, 9999999)}"
                db["keys"][nk] = {"exp": int(time.time()*1000) + duration_ms, "maxDevices": 1, "devices": [], "known_ips": [], "status": "active", "vip": True, "target": "olm"}
                save_db(db)
                markup = {"inline_keyboard": [[{"text": "🔙 Quay lại", "callback_data": "MENU_MAIN"}]]}
                send_telegram_message(chat_id, f"🎉 <b>MUA KEY THÀNH CÔNG!</b>\n\n🔑 Key của bạn: <code>{nk}</code>\n💰 Số dư còn lại: {user['balance']}đ\n\n<i>(Chạm vào Key để copy và dán vào Tool nhé!)</i>", markup)
            else:
                markup = {"inline_keyboard": [[{"text": "🔙 Quay lại Menu", "callback_data": "MENU_MAIN"}]]}
                send_telegram_message(chat_id, f"❌ <b>Số dư không đủ!</b>\nGói này giá {cost}đ nhưng bạn chỉ có {user['balance']}đ.\n\nVui lòng gửi Username: <code>{formatted_username}</code> hoặc ID: <code>{sender_id}</code> cho Admin để nạp tiền.", markup)
    
    elif cmd == "MENU_RESET":
        if user["resets"] <= 0:
            markup = {"inline_keyboard": [[{"text": "🔙 Quay lại Menu", "callback_data": "MENU_MAIN"}]]}
            send_telegram_message(chat_id, "❌ Bạn đã hết lượt Reset miễn phí (0/3).", markup)
        else:
            markup = {"inline_keyboard": [
                [{"text": "Reset Key VIP", "callback_data": "RESET_ACTION"}, {"text": "Reset Key Thường", "callback_data": "RESET_ACTION"}],
                [{"text": "🔙 Quay lại Menu", "callback_data": "MENU_MAIN"}]
            ]}
            send_telegram_message(chat_id, f"Bạn đang còn <b>{user['resets']} lượt Reset</b>. Bạn muốn reset loại Key nào?", markup)
            
    elif cmd == "RESET_ACTION":
        user["state"] = "waiting_for_reset_key"
        save_db(db)
        markup = {"inline_keyboard": [[{"text": "🔙 Hủy bỏ", "callback_data": "MENU_MAIN"}]]}
        send_telegram_message(chat_id, "📝 Vui lòng nhắn chính xác <b>Key</b> bạn muốn Reset vào khung chat:", markup)

    return "ok", 200


@app.route('/api/check', methods=['POST', 'OPTIONS'])
def check_key():
    if request.method == 'OPTIONS': return jsonify({}), 200
    data = request.get_json() or {}
    pin = data.get('pin')
    if pin:
        db = load_db()
        if pin in db.get("logout_pins", []):
            db["logout_pins"].remove(pin); save_db(db)
            return jsonify({"status": "error", "message": "Đã bị đăng xuất từ xa!"})
            
    success, response = process_key_validation(
        data.get('key'), 
        data.get('deviceId', 'Unknown'), 
        get_real_ip(), 
        data.get('target_app', 'tool'), 
        data.get('expected_type', 'normal'),
        data.get('device_name', 'Unknown Device'),
        data.get('olm_name', 'N/A')
    )
    return jsonify(response)

@app.route('/api/remote_unlock', methods=['POST', 'OPTIONS'])
def remote_unlock():
    if request.method == 'OPTIONS': return jsonify({}), 200 
    data = request.get_json() or {}
    key, pin, deviceId = data.get('key'), data.get('pin'), data.get('deviceId', 'Unknown')
    target_app, expected_type = data.get('target_app', 'tool'), data.get('expected_type', 'normal')
    if not pin: return jsonify({"status": "error", "message": "Thiếu mã PIN!"})
    
    success, response = process_key_validation(key, deviceId, get_real_ip(), target_app, expected_type)
    if success:
        remote_unlocks[pin] = key 
        response['message'] = f"ĐÃ KÍCH HOẠT VÀO HỆ THỐNG {target_app.upper()}!"
    return jsonify(response)

@app.route('/api/poll_unlock', methods=['POST'])
def poll_unlock():
    pin = request.json.get('pin')
    if pin in remote_unlocks: return jsonify({"status": "success", "key": remote_unlocks.pop(pin)}) 
    return jsonify({"status": "pending"})

@app.route('/api/trigger_logout', methods=['POST', 'OPTIONS'])
def trigger_logout():
    if request.method == 'OPTIONS': return jsonify({}), 200
    pin = (request.get_json() or {}).get('pin')
    if pin: 
        db = load_db()
        if pin not in db.setdefault("logout_pins", []): db["logout_pins"].append(pin)
        save_db(db)
    return jsonify({"status": "success"})

# ====================== QUẢN TRỊ ADMIN ======================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            resp = make_response(redirect('/'))
            resp.set_cookie('admin_auth', 'true', max_age=86400 * 30)
            return resp
        return f"<html><script>alert('Sai mật khẩu!');window.location.href='/login';</script></html>"
    return render_login_html()

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
        db["keys"][nk] = {"exp": "permanent" if t == 'permanent' else "pending", "maxDevices": md, "devices": [], "known_ips": [], "status": "active", "vip": vip, "target": target_app}
        if t != 'permanent': db["keys"][nk]["durationMs"] = int(dur) * multipliers.get(t, 86400000)
    save_db(db); return redirect('/')

@app.route('/admin/ban-ip', methods=['POST'])
def ban_ip():
    ip, dur, t = request.form.get('ip').strip(), request.form.get('duration'), request.form.get('type')
    db = load_db()
    db.setdefault("banned_ips", {})[ip] = "permanent" if t == 'permanent' else int(time.time() * 1000) + int(dur) * multipliers.get(t, 86400000)
    save_db(db); return redirect('/')

@app.route('/admin/lock_olm', methods=['POST'])
def lock_olm():
    user, dur, t = request.form.get('user').strip(), request.form.get('duration'), request.form.get('type')
    db = load_db()
    db.setdefault("locked_olm", {})[user] = "permanent" if t == 'permanent' else int(time.time() * 1000) + int(dur) * multipliers.get(t, 86400000)
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
    exp = "permanent" if t == 'permanent' else int(time.time() * 1000) + int(dur) * multipliers.get(t, 1000)
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
        db["keys"][key]['exp'] = (db["keys"][key]['exp'] if db["keys"][key]['exp'] > int(time.time() * 1000) else int(time.time() * 1000)) + int(dur) * multipliers.get(t, 86400000)
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
        
        # Nhãn hiệu hệ thống
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
        
        keys_html += f'''
        <tr class="key-row" data-status="{ "banned" if is_banned else ("expired" if is_expired else "active") }">
            <td><div class="d-flex align-items-center"><strong class="me-2 text-info">{k}</strong><button class="btn btn-sm btn-outline-light copy-btn" onclick="copyText('{k}')" title="Sao chép">📋</button></div><div class="mt-1">{status_badge} {sys_badge}</div></td>
            <td>{exp_text}</td><td><span class="badge bg-primary">{len(data.get('devices', []))}/{data.get('maxDevices', 1)}</span></td>
            <td><div class="btn-group btn-group-sm"><button class="btn btn-info" onclick="openExtendModal('{k}')">⏳</button><a href="/admin/action/add-dev/{k}" class="btn btn-success">+</a><a href="/admin/action/sub-dev/{k}" class="btn btn-warning">-</a><a href="/admin/action/reset-dev/{k}" class="btn btn-secondary">🔄</a><a href="/admin/action/{"unban" if is_banned else "ban"}/{k}" class="btn btn-{"light" if is_banned else "danger"}">{"Mở" if is_banned else "Khóa"}</a><a href="/admin/action/toggle_vip/{k}" class="btn btn-warning text-dark">VIP↕</a><a href="/admin/action/delete/{k}" class="btn btn-dark" onclick="return confirm('Xóa?')">🗑️</a></div></td>
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
        elif "BANNED" in log['action'] or "BỊ CHẶN" in log['action'] or "SAI" in log['action'] or "GIỚI HẠN" in log['action']: color = "danger"
        else: color = "warning"
        
        logs_html += f'<tr><td><small class="text-muted">{time.strftime("%H:%M:%S %d/%m", time.localtime(log["time"]))}</small></td><td><span class="badge bg-{color}">{log["action"]}</span></td><td class="text-info">{log["key"]}</td><td><span class="badge bg-secondary">{log["ip"]}</span><br><small class="text-muted">{log.get("olm_name","")}</small><br><small style="font-size:10px;">{log.get("device","")}</small></td></tr>'

    users_html = ''
    for uid, udata in db.get("bot_users", {}).items():
        uname = udata.get("username", "")
        uname_html = f'<span class="text-warning">{uname}</span>' if uname else ''
        users_html += f'<tr><td><strong class="text-info">{udata["name"]}</strong> {uname_html}<br><small class="text-muted">{uid}</small></td><td><span class="badge bg-success">{udata["balance"]}đ</span></td><td>{udata["resets"]} lần</td></tr>'

    current_notice = db.get("global_notice", {}).get("msg", "")

    return f'''
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>LVT PRO - Admin</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>:root {{ --bg-main: #0a0a12; --bg-card: #151525; --neon-cyan: #00ffcc; --neon-purple: #bd00ff; }} body {{ background: var(--bg-main); color: #e0e0e0; font-family: 'Segoe UI', Tahoma, sans-serif; }} .card {{ background: var(--bg-card); border: 1px solid #2a2a40; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }} h1, h4 {{ color: var(--neon-cyan); font-weight: 800; }} .btn-primary {{ background: linear-gradient(45deg, var(--neon-purple), #7a00ff); border: none; font-weight: bold; }} .table-container {{ max-height: 500px; overflow-y: auto; }} tbody tr:hover {{ background-color: rgba(0, 255, 204, 0.05) !important; }} #toastBox {{ position: fixed; bottom: 20px; right: 20px; z-index: 9999; }}</style></head><body class="p-2 p-md-4"><div id="toastBox"></div><div class="container-fluid"><div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary"><h1 class="m-0">⚡ LVT ADMIN</h1><div><a href="/admin/online" class="btn btn-success me-2 fw-bold">📡 Giám Sát IP Online</a><a href="/logout" class="btn btn-outline-danger">Đăng xuất</a></div></div><div class="row g-4"><div class="col-lg-4">
    
    <div class="card p-3 mb-4" style="border-color: #00ffcc;"><h4><i class="fas fa-wrench"></i> Tạo Key LVT Tool</h4><form action="/admin/create" method="POST" class="row g-2"><input type="hidden" name="target_app" value="tool"><div class="col-6"><input type="text" name="prefix" class="form-control bg-dark text-light" placeholder="Prefix (Mặc định: LVT)"></div><div class="col-6"><input type="number" name="quantity" class="form-control bg-dark text-light" value="1"></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="min">Phút</option><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-6"><input type="number" name="maxDevices" class="form-control bg-dark text-light" placeholder="Max TB" value="1"></div><div class="col-6 d-flex align-items-end"><div class="form-check form-switch"><input class="form-check-input" type="checkbox" name="is_vip" id="vipSwitch1"><label class="form-check-label text-warning" for="vipSwitch1">Chế độ VIP</label></div></div><div class="col-12 mt-3"><button type="submit" class="btn btn-primary w-100" style="background: linear-gradient(45deg, #00ffcc, #0066ff); color:black;">TẠO KEY LVT</button></div></form></div>
    
    <div class="card p-3 mb-4" style="border-color: #ff3366;"><h4><i class="fas fa-crosshairs"></i> Tạo Key OLM</h4><form action="/admin/create" method="POST" class="row g-2"><input type="hidden" name="target_app" value="olm"><div class="col-6"><input type="text" name="prefix" class="form-control bg-dark text-light" placeholder="Prefix (Mặc định: OLM)"></div><div class="col-6"><input type="number" name="quantity" class="form-control bg-dark text-light" value="1"></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="min">Phút</option><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-6"><input type="number" name="maxDevices" class="form-control bg-dark text-light" placeholder="Max TB" value="1"></div><div class="col-6 d-flex align-items-end"><div class="form-check form-switch"><input class="form-check-input" type="checkbox" name="is_vip" id="vipSwitch2"><label class="form-check-label text-warning" for="vipSwitch2">Chế độ VIP</label></div></div><div class="col-12 mt-3"><button type="submit" class="btn btn-primary w-100" style="background: linear-gradient(45deg, #ff3366, #ff9900); color:white;">TẠO KEY OLM</button></div></form></div>
    
    <div class="card p-3 mb-4" style="border-color: #fff;"><h4><i class="fas fa-robot"></i> Tạo Key Admin Telegram</h4><form action="/admin/create" method="POST" class="row g-2"><input type="hidden" name="target_app" value="admin_bot"><input type="hidden" name="is_vip" value="on"><input type="hidden" name="quantity" value="1"><div class="col-12"><input type="text" name="prefix" class="form-control bg-dark text-light" placeholder="Tên Key (VD: ADMIN)"></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="day">Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-12"><input type="number" name="maxDevices" class="form-control bg-dark text-light" placeholder="Giới hạn số Telegram dùng chung" value="1"></div><div class="col-12 mt-2"><button type="submit" class="btn btn-light w-100 fw-bold text-dark">TẠO KEY ADMIN</button></div></form></div>
    
    <div class="card p-3 mb-4" style="border-color: #2AABEE;"><h4><i class="fab fa-telegram"></i> Quản Lý User Bot Telegram</h4>
    <form action="/admin/add_balance" method="POST" class="row g-2 mb-3">
        <div class="col-12"><input type="text" name="target_user" class="form-control bg-dark text-light" placeholder="Nhập @username hoặc ID khách..." required></div>
        <div class="col-5"><input type="number" name="amount" class="form-control bg-dark text-light" placeholder="Tiền (VD: 50k)" value="0" required></div>
        <div class="col-4"><input type="number" name="resets" class="form-control bg-dark text-light" placeholder="+ Lượt Reset" value="0" required></div>
        <div class="col-3"><button type="submit" class="btn w-100 fw-bold" style="background:#2AABEE; color:white;">Nạp</button></div>
    </form>
    <div class="table-container" style="max-height:150px;"><table class="table table-dark table-sm mb-0"><thead><tr><th>Tên (Username/ID)</th><th>Số Dư</th><th>Reset</th></tr></thead><tbody>{users_html}</tbody></table></div></div>
    
    </div><div class="col-lg-8">
    
    <div class="card p-3 mb-4"><h4 class="text-danger">🛡️ Block IP & Khóa Tên OLM</h4><div class="row g-3"><div class="col-md-6"><form action="/admin/ban-ip" method="POST" class="row g-2"><div class="col-12"><input type="text" name="ip" class="form-control bg-dark text-light" placeholder="Nhập IP..." required></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian"></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="hour">Giờ</option><option value="day">Ngày</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-12"><button type="submit" class="btn btn-danger w-100">Ban IP</button></div></form><div class="table-container mt-2" style="max-height:150px;"><table class="table table-dark table-sm mb-0"><thead><tr><th>IP</th><th>Hạn</th><th>Xóa</th></tr></thead><tbody>{ips_html}</tbody></table></div></div><div class="col-md-6"><form action="/admin/lock_olm" method="POST" class="row g-2"><div class="col-12"><input type="text" name="user" class="form-control bg-dark text-light" placeholder="Nhập Tên OLM (VD: hp_abc)" required></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian"></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="hour">Giờ</option><option value="day">Ngày</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-12"><button type="submit" class="btn btn-warning w-100 text-dark fw-bold">Khóa Tên OLM</button></div></form><div class="table-container mt-2" style="max-height:150px;"><table class="table table-dark table-sm mb-0"><thead><tr><th>Tên OLM</th><th>Hạn</th><th>Xóa</th></tr></thead><tbody>{olm_html}</tbody></table></div></div></div></div>
    
    <div class="card p-3 mb-4" style="border-color: #bd00ff;"><h4>📢 Thông Báo Toàn Cầu (Gửi đến Script/Tool)</h4><form action="/admin/notice" method="POST" class="row g-2"><div class="col-12"><input type="text" name="message" class="form-control bg-dark text-light" placeholder="Nhập thông báo hiện lên màn hình người dùng..." value="{current_notice}"></div><div class="col-4"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian" required value="10"></div><div class="col-5"><select name="type" class="form-select bg-dark text-light"><option value="sec">Giây</option><option value="min">Phút</option><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option><option value="year">Năm</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-3"><button type="submit" class="btn btn-info w-100 fw-bold">Phát Loa</button></div></form></div>
    
    <div class="card p-3 mb-4"><div class="d-flex justify-content-between align-items-center mb-3"><h4>📋 Quản Lý Key</h4><div class="d-flex gap-2"><form action="/admin/delete_all" method="POST"><button class="btn btn-sm btn-danger fw-bold" onclick="return confirm('CHẮC CHẮN XÓA TOÀN BỘ KEY?')">Xóa ALL Key</button></form><select id="statusFilter" class="form-select form-select-sm bg-dark text-light" onchange="filterTable()"><option value="all">Tất cả</option><option value="active">Hoạt động</option><option value="expired">Hết hạn</option><option value="banned">Bị khóa</option></select><input type="text" id="searchInput" class="form-control form-control-sm bg-dark text-light" placeholder="Tìm Key..." onkeyup="filterTable()"></div></div><div class="table-container"><table class="table table-dark table-hover mb-0 align-middle"><thead><tr><th>Key</th><th>Hạn</th><th>Thiết bị</th><th>Điều Khiển</th></tr></thead><tbody id="keyTableBody">{keys_html}</tbody></table></div></div><div class="card p-3"><h4>📡 Lịch sử Logs (Chi tiết IP, TB, User)</h4><div class="table-container" style="max-height:400px;"><table class="table table-dark table-sm table-striped mb-0"><thead><tr><th>Time</th><th>Trạng thái</th><th>Key</th><th>Thông tin IP / Device / OLM</th></tr></thead><tbody>{logs_html}</tbody></table></div></div></div></div></div><div class="modal fade" id="extendModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:var(--bg-card);"><div class="modal-header"><h5 class="modal-title">⏳ Gia hạn Key</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form action="/admin/extend" method="POST"><div class="modal-body"><input type="hidden" name="key" id="extendKeyInput"><p>Key: <strong id="extendKeyDisplay" class="text-info"></strong></p><div class="row g-2"><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option></select></div></div></div><div class="modal-footer"><button type="submit" class="btn btn-primary w-100">Gia hạn</button></div></form></div></div></div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function copyText(text) {{ navigator.clipboard.writeText(text); alert("Đã copy: " + text); }} 
        function filterTable() {{ let s = document.getElementById('searchInput').value.toLowerCase(), f = document.getElementById('statusFilter').value; document.querySelectorAll('.key-row').forEach(r => {{ r.style.display = (r.innerText.toLowerCase().includes(s) && (f==='all' || r.dataset.status===f)) ? '' : 'none'; }}); }} 
        function openExtendModal(key) {{ document.getElementById('extendKeyInput').value = key; document.getElementById('extendKeyDisplay').innerText = key; new bootstrap.Modal(document.getElementById('extendModal')).show(); }}
        
        let reloadTimer = setTimeout(() => location.reload(), 15000);
        document.querySelectorAll('input, select').forEach(el => {{
            el.addEventListener('focus', () => clearTimeout(reloadTimer));
            el.addEventListener('blur', () => reloadTimer = setTimeout(() => location.reload(), 15000));
        }});
    </script></body></html>
    '''

def render_login_html():
    return '''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Login - LVT PRO</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>body { background: #0a0a12; display: flex; justify-content: center; align-items: center; height: 100vh; } .login-box { background: #151525; padding: 40px; border-radius: 15px; border: 1px solid #00ffcc; text-align: center; } h2 { color: #00ffcc; margin-bottom: 30px; } input { background: #0a0a12 !important; color: white !important; border: 1px solid #333 !important; } .btn-login { background: linear-gradient(45deg, #00ffcc, #bd00ff); width: 100%; margin-top: 20px; font-weight:bold;}</style></head><body><div class="login-box"><h2>LVT SYSTEM</h2><form method="POST"><input type="password" name="password" class="form-control mb-3" placeholder="Nhập mật khẩu Admin..." required><button type="submit" class="btn btn-login text-white">XÁC NHẬN</button></form></div></body></html>'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
