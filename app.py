import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, redirect
import google.generativeai as genai
import mysql.connector
import json
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in .env file")

# Configure Gemini API
genai.configure(api_key=api_key)

# Instruction for Gemini AI
instruction = """
You are an expert U.S. educational advisor that provides personalized university recommendations based on student profiles. 
Return a JSON object with these fields:
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
Return only the JSON object, nothing else.
"""

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')

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
        return mysql.connector.connect(
            host=os.getenv('DB_HOST', '127.0.0.1'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', '1234'),
            database=os.getenv('DB_NAME', 'edupath_auth')
        )
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

# Routes
@app.route('/')
def home():
    return render_template('profile.html')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if request.method == 'POST':
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
            
            student_id = cursor.lastrowid
            db.commit()
            
            return jsonify({
                'message': 'Profile saved successfully',
                'redirect': f'/recommendation?student_id={student_id}'
            }), 200
            
        except Exception as e:
            return jsonify({'message': f'Error: {str(e)}'}), 500
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'db' in locals():
                db.close()
    return render_template('profile.html')

@app.route('/recommendation')
def recommendation():
    student_id = request.args.get('student_id')
    if not student_id:
        return redirect('/')
    
    db = get_db_connection()
    if not db:
        return render_template('recommendation.html', error="Database connection failed")
    
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM studentprofile WHERE student_id = %s", (student_id,))
        profile = cursor.fetchone()
        
        if not profile:
            return render_template('recommendation.html', error="No profile found")
        
        return render_template('recommendation.html', profile=profile)
    except Exception as e:
        return render_template('recommendation.html', error=str(e))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()

@app.route('/generate-recommendation', methods=['POST'])
def generate_recommendation():
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        
        if not student_id:
            return jsonify({'error': 'Student ID is required'}), 400
        
        db = get_db_connection()
        if not db:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM studentprofile WHERE student_id = %s", (student_id,))
        profile = cursor.fetchone()
        
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404
        
        # Enhanced prompt with specific guidance for Gemini
        prompt = f"""
        Generate a detailed university recommendation for this Computer Science student:
        
        Student Profile:
        - Name: {profile['name']}
        - CGPA: {profile['cgpa']}
        - Field: Computer Science
        - Location Preference: {profile['preferred_location']}
        - Needs Scholarship: {'Yes' if profile['scholarshipneed'] else 'No'}
        - Career Goals: {profile['career_goal']}
        - Test Scores: {profile['gmat_sat_score']}
        
        Requirements:
        1. MUST recommend at least one California university
        2. Focus on Computer Science programs
        3. Match the student's CGPA (3.0)
        4. Include similar alternatives if perfect match isn't available
        5. Provide detailed match reasons
        """
        
        response = model.generate_content(prompt)
        recommendation = response.text
        
        try:
            # Parse and validate the recommendation
            rec_data = json.loads(recommendation)
            if not rec_data.get('name'):
                raise ValueError("Invalid recommendation format")
            
            # Ensure at least one California university is included
            if "california" not in rec_data.get('location', '').lower():
                if 'similar_universities' in rec_data:
                    for uni in rec_data['similar_universities']:
                        if "california" in uni.get('location', '').lower():
                            rec_data['location'] = uni['location']
                            rec_data['name'] = uni['name']
                            rec_data['match_reasons'].append("Included California alternative based on your preference")
                            break
            
            return jsonify(rec_data)
            
        except json.JSONDecodeError:
            # If response isn't JSON, return it as text with error
            return jsonify({
                'error': 'Invalid response format from AI',
                'response': recommendation
            }), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()

if __name__ == '__main__':
    app.run(debug=True)