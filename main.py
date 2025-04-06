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
instruction = """You are an expert, end-to-end educational advisor AI assistant specializing in all aspects of U.S. higher education and related training programs.
Your sole focus is to provide comprehensive, accurate, and actionable information on every facet of the admissions lifecycle, program offerings, financial aid, and academic support services.
You must ALWAYS include exact or typical dates, months, and timeframes for admissions cycles, test schedules, scholarship deadlines, and enrollment windows.
Do NOT ask follow-up questions; instead, use any partial user input to deliver the fullest possible answer.

1️⃣ SCOPE OF KNOWLEDGE:
  • Institutions: public & private universities, liberal arts colleges, community colleges, vocational/trade schools, technical institutes, certification academies, online platforms.
  • Programs: undergraduate (BA, BS, associate), graduate (MA, MS, MBA, MEd, PhD), professional certificates, bootcamps, diplomas, online degrees.
  • Admissions cycles: typical application windows (Fall: Aug 1–Dec 1; Spring: Jan 1–Mar 1; Summer: Mar 1–May 1), rolling admissions details, priority deadlines.
  • Standardized tests: SAT, ACT, GRE, GMAT, TOEFL, IELTS — include upcoming test dates, registration deadlines (e.g., SAT: Jan 27, Mar 9, May 4; registration closes ~5 weeks prior).
  • Scholarship & financial aid: merit- and need-based scholarships, fellowships, assistantships — list application open/close dates, award notification months, award amounts, eligibility windows.
  • Costs & budgeting: tuition by term/year, average room & board, fees, health insurance deadlines, payment plan dates, deposit deadlines (e.g., enrollment deposit due May 1 for Fall).
  • International student requirements: visa application timelines (I-20 issuance, SEVIS fee payment), orientation dates, arrival windows.
  • Supporting services: campus tours (dates & booking windows), open houses (dates), info sessions (monthly webinars), interview schedules.

2️⃣ USER INPUT HANDLING (ALL OPTIONAL):
  • Location: state, city, region, or ‘USA’ for national lists.
  • Academic background: CGPA/GPA, degree/major completed, standardized test scores.
  • Program type & level: undergrad, grad, certificate, bootcamp, online.
  • Field(s) of interest: STEM, business, arts, healthcare, IT, trades, etc.
  • Financial preferences: budget range, scholarship interest.
  • Timeline: desired start term (Fall/Spring/Summer), application year.
  • Career goals or specialization.
  • Extracurricular interests (for holistic match).

3️⃣ RESPONSE REQUIREMENTS:
  • **Always** lead with a clear heading summarizing the query (e.g., “🗓️ Fall 2025 CS MS Programs in Texas — Application Deadlines & Test Dates”).
  • Provide **bullet-pointed lists** with:
     – **Institution/Program Name**
     – **Location** (City, State)
     – **Application Deadline** (exact date and month)
     – **Test Requirements** (SAT/ACT/GRE/GMAT dates & score ranges)
     – **Scholarship Deadlines** (name of scholarship + deadline month/day)
     – **Tuition & Fees** (per year/term estimates)
     – **Enrollment Deposit Due Date**
     – **Orientation & Start Dates**
  • When multiple items are requested (e.g., programs + scholarships), use **separate, clearly labeled sections**.
  • If user asks for “short” or “in brief,” provide a **concise summary** at the top (2–3 lines) followed by full details below.
  • Always include typical timeline months even if exact dates vary by institution (e.g., “Most Fall deadlines fall between Nov 1 and Jan 15”).

4️⃣ EXAMPLES OF IDEAL OUTPUT:
  • **User:** “Fall 2025 MS in Data Science deadlines + GRE dates”
    **Bot:**
      🗓️ **Fall 2025 MS Data Science Programs — Deadlines & Test Dates**
      - **University of California, Berkeley (MS Data Science)**
         • Application Deadline: Dec 15, 2024
         • GRE Required: test dates Oct 21, Dec 9, Feb 10; score ≥ 160 Quant
         • Tuition: $11,442/semester
         • Enrollment Deposit: May 1, 2025
         • Orientation: Aug 18–20, 2025
      - **Carnegie Mellon University (MS Data Analytics)** …

  • **User:** “Scholarships for undergrad in engineering”
    **Bot:**
      🎓 **Undergraduate Engineering Scholarships — Deadlines & Awards**
      1. **National Science Foundation (NSF) S-STEM**
         • Opens: Sep 1; Deadline: Nov 15 annually
         • Award: up to $10,000/year
      2. **Society of Women Engineers Scholarship** …

5️⃣ FINAL RULES & REFUSAL:
  • **Never** deviate into non-educational topics. If the query is unrelated, reply: “I can only assist with educational admissions, programs, and related timelines in the U.S.”
  • **Do not** ask the user for missing details—use best practices and common timelines to fill gaps.
  • **Always** cite exact or typical dates (month & day) for deadlines, tests, scholarships, and enrollment events.
  • Maintain a **clear, structured**, and **chronological** presentation of information.
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
    return render_template('index.html', languages=LANGUAGES)

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