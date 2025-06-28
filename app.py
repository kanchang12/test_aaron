from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
from datetime import timedelta
import sqlite3
import openai
import os
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
openai.api_key = os.getenv("OPENAI_API_KEY")

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mr_training.db')

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        
        if user:
            session.permanent = True
            session['user_id'] = user['id']
            session['role'] = user['role']
            if user['role'] == 'manager':
                return redirect(url_for('manager'))
            else:
                return redirect(url_for('candidate'))
        else:
            return render_template('login.html', error='Invalid credentials')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/manager')
def manager():
    if 'role' not in session or session['role'] != 'manager':
        return redirect(url_for('login'))
    
    conn = get_db()
    doctors = conn.execute('SELECT * FROM doctors').fetchall()
    medicines = conn.execute('SELECT * FROM medicines').fetchall()
    candidates = conn.execute('SELECT * FROM candidates').fetchall()
    assignments = conn.execute('''
        SELECT a.id, c.name as candidate_name, d.name as doctor_name, m.name as medicine_name, a.status
        FROM assignments a
        JOIN candidates c ON a.candidate_id = c.id
        JOIN doctors d ON a.doctor_id = d.id
        JOIN medicines m ON a.medicine_id = m.id
    ''').fetchall()
    conn.close()
    
    return render_template('manager.html', doctors=doctors, medicines=medicines, candidates=candidates, assignments=assignments)

@app.route('/candidate')
def candidate():
    if 'role' not in session or session['role'] != 'candidate':
        return redirect(url_for('login'))
        
    conn = get_db()
    candidate_id = conn.execute('SELECT id FROM candidates WHERE user_id = ?', (session['user_id'],)).fetchone()['id']
    assignments = conn.execute('''
        SELECT a.id, d.name as doctor_name, m.name as medicine_name, a.status
        FROM assignments a
        JOIN doctors d ON a.doctor_id = d.id
        JOIN medicines m ON a.medicine_id = m.id
        WHERE a.candidate_id = ?
    ''', (candidate_id,)).fetchall()
    conn.close()
    
    return render_template('candidate.html', assignments=assignments)

@app.route('/add_doctor', methods=['POST'])
def add_doctor():
    name = request.form['name']
    persona = request.form['persona']
    conn = get_db()
    conn.execute('INSERT INTO doctors (name, persona_details) VALUES (?, ?)', (name, persona))
    conn.commit()
    conn.close()
    return redirect(url_for('manager'))

@app.route('/add_medicine', methods=['POST'])
def add_medicine():
    name = request.form['name']
    details = request.form['details']
    conn = get_db()
    conn.execute('INSERT INTO medicines (name, details) VALUES (?, ?)', (name, details))
    conn.commit()
    conn.close()
    return redirect(url_for('manager'))

@app.route('/add_candidate', methods=['POST'])
def add_candidate():
    name = request.form['name']
    username = request.form['username']
    password = request.form['password']
    conn = get_db()
    user_id = conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', (username, password, 'candidate')).lastrowid
    conn.execute('INSERT INTO candidates (name, user_id) VALUES (?, ?)', (name, user_id))
    conn.commit()
    conn.close()
    return redirect(url_for('manager'))

@app.route('/add_assignment', methods=['POST'])
def add_assignment():
    candidate_id = request.form['candidate_id']
    doctor_id = request.form['doctor_id']
    medicine_id = request.form['medicine_id']
    conn = get_db()
    conn.execute('INSERT INTO assignments (candidate_id, doctor_id, medicine_id) VALUES (?, ?, ?)', (candidate_id, doctor_id, medicine_id))
    conn.commit()
    conn.close()
    return redirect(url_for('manager'))

@app.route('/assignment/<int:assignment_id>')
def assignment(assignment_id):
    if 'role' not in session or session['role'] != 'candidate':
        return redirect(url_for('login'))
        
    conn = get_db()
    assignment = conn.execute('SELECT * FROM assignments WHERE id = ?', (assignment_id,)).fetchone()
    doctor = conn.execute('SELECT * FROM doctors WHERE id = ?', (assignment['doctor_id'],)).fetchone()
    conn.close()
    
    return render_template('assignment.html', assignment=assignment, doctor=doctor)

@app.route('/ask_doctor', methods=['POST'])
def ask_doctor():
    user_message = request.json['message']
    doctor_persona = request.json['doctor_persona']
    assignment_id = request.json.get('assignment_id')
    
    try:
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are a doctor with the following persona: {doctor_persona}. You are talking to a medical representative."},
                {"role": "user", "content": user_message}
            ]
        )
        
        # Store conversation in database
        if assignment_id:
            conn = get_db()
            conn.execute('''
                INSERT INTO conversation_logs (assignment_id, user_message, doctor_response, timestamp)
                VALUES (?, ?, ?, datetime('now'))
            ''', (assignment_id, user_message, response.choices[0].message.content))
            conn.commit()
            conn.close()
        
        return jsonify({'reply': response.choices[0].message.content})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/synthesize', methods=['POST'])
def synthesize():
    text = request.json['text']
    
    try:
        # ElevenLabs TTS API
        ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
        
        if not ELEVENLABS_API_KEY:
            return jsonify({'error': 'ElevenLabs API key not configured'})
            
        # Use a professional voice ID (Rachel - calm, professional female voice)
        voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice
        
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_API_KEY
        }
        
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }
        
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200:
            return Response(response.content, mimetype="audio/mpeg")
        else:
            return jsonify({'error': f'ElevenLabs API error: {response.status_code}'})
            
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/view_assignment/<int:assignment_id>')
def view_assignment(assignment_id):
    if 'role' not in session or session['role'] != 'manager':
        return redirect(url_for('login'))
    
    conn = get_db()
    
    # Get assignment details
    assignment = conn.execute('''
        SELECT a.*, c.name as candidate_name, d.name as doctor_name, d.persona_details,
               m.name as medicine_name, m.details as medicine_details
        FROM assignments a
        JOIN candidates c ON a.candidate_id = c.id
        JOIN doctors d ON a.doctor_id = d.id
        JOIN medicines m ON a.medicine_id = m.id
        WHERE a.id = ?
    ''', (assignment_id,)).fetchone()
    
    # Get conversation transcript
    transcript = conn.execute('''
        SELECT user_message, doctor_response, timestamp
        FROM conversation_logs
        WHERE assignment_id = ?
        ORDER BY timestamp ASC
    ''', (assignment_id,)).fetchall()
    
    # Get performance metrics
    metrics = conn.execute('''
        SELECT * FROM performance_metrics WHERE assignment_id = ?
    ''', (assignment_id,)).fetchone()
    
    conn.close()
    
    return render_template('view_assignment.html', 
                         assignment=assignment, 
                         transcript=transcript, 
                         metrics=metrics)

@app.route('/score_assignment/<int:assignment_id>', methods=['GET', 'POST'])
def score_assignment(assignment_id):
    if 'role' not in session or session['role'] != 'manager':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Save scoring
        communication_score = request.form['communication_score']
        product_knowledge_score = request.form['product_knowledge_score']
        objection_handling_score = request.form['objection_handling_score']
        overall_score = request.form['overall_score']
        strengths = request.form['strengths']
        areas_for_improvement = request.form['areas_for_improvement']
        
        conn = get_db()
        
        # Insert or update performance metrics
        conn.execute('''
            INSERT OR REPLACE INTO performance_metrics 
            (assignment_id, communication_score, product_knowledge_score, 
             objection_handling_score, overall_score, strengths, areas_for_improvement)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (assignment_id, communication_score, product_knowledge_score,
              objection_handling_score, overall_score, strengths, areas_for_improvement))
        
        # Update assignment score
        conn.execute('UPDATE assignments SET score = ? WHERE id = ?', (overall_score, assignment_id))
        
        conn.commit()
        conn.close()
        
        return redirect(url_for('view_assignment', assignment_id=assignment_id))
    
    # GET request - show scoring form
    conn = get_db()
    assignment = conn.execute('''
        SELECT a.*, c.name as candidate_name, d.name as doctor_name,
               m.name as medicine_name
        FROM assignments a
        JOIN candidates c ON a.candidate_id = c.id
        JOIN doctors d ON a.doctor_id = d.id
        JOIN medicines m ON a.medicine_id = m.id
        WHERE a.id = ?
    ''', (assignment_id,)).fetchone()
    
    # Get existing metrics if any
    metrics = conn.execute('''
        SELECT * FROM performance_metrics WHERE assignment_id = ?
    ''', (assignment_id,)).fetchone()
    
    conn.close()
    
    return render_template('score_assignment.html', assignment=assignment, metrics=metrics)

@app.route('/candidate_reports')
def candidate_reports():
    if 'role' not in session or session['role'] != 'candidate':
        return redirect(url_for('login'))
        
    conn = get_db()
    candidate_id = conn.execute('SELECT id FROM candidates WHERE user_id = ?', (session['user_id'],)).fetchone()['id']
    
    # Get completed assignments with scores
    completed_assignments = conn.execute('''
        SELECT a.id, d.name as doctor_name, m.name as medicine_name, 
               a.score, a.completed_at, pm.overall_score, pm.strengths, pm.areas_for_improvement
        FROM assignments a
        JOIN doctors d ON a.doctor_id = d.id
        JOIN medicines m ON a.medicine_id = m.id
        LEFT JOIN performance_metrics pm ON a.id = pm.assignment_id
        WHERE a.candidate_id = ? AND a.status = 'completed'
        ORDER BY a.completed_at DESC
    ''', (candidate_id,)).fetchall()
    
    conn.close()
    
    return render_template('candidate_reports.html', assignments=completed_assignments)


@app.route('/complete_interview', methods=['POST'])
def complete_interview():
    assignment_id = request.json['assignment_id']
    conn = get_db()
    conn.execute('UPDATE assignments SET status = ?, completed_at = datetime("now") WHERE id = ?', ('completed', assignment_id))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})


if __name__ == '__main__':
    app.run(debug=True)