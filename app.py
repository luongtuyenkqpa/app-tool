import os, json, time, threading
from flask import Flask, request, jsonify, make_response, redirect, session
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.environ.get("SECRET_KEY", "gameauth_secret_2026")

# =====================================================
# DATABASE
# =====================================================
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
    except Exception:
        GLOBAL_DB = {"verified": {}, "blocked": {}}
    return GLOBAL_DB

def save_db():
    try:
        with open(DB_FILE, 'w') as f:
            json.dump(GLOBAL_DB, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

load_db()

def add_log(account_id, status):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    with log_lock:
        log_history.insert(0, {"time": ts, "id": account_id, "status": status})
        if len(log_history) > 50:
            log_history.pop()

def check_verified(account_id):
    with db_lock:
        exp = GLOBAL_DB.get("verified", {}).get(str(account_id))
        if exp and exp > time.time():
            return True
        elif exp:
            GLOBAL_DB["verified"].pop(str(account_id), None)
            save_db()
        return False

def add_verified(account_id, hours=1):
    with db_lock:
        GLOBAL_DB.setdefault("verified", {})[str(account_id)] = time.time() + hours * 3600
        GLOBAL_DB.setdefault("blocked", {}).pop(str(account_id), None)
        save_db()

def remove_verified(account_id):
    with db_lock:
        GLOBAL_DB.get("verified", {}).pop(str(account_id), None)
        save_db()

def add_blocked(account_id):
    with db_lock:
        if str(account_id) not in GLOBAL_DB.get("blocked", {}):
            GLOBAL_DB.setdefault("blocked", {})[str(account_id)] = int(time.time())
            save_db()

# =====================================================
# FAKE JSON RESPONSE
# =====================================================
def get_fake_resp():
    return {
        "status": "ok", "code": 0, "message": "success",
        "maintenance": False, "server_status": "online",
        "region": "VN", "version": "1.105.1",
        "data": {
            "is_white": True, "login_open": True,
            "server_time": int(time.time()),
            "cdn_url": "", "patch_version": "1.105.1"
        }
    }

def cors_resp(data, status=200, ctype="application/json"):
    if isinstance(data, str):
        r = make_response(data, status)
    else:
        r = make_response(json.dumps(data, ensure_ascii=False), status)
    r.headers['Content-Type'] = ctype + '; charset=utf-8'
    r.headers['Access-Control-Allow-Origin'] = '*'
    r.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    r.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    r.headers['Cache-Control'] = 'no-cache'
    return r

def get_account_id():
    for k in ['id', 'accountId', 'account_id', 'uid']:
        v = request.args.get(k)
        if v: return v.strip()
    try:
        data = request.get_json(silent=True) or {}
        for k in ['id', 'accountId', 'account_id', 'uid']:
            v = data.get(k) or data.get('data', {}).get(k)
            if v: return str(v).strip()
    except Exception:
        pass
    for k in ['id', 'accountId', 'uid']:
        v = request.form.get(k)
        if v: return v.strip()
    return None

# =====================================================
# WEB ADMIN HTML
# =====================================================
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

def get_admin_html():
    now = time.time()
    db = GLOBAL_DB

    # Stats
    verified_items = db.get("verified", {})
    blocked_items = db.get("blocked", {})
    active_count = sum(1 for exp in verified_items.values() if exp > now)
    blocked_count = len([bid for bid in blocked_items if str(bid) not in verified_items or verified_items.get(str(bid), 0) <= now])

    # Verified rows
    verified_rows = ""
    for uid, exp in sorted(verified_items.items(), key=lambda x: x[1], reverse=True):
        is_active = exp > now
        remaining_sec = max(0, int(exp - now))
        h, m = remaining_sec // 3600, (remaining_sec % 3600) // 60
        remaining_str = f"{h}h {m}m" if is_active else "Hết hạn"
        exp_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exp))
        badge = f'<span class="badge-active">● ACTIVE</span>' if is_active else '<span class="badge-expired">✗ HẾT HẠN</span>'
        verified_rows += f"""<tr>
            <td class="id-cell">{uid}</td>
            <td>{exp_str}</td>
            <td>{remaining_str}</td>
            <td>{badge}</td>
            <td>
                <a href="/admin/delete?id={uid}" class="btn-del" onclick="return confirm('Xóa ID {uid}?')">XÓA</a>
            </td>
        </tr>"""
    if not verified_rows:
        verified_rows = '<tr><td colspan="5" class="empty-row">Chưa có ID nào được kích hoạt</td></tr>'

    # Blocked rows
    blocked_rows = ""
    for bid, btime in sorted(blocked_items.items(), key=lambda x: x[1], reverse=True):
        if str(bid) in verified_items and verified_items[str(bid)] > now:
            continue
        btime_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(btime))
        blocked_rows += f"""<tr>
            <td class="id-cell warn">{bid}</td>
            <td>{btime_str}</td>
            <td>
                <a href="/admin/add?id={bid}&hours=1" class="btn-act1h">1 GIỜ</a>
                <a href="/admin/add?id={bid}&hours=24" class="btn-act24h">24 GIỜ</a>
            </td>
        </tr>"""
    if not blocked_rows:
        blocked_rows = '<tr><td colspan="3" class="empty-row">Không có ID nào đang bị chặn</td></tr>'

    # Log rows
    log_rows = ""
    with log_lock:
        for log in log_history[:20]:
            color = "#00dcc8" if "THÀNH CÔNG" in log['status'] else "#ff4444" if "CHẶN" in log['status'] else "#f0a500"
            log_rows += f'<tr><td class="log-time">{log["time"]}</td><td class="log-id">{log["id"]}</td><td style="color:{color}">{log["status"]}</td></tr>'
    if not log_rows:
        log_rows = '<tr><td colspan="3" class="empty-row">Chưa có log nào</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="15">
<title>Hệ Thống Quản Trị Xác Thực</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0b0c10;color:#66fcf1;font-family:'Consolas',monospace;padding:16px}}
h1{{text-align:center;font-size:20px;letter-spacing:2px;text-transform:uppercase;text-shadow:0 0 15px #66fcf1;margin-bottom:4px;color:#66fcf1}}
.subtitle{{text-align:center;font-size:11px;color:#45a29e;margin-bottom:16px}}
.auto-refresh{{text-align:right;font-size:10px;color:#444;margin-bottom:8px}}
.stats{{display:flex;gap:10px;margin-bottom:16px}}
.stat-box{{flex:1;background:rgba(15,20,30,0.95);border-radius:10px;padding:14px;text-align:center}}
.stat-box.green{{border:1px solid #00dcc8;box-shadow:0 0 12px rgba(0,220,200,0.2)}}
.stat-box.red{{border:1px solid #ff4444;box-shadow:0 0 12px rgba(255,68,68,0.2)}}
.stat-box.yellow{{border:1px solid #f0a500;box-shadow:0 0 12px rgba(240,165,0,0.2)}}
.stat-num{{font-size:32px;font-weight:bold}}
.stat-num.green{{color:#00dcc8}}
.stat-num.red{{color:#ff4444}}
.stat-num.yellow{{color:#f0a500}}
.stat-label{{font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-top:4px}}
.card{{background:rgba(15,20,30,0.95);border:1px solid #45a29e;border-radius:10px;padding:14px;margin-bottom:14px;box-shadow:0 0 12px rgba(69,162,158,0.2)}}
.card.warn{{border-color:#f0a500;box-shadow:0 0 12px rgba(240,165,0,0.15)}}
.card-title{{font-size:12px;letter-spacing:1px;text-transform:uppercase;padding-bottom:10px;border-bottom:1px solid rgba(69,162,158,0.3);margin-bottom:12px;color:#45a29e}}
.card-title.warn{{color:#f0a500;border-color:rgba(240,165,0,0.3)}}
.form-row{{display:flex;gap:8px;margin-bottom:10px}}
.form-input{{flex:1;background:#1f2833;color:#66fcf1;border:1px solid #45a29e;border-radius:6px;padding:10px;font-size:13px;outline:none}}
.form-input:focus{{border-color:#66fcf1;box-shadow:0 0 8px rgba(102,252,241,0.3)}}
.form-input.small{{width:80px;flex:none}}
.btn-submit{{background:transparent;border:2px solid #66fcf1;color:#66fcf1;padding:10px 16px;border-radius:6px;font-weight:bold;font-size:12px;text-transform:uppercase;cursor:pointer;white-space:nowrap;transition:all 0.2s}}
.btn-submit:hover{{background:#66fcf1;color:#0b0c10}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#66fcf1;text-transform:uppercase;font-size:10px;letter-spacing:1px;padding:8px 6px;border-bottom:2px solid rgba(102,252,241,0.3);text-align:left}}
td{{padding:8px 6px;border-bottom:1px solid rgba(69,162,158,0.15);color:#c5c6c7;vertical-align:middle}}
.id-cell{{color:#00dcc8;font-weight:bold}}
.id-cell.warn{{color:#f0a500}}
.empty-row{{text-align:center;color:#444;padding:16px!important}}
.badge-active{{background:transparent;border:1px solid #00dcc8;color:#00dcc8;padding:3px 8px;border-radius:4px;font-size:10px;box-shadow:0 0 6px rgba(0,220,200,0.4)}}
.badge-expired{{background:transparent;border:1px solid #ff4444;color:#ff4444;padding:3px 8px;border-radius:4px;font-size:10px}}
.btn-del{{background:transparent;border:1px solid #ff4444;color:#ff4444;padding:4px 10px;border-radius:4px;font-size:11px;text-decoration:none;transition:all 0.2s}}
.btn-del:hover{{background:#ff4444;color:#fff}}
.btn-act1h{{background:transparent;border:1px solid #f0a500;color:#f0a500;padding:4px 8px;border-radius:4px;font-size:11px;text-decoration:none;margin-right:4px;transition:all 0.2s}}
.btn-act1h:hover{{background:#f0a500;color:#000}}
.btn-act24h{{background:transparent;border:1px solid #00dcc8;color:#00dcc8;padding:4px 8px;border-radius:4px;font-size:11px;text-decoration:none;transition:all 0.2s}}
.btn-act24h:hover{{background:#00dcc8;color:#000}}
.log-time{{color:#555;font-size:11px}}
.log-id{{color:#66fcf1}}
.logout{{text-align:right;margin-bottom:8px}}
.logout a{{color:#ff4444;font-size:12px;text-decoration:none;border:1px solid #ff4444;padding:4px 10px;border-radius:4px}}
</style>
</head>
<body>
<div class="logout"><a href="/admin/logout">ĐĂNG XUẤT</a></div>
<h1>🛡️ Hệ Thống Quản Trị Xác Thực</h1>
<p class="subtitle">Free Fire MAX Auth Server</p>
<div class="auto-refresh">🔄 Tự động làm mới sau 15 giây</div>

<div class="stats">
  <div class="stat-box green"><div class="stat-num green">{active_count}</div><div class="stat-label">ID Đang Hoạt Động</div></div>
  <div class="stat-box red"><div class="stat-num red">{blocked_count}</div><div class="stat-label">ID Đang Bị Chặn</div></div>
  <div class="stat-box yellow"><div class="stat-num yellow">{len(log_history)}</div><div class="stat-label">Log Gần Nhất</div></div>
</div>

<div class="card">
  <div class="card-title">➕ Kích Hoạt ID Mới</div>
  <form action="/admin/add" method="GET">
    <div class="form-row">
      <input type="text" name="id" class="form-input" placeholder="Nhập ID Game..." required>
      <input type="number" name="hours" class="form-input small" value="1" min="1" placeholder="Giờ">
      <button type="submit" class="btn-submit">THÊM VÀO HỆ THỐNG</button>
    </div>
  </form>
</div>

<div class="card">
  <div class="card-title">📋 Danh Sách ID Được Duyệt</div>
  <table>
    <thead><tr><th>ID Game</th><th>Hết Hạn Lúc</th><th>Còn Lại</th><th>Trạng Thái</th><th>Hành Động</th></tr></thead>
    <tbody>{verified_rows}</tbody>
  </table>
</div>

<div class="card warn">
  <div class="card-title warn">🚨 ID Đang Bị Chặn (Cần Kích Hoạt)</div>
  <table>
    <thead><tr><th>ID Game</th><th>Lần Chặn Đầu</th><th>Kích Hoạt Nhanh</th></tr></thead>
    <tbody>{blocked_rows}</tbody>
  </table>
</div>

<div class="card">
  <div class="card-title">📡 Nhật Ký Máy Chủ</div>
  <table>
    <thead><tr><th>Thời Gian</th><th>ID</th><th>Trạng Thái</th></tr></thead>
    <tbody>{log_rows}</tbody>
  </table>
</div>
</body>
</html>"""

LOGIN_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Đăng Nhập Admin</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0b0c10;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:'Consolas',monospace}
.card{background:rgba(15,20,30,0.95);border:1px solid #45a29e;border-radius:12px;padding:32px;width:300px;box-shadow:0 0 20px rgba(69,162,158,0.3)}
h2{color:#66fcf1;text-align:center;margin-bottom:24px;font-size:16px;text-transform:uppercase;letter-spacing:2px}
input{width:100%;background:#1f2833;color:#66fcf1;border:1px solid #45a29e;border-radius:6px;padding:12px;font-size:14px;margin-bottom:14px;outline:none}
input:focus{border-color:#66fcf1}
button{width:100%;background:transparent;border:2px solid #66fcf1;color:#66fcf1;padding:12px;border-radius:6px;font-weight:bold;font-size:13px;text-transform:uppercase;cursor:pointer;transition:all 0.2s}
button:hover{background:#66fcf1;color:#0b0c10}
.err{color:#ff4444;text-align:center;font-size:12px;margin-top:8px}
</style>
</head>
<body>
<div class="card">
<h2>🛡️ Admin Login</h2>
<form method="POST">
<input type="password" name="password" placeholder="Mật khẩu..." required autofocus>
<button type="submit">ĐĂNG NHẬP</button>
{error}
</form>
</div>
</body>
</html>"""

# =====================================================
# ADMIN ROUTES
# =====================================================

@app.route('/admin/login', methods=['GET', 'POST'])
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        pw = request.form.get('password', '')
        if pw == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect('/admin')
        return LOGIN_HTML.replace('{error}', '<div class="err">❌ Sai mật khẩu!</div>')
    return LOGIN_HTML.replace('{error}', '')

@app.route('/admin')
def admin_panel():
    if not session.get('admin'):
        return redirect('/admin/login')
    return get_admin_html()

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect('/admin/login')

@app.route('/admin/add')
def admin_add():
    if not session.get('admin'):
        return redirect('/admin/login')
    uid = request.args.get('id', '').strip()
    hours = float(request.args.get('hours', 1))
    if uid:
        add_verified(uid, hours)
        add_log(uid, f"✅ Admin kích hoạt ({hours}h)")
    return redirect('/admin')

@app.route('/admin/delete')
def admin_delete():
    if not session.get('admin'):
        return redirect('/admin/login')
    uid = request.args.get('id', '').strip()
    if uid:
        remove_verified(uid)
        add_log(uid, "🗑️ Admin đã xóa")
    return redirect('/admin')

# =====================================================
# ADMIN API (token-based, dùng từ Termux)
# =====================================================
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "admin123")

def check_token():
    t = request.headers.get("X-Admin-Token") or request.args.get("token")
    return t == ADMIN_TOKEN

@app.route('/api/add', methods=['GET', 'POST'])
def api_add():
    if not check_token(): return jsonify({"error": "Unauthorized"}), 401
    uid = request.args.get('id') or (request.get_json(silent=True) or {}).get('id')
    hours = float(request.args.get('hours', 1))
    if not uid: return jsonify({"error": "Missing id"}), 400
    add_verified(uid, hours)
    add_log(uid, f"✅ API kích hoạt ({hours}h)")
    return jsonify({"ok": True, "id": uid, "hours": hours})

@app.route('/api/remove', methods=['GET', 'POST'])
def api_remove():
    if not check_token(): return jsonify({"error": "Unauthorized"}), 401
    uid = request.args.get('id') or (request.get_json(silent=True) or {}).get('id')
    if not uid: return jsonify({"error": "Missing id"}), 400
    remove_verified(uid)
    return jsonify({"ok": True, "id": uid})

@app.route('/api/list')
def api_list():
    if not check_token(): return jsonify({"error": "Unauthorized"}), 401
    now = time.time()
    verified = {uid: {"expires": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(exp)),
                      "remaining_min": max(0, int((exp-now)/60)), "active": exp > now}
               for uid, exp in GLOBAL_DB.get("verified", {}).items()}
    return jsonify({"verified": verified, "blocked": list(GLOBAL_DB.get("blocked", {}).keys())})

# =====================================================
# GAME ROUTES
# =====================================================

@app.route('/ping')
def ping(): return "OK", 200

@app.route('/', methods=['GET','POST','OPTIONS'])
@app.route('/<path:path>', methods=['GET','POST','OPTIONS'])
def game_handler(path=''):
    # Bỏ qua admin routes
    if path.startswith('admin') or path.startswith('api/'):
        from flask import abort
        abort(404)

    if request.method == 'OPTIONS':
        return cors_resp('', 200)

    uid = get_account_id()
    if uid:
        if check_verified(uid):
            add_log(uid, "✅ ĐĂNG NHẬP THÀNH CÔNG")
            exp = GLOBAL_DB.get("verified", {}).get(str(uid), 0)
            resp = {**get_fake_resp(), "status": "verified", "code": 0,
                   "remaining_seconds": max(0, int(exp - time.time()))}
            return cors_resp(resp, 200)
        else:
            add_blocked(uid)
            add_log(uid, "🚫 BỊ CHẶN: Chưa kích hoạt")
            msg = (f"Account ID: {uid} is Not Verified!\n\n"
                   f"Vui lòng kích hoạt ID để vào game.\n"
                   f"Đăng nhập máy chủ thất bại: 400")
            return cors_resp(msg, 400, "text/html")

    if path.endswith(('.txt', '.xml')):
        return cors_resp("OK", 200, "text/plain")
    return cors_resp(get_fake_resp(), 200)

# =====================================================
# KEEP ALIVE
# =====================================================
def keep_alive():
    time.sleep(30)
    while True:
        try:
            import urllib.request
            urllib.request.urlopen("https://app-tool-trlp.onrender.com/ping", timeout=10)
        except Exception:
            pass
        time.sleep(10 * 60)

threading.Thread(target=keep_alive, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Server: http://localhost:{port}")
    print(f"🔗 Admin : http://localhost:{port}/admin")
    print(f"🔑 Pass  : {ADMIN_PASSWORD}")
    app.run(host='0.0.0.0', port=port, threaded=True)
