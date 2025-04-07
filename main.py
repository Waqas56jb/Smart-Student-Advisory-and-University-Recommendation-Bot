import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, send_from_directory
import google.generativeai as genai
import pyttsx3
from googletrans import Translator
import json
from pathlib import Path

# Load environment variables
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in .env file")

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

# Instruction for Gemini AI (same as before)
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
        # Set voice properties based on language
        if lang == 'en':
            tts_engine.setProperty('voice', voices[0].id)  # English voice
        elif lang == 'es':
            tts_engine.setProperty('voice', 'spanish')  # Spanish voice
        # Add more language mappings as needed
        
        tts_engine.say(text)
        tts_engine.runAndWait()
    except Exception as e:
        print(f"TTS error: {e}")

@app.route('/')
def index():
    return render_template('landingpage.html', languages=LANGUAGES)

@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    user_input = data.get('query', '').strip()
    input_lang = data.get('input_lang', 'en')
    output_lang = data.get('output_lang', 'en')
    
    if not user_input:
        return jsonify({'response': "⚠️ Please ask a question.", 'lang': output_lang})

    try:
        # Translate input to English if needed
        if input_lang != 'en':
            user_input = translate_text(user_input, 'en')
        
        # Get response from Gemini
        response = model.generate_content(user_input)
        text = response.text.strip() if response.text else "⚠️ No response received from the model."
        
        # Translate response to target language if needed
        if output_lang != 'en':
            text = translate_text(text, output_lang)
        
        return jsonify({
            'response': text,
            'lang': output_lang
        })
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        if output_lang != 'en':
            error_msg = translate_text(error_msg, output_lang)
        return jsonify({'response': error_msg, 'lang': output_lang})

@app.route('/speak', methods=['POST'])
def speak():
    data = request.get_json()
    text = data.get('text', '')
    lang = data.get('lang', 'en')
    
    if text:
        text_to_speech(text, lang)
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'No text provided'})

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    text = data.get('text', '')
    lang = data.get('lang', 'en')
    
    if not text:
        return jsonify({'status': 'error', 'message': 'No text to download'})
    
    filename = f"response_{lang}.txt"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
        return jsonify({
            'status': 'success',
            'url': f'/download/{filename}'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, threaded=True)