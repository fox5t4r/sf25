from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import hashlib
import os
import secrets
import time
import requests
from lxml import etree
from functools import wraps
from collections import defaultdict

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

DATABASE_PATH = os.getenv('DATABASE_PATH', '/data/nhbank.db')
if not os.path.exists(os.path.dirname(DATABASE_PATH)) and DATABASE_PATH.startswith('/data'):
    DATABASE_PATH = './nhbank.db'

INTERNAL_WEB_URL = os.getenv('INTERNAL_WEB_URL', 'http://internal-web:53215')
BOT_URL = os.getenv('BOT_URL', 'http://ceo-bot:3000')

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', secrets.token_hex(16))
CEO_PASSWORD = os.getenv('CEO_PASSWORD', secrets.token_hex(16))

login_attempts = defaultdict(list)
report_cooldowns = {}  
MAX_ATTEMPTS = 10
LOCKOUT_TIME = 300
REPORT_COOLDOWN = 30 

def check_rate_limit(ip):
    now = time.time()
    login_attempts[ip] = [t for t in login_attempts[ip] if now - t < LOCKOUT_TIME]
    if len(login_attempts[ip]) >= MAX_ATTEMPTS:
        return False
    return True

def record_login_attempt(ip):
    login_attempts[ip].append(time.time())

def check_report_cooldown(token):
    now = time.time()
    last_report = report_cooldowns.get(token, 0)
    if now - last_report < REPORT_COOLDOWN:
        return int(REPORT_COOLDOWN - (now - last_report))
    return 0

def record_report(token):
    report_cooldowns[token] = time.time()

def get_or_create_token():
    if 'user_token' not in session:
        session['user_token'] = secrets.token_hex(16)
        init_token_data(session['user_token'])
    return session['user_token']

def init_token_data(token):
    conn = get_db()
    cursor = conn.cursor()

    guest_pw = hashlib.sha256('guest123'.encode()).hexdigest()
    admin_pw = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
    ceo_pw = hashlib.sha256(CEO_PASSWORD.encode()).hexdigest()
    
    try:
        cursor.execute("INSERT INTO users (token, username, password) VALUES (?, ?, ?)", 
                      (token, 'guest', guest_pw))
        cursor.execute("INSERT INTO users (token, username, password) VALUES (?, ?, ?)", 
                      (token, 'admin', admin_pw))
        cursor.execute("INSERT INTO users (token, username, password) VALUES (?, ?, ?)", 
                      (token, 'ceo', ceo_pw))
        conn.commit()
        print(f"[*] Initialized data for token: {token[:8]}...")
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()

def escape_js_string(content):
    if not content:
        return content
    content = content.replace('\\', '\\\\')
    content = content.replace('"', '\\"')
    content = content.replace("'", "\\'")
    content = content.replace('\n', '\\n')
    content = content.replace('\r', '\\r')
    content = content.replace('<', '\\x3c')
    content = content.replace('>', '\\x3e')
    return content

app.jinja_env.filters['js_escape'] = escape_js_string

class CustomResolver(etree.Resolver):
    def resolve(self, url, id, context):
        if url.startswith('file://'):
            return self.resolve_string('', context)
        if url.startswith('http://') or url.startswith('https://'):
            return None
        return self.resolve_string('', context)

def init_db():
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            UNIQUE(token, username)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS todolist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            author TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_token ON users(token)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_todolist_token ON todolist(token)')
    
    conn.commit()
    conn.close()
    
    print("[*] Database initialized (token-based schema)")
    print(f"[*] DB Path: {DATABASE_PATH}")

init_db()

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    get_or_create_token() 
    return render_template('home.html')

@app.route('/products')
def products():
    return render_template('products.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/api/token')
def get_token():
    token = get_or_create_token()
    return jsonify({'token': token})

@app.route('/login', methods=['GET', 'POST'])
def login():
    token = get_or_create_token()
    
    if request.method == 'GET':
        return render_template('login.html')
    
    client_ip = request.remote_addr
    if not check_rate_limit(client_ip):
        remaining = int(LOCKOUT_TIME - (time.time() - min(login_attempts[client_ip])))
        return render_template('login.html',
            error=f'너무 많은 로그인 시도입니다. {remaining}초 후에 다시 시도해주세요.')
    
    username = request.form.get('username', '')
    password = request.form.get('password', '')
    
    if not username or not password:
        return render_template('login.html', error='아이디와 비밀번호를 입력해주세요')
    
    conn = get_db()
    cursor = conn.cursor()
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    cursor.execute(
        "SELECT * FROM users WHERE token = ? AND username = ? AND password = ?",
        (token, username, password_hash)
    )
    
    user = cursor.fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        
        if user['username'] in ['admin', 'ceo']:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('home'))
    else:
        record_login_attempt(client_ip)
        attempts_left = MAX_ATTEMPTS - len(login_attempts[client_ip])
        return render_template('login.html',
            error=f'아이디 또는 비밀번호가 올바르지 않습니다. (남은 시도: {attempts_left}회)')

@app.route('/logout')
def logout():
    token = session.get('user_token')
    session.clear()
    if token:
        session['user_token'] = token
    return redirect(url_for('home'))

@app.route('/api/submit-feedback', methods=['POST'])
def submit_feedback():
    content_type = request.headers.get('Content-Type', '')
    
    if 'application/xml' in content_type:
        try:
            xml_data = request.get_data()
            
            parser = etree.XMLParser(
                resolve_entities=True,
                no_network=False,
                load_dtd=True
            )
            parser.resolvers.add(CustomResolver())
            
            root = etree.fromstring(xml_data, parser)
            
            customer_id = root.find('customer_id')
            category = root.find('category')
            message = root.find('message')
            
            return jsonify({
                "status": "received",
                "customer_id": customer_id.text[:100] if customer_id is not None and customer_id.text else "",
                "category": category.text if category is not None and category.text else "",
                "message": message.text[:100] if message is not None and message.text else "",
                "note": "XML feedback processed"
            }), 200
            
        except etree.XMLSyntaxError as e:
            return jsonify({"error": "Invalid XML format", "details": str(e)}), 400
        except Exception as e:
            return jsonify({"error": "XML processing error"}), 500
    else:
        try:
            data = request.json
            return jsonify({
                "message": "피드백이 정상적으로 접수되었습니다",
                "reference_id": "FB-" + str(abs(hash(data.get('email', 'anonymous'))))[:8],
                "status": "submitted",
                "note": "JSON and XML formats are supported"
            }), 200
        except:
            return jsonify({"error": "Invalid JSON"}), 400

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'username' not in session or session['username'] not in ['admin', 'ceo']:
            return "Access denied - Admin only", 403
        return f(*args, **kwargs)
    return wrapper

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html', username=session['username'])

@app.route('/admin/ceo-todolist')
@login_required
@admin_required
def ceo_todolist():
    if session['username'] == 'ceo' and request.args.get('token'):
        target_token = request.args.get('token')
    else:
        target_token = get_or_create_token()
    
    cooldown = check_report_cooldown(target_token)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM todolist WHERE token = ? ORDER BY created_at DESC LIMIT 1", (target_token,))
    todos = cursor.fetchall()
    conn.close()
    
    return render_template('ceo_todolist.html', todos=todos, username=session['username'], cooldown=cooldown)

@app.route('/api/admin/add-todo', methods=['POST'])
@login_required
@admin_required
def add_todo():
    token = get_or_create_token()
    data = request.json
    title = data.get('title', '')
    content = data.get('content', '')
    
    if not title or not content:
        return jsonify({"error": "Title and content required"}), 400
    
    if len(content) > 1000:
        return jsonify({"error": "Content too long (max 1000 chars)"}), 400
    
    blocked_patterns = [
        '<script', '</script>', 'javascript:',
        'onerror', 'onload', 'onclick', 'onmouseover',
        'onfocus', 'onblur', 'onchange', 'onsubmit',
        'onmouseenter', 'onmouseleave', 'onkeydown', 'onkeyup',
        'ondrag', 'ondrop', 'oncopy', 'onpaste',
        'eval(', 'alert(', 'confirm(', 'prompt(',
        'document.cookie', 'document.location',
        'window.location', 'location.href'
    ]
    
    content_lower = content.lower()
    for pattern in blocked_patterns:
        if pattern in content_lower:
            return jsonify({"error": f"Blocked pattern detected: {pattern}"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM todolist WHERE token = ?", (token,))
    cursor.execute(
        "INSERT INTO todolist (token, title, content, author) VALUES (?, ?, ?, ?)",
        (token, title, content, session['username'])
    )
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": "Todo added successfully"}), 200

@app.route('/api/report', methods=['POST'])
@login_required
@admin_required
def report_to_ceo():
    token = get_or_create_token()

    cooldown = check_report_cooldown(token)
    if cooldown > 0:
        return jsonify({
            "error": f"잠시 후에 다시 시도해주세요. ({cooldown}초 남음)",
            "cooldown": cooldown
        }), 429

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM todolist WHERE token = ? LIMIT 1", (token,))
    todo = cursor.fetchone()
    conn.close()
    
    if not todo:
        return jsonify({"error": "먼저 메시지를 작성해주세요."}), 400
    
    try:
        response = requests.post(
            f"{BOT_URL}/visit",
            json={"token": token},
            timeout=5
        )
        
        if response.status_code == 200:
            record_report(token)
            return jsonify({
                "success": True,
                "message": "CEO에게 보고되었습니다. 잠시 후 CEO가 확인합니다."
            })
        else:
            return jsonify({"error": "Bot 서버 오류"}), 500
            
    except requests.exceptions.RequestException as e:
        print(f"[!] Bot request error: {e}")
        return jsonify({"error": "CEO Bot에 연결할 수 없습니다."}), 503

@app.route('/internal/view-todo')
def bot_view_todo():
    token = request.args.get('token')
    if not token:
        return "Token required", 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM todolist WHERE token = ? ORDER BY created_at DESC LIMIT 1", (token,))
    todos = cursor.fetchall()
    conn.close()
    
    return render_template('ceo_todolist_bot.html', todos=todos)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=82)