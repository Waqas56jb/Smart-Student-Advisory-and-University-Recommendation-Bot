import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, Response
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
from google.api_core.exceptions import ServiceUnavailable

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

# Instruction for Gemini AI (Updated to request ONE recommendation)
instruction = """
You are an expert U.S. educational advisor that provides personalized university recommendations based on student profiles. 

When given a student profile, provide:
1. One university recommendation highly correlated with the student's interests and qualifications
2. For the university, include:
   - Name and classification (Public/Private)
   - Location (City, State)
   - Ranking (if notable)
   - Top 3 relevant programs
   - Admission rate and average test scores (if available)
   - Application deadlines
   - Website URL
   - Contact information
   - Special features matching the student's profile

Format the recommendation as a JSON object with these fields:
{
  "name": "University Name",
  "type": "Public/Private",
  "location": "City, State",
  "ranking": "Ranking info",
  "programs": ["Program 1", "Program 2", "Program 3"],
  "admission_rate": "XX%",
  "avg_scores": "SAT/ACT ranges",
  "deadlines": {
    "regular": "MM/DD",
    "early": "MM/DD (if applicable)"
  },
  "website": "https://university.edu",
  "contact": {
    "phone": "XXX-XXX-XXXX",
    "email": "admissions@university.edu"
  },
  "match_reasons": ["Reason 1", "Reason 2", "Reason 3"]
}

Return only the JSON object of the single recommendation, nothing else.
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

@app.route('/forget', methods=['GET'])
def forget_page():
    return render_template('forget.html')

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
        # Simply check if email exists
        cursor.execute('SELECT email FROM users WHERE email = %s', (email,))
        if not cursor.fetchone():
            return jsonify({'message': 'No account found with this email'}), 404
        
        # Return success if email exists
        return jsonify({
            'message': 'Password reset allowed',
            'email': email,
            'status': 'success'
        }), 200
    except mysql.connector.Error as err:
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        db.close()

@app.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    email = data.get('email')
    new_password = data.get('newPassword')
    confirm_password = data.get('confirmPassword')

    if not email or not new_password or not confirm_password:
        return jsonify({'message': 'All fields are required'}), 400

    if new_password != confirm_password:
        return jsonify({'message': 'Passwords do not match'}), 400

    db = get_db_connection()
    if not db:
        return jsonify({'message': 'Database connection failed'}), 500

    cursor = db.cursor()
    try:
        # Verify email exists (extra safety check)
        cursor.execute('SELECT email FROM users WHERE email = %s', (email,))
        if not cursor.fetchone():
            return jsonify({'message': 'No account found with this email'}), 404

        # Update password directly
        hashed_password = generate_password_hash(new_password)
        cursor.execute(
            'UPDATE users SET password = %s WHERE email = %s',
            (hashed_password, email)
        )
        db.commit()
        return jsonify({'message': 'Password reset successful'}), 200
    except mysql.connector.Error as err:
        return jsonify({'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        db.close()

@app.route('/profile', methods=['GET'])
def profile_page():
    return render_template('profile.html')

@app.route("/profile", methods=["POST"])
def handle_profile():
    if request.method == "POST":
        try:
            # Get form data as JSON
            data = request.get_json()
            
            # Convert scholarshipneed to boolean
            scholarshipneed = data.get('scholarshipneed', 'no') == 'yes'
            
            # Connect to database
            db = get_db_connection()
            if not db:
                return jsonify({'message': 'Database connection failed'}), 500
                
            cursor = db.cursor()
            
            # Insert data into database
            cursor.execute("""
                INSERT INTO studentprofile (
                    name, age, class, cgpa, interest, scholarshipneed, hobbies, state, email, phone, 
                    preferred_location, financial_status, parents_qualification, english_proficiency, 
                    extra_curriculars, career_goal, preferred_study_type, gmat_sat_score, past_achievements
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data.get('name'),
                data.get('age'),
                data.get('class'),
                data.get('cgpa'),
                data.get('interest'),
                scholarshipneed,
                data.get('hobbies'),
                data.get('state'),
                data.get('email'),
                data.get('phone'),
                data.get('preferred_location'),
                data.get('financial_status'),
                data.get('parents_qualification'),
                data.get('english_proficiency'),
                data.get('extra_curriculars'),
                data.get('career_goal'),
                data.get('preferred_study_type'),
                data.get('gmat_sat_score'),
                data.get('past_achievements')
            ))
            
            db.commit()
            return jsonify({'message': 'Profile saved successfully'}), 200
            
        except mysql.connector.Error as err:
            db.rollback()
            return jsonify({'message': f'Database error: {err}'}), 500
        except Exception as e:
            return jsonify({'message': f'Error: {str(e)}'}), 500
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'db' in locals():
                db.close()

@app.route('/recommendation')
def recommendation_page():
    # Get the most recent profile (you should replace this with user session logic)
    db = get_db_connection()
    if not db:
        return render_template('recommendation.html', error="Database connection failed")
    
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM studentprofile ORDER BY student_id DESC LIMIT 1")
        profile = cursor.fetchone()
        
        if not profile:
            return render_template('recommendation.html', error="No profile found")
        
        return render_template('recommendation.html', profile=profile)
        
    except Exception as e:
        print(f"Error getting profile: {str(e)}")
        return render_template('recommendation.html', error=str(e))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()

# Updated endpoint to handle ONE recommendation and ServiceUnavailable error
@app.route('/generate-recommendations', methods=['GET'])
def generate_recommendations():
    profile_id = request.args.get('profile_id')
    
    if not profile_id:
        return jsonify({'error': 'Profile ID is required'}), 400
    
    db = get_db_connection()
    if not db:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM studentprofile WHERE student_id = %s", (profile_id,))
        profile = cursor.fetchone()
        
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404
        
        # Build the prompt for Gemini (updated for one recommendation)
        prompt = f"""
        Generate one university recommendation highly correlated with this student profile:
        - Name: {profile['name']}
        - Age: {profile['age']}
        - Current Class: {profile['class']}
        - CGPA: {profile['cgpa']}
        - Field of Interest: {profile['interest']}
        - Needs Scholarship: {'Yes' if profile['scholarshipneed'] else 'No'}
        - State: {profile['state']}
        - Preferred Location: {profile['preferred_location']}
        - Financial Status: {profile['financial_status']}
        - English Proficiency: {profile['english_proficiency']}
        - Career Goals: {profile['career_goal']}
        - Study Type Preference: {profile['preferred_study_type']}
        - Test Scores: {profile['gmat_sat_score']}
        - Extracurriculars: {profile['extra_curriculars']}
        
        Provide one detailed recommendation matching this profile.
        """
        
        # Stream the response using server-sent events (SSE)
        def generate():
            try:
                response = model.generate_content(prompt, stream=True)
                for chunk in response:
                    yield f"data: {chunk.text}\n\n"
            except ServiceUnavailable as e:
                error_message = "The model is overloaded. Please try again later."
                yield f"data: {json.dumps({'error': error_message})}\n\n"
            except Exception as e:
                error_message = f"Error generating recommendation: {str(e)}"
                yield f"data: {json.dumps({'error': error_message})}\n\n"
            finally:
                yield "data: [DONE]\n\n"
        
        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as e:
        print(f"Error generating recommendation: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()

if __name__ == '__main__':
    app.run(debug=True, threaded=True)