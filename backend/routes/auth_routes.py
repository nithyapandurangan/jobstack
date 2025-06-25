# routes for authentication related API endpoints - /register and /login
from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from config import Config
import datetime

auth_bp = Blueprint('auth', __name__)

#Acces MySQL connection from the app context instead of importing it directly to avoid circular imports
def get_mysql():
    return current_app.extensions('mysql')
    if not mysql:
            raise RuntimeError("MySQL not initialized")
    return mysql

# Register a new user
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'job_seeker')  # default role

    # Basic validation
    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required"}), 400

    # Hash the password securely before storing
    hashed_password = generate_password_hash(password)

    try:
        mysql = current_app.extensions['mysql']
        cur = mysql.connection.cursor()

        # Insert new user into the database
        cur.execute("INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                    (name, email, hashed_password, role))
        mysql.connection.commit()
        cur.close()

        # Returns 201 Created on success
        return jsonify({"message": "User registered successfully"}), 201

    except Exception as e:
        # If email already exists or any other DB error
        return jsonify({"error": str(e)}), 500

# Login an existing user
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    try:
        mysql = current_app.extensions['mysql']
        cur = mysql.connection.cursor()
        # Fetch user by email from the database
        cur.execute("SELECT id, name, password, role FROM users WHERE email = %s", (email,))
        # Fetch one user record from the cursor if it exists and return it as a tuple
        user = cur.fetchone()
        cur.close()

        # If user exists, verify the password
        if user:
            user_id, name, hashed_pw, role = user
            # Check if the provided password matches the hashed password using werkzeug's security module- check_password_hash() 
            if check_password_hash(hashed_pw, password):
                # Create JWT token with user identity if password is correct
                access_token = create_access_token(
                    identity={"id": user_id, "name": name, "role": role},
                    expires_delta=datetime.timedelta(seconds=Config.JWT_EXPIRY_SECONDS)
                )
                return jsonify({"token": access_token}), 200
            else:
                return jsonify({"error": "Incorrect password"}), 401
        else:
            return jsonify({"error": "User not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500
