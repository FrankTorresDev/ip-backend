from flask import Blueprint, jsonify, request
from db import get_db

rentals_bp = Blueprint("rentals", __name__)

@rentals_bp.route("/", methods=["POST"])
def create_rental():
    data = request.get_json(silent=True) or {}

    film_id = data.get("film_id")
    customer_id = data.get("customer_id")

    # defaults (Sakila has staff/store)
    staff_id = int(data.get("staff_id", 1))

    if not film_id or not customer_id:
        return jsonify({"error": "film_id and customer_id are required"}), 400

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        # Find an available inventory item for this film:
        # available = no rental with return_date IS NULL for that inventory item
        cursor.execute("""
            SELECT i.inventory_id
            FROM inventory i
            LEFT JOIN rental r
              ON r.inventory_id = i.inventory_id
             AND r.return_date IS NULL
            WHERE i.film_id = %s
              AND r.rental_id IS NULL
            LIMIT 1
        """, (int(film_id),))
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "No available copies of this film to rent."}), 409

        inventory_id = row["inventory_id"]

        # Insert rental (return_date NULL means not returned)
        cursor.execute("""
            INSERT INTO rental (rental_date, inventory_id, customer_id, staff_id)
            VALUES (NOW(), %s, %s, %s)
        """, (int(inventory_id), int(customer_id), int(staff_id)))
        rental_id = cursor.lastrowid

        db.commit()

        return jsonify({
            "success": True,
            "rental_id": rental_id,
            "inventory_id": inventory_id,
            "film_id": int(film_id),
            "customer_id": int(customer_id)
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        db.close()