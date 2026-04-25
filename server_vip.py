import base64
import zlib

# Đọc file code gốc của bạn
with open('app.py', 'r', encoding='utf-8') as f:
    code_goc = f.read().encode('utf-8')

# Nén và Mã hóa Base64
code_da_nen = zlib.compress(code_goc)
code_ma_hoa = base64.b64encode(code_da_nen).decode('utf-8')

# Tạo file chạy Server đã mã hóa
with open('server_vip.py', 'w', encoding='utf-8') as f:
    f.write('import base64, zlib\n')
    f.write(f'exec(zlib.decompress(base64.b64decode("{code_ma_hoa}")).decode("utf-8"))')

print("✅ Đã mã hóa xong! Giờ bạn chỉ cần upload file 'server_vip.py' lên Hosting/Render để chạy!")
