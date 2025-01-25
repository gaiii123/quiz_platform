from flask import Flask, render_template, request, redirect, session
from pymongo import MongoClient

app = Flask(__name__)
app.secret_key = "secret"

# MongoDB connection
client = MongoClient("mongodb+srv://gaiii123:2001%40Gayan@cluster0.8ezvo.mongodb.net/")
db = client["quiz_platform"]
users_collection = db["users"]

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
            return redirect('/main')
        return "Invalid credentials"
    return render_template('login.html')

# Register Screen
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        print(f"Received data - Username: {username}, Email: {email}")
        
        # Check if the username already exists
        if users_collection.find_one({"username": username}):
            return "Username already exists"
        
        # Insert new user into the database
        users_collection.insert_one({"username": username, "email": email, "password": password})
        print("User registered successfully!")
        return redirect('/login')
    return render_template('register.html')


# Main Screen
@app.route('/main')
def main():
    if 'username' not in session:
        return redirect('/login')
    return render_template('main.html')

# Logout
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
