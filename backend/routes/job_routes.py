from flask import Blueprint, request, jsonify, current_app

jobs_bp = Blueprint('jobs', __name__)

@jobs_bp.route('/search', methods=['GET'])
def search_jobs():
    mysql = current_app.extensions['mysql']
    cursor = mysql.connection.cursor()

    skill = request.args.get('skill', type=str)
    min_yoe = request.args.get('min_yoe', type=int)
    max_yoe = request.args.get('max_yoe', type=int)

    query = """
        SELECT id, title, company, description, location, posted_at, salary,
               num_applications, work_mode, yoe, skills
        FROM jobs
        WHERE 1=1
    """
    params = []

    # Filter by skill (case-insensitive)
    if skill:
        query += " AND LOWER(skills) LIKE %s"
        params.append(f"%{skill.lower()}%")

    # Filter by min yoe, only if numeric yoe stored
    if min_yoe is not None:
        query += " AND yoe REGEXP '^[0-9]+$' AND CAST(yoe AS UNSIGNED) >= %s"
        params.append(min_yoe)

    # Filter by max yoe, only if numeric yoe stored
    if max_yoe is not None:
        query += " AND yoe REGEXP '^[0-9]+$' AND CAST(yoe AS UNSIGNED) <= %s"
        params.append(max_yoe)

    cursor.execute(query, tuple(params))
    jobs = cursor.fetchall()
    cursor.close()

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
            "skills": job[10].split(",") if job[10] else []
        })

    return jsonify({"jobs": jobs_list}), 200
