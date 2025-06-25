from flask import Blueprint, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

jobseeker_bp = Blueprint('jobseeker', __name__)

# /Profile endpoint that requires JWT authentication
@jobseeker_bp.route('/profile', methods=['GET'])
@jwt_required() # Ensures that the request has a valid JWT token
def profile():
    try:
        # Get the user ID from the JWT token
        user_id = int(get_jwt_identity())

        # Access MySQL connection from the app context using cursor to get user profile
        mysql = current_app.extensions['mysql']
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, name, email, role FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        cur.close()

        if not user:
            return jsonify({"error": "User not found"}), 404

        # Convert the user data to a dictionary for JSON response
        user_data = {
            "id": user[0],
            "name": user[1],
            "email": user[2],
            "role": user[3]
        }

        return jsonify({"profile": user_data}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
