from flask import Flask, render_template, request, redirect, session, flash, Response
import mysql.connector
import hashlib
import cv2
import os
import csv
from io import StringIO
from datetime import datetime

app = Flask(__name__)
app.secret_key = "studentportal"

# =========================
# DATABASE CONNECTION
# =========================
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Moraleda@20067",
    database="student_portal"
)

cursor = db.cursor()

# =========================
# HELPER FUNCTIONS
# =========================
def log_activity(student_id, action, details=''):
    """Log user activity to the database"""
    try:
        cursor.execute(
            "INSERT INTO activity_log (student_id, action, details, created_at) VALUES (%s, %s, %s, NOW())",
            (student_id, action, details)
        )
        db.commit()
        print(f"[{datetime.now()}] Activity logged: {student_id} - {action}")
    except Exception as e:
        print(f"Error logging activity: {e}")

# =========================
# LOGIN PAGE
# =========================
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_id = request.form['student_id']
        password = request.form['password']
        
        # Hash the password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        print(f"Attempting login for: {student_id}")
        print(f"Hashed password: {hashed_password}")

        cursor.execute(
            "SELECT * FROM students WHERE student_id=%s AND password=%s",
            (student_id, hashed_password)
        )

        user = cursor.fetchone()
        
        print(f"User found: {user}")

        if user:
            session['student_id'] = student_id
            # Log the login activity
            log_activity(student_id, 'LOGIN', 'User logged in successfully')
            flash('Login successful! Welcome back.', 'success')
            print(f"Login successful for {student_id}")
            return redirect('/dashboard')
        else:
            # Check if student exists
            cursor.execute(
                "SELECT * FROM students WHERE student_id=%s",
                (student_id,)
            )
            existing = cursor.fetchone()
            
            if existing:
                print(f"Student exists but password doesn't match")
                flash('Incorrect password! Please try again.', 'danger')
            else:
                print(f"Student doesn't exist")
                flash('Student ID not found! Please register first.', 'danger')
            
            return render_template('login.html')

    return render_template('login.html')

# =========================
# FACE LOGIN PAGE
# =========================
@app.route('/face_login')
def face_login():
    if 'student_id' in session:
        return redirect('/dashboard')
    return render_template('face_login.html')

# =========================
# FACE AUTHENTICATION
# =========================
@app.route('/face_auth')
def face_auth():
    try:
        import cv2
        import os
    except ImportError as e:
        flash(f'Required library not installed: {str(e)}', 'danger')
        return redirect('/face_login')

    if 'student_id' in session:
        return redirect('/dashboard')

    # Get student_id from session or use default
    student_id = '2025-12345'
    
    # Load the face cascade classifier
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    )

    # Initialize camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        flash('Could not access camera. Please check your camera connection.', 'danger')
        return redirect('/face_login')

    success = False
    attempts = 0
    max_attempts = 150  # Maximum attempts before timeout
    stable_frames = 0  # Count consecutive stable detections

    while attempts < max_attempts:
        ret, frame = cap.read()
        
        if not ret:
            flash('Failed to capture frame from camera.', 'danger')
            break

        # Convert to grayscale for face detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Detect faces
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(50, 50)
        )

        # Draw rectangles and check for faces
        if len(faces) > 0:
            for (x, y, w, h) in faces:
                # Draw rectangle around face
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(frame, "✅ FACE DETECTED!", (x, y-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"Face count: {len(faces)}", (x, y-40),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Count stable detections
            stable_frames += 1
            
            # If face detected for 10 consecutive frames, consider it successful
            if stable_frames >= 10:
                success = True
                cv2.putText(frame, "✅ LOGIN SUCCESSFUL!", (50, 150),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
        else:
            stable_frames = 0
            cv2.putText(frame, "❌ No face detected", (10, 150),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Show status
        cv2.putText(frame, f"Attempts: {attempts}/{max_attempts}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, "Press ESC to cancel", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, "Look at the camera", (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
        cv2.putText(frame, f"Stable frames: {stable_frames}/10", (10, 120),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        cv2.imshow("Face Login - Look at Camera", frame)

        if success:
            # Set session
            session['student_id'] = student_id
            # Log face login
            log_activity(student_id, 'FACE_LOGIN', 'User logged in via face detection')
            flash('Face authentication successful!', 'success')
            break

        if cv2.waitKey(1) == 27:  # ESC key
            flash('Face authentication cancelled.', 'info')
            break

        attempts += 1

    cap.release()
    cv2.destroyAllWindows()

    if success:
        return redirect('/dashboard')
    else:
        flash('Face not detected or timeout. Please try again.', 'danger')
        return redirect('/face_login')

# =========================
# FACE REGISTRATION
# =========================
@app.route('/register_face', methods=['GET', 'POST'])
def register_face():
    if 'student_id' not in session:
        flash('Please login first.', 'warning')
        return redirect('/')
    
    if request.method == 'POST':
        try:
            import cv2
            import os
        except ImportError:
            flash('OpenCV not installed.', 'danger')
            return redirect('/register_face')
        
        student_id = session['student_id']
        os.makedirs('faces', exist_ok=True)
        
        # Load face cascade
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            flash('Could not access camera.', 'danger')
            return redirect('/register_face')
        
        captured = False
        
        while not captured:
            ret, frame = cap.read()
            if not ret:
                break
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 5)
            
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(frame, "Press SPACE to capture", (x, y-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.putText(frame, "Position your face and press SPACE", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, "Press ESC to cancel", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, f"Faces detected: {len(faces)}", (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            
            cv2.imshow("Register Face", frame)
            
            key = cv2.waitKey(1)
            if key == 32:  # SPACE
                if len(faces) > 0:
                    face_path = f"faces/{student_id}.jpg"
                    cv2.imwrite(face_path, frame)
                    log_activity(student_id, 'REGISTER_FACE', 'Face registered successfully')
                    flash('Face registered successfully!', 'success')
                    captured = True
                else:
                    flash('No face detected!', 'danger')
            elif key == 27:  # ESC
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        if captured:
            return redirect('/profile')
    
    return render_template('register_face.html')

# =========================
# DASHBOARD
# =========================
@app.route('/dashboard')
def dashboard():
    if 'student_id' not in session:
        flash('Please login first.', 'warning')
        return redirect('/')

    student_id = session['student_id']
    
    # Log dashboard access
    log_activity(student_id, 'VIEW_DASHBOARD', 'User viewed dashboard')

    # Get student info
    cursor.execute(
        "SELECT * FROM students WHERE student_id=%s",
        (student_id,)
    )
    student = cursor.fetchone()

    # Count total notes
    cursor.execute(
        "SELECT COUNT(*) FROM notes WHERE student_id=%s",
        (student_id,)
    )
    total_notes = cursor.fetchone()[0]

    # Count total schedules
    cursor.execute(
        "SELECT COUNT(*) FROM schedules WHERE student_id=%s",
        (student_id,)
    )
    total_schedules = cursor.fetchone()[0]

    # Count total grades
    cursor.execute(
        "SELECT COUNT(*) FROM grades WHERE student_id=%s",
        (student_id,)
    )
    total_grades = cursor.fetchone()[0]

    # Calculate average grade
    cursor.execute(
        "SELECT AVG((quizzes*0.30)+(assignments*0.30)+(exams*0.40)) FROM grades WHERE student_id=%s",
        (student_id,)
    )
    average_grade = cursor.fetchone()[0]
    
    if average_grade is None:
        average_grade = 0
    else:
        average_grade = round(average_grade, 2)

    # Get average quiz, assignment, exam scores for chart
    cursor.execute(
        "SELECT AVG(quizzes), AVG(assignments), AVG(exams) FROM grades WHERE student_id=%s",
        (student_id,)
    )
    avg_scores = cursor.fetchone()
    
    avg_quiz = round(avg_scores[0] or 0, 2)
    avg_assignment = round(avg_scores[1] or 0, 2)
    avg_exam = round(avg_scores[2] or 0, 2)

    # Get recent notes (last 3)
    cursor.execute(
        "SELECT title, created_at FROM notes WHERE student_id=%s ORDER BY created_at DESC LIMIT 3",
        (student_id,)
    )
    recent_notes = cursor.fetchall()

    # Get upcoming schedules (next 3)
    cursor.execute(
        "SELECT subject, day, start_time FROM schedules WHERE student_id=%s ORDER BY day, start_time LIMIT 3",
        (student_id,)
    )
    upcoming_schedules = cursor.fetchall()

    # Get current date/time
    from datetime import datetime
    current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")

    return render_template(
        'dashboard.html',
        student=student,
        total_notes=total_notes,
        total_schedules=total_schedules,
        total_grades=total_grades,
        average_grade=average_grade,
        avg_quiz=avg_quiz,
        avg_assignment=avg_assignment,
        avg_exam=avg_exam,
        recent_notes=recent_notes,
        upcoming_schedules=upcoming_schedules,
        current_time=current_time
    )

# =========================
# ACTIVITY LOG
# =========================
@app.route('/activity_log')
def activity_log():
    if 'student_id' not in session:
        flash('Please login first.', 'warning')
        return redirect('/')
    
    student_id = session['student_id']
    
    # Get the user's activity log
    cursor.execute(
        "SELECT action, details, created_at FROM activity_log WHERE student_id=%s ORDER BY created_at DESC LIMIT 50",
        (student_id,)
    )
    activities = cursor.fetchall()
    
    return render_template('activity_log.html', activities=activities)

# =========================
# PROFILE PAGE
# =========================
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'student_id' not in session:
        flash('Please login first.', 'warning')
        return redirect('/')

    student_id = session['student_id']

    if request.method == 'POST':
        fullname = request.form['fullname']
        address = request.form['address']
        email = request.form['email']

        try:
            cursor.execute(
                """
                UPDATE students
                SET fullname=%s,
                    address=%s,
                    email=%s
                WHERE student_id=%s
                """,
                (fullname, address, email, student_id)
            )
            db.commit()
            log_activity(student_id, 'UPDATE_PROFILE', 'Profile updated')
            flash('Profile updated successfully!', 'success')
        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'danger')

    cursor.execute(
        "SELECT * FROM students WHERE student_id=%s",
        (student_id,)
    )

    student = cursor.fetchone()

    return render_template(
        'profile.html',
        student=student
    )

# =========================
# NOTES PAGE
# =========================
@app.route('/notes')
def notes():
    if 'student_id' not in session:
        flash('Please login first.', 'warning')
        return redirect('/')

    student_id = session['student_id']

    cursor.execute(
        "SELECT * FROM notes WHERE student_id=%s ORDER BY created_at DESC",
        (student_id,)
    )

    notes = cursor.fetchall()

    return render_template(
        'notes.html',
        notes=notes
    )

# =========================
# ADD NOTE
# =========================
@app.route('/add_note', methods=['GET', 'POST'])
def add_note():
    if 'student_id' not in session:
        flash('Please login first.', 'warning')
        return redirect('/')

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        if not title or not content:
            flash('Title and content are required!', 'danger')
            return render_template('add_note.html')

        student_id = session['student_id']

        try:
            cursor.execute(
                """
                INSERT INTO notes
                (student_id, title, content)
                VALUES (%s, %s, %s)
                """,
                (student_id, title, content)
            )
            db.commit()
            log_activity(student_id, 'ADD_NOTE', f'Created note: {title}')
            flash('Note added successfully!', 'success')
            return redirect('/notes')
        except Exception as e:
            flash(f'Error adding note: {str(e)}', 'danger')

    return render_template('add_note.html')

# =========================
# SEARCH NOTES
# =========================
@app.route('/search_notes', methods=['GET', 'POST'])
def search_notes():
    if 'student_id' not in session:
        flash('Please login first.', 'warning')
        return redirect('/')

    student_id = session['student_id']
    search_results = []

    if request.method == 'POST':
        search_term = request.form['search_term']
        
        cursor.execute(
            """
            SELECT * FROM notes 
            WHERE student_id=%s 
            AND (title LIKE %s OR content LIKE %s)
            ORDER BY created_at DESC
            """,
            (student_id, f'%{search_term}%', f'%{search_term}%')
        )
        search_results = cursor.fetchall()
        log_activity(student_id, 'SEARCH_NOTES', f'Searched for: {search_term}')

    return render_template('search_notes.html', notes=search_results)

# =========================
# DELETE NOTE
# =========================
@app.route('/delete_note/<int:note_id>')
def delete_note(note_id):
    if 'student_id' not in session:
        flash('Please login first.', 'warning')
        return redirect('/')

    student_id = session['student_id']

    try:
        # Check if the note exists and belongs to the user
        cursor.execute(
            "SELECT * FROM notes WHERE note_id=%s AND student_id=%s",
            (note_id, student_id)
        )
        
        note = cursor.fetchone()
        
        if note:
            title = note[2]  # Get title before deleting
            # Delete the note using note_id
            cursor.execute(
                "DELETE FROM notes WHERE note_id=%s AND student_id=%s",
                (note_id, student_id)
            )
            db.commit()
            log_activity(student_id, 'DELETE_NOTE', f'Deleted note: {title}')
            flash('Note deleted successfully!', 'success')
        else:
            flash('Note not found or you do not have permission to delete it.', 'danger')
    
    except Exception as e:
        flash(f'Error deleting note: {str(e)}', 'danger')
        print(f"Error: {e}")
    
    return redirect('/notes')

# =========================
# EDIT NOTE - FIXED
# =========================
@app.route('/edit_note/<int:note_id>', methods=['GET', 'POST'])
def edit_note(note_id):
    if 'student_id' not in session:
        flash('Please login first.', 'warning')
        return redirect('/')

    student_id = session['student_id']

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        if not title or not content:
            flash('Title and content are required!', 'danger')
            return redirect(f'/edit_note/{note_id}')

        try:
            cursor.execute(
                """
                UPDATE notes
                SET title=%s, content=%s
                WHERE note_id=%s AND student_id=%s
                """,
                (title, content, note_id, student_id)
            )
            db.commit()
            log_activity(student_id, 'EDIT_NOTE', f'Updated note: {title}')
            flash('Note updated successfully!', 'success')
            return redirect('/notes')
        except Exception as e:
            flash(f'Error updating note: {str(e)}', 'danger')

    cursor.execute(
        "SELECT * FROM notes WHERE note_id=%s AND student_id=%s",
        (note_id, student_id)
    )
    note = cursor.fetchone()

    if not note:
        flash('Note not found or you do not have permission to edit it.', 'danger')
        return redirect('/notes')

    return render_template('edit_note.html', note=note)

# =========================
# SCHEDULE PAGE (ADD)
# =========================
@app.route('/schedule', methods=['GET', 'POST'])
def schedule():
    if 'student_id' not in session:
        flash('Please login first.', 'warning')
        return redirect('/')

    student_id = session['student_id']

    if request.method == 'POST':
        subject = request.form['subject']
        day = request.form['day']
        start_time = request.form['start_time']
        end_time = request.form['end_time']

        if not subject or not day or not start_time or not end_time:
            flash('All fields are required!', 'danger')
            return redirect('/schedule')

        try:
            cursor.execute(
                """
                INSERT INTO schedules
                (student_id, subject, day, start_time, end_time)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (student_id, subject, day, start_time, end_time)
            )
            db.commit()
            log_activity(student_id, 'ADD_SCHEDULE', f'Added schedule: {subject} on {day}')
            flash('Schedule added successfully!', 'success')
            return redirect('/schedule')
        except Exception as e:
            flash(f'Error adding schedule: {str(e)}', 'danger')

    cursor.execute(
        "SELECT * FROM schedules WHERE student_id=%s ORDER BY day, start_time",
        (student_id,)
    )

    schedules = cursor.fetchall()

    return render_template(
        'schedule.html',
        schedules=schedules
    )

# =========================
# DELETE SCHEDULE
# =========================
@app.route('/delete_schedule/<int:schedule_id>')
def delete_schedule(schedule_id):

    if 'student_id' not in session:
        flash('Please login first.', 'warning')
        return redirect('/')

    student_id = session['student_id']

    try:

        cursor.execute(
            """
            SELECT *
            FROM schedules
            WHERE schedule_id=%s
            AND student_id=%s
            """,
            (schedule_id, student_id)
        )

        schedule = cursor.fetchone()

        if schedule:

            subject = schedule[2]

            cursor.execute(
                """
                DELETE FROM schedules
                WHERE schedule_id=%s
                AND student_id=%s
                """,
                (schedule_id, student_id)
            )

            db.commit()

            log_activity(
                student_id,
                'DELETE_SCHEDULE',
                f'Deleted schedule: {subject}'
            )

            flash(
                'Schedule deleted successfully!',
                'success'
            )

        else:

            flash(
                'Schedule not found or you do not have permission to delete it.',
                'danger'
            )

    except Exception as e:

        flash(
            f'Error deleting schedule: {str(e)}',
            'danger'
        )

        print(f"Error: {e}")

    return redirect('/schedule')

# =========================
# GRADES PAGE + ADD GRADE
# =========================
@app.route('/grades', methods=['GET', 'POST'])
def grades():
    if 'student_id' not in session:
        flash('Please login first.', 'warning')
        return redirect('/')

    student_id = session['student_id']

    if request.method == 'POST':
        subject = request.form['subject']
        quizzes = float(request.form['quizzes'])
        assignments = float(request.form['assignments'])
        exams = float(request.form['exams'])

        if not subject:
            flash('Subject is required!', 'danger')
            return redirect('/grades')

        try:
            cursor.execute(
                """
                INSERT INTO grades
                (student_id, subject, quizzes, assignments, exams)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (student_id, subject, quizzes, assignments, exams)
            )
            db.commit()
            log_activity(student_id, 'ADD_GRADE', f'Added grade for: {subject}')
            flash('Grade added successfully!', 'success')
            return redirect('/grades')
        except Exception as e:
            flash(f'Error adding grade: {str(e)}', 'danger')

    cursor.execute(
        "SELECT * FROM grades WHERE student_id=%s",
        (student_id,)
    )

    records = cursor.fetchall()

    grades = []

    for row in records:
        final_grade = (
            float(row[3]) * 0.30 +
            float(row[4]) * 0.30 +
            float(row[5]) * 0.40
        )

        grades.append({
            "id": row[0],
            "subject": row[2],
            "quiz": float(row[3]),
            "assignment": float(row[4]),
            "exam": float(row[5]),
            "final": round(final_grade, 2)
        })

    return render_template(
        'grades.html',
        grades=grades
    )

# =========================
# EXPORT GRADES TO CSV
# =========================
@app.route('/export_grades')
def export_grades():
    if 'student_id' not in session:
        flash('Please login first.', 'warning')
        return redirect('/')
    
    student_id = session['student_id']
    
    cursor.execute(
        "SELECT subject, quizzes, assignments, exams FROM grades WHERE student_id=%s",
        (student_id,)
    )
    grades_data = cursor.fetchall()
    
    # Create CSV
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['Subject', 'Quizzes (30%)', 'Assignments (30%)', 'Exams (40%)', 'Final Grade'])
    
    for row in grades_data:
        final = (row[1] * 0.30) + (row[2] * 0.30) + (row[3] * 0.40)
        writer.writerow([row[0], row[1], row[2], row[3], round(final, 2)])
    
    output = si.getvalue()
    
    log_activity(student_id, 'EXPORT_GRADES', 'Exported grades to CSV')
    
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=grades_{student_id}.csv'}
    )

# =========================
# DELETE GRADE - FIXED
# =========================
@app.route('/delete_grade/<int:grade_id>')
def delete_grade(grade_id):
    if 'student_id' not in session:
        flash('Please login first.', 'warning')
        return redirect('/')

    student_id = session['student_id']

    try:
        # Check if the grade exists and belongs to the user
        # Try different possible column names
        cursor.execute(
            "SELECT * FROM grades WHERE grade_id=%s AND student_id=%s",
            (grade_id, student_id)
        )
        grade = cursor.fetchone()
        
        if not grade:
            # Try 'id' if 'grade_id' doesn't work
            cursor.execute(
                "SELECT * FROM grades WHERE id=%s AND student_id=%s",
                (grade_id, student_id)
            )
            grade = cursor.fetchone()

        if grade:
            subject = grade[2]  # Get subject before deleting
            # Delete the grade using the correct column name
            cursor.execute(
                "DELETE FROM grades WHERE grade_id=%s AND student_id=%s",
                (grade_id, student_id)
            )
            # If that fails, try 'id'
            if cursor.rowcount == 0:
                cursor.execute(
                    "DELETE FROM grades WHERE id=%s AND student_id=%s",
                    (grade_id, student_id)
                )
            db.commit()
            log_activity(student_id, 'DELETE_GRADE', f'Deleted grade for: {subject}')
            flash('Grade deleted successfully!', 'success')
        else:
            flash('Grade not found or you do not have permission to delete it.', 'danger')
    
    except mysql.connector.errors.ProgrammingError as e:
        flash(f'Database error: {str(e)}', 'danger')
        print(f"Error: {e}")
    except Exception as e:
        flash(f'Error deleting grade: {str(e)}', 'danger')
        print(f"Error: {e}")

    return redirect('/grades')

# =========================
# REGISTER PAGE
# =========================
@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        student_id = request.form['student_id']
        fullname = request.form['fullname']
        address = request.form['address']
        email = request.form['email']

        # HASH PASSWORD
        password = hashlib.sha256(
            request.form['password'].encode()
        ).hexdigest()

        try:

            cursor.execute(
                """
                INSERT INTO students
                (student_id, fullname, address, email, password)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (
                    student_id,
                    fullname,
                    address,
                    email,
                    password
                )
            )

            db.commit()

            log_activity(
                student_id,
                'REGISTER',
                'New account created'
            )

            flash(
                'Registration successful! Please login.',
                'success'
            )

            return redirect('/')

        except Exception as e:

            flash(
                f'Registration failed: {str(e)}',
                'danger'
            )

            print(f"Registration Error: {e}")

    return render_template('register.html')

# =========================
# LOGOUT
# =========================
@app.route('/logout')
def logout():
    if 'student_id' in session:
        log_activity(session['student_id'], 'LOGOUT', 'User logged out')
    
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect('/')

# =========================
# START APP
# =========================
if __name__ == '__main__':
    app.run(debug=True)