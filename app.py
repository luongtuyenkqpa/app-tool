import os
import json
import time
import random
import secrets
from flask import Flask, request, jsonify, redirect, make_response

app = Flask(__name__)
DB_FILE = './database.json'
ADMIN_PASSWORD = 'admin' # ← THAY MẬT KHẨU Ở ĐÂY

# Lưu trữ các phiên mở khóa từ xa (Web độc lập -> Tool)
remote_unlocks = {}

# ====================== CHO PHÉP GIAO TIẾP TỪ WEB ĐỘC LẬP (CORS) ======================
@app.after_request
def add_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# ====================== QUẢN LÝ DATABASE ======================
def load_db():
    if not os.path.exists(DB_FILE): return {"keys": {}, "logs": [], "banned_ips": {}}
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            if "keys" not in data: return {"keys": data, "logs": [], "banned_ips": {}}
            return data
        except: return {"keys": {}, "logs": [], "banned_ips": {}}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f: json.dump(db, f, indent=2, ensure_ascii=False)

def add_log(db, action, key, ip, device):
    db.setdefault("logs", []).insert(0, {"time": int(time.time()), "action": action, "key": key, "ip": ip, "device": device})
    db["logs"] = db["logs"][:200]

def get_real_ip():
    return request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip() if request.headers.getlist("X-Forwarded-For") else request.remote_addr

@app.before_request
def check_auth():
    # Bỏ chặn các API public để web loader độc lập có thể gọi được
    if request.path in ['/login', '/api/check', '/api/remote_unlock', '/api/poll_unlock'] or request.path.startswith('/static'): return
    if request.method == 'OPTIONS': return # Preflight requests cho CORS
    if request.cookies.get('admin_auth') != 'true': return redirect('/login')

# ====================== CORE LOGIC KIỂM TRA KEY ======================
def process_key_validation(key, deviceId, real_ip):
    db = load_db()
    if real_ip in db.get("banned_ips", {}):
        ban_exp = db["banned_ips"][real_ip]
        if ban_exp == 'permanent' or int(time.time() * 1000) < ban_exp:
            add_log(db, "BỊ CHẶN IP", key or "N/A", real_ip, deviceId); save_db(db)
            return False, {"status": "error", "message": "IP của bạn đã bị khóa khỏi hệ thống!"}
        else: del db["banned_ips"][real_ip]

    if not key or key not in db["keys"]:
        add_log(db, "SAI KEY", key or "Trống", real_ip, deviceId); save_db(db)
        return False, {"status": "error", "message": "Key không tồn tại!"}

    keyData = db["keys"][key]
    if keyData.get('status') == 'banned':
        add_log(db, "KEY BỊ BANNED", key, real_ip, deviceId); save_db(db)
        return False, {"status": "error", "message": "Key này đã bị khóa (Banned)!"}

    if keyData.get('exp') == 'pending': keyData['exp'] = int(time.time() * 1000) + keyData.get('durationMs', 0)
    if keyData.get('exp') != 'permanent' and int(time.time() * 1000) > keyData.get('exp', 0):
        add_log(db, "KEY HẾT HẠN", key, real_ip, deviceId); save_db(db)
        return False, {"status": "error", "message": "Key đã hết hạn!"}

    if deviceId not in keyData.get('devices', []):
        if len(keyData.get('devices', [])) >= keyData.get('maxDevices', 1):
            add_log(db, "QUÁ GIỚI HẠN THIẾT BỊ", key, real_ip, deviceId); save_db(db)
            return False, {"status": "error", "message": "Key đã đạt giới hạn thiết bị!"}
        keyData.setdefault('devices', []).append(deviceId)

    add_log(db, "THÀNH CÔNG", key, real_ip, deviceId); save_db(db)
    return True, {"status": "success", "message": "Xác thực thành công!", "exp": keyData.get('exp'), "vip": keyData.get('vip', False), "devices": f"{len(keyData.get('devices', []))}/{keyData.get('maxDevices', 1)}"}

# ====================== CÁC API CỦA HỆ THỐNG TỪ XA ======================
@app.route('/api/check', methods=['POST'])
def check_key():
    data = request.get_json() or {}
    success, response = process_key_validation(data.get('key'), data.get('deviceId', 'Unknown'), get_real_ip())
    return jsonify(response)

@app.route('/api/remote_unlock', methods=['POST', 'OPTIONS'])
def remote_unlock():
    if request.method == 'OPTIONS': return jsonify({}), 200 # Xác nhận CORS
    
    data = request.get_json() or {}
    key, pin, deviceId = data.get('key'), data.get('pin'), data.get('deviceId', 'Unknown')
    if not pin: return jsonify({"status": "error", "message": "Thiếu mã PIN kết nối!"})
    
    success, response = process_key_validation(key, deviceId, get_real_ip())
    if success:
        if not response.get('vip'): return jsonify({"status": "error", "message": "Chỉ Key VIP mới mở khóa được Tool!"})
        remote_unlocks[pin] = key # Lưu Key vào RAM Server đợi Tool lấy
        response['message'] = "ĐÃ MỞ KHÓA TOOL TỪ XA THÀNH CÔNG!"
    return jsonify(response)

@app.route('/api/poll_unlock', methods=['POST'])
def poll_unlock():
    pin = request.json.get('pin')
    if pin in remote_unlocks: 
        return jsonify({"status": "success", "key": remote_unlocks.pop(pin)}) # Gửi cho Tool rồi xóa luôn
    return jsonify({"status": "pending"})

# ====================== QUẢN TRỊ ADMIN VÀ HTML ======================
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

multipliers = {'sec': 1000, 'min': 60000, 'hour': 3600000, 'day': 86400000, 'month': 2592000000, 'year': 31536000000}
@app.route('/admin/create', methods=['POST'])
def create_key():
    dur, t, md, qty, vip, pfx = request.form.get('duration'), request.form.get('type'), int(request.form.get('maxDevices', 1)), int(request.form.get('quantity', 1)), request.form.get('is_vip')=='on', request.form.get('prefix', 'LVT').strip() or 'LVT'
    db = load_db()
    for _ in range(qty):
        nk = f"{pfx}-{random.randint(1000000, 9999999)}"
        # ĐÃ FIX Ở ĐÂY: Sử dụng biến md (maxDevices) thay vì fix cứng 999
        db["keys"][nk] = {"exp": "permanent" if t == 'permanent' else "pending", "maxDevices": md, "devices": [], "status": "active", "vip": vip}
        if t != 'permanent': db["keys"][nk]["durationMs"] = int(dur) * multipliers.get(t, 86400000)
    save_db(db); return redirect('/')

@app.route('/admin/ban-ip', methods=['POST'])
def ban_ip():
    ip, dur, t = request.form.get('ip').strip(), request.form.get('duration'), request.form.get('type')
    db = load_db()
    db.setdefault("banned_ips", {})[ip] = "permanent" if t == 'permanent' else int(time.time() * 1000) + int(dur) * multipliers.get(t, 86400000)
    save_db(db); return redirect('/')

@app.route('/admin/unban-ip/<ip>')
def unban_ip(ip):
    db = load_db()
    if ip in db.get("banned_ips", {}): del db["banned_ips"][ip]; save_db(db)
    return redirect('/')

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
        elif action == 'reset-dev': db["keys"][key]['devices'] = []
        save_db(db)
    return redirect('/')

@app.route('/')
def dashboard():
    db = load_db()
    keys_html = ''
    for k, data in db["keys"].items():
        is_banned, is_vip = data.get('status') == 'banned', data.get('vip', False)
        status_badge = '<span class="badge bg-danger">BANNED</span>' if is_banned else ('<span class="badge bg-warning text-dark">VIP</span>' if is_vip else '<span class="badge bg-success">ACTIVE</span>')
        current_time, is_expired = int(time.time() * 1000), False
        if data.get('exp') == 'pending': exp_text = '<span class="text-info">Chờ kích hoạt</span>'
        elif data.get('exp') == 'permanent': exp_text = '<span class="text-success fw-bold">Vĩnh viễn</span>'
        else:
            is_expired = current_time > data.get('exp', 0)
            exp_text = f'<span class="{"text-danger fw-bold" if is_expired else "text-light"}">{time.strftime("%d/%m/%Y %H:%M", time.localtime(data.get("exp", 0) / 1000))}</span>'
        if is_expired: status_badge = '<span class="badge bg-secondary">HẾT HẠN</span>'
        keys_html += f'''
        <tr class="key-row" data-status="{ "banned" if is_banned else ("expired" if is_expired else "active") }">
            <td><div class="d-flex align-items-center"><strong class="me-2 text-info">{k}</strong><button class="btn btn-sm btn-outline-light copy-btn" onclick="copyText('{k}')" title="Sao chép">📋</button></div><div class="mt-1">{status_badge}</div></td>
            <td>{exp_text}</td><td><span class="badge bg-primary">{len(data.get('devices', []))}/{data.get('maxDevices', 1)}</span></td>
            <td><div class="btn-group btn-group-sm"><button class="btn btn-info" onclick="openExtendModal('{k}')">⏳</button><a href="/admin/action/add-dev/{k}" class="btn btn-success">+</a><a href="/admin/action/sub-dev/{k}" class="btn btn-warning">-</a><a href="/admin/action/reset-dev/{k}" class="btn btn-secondary">🔄</a><a href="/admin/action/{"unban" if is_banned else "ban"}/{k}" class="btn btn-{"light" if is_banned else "danger"}">{"Mở Khóa" if is_banned else "Khóa"}</a><a href="/admin/action/delete/{k}" class="btn btn-dark" onclick="return confirm('Bạn chắc chắn muốn xóa?')">🗑️</a></div></td>
        </tr>'''

    ips_html = ''
    for ip, exp in db.get("banned_ips", {}).items():
        exp_txt = "Vĩnh viễn" if exp == 'permanent' else time.strftime('%d/%m/%Y %H:%M', time.localtime(exp / 1000))
        ips_html += f'<tr><td>{ip}</td><td>{exp_txt}</td><td><a href="/admin/unban-ip/{ip}" class="btn btn-sm btn-success">Gỡ Ban</a></td></tr>'

    logs_html = ''
    for log in db.get("logs", []):
        color = "success" if log['action'] == "THÀNH CÔNG" else ("danger" if "BANNED" in log['action'] or "BỊ CHẶN" in log['action'] else "warning")
        logs_html += f'<tr><td><small class="text-muted">{time.strftime("%H:%M:%S %d/%m", time.localtime(log["time"]))}</small></td><td><span class="badge bg-{color}">{log["action"]}</span></td><td class="text-info">{log["key"]}</td><td><span class="badge bg-secondary">{log["ip"]}</span></td></tr>'

    return f'''
    <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>LVT PRO - Admin</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>:root {{ --bg-main: #0a0a12; --bg-card: #151525; --neon-cyan: #00ffcc; --neon-purple: #bd00ff; }} body {{ background: var(--bg-main); color: #e0e0e0; font-family: 'Segoe UI', Tahoma, sans-serif; }} .card {{ background: var(--bg-card); border: 1px solid #2a2a40; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }} h1, h4 {{ color: var(--neon-cyan); font-weight: 800; }} .btn-primary {{ background: linear-gradient(45deg, var(--neon-purple), #7a00ff); border: none; font-weight: bold; }} .table-container {{ max-height: 500px; overflow-y: auto; }} tbody tr:hover {{ background-color: rgba(0, 255, 204, 0.05) !important; }} #toastBox {{ position: fixed; bottom: 20px; right: 20px; z-index: 9999; }}</style></head><body class="p-2 p-md-4"><div id="toastBox"></div><div class="container-fluid"><div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary"><h1 class="m-0">⚡ LVT ADMIN</h1><div><a href="/logout" class="btn btn-outline-danger">Đăng xuất</a></div></div><div class="row g-4"><div class="col-lg-4"><div class="card p-3 mb-4"><h4>🔑 Tạo Key</h4><form action="/admin/create" method="POST" class="row g-2"><div class="col-6"><input type="text" name="prefix" class="form-control bg-dark text-light" placeholder="Prefix (LVT)"></div><div class="col-6"><input type="number" name="quantity" class="form-control bg-dark text-light" value="1"></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="min">Phút</option><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-6"><input type="number" name="maxDevices" class="form-control bg-dark text-light" placeholder="Max TB" value="1"></div><div class="col-6 d-flex align-items-end"><div class="form-check form-switch"><input class="form-check-input" type="checkbox" name="is_vip" id="vipSwitch"><label class="form-check-label text-warning" for="vipSwitch">Chế độ VIP</label></div></div><div class="col-12 mt-3"><button type="submit" class="btn btn-primary w-100">TẠO KEY</button></div></form></div><div class="card p-3"><h4 class="text-danger">🛡️ Block IP</h4><form action="/admin/ban-ip" method="POST" class="row g-2 mb-3"><div class="col-12"><input type="text" name="ip" class="form-control bg-dark text-light" placeholder="Nhập IP..." required></div><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Thời gian"></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="hour">Giờ</option><option value="day">Ngày</option><option value="permanent">Vĩnh viễn</option></select></div><div class="col-12"><button type="submit" class="btn btn-danger w-100">Ban IP</button></div></form><div class="table-container" style="max-height:200px;"><table class="table table-dark table-sm mb-0"><thead><tr><th>IP</th><th>Hạn</th><th>Xóa</th></tr></thead><tbody>{ips_html}</tbody></table></div></div></div><div class="col-lg-8"><div class="card p-3 mb-4"><div class="d-flex justify-content-between align-items-center mb-3"><h4>📋 Quản Lý Key</h4><div class="d-flex gap-2"><select id="statusFilter" class="form-select form-select-sm bg-dark text-light" onchange="filterTable()"><option value="all">Tất cả</option><option value="active">Hoạt động</option><option value="expired">Hết hạn</option><option value="banned">Bị khóa</option></select><input type="text" id="searchInput" class="form-control form-control-sm bg-dark text-light" placeholder="Tìm Key..." onkeyup="filterTable()"></div></div><div class="table-container"><table class="table table-dark table-hover mb-0 align-middle"><thead><tr><th>Key</th><th>Hạn</th><th>Thiết bị</th><th>Điều Khiển</th></tr></thead><tbody id="keyTableBody">{keys_html}</tbody></table></div></div><div class="card p-3"><h4>📡 Lịch sử Logs</h4><div class="table-container" style="max-height:250px;"><table class="table table-dark table-sm table-striped mb-0"><thead><tr><th>Time</th><th>Trạng thái</th><th>Key</th><th>IP</th></tr></thead><tbody>{logs_html}</tbody></table></div></div></div></div></div><div class="modal fade" id="extendModal" tabindex="-1" data-bs-theme="dark"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content" style="background:var(--bg-card);"><div class="modal-header"><h5 class="modal-title">⏳ Gia hạn Key</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><form action="/admin/extend" method="POST"><div class="modal-body"><input type="hidden" name="key" id="extendKeyInput"><p>Key: <strong id="extendKeyDisplay" class="text-info"></strong></p><div class="row g-2"><div class="col-6"><input type="number" name="duration" class="form-control bg-dark text-light" required></div><div class="col-6"><select name="type" class="form-select bg-dark text-light"><option value="hour">Giờ</option><option value="day">Ngày</option><option value="month">Tháng</option></select></div></div></div><div class="modal-footer"><button type="submit" class="btn btn-primary w-100">Gia hạn</button></div></form></div></div></div><script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script><script>function copyText(text) {{ navigator.clipboard.writeText(text); alert("Đã copy: " + text); }} function filterTable() {{ let s = document.getElementById('searchInput').value.toLowerCase(), f = document.getElementById('statusFilter').value; document.querySelectorAll('.key-row').forEach(r => {{ r.style.display = (r.innerText.toLowerCase().includes(s) && (f==='all' || r.dataset.status===f)) ? '' : 'none'; }}); }} function openExtendModal(key) {{ document.getElementById('extendKeyInput').value = key; document.getElementById('extendKeyDisplay').innerText = key; new bootstrap.Modal(document.getElementById('extendModal')).show(); }}</script></body></html>
    '''

def render_login_html():
    return '''<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Login - LVT PRO</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"><style>body { background: #0a0a12; display: flex; justify-content: center; align-items: center; height: 100vh; } .login-box { background: #151525; padding: 40px; border-radius: 15px; border: 1px solid #00ffcc; text-align: center; } h2 { color: #00ffcc; margin-bottom: 30px; } input { background: #0a0a12 !important; color: white !important; border: 1px solid #333 !important; } .btn-login { background: linear-gradient(45deg, #00ffcc, #bd00ff); width: 100%; margin-top: 20px; font-weight:bold;}</style></head><body><div class="login-box"><h2>LVT SYSTEM</h2><form method="POST"><input type="password" name="password" class="form-control mb-3" placeholder="Nhập mật khẩu Admin..." required><button type="submit" class="btn btn-login text-white">XÁC NHẬN</button></form></div></body></html>'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
