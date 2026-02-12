from flask import Blueprint, jsonify, request
from db import get_db
from urllib.parse import unquote

films_bp = Blueprint("films", __name__)

@films_bp.route("/", methods=["GET"])
def get_films():
    title = request.args.get("title")
    topFive = request.args.get("topfive")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        if title:
            cursor.execute("""
                SELECT film_id, title, release_year
                FROM film
                WHERE title LIKE %s
                LIMIT 20
            """, (f"%{title}%",))

        elif topFive == "1":
            cursor.execute("""
                SELECT f.title, COUNT(*) AS rental_count
                FROM film f
                JOIN inventory i ON f.film_id = i.film_id
                JOIN rental r ON i.inventory_id = r.inventory_id
                GROUP BY f.title
                ORDER BY rental_count DESC
                LIMIT 5
            """)

        else:
            cursor.execute("""
                SELECT film_id, title, release_year
                FROM film
                LIMIT 20
            """)

        films = cursor.fetchall()
        return jsonify(films)

    finally:
        cursor.close()


@films_bp.route("/by-title/<path:title>", methods=["GET"])
def get_film_by_title(title):
    title = unquote(title)

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT film_id, title, description, release_year, rating, length
            FROM film
            WHERE title = %s
            LIMIT 1
        """, (title,))

        film = cursor.fetchone()

        if not film:
            return jsonify({"error": "Film not found"}), 404

        return jsonify(film)

    finally:
        cursor.close()


@films_bp.route("/by-actor/<path:actor>", methods=["GET"])
def get_film_by_actor(actor):
    actor = unquote(actor).strip()

    # support "First Last" and also "First Middle Last" (take first + last)
    parts = actor.split()
    if len(parts) < 2:
        return jsonify({"error": "Please provide actor as 'First Last'"}), 400

    actor_first = parts[0]
    actor_last = parts[-1]

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT f.film_id, f.title, f.description, f.release_year, f.rating, f.length,
                   a.first_name, a.last_name
            FROM film f
            JOIN film_actor fa ON f.film_id = fa.film_id
            JOIN actor a ON fa.actor_id = a.actor_id
            WHERE LOWER(a.first_name) = LOWER(%s)
              AND LOWER(a.last_name)  = LOWER(%s)
        """, (actor_first, actor_last))

        films = cursor.fetchall()

        if not films:
            return jsonify({"error": "Film not found"}), 404

        return jsonify(films)

    finally:
        cursor.close()


@films_bp.route("/search", methods=["GET"])
def search_films():
    title = request.args.get("title", "").strip()
    actor = request.args.get("actor", "").strip()
    category = request.args.get("category", "").strip()

    query = """
        SELECT DISTINCT f.film_id, f.title, f.description, f.release_year
        FROM film f
        LEFT JOIN film_actor fa ON f.film_id = fa.film_id
        LEFT JOIN actor a ON fa.actor_id = a.actor_id
        LEFT JOIN film_category fc ON f.film_id = fc.film_id
        LEFT JOIN category c ON fc.category_id = c.category_id
        WHERE 1=1
    """
    params = []

    if title:
        query += " AND f.title LIKE %s"
        params.append(f"%{title}%")

    if actor:
        # actor search as "contains" full name
        query += " AND CONCAT(a.first_name, ' ', a.last_name) LIKE %s"
        params.append(f"%{actor}%")

    if category:
        query += " AND c.name = %s"
        params.append(category)

    query += " ORDER BY f.title LIMIT 50"

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(query, params)
        results = cursor.fetchall()
        return jsonify(results)
    finally:
        cursor.close()
