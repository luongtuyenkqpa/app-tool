import os
import time
import requests
import uuid
import sys
import select
import termios
import tty
import shutil
import zipfile
import subprocess
import re
import random
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.progress import track

# =========================================================================
# LINK SERVER MẶC ĐỊNH
SERVER_URL = "https://app-tool-trlp.onrender.com"  
# =========================================================================

console = Console()

def auto_grant_storage():
    if not os.path.exists(os.path.expanduser('~/storage')):
        os.system('termux-setup-storage')
        time.sleep(2)

def get_device_id():
    mac = uuid.getnode()
    return f"TERMUX-{mac}"

DEVICE_ID = get_device_id()

def clear_screen():
    os.system('clear')

def show_banner(is_vip=False):
    if is_vip:
        banner = """
[bold yellow blink]╔════════════════════════════════════════════════════════════╗
║                   [bold red]👑 LVT INJECTOR VIP PRO 👑[/bold red]                 ║
║           [italic gold1]Hệ thống quản lý Key & Inject File APK[/italic gold1]           ║
╚════════════════════════════════════════════════════════════╝[/]
        """
    else:
        banner = """
[bold cyan]╔════════════════════════════════════════════════════════════╗
║                   [bold yellow]LVT INJECTOR PRO TERMUX[/bold yellow]                  ║
║           [italic white]Hệ thống quản lý Key & Inject File APK[/italic white]           ║
╚════════════════════════════════════════════════════════════╝[/]
        """
    console.print(banner, justify="center")

def check_key_api_silently(key):
    try:
        payload = {"key": key, "deviceId": DEVICE_ID, "target_app": "tool"}
        res = requests.post(f"{SERVER_URL}/api/check", json=payload, timeout=5)
        return res.json()
    except:
        return {"status": "error", "message": "Mất kết nối!"}

def display_message(status, message):
    color = "green" if status == "success" else "red"
    title = "THÀNH CÔNG" if status == "success" else "THẤT BẠI"
    console.print(Panel(f"[bold {color}]{message}[/]", title=f"[{color}]{title}[/]", border_style=color, width=60))
    time.sleep(2)

def check_dependencies():
    try:
        subprocess.run(["apktool", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["java", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False

class AuthService:
    pin = ""
    @staticmethod
    def parseAndSave(data, pin):
        info = data.get('data', data.get('info', data))
        
        raw_vip = info.get('vip', info.get('type', ''))
        is_vip = str(raw_vip).lower() in ['true', '1', 'vip', 'yes']
        
        exp = info.get('expire_time') or info.get('exp') or 'Vĩnh viễn'
        devs = info.get('devices') or info.get('max_devices') or '1/1'
        
        clean_data = {'key': data.get('key'), 'vip': is_vip, 'expire_time': exp, 'devices': devs}
        os.environ['LVT_VIP'] = str(is_vip)
        return clean_data
        
    @staticmethod
    def isVIP():
        return os.environ.get('LVT_VIP') == 'True'

def tool_le_2_decoder(target_apk, out_dir, temp_dir):
    console.print("[bold magenta][TOOL LẺ 2][/] Đang bung nén và quét cấu trúc lõi Bypass...")
    if os.path.exists(out_dir): shutil.rmtree(out_dir)
    os.system(f"apktool d -r -f '{target_apk}' -o '{out_dir}' > /dev/null 2>&1")
    return True

def tool_le_1_injector(out_dir):
    console.print("[bold cyan][TOOL LẺ 1][/] Kích hoạt Omni-Inject (Tiêm Toàn Diện) đè bẹp Engine Game...")
    random_id = str(uuid.uuid4()).replace("-", "")[:8].upper()
    obfuscated_class = f"Lcom/lvt/Auth_{random_id};"
    client_dir = os.path.join(out_dir, "smali", "com", "lvt")
    os.makedirs(client_dir, exist_ok=True)
    
    client_smali = f"""
.class public {obfuscated_class}
.super Landroid/webkit/WebViewClient;

.method public constructor <init>()V
    .locals 0
    invoke-direct {{p0}}, Landroid/webkit/WebViewClient;-><init>()V
    return-void
.end method

.method public shouldOverrideUrlLoading(Landroid/webkit/WebView;Ljava/lang/String;)Z
    .locals 2
    const-string v0, "lvt://close"
    invoke-virtual {{p2, v0}}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z
    move-result v0
    if-eqz v0, :cond_0
    new-instance v0, Landroid/widget/FrameLayout$LayoutParams;
    const/4 v1, -0x2
    invoke-direct {{v0, v1, v1}}, Landroid/widget/FrameLayout$LayoutParams;-><init>(II)V
    const/16 v1, 0x35
    iput v1, v0, Landroid/widget/FrameLayout$LayoutParams;->gravity:I
    invoke-virtual {{p1, v0}}, Landroid/webkit/WebView;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V
    const/4 v1, 0x0
    invoke-virtual {{p1, v1}}, Landroid/webkit/WebView;->setBackgroundColor(I)V
    const/4 v0, 0x1
    return v0
    :cond_0
    const-string v0, "lvt://open"
    invoke-virtual {{p2, v0}}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z
    move-result v0
    if-eqz v0, :cond_1
    new-instance v0, Landroid/widget/FrameLayout$LayoutParams;
    const/4 v1, -0x1
    invoke-direct {{v0, v1, v1}}, Landroid/widget/FrameLayout$LayoutParams;-><init>(II)V
    invoke-virtual {{p1, v0}}, Landroid/webkit/WebView;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V
    const/4 v1, 0x0
    invoke-virtual {{p1, v1}}, Landroid/webkit/WebView;->setBackgroundColor(I)V
    const/4 v0, 0x1
    return v0
    :cond_1
    const/4 v0, 0x0
    return v0
.end method

.method public static init(Landroid/app/Activity;)V
    .locals 4
    :try_start_lvt
    new-instance v0, Landroid/webkit/WebView;
    invoke-direct {{v0, p0}}, Landroid/webkit/WebView;-><init>(Landroid/content/Context;)V

    new-instance v1, {obfuscated_class}
    invoke-direct {{v1}}, {obfuscated_class}-><init>()V
    invoke-virtual {{v0, v1}}, Landroid/webkit/WebView;->setWebViewClient(Landroid/webkit/WebViewClient;)V

    invoke-virtual {{v0}}, Landroid/webkit/WebView;->getSettings()Landroid/webkit/WebSettings;
    move-result-object v1
    const/4 v2, 0x1
    invoke-virtual {{v1, v2}}, Landroid/webkit/WebSettings;->setJavaScriptEnabled(Z)V
    invoke-virtual {{v1, v2}}, Landroid/webkit/WebSettings;->setDomStorageEnabled(Z)V

    const/4 v2, 0x0
    invoke-virtual {{v0, v2}}, Landroid/webkit/WebView;->setBackgroundColor(I)V

    const-string v1, "file:///android_asset/GIAO_DIEN_LOGIN_LVT.html"
    invoke-virtual {{v0, v1}}, Landroid/webkit/WebView;->loadUrl(Ljava/lang/String;)V

    invoke-virtual {{p0}}, Landroid/app/Activity;->getWindow()Landroid/view/Window;
    move-result-object v1
    invoke-virtual {{v1}}, Landroid/view/Window;->getDecorView()Landroid/view/View;
    move-result-object v1
    check-cast v1, Landroid/view/ViewGroup;

    new-instance v2, Landroid/widget/FrameLayout$LayoutParams;
    const/4 v3, -0x1
    invoke-direct {{v2, v3, v3}}, Landroid/widget/FrameLayout$LayoutParams;-><init>(II)V
    invoke-virtual {{v1, v0, v2}}, Landroid/view/ViewGroup;->addView(Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V
    :try_end_lvt
    .catch Ljava/lang/Exception; {{:try_start_lvt .. :try_end_lvt}} :catch_lvt
    :catch_lvt
    return-void
.end method
"""
    with open(os.path.join(client_dir, f"Auth_{random_id}.smali"), "w", encoding="utf-8") as f:
        f.write(client_smali.strip())

    injected_count = 0
    for root, _, files in os.walk(out_dir):
        if "smali" not in root: continue
        for f in files:
            if f.endswith(".smali"):
                pth = os.path.join(root, f)
                try:
                    with open(pth, 'r', encoding='utf-8') as fp: lines = fp.readlines()
                    is_activity = False
                    for line in lines:
                        if line.startswith(".super ") and ("Activity;" in line or "AppCompatActivity;" in line):
                            is_activity = True; break
                    if is_activity:
                        new_lines = []
                        in_oncreate = False
                        injected = False
                        has_oncreate = any(".method" in l and "onCreate(" in l for l in lines)
                        for line in lines:
                            if ".method" in line and "onCreate(" in line: in_oncreate = True
                            if in_oncreate and line.strip() == "return-void":
                                new_lines.append(f"    invoke-static {{p0}}, {obfuscated_class}->init(Landroid/app/Activity;)V\n")
                                injected = True
                            if in_oncreate and ".end method" in line: in_oncreate = False
                            new_lines.append(line)
                        if not has_oncreate:
                            super_c = next((l.split()[1] for l in lines if l.startswith(".super ")), "Landroid/app/Activity;")
                            new_lines.append(f"\n.method protected onCreate(Landroid/os/Bundle;)V\n    .locals 0\n    invoke-super {{p0, p1}}, {super_c}->onCreate(Landroid/os/Bundle;)V\n    invoke-static {{p0}}, {obfuscated_class}->init(Landroid/app/Activity;)V\n    return-void\n.end method\n")
                            injected = True
                        if injected:
                            with open(pth, 'w', encoding='utf-8') as fp: fp.writelines(new_lines)
                            injected_count += 1
                except: pass
    console.print(f"[bold green]✓ Đã gài Menu Tàng hình vào {injected_count} tọa độ chốt chặn! (Chống lẩn tránh)[/]")
    return injected_count > 0

# ==========================================
# GIAO DIỆN HTML APK LOADER + MINI TAB BÊN PHẢI
# ==========================================
def get_html_payload(custom_server=SERVER_URL):
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; user-select: none; }}
        html, body {{ width: 100%; height: 100%; overflow: hidden; background: #000; margin: 0; padding: 0; }}
        body {{ display: flex; justify-content: center; align-items: center; font-family: monospace; color: white; font-size: 14px; transition: background 0.3s; }}
        .panel {{ width: 90%; max-width: 600px; padding: 20px; background: #000; border: 1px solid #ff3333; border-radius: 5px; text-align: center; }}
        .ascii {{ color: #ff3333; font-weight: bold; white-space: pre; line-height: 1.2; margin-bottom: 20px; font-size: 10px; }}
        @media (min-width: 400px) {{ .ascii {{ font-size: 14px; }} }}
        
        select, input {{ width: 100%; background: #000; border: 1px solid #ff3333; border-radius: 5px; padding: 12px; margin-bottom: 15px; color: #00ff00; text-align: center; outline: none; font-family: monospace; font-size: 16px; font-weight: bold; }}
        select {{ cursor: pointer; color: #a855f7; border-color: #a855f7; }}
        input::placeholder {{ color: #666; }}
        
        button {{ width: 100%; background: #ff3333; border: none; border-radius: 5px; padding: 12px; color: #fff; font-weight: bold; cursor: pointer; font-family: monospace; font-size: 16px; text-transform: uppercase; transition: 0.2s; }}
        button:active {{ background: #cc0000; }}
        
        .toast {{ position: fixed; top: -60px; left: 50%; transform: translateX(-50%); padding: 12px 25px; border-radius: 5px; font-weight: bold; font-family: monospace; transition: top 0.4s; z-index: 1000; border: 1px solid; width: max-content; max-width: 90%; text-align: center; }}
        .toast.show {{ top: 20px; }}
        
        .mini-tab {{ display: none; position: relative; margin: 15px; background: rgba(0,0,0,0.85); border: 1px solid #ff3333; padding: 12px; min-width: 150px; z-index: 9999; font-family: monospace; border-radius: 8px; box-shadow: 0 0 10px rgba(255,51,51,0.5); }}
        .m-title {{ font-size: 12px; font-weight: bold; color: #ff3333; text-align: center; border-bottom: 1px dashed #ff3333; padding-bottom: 5px; margin-bottom: 5px; }}
        .m-item {{ font-size: 11px; color: #fff; display: flex; justify-content: space-between; margin: 6px 0; align-items: center; gap: 15px; }}
        .m-val {{ color: #00ff00; font-weight: bold; text-align: right; }}
    </style>
</head>
<body>
    <div id="toast" class="toast"></div>
    <div id="login-panel" class="panel">
        <div class="ascii">
╔════════════════════════════════════╗
║         🔒 HỆ THỐNG ĐÃ KHÓA 🔒     ║
║ Tool đang đóng băng! Nhập Key mở!  ║
╚════════════════════════════════════╝
        </div>
        <div style="margin-bottom: 15px; font-weight: bold; color: white;">VUI LÒNG CHỌN CÔNG TẮC VÀ NHẬP KEY</div>
        
        <select id="keyType">
            <option value="vip">👑 SỬ DỤNG KEY VIP</option>
            <option value="thuong">👤 SỬ DỤNG KEY THƯỜNG</option>
        </select>
        
        <input type="text" id="keyInput" placeholder="Dán Key vào đây..." autocomplete="off">
        <button type="button" id="loginBtn" onclick="verifyKey()">🔓 XÁC THỰC MỞ KHÓA</button>
        <div style="margin-top:15px;font-size:12px;color:yellow">Mã Máy: <span id="hwid-val"></span></div>
    </div>
    
    <div id="mini-tab" class="mini-tab">
        <div class="m-title">≡ TRẠNG THÁI KEY ≡</div>
        <div class="m-item"><span>Gói:</span><span id="m-type" class="m-val"></span></div>
        <div class="m-item"><span>Key:</span><span id="m-key" class="m-val" style="color: #a855f7;"></span></div>
        <div class="m-item"><span>TB:</span><span id="m-dev" class="m-val" style="color: #38bdf8;"></span></div>
        <div class="m-item"><span>Hạn:</span><span id="m-time" class="m-val" style="color: yellow;"></span></div>
    </div>

    <script>
        const SERVER_URL = '{custom_server}/api/check';
        let deviceId = localStorage.getItem('lvt_app_hwid') || 'APK-' + Math.random().toString(36).substr(2, 9).toUpperCase();
        localStorage.setItem('lvt_app_hwid', deviceId);
        document.getElementById('hwid-val').innerText = deviceId;
        
        const savedKey = localStorage.getItem('lvt_saved_key');
        const savedType = localStorage.getItem('lvt_key_type');
        if (savedType) document.getElementById('keyType').value = savedType;
        if (savedKey) {{ document.getElementById('keyInput').value = savedKey; verifyKey(true); }}
        
        function showToast(msg, bg = '#000', borderColor = '#ff3333', color='#ff3333') {{ 
            const t = document.getElementById('toast'); 
            t.innerText = msg; t.style.background = bg; t.style.borderColor = borderColor; t.style.color = color;
            t.className = 'toast show'; setTimeout(() => t.className = 'toast', 3000); 
        }}
        
        // HÀM CHỐT HẠ ĐIỀU KHIỂN SMALI QUA LOCATION (Mượt như vuốt iPhone)
        function triggerClose() {{
            /* [LVT_SCHEME_CLOSE] */ window.location.replace("lvt://close");
        }}
        function triggerOpen() {{
            /* [LVT_SCHEME_OPEN] */ window.location.replace("lvt://open");
        }}

        async function verifyKey(isAuto = false) {{
            const key = document.getElementById('keyInput').value.trim();
            const keyType = document.getElementById('keyType').value;
            
            if (!key) return showToast('Vui lòng nhập Key!');
            if (!isAuto) document.getElementById('loginBtn').innerText = 'ĐANG QUÉT...';
            
            try {{
                const payload = {{ key: key, deviceId: deviceId, target_app: "tool", expected_type: keyType, type: keyType }};
                const res = await fetch(SERVER_URL, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(payload) }});
                
                if (!res.ok) throw new Error("Mất kết nối Server!");
                const data = await res.json();
                
                if (data.status === 'success') {{
                    if (!isAuto) showToast('Xác thực thành công!', '#000', '#00ff00', '#00ff00');
                    localStorage.setItem('lvt_saved_key', key);
                    localStorage.setItem('lvt_key_type', keyType);
                    
                    // THAY ĐỔI CSS ĐỂ SMALI CO NHỎ WEBVIEW LẠI, HIỆN BẢNG EXP LÊN
                    document.documentElement.style.cssText = 'width: fit-content; height: fit-content; background: transparent;';
                    document.body.style.cssText = 'width: fit-content; height: fit-content; background: transparent; display: block; overflow: visible; margin: 0; padding: 0;';
                    document.getElementById('login-panel').style.display = 'none';
                    
                    let mt = document.getElementById('mini-tab');
                    mt.style.display = 'block';
                    
                    let isVipStr = String(data.vip || data.type || keyType).toLowerCase();
                    let isVipBool = ['true', '1', 'vip', 'yes'].includes(isVipStr);
                    document.getElementById('m-type').innerText = isVipBool ? '👑 VIP' : '👤 THƯỜNG';
                    document.getElementById('m-type').style.color = isVipBool ? '#00ff00' : '#94a3b8';
                    
                    document.getElementById('m-key').innerText = key;
                    document.getElementById('m-dev').innerText = data.devices || data.max_devices || '1/1';
                    
                    startCountdown(data.expire_time || (data.data && data.data.exp));
                    startBackgroundCheck(key, keyType);
                    
                    // Delay 300ms báo Smali co nhỏ khung hình lại
                    setTimeout(() => {{ triggerClose(); }}, 300);
                }} else {{
                    localStorage.removeItem('lvt_saved_key');
                    showToast(data.message || 'Key sai hoặc đã hết hạn!');
                    setTimeout(() => {{ triggerOpen(); }}, 300);
                }}
            }} catch (e) {{ 
                showToast('Lỗi: ' + e.message); 
                if (!isAuto) document.getElementById('loginBtn').innerText = '🔓 XÁC THỰC MỞ KHÓA';
            }}
        }}
        
        const tab = document.getElementById('mini-tab');
        let isDragging = false, startX, startY, initX, initY;
        tab.addEventListener('touchstart', e => {{ 
            isDragging = true; startX = e.touches[0].clientX; startY = e.touches[0].clientY; 
            const rect = tab.getBoundingClientRect();
            initX = rect.left; initY = rect.top;
            tab.style.right = 'auto'; 
            tab.style.left = initX + 'px';
        }});
        tab.addEventListener('touchmove', e => {{ 
            if(!isDragging) return; 
            tab.style.left = (initX + e.touches[0].clientX - startX) + 'px'; 
            tab.style.top = (initY + e.touches[0].clientY - startY) + 'px'; 
            e.preventDefault(); 
        }}, {{passive: false}});
        tab.addEventListener('touchend', () => isDragging = false);
        
        let timerInt, checkInt;
        function startCountdown(exp) {{
            let el = document.getElementById('m-time');
            if(timerInt) clearInterval(timerInt);
            if(!exp || exp === 'Vĩnh viễn' || exp === 'permanent') {{ el.innerText = 'VĨNH VIỄN'; return; }}
            
            let expNum = parseInt(exp);
            if(isNaN(expNum)) {{ el.innerText = 'N/A'; return; }}
            
            timerInt = setInterval(() => {{
                let diff = expNum - new Date().getTime();
                if (diff <= 0) {{ el.innerText = 'HẾT HẠN'; el.style.color = '#ff3333'; return; }}
                let d = Math.floor(diff / 86400000), h = Math.floor((diff % 86400000) / 3600000), m = Math.floor((diff % 3600000) / 60000);
                el.innerText = `${{d}}N ${{h}}G ${{m}}P`;
            }}, 1000);
        }}
        
        function startBackgroundCheck(key, keyType) {{
            if(checkInt) clearInterval(checkInt);
            checkInt = setInterval(async () => {{
                try {{
                    const payload = {{key: key, deviceId: deviceId, target_app: "tool", expected_type: keyType, type: keyType}};
                    const res = await fetch(SERVER_URL, {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify(payload) }});
                    const data = await res.json();
                    if(data.status !== 'success') {{
                        clearInterval(checkInt); if(timerInt) clearInterval(timerInt);
                        document.getElementById('mini-tab').style.display = 'none';
                        document.getElementById('login-panel').style.display = 'block';
                        document.documentElement.style.cssText = 'width: 100%; height: 100%; background: #000;';
                        document.body.style.cssText = 'width: 100%; height: 100%; background: #000; display: flex; overflow: hidden; justify-content: center; align-items: center;';
                        setTimeout(() => {{ triggerOpen(); }}, 300);
                        showToast(data.message || 'Key bị khoá hoặc Hết hạn!');
                    }} else {{
                        document.getElementById('m-dev').innerText = data.devices || data.max_devices || '1/1';
                        startCountdown(data.expire_time || (data.data && data.data.exp));
                    }}
                }}catch(e){{}}
            }}, 15000);
        }}
    </script>
</body>
</html>"""

def app_gen_html_payload(target_url, custom_server):
    base_html = get_html_payload(custom_server)
    base_html = base_html.replace('<body>', f'<body>\n    <iframe id="target-frame" src=""></iframe>')
    base_html = base_html.replace('/* [LVT_SCHEME_CLOSE] */ window.location.replace("lvt://close");', f'let frame = document.getElementById("target-frame"); frame.src = "{target_url}"; frame.style.display = "block";')
    base_html = base_html.replace('/* [LVT_SCHEME_OPEN] */ window.location.replace("lvt://open");', f'let frame = document.getElementById("target-frame"); if(frame){{frame.style.display="none"; frame.src="";}}')
    style_inject = '#target-frame { display: none; width: 100vw; height: 100vh; border: none; position: absolute; top: 0; left: 0; z-index: 1; background: #fff; }'
    base_html = base_html.replace('</style>', f'    {style_inject}\n    </style>')
    return base_html

def tool_le_2_framework(build_dir):
    console.print("[bold magenta][TOOL LẺ 2][/] Đang xây dựng lõi ứng dụng (Framework) từ con số 0...")
    os.makedirs(build_dir, exist_ok=True)
    manifest_code = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.lvt.vipapp" android:compileSdkVersion="33" android:compileSdkVersionCodename="13">
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>
    <application android:label="LVT VIP APP" android:usesCleartextTraffic="true">
        <activity android:name="com.lvt.vipapp.MainActivity" android:exported="true" android:theme="@android:style/Theme.NoTitleBar.Fullscreen">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>"""
    with open(os.path.join(build_dir, "AndroidManifest.xml"), "w", encoding="utf-8") as f: f.write(manifest_code)

    apktool_yml = """version: 2.9.3
apkFileName: app.apk
isFrameworkApk: false
usesFramework:
  ids:
  - 1
sdkInfo:
  minSdkVersion: '21'
  targetSdkVersion: '33'"""
    with open(os.path.join(build_dir, "apktool.yml"), "w", encoding="utf-8") as f: f.write(apktool_yml)

    smali_dir = os.path.join(build_dir, "smali", "com", "lvt", "vipapp")
    os.makedirs(smali_dir, exist_ok=True)
    main_activity_smali = """.class public Lcom/lvt/vipapp/MainActivity;
.super Landroid/app/Activity;

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Landroid/app/Activity;-><init>()V
    return-void
.end method

.method protected onCreate(Landroid/os/Bundle;)V
    .locals 3
    invoke-super {p0, p1}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V
    
    new-instance v0, Landroid/webkit/WebView;
    invoke-direct {v0, p0}, Landroid/webkit/WebView;-><init>(Landroid/content/Context;)V
    
    invoke-virtual {v0}, Landroid/webkit/WebView;->getSettings()Landroid/webkit/WebSettings;
    move-result-object v1
    const/4 v2, 0x1
    invoke-virtual {v1, v2}, Landroid/webkit/WebSettings;->setJavaScriptEnabled(Z)V
    invoke-virtual {v1, v2}, Landroid/webkit/WebSettings;->setDomStorageEnabled(Z)V
    
    const-string v1, "file:///android_asset/index.html"
    invoke-virtual {v0, v1}, Landroid/webkit/WebView;->loadUrl(Ljava/lang/String;)V
    
    invoke-virtual {p0, v0}, Landroid/app/Activity;->setContentView(Landroid/view/View;)V
    return-void
.end method"""
    with open(os.path.join(smali_dir, "MainActivity.smali"), "w", encoding="utf-8") as f: f.write(main_activity_smali)

def tool_le_1_ui_generator(build_dir, custom_server, target_url):
    console.print("[bold cyan][TOOL LẺ 1][/] Phù Thủy Đồ Họa đang nạp Menu Cyberpunk và Đường dẫn ảo Iframe...")
    assets_dir = os.path.join(build_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    with open(os.path.join(assets_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(app_gen_html_payload(target_url, custom_server))

def tool_le_3_supervisor(custom_server, target_url):
    console.print(Panel("[bold green][TOOL 3 - SUPERVISOR][/] Đang tiến hành điều phối tạo App VIP từ số 0...", border_style="green"))
    search_dir = "/storage/emulated/0/Download"
    build_dir = os.path.join(search_dir, "LVT_GENERATED_APP")
    final_apk = os.path.join(search_dir, f"LVT_App_{uuid.uuid4().hex[:6].upper()}.apk")
    
    if os.path.exists(build_dir): shutil.rmtree(build_dir)
    
    tool_le_2_framework(build_dir)
    tool_le_1_ui_generator(build_dir, custom_server, target_url)
    
    console.print("[bold green][TOOL 3][/] Các Tool lẻ đã hoàn tất. Đang ra lệnh Đóng gói APK...")
    os.system(f"apktool b '{build_dir}' -o '{final_apk}' > /dev/null 2>&1")
    
    if os.path.exists(final_apk):
        shutil.rmtree(build_dir, ignore_errors=True)
        display_message("success", f"TẠO APP VIP THÀNH CÔNG!\nFile của bạn: {os.path.basename(final_apk)}\n-> Ứng dụng này đã chứa link của bạn và được bảo vệ bằng LVT Key!")
    else:
        display_message("error", "Tiến trình đóng gói gặp lỗi hệ thống Termux (Apktool).")

def auto_create_app_feature():
    clear_screen()
    show_banner(False)
    console.print(Panel("[bold yellow blink]🚀 HỆ THỐNG TẠO APP VIP TỪ CON SỐ 0 🚀[/]", border_style="yellow"))
    
    custom_server = Prompt.ask("[bold yellow]1. Nhập URL Server Key[/] [dim](Bỏ trống để dùng Server mặc định)[/]").strip()
    if not custom_server: custom_server = SERVER_URL
    
    target_url = Prompt.ask("[bold yellow]2. Nhập Đường Link App sẽ trỏ đến (VD: https://google.com)[/]").strip()
    if not target_url:
        display_message("error", "Đường Link không được để trống!")
        time.sleep(2); return
        
    tool_le_3_supervisor(custom_server, target_url)
    Prompt.ask("\nNhấn Enter để quay lại")


# ==========================================
# CHỨC NĂNG 1 & 2: QUẢN LÝ BƠM APK 
# ==========================================
def inject_apk_feature(is_vip=False):
    auto_grant_storage(); clear_screen(); show_banner(is_vip)
    panel_title = "[bold yellow blink]👑 HỆ THỐNG AUTO BƠM HTML VIP 👑[/]" if is_vip else "[bold cyan]HỆ THỐNG AUTO SCAN & INJECT GIAO DIỆN HTML[/]"
    console.print(Panel(panel_title, border_style="yellow" if is_vip else "cyan"))
    
    custom_server = Prompt.ask("\n[bold yellow]Nhập URL Server Key[/] [dim](Bỏ trống để dùng Server mặc định)[/]").strip()
    if not custom_server: custom_server = SERVER_URL

    search_dirs = ["/storage/emulated/0/Download", os.path.expanduser("~/storage/downloads")]
    apk_files, found_dirs = [], []
    for s_dir in search_dirs:
        if os.path.exists(s_dir):
            for file in os.listdir(s_dir):
                if file.lower().endswith('.apk') and not file.startswith('LVT_VIP_') and not file.startswith('HOOKED_'):
                    apk_files.append(file); found_dirs.append(s_dir)
    if not apk_files:
        display_message("error", "Không tìm thấy file .apk gốc nào trong Download!")
        Prompt.ask("\nNhấn Enter để quay lại"); return
        
    table = Table(show_header=True); table.add_column("STT", style="cyan"); table.add_column("Tên File APK Gốc", style="white")
    for idx, apk in enumerate(apk_files): table.add_row(f"[{idx + 1}]", apk)
    console.print(table)
    
    try:
        choice_idx = int(Prompt.ask(f"\n[bold yellow]Nhập STT file để nạp hoặc 0 để hủy[/]"))
        if choice_idx == 0: return
        filename = apk_files[choice_idx - 1]; filepath = os.path.join(found_dirs[choice_idx - 1], filename)
    except: return
    out_path = f"/sdcard/Download/LVT_VIP_{filename}"
    console.print(f"\n[bold green]✓ Đã chọn file:[/bold green] {filename}")
    for task in ["Đang tạo UI chuẩn Form...", "Bơm Javascript Di chuyển..."]:
        for step in track(range(50), description=f"[bold cyan]{task}[/]"): time.sleep(0.01) 
    try:
        shutil.copy(filepath, out_path)
        with zipfile.ZipFile(out_path, 'a', zipfile.ZIP_DEFLATED) as apk_zip:
            apk_zip.writestr('assets/GIAO_DIEN_LOGIN_LVT.html', get_html_payload(custom_server))
        display_message("success", f"Bơm Giao Diện hoàn tất!\nFile: LVT_VIP_{filename}\n-> Hãy chạy [2] để Auto Hook file này!")
    except Exception as e: display_message("error", f"Lỗi hệ thống ghi file: {e}")
    Prompt.ask("\nNhấn Enter để quay lại")

def auto_hook_feature(is_vip=False):
    clear_screen()
    show_banner(is_vip)
    panel_title = "[bold yellow blink]👑 HỆ THỐNG AUTO HOOKER VIP PRO 👑[/]" if is_vip else "[bold cyan]HỆ THỐNG AUTO SMALI HOOKER PRO[/]"
    console.print(Panel(panel_title, border_style="yellow" if is_vip else "cyan"))
    
    custom_server = Prompt.ask("\n[bold yellow]Nhập URL Server Key[/] [dim](Bỏ trống để dùng Server mặc định)[/]").strip()
    if not custom_server: custom_server = SERVER_URL

    if not check_dependencies():
        display_message("error", "LỖI: Máy chưa cài đủ Java và Apktool!\nChạy lệnh sau:\npkg install openjdk-17 apktool -y")
        Prompt.ask("\nNhấn Enter để quay lại"); return
    
    search_dir = "/storage/emulated/0/Download"
    apk_files = [f for f in os.listdir(search_dir) if f.endswith(".apk") and not f.startswith("HOOKED_")] if os.path.exists(search_dir) else []
    
    if not apk_files:
        display_message("error", "Không tìm thấy file .apk nào để Hook!")
        Prompt.ask("\nNhấn Enter để quay lại"); return
        
    table = Table(show_header=True, header_style="bold yellow" if is_vip else "bold magenta")
    table.add_column("STT", style="cyan", width=5); table.add_column("File APK Cần Hook Giao Diện", style="white")
    for idx, apk in enumerate(apk_files): table.add_row(f"[{idx + 1}]", apk)
    console.print(table)
    
    try:
        idx = int(Prompt.ask("\n[bold yellow]Nhập STT file để Auto Hook hoặc 0 để hủy[/]"))
        if idx == 0: return
        target_apk = os.path.join(search_dir, apk_files[idx - 1])
    except: return

    out_dir = os.path.join(search_dir, "LVT_DECOMPILED")
    temp_dir = os.path.join(search_dir, "LVT_TEMP_MANIFEST") 
    console.print(Panel(f"[bold green]BẮT ĐẦU AUTO HOOK ĐA TẦNG VÀO: {apk_files[idx-1]}[/]", border_style="green"))
    tool_le_2_decoder(target_apk, out_dir, temp_dir)
    
    if not tool_le_1_injector(out_dir):
        display_message("error", "Tool Lẻ 1 báo cáo: App không có cấu trúc Activity hợp lệ!")
        Prompt.ask("\nNhấn Enter để quay lại"); return
        
    console.print("[cyan][*] Đang tự động tiêm mã HTML Giao diện vào tệp...[/]")
    assets_dir = os.path.join(out_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    with open(os.path.join(assets_dir, "GIAO_DIEN_LOGIN_LVT.html"), "w", encoding="utf-8") as f: 
        f.write(get_html_payload(custom_server))

    console.print("[cyan][*] Đang Đổi Tên và Chiếm đoạt Logo gốc (Icon Hijacker)...[/]")
    try:
        manifest_path = os.path.join(out_dir, "AndroidManifest.xml")
        icon_name = "ic_launcher"
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f: manifest_data = f.read()
            manifest_data = re.sub(r'(<application[^>]*?)android:label="[^"]+"', r'\1android:label="LVT"', manifest_data)
            match = re.search(r'<application[^>]*?android:icon="@(?:mipmap|drawable)/([^"]+)"', manifest_data)
            if match: icon_name = match.group(1)
            with open(manifest_path, 'w', encoding='utf-8') as f: f.write(manifest_data)
        logo_url = "https://ui-avatars.com/api/?name=LVT&background=0a0f14&color=00f2fe&size=256&bold=true&format=png"
        res_logo = requests.get(logo_url, timeout=10)
        if res_logo.status_code == 200:
            res_dir = os.path.join(out_dir, "res")
            if os.path.exists(res_dir):
                for root, _, files in os.walk(res_dir):
                    for f in files:
                        if f.startswith(icon_name) and f.endswith(".png"):
                            with open(os.path.join(root, f), "wb") as img_f: img_f.write(res_logo.content)
        console.print("[bold green]✓ Đã Đổi Tên thành LVT và Ghi đè Logo gốc![/]")
    except Exception as e: console.print(f"[bold yellow]⚠ Bỏ qua Logo: {e}[/]")

    final_apk = os.path.join(search_dir, f"HOOKED_{apk_files[idx-1]}")
    console.print("[cyan][*] Đang đóng gói và hoàn thiện APK...[/]")
    os.system(f"apktool b '{out_dir}' -o '{final_apk}'")
    if os.path.exists(final_apk):
        shutil.rmtree(out_dir, ignore_errors=True)
        display_message("success", f"HOÀN TẤT AUTO HOOK!\nFile APK của bạn: HOOKED_{apk_files[idx-1]}")
    else: display_message("error", "Đóng gói APK thất bại! Vui lòng đọc lỗi Apktool in ra.")
    Prompt.ask("\nNhấn Enter để quay lại")


# ==========================================
# KHU VỰC MÀN HÌNH KHÓA TERMUX (GIỮ NGUYÊN)
# ==========================================
def lock_screen():
    pin = str(random.randint(100000, 999999))
    lock_banner = f"""
[bold red]╔════════════════════════════════════════════════════════════╗
║                     🔒 HỆ THỐNG ĐÃ KHÓA 🔒                 ║
║        [white]Tool đang đóng băng! Chỉ nhận lệnh mở khóa từ Web[/white]       ║
╚════════════════════════════════════════════════════════════╝[/]
    """
    clear_screen()
    console.print(lock_banner, justify="center")
    box_content = f"""
[bold white]VUI LÒNG VÀO TRANG WEB LOADER KEY ĐỂ AUTO MỞ KHÓA TOOL[/]

[bold yellow]👉 Truy cập Website hoặc file HTML Web Loader của bạn.[/]

Sau khi dán Key vào Website, hãy nhập mã PIN dưới đây:
[bold yellow]Mã PIN của bạn là:[/] [bold green blink]{pin}[/]
    """
    console.print(Panel(box_content, border_style="red"))
    
    with console.status("[bold magenta blink]Đang quét chờ tín hiệu mở khóa từ Web Loader...[/]", spinner="bouncingBar"):
        while True:
            try:
                payload = {"pin": pin, "deviceId": DEVICE_ID, "target_app": "tool"}
                response = requests.post(f"{SERVER_URL}/api/poll_unlock", json=payload).json()
                if response.get("status") == "success":
                    received_key = response.get("key")
                    AuthService.parseAndSave(response, pin)
                    return received_key 
            except: pass
            time.sleep(3)


# ==========================================
# KHU VỰC DASHBOARD MENU (GIỮ NGUYÊN)
# ==========================================
def show_dashboard(initial_key):
    last_sync = 0
    while True:
        current_time = time.time()
        if current_time - last_sync > 15:
            res = check_key_api_silently(initial_key)
            if res.get('status') != 'success':
                clear_screen()
                is_vip = AuthService.isVIP()
                show_banner(is_vip)
                display_message("error", f"CẢNH BÁO: MẤT KẾT NỐI!\nLý do: {res.get('message', 'Key không còn hiệu lực!')}")
                time.sleep(3)
                return 
            AuthService.parseAndSave(res, AuthService.pin)
            last_sync = current_time

        is_vip = AuthService.isVIP()
        sys.stdout.write("\033[H\033[J"); sys.stdout.flush()
        show_banner(is_vip)
        vip_text = "[bold green]VIP[/]" if is_vip else "[bold cyan]THƯỜNG[/]"
        console.print(Panel(f"[bold green]✅ ĐÃ KẾT NỐI {vip_text} THÀNH CÔNG TỪ WEB LOADER[/]", border_style="green"))
        
        console.print("\n[bold cyan][1][/] Bơm Giao Diện Login VIP (Vào file tải sẵn)")
        console.print("[bold cyan][2][/] Auto Hook Đa Tầng (Có Tool Lẻ)")
        
        if is_vip:
            console.print("[bold magenta blink][3][/] Auto Tạo App.apk (Đóng gói Link/Web)")
        else:
            console.print("[bold black][3] Auto Tạo App.apk (Khóa - Yêu cầu Key VIP)[/]")
            
        console.print("[bold red][0][/] Đăng xuất")
        console.print("\n[bold yellow]Chọn chức năng: [/]", end="")
        sys.stdout.flush()

        fd = sys.stdin.fileno(); old_settings = termios.tcgetattr(fd)
        choice = None
        try:
            tty.setcbreak(fd); ready, _, _ = select.select([sys.stdin], [], [], 1.0)
            if ready: choice = sys.stdin.read(1)
        finally: termios.tcsetattr(fd, termios.TCSAFLUSH, old_settings)

        if choice == '1': inject_apk_feature(is_vip); last_sync = 0
        elif choice == '2': auto_hook_feature(is_vip); last_sync = 0
        elif choice == '3': 
            if is_vip: auto_create_app_feature()
            else: display_message("error", "Chức năng này bị khóa! Cần Key VIP để sử dụng.")
            last_sync = 0
        elif choice == '0':
            console.print("\n[bold green]Đang đăng xuất an toàn...[/]")
            time.sleep(1)
            return

if __name__ == "__main__":
    try:
        auto_grant_storage()
        while True:
            valid_key = lock_screen()
            clear_screen()
            is_vip = AuthService.isVIP()
            show_banner(is_vip)
            display_message("success", f"✅ XÁC THỰC {'VIP' if is_vip else 'THƯỜNG'} THÀNH CÔNG!\nĐã nhận Lệnh mở khóa từ Web Loader!")
            time.sleep(1)
            show_dashboard(valid_key)
            
    except KeyboardInterrupt:
        console.print("\n[bold red]Đã thoát Tool LVT![/]")
    except Exception as e:
        console.print(f"\n[bold red]Lỗi hệ thống: {e}[/]")
