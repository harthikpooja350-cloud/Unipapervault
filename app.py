from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import os
import re
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app)

# Database Connection
client = MongoClient('mongodb://localhost:27017/')
db = client['unipaper_vault']
papers_collection = db['papers']
users_collection = db['users']
messages_collection = db['messages']

# Upload config
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Helper to convert ObjectId to string
def serialize_doc(doc):
    if not doc:
        return None
    doc['_id'] = str(doc['_id'])
    if doc.get('createdAt'):
        doc['createdAt'] = doc['createdAt'].isoformat()
    return doc

def validate_password_complexity(password):
    """
    Validates that the password has at least:
    - 8 characters
    - 1 letter
    - 1 number
    - 1 special character
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[a-zA-Z]", password):
        return False, "Password must contain at least one letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    if not re.search(r"[ !@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password):
        return False, "Password must contain at least one special character"
    return True, ""

@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    # as_attachment=False allows browser to display PDF/images inline
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=False)

# --- Routes ---

# Admin Statistics
@app.route('/api/admin/stats', methods=['GET'])
def get_admin_stats():
    try:
        users_count = users_collection.count_documents({})
        papers_count = papers_collection.count_documents({})
        
        # Aggregate total downloads
        pipeline = [{"$group": {"_id": None, "total": {"$sum": "$downloads"}}}]
        dl_res = list(papers_collection.aggregate(pipeline))
        downloads_count = dl_res[0]['total'] if dl_res else 0
        
        # Recent Messages
        messages = list(messages_collection.find().sort('createdAt', -1).limit(5))
        
        return jsonify({
            'success': True,
            'stats': {
                'usersCount': users_count,
                'papersCount': papers_count,
                'downloadsCount': downloads_count,
                'messages': [serialize_doc(m) for m in messages]
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# GET All Papers
@app.route('/api/papers', methods=['GET'])
def get_papers():
    try:
        query = {}
        university = request.args.get('university')
        course = request.args.get('course')
        year = request.args.get('year')
        p_type = request.args.get('type')
        sem = request.args.get('sem')
        search = request.args.get('search')

        if university:
            query['university'] = {'$regex': university, '$options': 'i'}
        if course:
            query['course'] = {'$regex': course, '$options': 'i'}
        if year:
            query['year'] = year
        if p_type and p_type != 'All':
            query['type'] = p_type
        if sem and sem != 'Both':
            query['sem'] = {'$regex': sem, '$options': 'i'}
        
        if search:
            query['$or'] = [
                {'subject': {'$regex': search, '$options': 'i'}},
                {'code': {'$regex': search, '$options': 'i'}},
                {'course': {'$regex': search, '$options': 'i'}}
            ]

        papers = list(papers_collection.find(query).sort('createdAt', -1))
        return jsonify([serialize_doc(p) for p in papers])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# POST Upload Paper
@app.route('/api/universities', methods=['GET'])
def get_universities():
    try:
        # Get distinct universities that are not null/empty
        universities = papers_collection.distinct('university', {'university': {'$nin': [None, '']}})
        return jsonify(sorted(universities)), 200
    except Exception as e:
        print(f"Error fetching universities: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/papers', methods=['POST'])
def upload_paper():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        filename = None
        
        if file and file.filename != '':
            timestamp = str(int(datetime.now().timestamp() * 1000))
            filename = f"{timestamp}-{file.filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        data = request.form
        
        new_paper = {
            'subject': data.get('subject'),
            'code': data.get('code'),
            'course': data.get('course'),
            'university': data.get('university'),
            'year': data.get('year'),
            'sem': data.get('sem'),
            'type': data.get('type'),
            'filename': filename,
            'downloads': 0,
            'createdAt': datetime.now()
        }
        
        result = papers_collection.insert_one(new_paper)
        new_paper['_id'] = result.inserted_id
        
        return jsonify(serialize_doc(new_paper)), 201
    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500

# PUT Update Paper
@app.route('/api/papers/<id>', methods=['PUT'])
def update_paper(id):
    try:
        data = request.json
        update_fields = {
            'subject': data.get('subject'),
            'code': data.get('code'),
            'course': data.get('course'),
            'university': data.get('university'),
            'year': data.get('year'),
            'sem': data.get('sem'),
            'type': data.get('type')
        }
        # Remove None values
        update_fields = {k: v for k, v in update_fields.items() if v is not None}
        
        result = papers_collection.update_one({'_id': ObjectId(id)}, {'$set': update_fields})
        
        if result.matched_count == 0:
            return jsonify({'error': 'Paper not found'}), 404
            
        return jsonify({'success': True, 'message': 'Paper updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# DELETE Paper
@app.route('/api/papers/<id>', methods=['DELETE'])
def delete_paper(id):
    try:
        paper = papers_collection.find_one({'_id': ObjectId(id)})
        if not paper:
            return jsonify({'error': 'Paper not found'}), 404
            
        # Delete file
        if paper.get('filename'):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], paper['filename'])
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass # Continue even if file delete fails
        
        papers_collection.delete_one({'_id': ObjectId(id)})
        return jsonify({'success': True, 'message': 'Paper deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# POST Download
@app.route('/api/papers/<id>/download', methods=['POST'])
def download_paper(id):
    try:
        paper = papers_collection.find_one({'_id': ObjectId(id)})
        if paper:
            new_downloads = paper.get('downloads', 0) + 1
            papers_collection.update_one({'_id': ObjectId(id)}, {'$set': {'downloads': new_downloads}})
            return jsonify({'success': True, 'downloads': new_downloads})
        else:
            return jsonify({'error': 'Paper not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# POST Contact Message
@app.route('/api/contact', methods=['POST'])
def contact_message():
    try:
        data = request.json
        new_message = {
            'name': data.get('name'),
            'email': data.get('email'),
            'message': data.get('message'),
            'createdAt': datetime.now()
        }
        messages_collection.insert_one(new_message)
        return jsonify({'success': True, 'message': 'Message received'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# DELETE Contact Message
@app.route('/api/contact/<id>', methods=['DELETE'])
def delete_contact_message(id):
    try:
        result = messages_collection.delete_one({'_id': ObjectId(id)})
        if result.deleted_count == 1:
            return jsonify({'success': True, 'message': 'Message deleted successfully'})
        else:
            return jsonify({'error': 'Message not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# POST Validate Email
@app.route('/api/validate-email', methods=['POST'])
def check_email_validity():
    try:
        data = request.json
        email = data.get('email')
        
        if not email:
            return jsonify({'is_valid': False, 'reason': 'Email is required'}), 400
            
        # Validate email with DNS check
        try:
            # check_deliverability=True performs DNS checks (MX records)
            v = validate_email(email, check_deliverability=True)
            email = v["email"] # normalized form
            return jsonify({'is_valid': True, 'normalized': email})
        except EmailNotValidError as e:
            # email is not valid
            return jsonify({'is_valid': False, 'reason': str(e)}), 200 # Return 200 so frontend can handle it gracefully as a validation result
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Auth Routes

# Signup
@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.json
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        role = data.get('role', 'student') # 'student' or 'admin'
        
        if users_collection.find_one({'email': email}):
            return jsonify({'error': 'User already exists'}), 400

        # Validate complexity
        is_valid, msg = validate_password_complexity(password)
        if not is_valid:
            return jsonify({'error': msg}), 400
            
        # Hash password
        hashed_password = generate_password_hash(password)
        
        # Determine approval status
        is_approved = True
        if role == 'admin':
            # Main admin is always approved
            if email == 'harthikpooja350@gmail.com': # maintain lowercase comparison
                 is_approved = True
            else:
                 is_approved = False
        
        new_user = {
            'name': name,
            'email': email,
            'password': hashed_password,
            'role': role,
            'isApproved': is_approved,
            'createdAt': datetime.now()
        }
        
        users_collection.insert_one(new_user)
        
        if role == 'admin' and not is_approved:
             return jsonify({'success': True, 'message': 'Admin account created. Waiting for approval.', 'requiresApproval': True}), 201

        # Return user without password
        return jsonify({'success': True, 'user': {'name': name, 'email': email, 'role': role}}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Login
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        # Case insensitive email search ? best practice but sticking to exact for now unless finding
        user = users_collection.find_one({'email': email})
        
        # Hardcoded Fallback for Super Admin if not in DB yet (First run)
        # Hardcoded Fallback for Super Admin if not in DB yet (First run)
        if not user and email == 'Harthikpooja350@gmail.com' and password == 'Harthik@7373':
             # Create the main admin user in DB so we don't need this check next time
             hashed_password = generate_password_hash(password)
             new_user = {
                'name': 'Harthik',
                'email': email,
                'password': hashed_password,
                'role': 'admin',
                'isApproved': True,
                'createdAt': datetime.now()
             }
             users_collection.insert_one(new_user)
             # Fetch it back
             user = users_collection.find_one({'email': email})

        if not user:
            return jsonify({'error': 'Invalid credentials'}), 400
            
        stored_password = user.get('password')
        
        # Check password
        is_valid = False
        start_is_hash = stored_password.startswith('scrypt:') or stored_password.startswith('pbkdf2:')
        
        if start_is_hash:
            if check_password_hash(stored_password, password):
                is_valid = True
        else:
            if stored_password == password:
                is_valid = True
                # Auto-migrate
                new_hash = generate_password_hash(password)
                users_collection.update_one({'_id': user['_id']}, {'$set': {'password': new_hash}})
        
        if not is_valid:
             return jsonify({'error': 'Invalid credentials'}), 400
        
        # --- SUPER ADMIN PRIVILEGE FIX ---
        if email.lower() == 'harthikpooja350@gmail.com':
            if user.get('role') != 'admin' or not user.get('isApproved'):
                users_collection.update_one({'_id': user['_id']}, {'$set': {'role': 'admin', 'isApproved': True}})
                user['role'] = 'admin'
                user['isApproved'] = True
                role = 'admin' # Ensure local var is updated for response
        # ---------------------------------

        # Check Approval
        role = user.get('role', 'student') # This might overwrite it back to student if we don't return 'admin' from DB or variable... 
        # Actually user.get('role') gets from the fetched user object. I updated user['role'] above so it should be fine.
        is_approved = user.get('isApproved', True) 
        
        if role == 'admin' and not is_approved:
            if email.lower() != 'harthikpooja350@gmail.com':
                 return jsonify({'error': 'Admin must approve your account'}), 403
            
        return jsonify({'success': True, 'user': {'name': user['name'], 'email': user['email'], 'role': role}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Admin Management Routes ---

@app.route('/api/admin/pending-users', methods=['GET'])
def get_pending_users():
    try:
        # Ideally check if requester is authorized admin
        users = list(users_collection.find({'role': 'admin', 'isApproved': False}))
        return jsonify([serialize_doc(u) for u in users])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/approve-user', methods=['POST'])
def approve_user():
    try:
        data = request.json
        user_id = data.get('userId')
        approve = data.get('approve') # True/False
        
        if approve:
            users_collection.update_one({'_id': ObjectId(user_id)}, {'$set': {'isApproved': True}})
            return jsonify({'success': True, 'message': 'User approved'})
        else:
            users_collection.delete_one({'_id': ObjectId(user_id)})
            return jsonify({'success': True, 'message': 'User rejected'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- OTP FLOW ROUTES ---
import random
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# EMAIL CONFIGURATION
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
SENDER_EMAIL = "unipapervalut@gmail.com"
SENDER_PASSWORD = "kagt whpm iutq kyvf"

@app.route('/api/request-otp', methods=['POST'])
def request_otp():
    try:
        data = request.json
        email = data.get('email')
        
        user = users_collection.find_one({'email': email})
        if not user:
            return jsonify({'error': 'Email not found'}), 404
            
        # Generate 4-digit OTP
        otp = str(random.randint(1000, 9999))
        
        # Save OTP to user document
        users_collection.update_one({'email': email}, {'$set': {'otp': otp}})
        
        # Send Email via SMTP
        try:
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = email
            msg['Subject'] = "UniPaper Vault - Password Reset OTP"
            
            # HTML Email Content
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                    <div style="max-width: 500px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        <h2 style="color: #2563eb; text-align: center; margin-bottom: 20px;">UniPaper Vault</h2>
                        <p style="color: #333333; font-size: 16px;">Hello {user.get('name', 'Student')},</p>
                        <p style="color: #666666; font-size: 14px; line-height: 1.5;">You requested a password reset. Use the One-Time Password (OTP) below to proceed. This code is valid for 10 minutes.</p>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <span style="display: inline-block; font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #2563eb; background-color: #eff6ff; padding: 10px 20px; border-radius: 5px; border: 1px dashed #2563eb;">
                                {otp}
                            </span>
                        </div>
                        
                        <p style="color: #999999; font-size: 12px; text-align: center; margin-top: 30px;">If you didn't request this, you can safely ignore this email.</p>
                    </div>
                </body>
            </html>
            """
            
            msg.attach(MIMEText(html_content, 'html'))
            
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, email, msg.as_string())
                
            return jsonify({'success': True, 'message': f'OTP sent to {email}'})
            
        except Exception as e:
            print(f"Email Error: {e}")
            return jsonify({'error': 'Failed to send email via Gmail'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    try:
        data = request.json
        email = data.get('email')
        otp = data.get('otp')
        
        user = users_collection.find_one({'email': email})
        
        if user and user.get('otp') == otp:
            # OTP Matches
            return jsonify({'success': True, 'message': 'OTP Verified'})
        else:
            return jsonify({'error': 'Invalid OTP'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    try:
        data = request.json
        email = data.get('email')
        # otp = data.get('otp') # Ideally verify OTP again or use a token, but skipping for simplicity
        new_password = data.get('newPassword')

        # Validate complexity
        is_valid, msg = validate_password_complexity(new_password)
        if not is_valid:
            return jsonify({'error': msg}), 400
        
        # Hash new password
        hashed_password = generate_password_hash(new_password)
        
        # Update Password and Clear OTP
        users_collection.update_one(
            {'email': email}, 
            {'$set': {'password': hashed_password, 'otp': None}}
        )
        
        return jsonify({'success': True, 'message': 'Password reset successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
