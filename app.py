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

# Enhanced Instruction for Gemini AI
instruction = """
You are an expert U.S. educational advisor specializing in Computer Science programs. 
When given a student profile, provide a detailed university recommendation that closely matches:
- The student's academic qualifications (CGPA, test scores)
- Field of interest (Computer Science)
- Preferred location (California)
- Financial needs (scholarship requirements)
- Career goals

For the recommended university, provide ALL of these details in STRICT JSON format:
{
  "name": "University Name",
  "type": "Public/Private",
  "location": "City, State",
  "ranking": "National/Regional ranking",
  "programs": ["Computer Science Program 1", "Program 2", "Program 3"],
  "admission_rate": "XX%",
  "avg_scores": "Average SAT/ACT scores",
  "deadlines": {
    "regular": "MM/DD/YYYY",
    "early": "MM/DD/YYYY (if applicable)"
  },
  "website": "https://university.edu",
  "contact": {
    "phone": "XXX-XXX-XXXX",
    "email": "admissions@university.edu"
  },
  "match_reasons": [
    "Reason 1: How it matches the student's CGPA",
    "Reason 2: How it matches the preferred location",
    "Reason 3: Special CS programs matching interests",
    "Reason 4: Scholarship opportunities if needed"
  ],
  "similar_universities": [
    {"name": "Similar University 1", "location": "City, State"},
    {"name": "Similar University 2", "location": "City, State"}
  ]
}

IMPORTANT:
1. MUST include at least one California university
2. MUST return ONLY the JSON object, no additional text
3. MUST validate the JSON structure before returning
4. MUST include all specified fields
5. If no perfect match exists, recommend the closest alternatives
"""

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')

# Instantiate the Gemini model
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=instruction,
    generation_config={
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
        "max_output_tokens": 1000,
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
        3. Match the student's CGPA ({profile['cgpa']})
        4. Include similar alternatives if perfect match isn't available
        5. Provide detailed match reasons
        6. Return ONLY valid JSON with all required fields
        """
        
        # Generate and validate the response
        response = model.generate_content(prompt)
        recommendation = response.text
        
        # Clean the response to extract just the JSON
        try:
            # Remove markdown code blocks if present
            if recommendation.startswith('```json'):
                recommendation = recommendation[7:-3]  # Remove ```json and ```
            elif recommendation.startswith('```'):
                recommendation = recommendation[3:-3]  # Remove ``` and ```
            
            rec_data = json.loads(recommendation)
            
            # Validate required fields
            required_fields = ['name', 'type', 'location', 'programs', 'match_reasons']
            for field in required_fields:
                if field not in rec_data:
                    raise ValueError(f"Missing required field: {field}")
            
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
            
        except json.JSONDecodeError as e:
            return jsonify({
                'error': 'Invalid JSON response from AI',
                'response': recommendation,
                'message': str(e)
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