from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
from dotenv import load_dotenv

# Load environment variables FIRST before any other imports
load_dotenv()

import firebase_admin
from firebase_admin import credentials, auth, firestore, storage
from werkzeug.utils import secure_filename
from modules.utils import generate_filename, allowed_file, extract_text
from modules.summary import generate_summary
from modules.questions import generate_questions
import datetime
import requests

app = Flask(__name__)
app.config.from_object('config.Config')

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Context processor to make user info available globally
@app.context_processor
def inject_user():
    if 'user' in session:
        uid = session['user']
        if db:
            user_doc = db.collection('users').document(uid).get()
            if user_doc.exists:
                return {'current_user': user_doc.to_dict()}
    return {'current_user': None}

# Initialize Firebase Admin
cred_path = app.config['FIREBASE_CREDENTIALS_PATH']
if os.path.exists(cred_path):
    cred = credentials.Certificate(cred_path)
    # Check if app is already initialized to avoid errors
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {
            'storageBucket': 'notestack-d14e7.appspot.com'
        })
    db = firestore.client()
    bucket = storage.bucket() if firebase_admin._apps else None
elif os.environ.get('FIREBASE_CREDENTIALS_JSON'):
    # Fallback for Render/Production using Environment Variable
    import json
    cred_json = json.loads(os.environ.get('FIREBASE_CREDENTIALS_JSON'))
    cred = credentials.Certificate(cred_json)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {
            'storageBucket': 'notestack-d14e7.appspot.com'
        })
    db = firestore.client()
    bucket = storage.bucket() if firebase_admin._apps else None
else:
    print(f"Warning: Firebase credentials not found at {cred_path} and FIREBASE_CREDENTIALS_JSON not set.")
    db = None
    bucket = None

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/upload')
def upload():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('upload.html')

@app.route('/upload_file', methods=['POST'])
def upload_file():
    # Use session instead of token
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    uid = session['user']
    
    # Get user data from Firestore
    user_data = {'name': 'Unknown User'}
    enrollment_id = 'Unknown'
    
    try:
        if db:
            user_doc = db.collection('users').document(uid).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                enrollment_id = user_data.get('enrollmentId', 'Unknown')
                print(f"User found: {user_data.get('name')} ({enrollment_id})")
            else:
                # Fallback: Get email from Firebase Auth
                try:
                    user_record = auth.get_user(uid)
                    user_data = {
                        'name': user_record.email.split('@')[0],
                        'email': user_record.email
                    }
                    enrollment_id = 'NotSet'
                    print(f"User profile not in Firestore, using email: {user_record.email}")
                except Exception as auth_err:
                    print(f"Could not get user from Auth: {auth_err}")
        else:
            return jsonify({'error': 'Database not initialized'}), 500
    except Exception as e:
        print(f"Error fetching user: {e}")

    if file and allowed_file(file.filename):
        subject_name = request.form.get('subjectName')
        department = request.form.get('department')
        file_type = request.form.get('fileType', 'note') # 'note' or 'pyq'
        
        if not subject_name or not department:
            return jsonify({'error': 'Subject Name and Department are required'}), 400
        
        try:
            # 1. Rename and save locally
            new_filename = generate_filename(subject_name, department, enrollment_id)
            local_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
            file.save(local_path)
            print(f"File saved locally: {local_path}")
            
            # 2. Use local file URL
            file_url = f"/uploads/{new_filename}"
            
            # 3. Save metadata to Firestore
            doc_ref = db.collection('notes').document()
            doc_ref.set({
                'subjectName': subject_name,
                'department': department,
                'type': file_type,
                'uploaderId': uid,
                'uploaderName': user_data.get('name', 'User'),
                'filename': new_filename,
                'fileUrl': file_url,
                'timestamp': datetime.datetime.now(),
                'status': 'approved'
            })
            print(f"Metadata saved to Firestore for: {new_filename}")
            
            return jsonify({'message': 'File uploaded successfully!'}), 200
        except Exception as e:
            print(f"Upload error: {str(e)}")
            if os.path.exists(local_path):
                os.remove(local_path)
            return jsonify({'error': f'Upload failed: {str(e)}'}), 500

    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/ai-assist')
def ai_assist():
    if 'user' not in session:
        return redirect(url_for('login'))
    if not db:
        return "Database not initialized", 500
    
    uid = session['user']
    try:
        # Get saved notes for this user
        saved_refs = db.collection('saved_notes').where('userId', '==', uid).stream()
        saved_note_ids = [doc.to_dict().get('noteId') for doc in saved_refs]
        
        notes_list = []
        if saved_note_ids:
            # Firestore 'in' query supports up to 30 items
            # For simplicity, we fetch all notes and filter, or batch if needed
            # Here we just fetch the saved ones individually for accuracy if list is small
            for note_id in saved_note_ids:
                note_doc = db.collection('notes').document(note_id).get()
                if note_doc.exists:
                    note = note_doc.to_dict()
                    note['id'] = note_doc.id
                    notes_list.append(note)
        
        return render_template('ai_assist.html', notes=notes_list)
    except Exception as e:
        print(f"AI Assist fetch error: {e}")
        return render_template('ai_assist.html', notes=[])

@app.route('/api/generate_summary', methods=['POST'])
def api_generate_summary():
    data = request.json
    note_id = data.get('noteId')
    
    note_ref = db.collection('notes').document(note_id)
    note = note_ref.get()
    if not note.exists:
        return jsonify({'error': 'Note not found'}), 404
        
    note_data = note.to_dict()
    text = note_data.get('extractedText', '')
    
    if not text:
        # Extract on the fly
        filename = note_data.get('filename')
        if filename:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            print(f"DEBUG: Looking for file at {filepath}")
            if os.path.exists(filepath):
                print(f"DEBUG: File found, extracting text for {filename}")
                text = extract_text(filepath)
                if text:
                    print(f"DEBUG: Text extracted successfully ({len(text)} chars)")
                    # Update Firestore so we don't have to extract again
                    note_ref.update({'extractedText': text})
                else:
                    print("DEBUG: extract_text returned empty/None")
            else:
                print(f"DEBUG: File NOT found at {filepath}")
        else:
            print("DEBUG: No filename in note metadata")
    
    if not text:
        return jsonify({'error': 'No text content available or extracted for this note.'}), 400
        
    try:
        summary = generate_summary(text)
        return jsonify(summary)
    except Exception as e:
        print(f"Summary Gen Error: {e}")
        return jsonify({'error': f'AI Summary generation failed: {str(e)}'}), 500

@app.route('/api/generate_questions', methods=['POST'])
def api_generate_questions():
    data = request.json
    note_id = data.get('noteId')
    mode = data.get('mode', 'objective')
    marks = data.get('marks')
    
    note_ref = db.collection('notes').document(note_id)
    note = note_ref.get()
    if not note.exists:
        return jsonify({'error': 'Note not found'}), 404
        
    note_data = note.to_dict()
    text = note_data.get('extractedText', '')
    
    if not text:
        # Extract on the fly
        filename = note_data.get('filename')
        if filename:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(filepath):
                print(f"Extracting text on-the-fly for {filename}")
                text = extract_text(filepath)
                if text:
                    # Update Firestore so we don't have to extract again
                    note_ref.update({'extractedText': text})

    if not text:
        return jsonify({'error': 'No text content available or extracted for this note.'}), 400

    try:
        num_questions = int(data.get('numQuestions', 1))
        questions = generate_questions(text, mode, marks, num_questions)
        return jsonify(questions)
    except Exception as e:
        print(f"Questions Gen Error: {e}")
        return jsonify({'error': f'AI Questions generation failed: {str(e)}'}), 500


@app.route('/library')
def library():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    uid = session['user']
    if not db:
        return "Database not initialized", 500
    
    notes_list = []
    
    # Get only saved notes (not uploads)
    saved_refs = db.collection('saved_notes').where('userId', '==', uid).stream()
    saved_note_ids = [doc.to_dict().get('noteId') for doc in saved_refs]
    
    for note_id in saved_note_ids:
        note_doc = db.collection('notes').document(note_id).get()
        if note_doc.exists:
            note = note_doc.to_dict()
            note['id'] = note_doc.id
            notes_list.append(note)
        
    return render_template('library.html', notes=notes_list)


@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/session_login', methods=['POST'])
def session_login():
    id_token = request.json.get('idToken')
    try:
        decoded_token = auth.verify_id_token(id_token)
        session['user'] = decoded_token['uid']
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 401

@app.route('/register_user', methods=['POST'])
def register_user():
    data = request.json
    id_token = data.get('idToken')
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        
        user_data = {
            'name': data.get('name'),
            'enrollmentId': data.get('enrollmentId'),
            'branch': data.get('branch'),
            'email': decoded_token['email'],
            'role': 'student' 
        }
        if db:
            db.collection('users').document(uid).set(user_data)
        
        # Ensure session is empty after registration
        session.clear()
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    uid = session['user']
    stats = {
        'uploads': 0,
        'views': 0,
        'recent_views': []
    }
    
    try:
        if db:
            # 1. Total Uploads
            uploads_ref = db.collection('notes').where('uploaderId', '==', uid).get()
            stats['uploads'] = len(uploads_ref)
            
            # 2. Total Views & Recent Views
            # Simplify query to avoid index requirement - sort in Python
            views_stream = db.collection('user_views').where('userId', '==', uid).stream()
            all_views = [doc.to_dict() for doc in views_stream]
            
            # Sort by timestamp descending
            all_views.sort(key=lambda x: x.get('timestamp'), reverse=True)
            
            seen_notes = set()
            recent_notes = []
            
            for view_data in all_views:
                note_id = view_data.get('noteId')
                
                if note_id and note_id not in seen_notes:
                    seen_notes.add(note_id)
                    # Fetch note details
                    note_doc = db.collection('notes').document(note_id).get()
                    if note_doc.exists:
                        note = note_doc.to_dict()
                        note['id'] = note_doc.id
                        recent_notes.append(note)
                
                if len(recent_notes) >= 5:
                    break
            
            stats['views'] = len(all_views)
            stats['recent_views'] = recent_notes
            print(f"Stats updated for {uid}: {stats['uploads']} uploads, {stats['views']} total views")
            
    except Exception as e:
        print(f"Dashboard stats error: {e}")
        import traceback
        traceback.print_exc()
        
    return render_template('dashboard.html', stats=stats)

@app.route('/api/log_view', methods=['POST'])
def log_view():
    if 'user' not in session:
        return jsonify({'status': 'ignored'}), 200
    
    data = request.json
    note_id = data.get('noteId')
    uid = session['user']
    
    if not note_id:
        return jsonify({'error': 'Missing noteId'}), 400
        
    try:
        if db:
            print(f"Logging view for uid: {uid}, noteId: {note_id}")
            db.collection('user_views').add({
                'userId': uid,
                'noteId': note_id,
                'timestamp': datetime.datetime.now()
            })
            return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    return jsonify({'status': 'no_db'}), 200

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('landing'))

@app.route('/search')
def search():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('search.html')

@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    uid = session['user']
    profile_data = None
    my_notes = []
    
    try:
        if db:
            # Get user profile
            user_doc = db.collection('users').document(uid).get()
            if user_doc.exists:
                profile_data = user_doc.to_dict()
                # Ensure pfp, timetable, syllabus keys exist
                if 'pfpUrl' not in profile_data: profile_data['pfpUrl'] = None
                if 'timetableUrl' not in profile_data: profile_data['timetableUrl'] = None
                if 'syllabusUrl' not in profile_data: profile_data['syllabusUrl'] = None
            else:
                # Try to get from auth
                try:
                    user_record = auth.get_user(uid)
                    profile_data = {
                        'name': user_record.email.split('@')[0],
                        'email': user_record.email,
                        'enrollmentId': 'Not Set',
                        'branch': 'Not Set',
                        'pfpUrl': None,
                        'timetableUrl': None,
                        'syllabusUrl': None
                    }
                except:
                    pass
            
            # Get user's saved notes to mark status
            saved_refs = db.collection('saved_notes').where('userId', '==', uid).stream()
            saved_note_ids = [doc.to_dict().get('noteId') for doc in saved_refs]
            
            # Get user's uploads
            notes_ref = db.collection('notes').where('uploaderId', '==', uid).stream()
            for doc in notes_ref:
                note = doc.to_dict()
                note['id'] = doc.id
                note['isSaved'] = note['id'] in saved_note_ids
                my_notes.append(note)
    except Exception as e:
        print(f"Profile fetch error: {e}")
    
    return render_template('profile.html', profile=profile_data, my_notes=my_notes)

@app.route('/api/update_profile', methods=['POST'])
def update_profile():
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.json
    uid = session['user']
    name = data.get('name')
    
    try:
        if db:
            db.collection('users').document(uid).update({'name': name})
            return jsonify({'message': 'Profile updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Database not initialized'}), 500

@app.route('/api/upload_profile_file', methods=['POST'])
def upload_profile_file():
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    file_type = request.form.get('type') # 'pfp', 'timetable', 'syllabus'
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and file_type:
        uid = session['user']
        ext = file.filename.rsplit('.', 1)[1].lower()
        new_filename = f"{file_type}_{uid}.{ext}"
        local_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        file.save(local_path)
        
        file_url = f"/uploads/{new_filename}"
        field_name = f"{file_type}Url"
        
        try:
            if db:
                db.collection('users').document(uid).update({field_name: file_url})
                return jsonify({'message': f'{file_type} updated', 'url': file_url})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
            
    return jsonify({'error': 'Invalid request'}), 400

@app.route('/api/change_password', methods=['POST'])
def change_password():
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.json
    new_password = data.get('newPassword')
    uid = session['user']
    
    try:
        auth.update_user(uid, password=new_password)
        return jsonify({'message': 'Password updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search_notes')
def api_search_notes():
    query = request.args.get('q', '').lower()
    file_type = request.args.get('type', 'all')
    if not db or not query:
        return jsonify([])
    
    try:
        # Get current user's saved notes to mark status
        saved_note_ids = []
        if 'user' in session:
            uid = session['user']
            saved_refs = db.collection('saved_notes').where('userId', '==', uid).stream()
            saved_note_ids = [doc.to_dict().get('noteId') for doc in saved_refs]

        notes_ref = db.collection('notes').where('status', '==', 'approved').stream()
        results = []
        for doc in notes_ref:
            note = doc.to_dict()
            note['id'] = doc.id
            note['isSaved'] = note['id'] in saved_note_ids
            
            # Simple search matching
            subject_match = query in note.get('subjectName', '').lower()
            dept_match = query in note.get('department', '').lower() or query in note.get('subjectCode', '').lower()
            uploader_match = query in note.get('uploaderName', '').lower()
            
            type_match = (file_type == 'all' or note.get('type', 'note') == file_type)
            
            if (subject_match or dept_match or uploader_match) and type_match:
                results.append(note)
        return jsonify(results)
    except Exception as e:
        print(f"Search error: {e}")
        return jsonify([])

@app.route('/api/get_profile')
def api_get_profile():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'No token'}), 401
    
    try:
        id_token = auth_header.replace('Bearer ', '')
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        
        if db:
            user_doc = db.collection('users').document(uid).get()
            if user_doc.exists:
                profile = user_doc.to_dict()
                return jsonify(profile)
            else:
                # Create profile from auth data if missing
                profile = {
                    'name': decoded_token.get('email', 'User').split('@')[0],
                    'email': decoded_token.get('email', 'N/A'),
                    'enrollmentId': 'Not Set',
                    'branch': 'Not Set'
                }
                # Save it to Firestore for next time
                db.collection('users').document(uid).set(profile)
                return jsonify(profile)
        
        return jsonify({
            'name': decoded_token.get('name', decoded_token.get('email', 'User').split('@')[0]),
            'email': decoded_token.get('email', 'N/A'),
            'enrollmentId': 'Not Set',
            'branch': 'Not Set'
        })
    except Exception as e:
        print(f"Profile fetch error: {e}")
        return jsonify({'error': str(e)}), 401

@app.route('/api/my_notes')
def api_my_notes():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'No token'}), 401
    
    try:
        id_token = auth_header.replace('Bearer ', '')
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        
        if not db:
            return jsonify([])
        
        notes_ref = db.collection('notes').where('uploaderId', '==', uid).stream()
        notes_list = []
        for doc in notes_ref:
            note = doc.to_dict()
            note['id'] = doc.id
            notes_list.append(note)
        return jsonify(notes_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 401



@app.route('/api/save_note', methods=['POST'])
def api_save_note():
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.json
    note_id = data.get('noteId')
    uid = session['user']
    
    try:
        # Check if already saved
        existing = db.collection('saved_notes').where('userId', '==', uid).where('noteId', '==', note_id).get()
        if not existing:
            # Save to saved_notes collection
            save_ref = db.collection('saved_notes').document()
            save_ref.set({
                'userId': uid,
                'noteId': note_id,
                'savedAt': datetime.datetime.now()
            })
            return jsonify({'message': 'Note saved successfully!'})
        else:
            return jsonify({'message': 'Note already in your library!'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/unsave_note', methods=['POST'])
def api_unsave_note():
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.json
    note_id = data.get('noteId')
    uid = session['user']
    
    try:
        # Find and delete the saved note
        saved_refs = db.collection('saved_notes').where('userId', '==', uid).where('noteId', '==', note_id).stream()
        for doc in saved_refs:
            doc.reference.delete()
        return jsonify({'message': 'Note removed from saved collection'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/saved_notes')
def api_saved_notes():
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    uid = session['user']
    
    try:
        # Get all saved note IDs for this user
        saved_refs = db.collection('saved_notes').where('userId', '==', uid).stream()
        note_ids = [doc.to_dict().get('noteId') for doc in saved_refs]
        
        # Get full note details
        notes_list = []
        for note_id in note_ids:
            note_doc = db.collection('notes').document(note_id).get()
            if note_doc.exists:
                note = note_doc.to_dict()
                note['id'] = note_doc.id
                notes_list.append(note)
        
        return jsonify(notes_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/clear_all_users', methods=['POST'])
def clear_all_users():
    """Admin route to clear all users - USE WITH CAUTION"""
    try:
        # Clear Firestore users
        if db:
            users_ref = db.collection('users').stream()
            for doc in users_ref:
                doc.reference.delete()
                print(f"Deleted user: {doc.id}")
            
            # Clear notes
            notes_ref = db.collection('notes').stream()
            for doc in notes_ref:
                doc.reference.delete()
                print(f"Deleted note: {doc.id}")
            
            # Clear saved notes
            saved_ref = db.collection('saved_notes').stream()
            for doc in saved_ref:
                doc.reference.delete()
        
        # Clear Firebase Auth users
        page = auth.list_users()
        while page:
            for user in page.users:
                auth.delete_user(user.uid)
                print(f"Deleted auth user: {user.email}")
            page = page.get_next_page()
        
        return jsonify({'message': 'All users and data cleared successfully!'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
