from flask import Flask, render_template, request, redirect, session
from pymongo import MongoClient
from bson.objectid import ObjectId
from flask import jsonify

app = Flask(__name__)
app.secret_key = "secret"

# MongoDB connection
client = MongoClient("mongodb+srv://gaiii123:2001%40Gayan@cluster0.8ezvo.mongodb.net/")
db = client["quiz_platform"]
users_collection = db["users"]
quizzes_collection = db["quizzes"]
results_collection = db["results"]  # Collection to store quiz results

# Landing Page
@app.route('/')
def landing():
    return render_template('index.html')

# Login Screen
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users_collection.find_one({"username": username, "password": password})
        
        if user:
            session['username'] = username
            session['role'] = user['role']  # Store role in session
            
            # Redirect based on role
            if user['role'] == 'teacher':
                return redirect('/teacher_dashboard')
            elif user['role'] == 'student':
                return redirect('/student_dashboard')
        return "Invalid credentials"
    
    return render_template('login.html')

# Register Screen
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']  # Capture role (teacher/student)
        
        # Check if the username already exists
        if users_collection.find_one({"username": username}):
            return "Username already exists"
        
        # Insert new user into the database
        users_collection.insert_one({
            "username": username,
            "email": email,
            "password": password,
            "role": role  # Store role in DB
        })
        return redirect('/login')
    
    return render_template('register.html')

# Create Quiz
@app.route('/create_quiz', methods=['GET', 'POST'])
def create_quiz():
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect('/login')

    if request.method == 'POST':
        title = request.form['title']
        time_limit = request.form['time_limit']

        questions = []
        for i in range(1, 11):  # Loop for 10 questions
            question_text = request.form.get(f'question{i}')
            options = [
                request.form.get(f'q{i}_option1'),
                request.form.get(f'q{i}_option2'),
                request.form.get(f'q{i}_option3'),
                request.form.get(f'q{i}_option4')
            ]
            correct_answer = int(request.form.get(f'q{i}_correct'))

            questions.append({
                "question_text": question_text,
                "options": options,
                "correct_answer": correct_answer
            })

        quiz_data = {
            "title": title,
            "time_limit": int(time_limit),
            "questions": questions
        }

        quizzes_collection.insert_one(quiz_data)
        return redirect('/teacher_dashboard')

    return render_template('create_quiz.html')

# Quizzes
@app.route('/quizzes')
def quizzes():
    if 'username' not in session:
        return redirect('/login')
    
    quiz_list = list(quizzes_collection.find())
    return render_template('quizzes.html', quizzes=quiz_list)

# Attempt Quiz
@app.route('/attempt_quiz/<quiz_id>', methods=['GET'])
def attempt_quiz(quiz_id):
    if 'username' not in session or session.get('role') != 'student':
        return redirect('/login')

    quiz = quizzes_collection.find_one({"_id": ObjectId(quiz_id)})
    return render_template('attempt_quiz.html', quiz=quiz)

# Submit Quiz
@app.route('/submit_quiz/<quiz_id>', methods=['POST'])
def submit_quiz(quiz_id):
    if 'username' not in session or session.get('role') != 'student':
        return redirect('/login')

    quiz = quizzes_collection.find_one({"_id": ObjectId(quiz_id)})
    if not quiz:
        return "Quiz not found", 404

    score = 0
    total_questions = len(quiz['questions'])
    student_answers = []

    for i, question in enumerate(quiz['questions']):
        user_answer = request.form.get(f'q{i + 1}')  # Get student's answer (q1, q2, etc.)
        if user_answer is None:
            return "Please answer all questions before submitting!", 400  # Return error if any question is unanswered

        user_answer = int(user_answer)
        correct_answer = question["correct_answer"]
        is_correct = (user_answer == correct_answer)

        student_answers.append({
            "question": question["question_text"],
            "selected_option": question["options"][user_answer - 1],  # User's selected option
            "correct_option": question["options"][correct_answer - 1],  # Correct option
            "is_correct": is_correct
        })

        if is_correct:
            score += 1

    percentage = (score / total_questions) * 100

    # Store student result in the database
    result_id = results_collection.insert_one({
        "username": session['username'],
        "quiz_id": quiz_id,
        "score": score,
        "total": total_questions,
        "percentage": percentage,
        "answers": student_answers
    }).inserted_id

    return redirect(f'/quiz_result/{result_id}')

# Quiz Result
@app.route('/quiz_result/<result_id>', methods=['GET'])
def quiz_result(result_id):
    if 'username' not in session or session.get('role') != 'student':
        return redirect('/login')

    result = results_collection.find_one({"_id": ObjectId(result_id)})
    if not result:
        return "Result not found", 404

    return render_template('quiz_result.html', result=result)

# Teacher Dashboard
@app.route('/teacher_dashboard')
def teacher_dashboard():
    if 'username' not in session or session['role'] != 'teacher':
        return redirect('/login')
    
    return render_template('teacher_dashboard.html', username=session['username'])

# Student Dashboard
@app.route('/student_dashboard')
def student_dashboard():
    if 'username' not in session or session['role'] != 'student':
        return redirect('/login')
    
    return render_template('student_dashboard.html', username=session['username'])

#leaderboard
@app.route('/leaderboard')
def leaderboard():
    quiz_id = request.args.get('quiz_id')
    quizzes_list = list(quizzes_collection.find())  # Fetch all quizzes for the dropdown

    if quiz_id:
        try:
            # Convert quiz_id to ObjectId
            from bson import ObjectId
            quiz_id = ObjectId(quiz_id)

            # Fetch leaderboard for the selected quiz
            quiz_leaderboard = results_collection.aggregate([
                {
                    "$match": {"quiz_id": str(quiz_id)}  # Ensure quiz_id is a string
                },
                {
                    "$group": {
                        "_id": "$username",
                        "total_score": {"$sum": "$score"}
                    }
                },
                {
                    "$sort": {"total_score": -1}
                },
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "_id",
                        "foreignField": "username",
                        "as": "user_details"
                    }
                },
                {
                    "$unwind": "$user_details"
                },
                {
                    "$project": {
                        "username": "$_id",
                        "score": "$total_score",
                        "role": "$user_details.role"
                    }
                },
                {
                    "$match": {
                        "role": "student"
                    }
                }
            ])
            
            leaderboard_data = list(quiz_leaderboard)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(leaderboard_data)  # Return JSON for AJAX requests
            else:
                return render_template('leaderboard.html', leaderboard=leaderboard_data, quizzes=quizzes_list)
        except Exception as e:
            print(f"Error: {e}")  # Debugging
            return render_template('leaderboard.html', leaderboard=[], quizzes=quizzes_list)
    else:
        # If no quiz_id is selected, show an empty leaderboard
        return render_template('leaderboard.html', leaderboard=[], quizzes=quizzes_list)


# Logout
@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)