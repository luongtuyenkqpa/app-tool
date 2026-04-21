import os
import json
import time
import random
import secrets
from flask import Flask, request, jsonify, redirect, make_response

app = Flask(__name__)
DB_FILE = './database.json'
ADMIN_PASSWORD = 'admin' # ← THAY MẬT KHẨU Ở ĐÂY

# ====================== QUẢN LÝ DATABASE (Tự động nâng cấp DB cũ) ======================
def load_db():
    if not os.path.exists(DB_FILE):
        return {"keys": {}, "logs": [], "banned_ips": {}}
    
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            if "keys" not in data:
                return {"keys": data, "logs": [], "banned_ips": {}}
            return data
        except:
            return {"keys": {}, "logs": [], "banned_ips": {}}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def add_log(db, action, key, ip, device):
    log_entry = {
        "time": int(time.time()),
        "action": action,
        "key": key,
        "ip": ip,
        "device": device
    }
    db.setdefault("logs", []).insert(0, log_entry)
    db["logs"] = db["logs"][:200]

def get_real_ip():
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
    return request.remote_addr

# ====================== AUTH ======================
@app.before_request
def check_auth():
    # Thêm '/client' vào danh sách không cần đăng nhập admin
    if request.path in ['/login', '/api/check', '/client']:
        return
    if request.path.startswith('/static'):
        return
    if request.cookies.get('admin_auth') != 'true':
        return redirect('/login')

# ====================== LOGIN ======================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            resp = make_response(redirect('/'))
            resp.set_cookie('admin_auth', 'true', max_age=86400 * 30)
            return resp
        return f"{render_login_html()}<script>alert('Sai mật khẩu!');</script>"
    return render_login_html()

@app.route('/logout')
def logout():
    resp = make_response(redirect('/login'))
    resp.set_cookie('admin_auth', '', max_age=0)
    return resp

# ====================== TRANG DÀNH CHO KHÁCH HÀNG (CLIENT) ======================
@app.route('/client')
def client_page():
    return render_client_html()

# ====================== API CHECK KEY & IP ======================
@app.route('/api/check', methods=['POST'])
def check_key():
    data = request.get_json() or {}
    key = data.get('key')
    deviceId = data.get('deviceId', 'Unknown')
    real_ip = get_real_ip()
    db = load_db()
    
    if real_ip in db.get("banned_ips", {}):
        ban_exp = db["banned_ips"][real_ip]
        if ban_exp == 'permanent' or int(time.time() * 1000) < ban_exp:
            add_log(db, "BỊ CHẶN IP", key or "N/A", real_ip, deviceId)
            save_db(db)
            return jsonify({"status": "error", "message": "IP của bạn đã bị khóa khỏi hệ thống!"})
        else:
            del db["banned_ips"][real_ip]

    if not key or key not in db["keys"]:
        add_log(db, "SAI KEY", key or "Trống", real_ip, deviceId)
        save_db(db)
        return jsonify({"status": "error", "message": "Key không tồn tại!"})

    keyData = db["keys"][key]
    
    if keyData.get('status') == 'banned':
        add_log(db, "KEY BỊ BANNED", key, real_ip, deviceId)
        save_db(db)
        return jsonify({"status": "error", "message": "Key này đã bị khóa (Banned)!"})

    if keyData.get('exp') == 'pending':
        keyData['exp'] = int(time.time() * 1000) + keyData.get('durationMs', 0)

    if keyData.get('exp') != 'permanent' and int(time.time() * 1000) > keyData.get('exp', 0):
        add_log(db, "KEY HẾT HẠN", key, real_ip, deviceId)
        save_db(db)
        return jsonify({"status": "error", "message": "Key đã hết hạn!"})

    if deviceId not in keyData.get('devices', []):
        if len(keyData.get('devices', [])) >= keyData.get('maxDevices', 1):
            add_log(db, "QUÁ GIỚI HẠN THIẾT BỊ", key, real_ip, deviceId)
            save_db(db)
            return jsonify({"status": "error", "message": "Key đã đạt giới hạn số thiết bị!"})
        keyData.setdefault('devices', []).append(deviceId)

    add_log(db, "THÀNH CÔNG", key, real_ip, deviceId)
    save_db(db)
    
    # ĐÃ THÊM: Trả về trạng thái VIP cho web Client xử lý giao diện
    return jsonify({
        "status": "success",
        "message": "Xác thực thành công!",
        "exp": keyData.get('exp'),
        "vip": keyData.get('vip', False), 
        "devices": f"{len(keyData.get('devices', []))}/{keyData.get('maxDevices', 1)}"
    })

# ====================== TẠO KEY & IP BANNING ======================
multipliers = {'sec': 1000, 'min': 60000, 'hour': 3600000, 'day': 86400000, 'month': 2592000000, 'year': 31536000000}

@app.route('/admin/create', methods=['POST'])
def create_key():
    duration = request.form.get('duration')
    type_ = request.form.get('type')
    maxDevices = int(request.form.get('maxDevices', 1))
    quantity = int(request.form.get('quantity', 1))
    is_vip = request.form.get('is_vip') == 'on'
    custom_prefix = request.form.get('prefix', 'LVT').strip() or 'LVT'
    
    db = load_db()

    for _ in range(quantity):
        newKey = f"{custom_prefix}-{random.randint(1000000, 9999999)}"
        if type_ == 'permanent':
            db["keys"][newKey] = {
                "exp": "permanent",
                "maxDevices": 999 if is_vip else maxDevices,
                "devices": [], "status": "active", "vip": is_vip
            }
        else:
            durationMs = int(duration) * multipliers.get(type_, 86400000)
            db["keys"][newKey] = {
                "exp": "pending",
                "durationMs": durationMs,
                "maxDevices": 999 if is_vip else maxDevices,
                "devices": [], "status": "active", "vip": is_vip
            }

    save_db(db)
    return redirect('/')

@app.route('/admin/ban-ip', methods=['POST'])
def ban_ip():
    ip = request.form.get('ip').strip()
    duration = request.form.get('duration')
    type_ = request.form.get('type')
    db = load_db()
    
    if type_ == 'permanent':
        db.setdefault("banned_ips", {})[ip] = "permanent"
    else:
        durationMs = int(duration) * multipliers.get(type_, 86400000)
        db.setdefault("banned_ips", {})[ip] = int(time.time() * 1000) + durationMs
        
    save_db(db)
    return redirect('/')

@app.route('/admin/unban-ip/<ip>')
def unban_ip(ip):
    db = load_db()
    if ip in db.get("banned_ips", {}):
        del db["banned_ips"][ip]
        save_db(db)
    return redirect('/')

# ====================== QUẢN LÝ KEY (EXTEND, ADD/SUB DEV, BAN) ======================
@app.route('/admin/extend', methods=['POST'])
def extend_key():
    key = request.form.get('key')
    duration = request.form.get('duration')
    type_ = request.form.get('type')
    db = load_db()
    
    if key in db["keys"]:
        k_data = db["keys"][key]
        if k_data.get('exp') != 'permanent' and k_data.get('exp') != 'pending':
            add_time_ms = int(duration) * multipliers.get(type_, 86400000)
            current_time = int(time.time() * 1000)
            base_time = k_data['exp'] if k_data['exp'] > current_time else current_time
            k_data['exp'] = base_time + add_time_ms
            save_db(db)
    return redirect('/')

@app.route('/admin/action/<action>/<key>')
def key_actions(action, key):
    db = load_db()
    if key in db["keys"]:
        if action == 'add-dev':
            db["keys"][key]['maxDevices'] += 1
        elif action == 'sub-dev' and db["keys"][key].get('maxDevices', 1) > 1:
            db["keys"][key]['maxDevices'] -= 1
        elif action == 'ban':
            db["keys"][key]['status'] = 'banned'
        elif action == 'unban':
            db["keys"][key]['status'] = 'active'
        elif action == 'delete':
            del db["keys"][key]
        elif action == 'reset-dev':
            db["keys"][key]['devices'] = []
        save_db(db)
    return redirect('/')

# ====================== GIAO DIỆN ADMIN ======================
@app.route('/')
def dashboard():
    db = load_db()
    
    keys_html = ''
    for k, data in db["keys"].items():
        is_banned = data.get('status') == 'banned'
        is_vip = data.get('vip', False)
        status_badge = '<span class="badge bg-danger">BANNED</span>' if is_banned else ('<span class="badge bg-warning text-dark">VIP</span>' if is_vip else '<span class="badge bg-success">ACTIVE</span>')
        
        current_time = int(time.time() * 1000)
        is_expired = False
        
        if data.get('exp') == 'pending':
            exp_text = '<span class="text-info">Chờ kích hoạt</span>'
        elif data.get('exp') == 'permanent':
            exp_text = '<span class="text-success fw-bold">Vĩnh viễn</span>'
        else:
            is_expired = current_time > data.get('exp', 0)
            time_str = time.strftime('%d/%m/%Y %H:%M', time.localtime(data.get('exp', 0) / 1000))
            exp_text = f'<span class="{"text-danger fw-bold" if is_expired else "text-light"}">{time_str}</span>'

        if is_expired: status_badge = '<span class="badge bg-secondary">HẾT HẠN</span>'

        keys_html += f'''
        <tr class="key-row" data-status="{ "banned" if is_banned else ("expired" if is_expired else "active") }">
            <td>
                <div class="d-flex align-items-center">
                    <strong class="me-2 text-info">{k}</strong>
                    <button class="btn btn-sm btn-outline-light copy-btn" onclick="copyText('{k}')" title="Sao chép">📋</button>
                </div>
                <div class="mt-1">{status_badge}</div>
            </td>
            <td>{exp_text}</td>
            <td><span class="badge bg-primary">{len(data.get('devices', []))}/{data.get('maxDevices', 1)}</span></td>
            <td>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-info" onclick="openExtendModal('{k}')" title="Gia hạn">⏳</button>
                    <a href="/admin/action/add-dev/{k}" class="btn btn-success" title="Thêm thiết bị">+</a>
                    <a href="/admin/action/sub-dev/{k}" class="btn btn-warning" title="Bớt thiết bị">-</a>
                    <a href="/admin/action/reset-dev/{k}" class="btn btn-secondary" title="Reset Máy">🔄</a>
                    <a href="/admin/action/{"unban" if is_banned else "ban"}/{k}" class="btn btn-{"light" if is_banned else "danger"}">{"Mở Khóa" if is_banned else "Khóa"}</a>
                    <a href="/admin/action/delete/{k}" class="btn btn-dark" onclick="return confirm('Bạn chắc chắn muốn xóa key này vĩnh viễn?')">🗑️</a>
                </div>
            </td>
        </tr>'''

    ips_html = ''
    for ip, exp in db.get("banned_ips", {}).items():
        if exp == 'permanent':
            exp_txt = "Vĩnh viễn"
        else:
            exp_txt = time.strftime('%d/%m/%Y %H:%M', time.localtime(exp / 1000))
        ips_html += f'<tr><td>{ip}</td><td>{exp_txt}</td><td><a href="/admin/unban-ip/{ip}" class="btn btn-sm btn-success">Gỡ Ban</a></td></tr>'

    logs_html = ''
    for log in db.get("logs", []):
        log_time = time.strftime('%H:%M:%S %d/%m', time.localtime(log['time']))
        color = "success" if log['action'] == "THÀNH CÔNG" else ("danger" if "BANNED" in log['action'] or "BỊ CHẶN" in log['action'] else "warning")
        logs_html += f'''
        <tr>
            <td><small class="text-muted">{log_time}</small></td>
            <td><span class="badge bg-{color}">{log['action']}</span></td>
            <td class="text-info">{log['key']}</td>
            <td><span class="badge bg-secondary">{log['ip']}</span></td>
        </tr>'''

    return f'''
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>LVT PRO - Admin System</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            :root {{ --bg-main: #0a0a12; --bg-card: #151525; --neon-cyan: #00ffcc; --neon-purple: #bd00ff; }}
            body {{ background: var(--bg-main); color: #e0e0e0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; overflow-x: hidden; }}
            .card {{ background: var(--bg-card); border: 1px solid #2a2a40; border-radius: 15px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5); transition: 0.3s; }}
            .card:hover {{ border-color: var(--neon-cyan); box-shadow: 0 0 15px rgba(0, 255, 204, 0.2); }}
            h1, h4 {{ color: var(--neon-cyan); text-transform: uppercase; font-weight: 800; letter-spacing: 1px; }}
            .btn-primary {{ background: linear-gradient(45deg, var(--neon-purple), #7a00ff); border: none; font-weight: bold; }}
            .btn-primary:hover {{ background: linear-gradient(45deg, #7a00ff, var(--neon-purple)); box-shadow: 0 0 10px var(--neon-purple); }}
            .table-container {{ max-height: 500px; overflow-y: auto; border-radius: 10px; border: 1px solid #2a2a40; }}
            ::-webkit-scrollbar {{ width: 8px; }}
            ::-webkit-scrollbar-track {{ background: var(--bg-card); }}
            ::-webkit-scrollbar-thumb {{ background: var(--neon-cyan); border-radius: 4px; }}
            ::-webkit-scrollbar-thumb:hover {{ background: white; }}
            .table-dark {{ --bs-table-bg: transparent; }}
            tbody tr {{ transition: 0.2s; }}
            tbody tr:hover {{ background-color: rgba(0, 255, 204, 0.05) !important; transform: scale(1.01); }}
            .copy-btn {{ padding: 2px 6px; font-size: 12px; border: none; background: rgba(255,255,255,0.1); }}
            .copy-btn:hover {{ background: var(--neon-cyan); color: black; }}
            #toastBox {{ position: fixed; bottom: 20px; right: 20px; z-index: 9999; }}
        </style>
    </head>
    <body class="p-2 p-md-4">
        <div id="toastBox"></div>
        <div class="container-fluid">
            <div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary">
                <h1 class="m-0">⚡ LVT <span style="color: white;">ADMIN</span></h1>
                <div>
                    <a href="/client" target="_blank" class="btn btn-outline-info me-2">Mở Web Client 🌐</a>
                    <a href="/logout" class="btn btn-outline-danger">Đăng xuất 🚪</a>
                </div>
            </div>

            <div class="row g-4">
                <div class="col-lg-4">
                    <div class="card p-3 mb-4">
                        <h4><span style="font-size:1.2rem;">🔑</span> Tạo Key Mới</h4>
                        <form action="/admin/create" method="POST" class="row g-2">
                            <div class="col-6">
                                <label class="form-label small text-muted">Prefix (Tùy chọn)</label>
                                <input type="text" name="prefix" class="form-control bg-dark text-light border-secondary" placeholder="LVT">
                            </div>
                            <div class="col-6">
                                <label class="form-label small text-muted">Số lượng tạo</label>
                                <input type="number" name="quantity" class="form-control bg-dark text-light border-secondary" value="1" min="1">
                            </div>
                            <div class="col-6">
                                <label class="form-label small text-muted">Thời lượng</label>
                                <input type="number" name="duration" class="form-control bg-dark text-light border-secondary" placeholder="VD: 30" required>
                            </div>
                            <div class="col-6">
                                <label class="form-label small text-muted">Đơn vị</label>
                                <select name="type" class="form-select bg-dark text-light border-secondary">
                                    <option value="min">Phút</option>
                                    <option value="hour">Giờ</option>
                                    <option value="day">Ngày</option>
                                    <option value="month">Tháng</option>
                                    <option value="permanent">Vĩnh viễn</option>
                                </select>
                            </div>
                            <div class="col-6">
                                <label class="form-label small text-muted">Max Thiết Bị</label>
                                <input type="number" name="maxDevices" class="form-control bg-dark text-light border-secondary" value="1" min="1">
                            </div>
                            <div class="col-6 d-flex align-items-end mb-1">
                                <div class="form-check form-switch">
                                    <input class="form-check-input" type="checkbox" name="is_vip" id="vipSwitch">
                                    <label class="form-check-label text-warning fw-bold" for="vipSwitch">Chế độ VIP 🌟</label>
                                </div>
                            </div>
                            <div class="col-12 mt-3">
                                <button type="submit" class="btn btn-primary w-100 py-2">TẠO KEY TỰ ĐỘNG</button>
                            </div>
                        </form>
                    </div>

                    <div class="card p-3">
                        <h4 class="text-danger"><span style="font-size:1.2rem;">🛡️</span> Block IP</h4>
                        <form action="/admin/ban-ip" method="POST" class="row g-2 mb-3">
                            <div class="col-12">
                                <input type="text" name="ip" class="form-control bg-dark text-light border-secondary" placeholder="Nhập IP cần Ban..." required>
                            </div>
                            <div class="col-6">
                                <input type="number" name="duration" class="form-control bg-dark text-light border-secondary" placeholder="Thời gian (VD: 1)">
                            </div>
                            <div class="col-6">
                                <select name="type" class="form-select bg-dark text-light border-secondary">
                                    <option value="hour">Giờ</option>
                                    <option value="day">Ngày</option>
                                    <option value="permanent">Vĩnh viễn</option>
                                </select>
                            </div>
                            <div class="col-12">
                                <button type="submit" class="btn btn-danger w-100">Búa Tạ IP 🔨</button>
                            </div>
                        </form>
                        
                        <div class="table-container" style="max-height: 200px;">
                            <table class="table table-dark table-sm mb-0">
                                <thead style="position: sticky; top: 0; background: var(--bg-card); z-index: 1;">
                                    <tr><th>IP Bị Khóa</th><th>Hạn</th><th>Xóa</th></tr>
                                </thead>
                                <tbody>{ips_html}</tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div class="col-lg-8">
                    <div class="card p-3 mb-4">
                        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
                            <h4><span style="font-size:1.2rem;">📋</span> Quản Lý Key</h4>
                            <div class="d-flex gap-2">
                                <select id="statusFilter" class="form-select form-select-sm bg-dark text-light" style="width: auto;" onchange="filterTable()">
                                    <option value="all">Tất cả trạng thái</option>
                                    <option value="active">Đang hoạt động</option>
                                    <option value="expired">Đã hết hạn</option>
                                    <option value="banned">Bị khóa</option>
                                </select>
                                <input type="text" id="searchInput" class="form-control form-control-sm bg-dark text-light" placeholder="🔍 Tìm kiếm Key..." onkeyup="filterTable()">
                            </div>
                        </div>
                        
                        <div class="table-container">
                            <table class="table table-dark table-hover mb-0 align-middle">
                                <thead style="position: sticky; top: 0; background: #1a1a2e; z-index: 1; border-bottom: 2px solid var(--neon-cyan);">
                                    <tr>
                                        <th>Key & Trạng Thái</th>
                                        <th>Thời hạn</th>
                                        <th>Thiết bị</th>
                                        <th>Bảng Điều Khiển</th>
                                    </tr>
                                </thead>
                                <tbody id="keyTableBody">{keys_html}</tbody>
                            </table>
                        </div>
                    </div>

                    <div class="card p-3">
                        <h4><span style="font-size:1.2rem;">📡</span> Lịch sử hoạt động (Live Logs)</h4>
                        <div class="table-container" style="max-height: 250px;">
                            <table class="table table-dark table-sm table-striped mb-0">
                                <thead style="position: sticky; top: 0; background: var(--bg-card); z-index: 1;">
                                    <tr>
                                        <th>Thời gian</th>
                                        <th>Trạng thái</th>
                                        <th>Key thao tác</th>
                                        <th>IP Máy</th>
                                    </tr>
                                </thead>
                                <tbody>{logs_html}</tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="modal fade" id="extendModal" tabindex="-1" data-bs-theme="dark">
            <div class="modal-dialog modal-sm modal-dialog-centered">
                <div class="modal-content" style="background: var(--bg-card); border: 1px solid var(--neon-cyan);">
                    <div class="modal-header border-secondary">
                        <h5 class="modal-title text-info">⏳ Gia hạn Key</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <form action="/admin/extend" method="POST">
                        <div class="modal-body">
                            <input type="hidden" name="key" id="extendKeyInput">
                            <p class="small text-muted mb-2">Đang cộng thêm giờ cho key: <strong id="extendKeyDisplay" class="text-light"></strong></p>
                            <div class="row g-2">
                                <div class="col-6">
                                    <input type="number" name="duration" class="form-control bg-dark text-light" placeholder="Số" required>
                                </div>
                                <div class="col-6">
                                    <select name="type" class="form-select bg-dark text-light">
                                        <option value="hour">Giờ</option>
                                        <option value="day">Ngày</option>
                                        <option value="month">Tháng</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer border-secondary">
                            <button type="submit" class="btn btn-primary w-100">Bơm Thời Gian 🚀</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            function copyText(text) {{
                navigator.clipboard.writeText(text).then(() => {{
                    showToast("✅ Đã sao chép: " + text);
                }});
            }}

            function showToast(msg) {{
                let toastBox = document.getElementById('toastBox');
                let toast = document.createElement('div');
                toast.classList.add('bg-success', 'text-white', 'px-3', 'py-2', 'rounded', 'mb-2', 'shadow');
                toast.style.transition = '0.5s';
                toast.innerText = msg;
                toastBox.appendChild(toast);
                setTimeout(() => {{ toast.style.opacity = '0'; setTimeout(() => toast.remove(), 500); }}, 2000);
            }}

            function filterTable() {{
                let searchVal = document.getElementById('searchInput').value.toLowerCase();
                let statusVal = document.getElementById('statusFilter').value;
                let rows = document.querySelectorAll('.key-row');
                
                rows.forEach(row => {{
                    let textMatch = row.innerText.toLowerCase().includes(searchVal);
                    let statusMatch = (statusVal === 'all') || (row.getAttribute('data-status') === statusVal);
                    
                    if (textMatch && statusMatch) {{
                        row.style.display = '';
                    }} else {{
                        row.style.display = 'none';
                    }}
                }});
            }}

            function openExtendModal(key) {{
                document.getElementById('extendKeyInput').value = key;
                document.getElementById('extendKeyDisplay').innerText = key;
                new bootstrap.Modal(document.getElementById('extendModal')).show();
            }}
        </script>
    </body>
    </html>
    '''

def render_login_html():
    return '''
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Login - LVT PRO</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background: #0a0a12; display: flex; justify-content: center; align-items: center; height: 100vh; }
            .login-box { background: #151525; padding: 40px; border-radius: 15px; border: 1px solid #00ffcc; box-shadow: 0 0 20px rgba(0,255,204,0.3); width: 100%; max-width: 400px; text-align: center; }
            h2 { color: #00ffcc; font-weight: bold; margin-bottom: 30px; letter-spacing: 2px; }
            input { background: #0a0a12 !important; color: white !important; border: 1px solid #333 !important; }
            input:focus { border-color: #00ffcc !important; box-shadow: none !important; }
            .btn-login { background: linear-gradient(45deg, #00ffcc, #bd00ff); border: none; font-weight: bold; padding: 10px; width: 100%; margin-top: 20px; transition: 0.3s; }
            .btn-login:hover { transform: scale(1.05); box-shadow: 0 0 15px #bd00ff; color: white; }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h2>LVT SYSTEM</h2>
            <form method="POST">
                <input type="password" name="password" class="form-control mb-3" placeholder="Nhập mật khẩu Admin..." required>
                <button type="submit" class="btn btn-login text-white">XÁC NHẬN ĐĂNG NHẬP</button>
            </form>
        </div>
    </body>
    </html>
    '''

def render_client_html():
    return '''
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>LVT - Premium Client Portal</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Roboto:wght@300;400;700&display=swap');

            :root {
                --bg: #05050A;
                --primary: #00ffcc;
                --primary-glow: rgba(0, 255, 204, 0.5);
                --vip: #ffd700;
                --vip-glow: rgba(255, 215, 0, 0.5);
                --danger: #ff3366;
                --glass: rgba(20, 20, 35, 0.6);
                --border: rgba(255, 255, 255, 0.1);
            }

            body {
                margin: 0; padding: 0; font-family: 'Roboto', sans-serif;
                background: radial-gradient(circle at center, #111122 0%, var(--bg) 100%);
                color: white; min-height: 100vh; display: flex;
                justify-content: center; align-items: center; overflow: hidden;
            }

            .grid-bg {
                position: absolute; top: 0; left: 0; width: 100vw; height: 100vh;
                background-image: linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px);
                background-size: 40px 40px;
                transform: perspective(500px) rotateX(60deg) translateY(-100px) translateZ(-200px);
                animation: gridMove 20s linear infinite; z-index: -1; opacity: 0.3;
            }
            @keyframes gridMove { 0% { background-position: 0 0; } 100% { background-position: 0 40px; } }

            .glass-panel {
                background: var(--glass); backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px);
                border: 1px solid var(--border); border-radius: 20px; padding: 40px;
                width: 100%; max-width: 450px; box-shadow: 0 0 40px rgba(0,0,0,0.8);
                transition: all 0.5s ease; position: relative; z-index: 10;
            }

            .glass-panel:hover { border-color: var(--primary); box-shadow: 0 0 30px var(--primary-glow); }

            body.vip-mode .glass-panel { border-color: var(--vip); box-shadow: 0 0 50px var(--vip-glow); }
            body.vip-mode .title { color: var(--vip); text-shadow: 0 0 10px var(--vip); }
            body.vip-mode .btn-login { background: linear-gradient(45deg, #ff9900, #ffd700); color: black; box-shadow: 0 0 15px var(--vip-glow); }

            .title {
                font-family: 'Rajdhani', sans-serif; font-size: 2.5rem; font-weight: 700;
                text-align: center; margin-bottom: 30px; color: var(--primary);
                letter-spacing: 2px; text-transform: uppercase;
            }

            .input-group { position: relative; margin-bottom: 25px; }
            .input-group i { position: absolute; left: 15px; top: 50%; transform: translateY(-50%); color: #888; font-size: 1.2rem; }
            .form-control {
                width: 100%; padding: 15px 15px 15px 45px; background: rgba(0, 0, 0, 0.5);
                border: 1px solid var(--border); border-radius: 10px; color: white;
                font-size: 1rem; outline: none; box-sizing: border-box; transition: 0.3s;
            }
            .form-control:focus { border-color: var(--primary); box-shadow: 0 0 10px var(--primary-glow); }

            .btn-login {
                width: 100%; padding: 15px; background: linear-gradient(45deg, #00ffcc, #0066ff);
                border: none; border-radius: 10px; color: white; font-weight: bold;
                font-size: 1.1rem; cursor: pointer; transition: 0.3s; text-transform: uppercase; letter-spacing: 1px;
            }
            .btn-login:hover { transform: translateY(-3px); box-shadow: 0 10px 20px var(--primary-glow); }

            #dashboardView { display: none; text-align: center; }
            .info-box {
                background: rgba(0,0,0,0.4); border: 1px solid var(--border);
                border-radius: 10px; padding: 15px; margin-bottom: 15px;
                display: flex; justify-content: space-between; align-items: center;
            }
            .info-box span { color: #aaa; font-size: 0.9rem; }
            .info-box strong { font-size: 1.1rem; }
            
            .premium-feature { margin-top: 20px; padding: 20px; border-radius: 10px; border: 1px dashed var(--border); background: rgba(255,255,255,0.02); }
            .locked { opacity: 0.5; filter: grayscale(100%); cursor: not-allowed; }
            .hwid-text { text-align: center; font-size: 0.8rem; color: #666; margin-top: 20px; font-family: monospace; }

            #toastContainer { position: fixed; top: 20px; right: 20px; z-index: 9999; }
            .toast {
                background: var(--glass); border-left: 4px solid var(--primary); color: white;
                padding: 15px 25px; margin-bottom: 10px; border-radius: 5px; box-shadow: 0 5px 15px rgba(0,0,0,0.5);
                transform: translateX(120%); transition: transform 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                display: flex; align-items: center; gap: 10px; backdrop-filter: blur(10px);
            }
            .toast.show { transform: translateX(0); }
            .toast.error { border-left-color: var(--danger); }
            .toast.error i { color: var(--danger); }
            .toast.success i { color: var(--primary); }
            .toast.vip { border-left-color: var(--vip); }
            .toast.vip i { color: var(--vip); }
        </style>
    </head>
    <body>
        <div class="grid-bg"></div>
        <div id="toastContainer"></div>

        <div class="glass-panel" id="mainPanel">
            <div id="loginView">
                <div class="title">LVT ACCESS</div>
                <div class="input-group">
                    <i class="fas fa-key"></i>
                    <input type="text" id="keyInput" class="form-control" placeholder="Nhập Key của bạn..." autocomplete="off">
                </div>
                <button class="btn-login" onclick="attemptLogin()" id="loginBtn">
                    <i class="fas fa-sign-in-alt"></i> KÍCH HOẠT HỆ THỐNG
                </button>
                <div class="hwid-text">Device ID: <span id="hwidDisplay">Loading...</span></div>
            </div>

            <div id="dashboardView">
                <div class="title" id="welcomeTitle">WELCOME</div>
                
                <div class="info-box">
                    <span><i class="far fa-clock"></i> Thời hạn</span>
                    <strong id="expDisplay" class="text-primary">Đang tải...</strong>
                </div>
                
                <div class="info-box">
                    <span><i class="fas fa-desktop"></i> Thiết bị</span>
                    <strong id="devDisplay">0/0</strong>
                </div>

                <div class="premium-feature" id="vipSection">
                    <h4 style="margin:0 0 10px 0; color:var(--vip); font-family:'Rajdhani'"><i class="fas fa-crown"></i> CÔNG CỤ VIP</h4>
                    <p style="font-size: 0.85rem; color: #aaa;">Các tính năng độc quyền chỉ dành cho tài khoản VIP.</p>
                    <button class="btn-login" style="padding: 10px; font-size: 0.9rem;" onclick="showToast('Đang khởi chạy Tool VIP...', 'vip')">MỞ CÔNG CỤ</button>
                </div>

                <button class="btn-login" style="margin-top:20px; background: rgba(255,51,102,0.2); border: 1px solid var(--danger);" onclick="logout()">ĐĂNG XUẤT</button>
            </div>
        </div>

        <script>
            let deviceId = localStorage.getItem('lvt_hwid');
            if (!deviceId) {
                deviceId = 'PC-' + Math.random().toString(36).substring(2, 10).toUpperCase();
                localStorage.setItem('lvt_hwid', deviceId);
            }
            document.getElementById('hwidDisplay').innerText = deviceId;

            window.onload = () => {
                const savedKey = localStorage.getItem('lvt_saved_key');
                if (savedKey) {
                    document.getElementById('keyInput').value = savedKey;
                    attemptLogin(true);
                }
            }

            function showToast(message, type = 'success') {
                const container = document.getElementById('toastContainer');
                const toast = document.createElement('div');
                toast.className = `toast ${type}`;
                
                let icon = 'fa-check-circle';
                if(type === 'error') icon = 'fa-exclamation-circle';
                if(type === 'vip') icon = 'fa-crown';

                toast.innerHTML = `<i class="fas ${icon}"></i> <span>${message}</span>`;
                container.appendChild(toast);
                setTimeout(() => toast.classList.add('show'), 10);
                setTimeout(() => {
                    toast.classList.remove('show');
                    setTimeout(() => toast.remove(), 400);
                }, 3000);
            }

            async function attemptLogin(isAuto = false) {
                const key = document.getElementById('keyInput').value.trim();
                const btn = document.getElementById('loginBtn');
                
                if (!key) {
                    showToast('Vui lòng nhập Key!', 'error');
                    return;
                }

                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ĐANG XÁC THỰC...';
                btn.style.opacity = '0.7';

                try {
                    const response = await fetch('/api/check', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ key: key, deviceId: deviceId })
                    });

                    const data = await response.json();

                    if (data.status === 'success') {
                        if(!isAuto) showToast(data.message, data.vip ? 'vip' : 'success');
                        if(data.vip && !isAuto) showToast('Kích hoạt chế độ VIP!', 'vip');
                        
                        localStorage.setItem('lvt_saved_key', key);
                        renderDashboard(key, data);
                    } else {
                        showToast(data.message, 'error');
                        localStorage.removeItem('lvt_saved_key');
                    }
                } catch (error) {
                    showToast('Không thể kết nối đến máy chủ!', 'error');
                    console.error(error);
                } finally {
                    btn.innerHTML = '<i class="fas fa-sign-in-alt"></i> KÍCH HOẠT HỆ THỐNG';
                    btn.style.opacity = '1';
                }
            }

            function renderDashboard(key, data) {
                document.getElementById('loginView').style.display = 'none';
                document.getElementById('dashboardView').style.display = 'block';
                
                const vipSection = document.getElementById('vipSection');
                if (data.vip) {
                    document.body.classList.add('vip-mode');
                    document.getElementById('welcomeTitle').innerHTML = '👑 VIP MEMBER';
                    vipSection.classList.remove('locked');
                } else {
                    document.body.classList.remove('vip-mode');
                    document.getElementById('welcomeTitle').innerHTML = 'USER ACCESS';
                    vipSection.classList.add('locked');
                }

                let expText = '';
                if (data.exp === 'permanent') {
                    expText = 'Vĩnh viễn';
                } else {
                    const date = new Date(data.exp);
                    expText = date.toLocaleString('vi-VN');
                }
                
                document.getElementById('expDisplay').innerText = expText;
                if(data.vip) document.getElementById('expDisplay').style.color = 'var(--vip)';

                document.getElementById('devDisplay').innerText = data.devices;
            }

            function logout() {
                localStorage.removeItem('lvt_saved_key');
                document.body.classList.remove('vip-mode');
                document.getElementById('dashboardView').style.display = 'none';
                document.getElementById('loginView').style.display = 'block';
                document.getElementById('keyInput').value = '';
                showToast('Đã đăng xuất an toàn.', 'success');
            }
        </script>
    </body>
    </html>
    '''

if __name__ == '__main__':
    print("=========================================")
    print("🚀 LVT PRO SYSTEM V2.0 ĐANG KHỞI CHẠY...")
    print("=========================================")
    
    # Render sẽ cung cấp một PORT động. Nếu không có (chạy local), nó sẽ dùng mặc định 5000.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
