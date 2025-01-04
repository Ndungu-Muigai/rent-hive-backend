from flask import Flask, make_response, jsonify, request
from flask_restful import Api, Resource
from flask_migrate import Migrate
from flask_cors import CORS
from flask_session import Session
from datetime import timedelta
from werkzeug.utils import secure_filename

import boto3
import os
import redis 
import json
import hashlib
import uuid

from schema import UserSchema, PropertySchema, ImageSchema
from api.models import db, Users, Properties, Images, Leases, Invoices, Payments
from Mail.credentials import send_login_credentials

app = Flask(__name__)

# Configuring the database
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI")

# Email sender configuration
app.config["SENDER_NAME"] = "Rent Hive Rental Management System"
app.config["SENDER_EMAIL"] = "rms@rent-hive.co.ke"

# Configuring redis
r = redis.from_url("rediss://red-cs2f4956l47c73bgt4c0:vfHKfN8YalQnHnhGXV01tooGpCe8ugtf@oregon-redis.render.com:6379")
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config["SESSION_TYPE"] = "redis"
app.config['SESSION_REDIS'] = r
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# AWS S3 configuration
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("S3_REGION")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")

s3 = boto3.client("s3", region_name=S3_REGION, aws_access_key_id=S3_ACCESS_KEY, aws_secret_access_key=S3_SECRET_ACCESS_KEY)

#Initializing the migration
migrate=Migrate(app, db)
db.init_app(app)

#Initializing the API
api=Api(app)

#Initializing the session
Session(app)

#Configuring CORS
CORS(app, origins=["http://localhost:3000", "https://rent-hive.vercel.app"])

# Function to extract session data
def get_session_data():
    if request.path == "/logout":
        return None  # Skip validation for logout
    
    session_id = request.headers.get("X-Session-ID")

    if not session_id:
        raise ValueError("Session ID is missing from the request headers.")
    
    session_data = r.get(f"session:{session_id}")

    if not session_data:
        raise ValueError("Invalid or expired session. Kindly login to continue.")
    
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
            print("An account with the given email already exists")
            return make_response(jsonify(
                {
                    "type":"error",
                    "message" : "An account with the given email already exists"
                }), 409)
        
        #Checking if the two passwords match
        if password != confirm_password:
            print("Passwords do not match")
            return make_response(jsonify(
                {
                    "type":"error",
                    "message" : "Passwords do not match"
                }
            ),409)
        #Adding the details to the database
        try:
            #Creating a hashed password to be saved in the database
            hashed_password=hashlib.md5(password.encode("utf-8")).hexdigest()

            #Saving the info to the database
            new_user=Users(first_name=first_name, last_name=last_name, email=email, phone_number=phone_number, role=role, password=hashed_password)

            db.session.add(new_user)
            db.session.commit()

            try:
                #Sending the login credentials via email
                send_login_credentials(first_name=first_name,last_name=last_name, email=email, password=password)

                #Returning the response
                return make_response(jsonify(
                    {
                        "type" : "success",
                        "message" : "Account created successfully!"
                    }
                ),200)
            
            except Exception as e:
                print(f"Email error: {e}")
                db.session.rollback()
                return make_response(jsonify(
                    {
                    "type": "error",
                    "message": "Account created but failed to send email. Please check your email settings."
                }), 500)
            
        except Exception as e:
            print(e)
            #Rolling back the database changes
            db.session.rollback()
            return make_response(jsonify(
                {
                    "type": "error",
                    "message": "An error occured while creating your account. Please try again later!"
                }
            ),400)
        
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
            "user_email" : user.email,
            "user_role" : user.role
        }

        # Set the session data in Redis with the unique session ID
        r.set(f"session:{session_id}", json.dumps(session_data))

        #Returning a success message once a user is successfully authenticated
        return make_response(jsonify(
            {
                "type" : "success",
                "session_id": session_id,
                "message" : "Login successful"
            }
        ),200)

api.add_resource(Login, "/login")

class Dashboard(Resource):
    def get(self):
        #Getting the session ID from the frontend
        session_data=get_session_data()

        #Extracting the data
        user_id=session_data["user_id"]
        user_role=session_data["user_role"]

        #Getting the user's full name
        user=Users.query.filter_by(id=user_id).first()

        #Returning a response to the frontend
        return make_response(jsonify(
            {
                "type" : "success",
                "role": user_role,
                "fullName" : user.full_name()
            }),200)
    
api.add_resource(Dashboard, "/dashboard")

#Property resource
class Property(Resource):
    def get(self):
        #Getting the session ID from the frontend
        session_data=get_session_data()

        #Extracting the user ID and role
        user_id=session_data["user_id"]
        user_role=session_data["user_role"]

        #If the role is not an owner, return an error
        if user_role != "owner":
            return make_response(jsonify(
                {
                    "type" : "error",
                    "message" : "You are not an owner"
                }
            ),409)
        
        #Getting the properties of the said owner
        properties=Properties.query.filter_by(owner_id=user_id).all()
        print(properties)

        #Creating a schema for the properties
        property_schema=PropertySchema().dump(properties, many=True)

        print(property_schema)

        #Returning a response to the front end
        return make_response(jsonify(
        {
            "type" : "success",
            "properties" : property_schema
        }),200)
    
    def post(self):
        # Getting the data from the front end
        name = request.form.get("name")
        description = request.form.get("description")
        property_type = request.form.get("property_type")
        location = request.form.get("location")
        rent = request.form.get("rent")
        images = request.files.getlist("images")  # Get a list of images

        print(name)
        print(description)
        print(property_type)
        print(location)
        print(rent)

        # Checking if the property already exists in the database
        property = Properties.query.filter_by(name=name).first()

        if property:
            return make_response(jsonify(
                {
                    "type": "error",
                    "message": "Property already exists"
                }), 409)

        try:
            # If it doesn't exist, add it to the database
            new_property = Properties(name=name, property_type=property_type, description=description, location=location, rent=rent)
            db.session.add(new_property)
            db.session.commit()

            # Iterate over each image
            for image in images:
                # Getting the image file name
                image_name = secure_filename(image.filename)
                # Generating a unique ID for each image
                unique_image_name = str(uuid.uuid1()) + "_" + image_name

                # Setting the path to the images folder in the S3 bucket
                s3_path = f"images/{unique_image_name}"

                # Uploading the image to the S3 bucket
                s3.upload_fileobj(image, "images", s3_path)

                # Adding the image to the database
                new_image = Images(property_id=new_property.id, image_path=s3_path)
                db.session.add(new_image)

            # Commit all changes after processing all images
            db.session.commit()

            # Returning a response to the frontend
            return make_response(jsonify(
                {
                    "type": "success",
                    "message": "Property added successfully!"
                }), 200)

        except Exception as e:
            print(e)
            # Rolling back the database changes
            db.session.rollback()
            return make_response(jsonify(
                {
                    "type": "error",
                    "message": "Error uploading images. Please try again later!"
                }), 409)
            
api.add_resource(Property, "/properties")

#Logout resource
class Logout(Resource):
    def post(self):
        try:
            session_id = request.headers.get("X-Session-ID")
            if session_id:
                r.delete(f"session:{session_id}")  # Explicitly clear Redis session
            return make_response(jsonify(
            {
                "type": "success",
                "message": "Logged out successfully."
            }), 200)
        except Exception as e:
            return make_response(jsonify({
                "type": "error",
                "message": str(e)
            }), 500)
api.add_resource(Logout, "/logout")

if __name__=="__main__":
    app.run(port=5555, debug=True)