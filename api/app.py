from flask import Flask, make_response, jsonify, request
from flask_restful import Api, Resource
from flask_migrate import Migrate
from flask_cors import CORS
from flask_session import Session
from datetime import timedelta

import os
import redis 
import json
import hashlib
import uuid

from api.models import db, Users
from Mail.credentials import send_login_credentials

app = Flask(__name__)

# Configuring the database
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI")

# Email sender configuration
app.config["SENDER_NAME"] = "Rent Hive Rental Management System"
app.config["SENDER_EMAIL"] = "rms@rent-hive.co.ke"
app.static_folder = 'static'
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
CORS(app, origins=["http://localhost:3000", "https://rent-hive.vercel.app"])

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

#Sign up resource
class SignUp(Resource):
    def post(self):

        #Getting the form details
        first_name=request.json["first_name"]
        last_name=request.json["last_name"]
        email=request.json["email"]
        phone_number=request.json["phone_number"]
        role=request.json["role"]
        password=request.json["password"]
        confirm_password=request.json["confirm_password"]

        #Checking if an account exists with the given email
        if Users.query.filter_by(email=email).first():
            return make_response(jsonify(
                {
                    "type":"error",
                    "message" : "An account with the given email already exists"
                }), 409)
        
        #Checking if the two passwords given match
        if password != confirm_password:
            return make_response(jsonify(
                {
                    "type":"error",
                    "message" : "The two passwords do not match"
                }
            ), 400)
        
        #Adding the details to the database
        try:
            #Creating a hashed password to be saved in the database
            hashed_password=hashlib.md5(password.encode("utf-8")).hexdigest()

            #Saving the info in the database
            new_user=Users(first_name=first_name, last_name=last_name, email=email, phone_number=phone_number, role=role, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()

            try:
                send_login_credentials(first_name=first_name,last_name=last_name, email=email, password=password)

            except Exception as e:
                print(f"Email error: {e}")
                return make_response(jsonify(
                    {
                    "type": "error",
                    "message": "Account created but failed to send email. Please check your email settings."
                }), 500)
            
            #Returning the response
            return make_response(jsonify(
                {
                    "type" : "success",
                    "message" : "Account created successfully!"
                }
            ))

        except:
            #Rolling back the database changes
            db.session.rollback()

            return make_response(jsonify(
                {
                    "type": "error",
                    "message": "An error occured while creating your account. Please try again later!"
                }
            ), 400)
        
api.add_resource(SignUp, "/sign-up")

#Login resource
class Login(Resource):
    def post(self):
        #Getting the credentials from the frontend
        email=request.json["email"]
        password=request.json["password"]

        #Checking if the account with the provided email exists
        user=Users.query.filter_by(email=email).first()
        if not user:
            return make_response(jsonify(
                {
                    "type" : "error",
                    "message" : "An account with the given email does not exist!"
                }
            ), 404)
        
        #Checking if the password given matches the password saved in the database
        elif user.password != hashlib.md5(password.encode("utf-8")).hexdigest():
            return make_response(jsonify(
                {
                    "type" : "error",
                    "message" : "Incorrect password!"
                }
            ), 409)
        
        #Creating a unique session identifier
        session_id=str(uuid.uuid4())

        # Storing session information in Redis with a unique key
        session_data={
            "user_id": user.id,
            "user_email" : user.email
        }

        # Set the session data in Redis with the unique session ID
        r.set(f"session:{session_id}", json.dumps(session_data))

        #Returning a success message once a user is successfully authenticated
        return make_response(jsonify(
            {
                "type" : "success",
                "message" : "Login successful"
            }
        ))

api.add_resource(Login, "/login")

if __name__=="__main__":
    app.run(port=5555, debug=True)