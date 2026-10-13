from flask import Flask, render_template_string, request, jsonify, redirect, url_for, session
from datetime import timedelta, datetime
from werkzeug.utils import secure_filename
import pymysql
import os
import re

app = Flask(__name__)
app.secret_key = 'shahoor_all_in_one_pos_2026_v10'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

DB_CONFIG = {
    'host': 'sakura.proxy.rlwy.net',
    'port': 31707,
    'user': 'root',
    'password': 'HITVDFaMFehpQFmWrZlnaTKtavNtBZyw',
    'database': 'railway',
    'charset': 'utf8mb4',
    'connect_timeout': 10,
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db():
    conn = pymysql.connect(**DB_CONFIG)
    conn.ping(reconnect=True)
    return conn

def normalize_digits(text):
    if not text: return ""
    return str(text).strip().translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))

# ==========================================
# 2. دروستکردنی خشتەکان (Database Tables)
# ==========================================
def ensure_all_tables():
    conn = None
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute("""CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(100) NOT NULL UNIQUE, password VARCHAR(100) NOT NULL, full_name VARCHAR(150) DEFAULT '', role VARCHAR(50) DEFAULT 'Waiter', can_view_menu TINYINT DEFAULT 1, can_view_tables TINYINT DEFAULT 1, can_view_cashier TINYINT DEFAULT 0, can_view_qsa TINYINT DEFAULT 0, can_view_reports TINYINT DEFAULT 0, can_view_settings TINYINT DEFAULT 0, is_active TINYINT DEFAULT 1);""")
            cursor.execute("""CREATE TABLE IF NOT EXISTS nse (id INT AUTO_INCREMENT PRIMARY KEY, food_name VARCHAR(255) NOT NULL, price DECIMAL(18, 0) NOT NULL DEFAULT 0, category VARCHAR(150) DEFAULT 'گشتی', image_path TEXT, nsecol VARCHAR(50) DEFAULT '');""")
            
            try: cursor.execute("ALTER TABLE nse ADD COLUMN food_name_ar VARCHAR(255) DEFAULT '';")
            except: pass
            try: cursor.execute("ALTER TABLE nse ADD COLUMN food_name_en VARCHAR(255) DEFAULT '';")
            except: pass

            cursor.execute("""CREATE TABLE IF NOT EXISTS froshtn (order_id INT AUTO_INCREMENT PRIMARY KEY, quantity DECIMAL(10, 3) DEFAULT 1, food_name VARCHAR(255), price DECIMAL(18, 0), category VARCHAR(150), table_cabin VARCHAR(150), notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, status VARCHAR(50) DEFAULT 'Active', is_printed TINYINT DEFAULT 0);""")
            try: cursor.execute("ALTER TABLE froshtn MODIFY COLUMN quantity DECIMAL(10, 3) DEFAULT 1;")
            except: pass

            cursor.execute("""CREATE TABLE IF NOT EXISTS table_permissions (table_number INT PRIMARY KEY, allow_ordering TINYINT DEFAULT 1);""")
            cursor.execute("""CREATE TABLE IF NOT EXISTS workers (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(150) NOT NULL, phone VARCHAR(50) DEFAULT '', salary DECIMAL(18, 0) NOT NULL DEFAULT 0);""")
            cursor.execute("""CREATE TABLE IF NOT EXISTS worker_attendance (id INT AUTO_INCREMENT PRIMARY KEY, worker_id INT NOT NULL, date DATE NOT NULL, status VARCHAR(50) DEFAULT 'هاتوو', bonus DECIMAL(18, 0) DEFAULT 0, UNIQUE KEY uniq_worker_date (worker_id, date));""")
            cursor.execute("""CREATE TABLE IF NOT EXISTS masrwf (id INT AUTO_INCREMENT PRIMARY KEY, masrwf_date DATETIME NOT NULL, masrwf_name VARCHAR(150) DEFAULT '', masrwf_type VARCHAR(100) NOT NULL, spent_by VARCHAR(100) DEFAULT '', amount DECIMAL(18, 0) NOT NULL, payment_type VARCHAR(50) DEFAULT 'نەغد', notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);""")
            
            try: cursor.execute("ALTER TABLE masrwf ADD COLUMN masrwf_name VARCHAR(150) DEFAULT '';")
            except: pass
            try: cursor.execute("ALTER TABLE masrwf ADD COLUMN spent_by VARCHAR(100) DEFAULT '';")
            except: pass
            try: cursor.execute("ALTER TABLE masrwf ADD COLUMN payment_type VARCHAR(50) DEFAULT 'نەغد';")
            except: pass
            
            cursor.execute("""CREATE TABLE IF NOT EXISTS qasa (id INT AUTO_INCREMENT PRIMARY KEY, transaction_time DATETIME DEFAULT CURRENT_TIMESTAMP, place_id VARCHAR(150), amount DECIMAL(18, 0), discount DECIMAL(18, 0) DEFAULT 0);""")
            
            cursor.execute("SELECT id FROM users WHERE username = 'admin'")
            if not cursor.fetchone():
                cursor.execute("INSERT INTO users (username, password, full_name, role, is_active) VALUES ('admin', '1234', 'بەڕێوەبەری سەرەکی', 'Manager', 1)")
        conn.commit()
    except Exception as ex: print("Setup tables error:", ex)
    finally:
        if conn:
            try: conn.close()
            except: pass

ensure_all_tables()

# ==========================================
# 3. پاراستن (Security & Middleware)
# ==========================================
@app.before_request
def enforce_security():
    endpoint = request.endpoint or ''
    exempt_endpoints = ['login', 'customer_table_view', 'save_customer_order', 'static', 'index']
    if endpoint in exempt_endpoints or request.path.startswith(('/get_', '/save_', '/clear_', '/change_', '/set_', '/toggle_', '/api_')):
        return
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    if request.path.startswith('/admin') and session.get('role') != 'admin':
        session.clear()
        return redirect(url_for('login'))

# ==========================================
# 4. بەشی دیزاینی هاوبەش (Common HTML/CSS/JS)
# ==========================================
COMMON_HEAD = """
<link href="https://fonts.googleapis.com/css2?family=Noto+Kufi+Arabic:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
    :root { --bg: #0B0F19; --card: #151D30; --primary: #F59E0B; --accent: #10B981; --danger: #EF4444; --text: #F8FAFC; --border: #1E293B; }
    [data-theme="blue"] { --bg: #0f172a; --card: #1e293b; --primary: #3b82f6; --accent: #06b6d4; --border: #334155; }
    [data-theme="green"] { --bg: #064e3b; --card: #065f46; --primary: #10b981; --accent: #f59e0b; --border: #047857; }
    [data-theme="purple"] { --bg: #2e1065; --card: #4c1d95; --primary: #a855f7; --accent: #f472b6; --border: #5b21b6; }
    [data-theme="darkred"] { --bg: #2a0808; --card: #450a0a; --primary: #fca5a5; --accent: #f87171; --border: #7f1d1d; }
    [data-theme="gold"] { --bg: #1c1400; --card: #382700; --primary: #fbbf24; --accent: #f59e0b; --border: #78350f; }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Noto Kufi Arabic', sans-serif; transition: background 0.3s, border-color 0.3s; }
</style>
<script>
    window.savedTheme = localStorage.getItem('theme') || 'luxury';
    document.documentElement.setAttribute('data-theme', window.savedTheme);
    window.savedLang = localStorage.getItem('lang') || 'ku';
    document.documentElement.dir = window.savedLang === 'en' ? 'ltr' : 'rtl';

    const DICT = {
        'ku': { 'dashboard': 'داشبۆرد', 'logout': 'دەرچوون', 'pos': 'فرۆشتن', 'cashier': 'کاشێر', 'reports': 'ئامار', 'expenses': 'مەسرووفات', 'workers': 'شاگرد', 'menu': 'مێنیو', 'users': 'بەکارهێنەر', 'qr': 'بارکۆد', 'cart': 'سەبەتە', 'send': 'ناردن', 'all': 'هەموو' },
        'ar': { 'dashboard': 'لوحة القيادة', 'logout': 'خروج', 'pos': 'نقطة البيع', 'cashier': 'الكاشير', 'reports': 'التقارير', 'expenses': 'المصروفات', 'workers': 'العمال', 'menu': 'القائمة', 'users': 'المستخدمين', 'qr': 'باركود', 'cart': 'السلة', 'send': 'إرسال', 'all': 'الكل' },
        'en': { 'dashboard': 'Dashboard', 'logout': 'Logout', 'pos': 'POS', 'cashier': 'Cashier', 'reports': 'Reports', 'expenses': 'Expenses', 'workers': 'Staff', 'menu': 'Menu', 'users': 'Users', 'qr': 'QR Codes', 'cart': 'Cart', 'send': 'Send', 'all': 'All' }
    };

    function updateGlobalLanguage() {
        document.querySelectorAll('[data-tr]').forEach(el => {
            let k = el.getAttribute('data-tr');
            if(DICT[window.savedLang] && DICT[window.savedLang][k]) el.innerText = DICT[window.savedLang][k];
        });
        window.dispatchEvent(new Event('langChanged'));
    }

    document.addEventListener('DOMContentLoaded', updateGlobalLanguage);

    function setLang(l) {
        localStorage.setItem('lang', l);
        window.savedLang = l;
        document.documentElement.dir = (l==='en') ? 'ltr' : 'rtl';
        updateGlobalLanguage();
    }

    function setTheme(t) {
        localStorage.setItem('theme', t);
        window.savedTheme = t;
        document.documentElement.setAttribute('data-theme', t);
    }
</script>
"""

# ==========================================
# 5. پەڕەکانی HTML (Templates)
# ==========================================

# ----------------- Login -----------------
LOGIN_TEMPLATE = COMMON_HEAD + """
<!DOCTYPE html>
<html lang="ckb" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>چوونەژوورەوە</title>
    <style>
        body { background: var(--bg); color: var(--text); display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 20px; }
        .settings-bar { position: absolute; top: 20px; left: 20px; right: 20px; display: flex; justify-content: space-between; align-items: center; z-index: 10; }
        .color-picker, .lang-picker { display: flex; gap: 8px; background: rgba(0,0,0,0.3); padding: 8px; border-radius: 12px; border: 1px solid var(--border); }
        .color-circle { width: 24px; height: 24px; border-radius: 50%; cursor: pointer; border: 2px solid transparent; }
        .color-circle.active { border-color: #fff; transform: scale(1.1); }
        .lang-btn { background: transparent; color: #fff; border: none; padding: 4px 8px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: bold; }
        .lang-btn.active { background: var(--primary); color: #000; }
        .login-card { background: var(--card); border: 1px solid var(--border); padding: 40px 30px; border-radius: 24px; width: 100%; max-width: 400px; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.4); position: relative; }
        .brand-title { color: var(--primary); font-size: 26px; font-weight: 800; margin-bottom: 8px; }
        .brand-sub { color: #94A3B8; font-size: 13px; margin-bottom: 30px; }
        .input-group { text-align: start; margin-bottom: 16px; }
        .input-group label { display: block; font-size: 13px; font-weight: 700; color: #cbd5e1; margin-bottom: 6px; }
        .login-input { width: 100%; padding: 14px; background: rgba(0,0,0,0.2); border: 1px solid var(--border); border-radius: 12px; color: var(--text); font-size: 15px; outline: none; }
        .login-input:focus { border-color: var(--primary); }
        .btn-submit { width: 100%; background: var(--primary); color: #000; border: none; padding: 15px; border-radius: 12px; font-size: 16px; font-weight: 800; cursor: pointer; margin-top: 10px; }
        .error-msg { color: #ef4444; font-size: 13px; margin-top: 14px; font-weight: 700; background: rgba(239, 68, 68, 0.1); padding: 10px; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="settings-bar">
        <div class="color-picker">
            <div class="color-circle" id="theme-luxury" style="background:#F59E0B;" onclick="changeTheme('luxury', this)"></div>
            <div class="color-circle" id="theme-gold" style="background:#fbbf24;" onclick="changeTheme('gold', this)"></div>
            <div class="color-circle" id="theme-darkred" style="background:#ef4444;" onclick="changeTheme('darkred', this)"></div>
            <div class="color-circle" id="theme-blue" style="background:#3b82f6;" onclick="changeTheme('blue', this)"></div>
            <div class="color-circle" id="theme-green" style="background:#10b981;" onclick="changeTheme('green', this)"></div>
            <div class="color-circle" id="theme-purple" style="background:#a855f7;" onclick="changeTheme('purple', this)"></div>
        </div>
        <div class="lang-picker">
            <button class="lang-btn" id="lang-ku" onclick="changeLang('ku', this)">KU</button>
            <button class="lang-btn" id="lang-ar" onclick="changeLang('ar', this)">AR</button>
            <button class="lang-btn" id="lang-en" onclick="changeLang('en', this)">EN</button>
        </div>
    </div>
    <div class="login-card">
        <div class="brand-title" id="t_title">✨ چێشتماڵە</div>
        <div class="brand-sub" id="t_sub">تکایە ناوی بەکارهێنەر و وشەی نهێنی بنووسە</div>
        <form method="POST" action="/login">
            <div class="input-group"><label id="t_lbl_u">ناوی بەکارهێنەر</label><input type="text" name="username" class="login-input" autofocus></div>
            <div class="input-group"><label id="t_lbl_p">وشەی نهێنی</label><input type="password" name="password" class="login-input"></div>
            <button type="submit" class="btn-submit" id="t_btn">چوونەژوورەوە ➔</button>
        </form>
        {% if error %}<div class="error-msg">{{ error }}</div>{% endif %}
    </div>
    <script>
        const langDictL = {
            'ku': { 'title': '✨ چێشتماڵە', 'sub': 'تکایە ناوی بەکارهێنەر و وشەی نهێنی بنووسە', 'lbl_u': 'ناوی بەکارهێنەر', 'lbl_p': 'وشەی نهێنی', 'btn': 'چوونەژوورەوە ➔' },
            'ar': { 'title': '✨ جيشتمالة', 'sub': 'يرجى إدخال اسم المستخدم وكلمة المرور', 'lbl_u': 'اسم المستخدم', 'lbl_p': 'كلمة المرور', 'btn': 'تسجيل الدخول ➔' },
            'en': { 'title': '✨ Cheshtmala', 'sub': 'Please enter your username and password', 'lbl_u': 'Username', 'lbl_p': 'Password', 'btn': 'Login ➔' }
        };
        
        let themeEl = document.getElementById('theme-' + window.savedTheme);
        if(themeEl) themeEl.classList.add('active');
        
        let langEl = document.getElementById('lang-' + window.savedLang);
        if(langEl) langEl.classList.add('active');
        
        applyL(window.savedLang);

        function applyL(l) {
            document.getElementById('t_title').innerText = langDictL[l].title;
            document.getElementById('t_sub').innerText = langDictL[l].sub;
            document.getElementById('t_lbl_u').innerText = langDictL[l].lbl_u;
            document.getElementById('t_lbl_p').innerText = langDictL[l].lbl_p;
            document.getElementById('t_btn').innerText = langDictL[l].btn;
        }

        window.addEventListener('langChanged', () => applyL(window.savedLang));

        function changeLang(l, btn) {
            document.querySelectorAll('.lang-btn').forEach(b=>b.classList.remove('active'));
            btn.classList.add('active');
            setLang(l);
        }
        function changeTheme(t, btn) {
            document.querySelectorAll('.color-circle').forEach(b=>b.classList.remove('active')); 
            btn.classList.add('active');
            setTheme(t);
        }
    </script>
</body>
</html>
"""

# ----------------- Admin Dashboard -----------------
ADMIN_DASHBOARD_TEMPLATE = COMMON_HEAD + """
<!DOCTYPE html>
<html lang="ckb" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>داشبۆردی سەرەکی</title>
    <style>
        body { background-color: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; }
        .admin-nav { background: var(--card); padding: 16px 28px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border); }
        .admin-brand { font-size: 20px; font-weight: 800; color: var(--primary); }
        .btn-exit { background: var(--danger); color: #fff; text-decoration: none; padding: 8px 18px; border-radius: 8px; font-weight: 800; font-size: 13px; }
        .admin-content { flex: 1; padding: 30px 24px; max-width: 1400px; margin: 0 auto; width: 100%; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 32px; }
        .stat-card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 24px; display: flex; align-items: center; justify-content: space-between; }
        .stat-info { display: flex; flex-direction: column; gap: 8px; }
        .stat-label { font-size: 13px; font-weight: 700; color: #94A3B8; }
        .stat-value { font-size: 24px; font-weight: 800; }
        .modules-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; }
        .module-card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 24px; text-decoration: none; color: var(--text); display: flex; flex-direction: column; gap: 12px; transition: 0.2s; }
        .module-card:hover { border-color: var(--primary); transform: translateY(-3px); }
        .module-top { display: flex; align-items: center; justify-content: space-between; }
        .module-icon { font-size: 32px; }
        .module-badge { background: var(--accent); color: #000; font-size: 11px; font-weight: 800; padding: 4px 10px; border-radius: 8px; }
        .module-title { font-size: 16px; font-weight: 800; color: var(--primary); }
    </style>
</head>
<body>
    <header class="admin-nav">
        <div class="admin-brand" data-tr="dashboard">✨ چێشتماڵە - داشبۆرد</div>
        <div style="display: flex; align-items: center; gap: 16px;">
            <span style="color:#cbd5e1; font-size:13px; font-weight:700;">👑 {{ session.get('full_name', 'بەڕێوەبەر') }}</span>
            <a href="/logout" class="btn-exit" data-tr="logout">✕ دەرچوون</a>
        </div>
    </header>
    <main class="admin-content">
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-info"><span class="stat-label">💰 فرۆشی ئەمڕۆ</span><span class="stat-value" style="color: var(--accent);">{{ "{:,.0f}".format(today_sales) }} د.ع</span></div><div class="module-icon">📈</div></div>
            <div class="stat-card"><div class="stat-info"><span class="stat-label">💸 مەسرووفی ئەمڕۆ</span><span class="stat-value" style="color: var(--danger);">{{ "{:,.0f}".format(today_expense) }} د.ع</span></div><div class="module-icon">🧾</div></div>
            <div class="stat-card"><div class="stat-info"><span class="stat-label">🛎️ مێزە کراوەکان</span><span class="stat-value" style="color: var(--primary);">{{ active_tables_count }} مێز</span></div><div class="module-icon">🍽️</div></div>
            <div class="stat-card"><div class="stat-info"><span class="stat-label">👥 ژمارەی شاگرد</span><span class="stat-value" style="color: #38bdf8;">{{ total_workers }} شاگرد</span></div><div class="module-icon">👤</div></div>
        </div>

        <div class="modules-grid">
            <a href="/admin/amar" class="module-card"><div class="module-top"><div class="module-icon">📊</div><span class="module-badge" style="background:var(--primary);">VIP</span></div><div class="module-title" data-tr="reports">ئامار و قازانج</div></a>
            <a href="/admin/cashier" class="module-card"><div class="module-top"><div class="module-icon">🛎️</div><span class="module-badge">#1</span></div><div class="module-title" data-tr="cashier">کاشێر و واصڵکردن</div></a>
            <a href="/admin/qasa" class="module-card"><div class="module-top"><div class="module-icon">💵</div><span class="module-badge">#2</span></div><div class="module-title">قاسەی فرۆشتن</div></a>
            <a href="/admin/masrwf" class="module-card"><div class="module-top"><div class="module-icon">🧾</div><span class="module-badge" style="background:var(--danger);color:#fff;">$</span></div><div class="module-title" data-tr="expenses">مەسرووفات</div></a>
            <a href="/admin/workers" class="module-card"><div class="module-top"><div class="module-icon">👥</div><span class="module-badge" style="background:#3b82f6;color:#fff;">HR</span></div><div class="module-title" data-tr="workers">حیساباتی شاگردان</div></a>
            <a href="/admin/menu_manager" class="module-card"><div class="module-top"><div class="module-icon">📖</div><span class="module-badge" style="background:#a855f7;color:#fff;">+</span></div><div class="module-title" data-tr="menu">بەڕێوەبردنی مێنیو</div></a>
            <a href="/desktop/tables" class="module-card"><div class="module-top"><div class="module-icon">🖥️</div><span class="module-badge">PC</span></div><div class="module-title" data-tr="pos">شاشەی ئایپاد / شاشەگەورە</div></a>
            <a href="/mobile/tables" class="module-card"><div class="module-top"><div class="module-icon">📱</div><span class="module-badge">MOB</span></div><div class="module-title">مێزەکانی مۆبایل</div></a>
            <a href="/admin/users" class="module-card"><div class="module-top"><div class="module-icon">🔐</div><span class="module-badge" style="background:#64748b;color:#fff;">SEC</span></div><div class="module-title" data-tr="users">بەکارهێنەران</div></a>
            <a href="/qr_manager" class="module-card"><div class="module-top"><div class="module-icon">🖨️</div><span class="module-badge">QR</span></div><div class="module-title" data-tr="qr">بەڕێوەبردنی QR</div></a>
        </div>
    </main>
</body>
</html>
"""

# ----------------- Amar -----------------
WEB_AMAR_TEMPLATE = COMMON_HEAD + """
<!DOCTYPE html>
<html lang="ckb" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>ئامار</title>
    <style>
        body { background: var(--bg); color: var(--text); padding: 20px; }
        .top-bar { display: flex; justify-content: space-between; align-items: center; background: var(--card); padding: 14px 20px; border-radius: 12px; border: 1px solid var(--border); margin-bottom: 20px; }
        .btn-dash { background: var(--border); color: #fff; padding: 8px 16px; border-radius: 8px; text-decoration: none; font-weight: 800; }
        .filter-card { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 18px; margin-bottom: 20px; display:flex; gap:10px; }
        .date-input { background: var(--bg); border: 1px solid var(--border); border-radius: 10px; padding: 10px; color: #fff; outline: none; }
        .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 22px; }
        .sum-card { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 18px; text-align: center; }
        .sum-val { font-size: 20px; font-weight: 900; margin-top:5px; }
        table { width: 100%; border-collapse: collapse; text-align: center; background: var(--card); border: 1px solid var(--border); }
        th { background: rgba(0,0,0,0.2); padding: 14px; color: var(--primary); border-bottom: 1px solid var(--border); }
        td { padding: 12px; border-bottom: 1px solid var(--border); }
    </style>
</head>
<body>
    <div class="top-bar">
        <h2 style="color:var(--primary); font-size: 18px;" data-tr="reports">📊 ڕاپۆرتی ئامار و قازانج</h2>
        <a href="/admin" class="btn-dash" data-tr="dashboard">⬅️ داشبۆرد</a>
    </div>
    <form method="GET" action="/admin/amar" class="filter-card">
        <input type="date" name="start_date" class="date-input" value="{{ start_date }}" required>
        <input type="date" name="end_date" class="date-input" value="{{ end_date }}" required>
        <button type="submit" style="background:var(--accent); color:#000; border:none; padding:10px 20px; border-radius:8px; font-weight:bold;">فلتەر</button>
    </form>
    <div class="summary-grid">
        <div class="sum-card"><div>کۆی فرۆش</div><div class="sum-val" style="color: var(--accent);">{{ "{:,.0f}".format(total_sales) }}</div></div>
        <div class="sum-card"><div>کۆی مەسرووف</div><div class="sum-val" style="color: var(--danger);">{{ "{:,.0f}".format(total_expenses) }}</div></div>
        <div class="sum-card"><div>کرێی شاگرد</div><div class="sum-val" style="color: #3b82f6;">{{ "{:,.0f}".format(total_workers_wage) }}</div></div>
        <div class="sum-card"><div>قازانجی سافی</div><div class="sum-val" style="color: {{ 'var(--accent)' if net_profit >= 0 else 'var(--danger)' }};">{{ "{:,.0f}".format(net_profit) }}</div></div>
    </div>
    <table>
        <thead><tr><th>ناوی خواردن</th><th>ژمارە</th><th>کۆی داهات</th></tr></thead>
        <tbody>
            {% for r in report_rows %}
            <tr><td>{{ r.food_name }}</td><td>{{ "{:,.2f}".format(r.qty).rstrip('0').rstrip('.') }}</td><td style="color:var(--accent); font-weight:bold;">{{ "{:,.0f}".format(r.total) }}</td></tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

# ----------------- Masrwfat -----------------
WEB_MASRWF_TEMPLATE = COMMON_HEAD + """
<!DOCTYPE html>
<html lang="ckb" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>مەسرووفات</title>
    <style>
        body { background: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; padding: 20px; }
        .header { background: var(--card); padding: 14px 24px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); margin-bottom:20px; border-radius:12px; }
        .btn-dash { background: var(--border); color: #fff; padding: 8px 16px; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: bold; }
        .layout { display: grid; grid-template-columns: 1fr 380px; flex: 1; gap: 20px; }
        .table-area { background: var(--card); border: 1px solid var(--border); border-radius: 14px; display: flex; flex-direction: column; overflow: hidden; }
        .filter-bar { padding: 14px; background: rgba(0,0,0,0.2); border-bottom: 1px solid var(--border); display: flex; gap: 10px; align-items: center; }
        .date-input { background: var(--bg); border: 1px solid var(--border); color: #fff; padding: 8px; border-radius: 8px; outline: none; }
        table { width: 100%; border-collapse: collapse; text-align: center; }
        th { background: rgba(0,0,0,0.2); padding: 12px; color: var(--primary); font-size: 13px; font-weight: bold; border-bottom: 1px solid var(--border); }
        td { padding: 12px; font-size: 13px; border-bottom: 1px solid var(--border); }
        tr.selected { background: rgba(0,0,0,0.3); outline: 1px solid var(--primary); }
        .form-area { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 20px; display: flex; flex-direction: column; gap: 14px; }
        .form-area label { font-size: 12px; font-weight: bold; color: #94A3B8; }
        .c-input { width: 100%; background: var(--bg); border: 1px solid var(--border); color: #fff; padding: 10px; border-radius: 8px; outline: none; margin-top: 4px; }
        .c-input:focus { border-color: var(--primary); }
        .btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }
        .btn { padding: 12px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; color: #fff; }
        .btn-save { background: var(--accent); color: #000; }
        .btn-edit { background: var(--primary); color: #000; }
        .btn-del { background: var(--danger); }
        .btn-clr { background: var(--border); }
        @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <header class="header">
        <h2 style="color:var(--danger); font-size:18px;" data-tr="expenses">🧾 مەسرووفات</h2>
        <a href="/admin" class="btn-dash" data-tr="dashboard">⬅️ داشبۆرد</a>
    </header>
    <div class="layout">
        <div class="table-area">
            <div class="filter-bar">
                <form method="GET" style="display:flex; gap:10px;">
                    <input type="date" name="from_date" value="{{ from_date }}" class="date-input">
                    <input type="date" name="to_date" value="{{ to_date }}" class="date-input">
                    <button type="submit" style="padding:8px 16px; background:var(--accent); color:#000; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">گەڕان</button>
                </form>
            </div>
            <div style="overflow-y:auto; flex:1;">
                <table id="tblMasrwf">
                    <thead><tr><th>#</th><th>بەروار</th><th>جۆر</th><th>خەرجکەر</th><th>بڕی پارە</th><th>شێواز</th></tr></thead>
                    <tbody>
                        {% for r in rows %}
                        <tr onclick="selectRow(this, {{ r.id }}, '{{ r.m_date_raw }}', '{{ r.masrwf_type }}', '{{ r.spent_by }}', {{ r.amount }}, '{{ r.payment_type }}', '{{ r.notes }}')">
                            <td>{{ loop.index }}</td><td>{{ r.m_date }}</td><td style="color:var(--primary);">{{ r.masrwf_type }}</td>
                            <td>{{ r.spent_by }}</td><td style="color:var(--danger); font-weight:bold;">{{ "{:,.0f}".format(r.amount) }}</td>
                            <td>{{ r.payment_type }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        <div class="form-area">
            <form id="mForm" method="POST" action="/admin/save_masrwf">
                <input type="hidden" id="selected_id" name="id" value="0">
                <div><label>بەروار:</label><input type="date" id="txt_date" name="masrwf_date" class="c-input" value="{{ today_date }}" required></div>
                <div><label>جۆری مەسرووف:</label><input list="typeOpt" id="txt_type" name="masrwf_type" class="c-input" required><datalist id="typeOpt">{% for t in existing_types %}<option value="{{ t }}">{% endfor %}</datalist></div>
                <div><label>خەرجکەر:</label><input list="spOpt" id="txt_spent_by" name="spent_by" class="c-input"><datalist id="spOpt">{% for s in existing_spenders %}<option value="{{ s }}">{% endfor %}</datalist></div>
                <div style="display:flex; gap:10px;">
                    <div style="flex:2;"><label>بڕی پارە:</label><input type="number" id="txt_amount" name="amount" class="c-input" required></div>
                    <div style="flex:1;"><label>شێواز:</label><select id="txt_payment_type" name="payment_type" class="c-input"><option value="نەغد">نەغد</option><option value="قەرز">قەرز</option></select></div>
                </div>
                <div><label>تێبینی:</label><input type="text" id="txt_notes" name="notes" class="c-input"></div>
                <div class="btn-grid">
                    <button type="button" class="btn btn-save" onclick="sub('/admin/save_masrwf')">تۆمارکردن</button>
                    <button type="button" class="btn btn-edit" onclick="sub('/admin/update_masrwf')">گۆڕین</button>
                    <button type="button" class="btn btn-del" onclick="del()">سڕینەوە</button>
                    <button type="button" class="btn btn-clr" onclick="clr()">پاککردنەوە</button>
                </div>
            </form>
        </div>
    </div>
    <script>
        let sId = 0;
        function selectRow(r, id, dt, ty, sp, am, pt, no) {
            document.querySelectorAll('tr').forEach(tr=>tr.classList.remove('selected')); r.classList.add('selected');
            sId = id; document.getElementById('selected_id').value = id;
            document.getElementById('txt_date').value = dt; document.getElementById('txt_type').value = ty;
            document.getElementById('txt_spent_by').value = sp; document.getElementById('txt_amount').value = am;
            document.getElementById('txt_payment_type').value = pt; document.getElementById('txt_notes').value = no;
        }
        function clr() {
            sId = 0; document.getElementById('mForm').reset();
            document.querySelectorAll('tr').forEach(tr=>tr.classList.remove('selected'));
            document.getElementById('selected_id').value = 0;
        }
        function sub(url) {
            if(url.includes('update') && sId === 0) return alert('سەرەتا دێڕێک هەڵبژێرە!');
            let f = document.getElementById('mForm'); f.action = url; f.submit();
        }
        function del() {
            if(sId === 0) return alert('دێڕێک هەڵبژێرە!');
            if(confirm('دڵنیایت؟')) location.href = '/admin/delete_masrwf/' + sId;
        }
    </script>
</body>
</html>
"""

# ----------------- Workers -----------------
WEB_WORKERS_TEMPLATE = COMMON_HEAD + """
<!DOCTYPE html>
<html lang="ckb" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>شاگردەکان</title>
    <style>
        body { background: var(--bg); color: var(--text); padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .btn-dash { background: var(--card); border: 1px solid var(--border); color: #fff; padding: 8px 16px; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: bold; }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 10px; }
        .tab-btn { background: none; border: none; color: #94A3B8; font-weight: bold; font-size: 14px; cursor: pointer; padding: 10px; }
        .tab-btn.active { color: var(--accent); border-bottom: 2px solid var(--accent); }
        .tab-content { display: none; } .tab-content.active { display: block; }
        .card { background: var(--card); border: 1px solid var(--border); padding: 20px; border-radius: 14px; }
        table { width: 100%; border-collapse: collapse; text-align: center; margin-top: 15px; }
        th { background: rgba(0,0,0,0.2); padding: 12px; color: var(--primary); font-size: 13px; font-weight: bold; border-bottom: 1px solid var(--border); }
        td { padding: 12px; font-size: 13px; border-bottom: 1px solid var(--border); }
        .input-group { margin-bottom: 15px; }
        .input-group label { display: block; font-size: 12px; color: #94A3B8; margin-bottom: 5px; }
        .c-input { width: 100%; background: var(--bg); border: 1px solid var(--border); color: #fff; padding: 10px; border-radius: 8px; outline: none; }
        .btn-action { background: var(--accent); color: #000; padding: 10px 20px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; }
        .worker-row { display: flex; align-items: center; justify-content: space-between; background: var(--bg); padding: 15px; border-radius: 10px; border: 1px solid var(--border); margin-bottom: 10px; }
        .modal { position: fixed; top:0; left:0; right:0; bottom:0; background: rgba(0,0,0,0.8); display:none; align-items:center; justify-content:center; z-index: 1000; padding: 20px; }
        .m-box { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 20px; width: 100%; max-width: 400px; }
    </style>
</head>
<body>
    <div class="header">
        <h2 style="color:var(--primary); font-size:18px;" data-tr="workers">👥 حیساباتی شاگردەکان</h2>
        <a href="/admin" class="btn-dash" data-tr="dashboard">⬅️ داشبۆرد</a>
    </div>
    <div class="tabs">
        <button class="tab-btn active" onclick="showTab('calc')">💰 مووچە</button>
        <button class="tab-btn" onclick="showTab('att')">🗓️ دەوام و بەخشش</button>
        <button class="tab-btn" onclick="showTab('add')">➕ زیادکردن</button>
    </div>

    <div id="calc" class="tab-content active card">
        <form method="GET" style="display:flex; gap:10px; margin-bottom: 15px;">
            <input type="date" name="start_date" value="{{ start_date }}" class="c-input" style="width: auto;">
            <input type="date" name="end_date" value="{{ end_date }}" class="c-input" style="width: auto;">
            <button type="submit" class="btn-action">فلتەر</button>
        </form>
        <table>
            <thead><tr><th>ناو</th><th>ڕۆژانە</th><th>دەوام (ڕۆژ)</th><th>کۆی مووچە</th><th>بەخشش</th><th>کۆی گشتی</th><th>کردار</th></tr></thead>
            <tbody>
                {% for w in wage_rows %}
                <tr>
                    <td style="color:var(--accent); font-weight:bold;">{{ w.name }}</td><td>{{ "{:,.0f}".format(w.salary) }}</td>
                    <td>{{ w.work_days }}</td><td>{{ "{:,.0f}".format(w.total_salary) }}</td>
                    <td style="color:var(--primary);">{{ "{:,.0f}".format(w.total_bonus) }}</td>
                    <td style="color:var(--accent); font-weight:bold;">{{ "{:,.0f}".format(w.total_due) }}</td>
                    <td>
                        <button style="background:#3b82f6; color:#fff; border:none; padding:4px 8px; border-radius:4px; font-weight:bold; cursor:pointer;" onclick="openEdit({{ w.id }}, '{{ w.name }}', {{ w.salary }})">دەستکاری</button>
                        <a href="/admin/delete_worker/{{ w.id }}" style="color:var(--danger); text-decoration:none; margin-right:10px;" onclick="return confirm('سڕینەوە؟')">🗑️</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    
    <div id="att" class="tab-content card">
        <form method="POST" action="/admin/save_attendance">
            <input type="date" name="att_date" value="{{ today_date }}" class="c-input" style="width:200px; margin-bottom:15px;">
            {% for aw in all_workers %}
            <div class="worker-row">
                <input type="hidden" name="worker_ids" value="{{ aw.id }}">
                <div style="font-weight:bold; width: 150px;">{{ aw.name }}</div>
                <div><label><input type="radio" name="status_{{ aw.id }}" value="هاتوو" {{ 'checked' if aw.last_status != 'نەهاتوو' else '' }}> هاتوو</label></div>
                <div><label><input type="radio" name="status_{{ aw.id }}" value="نەهاتوو" {{ 'checked' if aw.last_status == 'نەهاتوو' else '' }}> نەهاتوو</label></div>
                <div><input type="number" name="bonus_{{ aw.id }}" class="c-input" value="0" placeholder="بەخشش" style="width:100px;"></div>
            </div>
            {% endfor %}
            <button type="submit" class="btn-action" style="width:100%; margin-top:10px;">پاشەکەوتکردنی دەوام</button>
        </form>
    </div>
    
    <div id="add" class="tab-content card">
        <form method="POST" action="/admin/add_worker" style="max-width: 400px; margin: 0 auto;">
            <div class="input-group"><label>ناو</label><input type="text" name="name" class="c-input" required></div>
            <div class="input-group"><label>مۆبایل</label><input type="text" name="phone" class="c-input"></div>
            <div class="input-group"><label>مووچەی ڕۆژانە</label><input type="number" name="salary" class="c-input" required></div>
            <button type="submit" class="btn-action" style="width:100%;">تۆمارکردن</button>
        </form>
    </div>

    <div class="modal" id="editModal">
        <div class="m-box">
            <h3 style="color:var(--primary); margin-bottom:15px; text-align:center;">دەستکاریکردنی شاگرد</h3>
            <form id="editForm" method="POST">
                <input type="text" id="e_name" name="name" class="c-input" placeholder="ناو" required style="margin-bottom:10px;">
                <input type="number" id="e_salary" name="salary" class="c-input" placeholder="مووچە" required style="margin-bottom:10px;">
                <button type="submit" style="background:var(--accent); color:#000; width:100%; padding:10px; border:none; border-radius:8px; font-weight:bold; margin-top:10px;">پاشەکەوتکردن</button>
                <button type="button" style="background:transparent; border:1px solid var(--border); color:#fff; width:100%; padding:10px; border-radius:8px; font-weight:bold; margin-top:5px;" onclick="document.getElementById('editModal').style.display='none'">داخستن</button>
            </form>
        </div>
    </div>

    <script>
        function showTab(id) {
            document.querySelectorAll('.tab-content').forEach(t=>t.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
            document.getElementById(id).classList.add('active');
            event.currentTarget.classList.add('active');
        }
        function openEdit(id, n, s) {
            document.getElementById('editForm').action = '/admin/edit_worker/' + id;
            document.getElementById('e_name').value = n;
            document.getElementById('e_salary').value = s;
            document.getElementById('editModal').style.display = 'flex';
        }
    </script>
</body>
</html>
"""

# ----------------- Users -----------------
WEB_USERS_TEMPLATE = COMMON_HEAD + """
<!DOCTYPE html>
<html lang="ckb" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>بەکارهێنەران</title>
    <style>
        body { background: var(--bg); color: var(--text); padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .btn-dash { background: var(--card); border: 1px solid var(--border); color: #fff; padding: 8px 16px; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: bold; }
        .card { background: var(--card); border: 1px solid var(--border); padding: 20px; border-radius: 14px; margin-bottom: 20px; }
        .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; align-items: end; }
        .c-input { width: 100%; background: var(--bg); border: 1px solid var(--border); color: #fff; padding: 10px; border-radius: 8px; outline: none; }
        .btn-add { background: var(--accent); color: #000; padding: 10px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; }
        table { width: 100%; border-collapse: collapse; text-align: center; }
        th { background: rgba(0,0,0,0.2); padding: 12px; color: var(--primary); font-size: 13px; border-bottom: 1px solid var(--border); }
        td { padding: 12px; font-size: 13px; border-bottom: 1px solid var(--border); }
        .modal { position: fixed; top:0; left:0; right:0; bottom:0; background: rgba(0,0,0,0.8); display:none; align-items:center; justify-content:center; z-index: 1000; padding: 20px; }
        .m-box { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 20px; width: 100%; max-width: 400px; }
    </style>
</head>
<body>
    <div class="header">
        <h2 style="color:var(--primary); font-size:18px;" data-tr="users">🔐 بەکارهێنەران</h2>
        <a href="/admin" class="btn-dash" data-tr="dashboard">⬅️ داشبۆرد</a>
    </div>
    <div class="card">
        <form method="POST" action="/admin/add_user" class="form-grid">
            <div><label style="font-size:12px;color:#94A3B8;">یوسەر</label><input type="text" name="username" class="c-input" required></div>
            <div><label style="font-size:12px;color:#94A3B8;">پاسوۆرد</label><input type="text" name="password" class="c-input" required></div>
            <div><label style="font-size:12px;color:#94A3B8;">ناو</label><input type="text" name="full_name" class="c-input"></div>
            <div>
                <label style="font-size:12px;color:#94A3B8;">ڕۆڵ</label>
                <select name="role" class="c-input">
                    <option value="Manager">بەڕێوەبەر</option><option value="Waiter">گارسۆن ئایپاد</option>
                    <option value="Mobile_Waiter">گارسۆن مۆبایل</option><option value="Cashier">کاشێر</option>
                </select>
            </div>
            <button type="submit" class="btn-add">زیادکردن</button>
        </form>
    </div>
    <div class="card" style="overflow-x:auto;">
        <table>
            <thead><tr><th>یوسەر</th><th>پاسوۆرد</th><th>ناو</th><th>ڕۆڵ</th><th>دۆخ</th><th>کردار</th></tr></thead>
            <tbody>
                {% for u in users %}
                <tr>
                    <td style="color:var(--accent); font-weight:bold;">{{ u.username }}</td><td>{{ u.password }}</td>
                    <td>{{ u.full_name }}</td><td>{{ u.role }}</td>
                    <td><a href="/admin/toggle_user/{{ u.id }}" style="color:{{ 'var(--accent)' if u.is_active else 'var(--danger)' }}; text-decoration:none;">{{ 'کارا' if u.is_active else 'بلۆک' }}</a></td>
                    <td>
                        <button style="background:#3b82f6; color:#fff; border:none; padding:4px 8px; border-radius:4px; font-weight:bold; cursor:pointer;" onclick="openEdit({{ u.id }}, '{{ u.username }}', '{{ u.password }}', '{{ u.full_name }}', '{{ u.role }}')">دەستکاری</button>
                        {% if u.username != 'admin' %}<a href="/admin/delete_user/{{ u.id }}" style="color:var(--danger); text-decoration:none; margin-right:5px;" onclick="return confirm('سڕینەوە؟')">🗑️</a>{% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <div class="modal" id="editModal">
        <div class="m-box">
            <h3 style="color:var(--primary); margin-bottom:15px; text-align:center;">دەستکاریکردنی بەکارهێنەر</h3>
            <form id="editForm" method="POST">
                <input type="text" id="e_user" name="username" class="c-input" placeholder="یوسەر" required style="margin-bottom:10px;">
                <input type="text" id="e_pass" name="password" class="c-input" placeholder="پاسوۆرد" required style="margin-bottom:10px;">
                <input type="text" id="e_name" name="full_name" class="c-input" placeholder="ناو" style="margin-bottom:10px;">
                <select id="e_role" name="role" class="c-input" style="margin-bottom:10px;">
                    <option value="Manager">بەڕێوەبەر</option><option value="Waiter">گارسۆن ئایپاد</option>
                    <option value="Mobile_Waiter">گارسۆن مۆبایل</option><option value="Cashier">کاشێر</option>
                </select>
                <button type="submit" style="background:var(--accent); color:#000; width:100%; padding:10px; border:none; border-radius:8px; font-weight:bold; margin-top:10px;">پاشەکەوتکردن</button>
                <button type="button" style="background:transparent; border:1px solid var(--border); color:#fff; width:100%; padding:10px; border-radius:8px; font-weight:bold; margin-top:5px;" onclick="document.getElementById('editModal').style.display='none'">داخستن</button>
            </form>
        </div>
    </div>

    <script>
        function openEdit(id, u, p, n, r) {
            document.getElementById('editForm').action = '/admin/edit_user/' + id;
            document.getElementById('e_user').value = u;
            document.getElementById('e_pass').value = p;
            document.getElementById('e_name').value = n;
            document.getElementById('e_role').value = r;
            document.getElementById('editModal').style.display = 'flex';
        }
    </script>
</body>
</html>
"""

# ----------------- Cashier & Qasa -----------------
WEB_CASHIER_TEMPLATE = COMMON_HEAD + """
<!DOCTYPE html>
<html lang="ckb" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>کاشێر</title>
    <style>
        body { background: var(--bg); color: var(--text); padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; background: var(--card); padding: 15px 20px; border-radius: 12px; border: 1px solid var(--border); }
        .btn-dash { background: var(--accent); color: #000; padding: 8px 16px; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: bold; }
        .tables-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 15px; }
        .t-card { background: var(--card); border: 2px solid var(--border); border-radius: 14px; height: 140px; display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: pointer; transition: 0.2s; box-shadow: 0 4px 10px rgba(0,0,0,0.2); }
        .t-card:hover { border-color: var(--primary); transform: translateY(-3px); }
        .t-card.safari { border-color: #3b82f6; }
        .modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); display: none; align-items: center; justify-content: center; z-index: 1000; padding: 15px; }
        .m-box { background: var(--bg); border: 1px solid var(--border); border-radius: 16px; width: 100%; max-width: 500px; padding: 20px; }
        .m-header { display: flex; justify-content: space-between; border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 15px; font-size: 18px; font-weight: bold; color: var(--primary); }
        table { width: 100%; font-size: 13px; margin-bottom: 15px; text-align: center; }
        th { color: var(--accent); border-bottom: 1px solid var(--border); padding-bottom: 5px; }
        td { padding: 5px 0; border-bottom: 1px dashed var(--border); }
        .calc-box { background: var(--card); padding: 15px; border-radius: 10px; margin-bottom: 15px; }
        .calc-row { display: flex; justify-content: space-between; margin-bottom: 10px; font-weight: bold; align-items: center; }
        .c-input { background: var(--bg); border: 1px solid var(--border); color: #fff; padding: 8px; border-radius: 8px; width: 120px; text-align: center; outline: none; font-weight: bold; }
        .btn-pay { background: var(--accent); color: #000; width: 100%; padding: 12px; border: none; border-radius: 10px; font-weight: bold; font-size: 16px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="header">
        <h2 style="color:var(--accent); font-size:18px;" data-tr="cashier">🛎️ کاشێر</h2>
        <a href="/admin" class="btn-dash" data-tr="dashboard">داشبۆرد</a>
    </div>
    <div class="tables-grid" id="tablesGrid">
        {% for t in active_tables %}
        <div class="t-card {% if 'سەفەری' in t.table_cabin %}safari{% endif %}" onclick="openCh('{{ t.table_cabin }}')">
            <div style="font-size:30px; margin-bottom:5px;">{{ '🛵' if 'سەفەری' in t.table_cabin else '🍽️' }}</div>
            <div style="font-size:16px; font-weight:bold;">{{ t.table_cabin | replace('سەفەری (', '') | replace(')', '') }}</div>
            <div style="font-size:11px; color:#94A3B8; margin-top:5px;">{{ t.rounds }} جار داواکراوە</div>
        </div>
        {% endfor %}
    </div>

    <div class="modal" id="chModal">
        <div class="m-box">
            <div class="m-header"><span id="chTitle">مێز</span><span style="color:var(--danger); cursor:pointer;" onclick="document.getElementById('chModal').style.display='none'">✕</span></div>
            <div style="max-height:200px; overflow-y:auto;">
                <table><thead><tr><th style="text-align:right;">خواردن</th><th>بڕ</th><th>نرخ</th><th>کۆ</th></tr></thead><tbody id="chList"></tbody></table>
            </div>
            <div class="calc-box">
                <div class="calc-row"><span>کۆی حیساب:</span><span id="lblTot" style="color:var(--primary); font-size:18px;">0</span></div>
                <div class="calc-row"><span>وەرگیراو:</span>
                    <div style="display:flex; gap:5px;">
                        <button onclick="adj(-500)" style="background:var(--danger); color:#fff; border:none; border-radius:5px; padding:5px;">-٥٠٠</button>
                        <input type="number" id="txtPaid" class="c-input" oninput="calcChange()">
                        <button onclick="adj(500)" style="background:var(--accent); color:#000; border:none; border-radius:5px; padding:5px;">+٥٠٠</button>
                    </div>
                </div>
                <div class="calc-row"><span>باقی:</span><span id="lblChange" style="color:var(--accent);">0</span></div>
            </div>
            <button class="btn-pay" onclick="pay()">واصڵکردن و چاپ</button>
        </div>
    </div>
    <script>
        let curTable = '', tot = 0;
        function openCh(tbl) {
            curTable = tbl; document.getElementById('chTitle').innerText = tbl;
            fetch('/get_table_orders/' + encodeURIComponent(tbl)).then(r=>r.json()).then(items => {
                let tbody = document.getElementById('chList'); tbody.innerHTML = ''; tot = 0;
                items.forEach(it => {
                    let line = it.price * parseFloat(it.quantity); tot += line;
                    tbody.innerHTML += `<tr><td style="text-align:right;">${it.food_name}</td><td>${parseFloat(it.quantity)}</td><td>${it.price}</td><td>${line}</td></tr>`;
                });
                document.getElementById('lblTot').innerText = tot; document.getElementById('txtPaid').value = tot;
                calcChange(); document.getElementById('chModal').style.display = 'flex';
            });
        }
        function adj(v) { let p = parseInt(document.getElementById('txtPaid').value)||0; document.getElementById('txtPaid').value = Math.max(0, p+v); calcChange(); }
        function calcChange() { let d = (parseInt(document.getElementById('txtPaid').value)||0) - tot; document.getElementById('lblChange').innerText = d; document.getElementById('lblChange').style.color = d>=0?'var(--accent)':'var(--danger)'; }
        function pay() {
            let p = parseInt(document.getElementById('txtPaid').value)||0;
            if(p<=0) return alert('بڕی پارە هەڵەیە');
            fetch('/admin/complete_payment', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({table_number:curTable, amount_paid:p, total_amount:tot})})
            .then(r=>r.json()).then(res=>{ if(res.status==='success'){ printR(res.receipt); } else alert(res.message); });
        }
        function printR(d) {
            let win = window.open('','_blank','width=400,height=600');
            let h = `<!DOCTYPE html><html dir="rtl"><head><style>body{font-family:sans-serif; width:72mm; margin:0 auto; padding:4mm; font-size:12px; text-align:center;} .line{border-top:1px dashed #000; margin:5px 0;} th,td{text-align:center; padding:2px;} .r{text-align:right;}</style></head><body>
            <h3>چێشتماڵە</h3><div>مێزی: ${d.table}</div><div class="line"></div>
            <table style="width:100%"><tr><th class="r">خواردن</th><th>بڕ</th><th>کۆ</th></tr>`;
            d.items.forEach(it => { h += `<tr><td class="r">${it.food_name||it[0]}</td><td>${parseFloat(it.quantity||it[1])}</td><td>${(it.price||it[2])*parseFloat(it.quantity||it[1])}</td></tr>`; });
            h += `</table><div class="line"></div><div style="text-align:right">کۆی گشتی: ${d.total}</div><div style="text-align:right">وەرگیراو: ${d.paid}</div>
            <div class="line"></div><div>سوپاس!</div><script>window.onload=function(){window.print();setTimeout(function(){window.close();},500);}<\/script></body></html>`;
            win.document.write(h); win.document.close();
            document.getElementById('chModal').style.display='none'; setTimeout(()=>location.reload(), 1000);
        }
    </script>
</body>
</html>
"""

WEB_QASA_TEMPLATE = COMMON_HEAD + """
<!DOCTYPE html>
<html lang="ckb" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>قاسە</title>
    <style>
        body { background: var(--bg); color: var(--text); padding: 20px; }
        .top-bar { display: flex; justify-content: space-between; align-items: center; background: var(--card); padding: 14px 20px; border-radius: 12px; border: 1px solid var(--border); margin-bottom: 20px; }
        .btn-dash { background: var(--border); color: #fff; padding: 8px 16px; border-radius: 8px; text-decoration: none; font-weight: 800; }
        .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 22px; }
        .sum-card { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 18px; text-align: center; }
        .sum-val { font-size: 20px; font-weight: 900; margin-top:5px; }
        table { width: 100%; border-collapse: collapse; text-align: center; background: var(--card); border: 1px solid var(--border); }
        th { background: rgba(0,0,0,0.2); padding: 14px; color: var(--primary); border-bottom: 1px solid var(--border); }
        td { padding: 12px; border-bottom: 1px solid var(--border); }
    </style>
</head>
<body>
    <div class="top-bar">
        <h2 style="color:var(--primary); font-size: 18px;">💵 قاسەی فرۆشتن (٢٤ کاتژمێری ڕابردوو)</h2>
        <a href="/admin" class="btn-dash" data-tr="dashboard">⬅️ داشبۆرد</a>
    </div>
    <div class="summary-grid">
        <div class="sum-card"><div>کۆی وەرگیراو لە قاسە</div><div class="sum-val" style="color: var(--accent);">{{ "{:,.0f}".format(total_received) }} د.ع</div></div>
        <div class="sum-card" style="border-color:var(--danger);"><div>کۆی داشکاندن (خەسارەت)</div><div class="sum-val" style="color: var(--danger);">{{ "{:,.0f}".format(total_discount) }} د.ع</div></div>
    </div>
    <table>
        <thead><tr><th>کات</th><th>شوێن/مێز</th><th>وەرگیراو</th><th>داشکاندن</th></tr></thead>
        <tbody>
            {% for r in qasa_rows %}
            <tr><td dir="ltr">{{ r.transaction_time }}</td><td style="font-weight:bold;">{{ r.place_id }}</td><td style="color:var(--accent);">{{ "{:,.0f}".format(r.amount) }}</td><td style="color:var(--danger);">{{ "{:,.0f}".format(r.discount) }}</td></tr>
            {% else %}
            <tr><td colspan="4" style="padding:20px;">هیچ داتایەک نییە لە ٢٤ کاتژمێری ڕابردوو</td></tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

# ----------------- Menu Manager -----------------
WEB_MENU_MANAGER_TEMPLATE = COMMON_HEAD + """
<!DOCTYPE html>
<html lang="ckb" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>مێنیو</title>
    <style>
        body { background: var(--bg); color: var(--text); padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .btn-dash { background: var(--card); border: 1px solid var(--border); color: #fff; padding: 8px 16px; border-radius: 8px; text-decoration: none; font-weight: bold; }
        .card { background: var(--card); border: 1px solid var(--border); padding: 20px; border-radius: 14px; margin-bottom: 20px; }
        .c-input { width: 100%; background: var(--bg); border: 1px solid var(--border); color: #fff; padding: 10px; border-radius: 8px; outline: none; margin-bottom: 10px; }
        .f-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; }
        .f-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 10px; text-align: center; }
        .f-img { width: 100%; height: 130px; object-fit: cover; border-radius: 8px; margin-bottom: 10px; }
        .modal { position: fixed; top:0; left:0; right:0; bottom:0; background: rgba(0,0,0,0.8); display:none; align-items:center; justify-content:center; z-index: 1000; padding: 20px; }
        .m-box { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 20px; width: 100%; max-width: 400px; }
    </style>
</head>
<body>
    <div class="header">
        <h2 style="color:var(--primary); font-size:18px;" data-tr="menu">📖 بەڕێوەبردنی مێنیو</h2>
        <a href="/admin" class="btn-dash" data-tr="dashboard">⬅️ داشبۆرد</a>
    </div>
    <div class="card">
        <form method="POST" action="/admin/add_food" enctype="multipart/form-data" style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
            <input type="text" name="food_name" class="c-input" placeholder="ناو (کوردی)" required style="flex:1; margin:0;">
            <input type="text" name="food_name_ar" class="c-input" placeholder="ناو (عەرەبی)" style="flex:1; margin:0;">
            <input type="text" name="food_name_en" class="c-input" placeholder="ناو (ئینگلیزی)" style="flex:1; margin:0;">
            <input type="number" name="price" class="c-input" placeholder="نرخ" required style="flex:1; margin:0;">
            <input list="cats" name="category" class="c-input" placeholder="پۆلێن" required style="flex:1; margin:0;"><datalist id="cats">{% for c in existing_categories %}<option value="{{ c }}">{% endfor %}</datalist>
            
            <div style="flex:2; display:flex; gap:5px; margin:0;">
                <input type="text" name="image_path_link" class="c-input" placeholder="لینکی وێنە (ئارەزوومەندانە)" style="margin:0;">
                <input type="file" name="food_image" class="c-input" style="margin:0; padding:7px;">
            </div>
            
            <button type="submit" style="background:var(--accent); color:#000; padding:10px; border:none; border-radius:8px; font-weight:bold;">زیادکردن</button>
        </form>
    </div>
    <div class="f-grid">
        {% for f in foods %}
        <div class="f-card">
            <img src="{{ f.image_path if f.image_path else 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=300' }}" class="f-img">
            <div style="font-weight:bold; margin-bottom:5px;">{{ f.food_name }}</div>
            <div style="color:var(--primary); margin-bottom:10px; font-weight:bold;">{{ "{:,.0f}".format(f.price) }} د.ع</div>
            <div style="display:flex; gap:5px;">
                <button style="flex:1; background:#3b82f6; color:#fff; border:none; padding:6px; border-radius:6px; cursor:pointer; font-weight:bold;" onclick="openEdit({{ f.id }}, '{{ f.food_name }}', '{{ f.food_name_ar }}', '{{ f.food_name_en }}', {{ f.price }}, '{{ f.category }}', '{{ f.image_path }}')">دەستکاری</button>
                <a href="/admin/delete_food/{{ f.id }}" style="flex:1; background:var(--danger); color:#fff; padding:6px; border-radius:6px; text-decoration:none; font-weight:bold;" onclick="return confirm('سڕینەوە؟')">سڕینەوە</a>
            </div>
        </div>
        {% endfor %}
    </div>

    <div class="modal" id="editModal">
        <div class="m-box">
            <h3 style="color:var(--primary); margin-bottom:15px; text-align:center;">دەستکاریکردنی خواردن</h3>
            <form id="editForm" method="POST" enctype="multipart/form-data">
                <input type="text" id="e_name" name="food_name" class="c-input" placeholder="ناو (کوردی)" required>
                <input type="text" id="e_name_ar" name="food_name_ar" class="c-input" placeholder="ناو (عەرەبی)">
                <input type="text" id="e_name_en" name="food_name_en" class="c-input" placeholder="ناو (ئینگلیزی)">
                <input type="number" id="e_price" name="price" class="c-input" placeholder="نرخ" required>
                
                <label style="font-size:12px; color:#94a3b8; display:block; margin-bottom:5px;">پۆلێن</label>
                <input list="edit_cats" id="e_cat" name="category" class="c-input" required>
                <datalist id="edit_cats">{% for c in existing_categories %}<option value="{{ c }}">{% endfor %}</datalist>
                
                <label style="font-size:12px; color:#94a3b8; display:block; margin-bottom:5px;">وێنەی نوێ (لینک یان فایل)</label>
                <input type="text" id="e_img_link" name="image_path_link" class="c-input" placeholder="لینکی وێنە (ئارەزوومەندانە)">
                <input type="file" name="food_image" class="c-input" style="padding:7px;">
                
                <button type="submit" style="background:var(--accent); color:#000; width:100%; padding:10px; border:none; border-radius:8px; font-weight:bold; margin-top:10px;">پاشەکەوتکردن</button>
                <button type="button" style="background:transparent; border:1px solid var(--border); color:#fff; width:100%; padding:10px; border-radius:8px; font-weight:bold; margin-top:5px;" onclick="document.getElementById('editModal').style.display='none'">داخستن</button>
            </form>
        </div>
    </div>
    <script>
        function openEdit(id, n, na, ne, p, c, imgUrl) {
            document.getElementById('editForm').action = '/admin/edit_food/' + id;
            document.getElementById('e_name').value = n;
            document.getElementById('e_name_ar').value = na !== 'None' ? na : '';
            document.getElementById('e_name_en').value = ne !== 'None' ? ne : '';
            document.getElementById('e_price').value = p;
            document.getElementById('e_cat').value = c;
            document.getElementById('e_img_link').value = (imgUrl && imgUrl.startsWith('http')) ? imgUrl : '';
            document.getElementById('editModal').style.display = 'flex';
        }
    </script>
</body>
</html>
"""

# ----------------- QR Manager -----------------
QR_MANAGER_TEMPLATE = COMMON_HEAD + """
<!DOCTYPE html>
<html lang="ckb" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>QR مێزەکان</title>
    <style>
        body { background: var(--bg); color: var(--text); padding: 20px; }
        .top-bar { display: flex; justify-content: space-between; align-items: center; background: var(--card); padding: 14px 20px; border-radius: 12px; border: 1px solid var(--border); margin-bottom: 20px; }
        .btn { padding: 8px 16px; border-radius: 8px; font-weight: bold; border: none; cursor: pointer; text-decoration: none; color: #fff; font-size: 13px; }
        .qr-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 15px; }
        .qr-card { background: #fff; color: #000; border-radius: 12px; padding: 15px; text-align: center; }
        .qr-card img { width: 120px; height: 120px; margin: 10px 0; }
        .btn-toggle { width: 100%; padding: 6px; border-radius: 6px; border: none; font-weight: bold; cursor: pointer; font-size: 11px; }
        @media print { body{background:#fff; color:#000; padding:0;} .top-bar, .btn-toggle {display:none;} .qr-grid{grid-template-columns: repeat(4, 1fr); gap:10px;} .qr-card{border:1px solid #000;} }
    </style>
</head>
<body>
    <div class="top-bar">
        <h2 style="color:var(--primary); font-size:18px;" data-tr="qr">🖨️ بارکۆدی مێزەکان</h2>
        <div style="display:flex; gap:10px;">
            <button class="btn" style="background:var(--accent); color:#000;" onclick="window.print()">چاپکردن</button>
            <a href="/admin" class="btn" style="background:var(--border);" data-tr="dashboard">داشبۆرد</a>
        </div>
    </div>
    <div class="qr-grid">
        {% for num in range(1, 91) %}
        {% set is_allowed = perm_dict.get(num, 1) %}
        <div class="qr-card">
            <div style="font-weight:bold;">مێزی {{ num }}</div>
            <img src="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={{ base_url }}/table/{{ num }}">
            <button class="btn-toggle" style="background:{{ '#dcfce7' if is_allowed else '#fee2e2' }}; color:{{ '#166534' if is_allowed else '#991b1b' }};" onclick="tog({{ num }}, this)">{{ 'کراوەیە' if is_allowed else 'داخراوە' }}</button>
        </div>
        {% endfor %}
    </div>
    <script>
        function tog(t, btn) {
            fetch('/toggle_table_permission', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({table_number:t}) })
            .then(r=>r.json()).then(d=>{ if(d.status==='success'){ btn.innerText=d.allow_ordering?'کراوەیە':'داخراوە'; btn.style.background=d.allow_ordering?'#dcfce7':'#fee2e2'; btn.style.color=d.allow_ordering?'#166534':'#991b1b'; } });
        }
    </script>
</body>
</html>
"""

# ----------------- Desktop Tables -----------------
DESKTOP_TABLES_TEMPLATE = COMMON_HEAD + """
<!DOCTYPE html>
<html lang="ckb" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>هەڵبژاردنی مێز</title>
    <style>
        body { padding:20px; margin: 0; overflow-y: auto; }
        .hdr { display:flex; justify-content:space-between; margin-bottom:20px; background:var(--card); padding:15px; border-radius:12px; border:1px solid var(--border); align-items:center; }
        .g { display:grid; grid-template-columns:repeat(8,1fr); gap:15px; max-width:1400px; margin:0 auto; }
        .b { background:var(--card); border:1px solid var(--border); padding:20px; text-align:center; font-size:24px; font-weight:bold; color:var(--text); text-decoration:none; border-radius:12px; box-shadow: 0 4px 6px rgba(0,0,0,0.2); height:100px; display:flex; flex-direction:column; align-items:center; justify-content:center; overflow:hidden; }
        .b.act { background:var(--accent); color:#000; border-color:var(--accent); }
        .btn-take { background:#3b82f6; color:#fff; border:none; padding:10px 20px; border-radius:8px; font-weight:bold; cursor:pointer; text-decoration:none; }
        @media(max-width:900px){ .g{grid-template-columns:repeat(5,1fr); gap:10px;} .b{padding:15px; font-size:20px;} }
    </style>
</head>
<body>
    <div class="hdr">
        <a href="/logout" style="color:var(--danger); font-weight:bold; text-decoration:none;">دەرچوون ✕</a>
        <h2 style="color:var(--primary); font-size:18px;">تکایە مێزێک هەڵبژێرە</h2>
        <div style="display:flex; gap:10px;">
            {% if session.get('role') == 'admin' %}<a href="/admin" class="btn-take" style="background:var(--accent); color:#000;">داشبۆرد</a>{% endif %}
            <button class="btn-take" onclick="let n=prompt('ناوی کڕیار:'); if(n) location.href='/desktop?table='+encodeURIComponent('سەفەری ('+n+')')">سەفەری 🛵</button>
        </div>
    </div>
    <div class="g" id="tg">
        {% for n in range(1,91) %}<a href="/desktop?table={{n}}" id="tb-{{n}}" class="b">{{n}}</a>{% endfor %}
        {% for t in active_takeaways %}<a href="/desktop?table={{t|urlencode}}" class="b act" style="font-size:14px; padding:10px;">
            <span style="font-size: 24px;">🛵</span>
            <span style="font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; width: 100%;">{{t.replace('سەفەری (','').replace(')','')}}</span>
        </a>{% endfor %}
    </div>
    <script>
        setInterval(()=>{fetch('/get_active_tables?t='+Date.now()).then(r=>r.json()).then(a=>{for(let i=1;i<=90;i++){let e=document.getElementById('tb-'+i);if(e){if(a.includes(i.toString()))e.classList.add('act');else e.classList.remove('act');}}});},3000);
    </script>
</body>
</html>
"""

# ----------------- Mobile Tables -----------------
MOBILE_TABLES_TEMPLATE = DESKTOP_TABLES_TEMPLATE.replace('grid-template-columns:repeat(8,1fr)', 'grid-template-columns:repeat(4,1fr)').replace('/desktop', '/mobile/menu')

# ----------------- Desktop POS (iPad/PC) -----------------
DESKTOP_TEMPLATE = COMMON_HEAD + """
<!DOCTYPE html>
<html lang="ckb" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>POS - {{ selected_table }}</title>
    <style>
        * { user-select: none; }
        body { margin: 0; padding: 0; background: var(--bg); color: var(--text); height: 100vh; overflow: hidden; }
        .desktop-main-layout { display: flex; flex-direction: row; width: 100vw; height: 100vh; }
        
        .cart-side { width: 40%; height: 100vh; display: flex; flex-direction: column; padding: 15px; background: rgba(0,0,0,0.2); border-left: 1px solid var(--border); overflow: hidden; }
        .c-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
        .btn-top { background: var(--card); border: 1px solid var(--border); color: #fff; padding: 6px 10px; border-radius: 6px; font-size: 11px; font-weight: bold; cursor: pointer; text-decoration: none; }
        
        .c-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px; padding-right: 5px; }
        .c-row { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 10px; display: flex; justify-content: space-between; align-items: center; }
        
        .c-ctrl { display: flex; align-items: center; gap: 6px; background: var(--bg); padding: 4px; border-radius: 8px; }
        .c-btn { width: 28px; height: 28px; border-radius: 6px; border: none; background: #334155; color: #fff; font-weight: bold; font-size: 14px; cursor: pointer; }
        .c-btn.add { background: var(--primary); color: #000; }
        
        .cart-bottom { flex-shrink: 0; background: var(--bg); padding: 10px; border-radius: 12px; border: 1px solid var(--border); margin-top: 5px; }
        .c-tot { font-size: 15px; font-weight: bold; color: var(--accent); display: flex; justify-content: space-between; margin-bottom: 8px; }
        .btn-send { background: var(--accent); color: #000; border: none; padding: 8px; border-radius: 8px; font-size: 13px; font-weight: bold; cursor: pointer; width: 100%; box-shadow: 0 4px 10px rgba(16, 185, 129, 0.3); }

        .menu-side { width: 60%; height: 100vh; display: flex; flex-direction: column; padding: 15px; overflow: hidden; }
        .cat-bar { display: flex; gap: 10px; overflow-x: auto; padding-bottom: 10px; margin-bottom: 15px; flex-shrink: 0; }
        .cat-btn { background: var(--card); border: 2px solid var(--border); border-radius: 12px; padding: 5px 15px; min-width: 80px; text-align: center; cursor: pointer; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .cat-btn.active { border-color: var(--primary); background: rgba(0,0,0,0.3); }
        .cat-visual-img { width: 40px; height: 40px; border-radius: 8px; object-fit: cover; margin-bottom: 5px; pointer-events: none; }
        .cat-visual-title { font-size: 11px; font-weight: bold; color: #fff; pointer-events: none; }

        .food-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; overflow-y: auto; padding-right: 5px; align-content: start; padding-bottom: 20px; }
        .f-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 8px; text-align: center; cursor: pointer; transition: 0.1s; display: flex; flex-direction: column; justify-content: space-between; min-height: 220px; }
        .f-card:active { transform: scale(0.97); }
        .f-img { width: 100%; height: 130px; object-fit: cover; border-radius: 8px; margin-bottom: 6px; pointer-events: none; }
        .f-name { font-size: 14px; font-weight: bold; line-height: 1.3; margin-bottom: 4px; pointer-events: none; }
        .f-price { color: var(--accent); font-weight: bold; font-size: 13px; margin-bottom: 2px; pointer-events: none; }
        .opt-select { width: 100%; background: var(--bg); border: 1px solid var(--border); color: #fff; border-radius: 6px; padding: 4px; font-size: 11px; outline: none; }
        
        #toastMsg { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: var(--accent); color: #000; padding: 10px 24px; border-radius: 30px; font-size: 14px; font-weight: 700; z-index: 1000; display: none; }

        .modal-transfer { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.75); display: none; align-items: center; justify-content: center; z-index: 2000; padding: 16px; }
        .modal-transfer-box { background: var(--card); border: 2px solid var(--border); border-radius: 14px; padding: 20px; width: 100%; max-width: 360px; color: #fff; text-align: center; }
    </style>
</head>
<body dir="rtl">
    <div id="toastMsg">✅ نێردرا</div>
    
    <div class="desktop-main-layout">
        <div class="cart-side">
            <div class="c-header">
                <div style="background:var(--primary); color:#000; padding:4px 10px; border-radius:6px; font-weight:bold; font-size:13px;">📍 {{ selected_table }}</div>
                <div style="display:flex; gap:5px;">
                    <button type="button" class="btn-top" style="background:#3b82f6;" onclick="openTransferModal()">🔄 گواستنەوە</button>
                    <a href="/desktop/tables" class="btn-top">گەڕانەوە</a>
                    <button class="btn-top" style="color:var(--danger);" onclick="clrT()">سڕینەوە</button>
                </div>
            </div>
            
            <div class="c-list" id="cList"></div>
            
            <div class="cart-bottom">
                <div class="c-tot"><span>کۆی گشتی:</span><span id="totTxt">0</span></div>
                <div style="display:flex; gap:10px;">
                    <button class="btn-send" style="background:#8b5cf6; flex:1; display:none; color:#fff;" id="btnDiv" onclick="addDiv()">+ هێڵ</button>
                    <button class="btn-send" style="flex:2;" onclick="sendO()">ناردن ➔</button>
                </div>
            </div>
        </div>

        <div class="menu-side">
            <div class="cat-bar">
                <div class="cat-btn active" onclick="fCat('all', this)">
                    <img src="https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=140" class="cat-visual-img">
                    <span class="cat-visual-title" data-tr="all">هەموو</span>
                </div>
                {% for cat, items in categories.items() %}
                <div class="cat-btn" onclick="fCat('cat-{{ loop.index }}', this)">
                    <img src="{{ items[0].image_path if items[0].image_path else 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=140' }}" class="cat-visual-img" onerror="this.src='https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=140'">
                    <span class="cat-visual-title">{{ cat }}</span>
                </div>
                {% endfor %}
            </div>
            <div class="food-grid" id="fGrid">
                {% for cat, items in categories.items() %}
                {% set cat_idx = loop.index %}
                {% for it in items %}
                {% set c_name = (it.category or '') | replace('ي', 'ی') | trim %}
                {% set show_fish = ('ماسی' in c_name or 'ماسی' in it.food_name) %}
                <div class="f-card cat-item cat-{{ cat_idx }}" onclick="addF('{{ it.food_name | replace("'", "\\'") }}', {{ it.price }}, '{{ (it.category or '') | replace("'", "\\'") }}', {{ it.id }})">
                    <img src="{{ it.image_path if it.image_path else 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=300' }}" class="f-img" onerror="this.src='https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=300'">
                    <div class="f-name food-title-disp" data-ku="{{ it.food_name }}" data-ar="{{ it.food_name_ar or it.food_name }}" data-en="{{ it.food_name_en or it.food_name }}">{{ it.food_name }}</div>
                    <div class="f-price">{{ "{:,.0f}".format(it.price) }}</div>
                    
                    {% set show_r = ('کوڵاو' in c_name or 'پەلەوەر' in c_name or 'کورد' in c_name) %}
                    {% set show_c = ('پەلەوەر' in c_name or 'مریشک' in c_name) %}
                    {% if show_r or show_c or show_fish %}
                    <div style="display:flex; gap:4px; width:100%;">
                        {% if show_fish %}
                        <input type="number" id="w_{{it.id}}" class="opt-select" step="0.25" min="0.25" value="1" onclick="event.stopPropagation()" placeholder="کێش">
                        {% endif %}
                        {% if show_r %}<select class="opt-select" id="r_{{it.id}}" onclick="event.stopPropagation()"><option value="">ج. برنج</option><option value="درێژ">درێژ</option><option value="خڕ">خڕ</option><option value="کوردی">کوردی</option></select>{% endif %}
                        {% if show_c %}<select class="opt-select" id="c_{{it.id}}" onclick="event.stopPropagation()"><option value="">ب. مریشک</option><option value="سینگ">سینگ</option><option value="ڕان">ڕان</option></select>{% endif %}
                    </div>
                    {% endif %}
                </div>
                {% endfor %}
                {% endfor %}
            </div>
        </div>
    </div>

    <div class="modal-transfer" id="transferModal">
        <div class="modal-transfer-box">
            <h3 style="color:var(--primary); margin-bottom:12px;">گواستنەوە بۆ مێزێکی تر</h3>
            <select id="newTableSelect" style="width:100%; padding:10px; background:var(--bg); border:1px solid var(--border); color:#fff; border-radius:8px; margin-bottom:14px;">
                {% for n in range(1, 91) %}
                    <option value="{{ n }}">مێزی {{ n }}</option>
                {% endfor %}
            </select>
            <button type="button" onclick="confirmTransferTable()" style="background:var(--accent); color:#000; padding:10px; border:none; border-radius:8px; font-weight:bold; width:100%;">پشتڕاستکردنەوە</button>
            <button type="button" onclick="closeTransferModal()" style="background:none; border:none; color:#94a3b8; width:100%; margin-top:10px; cursor:pointer;">داخستن</button>
        </div>
    </div>

    <script>
        let cart = [], orig = []; const tbl = "{{ selected_table }}";

        window.addEventListener('langChanged', () => {
            let l = window.savedLang;
            document.querySelectorAll('.food-title-disp').forEach(el => {
                el.innerText = el.getAttribute('data-' + l) || el.getAttribute('data-ku');
            });
            ren();
        });

        function fCat(id, btn) {
            document.querySelectorAll('.cat-btn').forEach(b=>b.classList.remove('active')); btn.classList.add('active');
            document.querySelectorAll('.cat-item').forEach(i => { i.style.display = (id==='all' || i.classList.contains(id)) ? 'flex' : 'none'; });
        }

        function addF(n, p, c, id) {
            let fn = n, pts = [];
            let rel = document.getElementById('r_'+id), cel = document.getElementById('c_'+id);
            if(rel && rel.value) pts.push(rel.value);
            if(cel && cel.value) pts.push(cel.value);
            if(pts.length>0) fn += ` (${pts.join(' - ')})`;
            
            let qtyToAdd = 1;
            let wEl = document.getElementById('w_'+id);
            if(wEl && wEl.value) {
                let w = parseFloat(wEl.value);
                if(!isNaN(w) && w > 0) qtyToAdd = w;
            }

            let fd = false;
            for(let i=cart.length-1; i>=0; i--) {
                if(cart[i].is_divider) break;
                if(cart[i].ku === fn) { cart[i].qty += qtyToAdd; fd=true; break; }
            }
            if(!fd) cart.push({is_divider:false, ku:fn, full_name:fn, price:p, qty:qtyToAdd, cat:c});
            ren();
        }

        function updQ(idx, d) { 
            let oQ = orig.find(o=>o.ku===cart[idx].ku && !o.is_divider); oQ = oQ?oQ.qty:0;
            let nQ = cart[idx].qty + d;
            cart[idx].qty = nQ; 
            if(cart[idx].qty <= 0) cart.splice(idx, 1); 
            ren(); 
        }
        function delI(idx) { cart.splice(idx, 1); ren(); }

        function editNote(idx) {
            let note = prompt('تێبینی (بۆ نموونە: بێ پیاز):');
            if (note && note.trim() !== '') {
                cart[idx].ku += ' (' + note.trim() + ')';
                cart[idx].full_name = cart[idx].ku;
                ren();
            }
        }

        function addDiv() {
            if(cart.length===0 || (cart[cart.length-1] && cart[cart.length-1].is_divider)) return;
            cart.push({is_divider:true, ku:'─── قاپی نوێ ───', full_name:'───', price:0, qty:1, cat:''}); ren();
        }

        function ren() {
            let h = '', tot = 0, pN = 1, hG = false;
            let l = window.savedLang;
            cart.forEach((it, i) => {
                if(it.is_divider) {
                    pN++; h += `<div style="background:#8b5cf6; padding:8px; border-radius:6px; font-size:13px; font-weight:bold; display:flex; justify-content:space-between; margin-bottom:5px;"><span>🍽 قاپی ${pN}</span><span onclick="delI(${i})" style="cursor:pointer; background:#ef4444; padding:2px 8px; border-radius:4px; color:#fff;">✕</span></div>`;
                } else {
                    if(it.cat==='برژاو' || it.ku.includes('کەباب')) hG = true;
                    tot += it.price * it.qty;
                    let dName = it[l] || it.ku;
                    
                    h += `<div class="c-row">
                        <div style="flex:1; text-align:right; font-size:13px; font-weight:bold; padding-left:10px;">${dName}</div>
                        <div class="c-ctrl">
                            <span style="color:var(--accent); font-size:12px; font-weight:bold; margin-left:10px;">${(it.price*it.qty).toLocaleString()}</span>
                            <button class="c-btn" style="background:#ef4444; font-size:12px;" onclick="delI(${i})">🗑</button>
                            <button class="c-btn" style="background:#3b82f6; font-size:12px;" onclick="editNote(${i})">✏️</button>
                            <button class="c-btn" onclick="updQ(${i},-1)">-</button>
                            <span style="width:30px;text-align:center;font-weight:bold;font-size:14px;">${parseFloat(it.qty.toFixed(3))}</span>
                            <button class="c-btn add" onclick="updQ(${i},1)">+</button>
                        </div>
                    </div>`;
                }
            });
            document.getElementById('cList').innerHTML = h;
            document.getElementById('totTxt').innerText = tot.toLocaleString();
            document.getElementById('btnDiv').style.display = hG ? 'block' : 'none';
        }

        function sendO() {
            if(cart.length===0) return;
            let fCart = cart.map(it => ({ is_divider: it.is_divider, food_name: it.ku, qty: it.qty, price: it.price, cat: it.cat || 'گشتی' }));
            fetch('/save_cart_order', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({table_number:tbl, cart_items:fCart, original_items:orig}) })
            .then(r=>r.json()).then(d=>{ if(d.status==='success') location.href='/desktop/tables'; else alert('هەڵە'); });
        }

        function clrT() {
            if(confirm('سڕینەوە؟')) fetch('/clear_table_orders', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({table_number:tbl})}).then(()=>location.reload());
        }

        function openTransferModal() { document.getElementById('transferModal').style.display = 'flex'; }
        function closeTransferModal() { document.getElementById('transferModal').style.display = 'none'; }
        function confirmTransferTable() {
            let target = document.getElementById('newTableSelect').value;
            if (target === tbl) { alert("هەمان مێزە!"); return; }
            fetch('/transfer_table_orders', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ from_table: tbl, to_table: target })
            }).then(r => r.json()).then(res => {
                if(res.status === 'success') location.href = '/desktop?table=' + target;
                else alert(res.message);
            });
        }

        fetch('/get_table_orders/'+encodeURIComponent(tbl)).then(r=>r.json()).then(d=>{
            if(d) {
                d.forEach(it=>{
                    let o = {is_divider:it.food_name.includes('───'), ku:it.food_name, full_name:it.food_name, price:parseFloat(it.price), qty:parseFloat(it.quantity), cat:it.category};
                    cart.push(o); orig.push(JSON.parse(JSON.stringify(o)));
                });
                ren();
            }
        });
    </script>
</body>
</html>
"""

# ----------------- Mobile POS (Customer/Waiter) -----------------
CUSTOMER_MENU_TEMPLATE = COMMON_HEAD + """
<!DOCTYPE html>
<html lang="ckb" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>مێنیو - {{ table_num }}</title>
    <style>
        * { user-select: none; }
        body { background: var(--bg); color: var(--text); padding-bottom: {{ '115px' if allow_ordering else '30px' }}; min-height: 100vh; }
        .hdr { background: var(--card); padding: 12px 15px; position: sticky; top: 0; z-index: 100; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
        .pill { background: var(--primary); color: #000; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }
        .cats { display: flex; overflow-x: auto; gap: 8px; padding: 10px 15px; }
        .c-btn { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 5px 15px; white-space: nowrap; font-size: 12px; font-weight: bold; display: flex; flex-direction: column; align-items: center; }
        .c-btn.act { border-color: var(--primary); background: rgba(0,0,0,0.3); color: var(--primary); }
        .cat-visual-img { width: 50px; height: 50px; border-radius: 8px; object-fit: cover; margin-bottom: 5px; }
        
        .f-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; padding: 0 15px; }
        .f-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 8px; text-align: center; }
        .f-img { width: 100%; height: 110px; object-fit: cover; border-radius: 8px; margin-bottom: 8px; }
        .f-name { font-size: 13px; font-weight: bold; margin-bottom: 4px; }
        .f-price { color: var(--accent); font-weight: bold; font-size: 12px; margin-bottom: 8px; }
        .opt-select { width:100%; background:var(--bg); border:1px solid var(--border); color:var(--primary); border-radius:6px; padding:4px; font-size:11px; outline:none; margin-bottom:6px; }
        .stp { display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.2); border-radius: 8px; padding: 2px; }
        .s-btn { width: 30px; height: 30px; border: none; border-radius: 6px; background: #334155; color: #fff; font-weight: bold; font-size: 18px; }
        .s-btn.add { background: var(--primary); color: #000; }
        .btm-bar { position: fixed; bottom: 0; left: 0; right: 0; background: var(--card); padding: 15px; border-top: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; z-index: 200; }
        .modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); display: none; align-items: flex-end; z-index: 300; }
        .m-box { background: var(--bg); width: 100%; max-height: 85vh; border-radius: 20px 20px 0 0; padding: 20px; display: flex; flex-direction: column; border-top: 2px solid var(--primary); }
        .m-list { flex: 1; overflow-y: auto; margin-bottom: 15px; }
        .c-row { background: var(--card); border: 1px solid var(--border); padding: 10px; border-radius: 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
        .btn-send { background: var(--accent); color: #000; border: none; padding: 15px; border-radius: 12px; font-weight: bold; font-size: 15px; width: 100%; }
        #toast { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: var(--accent); color: #000; padding: 10px 20px; border-radius: 20px; font-weight: bold; font-size: 13px; display: none; z-index: 1000; }
        
        .wl-lang-btn { background: var(--card); border: 2px solid var(--border); color: var(--text); padding: 10px 20px; border-radius: 10px; font-weight: bold; font-size:14px; cursor:pointer; }
        .wl-lang-btn.active { border-color: var(--primary); background: rgba(0,0,0,0.3); color: var(--primary); }
    </style>
</head>
<body>
    <div id="welcomeOverlay" style="position:fixed; inset:0; background:var(--bg); z-index:9999; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:20px;">
        <h1 style="color:var(--primary); margin-bottom:10px;">✨ چێشتماڵە</h1>
        <h3 style="color:var(--text); margin-bottom:30px; font-size:16px;">بەخێربێیت بۆ مێزی {{ table_num }}</h3>
        
        <p style="color:var(--text); margin-bottom:15px; font-size:14px;">تکایە زمانێک هەڵبژێرە / Select Language</p>
        <div style="display:flex; gap:10px; margin-bottom:40px;">
            <button class="wl-lang-btn" onclick="selWLang('ku', this)">کوردی</button>
            <button class="wl-lang-btn" onclick="selWLang('ar', this)">العربية</button>
            <button class="wl-lang-btn" onclick="selWLang('en', this)">English</button>
        </div>
        
        <button onclick="closeWelcome()" style="background:var(--accent); color:#000; padding:15px; border:none; border-radius:12px; font-size:18px; font-weight:bold; width:100%; max-width:300px; cursor:pointer;">بەردەوامبە ➔</button>
    </div>

    <div id="toast">✅ نێردرا</div>
    <div class="hdr">
        <span style="font-weight:bold; color:var(--primary);">چێشتماڵە</span>
        <span class="pill">{{ table_num }}</span>
    </div>
    {% if not allow_ordering %}
    <div style="text-align:center; padding:5px; background:var(--danger); font-size:11px; font-weight:bold;">تەنها بۆ بینینە</div>
    {% endif %}
    
    <div class="cats">
        <div class="c-btn act" onclick="fCat('all', this)">
            <img src="https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=100" class="cat-visual-img">
            <span data-tr="all">هەموو</span>
        </div>
        {% for cat, items in categories.items() %}
        <div class="c-btn" onclick="fCat('c-{{ loop.index }}', this)">
            <img src="{{ items[0].image_path if items[0].image_path else 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=100' }}" class="cat-visual-img" onerror="this.src='https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=100'">
            <span>{{ cat }}</span>
        </div>
        {% endfor %}
    </div>

    <div class="f-grid" id="fGrid">
        {% for cat, items in categories.items() %}
        {% set cat_idx = loop.index %}
        {% for it in items %}
        <div class="f-card cat-it c-{{ cat_idx }}">
            <img src="{{ it.image_path if it.image_path else 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=300' }}" class="f-img" onerror="this.src='https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=300'">
            <div class="f-name food-title-disp" data-ku="{{ it.food_name }}" data-ar="{{ it.food_name_ar or it.food_name }}" data-en="{{ it.food_name_en or it.food_name }}">{{ it.food_name }}</div>
            <div class="f-price">{{ "{:,.0f}".format(it.price) }}</div>
            {% if allow_ordering %}
            {% set c_name = (it.category or '') | replace('ي', 'ی') | trim %}
            {% set show_fish = ('ماسی' in c_name or 'ماسی' in it.food_name) %}
            {% set show_r = ('کوڵاو' in c_name or 'پەلەوەر' in c_name or 'کورد' in c_name) %}
            {% set show_c = ('پەلەوەر' in c_name or 'مریشک' in c_name) %}
            
            {% if show_r or show_c or show_fish %}
                {% if show_fish %}
                <input type="number" id="w_{{it.id}}" class="opt-select" step="0.25" min="0.25" value="1" onclick="event.stopPropagation()" placeholder="کێش">
                {% endif %}
                {% if show_r %}<select class="opt-select" id="rm_{{it.id}}"><option value="">ج. برنج</option><option value="درێژ">درێژ</option><option value="خڕ">خڕ</option><option value="کوردی">کوردی</option></select>{% endif %}
                {% if show_c %}<select class="opt-select" id="cm_{{it.id}}"><option value="">ب. مریشک</option><option value="سینگ">سینگ</option><option value="ڕان">ڕان</option></select>{% endif %}
            {% endif %}
            <div class="stp">
                <button class="s-btn" onclick="addF('{{ it.food_name | replace("'", "\\'") }}',-1,{{it.price}},'{{it.category}}',{{it.id}})">-</button>
                <span style="font-weight:bold; font-size:14px;" data-name="{{it.food_name}}" class="qty-lbl">0</span>
                <button class="s-btn add" onclick="addF('{{ it.food_name | replace("'", "\\'") }}',1,{{it.price}},'{{it.category}}',{{it.id}})">+</button>
            </div>
            {% endif %}
        </div>
        {% endfor %}
        {% endfor %}
    </div>

    {% if allow_ordering %}
    <div class="btm-bar">
        <div style="display:flex; align-items:center; gap:10px;">
            <span style="font-size:20px;">🛒</span>
            <span style="background:var(--primary); color:#000; padding:2px 8px; border-radius:10px; font-weight:bold; font-size:12px;" id="cBadge">0</span>
            <span style="font-weight:bold;" id="cTot">0 د.ع</span>
        </div>
        <button style="background:var(--accent); color:#000; border:none; padding:10px 20px; border-radius:10px; font-weight:bold;" onclick="document.getElementById('mCart').style.display='flex'" data-tr="cart">سەبەتە ➔</button>
    </div>

    <div class="modal" id="mCart" onclick="if(event.target.id==='mCart') this.style.display='none'">
        <div class="m-box" onclick="event.stopPropagation()">
            <div style="display:flex; justify-content:space-between; margin-bottom:15px; border-bottom:1px solid var(--border); padding-bottom:10px;">
                <span style="font-weight:bold; color:var(--primary);" data-tr="cart">🛒 سەبەتە</span>
                <span style="color:var(--danger); cursor:pointer; font-weight:bold;" onclick="document.getElementById('mCart').style.display='none'">✕</span>
            </div>
            <div class="m-list" id="mList"></div>
            <div style="display:flex; gap:10px;">
                <button class="btn-send" style="background:#8b5cf6; flex:1; display:none; color:#fff;" id="btnDivM" onclick="addDivM()">+ هێڵ</button>
                <button class="btn-send" style="flex:2;" onclick="sendOrder()" data-tr="send">ناردن بۆ مەتبەخ</button>
            </div>
        </div>
    </div>
    {% endif %}

    <script>
        let cart=[], orig=[]; const tbl="{{ table_num }}"; const isW=location.href.includes('/mobile/menu');

        let tempWL = localStorage.getItem('lang') || 'ku';
        function selWLang(l, btn) {
            tempWL = l;
            document.querySelectorAll('.wl-lang-btn').forEach(b=>b.classList.remove('active'));
            btn.classList.add('active');
        }
        function closeWelcome() {
            setLang(tempWL);
            document.getElementById('welcomeOverlay').style.display = 'none';
        }

        document.addEventListener("DOMContentLoaded", () => {
            if(isW) { document.getElementById('welcomeOverlay').style.display = 'none'; }
            else {
                let el = document.querySelector(`.wl-lang-btn[onclick*="'${tempWL}'"]`);
                if(el) selWLang(tempWL, el);
            }
        });

        window.addEventListener('langChanged', () => {
            let l = window.savedLang;
            document.querySelectorAll('.food-title-disp').forEach(el => {
                el.innerText = el.getAttribute('data-' + l) || el.getAttribute('data-ku');
            });
            ren();
        });

        function fCat(id, btn) {
            document.querySelectorAll('.c-btn').forEach(b=>b.classList.remove('act')); btn.classList.add('act');
            document.querySelectorAll('.cat-it').forEach(i => i.style.display = (id==='all' || i.classList.contains(id)) ? 'block' : 'none');
        }

        function addF(n, d, p, c, id) {
            let fn = n, rel = document.getElementById('rm_'+id), cel = document.getElementById('cm_'+id);
            if(rel && rel.value) fn += ` (${rel.value})`;
            if(cel && cel.value) fn += ` (${cel.value})`;
            
            let qtyToAdd = d;
            let wEl = document.getElementById('w_'+id);
            if(wEl && wEl.value) {
                let w = parseFloat(wEl.value);
                if(!isNaN(w) && w > 0) {
                    qtyToAdd = d > 0 ? w : -w;
                }
            }

            let oQ = orig.find(o=>o.ku===fn && !o.is_divider); oQ = oQ?oQ.qty:0;
            let f = false;
            for(let i=cart.length-1; i>=0; i--) {
                if(cart[i].is_divider) break;
                if(cart[i].ku === fn) {
                    let nQ = cart[i].qty + qtyToAdd;
                    if(!isW && nQ < oQ) return alert("ناتوانیت داواکاری پێشوو کەم بکەیتەوە!");
                    cart[i].qty = nQ;
                    if(cart[i].qty<=0) cart.splice(i,1);
                    f=true; break;
                }
            }
            if(!f && d>0) {
                cart.push({is_divider:false, ku:fn, full_name:fn, price:p, qty:qtyToAdd, cat:c});
            }
            ren();
        }

        function updQ(i, d) {
            let oQ = orig.find(o=>o.ku===cart[i].ku && !o.is_divider); oQ = oQ?oQ.qty:0;
            let nQ = cart[i].qty + d;
            if(!isW && nQ < oQ) return alert("ناتوانیت داواکاری پێشوو کەم بکەیتەوە!");
            cart[i].qty = nQ;
            if(cart[i].qty<=0) cart.splice(i,1);
            ren();
        }

        function delI(i) { cart.splice(i, 1); ren(); }
        
        function edtM(i) { 
            let n=prompt('تێبینی (بۆ نموونە: بێ پیاز):'); 
            if(n && n.trim() !== '') {
                cart[i].ku += ` (${n.trim()})`;
                cart[i].full_name = cart[i].ku; 
                ren();
            } 
        }

        function addDivM() { 
            if(cart.length===0 || (cart[cart.length-1] && cart[cart.length-1].is_divider)) return; 
            cart.push({is_divider:true, ku:'─── قاپی نوێ ───', full_name:'───', price:0, qty:1, cat:''}); 
            ren(); 
        }

        function ren() {
            let cnt=0, h='', pN=1, hG=false, tot=0;
            let l = window.savedLang;
            cart.forEach((it, i) => {
                if(it.is_divider) {
                    pN++; h += `<div style="background:#8b5cf6; color:#fff; padding:6px 10px; border-radius:6px; font-size:12px; font-weight:bold; display:flex; justify-content:space-between; margin-bottom:5px;"><span>🍽 قاپی ${pN}</span><span onclick="delI(${i})" style="cursor:pointer; background:#ef4444; padding:2px 8px; border-radius:4px;">✕</span></div>`;
                } else {
                    if(it.cat==='برژاو' || it.ku.includes('کەباب')) hG=true;
                    cnt += it.qty; tot += it.price*it.qty;
                    let dName = it[l] || it.ku;
                    h += `<div class="c-row">
                        <div style="flex:1; text-align:right; font-size:14px; font-weight:bold;">${dName}</div>
                        <div style="display:flex; align-items:center; gap:6px;">
                            <span style="color:var(--accent); font-size:12px; font-weight:bold;">${(it.price*it.qty).toLocaleString()}</span>
                            <button class="s-btn" style="background:#ef4444; font-size:12px;" onclick="delI(${i})">🗑</button>
                            <button class="s-btn" style="background:#3b82f6; font-size:12px;" onclick="edtM(${i})">✏️</button>
                            <button class="s-btn" onclick="updQ(${i},-1)">-</button>
                            <span style="width:30px; text-align:center; font-weight:bold; background:rgba(255,255,255,0.1); border-radius:4px; padding:2px;">${parseFloat(it.qty.toFixed(3))}</span>
                            <button class="s-btn add" onclick="updQ(${i},1)">+</button>
                        </div>
                    </div>`;
                }
            });
            let ls=document.getElementById('mList'); if(ls) ls.innerHTML=h;
            let cb=document.getElementById('cBadge'); if(cb) { cb.innerText=parseFloat(cnt.toFixed(3)); document.getElementById('cTot').innerText = tot.toLocaleString() + ' د.ع'; }
            let dV=document.getElementById('btnDivM'); if(dV) dV.style.display=hG?'block':'none';
            document.querySelectorAll('.qty-lbl').forEach(el => {
                let n=el.getAttribute('data-name'), tq=0;
                cart.forEach(c => { if(!c.is_divider && c.ku.includes(n)) tq+=c.qty; });
                el.innerText=parseFloat(tq.toFixed(3));
            });
        }

        function toast(m, e=false) {
            let t = document.getElementById('toast'); t.innerText=m; t.style.background=e?'var(--danger)':'var(--accent)'; t.style.display='block';
            setTimeout(()=>t.style.display='none', 2000);
        }

        function sendOrder() {
            if(cart.length===0) return toast('سەبەتە بەتاڵە', true);
            let fCart = cart.map(it => ({ is_divider: it.is_divider, food_name: it.ku, qty: it.qty, price: it.price, cat: it.cat || 'گشتی' }));
            fetch('/save_cart_order', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({table_number:tbl, cart_items:fCart, original_items:orig}) })
            .then(r=>r.json()).then(d=>{
                if(d.status==='success') { document.getElementById('mCart').style.display='none'; if(isW) location.href='/mobile/tables'; else fetchTable(); }
            });
        }

        function fetchTable() {
            fetch('/get_table_orders/'+encodeURIComponent(tbl)).then(r=>r.json()).then(d=>{
                cart=[]; orig=[];
                if(d) { d.forEach(it=>{ 
                    let o={is_divider:it.food_name.includes('───'), ku:it.food_name, full_name:it.food_name, price:parseFloat(it.price), qty:parseFloat(it.quantity), cat:it.category}; 
                    cart.push(o); orig.push(JSON.parse(JSON.stringify(o))); 
                }); } ren();
            });
        }
        window.onload = fetchTable;
    </script>
</body>
</html>
"""

# ==========================================
# 6. ڕێڕەوەکان (Routes)
# ==========================================

@app.route('/')
def index():
    session.clear()
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        uname = normalize_digits(request.form.get('username', '')).strip()
        pwd = normalize_digits(request.form.get('password', '')).strip()

        if uname == '' and pwd == '':
            session.clear()
            session.permanent = True
            session['authenticated'] = True
            session['role'] = 'waiter'
            session['full_name'] = 'گارسۆن'
            return redirect(url_for('desktop_tables'))

        conn = None
        user_row = None
        try:
            conn = get_db()
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (uname, pwd))
                user_row = cur.fetchone()
        except: pass
        finally:
            if conn:
                try: conn.close()
                except: pass

        if user_row:
            if not user_row.get('is_active', 1): return render_template_string(LOGIN_TEMPLATE, error='بلۆککراوە!')
            session.clear()
            session.permanent = True
            session['authenticated'] = True
            session['user_id'] = user_row['id']
            session['username'] = user_row['username']
            session['full_name'] = user_row.get('full_name', '')
            role = user_row.get('role', 'Waiter')
            if role in ['Manager', 'Admin', 'admin']: session['role'] = 'admin'; return redirect(url_for('admin_dashboard'))
            elif role == 'Mobile_Waiter': session['role'] = 'mobile_waiter'; return redirect(url_for('mobile_waiter_tables'))
            elif role == 'Cashier': session['role'] = 'admin'; return redirect(url_for('admin_cashier'))
            else: session['role'] = 'waiter'; return redirect(url_for('desktop_tables'))

        if pwd in ['99', '٩٩', '222', '٢٢٢']:
            session.clear(); session.permanent = True; session['authenticated'] = True; session['role'] = 'admin'; session['full_name'] = 'بەڕێوەبەر'; return redirect(url_for('admin_dashboard'))
        elif pwd in ['345678', '٣٤٥٦٧٨']:
            session.clear(); session.permanent = True; session['authenticated'] = True; session['role'] = 'mobile_waiter'; return redirect(url_for('mobile_waiter_tables'))
        elif pwd in ['22', '٢٢']:
            session.clear(); session.permanent = True; session['authenticated'] = True; session['role'] = 'waiter'; return redirect(url_for('desktop_tables'))
        error = 'زانیارییەکان هەڵەیە!'
    return render_template_string(LOGIN_TEMPLATE, error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('authenticated') or session.get('role') != 'admin': return redirect(url_for('login'))
    today_sales, today_expense, active_tables, total_workers = 0, 0, 0, 0
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT IFNULL(SUM(amount), 0) AS s FROM qasa WHERE transaction_time >= NOW() - INTERVAL 1 DAY")
            today_sales = float(cur.fetchone()['s'])
            if today_sales == 0:
                cur.execute("SELECT IFNULL(SUM(quantity * price), 0) AS s FROM froshtn WHERE created_at >= NOW() - INTERVAL 1 DAY AND food_name NOT LIKE '%قاپی نوێ%'")
                today_sales = float(cur.fetchone()['s'])
            cur.execute("SELECT IFNULL(SUM(amount), 0) AS e FROM masrwf WHERE DATE(masrwf_date) = CURDATE()")
            today_expense = float(cur.fetchone()['e'])
            cur.execute("SELECT COUNT(DISTINCT table_cabin) AS c FROM froshtn WHERE table_cabin NOT LIKE '%[%' AND table_cabin != ''")
            active_tables = int(cur.fetchone()['c'])
            cur.execute("SELECT COUNT(*) AS w FROM workers")
            total_workers = int(cur.fetchone()['w'])
    except: pass
    finally: conn.close()
    return render_template_string(ADMIN_DASHBOARD_TEMPLATE, today_sales=today_sales, today_expense=today_expense, active_tables_count=active_tables, total_workers=total_workers)

@app.route('/admin/amar')
def admin_amar():
    if not session.get('authenticated') or session.get('role') != 'admin': return redirect(url_for('login'))
    today = datetime.now()
    start_date = request.args.get('start_date', today.replace(day=1).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', today.strftime('%Y-%m-%d'))
    report_rows, total_sales, total_expenses, total_workers_wage = [], 0.0, 0.0, 0.0
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT food_name, quantity, price FROM froshtn WHERE DATE(created_at) >= %s AND DATE(created_at) <= %s AND food_name NOT LIKE '%%قاپی نوێ%%'", (start_date, end_date))
            raw_data = cur.fetchall()
            aggregated = {}
            for item in raw_data:
                clean_name = re.sub(r'^[+\s]+|[+\s]+$', '', str(item.get('food_name') or '')).replace('+', '').strip()
                qty = float(item.get('quantity') or 1); price = float(item.get('price') or 0)
                if clean_name not in aggregated: aggregated[clean_name] = {'food_name': clean_name, 'qty': 0, 'price': price, 'total': 0.0}
                aggregated[clean_name]['qty'] += qty
                aggregated[clean_name]['total'] += (qty * price)
            report_rows = sorted(list(aggregated.values()), key=lambda x: x['qty'], reverse=True)
            total_sales = sum(r['total'] for r in report_rows)
            try:
                cur.execute("SELECT IFNULL(SUM(amount), 0) AS e FROM masrwf WHERE DATE(masrwf_date) >= %s AND DATE(masrwf_date) <= %s", (start_date, end_date))
                total_expenses = float(cur.fetchone()['e'])
            except: pass
            try:
                cur.execute("SELECT IFNULL(SUM((CASE WHEN wa.status = 'هاتوو' THEN w.salary ELSE 0 END) + IFNULL(wa.bonus, 0)), 0) AS w_due FROM workers w INNER JOIN worker_attendance wa ON w.id = wa.worker_id WHERE wa.date >= %s AND wa.date <= %s", (start_date, end_date))
                total_workers_wage = float(cur.fetchone()['w_due'])
            except: pass
    except: pass
    finally: conn.close()
    net_profit = total_sales - (total_expenses + total_workers_wage)
    return render_template_string(WEB_AMAR_TEMPLATE, start_date=start_date, end_date=end_date, report_rows=report_rows, total_sales=total_sales, total_expenses=total_expenses, total_workers_wage=total_workers_wage, net_profit=net_profit)

@app.route('/admin/masrwf')
def admin_masrwf():
    if not session.get('authenticated') or session.get('role') != 'admin': return redirect(url_for('login'))
    from_date = request.args.get('from_date', datetime.now().replace(day=1).strftime('%Y-%m-%d'))
    to_date = request.args.get('to_date', datetime.now().strftime('%Y-%m-%d'))
    rows, existing_types, existing_spenders = [], [], []
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, DATE_FORMAT(masrwf_date, '%%Y/%%m/%%d') AS m_date, DATE_FORMAT(masrwf_date, '%%Y-%%m-%%d') AS m_date_raw, masrwf_type, masrwf_name, spent_by, amount, payment_type, notes FROM masrwf WHERE DATE(masrwf_date) >= %s AND DATE(masrwf_date) <= %s ORDER BY masrwf_date DESC", (from_date, to_date))
            for r in cur.fetchall():
                rows.append({
                    'id': r['id'], 'm_date': r['m_date'], 'm_date_raw': r['m_date_raw'],
                    'masrwf_type': r.get('masrwf_type') if r.get('masrwf_type') != 'None' else r.get('masrwf_name'),
                    'spent_by': r.get('spent_by') or '', 'amount': float(r.get('amount') or 0),
                    'payment_type': r.get('payment_type') or 'نەغد', 'notes': r.get('notes') or ''
                })
            cur.execute("SELECT DISTINCT masrwf_type FROM masrwf WHERE masrwf_type IS NOT NULL AND masrwf_type != ''")
            existing_types = [r['masrwf_type'] for r in cur.fetchall()]
            cur.execute("SELECT DISTINCT spent_by FROM masrwf WHERE spent_by IS NOT NULL AND spent_by != ''")
            existing_spenders = [r['spent_by'] for r in cur.fetchall()]
    except: pass
    finally: conn.close()
    return render_template_string(WEB_MASRWF_TEMPLATE, rows=rows, from_date=from_date, to_date=to_date, today_date=datetime.now().strftime('%Y-%m-%d'), existing_types=existing_types, existing_spenders=existing_spenders)

@app.route('/admin/save_masrwf', methods=['POST'])
def admin_save_masrwf():
    conn = get_db()
    try:
        with conn.cursor() as cur: cur.execute("INSERT INTO masrwf (masrwf_date, masrwf_type, spent_by, amount, payment_type, notes) VALUES (%s, %s, %s, %s, %s, %s)", (request.form.get('masrwf_date'), request.form.get('masrwf_type', ''), request.form.get('spent_by', ''), float(request.form.get('amount', 0)), request.form.get('payment_type', 'نەغد'), request.form.get('notes', '')))
        conn.commit()
    except Exception as e: print(e)
    finally: conn.close()
    return redirect(url_for('admin_masrwf'))

@app.route('/admin/update_masrwf', methods=['POST'])
def admin_update_masrwf():
    conn = get_db()
    try:
        with conn.cursor() as cur: cur.execute("UPDATE masrwf SET masrwf_date=%s, masrwf_type=%s, spent_by=%s, amount=%s, payment_type=%s, notes=%s WHERE id=%s", (request.form.get('masrwf_date'), request.form.get('masrwf_type', ''), request.form.get('spent_by', ''), float(request.form.get('amount', 0)), request.form.get('payment_type', 'نەغد'), request.form.get('notes', ''), int(request.form.get('id', 0))))
        conn.commit()
    except Exception as e: print(e)
    finally: conn.close()
    return redirect(url_for('admin_masrwf'))

@app.route('/admin/delete_masrwf/<int:mid>')
def admin_delete_masrwf(mid):
    conn = get_db()
    try:
        with conn.cursor() as cur: cur.execute("DELETE FROM masrwf WHERE id=%s", (mid,))
        conn.commit()
    except: pass
    finally: conn.close()
    return redirect(url_for('admin_masrwf'))

@app.route('/admin/workers')
def admin_workers():
    if not session.get('authenticated') or session.get('role') != 'admin': return redirect(url_for('login'))
    start_date = request.args.get('start_date', datetime.now().replace(day=1).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    rows, all_workers = [], []
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT w.id, w.name, w.phone, w.salary, COUNT(CASE WHEN wa.status = 'هاتوو' THEN 1 END) AS work_days, (COUNT(CASE WHEN wa.status = 'هاتوو' THEN 1 END) * w.salary) AS total_salary, IFNULL(SUM(wa.bonus), 0) AS total_bonus, ((COUNT(CASE WHEN wa.status = 'هاتوو' THEN 1 END) * w.salary) + IFNULL(SUM(wa.bonus), 0)) AS total_due FROM workers w LEFT JOIN worker_attendance wa ON w.id = wa.worker_id AND wa.date >= %s AND wa.date <= %s GROUP BY w.id ORDER BY w.id DESC", (start_date, end_date))
            rows = cur.fetchall()
            cur.execute("SELECT id, name, salary FROM workers ORDER BY id ASC")
            for w in cur.fetchall():
                cur.execute("SELECT status FROM worker_attendance WHERE worker_id = %s ORDER BY date DESC LIMIT 1", (w['id'],))
                st_row = cur.fetchone()
                w['last_status'] = st_row['status'] if st_row else 'هاتوو'
                all_workers.append(w)
    except: pass
    finally: conn.close()
    return render_template_string(WEB_WORKERS_TEMPLATE, wage_rows=rows, all_workers=all_workers, start_date=start_date, end_date=end_date, today_date=datetime.now().strftime('%Y-%m-%d'))

@app.route('/admin/add_worker', methods=['POST'])
def admin_add_worker():
    conn = get_db()
    try:
        with conn.cursor() as cur: cur.execute("INSERT INTO workers (name, phone, salary) VALUES (%s, %s, %s)", (request.form.get('name'), request.form.get('phone', ''), float(request.form.get('salary', 0))))
        conn.commit()
    except: pass
    finally: conn.close()
    return redirect(url_for('admin_workers'))

@app.route('/admin/edit_worker/<int:wid>', methods=['POST'])
def admin_edit_worker(wid):
    conn = get_db()
    try:
        with conn.cursor() as cur: cur.execute("UPDATE workers SET name=%s, salary=%s WHERE id=%s", (request.form.get('name'), float(request.form.get('salary', 0)), wid))
        conn.commit()
    except: pass
    finally: conn.close()
    return redirect(url_for('admin_workers'))

@app.route('/admin/save_attendance', methods=['POST'])
def admin_save_attendance():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            for wid in request.form.getlist('worker_ids'):
                st = request.form.get(f'status_{wid}', 'هاتوو')
                bo = float(request.form.get(f'bonus_{wid}', 0) or 0)
                dt = request.form.get('att_date')
                cur.execute("INSERT INTO worker_attendance (worker_id, date, status, bonus) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE status=%s, bonus=%s", (wid, dt, st, bo, st, bo))
        conn.commit()
    except: pass
    finally: conn.close()
    return redirect(url_for('admin_workers'))

@app.route('/admin/delete_worker/<int:wid>')
def admin_delete_worker(wid):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM worker_attendance WHERE worker_id=%s", (wid,))
            cur.execute("DELETE FROM workers WHERE id=%s", (wid,))
        conn.commit()
    except: pass
    finally: conn.close()
    return redirect(url_for('admin_workers'))

@app.route('/admin/users')
def admin_users():
    if not session.get('authenticated') or session.get('role') != 'admin': return redirect(url_for('login'))
    users = []
    conn = get_db()
    try:
        with conn.cursor() as cur: cur.execute("SELECT * FROM users ORDER BY id DESC"); users = cur.fetchall()
    except: pass
    finally: conn.close()
    return render_template_string(WEB_USERS_TEMPLATE, users=users)

@app.route('/admin/add_user', methods=['POST'])
def admin_add_user():
    conn = get_db()
    try:
        with conn.cursor() as cur: cur.execute("INSERT INTO users (username, password, full_name, role) VALUES (%s, %s, %s, %s)", (request.form.get('username'), request.form.get('password'), request.form.get('full_name', ''), request.form.get('role', 'Waiter')))
        conn.commit()
    except: pass
    finally: conn.close()
    return redirect(url_for('admin_users'))

@app.route('/admin/edit_user/<int:uid>', methods=['POST'])
def admin_edit_user(uid):
    conn = get_db()
    try:
        with conn.cursor() as cur: cur.execute("UPDATE users SET username=%s, password=%s, full_name=%s, role=%s WHERE id=%s", (request.form.get('username'), request.form.get('password'), request.form.get('full_name', ''), request.form.get('role', 'Waiter'), uid))
        conn.commit()
    except: pass
    finally: conn.close()
    return redirect(url_for('admin_users'))

@app.route('/admin/toggle_user/<int:uid>')
def admin_toggle_user(uid):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT is_active FROM users WHERE id=%s", (uid,))
            r = cur.fetchone()
            if r: cur.execute("UPDATE users SET is_active=%s WHERE id=%s", (0 if r['is_active'] else 1, uid))
        conn.commit()
    except: pass
    finally: conn.close()
    return redirect(url_for('admin_users'))

@app.route('/admin/delete_user/<int:uid>')
def admin_delete_user(uid):
    conn = get_db()
    try:
        with conn.cursor() as cur: cur.execute("DELETE FROM users WHERE id=%s AND username!='admin'", (uid,))
        conn.commit()
    except: pass
    finally: conn.close()
    return redirect(url_for('admin_users'))

@app.route('/admin/cashier')
def admin_cashier():
    if not session.get('authenticated') or session.get('role') != 'admin': return redirect(url_for('login'))
    active_tables = []
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT table_cabin, COUNT(DISTINCT created_at) AS rounds FROM froshtn WHERE table_cabin != '' AND table_cabin NOT LIKE '%%[%%' GROUP BY table_cabin")
            active_tables = sorted(cur.fetchall(), key=lambda x: (0, int(x['table_cabin'])) if str(x['table_cabin']).isdigit() else (1, str(x['table_cabin'])))
    except: pass
    finally: conn.close()
    return render_template_string(WEB_CASHIER_TEMPLATE, active_tables=active_tables)

@app.route('/admin/complete_payment', methods=['POST'])
def admin_complete_payment():
    data = request.get_json() or {}
    t_num = str(data.get('table_number', ''))
    tot = float(data.get('total_amount', 0))
    paid = float(data.get('amount_paid', 0))
    disc = max(0, tot - paid)
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT food_name, quantity, price FROM froshtn WHERE table_cabin = %s", (t_num,))
            items = cur.fetchall()
            p_id = t_num if ('سەفەری' in t_num or t_num.startswith('m')) else f"m{t_num}"
            cur.execute("INSERT INTO qasa (place_id, amount, discount) VALUES (%s, %s, %s)", (p_id, paid, disc))
            cur.execute("DELETE FROM froshtn WHERE table_cabin = %s OR table_cabin LIKE %s", (t_num, f"{t_num} [%"))
        conn.commit()
        return jsonify({'status': 'success', 'receipt': {'table': t_num, 'items': items, 'total': tot, 'paid': paid}})
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)})
    finally: conn.close()

@app.route('/admin/qasa')
def admin_qasa():
    if not session.get('authenticated') or session.get('role') != 'admin': return redirect(url_for('login'))
    rows, tot_rec, tot_disc = [], 0, 0
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DATE_FORMAT(transaction_time, '%Y-%m-%d %H:%i') as transaction_time, place_id, amount, discount FROM qasa WHERE transaction_time >= NOW() - INTERVAL 1 DAY ORDER BY transaction_time DESC")
            rows = cur.fetchall()
            tot_rec = sum(float(r['amount']) for r in rows)
            tot_disc = sum(float(r['discount']) for r in rows)
    except: pass
    finally: conn.close()
    return render_template_string(WEB_QASA_TEMPLATE, qasa_rows=rows, total_received=tot_rec, total_discount=tot_disc)

@app.route('/admin/menu_manager')
def admin_menu_manager():
    if not session.get('authenticated') or session.get('role') != 'admin': return redirect(url_for('login'))
    foods, cats = [], ['برژاو', 'کوڵاو', 'پەلەوەر', 'شەربەت و خواردنەوە', 'سەوزە و زەڵاتە', 'کوردیەکان', 'خواردنی خێرا', 'شۆربا', 'شیرینی']
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, food_name, food_name_ar, food_name_en, price, category, image_path FROM nse ORDER BY id DESC")
            foods = cur.fetchall()
            for f in foods:
                if f.get('category') and f['category'] not in cats: cats.append(f['category'])
    except: pass
    finally: conn.close()
    return render_template_string(WEB_MENU_MANAGER_TEMPLATE, foods=foods, existing_categories=cats)

@app.route('/admin/add_food', methods=['POST'])
def admin_add_food():
    name = request.form.get('food_name')
    name_ar = request.form.get('food_name_ar', '')
    name_en = request.form.get('food_name_en', '')
    price = float(request.form.get('price', 0))
    cat = request.form.get('category', 'گشتی')
    img_link = request.form.get('image_path_link', '').strip()
    
    img = img_link
    if 'food_image' in request.files:
        f = request.files['food_image']
        if f.filename != '':
            fn = secure_filename(f"{int(datetime.now().timestamp())}_{f.filename}")
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
            img = url_for('static', filename=f'uploads/{fn}')
            
    conn = get_db()
    try:
        with conn.cursor() as cur: cur.execute("INSERT INTO nse (food_name, food_name_ar, food_name_en, price, category, image_path) VALUES (%s, %s, %s, %s, %s, %s)", (name, name_ar, name_en, price, cat, img))
        conn.commit()
    except: pass
    finally: conn.close()
    return redirect(url_for('admin_menu_manager'))

@app.route('/admin/edit_food/<int:fid>', methods=['POST'])
def admin_edit_food(fid):
    name = request.form.get('food_name')
    name_ar = request.form.get('food_name_ar', '')
    name_en = request.form.get('food_name_en', '')
    price = float(request.form.get('price', 0))
    cat = request.form.get('category', 'گشتی')
    img_link = request.form.get('image_path_link', '').strip()
    
    final_img = None
    if 'food_image' in request.files and request.files['food_image'].filename != '':
        f = request.files['food_image']
        fn = secure_filename(f"{int(datetime.now().timestamp())}_{f.filename}")
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
        final_img = url_for('static', filename=f'uploads/{fn}')
    elif img_link != '':
        final_img = img_link

    conn = get_db()
    try:
        with conn.cursor() as cur:
            if final_img is not None:
                cur.execute("UPDATE nse SET food_name=%s, food_name_ar=%s, food_name_en=%s, price=%s, category=%s, image_path=%s WHERE id=%s", (name, name_ar, name_en, price, cat, final_img, fid))
            else:
                cur.execute("UPDATE nse SET food_name=%s, food_name_ar=%s, food_name_en=%s, price=%s, category=%s WHERE id=%s", (name, name_ar, name_en, price, cat, fid))
        conn.commit()
    except: pass
    finally: conn.close()
    return redirect(url_for('admin_menu_manager'))

@app.route('/admin/delete_food/<int:fid>')
def admin_delete_food(fid):
    conn = get_db()
    try:
        with conn.cursor() as cur: cur.execute("DELETE FROM nse WHERE id=%s", (fid,))
        conn.commit()
    except: pass
    finally: conn.close()
    return redirect(url_for('admin_menu_manager'))

@app.route('/desktop/tables')
def desktop_tables():
    if not session.get('authenticated'): return redirect(url_for('login'))
    tk = []
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT table_cabin FROM froshtn WHERE table_cabin LIKE 'سەفەری%' AND table_cabin NOT LIKE '%%[%%'")
            tk = [r['table_cabin'] for r in cur.fetchall()]
    except: pass
    finally: conn.close()
    return render_template_string(DESKTOP_TABLES_TEMPLATE, active_takeaways=tk)

@app.route('/desktop')
def desktop_menu():
    if not session.get('authenticated'): return redirect(url_for('login'))
    tbl = request.args.get('table')
    if not tbl: return redirect(url_for('desktop_tables'))
    cats = {}
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, food_name, food_name_ar, food_name_en, price, category, image_path FROM nse WHERE food_name != ''")
            for f in cur.fetchall(): cats.setdefault(f['category'] or 'گشتی', []).append(f)
    except: pass
    finally: conn.close()
    return render_template_string(DESKTOP_TEMPLATE, categories=cats, selected_table=tbl)

@app.route('/mobile/tables')
def mobile_waiter_tables():
    if not session.get('authenticated'): return redirect(url_for('login'))
    tk = []
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT table_cabin FROM froshtn WHERE table_cabin LIKE 'سەفەری%' AND table_cabin NOT LIKE '%%[%%'")
            tk = [r['table_cabin'] for r in cur.fetchall()]
    except: pass
    finally: conn.close()
    return render_template_string(MOBILE_TABLES_TEMPLATE, active_takeaways=tk)

@app.route('/mobile/menu')
def mobile_waiter_menu():
    if not session.get('authenticated'): return redirect(url_for('login'))
    tbl = request.args.get('table', '1')
    cats = {}
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, food_name, food_name_ar, food_name_en, price, category, image_path FROM nse WHERE food_name != ''")
            for f in cur.fetchall(): cats.setdefault(f['category'] or 'گشتی', []).append(f)
    except: pass
    finally: conn.close()
    return render_template_string(CUSTOMER_MENU_TEMPLATE, table_num=tbl, categories=cats, allow_ordering=True)

@app.route('/table/<path:table_num>')
def customer_table_view(table_num):
    allow = True
    cats = {}
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if table_num.isdigit():
                cur.execute("SELECT allow_ordering FROM table_permissions WHERE table_number=%s", (int(table_num),))
                r = cur.fetchone()
                if r: allow = bool(r['allow_ordering'])
            cur.execute("SELECT id, food_name, food_name_ar, food_name_en, price, category, image_path FROM nse WHERE food_name != ''")
            for f in cur.fetchall(): cats.setdefault(f['category'] or 'گشتی', []).append(f)
    except: pass
    finally: conn.close()
    return render_template_string(CUSTOMER_MENU_TEMPLATE, table_num=table_num, categories=cats, allow_ordering=allow)

@app.route('/qr_manager')
def qr_manager():
    if not session.get('authenticated'): return redirect(url_for('login'))
    pd = {}
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT table_number, allow_ordering FROM table_permissions")
            for r in cur.fetchall(): pd[r['table_number']] = r['allow_ordering']
    except: pass
    finally: conn.close()
    return render_template_string(QR_MANAGER_TEMPLATE, base_url=request.host_url.rstrip('/'), perm_dict=pd)

@app.route('/toggle_table_permission', methods=['POST'])
def toggle_table_permission():
    t_num = int(request.get_json().get('table_number'))
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT allow_ordering FROM table_permissions WHERE table_number=%s", (t_num,))
            r = cur.fetchone()
            nv = 0 if (r and r['allow_ordering']) else 1
            cur.execute("INSERT INTO table_permissions (table_number, allow_ordering) VALUES (%s,%s) ON DUPLICATE KEY UPDATE allow_ordering=%s", (t_num, nv, nv))
        conn.commit()
        return jsonify({'status': 'success', 'allow_ordering': nv})
    except: return jsonify({'status': 'error'})
    finally: conn.close()

@app.route('/save_cart_order', methods=['POST'])
def save_cart_order():
    data = request.get_json() or {}
    tbl = str(data.get('table_number', ''))
    cart = data.get('cart_items', [])
    orig = data.get('original_items', [])

    def parse_items(items_list):
        parsed = {}
        plate_idx = 1
        for it in items_list:
            fname = str(it.get('full_name') or it.get('food_name') or '')
            is_div = it.get('is_divider') or 'قاپی نوێ' in fname or '───' in fname
            if is_div:
                plate_idx += 1
            else:
                key = f"{fname}__P{plate_idx}"
                if key not in parsed: parsed[key] = {'real_name': fname, 'qty': 0, 'price': float(it.get('price', 0)), 'cat': it.get('cat', 'گشتی')}
                parsed[key]['qty'] += float(it.get('qty', 1))
        return parsed

    old_map = parse_items(orig)
    new_map = parse_items(cart)

    conn = get_db()
    try:
        with conn.cursor() as cur:
            if tbl.isdigit():
                cur.execute("SELECT allow_ordering FROM table_permissions WHERE table_number = %s", (int(tbl),))
                p_row = cur.fetchone()
                if p_row and not p_row['allow_ordering'] and session.get('role') not in ['mobile_waiter', 'admin']:
                    return jsonify({'status': 'error', 'message': 'تەنها بۆ بینینە'})

            cur.execute("DELETE FROM froshtn WHERE table_cabin = %s", (tbl,))
            for it in cart:
                fname = str(it.get('ku') or it.get('full_name') or it.get('food_name') or '')
                is_div = it.get('is_divider') or 'قاپی نوێ' in fname or '───' in fname
                final_name = "─── قاپی نوێ ───" if is_div else fname
                cur.execute("INSERT INTO froshtn (table_cabin, food_name, quantity, price, category, created_at, is_printed) VALUES (%s, %s, %s, %s, %s, NOW(), 1)", (tbl, final_name, float(it.get('qty', 1)), float(it.get('price', 0)), it.get('cat', 'گشتی')))

            kitchen_inserts = []
            plate_idx = 1
            current_plate_printed = False

            for it in cart:
                fname = str(it.get('ku') or it.get('full_name') or it.get('food_name') or '')
                is_div = it.get('is_divider') or 'قاپی نوێ' in fname or '───' in fname
                if is_div:
                    plate_idx += 1; current_plate_printed = False
                else:
                    key = f"{fname}__P{plate_idx}"
                    new_qty = float(it.get('qty', 1))
                    old_qty = old_map.get(key, {}).get('qty', 0)
                    diff = new_qty - old_qty
                    if diff > 0:
                        if plate_idx > 1 and not current_plate_printed:
                            kitchen_inserts.append({'name': '─── قاپی نوێ ───', 'qty': 1, 'price': 0, 'cat': 'برژاو', 'action': 'add'})
                            current_plate_printed = True
                        kitchen_inserts.append({'name': f"+ {fname}", 'qty': diff, 'price': float(it.get('price', 0)), 'cat': it.get('cat', 'گشتی'), 'action': 'add'})

            for k, old_data in old_map.items():
                new_qty = new_map.get(k, {}).get('qty', 0)
                diff = new_qty - old_data['qty']
                if diff < 0:
                    kitchen_inserts.append({'name': f"سڕاوەتەوە: {old_data['real_name']}", 'qty': abs(diff), 'price': old_data['price'], 'cat': old_data['cat'], 'action': 'delete'})

            for ki in kitchen_inserts:
                tbl_suffix = " [زیادکراو]" if ki['action'] == 'add' else " [سڕاوەتەوە]"
                cur.execute("INSERT INTO froshtn (table_cabin, food_name, quantity, price, category, created_at, is_printed) VALUES (%s, %s, %s, %s, %s, NOW(), 0)", (tbl + tbl_suffix, ki['name'], float(ki['qty']), float(ki['price']), ki['cat']))

        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as ex: return jsonify({'status': 'error', 'message': str(ex)})
    finally: conn.close()

@app.route('/get_table_orders/<path:table_num>')
def get_table_orders(table_num):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT food_name, price, quantity, category FROM froshtn WHERE table_cabin = %s", (str(table_num),))
            return jsonify(cur.fetchall())
    except: return jsonify([])
    finally: conn.close()

@app.route('/clear_table_orders', methods=['POST'])
def clear_table_orders():
    tbl = str(request.get_json().get('table_number'))
    conn = get_db()
    try:
        with conn.cursor() as cur: cur.execute("DELETE FROM froshtn WHERE table_cabin = %s OR table_cabin LIKE %s", (tbl, f"{tbl} [%"))
        conn.commit()
        return jsonify({'status': 'success'})
    except: return jsonify({'status': 'error'})
    finally: conn.close()

@app.route('/get_active_tables')
def get_active_tables():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT table_cabin FROM froshtn WHERE table_cabin NOT LIKE '%%[%%' AND table_cabin != ''")
            return jsonify([str(r['table_cabin']).strip() for r in cur.fetchall()])
    except: return jsonify([])
    finally: conn.close()

@app.route('/transfer_table_orders', methods=['POST'])
def transfer_table_orders():
    data = request.get_json() or {}
    f_tbl = str(data.get('from_table', '')).strip()
    t_tbl = str(data.get('to_table', '')).strip()
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE froshtn SET table_cabin = REPLACE(table_cabin, %s, %s) WHERE table_cabin = %s OR table_cabin LIKE %s", (f_tbl, t_tbl, f_tbl, f"{f_tbl} [%"))
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as ex: return jsonify({'status': 'error', 'message': str(ex)})
    finally: conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
