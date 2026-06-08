import os
import pymysql
from urllib.parse import quote_plus
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from models import db, Pincode, ApiLog

# Load environment variables
load_dotenv()

def create_db_if_not_exists():
    """Create the MySQL database if it doesn't already exist."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # If database URL is provided (e.g., in production / Render), we skip manual creation
        return
        
    db_user = os.getenv("DB_USER", "root")
    db_password = os.getenv("DB_PASSWORD", "")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "3306"))
    db_name = os.getenv("DB_NAME", "pincode_db")
    
    try:
        conn = pymysql.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password
        )
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
        conn.close()
    except Exception as e:
        print(f"Database auto-creation warning: {e}")

# Run database pre-check
if os.getenv("FLASK_ENV") != "testing":
    create_db_if_not_exists()

app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Database Configuration
if os.getenv("FLASK_ENV") == "testing":
    db_uri = "sqlite:///:memory:"
else:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        if database_url.startswith("mysql://"):
            db_uri = database_url.replace("mysql://", "mysql+pymysql://", 1)
        else:
            db_uri = database_url
    else:
        db_user = os.getenv("DB_USER", "root")
        db_password = os.getenv("DB_PASSWORD", "")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "3306")
        db_name = os.getenv("DB_NAME", "pincode_db")
        
        # URL encode password for safety
        encoded_password = quote_plus(db_password) if db_password else ""
        if encoded_password:
            db_uri = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"
        else:
            db_uri = f"mysql+pymysql://{db_user}@{db_host}:{db_port}/{db_name}"

app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# Create tables within application context
if os.getenv("FLASK_ENV") != "testing":
    with app.app_context():
        db.create_all()

@app.before_request
def validate_and_log_request():
    """Middleware to validate RapidAPI secret and log request to database."""
    # Exclude /health and non-API endpoints from validation and logging
    if request.path.startswith('/api/'):
        # 1. Validate X-RapidAPI-Proxy-Secret
        expected_secret = os.getenv("RAPIDAPI_PROXY_SECRET")
        received_secret = request.headers.get("X-RapidAPI-Proxy-Secret")
        
        if expected_secret and received_secret != expected_secret:
            return jsonify({
                "success": False,
                "message": "Unauthorized: Invalid or missing X-RapidAPI-Proxy-Secret header"
            }), 401

        # 2. Extract pincode from URL path if applicable
        pincode_queried = None
        path_parts = request.path.strip('/').split('/')
        if len(path_parts) >= 3 and path_parts[0] == 'api' and path_parts[1] == 'pincode':
            pincode_queried = path_parts[2][:6]  # Ensure max length 6

        # 3. Log to database
        ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()

        try:
            log_entry = ApiLog(
                pincode_queried=pincode_queried,
                endpoint=request.path,
                ip_address=ip_address[:45] if ip_address else None
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            # Database logging failure shouldn't crash the request
            db.session.rollback()
            app.logger.error(f"API logging failure: {e}")

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200

@app.route('/api/pincode/<pincode>', methods=['GET'])
def get_pincode_details(pincode):
    """Returns all post offices and details for that pincode."""
    if not pincode or len(pincode) != 6 or not pincode.isdigit():
        return jsonify({
            "success": False,
            "message": "Pincode not found"
        }), 404

    results = Pincode.query.filter_by(pincode=pincode).all()
    if not results:
        return jsonify({
            "success": False,
            "message": "Pincode not found"
        }), 404

    return jsonify({
        "success": True,
        "data": [item.to_dict() for item in results]
    }), 200

@app.route('/api/pincode/<pincode>/summary', methods=['GET'])
def get_pincode_summary(pincode):
    """Returns just state, district, taluk, and city (first match)."""
    if not pincode or len(pincode) != 6 or not pincode.isdigit():
        return jsonify({
            "success": False,
            "message": "Pincode not found"
        }), 404

    first_match = Pincode.query.filter_by(pincode=pincode).first()
    if not first_match:
        return jsonify({
            "success": False,
            "message": "Pincode not found"
        }), 404

    # City defaults to taluk, then district name, then post office
    city = first_match.taluk or first_match.district_name or first_match.post_office

    return jsonify({
        "success": True,
        "data": {
            "state": first_match.state_name,
            "district": first_match.district_name,
            "taluk": first_match.taluk,
            "city": city
        }
    }), 200

@app.route('/api/search/district/<district_name>', methods=['GET'])
def search_district(district_name):
    """Returns all unique pincodes in a district with basic details."""
    if not district_name:
        return jsonify({
            "success": False,
            "message": "District not found"
        }), 404

    # Perform distinct query based on pincode to return clean results
    results = db.session.query(
        Pincode.pincode, 
        Pincode.taluk, 
        Pincode.district_name, 
        Pincode.state_name
    ).filter(Pincode.district_name.ilike(district_name)).distinct().all()

    if not results:
        return jsonify({
            "success": False,
            "message": "District not found"
        }), 404

    data = [
        {
            "pincode": row.pincode,
            "taluk": row.taluk,
            "district_name": row.district_name,
            "state_name": row.state_name
        }
        for row in results
    ]

    return jsonify({
        "success": True,
        "data": data
    }), 200

@app.route('/api/search/state/<state_name>', methods=['GET'])
def search_state(state_name):
    """Returns all unique districts in a state."""
    if not state_name:
        return jsonify({
            "success": False,
            "message": "State not found"
        }), 404

    results = db.session.query(Pincode.district_name).filter(
        Pincode.state_name.ilike(state_name)
    ).distinct().all()

    if not results:
        return jsonify({
            "success": False,
            "message": "State not found"
        }), 404

    # Extract strings from the query tuples
    districts = [row.district_name for row in results if row.district_name]
    
    # Sort for cleaner presentation
    districts.sort()

    return jsonify({
        "success": True,
        "data": districts
    }), 200

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({
        "success": False,
        "message": "Resource not found"
    }), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({
        "success": False,
        "message": "Internal server error"
    }), 500

if __name__ == '__main__':
    # Run the server locally
    app.run(host='0.0.0.0', port=5000, debug=True)
