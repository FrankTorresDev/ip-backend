from flask import Blueprint, jsonify, request
from db import get_db

films_bp = Blueprint("films", __name__)

@films_bp.route("/", methods=["GET"])
def get_films():
    title = request.args.get("title")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if title:
        cursor.execute("""
            SELECT film_id, title, release_year
            FROM film
            WHERE title LIKE %s
            LIMIT 20
        """, (f"%{title}%",))
    else:
        cursor.execute("""
            SELECT film_id, title, release_year
            FROM film
            LIMIT 20
        """)

    films = cursor.fetchall()
    cursor.close()
    db.close()

    return jsonify(films)
