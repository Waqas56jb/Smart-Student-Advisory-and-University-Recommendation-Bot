import mysql.connector
from datetime import datetime, timedelta

# ─── Establish Connection ─────────────────────────────────────────────────────
connection = mysql.connector.connect(
    host="localhost",
    port=3307,
    user="root",
    password="",         # XAMPP default
    database="edupath_auth"
)
cursor = connection.cursor()

try:
    # ─── 1) Insert into users ──────────────────────────────────────────────────
    users_sql = """
        INSERT INTO users (username, email, password)
        VALUES (%s, %s, %s)
    """
    users_data = (
        "johndoe", 
        "john.doe@example.com", 
        "supersecret"   # in real apps, hash this!
    )
    cursor.execute(users_sql, users_data)
    print(f"Inserted into users, id={cursor.lastrowid}")

    # ─── 2) Insert into password_resets ────────────────────────────────────────
    resets_sql = """
        INSERT INTO password_resets (email, token, expires_at)
        VALUES (%s, %s, %s)
    """
    expires = datetime.now() + timedelta(hours=2)
    resets_data = (
        "john.doe@example.com",
        "reset-token-123",
        expires
    )
    cursor.execute(resets_sql, resets_data)
    print(f"Inserted into password_resets, id={cursor.lastrowid}")

    # ─── 3) Insert into studentprofile ────────────────────────────────────────
    profile_sql = """
        INSERT INTO studentprofile (
            name, age, class, cgpa, interest, scholarshipneed,
            hobbies, state, email, phone, preferred_location,
            financial_status, parents_qualification, english_proficiency,
            extra_curriculars, career_goal, preferred_study_type,
            gmat_sat_score, past_achievements
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    profile_data = (
        "John Doe",          # name
        20,                  # age
        "Sophomore",         # class
        3.5,                 # cgpa
        "Computer Science",  # interest
        False,               # scholarshipneed
        "Reading, Soccer",   # hobbies
        "California",        # state
        "john.doe@uni.edu",  # email
        "555-1234",          # phone
        "Los Angeles",       # preferred_location
        "middle",            # financial_status
        "bachelor",          # parents_qualification
        "advanced",          # english_proficiency
        "Chess Club",        # extra_curriculars
        "Software Engineer", # career_goal
        "on_campus",         # preferred_study_type
        "1500",              # gmat_sat_score
        "Dean's List 2024"   # past_achievements
    )
    cursor.execute(profile_sql, profile_data)
    print(f"Inserted into studentprofile, id={cursor.lastrowid}")

    # ─── Commit all ─────────────────────────────────────────────────────────────
    connection.commit()
    print("✅ All inserts committed.")

except mysql.connector.Error as err:
    print("❌ Error during insert:", err)
    connection.rollback()

finally:
    cursor.close()
    connection.close()
    print("🔌 Connection closed.")
