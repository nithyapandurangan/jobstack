from flask import Blueprint, jsonify, current_app, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

admin_bp = Blueprint('admin', __name__)

def is_admin(user_id):
    mysql = current_app.extensions['mysql']
    cur = mysql.connection.cursor()
    cur.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    role = cur.fetchone()
    cur.close()
    return role and role[0] == 'admin'

### /users- to view all users
@admin_bp.route('/users', methods=['GET'])
@jwt_required()
def list_users():
    user_id = int(get_jwt_identity())
    if not is_admin(user_id):
        return jsonify({"error": "Unauthorized"}), 403

    mysql = current_app.extensions['mysql']
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, email, role FROM users")
    users = cur.fetchall()
    cur.close()

    return jsonify({"users": [
        {"id": u[0], "name": u[1], "email": u[2], "role": u[3]} for u in users
    ]}), 200

### /jobs- to view all jobs
@admin_bp.route('/jobs', methods=['GET'])
@jwt_required()
def list_all_jobs():
    try:
        user_id = int(get_jwt_identity())
        if not is_admin(user_id):
            return jsonify({"error": "Unauthorized"}), 403

        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=10, type=int)
        offset = (page - 1) * per_page

        mysql = current_app.extensions['mysql']
        cur = mysql.connection.cursor()

        # Get total count of jobs for pagination
        cur.execute("SELECT COUNT(*) FROM jobs")
        total = cur.fetchone()[0]

        # Fetch jobs with pagination
        cur.execute("""
            SELECT id, title, company, description, location, posted_by, posted_at, salary,
                   num_applications, work_mode, yoe, is_closed, skills
            FROM jobs
            LIMIT %s OFFSET %s
        """, (per_page, offset))
        jobs = cur.fetchall()
        cur.close()

        job_list = []
        for job in jobs:
            job_list.append({
                "id": job[0],
                "title": job[1],
                "company": job[2],
                "description": job[3],
                "location": job[4],
                "posted_by": job[5],
                "posted_at": job[6].isoformat() if job[6] else None,
                "salary": job[7],
                "num_applications": job[8],
                "work_mode": job[9],
                "yoe": job[10],
                "is_closed": bool(job[11]),
                "skills": job[12].split(",") if job[12] else []
            })

        return jsonify({
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
            "jobs": job_list
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


### /applications- to view all applications
@admin_bp.route('/applications', methods=['GET'])
@jwt_required()
def view_all_applications():
    user_id = int(get_jwt_identity())
    if not is_admin(user_id):
        return jsonify({"error": "Unauthorized"}), 403

    mysql = current_app.extensions['mysql']
    cur = mysql.connection.cursor()
    query = """
        SELECT a.id, u.name, j.title, a.applied_at
        FROM applications a
        JOIN users u ON a.user_id = u.id
        JOIN jobs j ON a.job_id = j.id
        ORDER BY a.applied_at DESC
    """
    cur.execute(query)
    results = cur.fetchall()
    cur.close()

    return jsonify({"applications": [
        {
            "application_id": row[0],
            "applicant_name": row[1],
            "job_title": row[2],
            "applied_at": row[3].isoformat() if row[3] else None
        } for row in results
    ]}), 200

### /jobs/job-id/close- to close a job
@admin_bp.route('/jobs/<int:job_id>/close', methods=['POST'])
@jwt_required()
def close_job(job_id):
    user_id = int(get_jwt_identity())
    if not is_admin(user_id):
        return jsonify({"error": "Unauthorized"}), 403

    mysql = current_app.extensions['mysql']
    cur = mysql.connection.cursor()

    # Check if the job exists and fetch is_closed status
    cur.execute("SELECT is_closed FROM jobs WHERE id = %s", (job_id,))
    result = cur.fetchone()
    if not result:
        return jsonify({"error": "Job not found"}), 404
    # Check if the job is already closed
    is_closed = result[0]
    if is_closed:
        return jsonify({"message": "Job is already closed"}), 400 
    
    # Update the job status to closed
    cur.execute("UPDATE jobs SET is_closed = TRUE WHERE id = %s", (job_id,))
    mysql.connection.commit()
    cur.close()

    return jsonify({"message": f"Job {job_id} marked as closed"}), 200

### /jobs/job-id/reopen- to reopen a job
@admin_bp.route("/jobs/<int:job_id>/reopen", methods=["POST"])
@jwt_required()
def reopen_job(job_id):
    user_id = int(get_jwt_identity())
    if not is_admin(user_id):
        return jsonify({"error": "Unauthorized"}), 403

    mysql = current_app.extensions['mysql']
    cur = mysql.connection.cursor()

    # Check if job exists and current is_closed status
    cur.execute("SELECT is_closed FROM jobs WHERE id = %s", (job_id,))
    result = cur.fetchone()
    if not result:
        return jsonify({"error": "Job not found"}), 404

    is_closed = result[0]
    if not is_closed:
        return jsonify({"message": "Job is already open"}), 400

    # Reopen the job
    cur.execute("UPDATE jobs SET is_closed = FALSE WHERE id = %s", (job_id,))
    mysql.connection.commit()
    cur.close()

    return jsonify({"message": "Job reopened successfully"}), 200

### /jobs/job-id - Delete a job
@admin_bp.route("/jobs/<int:job_id>", methods=["DELETE"])
@jwt_required()
def delete_job_by_admin(job_id):
    try:
        claims = get_jwt()
        if claims.get("role") != "admin":
            return jsonify({"error": "Only admins can delete jobs"}), 403

        mysql = current_app.extensions['mysql']
        cur = mysql.connection.cursor()

        # Check if job exists
        cur.execute("SELECT id FROM jobs WHERE id = %s", (job_id,))
        job = cur.fetchone()
        if not job:
            return jsonify({"error": "Job not found"}), 404

        # Delete related applications first
        cur.execute("DELETE FROM applications WHERE job_id = %s", (job_id,))
        # Delete the job
        cur.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "Job deleted by admin successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
