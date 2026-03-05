from flask import Blueprint, jsonify, request
from db import get_db

customers_bp = Blueprint("customers", __name__)

# -------------------------
# GET: list customers (only active so "deleted" customers disappear)
# URL: /api/customers/
# -------------------------
@customers_bp.route("/", methods=["GET"])
def get_customers():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT customer_id, first_name, last_name, email
        FROM customer
        WHERE active = 1
        ORDER BY customer_id
    """)

    customers = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(customers)


# -------------------------
# POST: create customer + address (minimal fields)
# URL: /api/customers/with-address
# -------------------------
@customers_bp.route("/with-address", methods=["POST"])
def create_customer_with_address():
    data = request.get_json(silent=True) or {}

    # customer fields
    store_id = data.get("store_id", 1)
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    email = (data.get("email") or "").strip() or None
    active = int(data.get("active", 1))

    # minimal address fields from UI
    address = (data.get("address") or "").strip()
    city = (data.get("city") or "").strip()
    postal_code = (data.get("postal_code") or "").strip() or None
    phone = (data.get("phone") or "").strip()

    # Sakila-required fields we auto-fill
    district = "Unknown"
    country = "United States"
    address2 = None

    missing = []
    if not first_name: missing.append("first_name")
    if not last_name: missing.append("last_name")
    if not address: missing.append("address")
    if not city: missing.append("city")
    if not phone: missing.append("phone")

    if missing:
        return jsonify({"error": "Missing required fields", "missing": missing}), 400

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        # 1) Country: find or create
        cursor.execute("SELECT country_id FROM country WHERE country = %s", (country,))
        row = cursor.fetchone()
        if row:
            country_id = row["country_id"]
        else:
            cursor.execute("INSERT INTO country (country) VALUES (%s)", (country,))
            country_id = cursor.lastrowid

        # 2) City: find or create
        cursor.execute(
            "SELECT city_id FROM city WHERE city = %s AND country_id = %s",
            (city, country_id)
        )
        row = cursor.fetchone()
        if row:
            city_id = row["city_id"]
        else:
            cursor.execute(
                "INSERT INTO city (city, country_id) VALUES (%s, %s)",
                (city, country_id)
            )
            city_id = cursor.lastrowid

        # 3) Address: insert
        # IMPORTANT: Sakila address.location is NOT NULL with no default.
        cursor.execute("""
            INSERT INTO address (address, address2, district, city_id, postal_code, phone, location)
            VALUES (%s, %s, %s, %s, %s, %s, ST_GeomFromText('POINT(0 0)'))
        """, (address, address2, district, city_id, postal_code, phone))
        address_id = cursor.lastrowid

        # 4) Customer: insert
        cursor.execute("""
            INSERT INTO customer (store_id, first_name, last_name, email, address_id, active)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (int(store_id), first_name, last_name, email, int(address_id), int(active)))
        customer_id = cursor.lastrowid

        db.commit()

        # Return created joined record
        cursor.execute("""
            SELECT
              c.customer_id, c.store_id, c.first_name, c.last_name, c.email, c.active,
              a.address_id, a.address, a.postal_code, a.phone,
              ci.city, co.country
            FROM customer c
            JOIN address a ON c.address_id = a.address_id
            JOIN city ci ON a.city_id = ci.city_id
            JOIN country co ON ci.country_id = co.country_id
            WHERE c.customer_id = %s
        """, (customer_id,))
        created = cursor.fetchone()

        return jsonify(created), 201

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        db.close()


# -------------------------
# GET: single customer (full info)
# URL: /api/customers/<id>
# -------------------------
@customers_bp.route("/<int:customer_id>", methods=["GET"])
def get_customer_by_id(customer_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
          c.customer_id, c.store_id, c.first_name, c.last_name, c.email, c.active,
          a.address_id, a.address, a.postal_code, a.phone,
          ci.city, co.country
        FROM customer c
        JOIN address a ON c.address_id = a.address_id
        JOIN city ci ON a.city_id = ci.city_id
        JOIN country co ON ci.country_id = co.country_id
        WHERE c.customer_id = %s
    """, (customer_id,))

    customer = cursor.fetchone()
    cursor.close()
    db.close()

    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    return jsonify(customer)


# -------------------------
# PUT: update customer + address (minimal fields)
# URL: /api/customers/<id>
# -------------------------
@customers_bp.route("/<int:customer_id>", methods=["PUT"])
def update_customer(customer_id):
    data = request.get_json(silent=True) or {}

    store_id = data.get("store_id")
    first_name = data.get("first_name")
    last_name = data.get("last_name")
    email = data.get("email")
    active = data.get("active")

    address = data.get("address")
    city = data.get("city")
    postal_code = data.get("postal_code")
    phone = data.get("phone")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        # Find the customer's address_id + country_id (we keep the same country on update)
        cursor.execute("""
            SELECT c.customer_id, c.address_id, ci.country_id
            FROM customer c
            JOIN address a ON c.address_id = a.address_id
            JOIN city ci ON a.city_id = ci.city_id
            WHERE c.customer_id = %s
        """, (customer_id,))
        existing = cursor.fetchone()
        if not existing:
            return jsonify({"error": "Customer not found"}), 404

        address_id = existing["address_id"]
        country_id = existing["country_id"]

        # If city provided, find-or-create within same country, then update address.city_id
        if city is not None:
            city_clean = (city or "").strip()
            if city_clean:
                cursor.execute(
                    "SELECT city_id FROM city WHERE city = %s AND country_id = %s",
                    (city_clean, country_id)
                )
                row = cursor.fetchone()
                if row:
                    city_id = row["city_id"]
                else:
                    cursor.execute(
                        "INSERT INTO city (city, country_id) VALUES (%s, %s)",
                        (city_clean, country_id)
                    )
                    city_id = cursor.lastrowid

                cursor.execute(
                    "UPDATE address SET city_id = %s WHERE address_id = %s",
                    (city_id, address_id)
                )

        # Update address fields (do NOT touch location)
        if address is not None:
            cursor.execute(
                "UPDATE address SET address = %s WHERE address_id = %s",
                ((address or "").strip(), address_id)
            )
        if postal_code is not None:
            pc = (postal_code or "").strip() or None
            cursor.execute(
                "UPDATE address SET postal_code = %s WHERE address_id = %s",
                (pc, address_id)
            )
        if phone is not None:
            cursor.execute(
                "UPDATE address SET phone = %s WHERE address_id = %s",
                ((phone or "").strip(), address_id)
            )

        # Update customer fields
        if store_id is not None:
            cursor.execute(
                "UPDATE customer SET store_id = %s WHERE customer_id = %s",
                (int(store_id), customer_id)
            )
        if first_name is not None:
            cursor.execute(
                "UPDATE customer SET first_name = %s WHERE customer_id = %s",
                ((first_name or "").strip(), customer_id)
            )
        if last_name is not None:
            cursor.execute(
                "UPDATE customer SET last_name = %s WHERE customer_id = %s",
                ((last_name or "").strip(), customer_id)
            )
        if email is not None:
            em = (email or "").strip() or None
            cursor.execute(
                "UPDATE customer SET email = %s WHERE customer_id = %s",
                (em, customer_id)
            )
        if active is not None:
            cursor.execute(
                "UPDATE customer SET active = %s WHERE customer_id = %s",
                (int(active), customer_id)
            )

        db.commit()

        # Return updated joined record
        cursor.execute("""
            SELECT
              c.customer_id, c.store_id, c.first_name, c.last_name, c.email, c.active,
              a.address_id, a.address, a.postal_code, a.phone,
              ci.city, co.country
            FROM customer c
            JOIN address a ON c.address_id = a.address_id
            JOIN city ci ON a.city_id = ci.city_id
            JOIN country co ON ci.country_id = co.country_id
            WHERE c.customer_id = %s
        """, (customer_id,))
        updated = cursor.fetchone()

        return jsonify(updated)

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        db.close()


# -------------------------
# DELETE: soft delete (sets active=0), so it disappears from UI and avoids FK errors
# URL: /api/customers/<id>
# -------------------------
@customers_bp.route("/<int:customer_id>", methods=["DELETE"])
def delete_customer(customer_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("SELECT customer_id FROM customer WHERE customer_id = %s", (customer_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Customer not found"}), 404

        cursor.execute("""
            UPDATE customer
            SET active = 0
            WHERE customer_id = %s
        """, (customer_id,))
        db.commit()

        return jsonify({"success": True})

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        db.close()


# -------------------------
# GET: rental history for a customer
# URL: /api/customers/<id>/rentals
# -------------------------
@customers_bp.route("/<int:customer_id>/rentals", methods=["GET"])
def get_customer_rentals(customer_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            r.rental_id,
            r.rental_date,
            r.return_date,
            r.inventory_id,
            f.film_id,
            f.title AS film_title
        FROM rental r
        JOIN inventory i ON r.inventory_id = i.inventory_id
        JOIN film f ON i.film_id = f.film_id
        WHERE r.customer_id = %s
        ORDER BY r.rental_date DESC
    """, (customer_id,))

    rentals = cursor.fetchall()
    cursor.close()
    db.close()

    return jsonify(rentals)