import os
import json
import time
import random
import secrets
import hashlib
import threading
import sys
import requests
import re
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
ADMIN_PASSWORD = 'admin120510'

# ========================================================
# CẤU HÌNH BOT TELEGRAM
# ========================================================
TELEGRAM_BOT_TOKEN = "8621133442:AAEimlzP2LKIfWOLE18iQGoUUHS7pyXmDuw"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
# ========================================================

remote_unlocks = {}
logout_pins = set()

# BỘ CHUYỂN ĐỔI THỜI GIAN LINH HOẠT (s, m, h, d, mo, y, vv)
def parse_duration(duration_str):
    if duration_str.lower() in ['vv', 'vinhvien', 'permanent']:
        return 'permanent'
    match = re.match(r"(\d+)([a-zA-Z]+)", duration_str.strip())
    if not match: return 0
    amount, unit = int(match.group(1)), match.group(2).lower()
    multipliers = {'s': 1000, 'm': 60000, 'h': 3600000, 'd': 86400000, 'mo': 2592000000, 'y': 31536000000}
    return amount * multipliers.get(unit, 0)

active_sessions = {} 

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
            data.setdefault("bot_users", {})
            data.setdefault("locked_olm", {})
            data.setdefault("banned_ips", {})
            data.setdefault("keys", {})
            data.setdefault("logs", [])
            if not isinstance(data.get("global_notice"), dict):
                data["global_notice"] = {"msg": "", "exp": "permanent"}
            # Đảm bảo user có mảng purchases và notices
            for uid in data["bot_users"]:
                data["bot_users"][uid].setdefault("purchases", [])
                data["bot_users"][uid].setdefault("notices", [])
            return data
        except: return {"keys": {}, "logs": [], "banned_ips": {}, "logout_pins": [], "global_notice": {}, "locked_olm": {}, "ip_strikes": {}, "bot_users": {}}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f: 
        json.dump(db, f, indent=2, ensure_ascii=False)

def add_log(db, action, key, ip, device, olm_name="N/A"):
    db.setdefault("logs", []).insert(0, {"time": int(time.time()), "action": action, "key": key, "ip": ip, "device": device, "olm_name": olm_name})
    db["logs"] = db["logs"][:500] 

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

    if real_ip in db["banned_ips"]:
        ban_exp = db["banned_ips"][real_ip]
        if ban_exp == 'permanent' or current_time < ban_exp:
            return False, {"status": "error", "message": "IP của bạn đã bị khóa hệ thống!"}
        else: del db["banned_ips"][real_ip]

    if olm_name != "N/A" and olm_name in db["locked_olm"]:
        olm_exp = db["locked_olm"][olm_name]
        if olm_exp == 'permanent' or current_time < olm_exp:
            return False, {"status": "error", "message": f"Tài khoản OLM '{olm_name}' đang bị khóa!", "is_locked_olm": True, "lock_exp": olm_exp}
        else: del db["locked_olm"][olm_name]

    if not key or key not in db["keys"]:
        return False, {"status": "error", "message": "Key không tồn tại!"}

    kData = db["keys"][key]
    if kData.get('target', 'tool') != target_app and target_app != "admin_bot":
        return False, {"status": "error", "message": "Sai hệ thống!"}

    if kData.get('status') == 'banned':
        return False, {"status": "error", "message": "Key bị khóa!"}

    if kData.get('exp') == 'pending': 
        kData['exp'] = current_time + kData.get('durationMs', 0)
    
    if kData.get('exp') != 'permanent' and current_time > kData.get('exp', 0):
        return False, {"status": "error", "message": "Key hết hạn!"}

    if deviceId not in kData.get('devices', []):
        if len(kData.get('devices', [])) >= kData.get('maxDevices', 1):
            return False, {"status": "error", "message": "Key đã đầy thiết bị!"}
        kData.setdefault('devices', []).append(deviceId)

    if target_app == "olm":
        active_sessions[deviceId] = {"ip": real_ip, "olm_name": olm_name, "key": key, "last_seen": time.time()}
        add_log(db, "TRUY CẬP OLM", key, real_ip, f"{device_name} ({deviceId})", olm_name)
    elif target_app == "admin_bot":
        add_log(db, "ADMIN BOT", key, real_ip, f"Telegram ({deviceId})", "N/A")
    else:
        add_log(db, "THÀNH CÔNG", key, real_ip, f"{device_name} ({deviceId})", olm_name)
    
    save_db(db)
    notice = db.get("global_notice", {})
    notice_msg = notice.get("msg", "") if (notice.get("exp") == "permanent" or current_time < notice.get("exp", 0)) else ""

    return True, {"status": "success", "exp": kData.get('exp'), "vip": kData.get('vip'), "notice": notice_msg}

# ====================================================================
# TELEGRAM BOT ENGINE (TỐI THƯỢNG)
# ====================================================================
def send_telegram_message(chat_id, text, reply_markup=None):
    if not TELEGRAM_BOT_TOKEN: return
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: payload["reply_markup"] = reply_markup
    try: requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload)
    except: pass

def get_user_id_by_username(db, username):
    username = username.strip().lower()
    for uid, info in db["bot_users"].items():
        if info.get("username", "").lower() == username: return uid
    return None

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    data = request.json
    if not data: return "ok", 200
    
    chat_id = None; msg_text = ""; payload = ""; user_name = "Khách"; tg_username = ""
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        msg_text = data["message"].get("text", "").strip()
        user_name = data["message"]["from"].get("first_name", "Khách")
        tg_username = data["message"]["from"].get("username", "")
    elif "callback_query" in data:
        chat_id = data["callback_query"]["message"]["chat"]["id"]
        payload = data["callback_query"]["data"]
        user_name = data["callback_query"]["from"].get("first_name", "Khách")
        tg_username = data["callback_query"]["from"].get("username", "")
        requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": data["callback_query"]["id"]})

    if not chat_id: return "ok", 200
    db = load_db()
    sid = str(chat_id)
    safe_name = user_name.replace("<", "").replace(">", "")
    f_uname = f"@{tg_username}" if tg_username else ""
    
    if sid not in db["bot_users"]:
        db["bot_users"][sid] = {"name": safe_name, "username": f_uname, "balance": 0, "resets": 3, "state": "none", "is_admin": False, "purchases": [], "notices": []}
    else: 
        db["bot_users"][sid]["username"] = f_uname
        db["bot_users"][sid].setdefault("purchases", [])
        db["bot_users"][sid].setdefault("notices", [])
    
    user = db["bot_users"][sid]
    now_ms = int(time.time() * 1000)

    # KIỂM TRA HỘP THƯ THÔNG BÁO BOT
    if msg_text.upper() == "/START" or msg_text.upper() == "/ADMIN" or payload == "MENU_MAIN":
        active_notices = []
        valid_notices = []
        for n in user["notices"]:
            if n["exp"] == 'permanent' or n["exp"] > now_ms:
                valid_notices.append(n)
                active_notices.append(n["msg"])
        user["notices"] = valid_notices
        save_db(db)
        
        if active_notices:
            notice_text = "🔔 <b>CÓ THÔNG BÁO MỚI TỪ ADMIN:</b>\n" + "\n".join([f"🔸 {m}" for m in active_notices])
            send_telegram_message(chat_id, notice_text)

    # --- ADMIN LOGIC ---
    if user.get("is_admin"):
        adm_key = user.get("admin_key", "")
        success, _ = process_key_validation(adm_key, sid, "TELEGRAM", "admin_bot", "any")
        if not success:
            user["is_admin"] = False; user["admin_key"] = ""; user["state"] = "none"; save_db(db)
            send_telegram_message(chat_id, "⚠️ Key Admin của bạn đã hết hạn. Quyền Admin đã bị tước!")

    if msg_text.upper() == "/ADMIN" or payload == "ADM_MENU":
        if user.get("is_admin"):
            user["state"] = "none"; save_db(db)
            markup = {"inline_keyboard": [
                [{"text": "➕ Tạo Key", "callback_data": "ADM_W_CREATE"}, {"text": "💰 Nạp Tiền", "callback_data": "ADM_W_BAL"}],
                [{"text": "🔒 Khóa OLM", "callback_data": "ADM_W_LOCK"}, {"text": "🚫 Ban IP", "callback_data": "ADM_W_BAN"}],
                [{"text": "📢 TB Tool", "callback_data": "ADM_W_NOTE"}, {"text": "💬 TB Bot", "callback_data": "ADM_BOT_NOTE"}],
                [{"text": "👤 Quản Lý User", "callback_data": "ADM_USER"}, {"text": "🛠 Quản Lý Key", "callback_data": "ADM_MANAGE"}],
                [{"text": "📜 Lịch Sử Log Chung", "callback_data": "ADM_LOGS"}],
                [{"text": "❌ Đăng Xuất Admin", "callback_data": "ADM_LOGOUT"}]
            ]}
            send_telegram_message(chat_id, "👑 <b>ADMIN PANEL TỐI THƯỢNG</b>", markup)
        else:
            user["state"] = "wait_admin_key"; save_db(db)
            send_telegram_message(chat_id, "🔐 Vui lòng nhập Key Admin:")
        return "ok", 200

    if user["state"] == "wait_admin_key":
        success, _ = process_key_validation(msg_text, sid, "TELEGRAM", "admin_bot", "any")
        if success:
            user["is_admin"] = True; user["admin_key"] = msg_text; user["state"] = "none"; save_db(db)
            send_telegram_message(chat_id, "✅ Đăng nhập Admin thành công! Gõ /admin")
        else: send_telegram_message(chat_id, "❌ Sai Key hoặc hết hạn!")
        return "ok", 200

    if user.get("is_admin"):
        if payload == "ADM_W_CREATE":
            user["state"] = "adm_create"; save_db(db)
            send_telegram_message(chat_id, "➕ <b>TẠO KEY</b>\nCú pháp: <code>Hệ Thời_gian MaxTB</code>\nVD: <code>OLM 30d 1</code> (Tạo key OLM 30 ngày 1 máy)")
        elif payload == "ADM_W_BAL":
            user["state"] = "adm_bal"; save_db(db)
            send_telegram_message(chat_id, "💰 <b>NẠP TIỀN & RESET</b>\nCú pháp: <code>@user Tiền Lượt_Reset</code>\nVD: <code>@lvt 50000 3</code>")
        elif payload == "ADM_W_LOCK":
            user["state"] = "adm_lock"; save_db(db)
            send_telegram_message(chat_id, "🔒 <b>KHÓA OLM</b>\nCú pháp: <code>Thời_gian Tên_OLM</code>\nVD: <code>30m hp_abc</code> (Khóa 30 phút)\nVD: <code>vv hp_abc</code> (Khóa vĩnh viễn)")
        elif payload == "ADM_W_BAN":
            user["state"] = "adm_ban"; save_db(db)
            send_telegram_message(chat_id, "🚫 <b>BAN IP</b>\nCú pháp: <code>Thời_gian IP</code>\nVD: <code>7d 1.2.3.4</code> (Khóa 7 ngày)\nVD: <code>vv 1.2.3.4</code>")
        elif payload == "ADM_W_NOTE":
            user["state"] = "adm_note"; save_db(db)
            send_telegram_message(chat_id, "📢 <b>THÔNG BÁO TOOL (GLOBAL)</b>\nCú pháp: <code>Thời_gian Nội_dung</code>\nVD: <code>1h Bảo trì server</code>")
        elif payload == "ADM_BOT_NOTE":
            markup = {"inline_keyboard": [[{"text": "Tất cả User", "callback_data": "ADM_BN_ALL"}, {"text": "User Cụ Thể", "callback_data": "ADM_BN_PRIV"}]]}
            send_telegram_message(chat_id, "💬 <b>GỬI THÔNG BÁO VÀO BOT TELEGRAM</b>", markup)
        elif payload == "ADM_BN_ALL":
            user["state"] = "adm_bn_all"; save_db(db)
            send_telegram_message(chat_id, "💬 <b>GỬI TẤT CẢ USER</b>\nCú pháp: <code>Thời_gian Nội_dung</code>\nVD: <code>1d Chúc mừng năm mới</code>")
        elif payload == "ADM_BN_PRIV":
            user["state"] = "adm_bn_priv"; save_db(db)
            send_telegram_message(chat_id, "👤 <b>GỬI USER CỤ THỂ</b>\nCú pháp: <code>@user Thời_gian Nội_dung</code>\nVD: <code>@lvt 1h Cảnh báo share key</code>")
        elif payload == "ADM_USER":
            user["state"] = "adm_check_user"; save_db(db)
            send_telegram_message(chat_id, "👤 <b>TRA CỨU USER</b>\nNhập <code>@username</code> hoặc <code>ID</code> khách hàng:")
        elif payload == "ADM_MANAGE":
            user["state"] = "adm_manage"; save_db(db)
            send_telegram_message(chat_id, "🛠 <b>QUẢN LÝ KEY</b>\nNhập lệnh:\n- <code>XOA Key</code>\n- <code>RESET Key</code>\n- <code>VIP Key</code>\n- <code>GIAHAN Key Thời_gian</code> (VD: GIAHAN OLM-123 7d)")
        elif payload == "ADM_LOGOUT":
            user["is_admin"] = False; save_db(db); send_telegram_message(chat_id, "👋 Đã thoát Admin!")
        elif payload == "ADM_LOGS":
            txt = "📜 <b>LOGS CHUNG (10 GẦN NHẤT):</b>\n"
            for l in db.get("logs", [])[:10]: txt += f"• {time.strftime('%H:%M %d/%m', time.localtime(l['time']))} | {l['action']} | <code>{l['key']}</code> | {l['ip']}\n"
            send_telegram_message(chat_id, txt, {"inline_keyboard": [[{"text": "🔙 Menu", "callback_data": "ADM_MENU"}]]})
        
        # --- XỬ LÝ LỆNH ADMIN NHẬP VÀO ---
        if msg_text and user["state"].startswith("adm_"):
            if msg_text.upper() == "/CANCEL":
                user["state"] = "none"; save_db(db); send_telegram_message(chat_id, "Đã hủy."); return "ok", 200
            try:
                parts = msg_text.split()
                if user["state"] == "adm_create":
                    sys_t, dur_str, devs = parts[0].upper(), parts[1], int(parts[2])
                    dur = parse_duration(dur_str)
                    nk = f"{sys_t}-{random.randint(1000,9999)}"
                    db["keys"][nk] = {"exp": "pending", "maxDevices": devs, "devices": [], "known_ips": [], "status": "active", "vip": True, "target": sys_t.lower(), "durationMs": dur}
                    send_telegram_message(chat_id, f"✅ Đã tạo: <code>{nk}</code>")
                
                elif user["state"] == "adm_bal":
                    t_user, amt, rst = parts[0], int(parts[1]), int(parts[2])
                    t_id = get_user_id_by_username(db, t_user) if t_user.startswith('@') else t_user
                    if t_id and t_id in db["bot_users"]:
                        db["bot_users"][t_id]["balance"] += amt; db["bot_users"][t_id]["resets"] += rst
                        send_telegram_message(chat_id, f"✅ Đã nạp {amt}đ cho {t_user}")
                        send_telegram_message(t_id, f"🎉 <b>Admin vừa nạp tiền!</b>\n💰 +{amt}đ | 🔄 +{rst} reset.")
                    else: send_telegram_message(chat_id, "❌ Không tìm thấy User!")

                elif user["state"] == "adm_lock":
                    dur_str, target = parts[0], parts[1]
                    dur = parse_duration(dur_str)
                    db["locked_olm"][target] = "permanent" if dur == 'permanent' else int(time.time()*1000) + dur
                    send_telegram_message(chat_id, f"✅ Đã khóa OLM: {target} ({dur_str})")

                elif user["state"] == "adm_ban":
                    dur_str, target = parts[0], parts[1]
                    dur = parse_duration(dur_str)
                    db["banned_ips"][target] = "permanent" if dur == 'permanent' else int(time.time()*1000) + dur
                    send_telegram_message(chat_id, f"✅ Đã Ban IP: {target} ({dur_str})")

                elif user["state"] == "adm_note":
                    parts = msg_text.split(maxsplit=1)
                    dur_str, msg = parts[0], parts[1]
                    dur = parse_duration(dur_str)
                    db["global_notice"] = {"msg": msg, "exp": "permanent" if dur == 'permanent' else int(time.time()*1000) + dur}
                    send_telegram_message(chat_id, f"✅ Đã cài Thông báo Tool ({dur_str}): {msg}")
                
                elif user["state"] == "adm_bn_all":
                    parts = msg_text.split(maxsplit=1)
                    dur, msg = parse_duration(parts[0]), parts[1]
                    exp = "permanent" if dur == 'permanent' else int(time.time()*1000) + dur
                    for uid in db["bot_users"]: db["bot_users"][uid]["notices"].append({"msg": msg, "exp": exp})
                    send_telegram_message(chat_id, f"✅ Đã gửi TB Bot cho TOÀN BỘ User.")
                
                elif user["state"] == "adm_bn_priv":
                    parts = msg_text.split(maxsplit=2)
                    t_user, dur, msg = parts[0], parse_duration(parts[1]), parts[2]
                    t_id = get_user_id_by_username(db, t_user) if t_user.startswith('@') else t_user
                    if t_id and t_id in db["bot_users"]:
                        exp = "permanent" if dur == 'permanent' else int(time.time()*1000) + dur
                        db["bot_users"][t_id]["notices"].append({"msg": msg, "exp": exp})
                        send_telegram_message(chat_id, f"✅ Đã gửi TB Bot riêng cho {t_user}.")
                    else: send_telegram_message(chat_id, "❌ Không tìm thấy User!")

                elif user["state"] == "adm_check_user":
                    t_user = msg_text
                    t_id = get_user_id_by_username(db, t_user) if t_user.startswith('@') else t_user
                    if t_id and t_id in db["bot_users"]:
                        uinfo = db["bot_users"][t_id]
                        txt = f"👤 <b>THÔNG TIN:</b> {uinfo['name']} ({uinfo.get('username','')})\n🆔 ID: <code>{t_id}</code>\n💰 Số dư: {uinfo['balance']}đ | 🔄 Reset: {uinfo['resets']}\n\n🛒 <b>LỊCH SỬ MUA KEY (Gần nhất):</b>\n"
                        user_keys = [p["key"] for p in uinfo.get("purchases", [])]
                        for p in uinfo.get("purchases", [])[:5]:
                            t = time.strftime('%d/%m', time.localtime(p['time']/1000))
                            txt += f"- <code>{p['key']}</code> ({p['type']}) - {t}\n"
                        
                        txt += "\n📜 <b>LOG HOẠT ĐỘNG CỦA USER NÀY:</b>\n"
                        count = 0
                        for l in db.get("logs", []):
                            if l["key"] in user_keys:
                                txt += f"• {time.strftime('%H:%M %d/%m', time.localtime(l['time']))} | {l['action']} | <code>{l['key']}</code> | {l['ip']} | OLM: {l.get('olm_name','')}\n"
                                count +=1
                                if count >= 5: break
                        if count == 0: txt += "<i>Chưa có hoạt động.</i>"
                        
                        send_telegram_message(chat_id, txt, {"inline_keyboard": [[{"text": "🔙 Menu", "callback_data": "ADM_MENU"}]]})
                    else: send_telegram_message(chat_id, "❌ Không tìm thấy User!")

                elif user["state"] == "adm_manage":
                    action = parts[0].upper()
                    k = parts[1] if len(parts) > 1 else ""
                    if action == "XOA_ALL" and k: # Tính năng xóa toàn bộ key của 1 user
                        t_id = get_user_id_by_username(db, k) if k.startswith('@') else k
                        if t_id and t_id in db["bot_users"]:
                            user_keys = [p["key"] for p in db["bot_users"][t_id].get("purchases", [])]
                            deleted = 0
                            for uk in user_keys:
                                if uk in db["keys"]: del db["keys"][uk]; deleted += 1
                            db["bot_users"][t_id]["purchases"] = []
                            send_telegram_message(chat_id, f"✅ Đã xóa {deleted} Key của User {k}.")
                        else: send_telegram_message(chat_id, "❌ User không tồn tại!")
                    elif k in db["keys"]:
                        if action == "XOA":
                            del db["keys"][k]; send_telegram_message(chat_id, f"✅ Đã xóa Key: <code>{k}</code>")
                        elif action == "RESET":
                            db["keys"][k]["devices"] = []; db["keys"][k]["known_ips"] = []
                            send_telegram_message(chat_id, f"✅ Đã gỡ TB/IP của Key: {k}")
                        elif action == "VIP":
                            db["keys"][k]["vip"] = not db["keys"][k].get("vip", False)
                            send_telegram_message(chat_id, f"✅ Đổi VIP Key {k} -> {db['keys'][k]['vip']}")
                        elif action == "GIAHAN" and len(parts) == 3:
                            dur = parse_duration(parts[2])
                            if db["keys"][k]['exp'] not in ['permanent', 'pending']:
                                db["keys"][k]['exp'] = max(db["keys"][k]['exp'], int(time.time()*1000)) + dur
                                send_telegram_message(chat_id, f"✅ Đã gia hạn Key {k} thêm {parts[2]}")
                    else: send_telegram_message(chat_id, "❌ Không tìm thấy Key (Hoặc lệnh sai)!")
                
                save_db(db); user["state"] = "none"; save_db(db)
            except Exception as e: send_telegram_message(chat_id, f"❌ Lỗi cú pháp! Gõ /admin để thao tác lại.")
        return "ok", 200

    # --- KHÁCH LOGIC (MUA NHIỀU KEY) ---
    if msg_text.upper() == "/START" or payload == "MENU_MAIN":
        user["state"] = "none"; save_db(db)
        txt = f"👋 Chào <b>{user['name']}</b>!\n💰 Số dư: <b>{user['balance']}đ</b>\n🔄 Reset: <b>{user['resets']}/3</b>"
        markup = {"inline_keyboard": [[{"text": "🔑 Mua Key", "callback_data": "BUY"}, {"text": "🔄 Reset Key", "callback_data": "RESET"}]]}
        send_telegram_message(chat_id, txt, markup)
        
    elif payload == "BUY":
        markup = {"inline_keyboard": [[{"text": "👑 Mua VIP", "callback_data": "BUY_VIP"}, {"text": "👤 Mua Thường", "callback_data": "BUY_NOR"}],[{"text": "🔙 Menu", "callback_data": "MENU_MAIN"}]]}
        send_telegram_message(chat_id, "Chọn loại Key muốn mua:", markup)
        
    elif payload == "BUY_NOR":
        send_telegram_message(chat_id, "🛠 <b>Key Thường đang bảo trì.</b> Bạn dùng VIP nhé!", {"inline_keyboard": [[{"text": "🔙 Quay lại", "callback_data": "BUY"}]]})
        
    elif payload == "BUY_VIP":
        txt = "🛒 <b>GIÁ VIP OLM:</b>\n- 1 Giờ: 7k\n- 7 Ngày: 30k\n- 30 Ngày: 85k\n- 1 Năm: 200k"
        markup = {"inline_keyboard": [
            [{"text": "1 Giờ", "callback_data": "V_1H"},{"text": "7 Ngày", "callback_data": "V_7D"}],
            [{"text": "30 Ngày", "callback_data": "V_30D"},{"text": "1 Năm", "callback_data": "V_1Y"}],
            [{"text": "🔙 Quay lại", "callback_data": "BUY"}]
        ]}
        send_telegram_message(chat_id, txt, markup)
        
    elif payload.startswith("V_"):
        user["state"] = f"wait_qty_{payload}"; save_db(db)
        send_telegram_message(chat_id, "🔢 Vui lòng nhập <b>SỐ LƯỢNG</b> Key bạn muốn mua (VD: 1, 2, 5...):")
        
    elif payload == "RESET":
        if user["resets"] <= 0: send_telegram_message(chat_id, "❌ Hết lượt Reset.")
        else:
            user["state"] = "wait_reset_key"; save_db(db)
            send_telegram_message(chat_id, "📝 Gửi chính xác <code>Key</code> cần Reset vào đây:")

    # Nhập Text khách hàng
    if msg_text and not user.get("is_admin"):
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
                        db["keys"][nk] = {"exp": now_ms + duration_ms, "maxDevices": 1, "devices": [], "known_ips": [], "status": "active", "vip": True, "target": "olm"}
                        user["purchases"].insert(0, {"key": nk, "type": f"VIP {name}", "time": now_ms})
                        gen_keys.append(nk)
                    user["state"] = "none"; save_db(db)
                    k_str = "\n".join([f"<code>{k}</code>" for k in gen_keys])
                    send_telegram_message(chat_id, f"🎉 <b>MUA THÀNH CÔNG {qty} KEY!</b>\n\n🔑 Danh sách Key:\n{k_str}\n\n💰 Bị trừ: {total_cost}đ\n💳 Số dư còn: {user['balance']}đ", {"inline_keyboard": [[{"text": "🔙 Menu", "callback_data": "MENU_MAIN"}]]})
                else:
                    send_telegram_message(chat_id, f"❌ <b>Thiếu Tiền!</b>\nCần {total_cost}đ cho {qty} Key. Số dư: {user['balance']}đ", {"inline_keyboard": [[{"text": "🔙 Menu", "callback_data": "MENU_MAIN"}]]})
            else: send_telegram_message(chat_id, "❌ Vui lòng nhập SỐ lớn hơn 0.")
            
        elif user["state"] == "wait_reset_key":
            if msg_text in db["keys"]:
                db["keys"][msg_text]["devices"] = []; db["keys"][msg_text]["known_ips"] = []
                user["resets"] -= 1; user["state"] = "none"; save_db(db)
                send_telegram_message(chat_id, f"✅ Reset thành công Key:\n<code>{msg_text}</code>")
            else: send_telegram_message(chat_id, "❌ Key không tồn tại!")

    return "ok", 200

# ====================== API & DASHBOARD ======================
@app.route('/api/check', methods=['POST', 'OPTIONS'])
def check_key():
    if request.method == 'OPTIONS': return jsonify({}), 200
    data = request.get_json() or {}
    success, res = process_key_validation(data.get('key'), data.get('deviceId'), get_real_ip(), data.get('target_app', 'tool'), data.get('expected_type', 'normal'), data.get('device_name'), data.get('olm_name'))
    return jsonify(res)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form.get('password') == ADMIN_PASSWORD:
        r = make_response(redirect('/')); r.set_cookie('admin_auth', 'true'); return r
    return '''<form method="POST">Pass: <input type="password" name="password"><input type="submit"></form>'''

@app.route('/')
def dashboard():
    return "<h1>Server LVT đang chạy ổn định. Vui lòng quản lý qua Telegram /admin</h1>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
