import os
import json
import time
import random
import secrets
import hashlib
import threading
import sys
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
                    os._exit(0) # Tự sập code nếu bị can thiệp
        except: pass

threading.Thread(target=__anti_tamper__, daemon=True).start()
# ----------------------------------------------------------------

app = Flask(__name__)
DB_FILE = './database.json'
ADMIN_PASSWORD = 'admin120510'

remote_unlocks = {}
logout_pins = set()
multipliers = {'sec': 1000, 'min': 60000, 'hour': 3600000, 'day': 86400000, 'month': 2592000000, 'year': 31536000000}

@app.after_request
def add_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

def load_db():
    if not os.path.exists(DB_FILE): 
        return {"keys": {}, "logs": [], "banned_ips": {}, "logout_pins": [], "global_notice": "", "locked_olm": {}, "ip_strikes": {}}
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            data.setdefault("keys", {})
            data.setdefault("logs", [])
            data.setdefault("banned_ips", {})
            data.setdefault("logout_pins", [])
            data.setdefault("global_notice", "")
            data.setdefault("locked_olm", {})
            data.setdefault("ip_strikes", {})
            return data
        except: 
            return {"keys": {}, "logs": [], "banned_ips": {}, "logout_pins": [], "global_notice": "", "locked_olm": {}, "ip_strikes": {}}

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
    db["logs"] = db["logs"][:200]

def get_real_ip():
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
    return request.remote_addr

@app.before_request
def check_auth():
    if request.path in ['/login', '/api/check', '/api/remote_unlock', '/api/poll_unlock', '/api/trigger_logout'] or request.path.startswith('/static'): return
    if request.method == 'OPTIONS': return 
    if request.cookies.get('admin_auth') != 'true': return redirect('/login')

def process_key_validation(key, deviceId, real_ip, target_app, expected_type, device_name="Unknown", olm_name="N/A"):
    db = load_db()
    current_time = int(time.time() * 1000)

    # CHECK IP BỊ BAN (CHUNG HOẶC DO CHIA SẺ)
    if real_ip in db.get("banned_ips", {}):
        ban_exp = db["banned_ips"][real_ip]
        if ban_exp == 'permanent' or current_time < ban_exp:
            add_log(db, "BỊ CHẶN IP", key or "N/A", real_ip, f"{device_name} ({deviceId})", olm_name)
            save_db(db)
            return False, {"status": "error", "message": "IP của bạn đã bị khóa hệ thống!"}
        else: 
            del db["banned_ips"][real_ip]

    # CHECK TÀI KHOẢN OLM BỊ KHÓA
    if olm_name != "N/A" and olm_name in db.get("locked_olm", {}):
        olm_exp = db["locked_olm"][olm_name]
        if olm_exp == 'permanent' or current_time < olm_exp:
            add_log(db, "OLM BỊ KHÓA", key or "N/A", real_ip, f"{device_name} ({deviceId})", olm_name)
            save_db(db)
            return False, {
                "status": "error", 
                "message": f"Tài khoản OLM '{olm_name}' đang bị khóa hệ thống!",
                "is_locked_olm": True, 
                "lock_exp": olm_exp
            }
        else:
            del db["locked_olm"][olm_name]

    if not key or key not in db["keys"]:
        add_log(db, "SAI KEY", key or "Trống", real_ip, f"{device_name} ({deviceId})", olm_name)
        save_db(db)
        return False, {"status": "error", "message": "Key không tồn tại!"}

    keyData = db["keys"][key]
    
    # CHECK CHÉO HỆ THỐNG
    actual_target = keyData.get('target', 'tool')
    if actual_target != target_app:
        add_log(db, "SAI HỆ THỐNG", key, real_ip, f"{device_name} ({deviceId})", olm_name)
        save_db(db)
        sys_name = "LVT Tool" if actual_target == "tool" else "OLM"
        return False, {"status": "error", "message": f"LỖI: Key này là của hệ thống {sys_name}!"}

    # CHECK CHÉO VIP/THƯỜNG
    is_key_vip = keyData.get('vip', False)
    is_expect_vip = (expected_type == 'vip')
    if is_expect_vip and not is_key_vip:
        return False, {"status": "error", "message": "Bạn đang dùng Key THƯỜNG. Hãy gạt công tắc sang 'Key Thường'!"}
    if not is_expect_vip and is_key_vip:
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

    # ANTI-SHARING (CHECK IP)
    known_ips = keyData.setdefault('known_ips', [])
    if real_ip not in known_ips:
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

    # CHECK DEVICE ID
    if deviceId not in keyData.get('devices', []):
        if len(keyData.get('devices', [])) >= keyData.get('maxDevices', 1):
            add_log(db, "QUÁ GIỚI HẠN TB", key, real_ip, f"{device_name} ({deviceId})", olm_name)
            save_db(db)
            return False, {"status": "error", "message": "Key đã đầy thiết bị!"}
        keyData.setdefault('devices', []).append(deviceId)

    add_log(db, "THÀNH CÔNG", key, real_ip, f"{device_name} ({deviceId})", olm_name)
    save_db(db)
    
    notice = db.get("global_notice", "")
    return True, {
        "status": "success", 
        "message": "Xác thực thành công!", 
        "exp": keyData.get('exp'), 
        "vip": is_key_vip, 
        "devices": f"{len(keyData.get('devices', []))}/{keyData.get('maxDevices', 1)}",
        "notice": notice
    }

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
    
    if not pfx: pfx = "LVT" if target_app == "tool" else "OLM"
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
    db = load_db()
    db["global_notice"] = msg
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
    save_db(db); return redirect('/')

@app.route('/admin/extend', methods=['POST'])
def extend_key():
    key, dur, t = request.form.get('key'), request.form.get('duration'), request.form.get('type')
    db = load_db()
    if key in db["keys"] and db["keys"][key].get('exp') not in ['permanent', 'pending']:
        db["keys"][key]['exp'] = (db["keys"][key]['exp'] if db["keys"][key]['exp'] > int(time.time() * 1000) else int(time.time() * 1000)) + int(dur) * multipliers.get(t, 86400000)
        save_db(db)
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
        elif action == 'toggle_vip':
            db["keys"][key]['vip'] = not db["keys"][key].get('vip', False)
        save_db(db)
    return redirect('/')

@app.route('/')
def dashboard():
    db = load_db()
    keys_html = ''
    for k, data in db["keys"].items():
        is_banned, is_vip, sys_target = data.get('status') == 'banned', data.get('vip', False), data.get('target', 'tool')
        
        status_badge = '<span class="badge bg-danger">BANNED</span>' if is_banned else ('<span class="badge bg-warning text-dark">VIP</span>' if is_vip else '<span class="badge bg-success">THƯỜNG</span>')
        sys_badge = '<span class="badge bg-info">LVT Tool</span>' if sys_target == 'tool' else '<span class="badge bg-danger">OLM</span>'

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
        color = "success" if log['action'] == "THÀNH CÔNG" else ("danger" if "BANNED" in log['action'] or "BỊ CHẶN" in log['action'] or "SAI" in log['action'] or "GIỚI HẠN" in log['action'] else "warning")
        logs_html += f'<tr><td><small class="text-muted">{time.strftime("%H:%M:%S %d/%m", time.localtime(log["time"]))}</small></td><td><span class="badge bg-{color}">{log["action"]}</span></td><td class="text-info">{log["key"]}</td><td><span class="badge bg-secondary">{log["ip"]}</span><br><small class="text-muted">{log.get("olm_name","")}</small><br><small style="font-size:10px;">{log.get("device","")}</small></td></tr>'

    current_notice = db.get("global_notice", "")

    return f'''
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>LVT PRO - Admin</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>:root {{ --bg-main: #0a0a12; --bg-card: #151525; --neon-cyan: #00ffcc; --neon-purple: #bd00ff; }} body {{ background: var(--bg-main); color: #e0e0e0; font-family: 'Segoe UI', Tahoma, sans-serif; }} .card {{ background: var(--bg-card); border: 1px solid #2a2a40; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }} h1, h4 {{ color: var(--neon-cyan); font-weight: 800; }} .btn-primary {{ background: linear-gradient(45deg, var(--neon-purple), #7a00ff); border: none; font-weight: bold; }} .table-container {{ max-height: 500px; overflow-y: auto; }} tbody tr:hover {{ background-color: rgba(0, 255, 204, 0.05) !important; }} #toastBox {{ position: fixed; bottom: 20px; right: 20px; z-index: 9999; }}</style></head><body class="p-2 p-md-4"><div id="toastBox"></div><div class="container-fluid"><div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary"><h1 class="m-0">⚡ LVT ADMIN</h1><div><a href="/logout" class="btn btn-outline-danger">Đăng xuất</a></div></div><div class="row g-4"><div class="col-lg-4">
    
    <div class="card p-3 mb-4" style="border-color: #00ffcc;"><h4><i class="fas fa-wrench"></i> Tạo Key LVT Tool</h4><form action="/admin/create" method="POST" class="row g-2"><input type="hidden" name="target_app" value="tool"><div class="col-6"><input type="text" name="prefix" class="form-control bg-dark text-light" placeholder="Prefix (Mặc định: LVT)"></div><div class="col-6"><input type="number" name="quantity" class="form-control bg-dark text-light" value="1"></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="min">Phút</option><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-6"><input type="number" name="maxDevices" class="form-control bg-dark text-light" placeholder="Max TB" value="1"></div><div class="col-6 d-flex align-items-end"><div class="form-check form-switch"><input class="form-check-input" type="checkbox" name="is_vip" id="vipSwitch1"><label class="form-check-label text-warning" for="vipSwitch1">Chế độ VIP</label></div></div><div class="col-12 mt-3"><button type="submit" class="btn btn-primary w-100" style="background: linear-gradient(45deg, #00ffcc, #0066ff); color:black;">TẠO KEY LVT</button></div></form></div>
    
    <div class="card p-3 mb-4" style="border-color: #ff3366;"><h4><i class="fas fa-crosshairs"></i> Tạo Key OLM</h4><form action="/admin/create" method="POST" class="row g-2"><input type="hidden" name="target_app" value="olm"><div class="col-6"><input type="text" name="prefix" class="form-control bg-dark text-light" placeholder="Prefix (Mặc định: OLM)"></div><div class="col-6"><input type="number" name="quantity" class="form-control bg-dark text-light" value="1"></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="min">Phút</option><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-6"><input type="number" name="maxDevices" class="form-control bg-dark text-light" placeholder="Max TB" value="1"></div><div class="col-6 d-flex align-items-end"><div class="form-check form-switch"><input class="form-check-input" type="checkbox" name="is_vip" id="vipSwitch2"><label class="form-check-label text-warning" for="vipSwitch2">Chế độ VIP</label></div></div><div class="col-12 mt-3"><button type="submit" class="btn btn-primary w-100" style="background: linear-gradient(45deg, #ff3366, #ff9900); color:white;">TẠO KEY OLM</button></div></form></div>
    
    <div class="card p-3 mb-4"><h4 class="text-danger">🛡️ Block IP</h4><form action="/admin/ban-ip" method="POST" class="row g-2 mb-3"><div class="col-12"><input type="text" name="ip" class="form-control bg-dark text-light" placeholder="Nhập IP..." required></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian"></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="hour">Giờ</option><option value="day">Ngày</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-12"><button type="submit" class="btn btn-danger w-100">Ban IP</button></div></form><div class="table-container" style="max-height:150px;"><table class="table table-dark table-sm mb-0"><thead><tr><th>IP</th><th>Hạn</th><th>Xóa</th></tr></thead><tbody>{ips_html}</tbody></table></div></div>
    
    <div class="card p-3"><h4 class="text-warning">🔒 Khóa Tên OLM</h4><form action="/admin/lock_olm" method="POST" class="row g-2 mb-3"><div class="col-12"><input type="text" name="user" class="form-control bg-dark text-light" placeholder="Nhập Tên OLM (VD: hp_luongvantuyen)" required></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian"></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="hour">Giờ</option><option value="day">Ngày</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-12"><button type="submit" class="btn btn-warning w-100 text-dark fw-bold">Khóa Tài Khoản OLM</button></div></form><div class="table-container" style="max-height:150px;"><table class="table table-dark table-sm mb-0"><thead><tr><th>Tên OLM</th><th>Hạn</th><th>Xóa</th></tr></thead><tbody>{olm_html}</tbody></table></div></div>
    
    </div><div class="col-lg-8">
    
    <div class="card p-3 mb-4" style="border-color: #bd00ff;"><h4>📢 Thông Báo Toàn Cầu (Gửi đến Script/Tool)</h4><form action="/admin/notice" method="POST" class="d-flex gap-2"><input type="text" name="message" class="form-control bg-dark text-light" placeholder="Nhập thông báo hiện lên màn hình người dùng..." value="{current_notice}"><button type="submit" class="btn btn-info">Lưu</button></form></div>
    
    <div class="card p-3 mb-4"><div class="d-flex justify-content-between align-items-center mb-3"><h4>📋 Quản Lý Key</h4><div class="d-flex gap-2"><form action="/admin/delete_all" method="POST"><button class="btn btn-sm btn-danger fw-bold" onclick="return confirm('CHẮC CHẮN XÓA TOÀN BỘ KEY?')">Xóa ALL Key</button></form><select id="statusFilter" class="form-select form-select-sm bg-dark text-light" onchange="filterTable()"><option value="all">Tất cả</option><option value="active">Hoạt động</option><option value="expired">Hết hạn</option><option value="banned">Bị khóa</option></select><input type="text" id="searchInput" class="form-control form-control-sm bg-dark text-light" placeholder="Tìm Key..." onkeyup="filterTable()"></div></div><div class="table-container"><table class="table table-dark table-hover mb-0 align-middle"><thead><tr><th>Key</th><th>Hạn</th><th>Thiết bị</th><th>Điều Khiển</th></tr></thead><tbody id="keyTableBody">{keys_html}</tbody></table></div></div><div class="card p-3"><h4>📡 Lịch sử Logs (Chi tiết IP, TB, User)</h4><div class="table-container" style="max-height:400px;"><table class="table table-dark table-sm table-striped mb-0"><thead><tr><th>Time</th><th>Trạng thái</th><th>Key</th><th>Thông tin IP / Device / OLM</th></tr></thead><tbody>{logs_html}</tbody></table></div></div></div></div></div><div class="modal fade" id="extendModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:var(--bg-card);"><div class="modal-header"><h5 class="modal-title">⏳ Gia hạn Key</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form action="/admin/extend" method="POST"><div class="modal-body"><input type="hidden" name="key" id="extendKeyInput"><p>Key: <strong id="extendKeyDisplay" class="text-info"></strong></p><div class="row g-2"><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option></select></div></div></div><div class="modal-footer"><button type="submit" class="btn btn-primary w-100">Gia hạn</button></div></form></div></div></div><script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script><script>function copyText(text) {{ navigator.clipboard.writeText(text); alert("Đã copy: " + text); }} function filterTable() {{ let s = document.getElementById('searchInput').value.toLowerCase(), f = document.getElementById('statusFilter').value; document.querySelectorAll('.key-row').forEach(r => {{ r.style.display = (r.innerText.toLowerCase().includes(s) && (f==='all' || r.dataset.status===f)) ? '' : 'none'; }}); }} function openExtendModal(key) {{ document.getElementById('extendKeyInput').value = key; document.getElementById('extendKeyDisplay').innerText = key; new bootstrap.Modal(document.getElementById('extendModal')).show(); }}</script></body></html>
    '''

def render_login_html():
    return '''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Login - LVT PRO</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>body { background: #0a0a12; display: flex; justify-content: center; align-items: center; height: 100vh; } .login-box { background: #151525; padding: 40px; border-radius: 15px; border: 1px solid #00ffcc; text-align: center; } h2 { color: #00ffcc; margin-bottom: 30px; } input { background: #0a0a12 !important; color: white !important; border: 1px solid #333 !important; } .btn-login { background: linear-gradient(45deg, #00ffcc, #bd00ff); width: 100%; margin-top: 20px; font-weight:bold;}</style></head><body><div class="login-box"><h2>LVT SYSTEM</h2><form method="POST"><input type="password" name="password" class="form-control mb-3" placeholder="Nhập mật khẩu Admin..." required><button type="submit" class="btn btn-login text-white">XÁC NHẬN</button></form></div></body></html>'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
