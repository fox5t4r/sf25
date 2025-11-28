#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, send_file, session
import os
import subprocess
import re
import secrets
from datetime import datetime

app = Flask(__name__)

app.secret_key = secrets.token_hex(32)

BASE_UPLOAD_FOLDER = '/app/uploads'
app.config['BASE_UPLOAD_FOLDER'] = BASE_UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB 제한

os.makedirs(BASE_UPLOAD_FOLDER, exist_ok=True)

def log_upload(session_id, original_filename, final_filename, client_ip):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = (
        f"[{timestamp}] UPLOAD - "
        f"Session: {session_id[:8]}... | "
        f"IP: {client_ip} | "
        f"Original: {original_filename} | "
        f"Final: {final_filename}"
    )

    print(log_message, flush=True)

def get_user_upload_folder():
    if 'user_id' not in session:
        session['user_id'] = secrets.token_hex(16)
        print(f"[SESSION] 새 세션 생성: {session['user_id'][:8]}...", flush=True)
    
    user_folder = os.path.join(BASE_UPLOAD_FOLDER, session['user_id'])
    os.makedirs(user_folder, exist_ok=True)
    
    return user_folder

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['GET'])
def upload_page():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_file():

    if 'file' not in request.files:
        return '파일이 선택되지 않았습니다.', 400
    
    file = request.files['file']
    
    if file.filename == '':
        return '파일이 선택되지 않았습니다.', 400
    
    original_filename = file.filename

    safe_filename = original_filename.replace('..', '').replace('/', '').replace('%','').replace('\\', '').replace('\x00', '')

    if len(safe_filename) > 50:
        return '파일명이 너무 깁니다.', 400

    content_type = file.content_type
    allowed_mime_types = ['image/jpeg', 'image/png']
    
    if content_type not in allowed_mime_types:
        return '허용되지 않는 파일 타입입니다.', 400

    name_parts = safe_filename.rsplit('.', 1)
    if len(name_parts) == 2:
        safe_filename = name_parts[0] + '.' + name_parts[1].lower()

    allowed_extensions = ['.jpg', '.png']
    if not any(safe_filename.lower().endswith(ext) for ext in allowed_extensions):
        return '허용되지 않는 파일 확장자입니다.', 400

    final_filename = re.sub(r'\.php', '', safe_filename, count=99, flags=re.IGNORECASE)

    if not final_filename or final_filename.startswith('.'):
        return '잘못된 파일명입니다.', 400

    user_folder = get_user_upload_folder()
    file_path = os.path.join(user_folder, final_filename)
    
    try:
        file.save(file_path)

        client_ip = request.remote_addr or 'unknown'
        log_upload(
            session['user_id'],
            original_filename,
            final_filename,
            client_ip
        )
        
    except Exception as e:
        print(f"[ERROR] 파일 저장 오류: {e}", flush=True)
        return f'파일 저장 중 오류가 발생했습니다.', 500
    
    return redirect(url_for('gallery'))

@app.route('/gallery')
def gallery():
    user_folder = get_user_upload_folder()
    
    files = []
    if os.path.exists(user_folder):
        files = os.listdir(user_folder)
    
    return render_template('gallery.html', files=files)

@app.route('/gallery/<filename>')
def serve_file(filename):

    filename = filename.replace('..', '').replace('/', '').replace('\\', '')

    user_folder = get_user_upload_folder()
    file_path = os.path.join(user_folder, filename)
    
    if not os.path.exists(file_path):
        return '파일을 찾을 수 없습니다.', 404

    if '.php' in filename:
        try:
            env = os.environ.copy()

            query_string = request.query_string.decode('utf-8')
            env['QUERY_STRING'] = query_string
            env['REQUEST_METHOD'] = 'GET'

            env['REDIRECT_STATUS'] = '200'
            env['SCRIPT_FILENAME'] = file_path

            result = subprocess.run(
                ['php-cgi', file_path],
                capture_output=True,
                env=env,
                timeout=5
            )

            output = result.stdout.decode('utf-8', errors='ignore')

            if '\n\n' in output:
                output = output.split('\n\n', 1)[1]
            elif '\r\n\r\n' in output:
                output = output.split('\r\n\r\n', 1)[1]
            
            return output, 200, {'Content-Type': 'text/html'}
            
        except subprocess.TimeoutExpired:
            return 'PHP 실행 시간 초과', 500
        except Exception as e:
            return f'PHP 실행 오류: {str(e)}', 500

    return send_file(file_path)

if __name__ == '__main__':
    print("[INFO] Flask 애플리케이션 시작", flush=True)
    print(f"[INFO] 업로드 폴더: {BASE_UPLOAD_FOLDER}", flush=True)
    app.run(host='0.0.0.0', port=88)
