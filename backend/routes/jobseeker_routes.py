from flask import Blueprint, jsonify, current_app, request
from flask_jwt_extended import jwt_required, get_jwt_identity

jobseeker_bp = Blueprint('jobseeker', __name__)

### /Profile endpoint that requires JWT authentication
@jobseeker_bp.route('/profile', methods=['GET'])
@jwt_required() 
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

### /jobs endpoint to get all jobs
@jobseeker_bp.route('/jobs', methods=['GET'])
def list_jobs():
    try:
        # Pagination parameters
        # Default to page 1 and 10 jobs per page if not provided
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=10, type=int)
        offset = (page - 1) * per_page

        mysql = current_app.extensions['mysql']
        cur = mysql.connection.cursor()

        # Total count for pagination metadata
        cur.execute("SELECT COUNT(*) FROM jobs")
        total = cur.fetchone()[0]

        # Fetch jobs with pagination
        cur.execute("""
        SELECT id, title, company, description, location, posted_at, salary, num_applications, work_mode, yoe, skills " \
        FROM jobs
        LIMIT %s OFFSET %s 
        """, (per_page, offset))
        jobs = cur.fetchall()
        cur.close()

        jobs_list = []
        for job in jobs:
            jobs_list.append({
                "id": job[0],
                "title": job[1],
                "company": job[2],
                "description": job[3],
                "location": job[4],
                "posted_at": job[5].isoformat() if job[5] else None,  # Convert datetime to ISO string
                "salary": job[6],
                "num_applications": job[7],
                "work_mode": job[8],
                "yoe": job[9],
                "skills": job[10]
            })

        return jsonify({
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
            "jobs": jobs_list
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

### /Jobs/apply endpoint that requires JWT authentication    
@jobseeker_bp.route('/jobs/apply', methods=['POST'])
@jwt_required()
def apply_to_job():
    try:
        identity = get_jwt_identity()
        user_id = int(identity)  

        data = request.get_json()
        job_id = data.get('job_id')

        if not job_id:
            return jsonify({"error": "Job ID is required"}), 400

        mysql = current_app.extensions['mysql']
        cur = mysql.connection.cursor()

        # Check if job exists and still open
        cur.execute("SELECT id, is_closed FROM jobs WHERE id = %s", (job_id,))
        job = cur.fetchone()
        if not job:
            return jsonify({"error": "Job not found"}), 404
        if job[1]:  # is_closed is True
            return jsonify({"error": "This job is closed and no longer accepting applications"}), 400

        # Check if already applied
        cur.execute("SELECT * FROM applications WHERE user_id = %s AND job_id = %s", (user_id, job_id))
        if cur.fetchone():
            return jsonify({"error": "Already applied to this job"}), 400

        # Insert into applications
        cur.execute("INSERT INTO applications (user_id, job_id) VALUES (%s, %s)", (user_id, job_id))

        # Update num_applications
        cur.execute("UPDATE jobs SET num_applications = num_applications + 1 WHERE id = %s", (job_id,))

        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "Applied to job successfully"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

### /Applications endpoint to list all job applications for the user
@jobseeker_bp.route('/applications', methods=['GET'])
@jwt_required()
def list_applications():
    try:
        user_id = int(get_jwt_identity())
        # Pagination parameters
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=10, type=int)
        offset = (page - 1) * per_page

        mysql = current_app.extensions['mysql']
        cur = mysql.connection.cursor()

         # Total count of applications for pagination metadata
        cur.execute("SELECT COUNT(*) FROM applications WHERE user_id = %s", (user_id,))
        total = cur.fetchone()[0]

        # Join applications with jobs to get job details for this user
        query = """
            SELECT jobs.id, jobs.title, jobs.company, jobs.description, jobs.location, jobs.posted_at, jobs.salary, applications.applied_at
            FROM applications
            JOIN jobs ON applications.job_id = jobs.id
            WHERE applications.user_id = %s
            ORDER BY applications.applied_at DESC
            LIMIT %s OFFSET %s
        """
        cur.execute(query, (user_id, per_page, offset))
        applications = cur.fetchall()
        cur.close()

        applied_jobs = []
        for app in applications:
            applied_jobs.append({
                "job_id": app[0],
                "title": app[1],
                "company": app[2],
                "description": app[3],
                "location": app[4],
                "posted_at": app[5].isoformat() if app[5] else None,
                "salary": app[6],
                "applied_at": app[7].isoformat() if app[7] else None
            })

        return jsonify({
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
            "applications": applied_jobs
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
