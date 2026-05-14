import os, json, time, hashlib, threading, requests, shutil, base64, secrets, hmac, string, copy, traceback
import urllib.parse
from html import escape
from flask import Flask, request, jsonify, redirect, make_response, session, abort
from werkzeug.exceptions import HTTPException

try:
    os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
    time.tzset()
except: pass

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = "8714375866:AAG9r0aCCFOKtgR6B-LcFYBAnJ7x9yMs-8o"
TELEGRAM_CHAT_ID = "7363320876"

app.secret_key = os.environ.get('SECRET_KEY', hashlib.sha256(b"LVT_SECURE_KEY_2026_VIP_V2").hexdigest())
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

DB_FILE = './database.json'
DB_BACKUP = './database.backup.json'
db_lock = threading.RLock()
GLOBAL_DB = {}
_last_db_mtime = 0
_last_mtime_check = 0

def load_db():
    global GLOBAL_DB, _last_db_mtime, _last_mtime_check
    now = time.time()
    with db_lock:
        if now - _last_mtime_check > 1.0:
            try: current_mtime = os.path.getmtime(DB_FILE)
            except OSError: current_mtime = 0
            _last_mtime_check = now
        else: current_mtime = _last_db_mtime

        if current_mtime > _last_db_mtime or not GLOBAL_DB:
            if not os.path.exists(DB_FILE) and os.path.exists(DB_BACKUP): shutil.copy2(DB_BACKUP, DB_FILE)
            data = None
            if os.path.exists(DB_FILE):
                try:
                    with open(DB_FILE, 'r', encoding='utf-8') as f: data = json.load(f)
                except Exception: pass
            if not data: data = {}
            try:
                data.setdefault("keys", {})
                data.setdefault("tg_auth_ids", {TELEGRAM_CHAT_ID: {"exp": "permanent", "banned_until": 0}})
                data.setdefault("banned_ips", [])
                data.setdefault("settings", {})
                data.setdefault("banned_olms", {})
                if "maintenance_until" not in data["settings"]: data["settings"]["maintenance_until"] = 0
                if "global_notice" not in data["settings"]: data["settings"]["global_notice"] = ""
                if "violentmonkey_script" not in data["settings"]: data["settings"]["violentmonkey_script"] = ""
                GLOBAL_DB = data
                _last_db_mtime = current_mtime
            except Exception: pass
        return GLOBAL_DB

def save_db(db=None):
    global _last_db_mtime
    if db is None: db = GLOBAL_DB
    with db_lock:
        try: 
            db_str = json.dumps(db, indent=2, ensure_ascii=False)
            temp_file = DB_FILE + f'.{int(time.time() * 1000)}.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f: 
                f.write(db_str)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, DB_FILE)
            shutil.copy2(DB_FILE, DB_BACKUP)
            _last_db_mtime = os.path.getmtime(DB_FILE)
        except: pass

def generate_secure_key(prefix="", is_vip=False):
    chars = string.ascii_letters + string.digits
    safe_chars = ''.join([c for c in chars if c not in 'IlO0'])
    rand_str = ''.join(secrets.choice(safe_chars) for _ in range(12))
    t_vip = "VIP" if is_vip else "NOR"
    if prefix: return f"{prefix}-{t_vip}-{rand_str}"
    return f"LVT-{t_vip}-{rand_str}"

def get_real_ip():
    try:
        if request.headers.get("CF-Connecting-IP"): return request.headers.get("CF-Connecting-IP")
        if request.headers.getlist("X-Forwarded-For"): return request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
        return request.remote_addr
    except: return "Unknown_IP"

@app.before_request
def firewall():
    db = load_db()
    if get_real_ip() in set(db.get("banned_ips", [])): return "BLOCKED", 403

@app.route('/')
def home():
    return redirect('/telegram_mini_app')

@app.route('/telegram_mini_app')
def mini_app():
    h = """<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no"><script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet"><style>body{background:#0f111a;color:#fff;font-family:sans-serif;margin:0;padding:15px}.s{display:none;animation:f .3s}.s.a{display:block}@keyframes f{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}.btn{background:linear-gradient(90deg,#00ffcc,#0099ff);border:none;width:100%;padding:14px;border-radius:10px;color:#000;font-weight:800;cursor:pointer;margin-bottom:10px}.btn:active{transform:scale(.98)}.inp{width:100%;box-sizing:border-box;background:#1a1d29;border:1px solid rgba(255,255,255,.1);color:#fff;padding:14px;border-radius:10px;margin-bottom:15px}.m-i{background:#1a1d29;border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:15px;display:flex;align-items:center;margin-bottom:12px;cursor:pointer}.ic{width:40px;height:40px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;margin-right:15px}.b-b{background:rgba(255,255,255,.1);border:none;padding:10px 15px;border-radius:10px;color:#fff;font-weight:600;margin-bottom:15px;display:inline-flex;align-items:center;gap:8px;cursor:pointer}.c-d{background:#1a1d29;border:1px solid #00ffcc;border-radius:12px;padding:15px;margin-bottom:10px;font-size:13px}</style></head><body>
    <div id="s-auth" class="s a"><div style="text-align:center;margin:50px 0"><i class="fas fa-shield-alt" style="font-size:60px;color:#00ffcc"></i><h2 style="color:#00ffcc">HỆ THỐNG QUẢN TRỊ</h2></div><input type="text" id="t-id" class="inp" placeholder="Nhập ID Telegram được cấp phép"><button class="btn" onclick="auth()">XÁC THỰC</button></div>
    <div id="s-menu" class="s"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px"><div>ID: <b id="d-id" style="color:#00ffcc"></b></div><div id="d-exp" style="color:#ffcc00;font-size:12px"></div><button style="background:#ef4444;color:#fff;border:none;padding:5px 10px;border-radius:5px" onclick="lout()">Thoát</button></div>
    <div class="m-i" onclick="n('s-act')"><div class="ic" style="background:rgba(189,0,255,.1);color:#bd00ff"><i class="fas fa-rocket"></i></div><div><b>Kích Hoạt Key</b><div style="font-size:12px;color:#aaa">Chỉ định Key vào OLM</div></div></div>
    <div class="m-i" onclick="n('s-list');loadK()"><div class="ic" style="background:rgba(0,255,204,.1);color:#00ffcc"><i class="fas fa-list"></i></div><div><b>Quản Lý Key Kích Hoạt</b><div style="font-size:12px;color:#aaa">Xem Key đã liên kết</div></div></div>
    <div class="m-i" onclick="n('s-cre')"><div class="ic" style="background:rgba(255,204,0,.1);color:#ffcc00"><i class="fas fa-key"></i></div><div><b>Tạo Key Mới</b><div style="font-size:12px;color:#aaa">Tạo Key VIP/Thường</div></div></div>
    <div class="m-i" onclick="n('s-scr')"><div class="ic" style="background:rgba(59,130,246,.1);color:#3b82f6"><i class="fas fa-code"></i></div><div><b>Nạp Script Gốc</b><div style="font-size:12px;color:#aaa">Thay đổi mã nguồn lõi</div></div></div>
    <div class="m-i" onclick="n('s-ban')"><div class="ic" style="background:rgba(239,68,68,.1);color:#ef4444"><i class="fas fa-ban"></i></div><div><b>Chặn OLM</b><div style="font-size:12px;color:#aaa">Cấm định danh OLM</div></div></div>
    <div class="m-i" onclick="getL()"><div class="ic" style="background:rgba(168,85,247,.1);color:#a855f7"><i class="fas fa-download"></i></div><div><b>Lấy Script Loader</b><div style="font-size:12px;color:#aaa">Copy code nạp vào VM</div></div></div>
    <div class="m-i" onclick="n('s-sys')"><div class="ic" style="background:rgba(249,115,22,.1);color:#f97316"><i class="fas fa-bullhorn"></i></div><div><b>Hệ Thống & Bảo Trì</b><div style="font-size:12px;color:#aaa">Bảo trì, Thông báo</div></div></div></div>
    <div id="s-act" class="s"><button class="b-b" onclick="n('s-menu')"><i class="fas fa-arrow-left"></i></button><h3 style="color:#bd00ff">KÍCH HOẠT KEY</h3><input type="text" id="a-k" class="inp" placeholder="Nhập Key"><input type="text" id="a-o" class="inp" placeholder="Nhập tài khoản OLM"><button class="btn" onclick="actK()">KÍCH HOẠT</button></div>
    <div id="s-list" class="s"><button class="b-b" onclick="n('s-menu')"><i class="fas fa-arrow-left"></i></button><h3 style="color:#00ffcc">DANH SÁCH KEY</h3><div id="k-c"></div></div>
    <div id="s-cre" class="s"><button class="b-b" onclick="n('s-menu')"><i class="fas fa-arrow-left"></i></button><h3 style="color:#ffcc00">TẠO KEY</h3><input type="number" id="c-q" class="inp" value="1" placeholder="Số lượng"><input type="number" id="c-d" class="inp" value="1" placeholder="Thời gian"><select id="c-u" class="inp"><option value="h">Giờ</option><option value="d" selected>Ngày</option><option value="p">Vĩnh viễn</option></select><div><input type="checkbox" id="c-v"> <label style="color:#ffcc00">Key VIP</label></div><button class="btn" style="margin-top:15px" onclick="creK()">TẠO</button></div>
    <div id="s-scr" class="s"><button class="b-b" onclick="n('s-menu')"><i class="fas fa-arrow-left"></i></button><h3 style="color:#3b82f6">SCRIPT GỐC</h3><textarea id="s-c" class="inp" rows="10" placeholder="// ==UserScript=="></textarea><button class="btn" onclick="upS()">LƯU</button></div>
    <div id="s-ban" class="s"><button class="b-b" onclick="n('s-menu')"><i class="fas fa-arrow-left"></i></button><h3 style="color:#ef4444">CHẶN OLM</h3><input type="text" id="b-o" class="inp" placeholder="Tên OLM"><input type="number" id="b-d" class="inp" value="1"><select id="b-u" class="inp"><option value="h">Giờ</option><option value="d" selected>Ngày</option><option value="p">Vĩnh viễn</option></select><button class="btn" onclick="banO()">CHẶN</button></div>
    <div id="s-sys" class="s"><button class="b-b" onclick="n('s-menu')"><i class="fas fa-arrow-left"></i></button><h3 style="color:#f97316">HỆ THỐNG</h3><textarea id="sy-m" class="inp" rows="3" placeholder="Thông báo admin"></textarea><button class="btn" onclick="sN()">GỬI THÔNG BÁO</button><hr style="border-color:#333;margin:20px 0"><input type="number" id="m-d" class="inp" value="0" placeholder="0 để tắt"><select id="m-u" class="inp"><option value="m">Phút</option><option value="h" selected>Giờ</option></select><button class="btn" onclick="sM()">BẬT/TẮT BẢO TRÌ</button></div>
    <script>let tid=localStorage.getItem('t_id');let tmr;function n(id){document.querySelectorAll('.s').forEach(e=>e.classList.remove('a'));document.getElementById(id).classList.add('a')}function api(u,d,cb){Swal.showLoading();fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tid:tid,...d})}).then(r=>r.json()).then(r=>{Swal.close();if(r.banned){localStorage.removeItem('t_id');clearInterval(tmr);Swal.fire({icon:'error',title:'BỊ CẤM',html:'Bạn đã bị cấm.<br>Thời gian còn: <b id="cd"></b>',allowOutsideClick:false});setInterval(()=>{let rem=r.exp-Date.now();if(rem<=0)location.reload();let h=Math.floor((rem%86400000)/3600000),m=Math.floor((rem%3600000)/60000),s=Math.floor((rem%60000)/1000);document.getElementById('cd').innerText=`${h}h ${m}m ${s}s`},1000);return}if(r.e)return Swal.fire('Lỗi',r.m,'error');cb(r)})}function chk(){if(!tid)return;api('/api/tg/chk',{},r=>{document.getElementById('d-id').innerText=tid;document.getElementById('d-exp').innerText='HSD: '+(r.exp==='permanent'?'Vĩnh viễn':new Date(r.exp).toLocaleString());n('s-menu');if(!tmr)tmr=setInterval(chk,15000)})}function auth(){tid=document.getElementById('t-id').value;if(!tid)return;localStorage.setItem('t_id',tid);chk()}function lout(){localStorage.removeItem('t_id');clearInterval(tmr);location.reload()}function actK(){api('/api/tg/act',{k:document.getElementById('a-k').value,o:document.getElementById('a-o').value},r=>{Swal.fire('Thành công',`Đã kích hoạt Key ${r.t} cho OLM: ${r.o}`,'success')})}function loadK(){api('/api/tg/get_k',{},r=>{let h='';r.d.forEach(k=>{h+=`<div class="c-d"><b style="color:#00ffcc" onclick="navigator.clipboard.writeText('${k.k}')">${k.k}</b> <span style="float:right;color:${k.s==='active'?'#00ffcc':'#ef4444'}">${k.s}</span><br><div style="color:#aaa;margin-top:5px">HSD: <span style="color:#fff">${k.e}</span></div><div style="color:#aaa">OLM: <span style="color:#ffcc00">${k.o}</span> | Loại: ${k.v?'VIP':'Thường'}</div></div>`});document.getElementById('k-c').innerHTML=h||'<div style="text-align:center;color:#aaa">Trống</div>'})}function creK(){api('/api/tg/cre',{q:document.getElementById('c-q').value,d:document.getElementById('c-d').value,u:document.getElementById('c-u').value,v:document.getElementById('c-v').checked},r=>{Swal.fire('Xong',r.k.join('<br>'),'success')})}function upS(){api('/api/tg/scr',{s:document.getElementById('s-c').value},r=>Swal.fire('Xong','Lưu thành công','success'))}function banO(){api('/api/tg/ban_o',{o:document.getElementById('b-o').value,d:document.getElementById('b-d').value,u:document.getElementById('b-u').value},r=>Swal.fire('Xong','Đã chặn','success'))}function sN(){api('/api/tg/sys',{a:'n',m:document.getElementById('sy-m').value},r=>Swal.fire('Xong','Gửi thành công','success'))}function sM(){api('/api/tg/sys',{a:'m',d:document.getElementById('m-d').value,u:document.getElementById('m-u').value},r=>Swal.fire('Xong','Đã set','success'))}function getL(){api('/api/tg/ld',{},r=>{navigator.clipboard.writeText(r.c);Swal.fire('Thành công','Đã copy Script Loader!','success')})}if(tid)chk();</script></body></html>"""
    return make_response(h)

def c_t(d):
    t = d.get('tid')
    if not t: return False, {"e":True,"m":"No ID"}
    db = load_db()
    if t not in db["tg_auth_ids"]: return False, {"e":True,"m":"ID không được phép"}
    u = db["tg_auth_ids"][t]
    now = int(time.time()*1000)
    b = u.get("banned_until",0)
    if b == "permanent" or (isinstance(b,int) and b > now): return False, {"banned":True,"exp":b}
    e = u.get("exp")
    if e != "permanent" and e < now: return False, {"e":True,"m":"ID đã hết hạn Admin"}
    return True, u

@app.route('/api/tg/chk', methods=['POST'])
def tg_chk():
    v, r = c_t(request.json)
    return jsonify({"exp": r.get("exp")} if v else r)

@app.route('/api/tg/act', methods=['POST'])
def tg_act():
    v, r = c_t(request.json)
    if not v: return jsonify(r)
    k, o = request.json.get('k','').strip(), request.json.get('o','').strip()
    if not k or not o: return jsonify({"e":True,"m":"Nhập đủ thông tin"})
    db = load_db()
    with db_lock:
        if k not in db["keys"]: return jsonify({"e":True,"m":"Key không tồn tại"})
        kd = db["keys"][k]
        if kd.get("bound_olm"): return jsonify({"e":True,"m":"Key này đã được kích hoạt trước đó"})
        kd["bound_olm"] = o
        if kd.get("exp") == "pending": kd["exp"] = int(time.time()*1000) + kd.get("durationMs",0)
        save_db(db)
        return jsonify({"t": "VIP" if kd.get("vip") else "Thường", "o": o})

@app.route('/api/tg/get_k', methods=['POST'])
def tg_gk():
    v, r = c_t(request.json)
    if not v: return jsonify(r)
    db = load_db()
    now = int(time.time()*1000)
    res = []
    for k, d in sorted(db["keys"].items(), key=lambda x: x[1].get('exp',0) if isinstance(x[1].get('exp'),int) else 9e12, reverse=True):
        if not d.get("bound_olm"): continue
        e = d.get("exp")
        es = "Vĩnh viễn" if e=="permanent" else ("Hết hạn" if e<now else time.strftime("%d/%m %H:%M", time.localtime(e/1000)))
        res.append({"k":k,"e":es,"o":d.get("bound_olm"),"s":d.get("status"),"v":d.get("vip")})
    return jsonify({"d": res})

@app.route('/api/tg/cre', methods=['POST'])
def tg_cre():
    v, r = c_t(request.json)
    if not v: return jsonify(r)
    j = request.json
    q, d, u, vi = int(j.get('q',1)), int(j.get('d',1)), j.get('u','d'), j.get('v',False)
    db = load_db()
    res = []
    with db_lock:
        for _ in range(q):
            nk = generate_secure_key("", vi)
            db["keys"][nk] = {"exp":"pending","bound_olm":"","status":"active","vip":vi}
            if u != 'p': db["keys"][nk]["durationMs"] = d * {"h":3600000,"d":86400000}.get(u,86400000)
            else: db["keys"][nk]["exp"] = "permanent"
            res.append(nk)
        save_db(db)
    return jsonify({"k": res})

@app.route('/api/tg/scr', methods=['POST'])
def tg_scr():
    v, r = c_t(request.json)
    if not v: return jsonify(r)
    db = load_db()
    with db_lock:
        db.setdefault("settings",{})["violentmonkey_script"] = request.json.get('s','')
        save_db(db)
    return jsonify({"s":1})

@app.route('/api/tg/ban_o', methods=['POST'])
def tg_bo():
    v, r = c_t(request.json)
    if not v: return jsonify(r)
    j = request.json
    o, d, u = j.get('o',''), int(j.get('d',1)), j.get('u','d')
    db = load_db()
    with db_lock:
        e = "permanent" if u=='p' else int(time.time()*1000) + d * {"h":3600000,"d":86400000}.get(u,86400000)
        db.setdefault("banned_olms",{})[o] = e
        save_db(db)
    return jsonify({"s":1})

@app.route('/api/tg/sys', methods=['POST'])
def tg_sys():
    v, r = c_t(request.json)
    if not v: return jsonify(r)
    j = request.json
    db = load_db()
    with db_lock:
        if j.get('a') == 'n': db.setdefault("settings",{})["global_notice"] = j.get('m','')
        else:
            d = int(j.get('d',0))
            db.setdefault("settings",{})["maintenance_until"] = 0 if d<=0 else int(time.time()*1000) + d * {"m":60000,"h":3600000}.get(j.get('u'),3600000)
        save_db(db)
    return jsonify({"s":1})

@app.route('/api/tg/ld', methods=['POST'])
def tg_ld():
    v, r = c_t(request.json)
    if not v: return jsonify(r)
    js = f"""(function(){{const U=location.origin;let k=localStorage.getItem('_vk');function go(){{let m=document.cookie.match(/username=([^;]+)/);if(m)return decodeURIComponent(m[1]).replace(/"/g,'');if(window.userData&&window.userData.username)return window.userData.username;return 'N/A';}}if(!k){{k=prompt('NHẬP KEY ĐÃ KÍCH HOẠT TỪ ADMIN:');if(k)localStorage.setItem('_vk',k);else return;}}GM_xmlhttpRequest({{method:'POST',url:'{request.host_url}api/v/l',headers:{{'Content-Type':'application/json'}},data:JSON.stringify({{k:k,o:go()}}),onload:function(r){{let d=JSON.parse(r.responseText);if(d.e){{alert(d.m);if(d.c)localStorage.removeItem('_vk');return;}}if(d.mn){{alert('BẢO TRÌ ĐẾN: '+d.mt);return;}}if(d.nt&&localStorage.getItem('_vn')!==d.nt){{let n=document.createElement('div');n.style.cssText='position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#000;color:#ffcc00;padding:20px;border:2px solid #ffcc00;z-index:999999;text-align:center';n.innerHTML=`<h3>THÔNG BÁO TỪ ADMIN</h3><p>${{d.nt}}</p><button id='_vnc' style='background:#ffcc00;color:#000;border:none;padding:5px 10px;cursor:pointer'>ĐÓNG (Ẩn 2H)</button>`;document.body.appendChild(n);document.getElementById('_vnc').onclick=()=>{localStorage.setItem('_vn',d.nt);setTimeout(()=>localStorage.removeItem('_vn'),7200000);n.remove()}}}if(!localStorage.getItem('_vw')){let w=document.createElement('div');w.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,0.9);z-index:999998;display:flex;align-items:center;justify-content:center;flex-direction:column;color:#fff';w.innerHTML=`<h1 style='color:#00ffcc'>CHÀO MỪNG QUÝ KHÁCH</h1><p>Chúc bạn sử dụng vui vẻ nhé. Thắc mắc liên hệ admin tele: luongtuyen20</p><div style='margin-top:20px'><button id='_vw1' style='background:#00ffcc;color:#000;padding:10px;border:none;margin-right:10px'>ẨN 2 GIỜ</button><button id='_vw2' style='background:#ef4444;color:#fff;padding:10px;border:none'>ĐÓNG VĨNH VIỄN</button></div>`;document.body.appendChild(w);document.getElementById('_vw1').onclick=()=>{localStorage.setItem('_vw','1');setTimeout(()=>localStorage.removeItem('_vw'),7200000);w.remove()};document.getElementById('_vw2').onclick=()=>{localStorage.setItem('_vw','2');w.remove()}}let s=document.createElement('div');s.style.cssText='position:fixed;top:10px;right:10px;background:#111;color:#0f0;padding:10px;border:1px solid #0f0;z-index:999997';s.innerHTML=`<b>KEY: ${{d.kn}}</b><br><span id='_vt'></span><br><button id='_vsc' style='background:#f00;color:#fff;border:none;font-size:10px'>ĐÓNG</button>`;document.body.appendChild(s);document.getElementById('_vsc').onclick=()=>s.remove();setInterval(()=>{let rm=d.ex-Date.now();if(rm<=0){alert('KEY HẾT HẠN');localStorage.removeItem('_vk');location.reload()}let hs=Math.floor((rm%86400000)/3600000),ms=Math.floor((rm%3600000)/60000),ss=Math.floor((rm%60000)/1000);document.getElementById('_vt').innerText=`CÒN: ${{hs}}h ${{ms}}m ${{ss}}s`},1000);new Function(decodeURIComponent(escape(atob(d.p))))()}}}})}})();"""
    b64 = base64.b64encode(js.encode()).decode()
    res = f"// ==UserScript==\n// @name OLM LOADER\n// @match *://olm.vn/*\n// @grant GM_xmlhttpRequest\n// ==/UserScript==\nnew Function(atob('{b64}'))();"
    return jsonify({"c": res})

@app.route('/api/v/l', methods=['POST'])
def v_l():
    j = request.json
    k, o = j.get('k',''), j.get('o','')
    db = load_db()
    now = int(time.time()*1000)
    mnt = db.get("settings",{}).get("maintenance_until",0)
    if mnt > now: return jsonify({"mn":True,"mt":time.strftime("%H:%M", time.localtime(mnt/1000))})
    b_o = db.get("banned_olms",{}).get(o,0)
    if b_o == "permanent" or (isinstance(b_o,int) and b_o > now): return jsonify({"e":True,"m":"Tài khoản OLM bị chặn","c":True})
    if k not in db["keys"]: return jsonify({"e":True,"m":"Key không tồn tại","c":True})
    kd = db["keys"][k]
    if kd.get("status") == "banned": return jsonify({"e":True,"m":"Key bị khóa","c":True})
    bo = kd.get("bound_olm","")
    if not bo: return jsonify({"e":True,"m":"Key chưa kích hoạt trên Admin Mini App","c":True})
    if bo != o: return jsonify({"e":True,"m":"Sai tài khoản OLM chỉ định","c":True})
    if kd.get("exp") != "permanent" and kd.get("exp") < now: return jsonify({"e":True,"m":"Key hết hạn","c":True})
    
    scr = base64.b64encode(db.get("settings",{}).get("violentmonkey_script","").encode()).decode()
    return jsonify({"p":scr,"kn": "VIP" if kd.get("vip") else "NOR","ex":kd.get("exp"),"nt":db.get("settings",{}).get("global_notice","")})

@app.route('/admin', methods=['GET', 'POST'])
def admin_p():
    ip = get_real_ip()
    global _last_mtime_check # abusing this for brute force limit temp
    now = time.time()
    if request.method == 'POST':
        p = request.form.get('p','')
        if hashlib.sha256(p.encode()).hexdigest() == "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92": # 123456
            session['a'] = 1
            return redirect('/admin')
        return "Sai pass"
    if not session.get('a'): return '<form method="POST"><input type="password" name="p"><button>VÀO</button></form>'
    
    db = load_db()
    if request.args.get('act') == 'add':
        tid = request.args.get('t')
        db.setdefault("tg_auth_ids",{})[tid] = {"exp":"permanent","banned_until":0}
        save_db(db)
        return redirect('/admin')
    if request.args.get('act') == 'del':
        db["tg_auth_ids"].pop(request.args.get('t'), None)
        save_db(db)
        return redirect('/admin')
        
    h = "<h3>QUẢN LÝ ID TELEGRAM MINI APP</h3><ul>"
    for t, d in db.get("tg_auth_ids",{}).items():
        h += f"<li>{t} - EXP: {d.get('exp')} <a href='?act=del&t={t}'>XÓA</a></li>"
    h += "</ul><form action='?act=add'><input name='t' placeholder='ID Tele'><button>THÊM</button><input type='hidden' name='act' value='add'></form>"
    return h

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
