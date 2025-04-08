import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, send_from_directory
import google.generativeai as genai
import pyttsx3
from googletrans import Translator
import json
from pathlib import Path
import mysql.connector
import random
import string
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in .env file. Please add it to a .env file in the project root.")

# Configure Gemini API
genai.configure(api_key=api_key)

# Initialize translator and TTS engine
translator = Translator()
tts_engine = pyttsx3.init()
voices = tts_engine.getProperty('voices')

# Supported languages with codes and flags
LANGUAGES = {
    'en': {'name': 'English', 'flag': '🇬🇧'},
    'es': {'name': 'Spanish', 'flag': '🇪🇸'},
    'fr': {'name': 'French', 'flag': '🇫🇷'},
    'de': {'name': 'German', 'flag': '🇩🇪'},
    'it': {'name': 'Italian', 'flag': '🇮🇹'},
    'pt': {'name': 'Portuguese', 'flag': '🇵🇹'},
    'ru': {'name': 'Russian', 'flag': '🇷🇺'},
    'zh': {'name': 'Chinese', 'flag': '🇨🇳'},
    'ja': {'name': 'Japanese', 'flag': '🇯🇵'},
    'ar': {'name': 'Arabic', 'flag': '🇸🇦'},
    'hi': {'name': 'Hindi', 'flag': '🇮🇳'},
}

# Instruction for Gemini AI
instruction = """
You are an expert U.S. educational advisor providing comprehensive guidance on:

[1] INSTITUTIONAL INFORMATION:
• University/college profiles (public/private/community)
• K-12 school systems and notable programs
• Admissions requirements for all levels
• Special programs (STEM, arts, IB, etc.)

[2] ADMISSIONS GUIDANCE:
• Application timelines (month/day format required)
• Testing requirements (SAT/ACT/PSAT etc.)
• Portfolio/audition requirements where applicable
• Transfer student pathways

[3] ACADEMIC PROGRAMMING:
• Curriculum strengths by institution
• Specialized programs (magnet, charter, etc.)
• Advanced placement opportunities
• Extracurricular alignments

For K-12 school inquiries, provide:
- School Name (Public/Private/Charter)
- Location (City, State)
- Notable Programs (STEM, Arts, etc.)
- Admissions Timeline (if applicable)
- Special Requirements

Example Response for School Inquiry:
🏫 **Notable Plano, TX Middle Schools for Math Students**
- **Wilson Middle School (Public)**
  • Math Program: Advanced STEM curriculum with math competitions
  • Application Window: January 15 - March 1 (for special programs)
  
- **St. Mark's School of Texas (Private)**
  • Math Program: Accelerated curriculum with Math Olympiad training
  • Admissions Deadline: December 1, 2024
  • Entrance Exam: ISEE required (November test dates)

For all responses:
1. Begin with appropriate header emoji (🎓 🏫 📚)
2. Use bullet points with exact dates when available
3. Include program specializations
4. Note any application/test requirements

Refuse non-educational queries with:
"I specialize in U.S. educational programs and admissions guidance."
"""

# Create Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'downloads'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)

# Instantiate the Gemini model
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=instruction,
    generation_config={
        "temperature": 0.4,
        "top_p": 0.9,
        "top_k": 40,
        "max_output_tokens": 600,
    },
)

# Database Connection Helper
def get_db_connection():
    try:
        db = mysql.connector.connect(
            host=os.getenv('DB_HOST', '127.0.0.1'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', '1234'),
            database=os.getenv('DB_NAME', 'edupath_auth')
        )
        return db
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

def translate_text(text, dest_lang='en'):
    try:
        if dest_lang == 'en':
            return text
        translation = translator.translate(text, dest=dest_lang)
        return translation.text
    except Exception as e:
        print(f"Translation error: {e}")
        return text

def text_to_speech(text, lang='en'):
    try:
        if lang == 'en':
            tts_engine.setProperty('voice', voices[0].id)  # English voice
        elif lang == 'es':
            tts_engine.setProperty('voice', 'spanish')  # Spanish voice
        tts_engine.say(text)
        tts_engine.runAndWait()
    except Exception as e:
        print(f"TTS error: {e}")

# Routes
@app.route('/')
def home():
    return render_template('landingpage.html', languages=LANGUAGES)

@app.route('/ask', methods=['POST'])
def ask_question():
    data = request.get_json()
    user_input = data.get('query', '').strip()
    input_lang = data.get('input_lang', 'en')
    output_lang = data.get('output_lang', 'en')
    
    if not user_input:
        return jsonify({'response': "⚠️ Please ask a question.", 'lang': output_lang})

    try:
        if input_lang != 'en':
            user_input = translate_text(user_input, 'en')
        
        response = model.generate_content(user_input)
        text = response.text.strip() if response.text else "⚠️ No response received from the model."
        
        if output_lang != 'en':
            text = translate_text(text, output_lang)
        
        return jsonify({'response': text, 'lang': output_lang})
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        if output_lang != 'en':
            error_msg = translate_text(error_msg, output_lang)
        return jsonify({'response': error_msg, 'lang': output_lang})

@app.route('/speak', methods=['POST'])
def speak_text():
    data = request.get_json()
    text = data.get('text', '')
    lang = data.get('lang', 'en')
    
    if text:
        text_to_speech(text, lang)
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'No text provided'})

@app.route('/download', methods=['POST'])
def download_text():
    data = request.get_json()
    text = data.get('text', '')
    lang = data.get('lang', 'en')
    
    if not text:
        return jsonify({'status': 'error', 'message': 'No text to download'})
    
    filename = f"response_{lang}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
        return jsonify({'status': 'success', 'url': f'/downloads/{filename}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/downloads/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# Authentication Routes
@app.route('/signup', methods=['GET'])
def signup_page():
    return render_template('signup.html')

@app.route('/index', methods=['GET'])
def index_page():
    return render_template('index.html')
@app.route('/home', methods=['GET'])
def home_page():
    return render_template('home.html')

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    confirm_password = data.get('confirmPassword')

    if not all([username, email, password, confirm_password]):
        return jsonify({'message': 'All fields are required'}), 400

    if password != confirm_password:
        return jsonify({'message': 'Passwords do not match'}), 400

    db = get_db_connection()
    if not db:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = db.cursor()
    try:
        # Check if email exists
        cursor.execute('SELECT email FROM users WHERE email = %s', (email,))
        if cursor.fetchone():
            return jsonify({'message': 'Email already exists'}), 400

        # Hash password before storing
        hashed_password = generate_password_hash(password)
        
        # Insert new user
        cursor.execute(
            'INSERT INTO users (username, email, password) VALUES (%s, %s, %s)',
            (username, email, hashed_password)
        )
        db.commit()
        return jsonify({'message': 'Signup successful'}), 201
    except mysql.connector.Error as err:
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        db.close()

@app.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'message': 'Email and password are required'}), 400

    db = get_db_connection()
    if not db:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()
        
        if not user or not check_password_hash(user['password'], password):
            return jsonify({'message': 'Invalid email or password'}), 401
        
        # Here you would typically create a session or JWT token
        return jsonify({'message': 'Login successful'}), 200
    except mysql.connector.Error as err:
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        db.close()

@app.route('/forgot-password', methods=['GET'])
def forgot_password_page():
    return render_template('forgot-password.html')

@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'message': 'Email is required'}), 400

    db = get_db_connection()
    if not db:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = db.cursor()
    try:
        # Check if email exists
        cursor.execute('SELECT email FROM users WHERE email = %s', (email,))
        if not cursor.fetchone():
            return jsonify({'message': 'If this email exists, a reset link has been sent'}), 200

        # Generate reset token
        token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        expires_at = datetime.now() + timedelta(hours=1)

        # Store token in database
        cursor.execute(
            'INSERT INTO password_resets (email, token, expires_at) VALUES (%s, %s, %s)',
            (email, token, expires_at)
        )
        db.commit()

        # In a real app, you would send an email with this token
        print(f"Password reset token for {email}: {token}")  # For development only
        
        return jsonify({'message': 'If this email exists, a reset link has been sent'}), 200
    except mysql.connector.Error as err:
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        db.close()

@app.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    token = data.get('token')
    new_password = data.get('newPassword')
    confirm_password = data.get('confirmPassword')

    if not token or not new_password or not confirm_password:
        return jsonify({'message': 'All fields are required'}), 400

    if new_password != confirm_password:
        return jsonify({'message': 'Passwords do not match'}), 400

    db = get_db_connection()
    if not db:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = db.cursor()
    try:
        # Check if token is valid and not expired
        cursor.execute(
            'SELECT email FROM password_resets WHERE token = %s AND expires_at > NOW()',
            (token,)
        )
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'message': 'Invalid or expired token'}), 400

        email = result[0]
        hashed_password = generate_password_hash(new_password)

        # Update password
        cursor.execute(
            'UPDATE users SET password = %s WHERE email = %s',
            (hashed_password, email)
        )
        
        # Delete used token
        cursor.execute('DELETE FROM password_resets WHERE token = %s', (token,))
        
        db.commit()
        return jsonify({'message': 'Password reset successful'}), 200
    except mysql.connector.Error as err:
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        db.close()

if __name__ == '__main__':
    app.run(debug=True, threaded=True)