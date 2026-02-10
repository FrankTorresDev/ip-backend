from flask import Blueprint, jsonify
from db import get_db

customers_bp = Blueprint("customers", __name__)

@customers_bp.route("/", methods=["GET"])
def get_customers():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT customer_id, first_name, last_name, email
        FROM customer
        LIMIT 20
    """)

    customers = cursor.fetchall()
    cursor.close()
    db.close()

    return jsonify(customers)
