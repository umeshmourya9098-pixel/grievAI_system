import os
import re
import secrets
import hashlib
import datetime
import random
import sqlite3
from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from functools import wraps
from time import time

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
CORS(app, supports_credentials=True)

# ==============================================
# CONFIGURATION
# ==============================================
PORT = int(os.environ.get('PORT', 10000))
BASE_URL = os.environ.get('BASE_URL', 'https://grievai-system.onrender.com')
DB_PATH = os.path.join(os.path.dirname(__file__), 'grievai.db')
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Store OTP and Verification Tokens
OTP_STORE = {}
VERIFICATION_TOKENS = {}

# ==============================================
# OTP FUNCTIONS
# ==============================================

def generate_otp():
    return ''.join(random.choices('0123456789', k=6))

def send_otp_email(email, otp):
    """Send OTP via email using Resend API"""
    api_key = os.environ.get('RESEND_API_KEY', '')
    
    if not api_key:
        print(f"\n⚠️ RESEND_API_KEY not set!")
        print(f"📧 OTP for {email}: {otp}\n")
        return
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial; text-align: center; background: #f4f6fb; padding: 20px;">
        <div style="max-width: 450px; margin: auto; background: white; border-radius: 16px; padding: 30px;">
            <div style="background: linear-gradient(135deg,#1B8A4E,#0E6B6B); padding: 15px; border-radius: 12px;">
                <h1 style="color: white; margin: 0;">🏛️ GrievAI</h1>
                <p style="color: rgba(255,255,255,0.9);">मध्य प्रदेश सरकार</p>
            </div>
            
            <h2 style="color: #1B8A4E;">नमस्ते! 👋</h2>
            <p>आपका OTP कोड नीचे दिया गया है:</p>
            
            <div style="font-size: 36px; font-weight: bold; background: #f0f0f0; padding: 15px; border-radius: 10px; letter-spacing: 5px; margin: 20px 0;">
                {otp}
            </div>
            
            <p style="color: #888; font-size: 12px;">⚠️ यह OTP <strong>10 मिनट</strong> के लिए वैध है।</p>
        </div>
    </body>
    </html>
    """
    
    try:
        import requests
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "from": "GrievAI <onboarding@resend.dev>",
                "to": email,
                "subject": "GrievAI - Your OTP Code",
                "html": html_content
            }
        )
        
        if response.status_code == 200:
            print(f"✅ OTP email sent to {email}")
        else:
            print(f"❌ Failed to send OTP to {email}")
            print(f"📧 OTP for {email}: {otp}")
    except Exception as e:
        print(f"❌ Email error: {e}")
        print(f"📧 OTP for {email}: {otp}")

# ==============================================
# DATABASE FUNCTIONS
# ==============================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def generate_complaint_id():
    now = datetime.datetime.now()
    rand = ''.join(random.choices('0123456789', k=4))
    return f"GRV{now.strftime('%y%m%d')}{rand}"

def generate_verification_token():
    return secrets.token_urlsafe(32)

# ==============================================
# INIT DATABASE
# ==============================================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    print("📦 Creating tables...")
    
    c.execute('''CREATE TABLE IF NOT EXISTS citizens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, 
        email TEXT UNIQUE NOT NULL,
        mobile TEXT NOT NULL, 
        password TEXT NOT NULL,
        city TEXT DEFAULT '',
        is_verified INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    print("✓ citizens table ready")
    
    c.execute('''CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dept_name TEXT NOT NULL, 
        officer_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL, 
        password TEXT NOT NULL,
        mobile TEXT DEFAULT '',
        city TEXT DEFAULT '',
        is_verified INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    print("✓ departments table ready")
    
    c.execute('''CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id TEXT UNIQUE NOT NULL,
        citizen_name TEXT NOT NULL, 
        citizen_email TEXT NOT NULL,
        mobile TEXT NOT NULL, 
        complaint_text TEXT NOT NULL,
        department TEXT NOT NULL, 
        status TEXT DEFAULT 'pending',
        photo_path TEXT DEFAULT NULL, 
        voice_path TEXT DEFAULT NULL,
        latitude REAL DEFAULT NULL, 
        longitude REAL DEFAULT NULL,
        address TEXT DEFAULT NULL,
        city TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    print("✓ complaints table ready")
    
    c.execute('''CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_name TEXT, 
        user_type TEXT DEFAULT 'citizen',
        rating INTEGER, 
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    print("✓ feedback table ready")
    
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        mobile TEXT DEFAULT '',
        role TEXT DEFAULT 'admin',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    print("✓ admins table ready")
    
    c.execute("DELETE FROM departments")
    c.execute("DELETE FROM citizens")
    c.execute("DELETE FROM admins")
    
    # Default departments
    default_depts = [
        ('Water Supply','Ramesh Sharma','water@grievai.com',hash_password('WaterSupply123'),'9876543201','Bhopal',1),
        ('Electricity','Suresh Verma','electricity@grievai.com',hash_password('Electricity123'),'9876543202','Bhopal',1),
        ('Roads & PWD','Mahesh Patel','roads@grievai.com',hash_password('RoadsPWD123'),'9876543203','Bhopal',1),
        ('Sanitation','Dinesh Kumar','sanitation@grievai.com',hash_password('Sanitation123'),'9876543204','Bhopal',1),
        ('Healthcare','Rakesh Singh','healthcare@grievai.com',hash_password('Healthcare123'),'9876543205','Bhopal',1),
    ]
    
    for d in default_depts:
        try:
            c.execute('''INSERT INTO departments 
                (dept_name, officer_name, email, password, mobile, city, is_verified) 
                VALUES (?,?,?,?,?,?,?)''', d)
            print(f"✓ Department added: {d[0]}")
        except:
            pass
    
    # Admin
    try:
        c.execute('''INSERT OR IGNORE INTO admins (name, email, password, mobile, role) 
                     VALUES (?,?,?,?,?)''',
                  ('Super Admin', 'admin@grievai.com', hash_password('admin123'), '9999999999', 'super_admin'))
        print("✓ Admin created: admin@grievai.com / admin123")
    except:
        pass
    
    # Test citizen
    try:
        c.execute('''INSERT OR IGNORE INTO citizens (name, email, mobile, password, city, is_verified) 
                     VALUES (?,?,?,?,?,?)''',
                  ('Test Citizen', 'test@citizen.com', '9999999999', hash_password('test123'), 'Bhopal', 1))
        print("✓ Test citizen added: test@citizen.com / test123")
    except:
        pass
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")

# ==============================================
# PAGES
# ==============================================

@app.route('/') 
def index(): 
    return render_template('index.html')

@app.route('/citizen') 
def citizen_page(): 
    return render_template('citizen_login.html')

@app.route('/citizen/dashboard') 
def citizen_dash(): 
    return render_template('citizen_dashboard.html')

@app.route('/department') 
def dept_page(): 
    return render_template('dept_login.html')

@app.route('/department/dashboard') 
def dept_dash(): 
    return render_template('dept_dashboard.html')

@app.route('/admin') 
def admin_page(): 
    return render_template('admin_login.html')

@app.route('/admin/dashboard') 
def admin_dash(): 
    return render_template('admin_dashboard.html')

@app.route('/faq')
def faq_page():
    return render_template('faq.html')

@app.route('/instructions')
def instructions_page():
    return render_template('instructions.html')

# ==============================================
# API: SEND OTP
# ==============================================

@app.route('/api/send-otp', methods=['POST'])
def send_otp():
    data = request.json
    email = data.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'success': False, 'message': 'Email is required'})
    
    # Check if user exists
    conn = get_db()
    user = conn.execute('SELECT * FROM citizens WHERE email = ?', (email,)).fetchone()
    conn.close()
    
    if not user:
        return jsonify({'success': False, 'message': 'Email not registered!'})
    
    if user['is_verified'] == 1:
        return jsonify({'success': False, 'message': 'Email already verified! Please login.'})
    
    # Generate and store OTP
    otp = generate_otp()
    OTP_STORE[email] = {
        'otp': otp,
        'expires': datetime.datetime.now() + datetime.timedelta(minutes=10)
    }
    
    # Send OTP via email
    send_otp_email(email, otp)
    
    print(f"\n{'='*40}")
    print(f"[OTP] {email} => {otp}")
    print(f"{'='*40}\n")
    
    return jsonify({'success': True, 'otp': otp, 'message': 'OTP sent successfully!'})

# ==============================================
# API: VERIFY OTP
# ==============================================

@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json
    email = data.get('email', '').strip().lower()
    otp = data.get('otp', '').strip()
    
    if not email or not otp:
        return jsonify({'success': False, 'message': 'Email and OTP required'})
    
    stored = OTP_STORE.get(email)
    
    if not stored:
        return jsonify({'success': False, 'message': 'OTP not requested or expired'})
    
    if datetime.datetime.now() > stored['expires']:
        del OTP_STORE[email]
        return jsonify({'success': False, 'message': 'OTP expired! Please request again.'})
    
    if stored['otp'] != otp:
        return jsonify({'success': False, 'message': 'Invalid OTP!'})
    
    # Mark user as verified
    conn = get_db()
    conn.execute('UPDATE citizens SET is_verified = 1 WHERE email = ?', (email,))
    conn.commit()
    conn.close()
    
    del OTP_STORE[email]
    
    return jsonify({'success': True, 'message': 'OTP verified successfully!'})

# ==============================================
# API: CITIZEN REGISTER
# ==============================================

@app.route('/api/citizen/register', methods=['POST'])
def citizen_register():
    data = request.json
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    mobile = data.get('mobile', '').strip()
    password = data.get('password', '')
    city = data.get('city', '').strip()
    
    if not all([name, email, mobile, password]):
        return jsonify({'success': False, 'message': 'सभी फील्ड भरें'})
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'पासवर्ड 6+ कैरेक्टर'})
    if len(mobile) != 10 or not mobile.isdigit():
        return jsonify({'success': False, 'message': 'मोबाइल नंबर 10 अंकों का होना चाहिए'})
    
    conn = get_db()
    
    existing = conn.execute('SELECT * FROM citizens WHERE email = ?', (email,)).fetchone()
    if existing:
        if existing['is_verified'] == 1:
            conn.close()
            return jsonify({'success': False, 'message': 'Email already registered and verified!'})
        else:
            conn.execute('''UPDATE citizens SET name=?, mobile=?, password=?, city=?, is_verified=0 
                           WHERE email=?''', (name, mobile, hash_password(password), city, email))
            print(f"🔄 Updated existing unverified user: {email}")
    else:
        conn.execute('''INSERT INTO citizens (name, email, mobile, password, city, is_verified) 
                       VALUES (?,?,?,?,?,0)''',
                     (name, email, mobile, hash_password(password), city))
        print(f"📝 Created new user: {email}")
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Registration successful! Please login and verify with OTP.'})

# ==============================================
# API: CITIZEN LOGIN
# ==============================================

@app.route('/api/citizen/login', methods=['POST'])
def citizen_login():
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    print(f"🔐 Login attempt - Email: {email}")
    
    conn = get_db()
    row = conn.execute('SELECT * FROM citizens WHERE email=? AND password=?', 
                       (email, hash_password(password))).fetchone()
    
    if not row:
        conn.close()
        print(f"❌ Login failed - User not found")
        return jsonify({'success': False, 'message': 'Email या पासवर्ड गलत है'})
    
    if row['is_verified'] == 0:
        conn.close()
        print(f"❌ Login failed - Email not verified")
        return jsonify({'success': False, 'not_verified': True, 'message': '❌ Please verify your email first! Check your email for OTP.'})
    
    conn.close()
    print(f"✅ Login successful for {email}")
    
    session['citizen_logged_in'] = True
    session['citizen_email'] = row['email']
    session['citizen_name'] = row['name']
    
    return jsonify({'success': True, 'name': row['name'], 'email': row['email'], 'mobile': row['mobile'], 'city': row['city'] or ''})

@app.route('/api/citizen/logout', methods=['POST'])
def citizen_logout():
    session.pop('citizen_logged_in', None)
    session.pop('citizen_email', None)
    session.pop('citizen_name', None)
    return jsonify({'success': True, 'message': 'Logged out'})

@app.route('/api/citizen/reset-password', methods=['POST'])
def citizen_reset():
    data = request.json
    email = data.get('email', '').strip().lower()
    new_pass = data.get('new_password', '')
    
    if len(new_pass) < 6:
        return jsonify({'success': False, 'message': 'पासवर्ड 6+ कैरेक्टर'})
    
    conn = get_db()
    result = conn.execute('UPDATE citizens SET password=? WHERE email=?', 
                         (hash_password(new_pass), email))
    conn.commit()
    conn.close()
    
    if result.rowcount == 0:
        return jsonify({'success': False, 'message': 'Email नहीं मिला'})
    
    return jsonify({'success': True, 'message': 'पासवर्ड बदल गया!'})

# ==============================================
# API: COMPLAINTS
# ==============================================

@app.route('/api/complaints', methods=['POST'])
def file_complaint():
    try:
        citizen_name = request.form.get('citizen_name', '').strip()
        citizen_email = request.form.get('citizen_email', '').strip().lower()
        mobile = request.form.get('mobile', '').strip()
        complaint_text = request.form.get('complaint_text', '').strip()
        department = request.form.get('department', '').strip()
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        address = request.form.get('address', '')
        city = request.form.get('city', '')
        
        voice_path = None
        if 'voice' in request.files:
            voice_file = request.files['voice']
            if voice_file and voice_file.filename:
                fname = f"voice_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.webm"
                voice_file.save(os.path.join(UPLOAD_FOLDER, fname))
                voice_path = fname
        
        photo_path = None
        if 'photo' in request.files:
            photo_file = request.files['photo']
            if photo_file and photo_file.filename:
                ext = photo_file.filename.rsplit('.', 1)[-1].lower() if '.' in photo_file.filename else 'jpg'
                fname = f"photo_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
                photo_file.save(os.path.join(UPLOAD_FOLDER, fname))
                photo_path = fname
        
        if not all([citizen_name, citizen_email, department]):
            return jsonify({'success': False, 'message': 'सभी जरूरी फील्ड भरें'})
        if not complaint_text:
            complaint_text = '[Media Complaint]'
        
        cid = generate_complaint_id()
        conn = get_db()
        conn.execute('''INSERT INTO complaints
            (complaint_id, citizen_name, citizen_email, mobile, complaint_text, department, 
             photo_path, voice_path, latitude, longitude, address, city)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (cid, citizen_name, citizen_email, mobile, complaint_text, department,
             photo_path, voice_path, latitude, longitude, address, city))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'complaint_id': cid, 'message': 'शिकायत दर्ज हो गई!'})
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/complaints', methods=['GET'])
def get_complaints():
    try:
        email = request.args.get('email')
        dept = request.args.get('department')
        conn = get_db()
        
        if email:
            rows = conn.execute('SELECT * FROM complaints WHERE citizen_email=? ORDER BY created_at DESC', (email,)).fetchall()
        elif dept:
            rows = conn.execute('SELECT * FROM complaints WHERE LOWER(department) = LOWER(?) ORDER BY created_at DESC', (dept,)).fetchall()
        else:
            rows = conn.execute('SELECT * FROM complaints ORDER BY created_at DESC').fetchall()
        
        conn.close()
        return jsonify([dict(row) for row in rows])
    except Exception as e:
        return jsonify([]), 500

@app.route('/api/complaints/update-status', methods=['POST'])
def update_status():
    try:
        data = request.json
        complaint_id = data.get('id')
        new_status = data.get('status')
        
        if not complaint_id or not new_status:
            return jsonify({'success': False, 'message': 'id and status required'})
        
        conn = get_db()
        conn.execute('UPDATE complaints SET status=? WHERE id=?', (new_status, complaint_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Status updated!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ==============================================
# API: DEPARTMENT
# ==============================================

@app.route('/api/department/register', methods=['POST'])
def dept_register():
    data = request.json
    dept_name = data.get('dept_name', '').strip()
    officer_name = data.get('officer_name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    mobile = data.get('mobile', '').strip()
    city = data.get('city', '').strip()
    
    if not all([dept_name, officer_name, email, password]):
        return jsonify({'success': False, 'message': 'सभी फील्ड भरें'})
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'पासवर्ड 6+ कैरेक्टर'})
    
    conn = get_db()
    try:
        conn.execute('''INSERT INTO departments (dept_name, officer_name, email, password, mobile, city, is_verified) 
                       VALUES (?,?,?,?,?,?,0)''',
                     (dept_name, officer_name, email, hash_password(password), mobile, city))
        conn.commit()
        return jsonify({'success': True, 'message': 'आवेदन भेज दिया! Admin verify करेगा।'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Email पहले से रजिस्टर है'})
    finally: 
        conn.close()

@app.route('/api/department/login', methods=['POST'])
def dept_login():
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    conn = get_db()
    row = conn.execute('SELECT * FROM departments WHERE email=? AND password=?', 
                       (email, hash_password(password))).fetchone()
    conn.close()
    
    if not row:
        return jsonify({'success': False, 'message': 'Email या पासवर्ड गलत है'})
    if row['is_verified'] == 0:
        return jsonify({'success': False, 'not_verified': True, 'message': '❌ अकाउंट Verify नहीं हुआ है।'})
    
    session['dept_logged_in'] = True
    session['dept_email'] = row['email']
    session['dept_name'] = row['dept_name']
    
    return jsonify({'success': True, 'dept_name': row['dept_name'], 'officer_name': row['officer_name'], 'email': row['email']})

@app.route('/api/department/logout', methods=['POST'])
def dept_logout():
    session.pop('dept_logged_in', None)
    session.pop('dept_email', None)
    session.pop('dept_name', None)
    return jsonify({'success': True, 'message': 'Logged out'})

# ==============================================
# API: ADMIN
# ==============================================

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    conn = get_db()
    row = conn.execute('SELECT * FROM admins WHERE email = ? AND password = ?', 
                       (email, hash_password(password))).fetchone()
    conn.close()
    
    if row:
        session['admin_logged_in'] = True
        session['admin_email'] = row['email']
        return jsonify({'success': True, 'name': row['name'], 'role': row['role']})
    return jsonify({'success': False, 'message': 'Admin credentials गलत हैं'})

@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_email', None)
    return jsonify({'success': True, 'message': 'Logged out'})

@app.route('/api/admin/all-data', methods=['GET'])
def admin_all_data():
    try:
        conn = get_db()
        complaints = [dict(row) for row in conn.execute('SELECT * FROM complaints ORDER BY created_at DESC').fetchall()]
        citizens = [dict(row) for row in conn.execute('SELECT id, name, email, mobile, city, is_verified FROM citizens ORDER BY created_at DESC').fetchall()]
        departments = [dict(row) for row in conn.execute('SELECT * FROM departments ORDER BY id DESC').fetchall()]
        admins = [dict(row) for row in conn.execute('SELECT id, name, email, role FROM admins ORDER BY created_at DESC').fetchall()]
        conn.close()
        return jsonify({'complaints': complaints, 'citizens': citizens, 'departments': departments, 'admins': admins})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/verify-dept/<int:did>', methods=['POST'])
def verify_dept(did):
    try:
        action = request.json.get('action', 'approve')
        conn = get_db()
        if action == 'approve':
            conn.execute('UPDATE departments SET is_verified=1 WHERE id=?', (did,))
        else:
            conn.execute('DELETE FROM departments WHERE id=?', (did,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/delete-complaint/<int:cid>', methods=['DELETE'])
def delete_complaint(cid):
    try:
        conn = get_db()
        conn.execute('DELETE FROM complaints WHERE id=?', (cid,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/admin/create', methods=['POST'])
def create_admin():
    data = request.json
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    mobile = data.get('mobile', '').strip()
    
    if not all([name, email, password]):
        return jsonify({'success': False, 'message': 'सभी फील्ड भरें'})
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'पासवर्ड 6+ कैरेक्टर'})
    
    conn = get_db()
    try:
        conn.execute('INSERT INTO admins (name, email, password, mobile, role) VALUES (?,?,?,?,?)',
                     (name, email, hash_password(password), mobile, 'admin'))
        conn.commit()
        return jsonify({'success': True, 'message': f'✅ Admin {name} created!'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': '❌ Email already registered'})
    finally:
        conn.close()

@app.route('/api/admin/delete/<int:aid>', methods=['DELETE'])
def delete_admin(aid):
    conn = get_db()
    admin = conn.execute('SELECT * FROM admins WHERE id = ?', (aid,)).fetchone()
    if admin and admin['role'] == 'super_admin':
        conn.close()
        return jsonify({'success': False, 'message': '❌ Cannot delete Super Admin'})
    conn.execute('DELETE FROM admins WHERE id = ?', (aid,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': '✅ Admin deleted!'})

# ==============================================
# API: FEEDBACK
# ==============================================

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    data = request.json
    conn = get_db()
    conn.execute('INSERT INTO feedback (user_name, user_type, rating, message) VALUES (?,?,?,?)',
                 (data.get('user_name', ''), data.get('user_type', 'citizen'), data.get('rating', 5), data.get('message', '')))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'फीडबैक दर्ज हो गया!'})

# ==============================================
# API: CHATBOT
# ==============================================

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({'success': False, 'response': 'कृपया कुछ लिखें'})
    
    msg_lower = message.lower()
    
    if any(g in msg_lower for g in ['namaste', 'hello', 'hi', 'नमस्ते']):
        response = "🙏 नमस्ते! मैं GrievAI सहायक हूं। आपकी कैसे मदद कर सकता हूं?"
    elif any(w in msg_lower for w in ['shikayat', 'complaint', 'शिकायत']):
        response = "📝 शिकायत दर्ज करने के लिए Citizen Portal में लॉगिन करें और 'नई शिकायत' टैब पर जाएं।"
    elif any(w in msg_lower for w in ['help', 'मदद']):
        response = "❓ मैं आपकी मदद कर सकता हूं:\n• शिकायत कैसे दर्ज करें?\n• विभागों के बारे में\n• पासवर्ड रीसेट\n• फीडबैक कैसे दें?"
    else:
        response = "🤔 मैं आपका प्रश्न समझ नहीं पाया। कृपया 'help' टाइप करें।"
    
    return jsonify({'success': True, 'response': response})

# ==============================================
# START SERVER
# ==============================================

if __name__ == '__main__':
    init_db()
    print("\n" + "=" * 50)
    print("  🏛️ GRIEVAI PORTAL STARTED!")
    print(f"  🌐 {BASE_URL}")
    print("  👑 Admin: admin@grievai.com / admin123")
    print("  👤 Citizen: test@citizen.com / test123")
    print("=" * 50 + "\n")
    app.run(host='0.0.0.0', port=PORT)
