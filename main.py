from flask import Flask, request, jsonify, make_response
from dotenv import load_dotenv
from stravalib import Client
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
import sqlite3
import os
from flask_cors import CORS
from datetime import datetime, timedelta

load_dotenv()
CLIENT_ID=os.getenv('CLIENT_ID')
CLIENT_SECRET=os.getenv('CLIENT_SECRET')
app = Flask(__name__)

cors = CORS(app, resources={r"/*": {"origins": os.getenv('FRONTEND_URL')}}, supports_credentials=True)

app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=15)

# Strava client
client = Client()

# SQLite database configuration
DATABASE = 'db/runsum.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Optional: to access rows as dictionaries
    return conn

# Create the database table if it doesn't exist
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logins (
            key INTEGER PRIMARY KEY AUTOINCREMENT,
            firstname TEXT,
            lastname TEXT,
            id INTEGER,
            timestamp INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()  # Call to initialize the database

@app.route("/")
def home():
    return "Hello HTTPS!"

@app.route("/get-token", methods=["POST"])
def getTokenFromCode():
    data = request.get_json()
    code = data['code']
    try:
        token_response = client.exchange_code_for_token(CLIENT_ID,
                                                        CLIENT_SECRET,
                                                        code=code)
    except Exception as e:
        print({'type': 'ERROR', 'message': str(e)})
        return {'type': 'ERROR', 'message': str(e)}, 500
    
    if 'access_token' in token_response and 'refresh_token' in token_response:
        resp = make_response(jsonify({"access_token": token_response['access_token']}))
        resp.set_cookie('refresh_token', token_response['refresh_token'], httponly=True, secure=os.getenv('SECURE'), samesite='Lax')
        # Get user
        athlete = client.get_athlete()
        new_login = (
            athlete.firstname,
            athlete.lastname,
            athlete.id,  # Store the athlete ID if available
            int(datetime.now().timestamp())  # Use the current Unix timestamp
        )

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO logins (firstname, lastname, id, timestamp) VALUES (?, ?, ?, ?)', new_login)
            conn.commit()
            conn.close()
        except Exception as e:
            print({'type': 'ERROR', 'message': f"Failed to insert into database: {e}"})
            return jsonify({"error": "Database insertion error"}), 500

        return resp, 200
    else:
        return jsonify({"error": "Failed to exchange token"}), 400
    
@app.route('/refresh-token', methods=['POST'])
def refresh_access_token():
    # Get refresh token from HttpOnly cookie
    refresh_token = request.cookies.get('refresh_token')
    if not refresh_token:
        return jsonify({"error": "No refresh token"}), 403

    # Request new access token from Strava
    token_data = client.refresh_access_token(CLIENT_ID, CLIENT_SECRET, refresh_token)
    
    if 'access_token' in token_data:
        new_access_token = token_data['access_token']
        # Return new access token to the frontend
        return jsonify({"access_token": new_access_token})
    else:
        return jsonify({"error": "Failed to refresh access token"}), 400

if __name__ == "__main__":
    app.run(debug=True, port=3011)
