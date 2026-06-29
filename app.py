import os, json, time, threading
from flask import Flask, request, jsonify, make_response, redirect, session, render_template_string
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.environ.get("SECRET_KEY", "ffmax_auth_2026_secret")

DB_FILE = "db.json"
db_lock = threading.Lock()
log_history = []
log_lock = threading.Lock()
GLOBAL_DB = {"verified": {}, "blocked": {}}

def load_db():
    global GLOBAL_DB
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r') as f:
                GLOBAL_DB = json.load(f)
                if "verified" not in GLOBAL_DB: GLOBAL_DB["verified"] = {}
                if "blocked" not in GLOBAL_DB: GLOBAL_DB["blocked"] = {}
    except: GLOBAL_DB = {"verified": {}, "blocked": {}}

def save_db():
    try:
        with open(DB_FILE, 'w') as f:
            json.dump(GLOBAL_DB, f, indent=2, ensure_ascii=False)
    except: pass

load_db()

def add_log(uid, status):
    ts = time.strftime('%d/%m %H:%M:%S')
    with log_lock:
        log_history.insert(0, {"time": ts, "id": uid, "status": status})
        if len(log_history) > 100: log_history.pop()

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
    if d: parts.append(f"{d}n")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}p")
    if not parts: parts.append(f"{s}s")
    return " ".join(parts)

ADMIN_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="20">
<title>FF MAX Auth Admin</title>
<style>
:root{--bg:#0a0e1a;--card:#111827;--border:#1e3a5f;--primary:#00d4ff;--success:#00ff88;--danger:#ff4757;--warn:#ffa502;--text:#e2e8f0;--muted:#64748b}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',monospace;min-height:100vh;padding:12px}
.header{text-align:center;padding:16px 0 20px;border-bottom:1px solid var(--border);margin-bottom:16px}
.header h1{font-size:18px;font-weight:800;letter-spacing:3px;text-transform:uppercase;background:linear-gradient(135deg,#00d4ff,#00ff88);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header p{color:var(--muted);font-size:11px;margin-top:4px}
.topbar{display:flex;justify-content:flex-end;margin-bottom:12px}
.btn-logout{color:var(--danger);border:1px solid var(--danger);padding:5px 14px;border-radius:6px;font-size:11px;text-decoration:none;transition:.2s}
.btn-logout:hover{background:var(--danger);color:#fff}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px}
.stat{background:var(--card);border-radius:10px;padding:14px;text-align:center;border-top:3px solid}
.stat.s1{border-color:var(--success)}
.stat.s2{border-color:var(--danger)}
.stat.s3{border-color:var(--warn)}
.stat-n{font-size:28px;font-weight:900;margin-bottom:2px}
.stat.s1 .stat-n{color:var(--success)}
.stat.s2 .stat-n{color:var(--danger)}
.stat.s3 .stat-n{color:var(--warn)}
.stat-l{font-size:9px;text-transform:uppercase;letter-spacing:1px;color:var(--muted)}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px;margin-bottom:14px}
.card-head{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--primary);border-bottom:1px solid var(--border);padding-bottom:10px;margin-bottom:12px}
.card-head.warn{color:var(--warn)}
.card-head.danger{color:var(--danger)}
.form-grid{display:grid;grid-template-columns:1fr auto;gap:8px;margin-bottom:8px}
.form-row{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.inp{background:#0f172a;color:var(--text);border:1px solid var(--border);border-radius:6px;padding:9px 12px;font-size:13px;outline:none;transition:.2s}
.inp:focus{border-color:var(--primary);box-shadow:0 0 0 2px rgba(0,212,255,.15)}
.inp-id{flex:1;min-width:120px}
.inp-sm{width:60px}
.inp-unit{background:#0f172a;color:var(--text);border:1px solid var(--border);border-radius:6px;padding:9px 8px;font-size:12px;outline:none}
.btn{border:none;border-radius:6px;padding:9px 14px;font-size:12px;font-weight:700;cursor:pointer;text-transform:uppercase;letter-spacing:.5px;transition:.2s;white-space:nowrap}
.btn-primary{background:linear-gradient(135deg,#0066cc,#00d4ff);color:#fff}
.btn-primary:hover{opacity:.85;transform:translateY(-1px)}
.btn-danger{background:transparent;border:1px solid var(--danger);color:var(--danger)}
.btn-danger:hover{background:var(--danger);color:#fff}
.btn-success{background:transparent;border:1px solid var(--success);color:var(--success)}
.btn-success:hover{background:var(--success);color:#000}
.btn-warn{background:transparent;border:1px solid var(--warn);color:var(--warn)}
.btn-warn:hover{background:var(--warn);color:#000}
.btn-sm{padding:5px 10px;font-size:10px}
table{width:100%;border-collapse:collapse;font-size:11px}
th{color:var(--muted);text-transform:uppercase;font-size:9px;letter-spacing:1px;padding:8px 6px;border-bottom:2px solid var(--border);text-align:left;white-space:nowrap}
td{padding:7px 6px;border-bottom:1px solid rgba(30,58,95,.5);vertical-align:middle}
.c-id{color:var(--primary);font-weight:700;font-size:12px;font-family:monospace}
.c-warn{color:var(--warn);font-weight:700;font-family:monospace}
.c-muted{color:var(--muted);font-size:10px}
.empty{text-align:center;color:var(--muted);padding:20px;font-size:12px}
.badge{display:inline-block;padding:3px 8px;border-radius:4px;font-size:9px;font-weight:700;letter-spacing:.5px;border:1px solid}
.badge-ok {border-color:var(--success);color:var(--success);box-shadow:0 0 6px rgba(0,255,136,.3)}
.badge-exp{border-color:var(--danger);color:var(--danger)}
.actions{display:flex;gap:4px;flex-wrap:wrap}
.refresh-note{font-size:10px;color:var(--muted);text-align:right;margin-bottom:10px}
.log-ok{color:var(--success)}
.log-block{color:var(--danger)}
.log-act{color:var(--warn)}
</style>
</head>
<body>
<div class="topbar"><a href="/admin/logout" class="btn-logout">Đăng Xuất</a></div>
<div class="header">
  <h1>🛡 FF MAX Auth System</h1>
  <p>Hệ Thống Quản Trị Xác Thực Tài Khoản</p>
</div>
<div class="refresh-note">🔄 Tự động làm mới sau 20 giây</div>

<div class="stats">
  <div class="stat s1"><div class="stat-n">{{active}}</div><div class="stat-l">ID Hoạt Động</div></div>
  <div class="stat s2"><div class="stat-n">{{blocked}}</div><div class="stat-l">ID Bị Chặn</div></div>
  <div class="stat s3"><div class="stat-n">{{logs}}</div><div class="stat-l">Log Gần Nhất</div></div>
</div>

<div class="card">
  <div class="card-head">➕ Kích Hoạt ID Mới</div>
  <form action="/admin/add" method="GET">
    <div class="form-row">
      <input type="text" name="id" class="inp inp-id" placeholder="Nhập ID Game..." required>
      <input type="number" name="val" class="inp inp-sm" value="1" min="1" required>
      <select name="unit" class="inp-unit">
        <option value="minutes">Phút</option>
        <option value="hours" selected>Giờ</option>
        <option value="days">Ngày</option>
        <option value="months">Tháng</option>
      </select>
      <button type="submit" class="btn btn-primary">THÊM</button>
    </div>
  </form>
</div>

<div class="card">
  <div class="card-head">📋 Danh Sách ID Được Duyệt</div>
  <table>
    <thead><tr><th>ID Game</th><th>Hết Hạn</th><th>Còn Lại</th><th>Trạng Thái</th><th>Thêm Giờ</th><th>Xóa</th></tr></thead>
    <tbody>{{verified_rows}}</tbody>
  </table>
</div>

<div class="card">
  <div class="card-head warn">🚨 ID Đang Bị Chặn (Cần Kích Hoạt)</div>
  <table>
    <thead><tr><th>ID Game</th><th>Lần Chặn Đầu</th><th>Kích Hoạt Nhanh</th></tr></thead>
    <tbody>{{blocked_rows}}</tbody>
  </table>
</div>

<div class="card">
  <div class="card-head">📡 Nhật Ký Máy Chủ</div>
  <table>
    <thead><tr><th>Thời Gian</th><th>ID</th><th>Trạng Thái</th></tr></thead>
    <tbody>{{log_rows}}</tbody>
  </table>
</div>
</body>
</html>"""

LOGIN_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin Login</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0e1a;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:'Segoe UI',sans-serif}
.card{background:#111827;border:1px solid #1e3a5f;border-radius:14px;padding:32px;width:320px;box-shadow:0 20px 60px rgba(0,0,0,.5)}
h2{color:#00d4ff;text-align:center;margin-bottom:6px;font-size:16px;text-transform:uppercase;letter-spacing:2px}
p{text-align:center;color:#64748b;font-size:11px;margin-bottom:24px}
input{width:100%;background:#0f172a;color:#e2e8f0;border:1px solid #1e3a5f;border-radius:8px;padding:12px;font-size:14px;margin-bottom:14px;outline:none;transition:.2s}
input:focus{border-color:#00d4ff}
button{width:100%;background:linear-gradient(135deg,#0066cc,#00d4ff);color:#fff;border:none;padding:13px;border-radius:8px;font-weight:700;font-size:13px;text-transform:uppercase;cursor:pointer;letter-spacing:1px}
.err{color:#ff4757;text-align:center;font-size:12px;margin-top:10px;padding:8px;background:rgba(255,71,87,.1);border-radius:6px;border:1px solid rgba(255,71,87,.3)}
</style>
</head>
<body>
<div class="card">
<h2>🛡 Admin</h2>
<p>FF MAX Auth System</p>
<form method="POST">
<input type="password" name="password" placeholder="Mật khẩu..." required autofocus>
<button type="submit">ĐĂNG NHẬP</button>
{{error}}
</form>
</div>
</body>
</html>"""

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
        exp_str = time.strftime('%d/%m/%y %H:%M', time.localtime(exp))
        badge = '<span class="badge badge-ok">● ACTIVE</span>' if is_ok else '<span class="badge badge-exp">✗ HẾT HẠN</span>'
        vrows += f"""<tr>
<td class="c-id">{uid}</td>
<td class="c-muted">{exp_str}</td>
<td>{'<span style="color:#00ff88">'+rem+'</span>' if is_ok else '<span style="color:#ff4757">'+rem+'</span>'}</td>
<td>{badge}</td>
<td>
  <form action="/admin/extend" method="GET" style="display:inline-flex;gap:4px;align-items:center">
    <input type="hidden" name="id" value="{uid}">
    <input type="number" name="val" value="1" min="1" class="inp inp-sm" style="width:50px;padding:4px 6px;font-size:11px">
    <select name="unit" class="inp-unit" style="padding:4px 6px;font-size:11px">
      <option value="minutes">Phút</option>
      <option value="hours" selected>Giờ</option>
      <option value="days">Ngày</option>
      <option value="months">Tháng</option>
    </select>
    <button type="submit" class="btn btn-success btn-sm">+</button>
  </form>
</td>
<td><a href="/admin/delete?id={uid}" class="btn btn-danger btn-sm" onclick="return confirm('Xóa {uid}?')">XÓA</a></td>
</tr>"""
    if not vrows: vrows = '<tr><td colspan="6" class="empty">Chưa có ID nào được kích hoạt</td></tr>'

    brows = ""
    for bid, bt in sorted(blocked_db.items(), key=lambda x: x[1], reverse=True):
        if str(bid) in verified and verified[str(bid)] > now: continue
        bt_str = time.strftime('%d/%m %H:%M', time.localtime(bt))
        brows += f"""<tr>
<td class="c-warn">{bid}</td>
<td class="c-muted">{bt_str}</td>
<td class="actions">
  <a href="/admin/add?id={bid}&val=30&unit=minutes" class="btn btn-sm" style="border:1px solid #64748b;color:#64748b;border-radius:4px;padding:4px 8px;font-size:10px;text-decoration:none">30P</a>
  <a href="/admin/add?id={bid}&val=1&unit=hours" class="btn btn-warn btn-sm" style="text-decoration:none">1H</a>
  <a href="/admin/add?id={bid}&val=1&unit=days" class="btn btn-success btn-sm" style="text-decoration:none">1N</a>
  <a href="/admin/add?id={bid}&val=1&unit=months" class="btn btn-primary btn-sm" style="text-decoration:none;background:linear-gradient(135deg,#0066cc,#00d4ff);color:#fff;border:none;border-radius:4px;padding:5px 10px;font-size:10px;font-weight:700">1TH</a>
</td>
</tr>"""
    if not brows: brows = '<tr><td colspan="3" class="empty">Không có ID nào đang bị chặn</td></tr>'

    lrows = ""
    with log_lock:
        for log in log_history[:30]:
            css = "log-ok" if "THÀNH CÔNG" in log['status'] else ("log-block" if "CHẶN" in log['status'] else "log-act")
            lrows += f'<tr><td class="c-muted">{log["time"]}</td><td class="c-id">{log["id"]}</td><td class="{css}">{log["status"]}</td></tr>'
    if not lrows: lrows = '<tr><td colspan="3" class="empty">Chưa có log nào</td></tr>'

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
        return LOGIN_HTML.replace("{{error}}", '<div class="err">❌ Sai mật khẩu!</div>')
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
    unit = request.args.get('unit', 'hours')
    if uid:
        secs = val * UNIT_SECONDS.get(unit, 3600)
        add_verified(uid, secs)
        add_log(uid, f"✅ Kích hoạt {val} {unit}")
    return redirect('/admin')

@app.route('/admin/extend')
def admin_extend():
    if not session.get('admin'): return redirect('/admin/login')
    uid = request.args.get('id','').strip()
    val = int(request.args.get('val', 1))
    unit = request.args.get('unit', 'hours')
    if uid:
        secs = val * UNIT_SECONDS.get(unit, 3600)
        extend_verified(uid, secs)
        add_log(uid, f"⏰ Gia hạn thêm {val} {unit}")
    return redirect('/admin')

@app.route('/admin/delete')
def admin_delete():
    if not session.get('admin'): return redirect('/admin/login')
    uid = request.args.get('id','').strip()
    if uid:
        remove_verified(uid)
        add_log(uid, "🗑️ Đã xóa")
    return redirect('/admin')

# =====================================================
# GAME ROUTES - FIX TRIỆT ĐỂ LỖI ĐƠ % LOAD
# =====================================================
FAKE_JSON = json.dumps({
    "status": "ok", "code": 0, "message": "success",
    "maintenance": False, "server_status": "online",
    "region": "VN", "version": "1.105.1",
    "data": {"is_white": True, "login_open": True,
             "server_time": 0, "cdn_url": "", "patch_version": "1.105.1"}
})

def game_resp(body, status=200, ctype="application/json"):
    r = make_response(body, status)
    r.headers.update({
        'Content-Type': f'{ctype}; charset=utf-8',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, User-Agent',
        'Cache-Control': 'no-cache, no-store',
        'Pragma': 'no-cache'
    })
    return r

def get_uid():
    for k in ['id','accountId','account_id','uid','userId','openId']:
        v = request.args.get(k)
        if v and v.strip(): return v.strip()
    try:
        d = request.get_json(force=True, silent=True) or {}
        for k in ['id','accountId','account_id','uid','openId']:
            v = d.get(k) or d.get('data',{}).get(k)
            if v: return str(v).strip()
    except: pass
    for k in ['id','accountId','uid']:
        v = request.form.get(k)
        if v: return v.strip()
    return None

@app.route('/ping')
def ping(): return "OK", 200

@app.route('/', methods=['GET','POST','OPTIONS'])
@app.route('/<path:path>', methods=['GET','POST','OPTIONS'])
def game_handler(path=''):
    if path.startswith(('admin','api/')):
        from flask import abort; abort(404)

    if request.method == 'OPTIONS':
        return game_resp('', 200)

    # Lấy thông tin UID nếu có
    uid = get_uid()
    path_lower = path.lower()

    # --- ĐOẠN FIX LỖI ĐƠ % LOAD GAME ---
    # Kiểm tra xem request có phải là tải các file config tĩnh, định dạng văn bản hệ thống của game hay không.
    # Khi game đang ở màn hình load % (như trong ảnh), các tệp này luôn cần phải trả về mã 200 (Success) để game tiếp tục tải.
    is_static_file = any(path_lower.endswith(ext) for ext in ['.txt', '.xml', '.json', '.u3d', '.bundle', '.bytes'])

    if uid:
        if check_verified(uid):
            add_log(uid, "✅ ĐĂNG NHẬP THÀNH CÔNG")
            resp = json.loads(FAKE_JSON)
            resp.update({"status":"verified","code":0,"remaining_seconds":get_remaining(uid)})
            resp["data"]["server_time"] = int(time.time())
            return game_resp(json.dumps(resp, ensure_ascii=False), 200)
        else:
            # Nếu phát hiện UID hệ thống rác từ luồng nạp file tĩnh, cho đi qua để tránh đơ %
            if is_static_file:
                resp = json.loads(FAKE_JSON)
                resp["data"]["server_time"] = int(time.time())
                return game_resp(json.dumps(resp, ensure_ascii=False), 200)

            # Trường hợp chặn thực tế tại sảnh đăng nhập khi bấm nút đăng nhập vào game
            add_blocked(uid)
            add_log(uid, "🚫 BỊ CHẶN: Chưa kích hoạt")
            
            # Giữ nguyên cấu trúc thông báo phản hồi lỗi 400 như code cũ của bạn
            msg = f"Account ID: {uid} is Not Verified!\n\nID: {uid} chưa được kích hoạt\nVui lòng liên hệ Admin để kích hoạt.\nĐăng nhập máy chủ thất bại: 400"
            return game_resp(msg, 400, "text/html")

    # Mặc định phản hồi nhanh cho mọi request load cấu hình nền (giúp thanh % chạy mượt)
    resp = json.loads(FAKE_JSON)
    resp["data"]["server_time"] = int(time.time())
    if path_lower.endswith(('.txt','.xml')):
        return game_resp("OK", 200, "text/plain")
    return game_resp(json.dumps(resp, ensure_ascii=False), 200)

# =====================================================
# KEEP ALIVE - Ping mỗi 4 phút để Render không ngủ
# =====================================================
def keep_alive():
    import urllib.request
    time.sleep(15)
    while True:
        try:
            urllib.request.urlopen("https://app-tool-trlp.onrender.com/ping", timeout=8)
        except: pass
        time.sleep(4 * 60)

threading.Thread(target=keep_alive, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 http://localhost:{port}")
    print(f"🔗 Admin: http://localhost:{port}/admin (pass: {ADMIN_PASSWORD})")
    app.run(host='0.0.0.0', port=port, threaded=True)
