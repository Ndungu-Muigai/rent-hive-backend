from flask import Flask, make_response, jsonify, request
from flask_restful import Api, Resource
from flask_migrate import Migrate
from flask_cors import CORS
from flask_session import Session
from datetime import timedelta
import os
import redis 
import json
from api.models import db

app = Flask(__name__)

# Configuring the database
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI")

# Configuring redis
r = redis.from_url("rediss://red-cs2f4956l47c73bgt4c0:vfHKfN8YalQnHnhGXV01tooGpCe8ugtf@oregon-redis.render.com:6379")
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config["SESSION_TYPE"] = "redis"
app.config['SESSION_REDIS'] = r
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

#Initializing the migration
migrate=Migrate(app, db)
db.init_app(app)

#Initializing the API
api=Api(app)

#Initializing the session
Session(app)

#Configuring CORS
CORS(app, origins=["http://localhost:3000", "https://rental-hive.vercel.app"])

#Function to extract session data
def get_session_data():
    session_id=request.headers.get("X-Session-ID")

    session_data=r.get(f"session:{session_id}")

    if not session_data:
        return make_response(jsonify({"error": "Kindly login to continue"}))

    return json.loads(session_data) 

class Index(Resource):
    def get(self):
        return make_response(jsonify({"message": "Welcome to Rent Hive Rental Management System"}))
    
api.add_resource(Index, "/")

if __name__=="__main__":
    app.run(port=5555, debug=True)