from flask import Flask, jsonify
from flask_cors import CORS
from routes.films import films_bp
from routes.customers import customers_bp
from routes.rentals import rentals_bp

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return jsonify({
        "message": "Sakila API is running",
        "endpoints": ["/api/films/", "/api/customers/", "/api/rentals/"]
    })

app.register_blueprint(films_bp, url_prefix="/api/films")
app.register_blueprint(customers_bp, url_prefix="/api/customers")
app.register_blueprint(rentals_bp, url_prefix="/api/rentals")

if __name__ == "__main__":
    app.run(debug=True)