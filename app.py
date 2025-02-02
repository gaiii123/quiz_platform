from flask import Flask, render_template, request, redirect, session, make_response
from pymongo import MongoClient
from bson.objectid import ObjectId
from flask import jsonify
from datetime import datetime
from config.db_config import users_collection, quizzes_collection, results_collection
app = Flask(__name__)
app.secret_key = "secret"



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

@app.route('/create_quiz', methods=['GET', 'POST'])
def create_quiz():
    if 'username' not in session or session.get('role') != 'teacher':
        return redirect('/login')

    if request.method == 'POST':
        title = request.form['title']
        time_limit = request.form['time_limit']

        # Combine date and time into datetime objects
        start_date = request.form['start_date']
        start_time = request.form['start_time']
        start_datetime = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")

        closing_date = request.form['closing_date']
        closing_time = request.form['closing_time']
        closing_datetime = datetime.strptime(f"{closing_date} {closing_time}", "%Y-%m-%d %H:%M")

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
            "start_time": start_datetime,  # Combined start datetime
            "closing_time": closing_datetime,  # Combined closing datetime
            "questions": questions,
            "created_at": datetime.now()  # Add creation timestamp
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
    current_time = datetime.now()  # Get the current time

    # Fetch attempted quizzes for the current user
    attempted_quizzes = {}
    if 'username' in session:
        for quiz in quiz_list:
            attempted = results_collection.find_one({
                "username": session['username'],
                "quiz_id": str(quiz['_id'])
            })
            if attempted:
                attempted_quizzes[str(quiz['_id'])] = True

    return render_template(
        'quizzes.html',
        quizzes=quiz_list,
        current_time=current_time,
        attempted_quizzes=attempted_quizzes  # Pass the attempted quizzes to the template
    )

@app.route('/attempt_quiz/<quiz_id>', methods=['GET'])
def attempt_quiz(quiz_id):
    if 'username' not in session or session.get('role') != 'student':
        return redirect('/login')

    quiz = quizzes_collection.find_one({"_id": ObjectId(quiz_id)})
    if not quiz:
        return "Quiz not found", 404

    # Check if the student has already attempted this quiz
    existing_attempt = results_collection.find_one({
        "username": session['username'],
        "quiz_id": quiz_id
    })

    current_time = datetime.now()
    if current_time > quiz['closing_time']:
        return render_template('quiz_ended.html')  # Show a "Quiz Ended" page

    # Pass a flag to the template indicating whether the quiz has been attempted
    return render_template('attempt_quiz.html', quiz=quiz, quiz_attempted=existing_attempt is not None)

@app.route('/submit_quiz/<quiz_id>', methods=['POST'])
def submit_quiz(quiz_id):
    if 'username' not in session or session.get('role') != 'student':
        return redirect('/login')

    quiz = quizzes_collection.find_one({"_id": ObjectId(quiz_id)})
    if not quiz:
        return "Quiz not found", 404

    # Check if the student has already attempted this quiz
    existing_attempt = results_collection.find_one({
        "username": session['username'],
        "quiz_id": quiz_id
    })

    if existing_attempt:
        return render_template('quiz_already_attempted.html')  # Show a "Quiz Already Attempted" page

    current_time = datetime.now()
    if current_time > quiz['closing_time']:
        return render_template('quiz_ended.html')  # Show a "Quiz Ended" page

    score = 0
    total_questions = len(quiz['questions'])
    student_answers = []

    for i, question in enumerate(quiz['questions']):
        user_answer = request.form.get(f'q{i + 1}')  # Get student's answer (q1, q2, etc.)
        if user_answer is None or user_answer == "0":
            # No answer provided, no points awarded
            student_answers.append({
                "question": question["question_text"],
                "selected_option": "No answer",
                "correct_option": question["options"][question["correct_answer"] - 1],
                "is_correct": False
            })
            continue

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
        "answers": student_answers,
        "timestamp": datetime.now()  # Add timestamp
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
@app.route('/student_dashboard')
def student_dashboard():
    if 'username' not in session or session['role'] != 'student':
        return redirect('/login')
    
    # Prevent caching
    response = make_response(render_template('student_dashboard.html', username=session['username']))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/teacher_dashboard')
def teacher_dashboard():
    if 'username' not in session or session['role'] != 'teacher':
        return redirect('/login')
    
   # Prevent caching
    response = make_response(render_template('teacher_dashboard.html', username=session['username']))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response
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