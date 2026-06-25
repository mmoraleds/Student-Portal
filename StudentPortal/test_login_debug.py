import mysql.connector
import hashlib

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Moraleda@20067",
    database="student_portal"
)

cursor = db.cursor()

student_id = '2025-123456'
password = input("Enter your password: ")  # Type the password you're trying to login with

# Hash the password
hashed_password = hashlib.sha256(password.encode()).hexdigest()

print(f"\nStudent ID: {student_id}")
print(f"Your password: {password}")
print(f"Your hashed password: {hashed_password}")

# Check if student exists
cursor.execute("SELECT * FROM students WHERE student_id=%s", (student_id,))
student = cursor.fetchone()

if student:
    print(f"\n✅ Student found!")
    print(f"Name: {student[1]}")
    print(f"Stored password hash: {student[4]}")
    print(f"Your password hash: {hashed_password}")
    
    if student[4] == hashed_password:
        print("\n✅ PASSWORDS MATCH! You should be able to login.")
    else:
        print("\n❌ PASSWORDS DON'T MATCH!")
        print("Updating password to match...")
        
        # Update the password
        cursor.execute(
            "UPDATE students SET password=%s WHERE student_id=%s",
            (hashed_password, student_id)
        )
        db.commit()
        print(f"✅ Password updated for {student_id}")
else:
    print(f"❌ Student {student_id} not found!")

db.close()