from flask import Flask, request, jsonify, render_template_string
import sqlite3
import secrets
import hashlib
import os

app = Flask(__name__)
DATABASE_PATH = os.getenv('DATABASE_PATH', '/data/nhbank.db')

csrf_tokens = {}

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def generate_csrf():
    token = secrets.token_hex(32)
    csrf_tokens[token] = True
    return token

def verify_csrf(token):
    return csrf_tokens.pop(token, False)

@app.before_request
def check_ip():
    source_ip = request.remote_addr

    if source_ip.startswith('172.25.0.') or source_ip.startswith('192.168.200.'):
        return None
    
    return jsonify({
        "error": "Access denied",
        "message": "Internal network only",
        "your_ip": source_ip
    }), 403

@app.route('/internal/csrf-token', methods=['GET'])
def get_csrf_token():
    csrf_token = generate_csrf()
    return csrf_token, 200, {'Content-Type': 'text/plain'}

@app.route('/internal/change-password', methods=['GET'])
def change_password():
    csrf_token = request.args.get('csrf_token')
    username = request.args.get('username')
    new_password = request.args.get('new_password')
    user_token = request.args.get('token') 
    
    if csrf_token and username and new_password and user_token:
        if not verify_csrf(csrf_token):
            return f"ERROR: Invalid CSRF token", 403, {'Content-Type': 'text/plain'}

        try:
            conn = get_db()
            cursor = conn.cursor()
            
            password_hash = hashlib.sha256(new_password.encode()).hexdigest()

            cursor.execute(
                "UPDATE users SET password = ? WHERE token = ? AND username = ?",
                (password_hash, user_token, username)
            )
            
            if cursor.rowcount == 0:
                conn.close()
                return f"ERROR: User not found for this token", 404, {'Content-Type': 'text/plain'}
            
            conn.commit()
            conn.close()

            return f"SUCCESS: Password changed for {username}", 200, {'Content-Type': 'text/plain'}
        except Exception as e:
            return f"ERROR: {str(e)}", 500, {'Content-Type': 'text/plain'}

    csrf_token = generate_csrf()
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>NH Bank - Internal Password Change</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 500px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #008485;
            margin-bottom: 20px;
        }}
        .warning {{
            background: #fff3cd;
            padding: 10px;
            border-left: 4px solid #ffc107;
            margin-bottom: 20px;
        }}
        input {{
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }}
        button {{
            background: #008485;
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            width: 100%;
        }}
        button:hover {{
            background: #006e6f;
        }}
        .info {{
            margin-top: 20px;
            padding: 10px;
            background: #e8f4f4;
            border-radius: 4px;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Internal Password Change</h1>
        
        <div class="warning">
            This page is only accessible from internal network
        </div>
        
        <form method="GET" action="/internal/change-password">
            <input type="hidden" name="csrf_token" value="{csrf_token}">
            
            <label>User Token:</label>
            <input type="text" name="token" required placeholder="Enter user token">
            
            <label>Username:</label>
            <input type="text" name="username" required placeholder="Enter username">
            
            <label>New Password:</label>
            <input type="password" name="new_password" required placeholder="Enter new password">
            
            <button type="submit">Change Password</button>
        </form>
        
        <div class="info">
            <strong>Note:</strong> This is an internal tool for IT department.<br>
            Available users: admin, guest<br>
            <strong>Token:</strong> Required for user identification<br>
            <br>
            <strong>API:</strong> GET /internal/csrf-token for token only
        </div>
    </div>
</body>
</html>
    """
    
    return html, 200

@app.route('/internal/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "internal-web"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=53215)