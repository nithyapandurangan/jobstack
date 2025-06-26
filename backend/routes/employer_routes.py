from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

employer_bp = Blueprint('employer', __name__)

### /api/employer/jobs/create - Create a new job posting
@employer_bp.route("/jobs/create", methods=["POST"])
@jwt_required()
def create_job():
    db = current_app.extensions["mysql"].connection
    cursor = db.cursor()

    # Check if the user is an employer
    claims = get_jwt()
    user = get_jwt_identity()
    # Get the JWT claims(role is in additional claims) to verify the role
    if claims.get("role") != "employer":
        return jsonify({"error": "Only employers can create jobs"}), 403

    # Get job details from the request
    data = request.get_json()
    title = data.get("title")
    description = data.get("description")
    location = data.get("location")
    work_mode = data.get("work_mode")
    yoe = data.get("yoe")
    salary = data.get("salary")
    company = data.get("company")
    skills_list = data.get("skills")  # get the list from JSON
    skills_str = ",".join(skills_list) if skills_list else None  # join it to a string for DB

    # Validate required fields
    if not all([title, description, location, work_mode, yoe, salary, company]):
        return jsonify({"error": "All fields are required"}), 400

    # Insert job into the database
    cursor.execute("""
        INSERT INTO jobs (title, description, location, work_mode, yoe, salary, company, posted_by, skills)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (title, description, location, work_mode, yoe, salary, company, user, skills_str))

    db.commit()
    return jsonify({"message": "Job created successfully"}), 201

### /api/employer/jobs - List all jobs posted by the employer
@employer_bp.route('/jobs', methods=['GET'])
@jwt_required()
def list_employer_jobs():
    try:
        user_id = int(get_jwt_identity())
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=10, type=int)
        offset = (page - 1) * per_page
        status = request.args.get('status', default=None, type=str)

        mysql = current_app.extensions['mysql']
        cur = mysql.connection.cursor()

        # Base count query to get total jobs for pagination
        count_query = "SELECT COUNT(*) FROM jobs WHERE posted_by = %s"
        params = [user_id]

        # Add status filter to count query
        if status == 'open':
            count_query += " AND is_closed = FALSE"
        elif status == 'closed':
            count_query += " AND is_closed = TRUE"

        cur.execute(count_query, tuple(params))
        total = cur.fetchone()[0]

        # Base select query with filters
        query = """
            SELECT id, title, company, description, location, posted_at, salary, num_applications, 
                   work_mode, yoe, skills, is_closed
            FROM jobs
            WHERE posted_by = %s
        """

        # Add status filter to select query
        if status == 'open':
            query += " AND is_closed = FALSE"
        elif status == 'closed':
            query += " AND is_closed = TRUE"

        query += " LIMIT %s OFFSET %s"
        params.extend([per_page, offset])

        cur.execute(query, tuple(params))
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
                "posted_at": job[5].isoformat() if job[5] else None,
                "salary": job[6],
                "num_applications": job[7],
                "work_mode": job[8],
                "yoe": job[9],
                "skills": job[10].split(",") if job[10] else [],
                "is_closed": bool(job[11])
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
    
### /api/employer/jobs/<int:job_id>/applications - View applications for a specific job
@employer_bp.route('/jobs/<int:job_id>/applications', methods=['GET'])
@jwt_required()
def view_job_applications(job_id):
    try:
        user_id = int(get_jwt_identity())
        mysql = current_app.extensions['mysql']
        cur = mysql.connection.cursor()

        # Check if job belongs to employer
        cur.execute("SELECT id FROM jobs WHERE id = %s AND posted_by = %s", (job_id, user_id))
        job = cur.fetchone()
        if not job:
            return jsonify({"error": "Job not found or unauthorized"}), 404

        # Get all applications for the job, join with users to get applicant details
        cur.execute("""
            SELECT users.id, users.name, users.email, applications.applied_at
            FROM applications
            JOIN users ON applications.user_id = users.id
            WHERE applications.job_id = %s
            ORDER BY applications.applied_at DESC
        """, (job_id,))
        applications = cur.fetchall()
        cur.close()

        # Format applications into a list of dictionaries
        apps_list = []
        for app in applications:
            apps_list.append({
                "applicant_id": app[0],
                "applicant_name": app[1],
                "applicant_email": app[2],
                "applied_at": app[3].isoformat() if app[3] else None
            })

        return jsonify({"applications": apps_list}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

### /api/employer/jobs/<int:job_id> - Update a job posting
@employer_bp.route("/jobs/<int:job_id>", methods=["PATCH"])
@jwt_required()
def update_job(job_id):
    mysql = current_app.extensions['mysql']
    cursor = mysql.connection.cursor()

    user_id = int(get_jwt_identity())

    # First verify if the user is an employer and owns this job
    cursor.execute("SELECT posted_by FROM jobs WHERE id = %s", (job_id,))
    job = cursor.fetchone()
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job[0] != user_id:
        return jsonify({"error": "Unauthorized to update this job"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"error": "No update data provided"}), 400

    # Allowed fields to update
    allowed_fields = ["title", "description", "location", "work_mode", "yoe", "salary", "company", "skills"]
    update_fields = []
    update_values = []

    # Check which fields are provided in the request and prepare the update query
    for field in allowed_fields:
        if field in data:
            update_fields.append(f"{field} = %s")
            update_values.append(data[field])

    if not update_fields:
        return jsonify({"error": "No valid fields to update"}), 400

    update_values.append(job_id)

    # Construct the update query dynamically
    update_query = f"UPDATE jobs SET {', '.join(update_fields)} WHERE id = %s"
    cursor.execute(update_query, tuple(update_values))
    mysql.connection.commit()
    cursor.close()

    return jsonify({"message": "Job updated successfully"}), 200

### /api/employer/jobs/<int:job_id> - Delete a job posting
@employer_bp.route('/jobs/<int:job_id>', methods=['DELETE'])
@jwt_required()
def delete_job(job_id):
    try:
        user_id = int(get_jwt_identity())
        mysql = current_app.extensions['mysql']
        cur = mysql.connection.cursor()

        # Check ownership
        cur.execute("SELECT id FROM jobs WHERE id = %s AND posted_by = %s", (job_id, user_id))
        job = cur.fetchone()
        if not job:
            return jsonify({"error": "Job not found or unauthorized"}), 404

        # Delete applications related to this job first (foreign key)
        cur.execute("DELETE FROM applications WHERE job_id = %s", (job_id,))
        # Then delete the job itself
        cur.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "Job deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

### /api/employer/jobs/<int:job_id>/close - Close a job
@employer_bp.route("/jobs/<int:job_id>/close", methods=["PATCH"])
@jwt_required()
def close_job(job_id):
    try:
        user_id = int(get_jwt_identity())
        mysql = current_app.extensions['mysql']
        cur = mysql.connection.cursor()

        # Verify ownership
        cur.execute("SELECT id, is_closed FROM jobs WHERE id = %s AND posted_by = %s", (job_id, user_id))
        job = cur.fetchone()
        if not job:
            return jsonify({"error": "Job not found or unauthorized"}), 404

        if job[1]:  # already closed
            return jsonify({"message": "Job is already closed"}), 400
        
        # Update job to mark it as closed
        cur.execute("UPDATE jobs SET is_closed = TRUE WHERE id = %s", (job_id,))
        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "Job closed successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
