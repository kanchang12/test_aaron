import sqlite3
import os

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mr_training.db')

def create_tables():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            persona_details TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            details TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            doctor_id INTEGER,
            medicine_id INTEGER,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (candidate_id) REFERENCES candidates (id),
            FOREIGN KEY (doctor_id) REFERENCES doctors (id),
            FOREIGN KEY (medicine_id) REFERENCES medicines (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER,
            speaker TEXT NOT NULL,
            text TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assignment_id) REFERENCES assignments (id)
        )
    ''')

    conn.commit()
    conn.close()

def insert_initial_data():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Add manager
    cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ('manager', 'manager123', 'manager'))
    
    # Add candidate
    cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ('candidate', 'candidate123', 'candidate'))
    user_id = cursor.lastrowid
    cursor.execute("INSERT INTO candidates (name, user_id) VALUES (?, ?)", ('Test Candidate', user_id))

    # Add doctors
    doctors = [
        ('Dr. Sharma', 'A very busy and slightly rude cardiologist from a top hospital in Delhi. He is always short on time and expects the MR to be very precise and quick.'),
        ('Dr. Gupta', 'A senior general physician in Mumbai who is very skeptical about new medicines. He has been practicing for 30 years and trusts only well-established drugs.'),
        ('Dr. Reddy', 'A young and enthusiastic pediatrician from Bangalore. She is open to new ideas and technologies but is very particular about the safety and efficacy of medicines for children.')
    ]
    cursor.executemany("INSERT INTO doctors (name, persona_details) VALUES (?, ?)", doctors)

    # Add medicines
    medicines = [
        ('CardioWell', 'A new generation beta-blocker for hypertension with fewer side effects.'),
        ('NeuroFast', 'An advanced solution for neuropathic pain, clinically proven to be more effective than existing options.'),
        ('PediaSure', 'A nutritional supplement for children that aids in growth and development.'),
        ('GastroCare', 'A proton-pump inhibitor for acidity and GERD with a longer-lasting effect.'),
        ('OrthoFlex', 'A non-steroidal anti-inflammatory drug for joint pain with a better safety profile.')
    ]
    cursor.executemany("INSERT INTO medicines (name, details) VALUES (?, ?)", medicines)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    create_tables()
    insert_initial_data()
    print("Database initialized successfully.")
