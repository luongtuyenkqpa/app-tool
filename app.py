import os, json, time, threading
from flask import Flask, request, jsonify, make_response, redirect, session
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.environ.get("SECRET_KEY", "ffmax_pro_2026_auth")

DB_FILE = "db.json"
db_lock = threading.Lock()
log_history = []
log_lock = threading.Lock()
GLOBAL_DB = {"verified": {}, "blocked": {}}

def load_db():
    global GLOBAL_DB
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                GLOBAL_DB = json.load(f)
                if "verified" not in GLOBAL_DB: GLOBAL_DB["verified"] = {}
                if "blocked" not in GLOBAL_DB: GLOBAL_DB["blocked"] = {}
    except: GLOBAL_DB = {"verified": {}, "blocked": {}}

def save_db():
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(GLOBAL_DB, f, indent=2, ensure_ascii=False)
    except: pass

load_db()

def add_log(uid, status):
    ts = time.strftime('%d/%m %H:%M:%S')
    with log_lock:
        log_history.insert(0, {"time": ts, "id": uid, "status": status})
        if len(log_history) > 150: log_history.pop()

def check_verified(uid):
    with db_lock:
        exp = GLOBAL_DB["verified"].get(str(uid))
        if exp and exp > time.time(): return True
        if exp:
            del GLOBAL_DB["verified"][str(uid)]
            save_db()
        return False

def get_remaining(uid):
    exp = GLOBAL_DB["verified"].get(str(uid), 0)
    return max(0, int(exp - time.time()))

def add_verified(uid, seconds):
    with db_lock:
        GLOBAL_DB["verified"][str(uid)] = time.time() + seconds
        GLOBAL_DB["blocked"].pop(str(uid), None)
        save_db()

def extend_verified(uid, seconds):
    with db_lock:
        current = GLOBAL_DB["verified"].get(str(uid), time.time())
        if current < time.time(): current = time.time()
        GLOBAL_DB["verified"][str(uid)] = current + seconds
        save_db()

def remove_verified(uid):
    with db_lock:
        GLOBAL_DB["verified"].pop(str(uid), None)
        save_db()

def add_blocked(uid):
    with db_lock:
        if str(uid) not in GLOBAL_DB["blocked"]:
            GLOBAL_DB["blocked"][str(uid)] = int(time.time())
            save_db()

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

def fmt_remaining(secs):
    if secs <= 0: return "Hết hạn"
    d, r = divmod(secs, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = []
    if d: parts.append(f"{d} Ngày")
    if h: parts.append(f"{h} Giờ")
    if m: parts.append(f"{m} Phút")
    if not parts: parts.append(f"{s} Giây")
    return " ".join(parts)

# =====================================================
# GIAO DIỆN WEB ADMIN (NÂNG CẤP PRO)
# =====================================================
ADMIN_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin Dashboard Pro</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
<style>
:root {--bg:#0f172a;--surface:#1e293b;--primary:#3b82f6;--secondary:#0ea5e9;--success:#10b981;--danger:#ef4444;--warn:#f59e0b;--text:#f8fafc;--text-muted:#94a3b8;--border:#334155;}
* {margin:0;padding:0;box-sizing:border-box;font-family:'Inter',sans-serif;}
body {background:var(--bg);color:var(--text);padding:20px;min-height:100vh;}
.container {max-width:1100px;margin:0 auto;}
.header {display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid var(--border);}
.header h1 {font-size:22px;font-weight:800;background:linear-gradient(to right,var(--secondary),var(--success));-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.header .logout {color:var(--danger);text-decoration:none;font-weight:600;padding:8px 16px;border:1px solid var(--danger);border-radius:8px;transition:0.2s;}
.header .logout:hover {background:var(--danger);color:#fff;}
.stats {display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px;}
.stat-card {background:var(--surface);padding:20px;border-radius:12px;border:1px solid var(--border);text-align:center;box-shadow:0 4px 6px rgba(0,0,0,0.1);}
.stat-card h3 {font-size:12px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;}
.stat-card .num {font-size:32px;font-weight:800;}
.stat-card.active .num {color:var(--success);}
.stat-card.blocked .num {color:var(--danger);}
.stat-card.logs .num {color:var(--warn);}
.card {background:var(--surface);border-radius:12px;border:1px solid var(--border);margin-bottom:24px;overflow:hidden;box-shadow:0 4px 6px rgba(0,0,0,0.1);}
.card-header {padding:16px 20px;border-bottom:1px solid var(--border);font-weight:600;font-size:15px;display:flex;justify-content:space-between;align-items:center;}
.card-body {padding:20px;}
form {display:flex;gap:10px;flex-wrap:wrap;}
input, select {background:var(--bg);color:var(--text);border:1px solid var(--border);padding:10px 14px;border-radius:8px;outline:none;font-size:14px;transition:0.2s;}
input:focus, select:focus {border-color:var(--primary);box-shadow:0 0 0 3px rgba(59,130,246,0.2);}
.btn {padding:10px 16px;border-radius:8px;font-weight:600;border:none;cursor:pointer;transition:0.2s;font-size:14px;}
.btn-primary {background:var(--primary);color:#fff;}
.btn-primary:hover {background:#2563eb;}
.btn-success {background:var(--success);color:#fff;}
.btn-success:hover {background:#059669;}
.btn-danger {background:transparent;border:1px solid var(--danger);color:var(--danger);}
.btn-danger:hover {background:var(--danger);color:#fff;}
.table-wrapper {overflow-x:auto;}
table {width:100%;border-collapse:collapse;text-align:left;}
th, td {padding:14px 20px;border-bottom:1px solid var(--border);white-space:nowrap;}
th {color:var(--text-muted);font-size:12px;text-transform:uppercase;font-weight:600;background:rgba(0,0,0,0.2);}
td {font-size:14px;}
.uid {font-family:monospace;color:var(--secondary);font-size:15px;font-weight:600;}
.badge {padding:4px 8px;border-radius:6px;font-size:11px;font-weight:800;letter-spacing:0.5px;}
.badge-ok {background:rgba(16,185,129,0.1);color:var(--success);border:1px solid var(--success);}
.badge-err {background:rgba(239,68,68,0.1);color:var(--danger);border:1px solid var(--danger);}
.time-left {color:var(--success);font-weight:600;}
.time-exp {color:var(--danger);font-weight:600;}
.flex-actions {display:flex;gap:6px;}
.quick-btn {text-decoration:none;padding:6px 12px;border-radius:6px;font-size:12px;font-weight:600;color:#fff;}
.qb-min {background:#64748b;}
.qb-hr {background:var(--warn);}
.qb-day {background:var(--success);}
.qb-mo {background:var(--primary);}
.quick-btn:hover {opacity:0.8;}
.auto-refresh {font-size:12px;color:var(--text-muted);}
@media (max-width:768px) {
    .header {flex-direction:column;gap:12px;}
    form {flex-direction:column;}
    input, select, .btn {width:100%;}
}
</style>
<script>setTimeout(()=>window.location.reload(), 20000);</script>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🛡️ ADMIN SYSTEM PRO</h1>
        <div>
            <span class="auto-refresh">🔄 Tự làm mới sau 20s | </span>
            <a href="/admin/logout" class="logout">ĐĂNG XUẤT</a>
        </div>
    </div>

    <div class="stats">
        <div class="stat-card active"><h3>Đang Hoạt Động</h3><div class="num">{{active}}</div></div>
        <div class="stat-card blocked"><h3>Bị Chặn Gần Đây</h3><div class="num">{{blocked}}</div></div>
        <div class="stat-card logs"><h3>Tổng Log</h3><div class="num">{{logs}}</div></div>
    </div>

    <div class="card">
        <div class="card-header" style="color:var(--secondary)">⚡ KÍCH HOẠT ID MỚI</div>
        <div class="card-body">
            <form action="/admin/add" method="GET">
                <input type="text" name="id" placeholder="Nhập ID Game..." required style="flex:1;min-width:200px">
                <input type="number" name="val" value="1" min="1" required style="width:80px">
                <select name="unit">
                    <option value="minutes">Phút</option>
                    <option value="hours">Giờ</option>
                    <option value="days" selected>Ngày</option>
                    <option value="months">Tháng</option>
                </select>
                <button type="submit" class="btn btn-primary">KÍCH HOẠT NGAY</button>
            </form>
        </div>
    </div>

    <div class="card">
        <div class="card-header">📋 DANH SÁCH ID ĐÃ DUYỆT</div>
        <div class="table-wrapper">
            <table>
                <thead><tr><th>ID Game</th><th>Thời Gian Còn Lại</th><th>Trạng Thái</th><th>Gia Hạn (Cộng Dồn)</th><th>Thao Tác</th></tr></thead>
                <tbody>{{verified_rows}}</tbody>
            </table>
        </div>
    </div>

    <div class="card" style="border-color:var(--danger)">
        <div class="card-header" style="color:var(--danger)">🚨 ID ĐANG BỊ CHẶN Ở SẢNH (CẦN DUYỆT)</div>
        <div class="table-wrapper">
            <table>
                <thead><tr><th>ID Game</th><th>Lần Bị Chặn Cuối</th><th>Duyệt Nhanh</th></tr></thead>
                <tbody>{{blocked_rows}}</tbody>
            </table>
        </div>
    </div>

    <div class="card">
        <div class="card-header">📡 NHẬT KÝ MÁY CHỦ</div>
        <div class="table-wrapper">
            <table>
                <thead><tr><th>Thời Gian</th><th>ID Game</th><th>Trạng Thái</th></tr></thead>
                <tbody>{{log_rows}}</tbody>
            </table>
        </div>
    </div>
</div>
</body>
</html>"""

LOGIN_HTML = """<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin Login</title><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet"><style>*{margin:0;padding:0;box-sizing:border-box;font-family:'Inter',sans-serif;}body{background:#0f172a;display:flex;align-items:center;justify-content:center;min-height:100vh;} .box{background:#1e293b;padding:40px;border-radius:16px;border:1px solid #334155;width:100%;max-width:360px;box-shadow:0 10px 25px rgba(0,0,0,0.5);} h2{color:#3b82f6;text-align:center;margin-bottom:24px;} input{width:100%;padding:12px;margin-bottom:16px;background:#0f172a;border:1px solid #334155;border-radius:8px;color:#fff;outline:none;} input:focus{border-color:#3b82f6;} button{width:100%;padding:12px;background:#3b82f6;color:#fff;border:none;border-radius:8px;font-weight:600;cursor:pointer;} button:hover{background:#2563eb;} .err{color:#ef4444;text-align:center;font-size:14px;margin-top:16px;}</style></head><body><div class="box"><h2>🛡️ ADMIN LOGIN</h2><form method="POST"><input type="password" name="password" placeholder="Nhập mật khẩu..." required autofocus><button type="submit">ĐĂNG NHẬP</button>{{error}}</form></div></body></html>"""

UNIT_SECONDS = {"minutes": 60, "hours": 3600, "days": 86400, "months": 2592000}

def render_admin():
    now = time.time()
    db = GLOBAL_DB
    verified = db.get("verified", {})
    blocked_db = db.get("blocked", {})
    active_count = sum(1 for e in verified.values() if e > now)
    blocked_count = sum(1 for bid in blocked_db if str(bid) not in verified or verified.get(str(bid),0) <= now)

    vrows = ""
    for uid, exp in sorted(verified.items(), key=lambda x: x[1], reverse=True):
        is_ok = exp > now
        rem = fmt_remaining(max(0, int(exp - now)))
        badge = '<span class="badge badge-ok">✅ HOẠT ĐỘNG</span>' if is_ok else '<span class="badge badge-err">❌ HẾT HẠN</span>'
        vrows += f"""<tr>
<td class="uid">{uid}</td>
<td class="{'time-left' if is_ok else 'time-exp'}">{rem}</td>
<td>{badge}</td>
<td>
  <form action="/admin/extend" method="GET" style="display:flex;gap:4px;flex-wrap:nowrap;margin:0">
    <input type="hidden" name="id" value="{uid}">
    <input type="number" name="val" value="1" min="1" style="width:60px;padding:6px;margin:0">
    <select name="unit" style="padding:6px;margin:0">
      <option value="minutes">Phút</option>
      <option value="hours">Giờ</option>
      <option value="days" selected>Ngày</option>
      <option value="months">Tháng</option>
    </select>
    <button type="submit" class="btn btn-success" style="padding:6px 12px">+</button>
  </form>
</td>
<td><a href="/admin/delete?id={uid}" class="btn btn-danger" onclick="return confirm('Xóa quyền truy cập của ID {uid}?')" style="text-decoration:none;padding:6px 12px;">XÓA</a></td>
</tr>"""
    if not vrows: vrows = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">Chưa có ID nào được cấp quyền</td></tr>'

    brows = ""
    for bid, bt in sorted(blocked_db.items(), key=lambda x: x[1], reverse=True):
        if str(bid) in verified and verified[str(bid)] > now: continue
        bt_str = time.strftime('%d/%m %H:%M', time.localtime(bt))
        brows += f"""<tr>
<td class="uid" style="color:var(--danger)">{bid}</td>
<td style="color:var(--text-muted)">{bt_str}</td>
<td class="flex-actions">
  <a href="/admin/add?id={bid}&val=30&unit=minutes" class="quick-btn qb-min">30 Phút</a>
  <a href="/admin/add?id={bid}&val=1&unit=hours" class="quick-btn qb-hr">1 Giờ</a>
  <a href="/admin/add?id={bid}&val=1&unit=days" class="quick-btn qb-day">1 Ngày</a>
  <a href="/admin/add?id={bid}&val=1&unit=months" class="quick-btn qb-mo">1 Tháng</a>
</td>
</tr>"""
    if not brows: brows = '<tr><td colspan="3" style="text-align:center;color:var(--text-muted)">Hiện không có ai bị chặn</td></tr>'

    lrows = ""
    with log_lock:
        for log in log_history[:50]:
            color = "var(--success)" if "THÀNH CÔNG" in log['status'] else ("var(--danger)" if "CHẶN" in log['status'] else "var(--warn)")
            lrows += f'<tr><td style="color:var(--text-muted)">{log["time"]}</td><td class="uid">{log["id"]}</td><td style="color:{color};font-weight:600">{log["status"]}</td></tr>'
    if not lrows: lrows = '<tr><td colspan="3" style="text-align:center;color:var(--text-muted)">Chưa có nhật ký hoạt động</td></tr>'

    return (ADMIN_HTML
        .replace("{{active}}", str(active_count))
        .replace("{{blocked}}", str(blocked_count))
        .replace("{{logs}}", str(len(log_history)))
        .replace("{{verified_rows}}", vrows)
        .replace("{{blocked_rows}}", brows)
        .replace("{{log_rows}}", lrows))

# =====================================================
# ADMIN ROUTES
# =====================================================
@app.route('/admin/login', methods=['GET','POST'])
@app.route('/admin_login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect('/admin')
        return LOGIN_HTML.replace("{{error}}", '<div class="err">❌ Sai mật khẩu truy cập!</div>')
    return LOGIN_HTML.replace("{{error}}", "")

@app.route('/admin')
def admin_panel():
    if not session.get('admin'): return redirect('/admin/login')
    return render_admin()

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect('/admin/login')

@app.route('/admin/add')
def admin_add():
    if not session.get('admin'): return redirect('/admin/login')
    uid = request.args.get('id','').strip()
    val = int(request.args.get('val', 1))
    unit = request.args.get('unit', 'days')
    if uid:
        secs = val * UNIT_SECONDS.get(unit, 86400)
        add_verified(uid, secs)
        unit_vn = {"minutes":"Phút","hours":"Giờ","days":"Ngày","months":"Tháng"}.get(unit, unit)
        add_log(uid, f"✅ Đã Duyệt: {val} {unit_vn}")
    return redirect('/admin')

@app.route('/admin/extend')
def admin_extend():
    if not session.get('admin'): return redirect('/admin/login')
    uid = request.args.get('id','').strip()
    val = int(request.args.get('val', 1))
    unit = request.args.get('unit', 'days')
    if uid:
        secs = val * UNIT_SECONDS.get(unit, 86400)
        extend_verified(uid, secs)
        unit_vn = {"minutes":"Phút","hours":"Giờ","days":"Ngày","months":"Tháng"}.get(unit, unit)
        add_log(uid, f"⏰ Cộng Dồn: {val} {unit_vn}")
    return redirect('/admin')

@app.route('/admin/delete')
def admin_delete():
    if not session.get('admin'): return redirect('/admin/login')
    uid = request.args.get('id','').strip()
    if uid:
        remove_verified(uid)
        add_log(uid, "🗑️ Hủy Quyền Kích Hoạt")
    return redirect('/admin')

# =====================================================
# GAME LOGIC - FIX ĐƠ LOAD GAME & HIỂN THỊ THÔNG BÁO XANH
# =====================================================
FAKE_JSON_BASE = {
    "status": "ok", "code": 0, "message": "success",
    "maintenance": False, "server_status": "online",
    "region": "VN", "version": "1.105.1",
    "data": {"is_white": True, "login_open": True, "server_time": 0, "cdn_url": "", "patch_version": "1.105.1"}
}

def game_resp(body, status=200, ctype="application/json"):
    r = make_response(body, status)
    r.headers.update({
        'Content-Type': f'{ctype}; charset=utf-8',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, User-Agent, Accept',
        'Cache-Control': 'no-cache, no-store',
        'Pragma': 'no-cache'
    })
    return r

def get_uid():
    # Lọc tìm UID cẩn thận để tránh nhầm lẫn config rác
    for k in ['id','accountId','account_id','uid','userId','openId']:
        v = request.args.get(k)
        if v and v.strip() and v.strip() != "null" and len(v.strip()) > 3: return v.strip()
    try:
        d = request.get_json(force=True, silent=True) or {}
        for k in ['id','accountId','account_id','uid','openId']:
            v = d.get(k) or d.get('data',{}).get(k)
            if v and str(v).strip() != "null": return str(v).strip()
    except: pass
    for k in ['id','accountId','uid']:
        v = request.form.get(k)
        if v and v.strip() and v.strip() != "null": return v.strip()
    return None

@app.route('/ping')
def ping(): return "OK", 200

@app.route('/', methods=['GET','POST','OPTIONS'])
@app.route('/<path:path>', methods=['GET','POST','OPTIONS'])
def game_handler(path=''):
    if path.startswith(('admin', 'api/')):
        from flask import abort; abort(404)

    if request.method == 'OPTIONS':
        return game_resp('', 200)

    # 1. FIX ĐƠ LOAD GAME (CỰC KỲ QUAN TRỌNG)
    # Nếu client tải file tĩnh (.json, .xml, .bundle...), LUÔN trả về HTTP 200 hợp lệ để % tiếp tục chạy.
    path_lower = path.lower()
    is_static_file = any(path_lower.endswith(ext) for ext in ['.txt', '.xml', '.json', '.u3d', '.bundle', '.bytes', '.png'])
    
    uid = get_uid()

    if uid:
        if check_verified(uid):
            add_log(uid, "✅ VÀO SẢNH THÀNH CÔNG")
            resp = FAKE_JSON_BASE.copy()
            resp.update({"status":"verified", "code":0, "remaining_seconds": get_remaining(uid)})
            resp["data"]["server_time"] = int(time.time())
            return game_resp(json.dumps(resp, ensure_ascii=False), 200)
        else:
            # Nếu chưa kích hoạt hoặc hết hạn
            add_blocked(uid)
            add_log(uid, "🚫 BỊ CHẶN Ở SẢNH")
            
            # Nếu request là xin lấy file tĩnh, vẫn cho nó lấy để qua đoạn load %
            if is_static_file:
                resp = FAKE_JSON_BASE.copy()
                resp["data"]["server_time"] = int(time.time())
                return game_resp(json.dumps(resp, ensure_ascii=False), 200)
            
            # 2. XỬ LÝ CHẶN SẢNH ĐĂNG NHẬP VỚI THÔNG BÁO MÀU XANH LÁ (Unity Rich Text)
            # Dùng màu lục sáng #00ff00 hoặc #00ff88 để game hiển thị
            block_msg = (
                f"<color=#00ff88><b>ID: {uid} CHƯA KÍCH HOẠT</b></color>\n\n"
                f"Tài khoản của bạn chưa được cấp quyền.\n"
                f"Vui lòng liên hệ Admin để kích hoạt ID!\n\n"
                f"<i>Lỗi máy chủ: 400</i>"
            )
            # Trả về 400 text/html để game móc ra thông báo báo lỗi ở màn hình đăng nhập
            return game_resp(block_msg, 400, "text/html")

    # Mặc định cho mọi request không có UID (game đang load % tài nguyên khởi tạo)
    resp = FAKE_JSON_BASE.copy()
    resp["data"]["server_time"] = int(time.time())
    
    # Fake file txt/xml nếu được yêu cầu
    if path_lower.endswith('.txt') or path_lower.endswith('.xml'):
        return game_resp("OK", 200, "text/plain")
        
    return game_resp(json.dumps(resp, ensure_ascii=False), 200)

# =====================================================
# KEEP ALIVE - Chống sập Render
# =====================================================
def keep_alive():
    import urllib.request
    time.sleep(15)
    while True:
        try:
            # Đổi URL bên dưới thành URL Render thực tế của bạn để tự nó ping chính nó
            urllib.request.urlopen("http://127.0.0.1:" + str(os.environ.get('PORT', 5000)) + "/ping", timeout=8)
        except: pass
        time.sleep(3 * 60) # Ping mỗi 3 phút

threading.Thread(target=keep_alive, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 GAME PROXY START: http://localhost:{port}")
    print(f"🔗 ADMIN DASHBOARD: http://localhost:{port}/admin (Pass: {ADMIN_PASSWORD})")
    app.run(host='0.0.0.0', port=port, threaded=True)
