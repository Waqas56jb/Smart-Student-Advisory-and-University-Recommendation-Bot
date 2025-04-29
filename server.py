Deploying Flask Smart Student Advisory Bot on Azure VM (Free Tier)
This guide continues from your current state (repository cloned at /home/azureuser/flask-chatbot-app, virtual environment created) to deploy your Flask-based "Smart Student Advisory and University Recommendation Bot" (https://github.com/Waqas56jb/Smart-Student-Advisory-and-University-Recommendation-Bot.git) on an Azure Ubuntu 24.04 VM (4.247.150.40). It integrates Google Gemini AI for university recommendations with the edupath_auth database (password_resets, users, studentprofile), makes the app publicly accessible, secures it with Cloudflare, and completes Steps 6–10 of Cloud Computing Assignment 4.

Step 6: Upload Web Application Files and Configure Web Server (10 Points)
Objective: Configure the Flask app and serve it with Gunicorn.

Action:
Status: Repository cloned, virtual environment created.
Steps:
Activate the virtual environment (if not already done):source venv/bin/activate


Install dependencies:pip install flask python-dotenv google-generativeai googletrans==3.1.0a0 pyttsx3 mysql-connector-python gunicorn Werkzeug


Secure the .env file (as above).
Update app.py for the VM:
Disable pyttsx3 to avoid audio issues on the headless VM.
Update database defaults to match .env.
Use your provided app.py with modifications:import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, send_from_directory, Response
import google.generativeai as genai
from googletrans import Translator
import json
from pathlib import Path
import mysql.connector
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from google.api_core.exceptions import ServiceUnavailable

# Load environment variables
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in .env file.")

# Configure Gemini API
genai.configure(api_key=api_key)

# Initialize translator
translator = Translator()

# Supported languages
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
do not answer anything else Educational institue admissions for school collages universities strickly say sorry just universities related questions i deal.
You are an expert U.S. educational advisor that provides personalized university recommendations based on student profiles.

When given a student profile, your task is to provide:

1. **One university recommendation** that closely aligns with the student's interests, qualifications, career goals, and preferences.

2. The recommendation must be **clearly and attractively formatted** in a human-readable layout, using **bold section headers** and organized details. Your response should not contain any JSON, code, or raw data structures.

For the university, include:

**🏫 University Name:** Full name along with classification (Public/Private)  
**📍 Location:** City and State  
**⭐ Ranking:** National or Global ranking (if notable)  
**🎓 Top Relevant Programs:** List of 3 programs aligned with the student's interests  
**📊 Admission Rate:** Percentage of students accepted  
**📈 Average Test Scores:** SAT, ACT, or GPA expectations (if available)  
**📅 Application Deadlines:** Mention both Regular and Early deadlines (if applicable)  
**🔗 Website:** Official university website  
**📞 Contact Information:** Phone and email address of the admissions office  
**💡 Why This is a Good Match:** A few bullet points explaining how the university aligns with the student's profile

✅ Format with good spacing, clear line breaks, and clean presentation.  
❌ Do **not** use JSON, tables, code formatting, or technical syntax.
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

# Database Connection
def get_db_connection():
    try:
        db = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '3306')),
            user=os.getenv('DB_USER', 'edupath_user'),
            password=os.getenv('DB_PASSWORD', 'EduPathPass123!'),
            database=os.getenv('DB_NAME', 'edupath_auth')
        )
        print("✅ Database connection established")
        return db
    except mysql.connector.Error as err:
        print(f"❌ Database connection error: {err}")
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

# Routes
@app.route('/')
def home():
    return render_template('landingpage.html', languages=LANGUAGES)

@app.route('/chat')
def chat_page():
    return render_template('chatbot.html')

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
    return jsonify({'status': 'error', 'message': 'Text-to-speech disabled on VM'})

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
def download_file():
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
        cursor.execute('SELECT email FROM users WHERE email = %s', (email,))
        if cursor.fetchone():
            return jsonify({'message': 'Email already exists'}), 400

        hashed_password = generate_password_hash(password)
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
        cursor.execute('SELECT email FROM users WHERE email = %s', (email,))
        if not cursor.fetchone():
            return jsonify({'message': 'No account found with this email'}), 404
        
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
        cursor.execute('SELECT email FROM users WHERE email = %s', (email,))
        if not cursor.fetchone():
            return jsonify({'message': 'No account found with this email'}), 404

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
            data = request.get_json()
            scholarshipneed = data.get('scholarshipneed', 'no') == 'yes'
            db = get_db_connection()
            if not db:
                return jsonify({'message': 'Database connection failed'}), 500
            cursor = db.cursor()
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
    app.run(debug=True, host='0.0.0.0', port=5000)


Save:nano app.py

Paste the code, save, and exit.


Test the app:source venv/bin/activate
gunicorn --bind 0.0.0.0:5000 app:app

Test locally:curl http://localhost:5000

Test signup:curl -X POST -H "Content-Type: application/json" -d '{"username":"testuser","email":"test@example.com","password":"Test123!","confirmPassword":"Test123!"}' http://localhost:5000/signup

Test profile creation:curl -X POST -H "Content-Type: application/json" -d '{"name":"Jane Doe","age":17,"class":"11th","cgpa":3.8,"interest":"AI","scholarshipneed":"yes","state":"New York","career_goal":"Data Scientist"}' http://localhost:5000/profile

Test recommendation:curl http://localhost:5000/generate-recommendations?profile_id=1

Stop Gunicorn (Ctrl+C).




Task:
Verify the app serves the landing page, handles signup/login, stores profiles, and generates Gemini AI recommendations.


Screenshot: Capture pip install, .env (redact sensitive data), curl outputs, and browser access to http://localhost:5000.


Step 7: Configure the Database to Work with the Web Application (10 Points)
Objective: Ensure Flask connects to edupath_auth and Gemini AI uses studentprofile.

Action:
Verify app.py:
Database connection:db = mysql.connector.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    port=int(os.getenv('DB_PORT', '3306')),
    user=os.getenv('DB_USER', 'edupath_user'),
    password=os.getenv('DB_PASSWORD', 'EduPathPass123!'),
    database=os.getenv('DB_NAME', 'edupath_auth')
)


Gemini AI uses studentprofile in /generate-recommendations.


Test:
Run the app:source venv/bin/activate
gunicorn --bind 0.0.0.0:5000 app:app


Test authentication:curl -X POST -H "Content-Type: application/json" -d '{"email":"test@example.com","password":"Test123!"}' http://localhost:5000/login


Test profile creation (again, if needed):curl -X POST -H "Content-Type: application/json" -d '{"name":"John Doe","age":18,"class":"12th","cgpa":3.5,"interest":"Computer Science","scholarshipneed":"no","state":"California","career_goal":"Software Engineer"}' http://localhost:5000/profile


Test recommendation:curl http://localhost:5000/generate-recommendations?profile_id=2


Verify database:sudo mysql -u root -p -e "SELECT * FROM edupath_auth.studentprofile;"






Task:
Confirm authentication, profile storage, and Gemini AI recommendations work.


Screenshot: Capture app.py (database and recommendation sections), curl responses, and studentprofile table contents.


Step 8: Configure Public IP and Firewall Rules (10 Points)
Objective: Make the app accessible via 4.247.150.40.

Action:
Azure Firewall:
In Azure Portal:
Go to Virtual Machines > mydynamicweb > Networking.
Add inbound rule:
Source: Any
Destination: Any
Service: Custom
Destination Port Ranges: 5000
Protocol: TCP
Action: Allow
Priority: 100
Name: Allow-Web-5000


Save.




VM Firewall (UFW):sudo apt install -y ufw
sudo ufw allow 5000/tcp
sudo ufw allow 22/tcp
sudo ufw enable
sudo ufw status


Test:
Run the app:source venv/bin/activate
gunicorn --bind 0.0.0.0:5000 app:app


Access http://4.247.150.40:5000 in a browser.
Test signup, login, profile creation, and recommendations via the UI.




Task:
Ensure public access to all features.


Screenshot: Capture Azure networking rules, UFW status, and browser access to http://4.247.150.40:5000.


Step 9: Configure Cloudflare Proxy for DDoS Protection (10 Points)
Objective: Protect with Cloudflare.

Action:
Cloudflare Setup:
Sign up at Cloudflare.
Add a site (use a placeholder or free domain from GitHub Student Developer Pack, e.g., .tech domain).


Configure Proxy:
DNS > Add Record:
Type: A
Name: @ or www
IPv4 Address: 4.247.150.40
Proxy Status: Proxied


Update nameservers (if using a domain).
Enable DDoS:
Security > **SettingsVV > Enable DDoS Protection.
Set Security Level to Medium.




Test:
Access http://4.247.150.40:5000 or http://yourdomain.com:5000.
Check for CF-RAY header in browser dev tools.




Task:
Confirm Cloudflare proxies traffic.


Screenshot: Capture Cloudflare DNS, DDoS settings, and browser access.


Step 10: Configure HTTPS with Cloudflare (10 Points)
Objective: Enable HTTPS.

Action:
Enable HTTPS:
SSL/TLS > Overview > Set Flexible mode.
Enable Always Use HTTPS.
SSL/TLS > Edge Certificates > Verify free SSL certificate.


Test:
Access https://4.247.150.40:5000 or https://yourdomain.com.
Confirm padlock icon in browser.




Task:
Ensure HTTPS works.


Screenshot: Capture Cloudflare SSL settings and browser HTTPS access.


Optional: Set Up a Domain Name (Bonus)

Action:
Use GitHub Student Developer Pack for a free domain (e.g., Namecheap).
Configure DNS in Cloudflare to point to 4.247.150.40.


Screenshot: Include domain setup if completed.


Submission Guidelines

PDF Report:
Name: f21xxxx_A3_CloudComputing.pdf (replace f21xxxx with your ID).
Content:
Detail Steps 6–10 with code snippets (e.g., app.py, .env structure, MySQL queries).
Screenshots (GitHub repo, Azure Portal, VM terminal, UI for signup/login/recommendations, Cloudflare settings, MySQL tables).
Redact sensitive data (e.g., GOOGLE_API_KEY, DB_PASSWORD).


Do not zip.


Bonus (30 Marks):
Write a blog on Medium about the deployment, highlighting Gemini AI and edupath_auth.
Share on LinkedIn.
Include links in PDF.


Shut Down:
Delete resources to avoid charges:az group delete --name <your-resource-group> --no-wait

Find <your-resource-group> in Azure Portal (Resource Groups).




Notes and Troubleshooting

Gemini AI:
Generate a new GOOGLE_API_KEY at https://makersuite.google.com/ and update .env.
Test the API locally:import google.generativeai as genai
genai.configure(api_key="your_new_google_api_key")
model = genai.GenerativeModel("gemini-1.5-flash")
response = model.generate_content("Test university recommendation")
print(response.text)


Monitor API usage to stay within Google’s free tier (if applicable).


Free Tier:
Monitor VM usage in Azure (Cost Management) to stay within 750 hours.
MySQL on the VM avoids managed database costs.


Security:
Ensure .env is removed from GitHub:git rm .env
git commit -m "Remove .env for security"
git push origin main


Add .env to .gitignore.


Text-to-Speech:
The /speak endpoint is disabled. If needed, install espeak and revert to the original endpoint, but test thoroughly.


Troubleshooting:
App Fails: Check Gunicorn logs:gunicorn --bind 0.0.0.0:5000 app:app --log-level debug


Database Errors: Verify credentials:sudo mysql -u edupath_user -pEduPathPass123! -e "SELECT * FROM edupath_auth.studentprofile;"


Gemini Errors: Ensure the API key is valid and test as above.
Public Access Fails: Check port 5000:sudo ufw status
netstat -tuln | grep 5000




Viva Preparation:
Demo signup, login, profile creation, and Gemini AI recommendations.
Explain edupath_auth tables, Gemini AI integration, and Cloudflare setup.
Discuss security measures (e.g., removing .env) and VM challenges.




Expected Outcome
A secure Flask-based Smart Student Advisory Bot on an Azure VM, accessible via https://4.247.150.40:5000, using Gemini AI for university recommendations based on studentprofile data, with authentication and profile management, protected by Cloudflare, and documented in a PDF report.

Final Steps

Test Thoroughly: Verify signup, login, profile creation, and recommendations via https://4.247.150.40:5000.
Secure Repo: Remove .env from GitHub and update the API key.
Document: Compile your PDF with screenshots and code snippets.
Submit: Upload the PDF as per assignment instructions.
Clean Up: Delete the VM:az group delete --name <your-resource-group> --no-wait



If you hit errors (e.g., Gemini API issues, database connection failures), share the error messages, and I’ll assist. Best of luck with your assignment, and I hope your bot impresses in the viva!
