from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import os
import mysql.connector
import json
import google.generativeai as genai
from google.api_core import exceptions

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configure Google Generative AI API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro')

# Database configuration using environment variables
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}

def get_db_connection():
    """Establish a connection to the MySQL database."""
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as e:
        print(f"Database connection failed: {e}")
        return None

@app.route('/profile', methods=['POST'])
def save_profile():
    """Save or update a student profile in the database."""
    data = request.get_json()
    required_fields = ['name', 'age', 'class', 'state']
    
    # Validate required fields
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400

    db = get_db_connection()
    if not db:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = db.cursor()
        query = """
        INSERT INTO studentprofile (name, age, class, cgpa, interest, scholarshipneed, state, 
            preferred_location, financial_status, english_proficiency, career_goal, 
            gmat_sat_score, extra_curriculars)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name=VALUES(name), age=VALUES(age), class=VALUES(class), cgpa=VALUES(cgpa),
            interest=VALUES(interest), scholarshipneed=VALUES(scholarshipneed), state=VALUES(state),
            preferred_location=VALUES(preferred_location), financial_status=VALUES(financial_status),
            english_proficiency=VALUES(english_proficiency), career_goal=VALUES(career_goal),
            gmat_sat_score=VALUES(gmat_sat_score), extra_curriculars=VALUES(extra_curriculars)
        """
        values = (
            data.get('name'), data.get('age'), data.get('class'), data.get('cgpa'),
            data.get('interest'), data.get('scholarshipneed', False), data.get('state'),
            data.get('preferred_location'), data.get('financial_status'),
            data.get('english_proficiency'), data.get('career_goal'),
            data.get('gmat_sat_score'), data.get('extra_curriculars')
        )
        cursor.execute(query, values)
        db.commit()
        
        # Retrieve the student_id
        cursor.execute("SELECT LAST_INSERT_ID()")
        student_id = cursor.fetchone()[0]
        if not student_id:
            cursor.execute("SELECT student_id FROM studentprofile WHERE name = %s", (data['name'],))
            student_id = cursor.fetchone()[0]
        
        return jsonify({
            'message': 'Profile saved',
            'student_id': student_id,
            'redirect': f'/recommendations?student_id={student_id}'
        })
    except Exception as e:
        print(f"Error saving profile: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        db.close()

@app.route('/generate-recommendation', methods=['POST'])
def generate_recommendation():
    """Generate a university recommendation using Google Generative AI."""
    data = request.get_json()
    student_id = data.get('student_id')
    
    if not student_id:
        return jsonify({'error': 'Student ID is required'}), 400
    
    db = get_db_connection()
    if not db:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM studentprofile WHERE student_id = %s", (student_id,))
        profile = cursor.fetchone()
        
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404
        
        # Prompt for the AI with safe handling of missing fields
        prompt = f"""
        You are an expert U.S. educational advisor providing personalized university recommendations.
        Given this student profile:
        - Name: {profile.get('name', 'Not specified')}
        - Age: {profile.get('age', 'Not specified')}
        - Current Class: {profile.get('class', 'Not specified')}
        - CGPA: {profile.get('cgpa', 'Not specified')}
        - Field of Interest: {profile.get('interest', 'Not specified')}
        - Needs Scholarship: {'Yes' if profile.get('scholarshipneed') else 'No'}
        - State: {profile.get('state', 'Not specified')}
        - Preferred Location: {profile.get('preferred_location', 'Not specified')}
        - Financial Status: {profile.get('financial_status', 'Not specified')}
        - English Proficiency: {profile.get('english_proficiency', 'Not specified')}
        - Career Goals: {profile.get('career_goal', 'Not specified')}
        - Test Scores: {profile.get('gmat_sat_score', 'Not specified')}
        - Extracurriculars: {profile.get('extra_curriculars', 'Not specified')}

        Provide one university recommendation with:
        - Name and classification (Public/Private)
        - Location (City, State)
        - Ranking (if notable)
        - Top 3 relevant programs
        - Admission rate and average test scores
        - Application deadlines
        - Website URL
        - Contact information
        - Special features matching the profile

        Format the response as a valid JSON object:
        {{
          "name": "University Name",
          "type": "Public/Private",
          "location": "City, State",
          "ranking": "Ranking info",
          "programs": ["Program 1", "Program 2", "Program 3"],
          "admission_rate": "XX%",
          "avg_scores": "SAT/ACT ranges",
          "deadlines": {{
            "regular": "MM/DD",
            "early": "MM/DD (if applicable)"
          }},
          "website": "https://university.edu",
          "contact": {{
            "phone": "XXX-XXX-XXXX",
            "email": "admissions@university.edu"
          }},
          "match_reasons": ["Reason 1", "Reason 2", "Reason 3"]
        }}
        Ensure the response is a valid JSON object and nothing else. Do not include additional text.
        """
        
        try:
            response = model.generate_content(prompt)
            recommendation = json.loads(response.text.strip())
            return jsonify(recommendation)
        except json.JSONDecodeError:
            print("Invalid JSON from AI:", response.text)
            return jsonify({'error': 'Invalid response format from AI'}), 500
        except exceptions.ServiceUnavailable:
            return jsonify({'error': 'The model is overloaded. Please try again later.'}), 503
        except Exception as e:
            print(f"Error generating recommendation: {e}")
            return jsonify({'error': str(e)}), 500
    
    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        db.close()

@app.route('/recommendations')
def recommendations_page():
    """Render the recommendations page with student profile."""
    student_id = request.args.get('student_id')
    if not student_id:
        return "No student ID provided", 400
    
    db = get_db_connection()
    if not db:
        return "Database connection failed", 500
    
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM studentprofile WHERE student_id = %s", (student_id,))
        profile = cursor.fetchone()
        return render_template('recommendation.html', profile=profile)
    except Exception as e:
        print(f"Error fetching profile: {e}")
        return "Error loading recommendations", 500
    finally:
        cursor.close()
        db.close()

if __name__ == '__main__':
    app.run(debug=True)