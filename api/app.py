from flask import Flask, make_response, jsonify, request
from flask_restful import Api, Resource
from flask_migrate import Migrate
from flask_cors import CORS
from flask_session import Session
from datetime import timedelta, datetime
from werkzeug.utils import secure_filename

import boto3
import os
import redis 
import json
import hashlib
import uuid

from schema import UserSchema, PropertySchema, ImageSchema, InvoiceSchema, LeaseSchema
from api.models import db, Users, Properties, Images, Leases, Invoices, Payments
from api.Invoices import generate_monthly_invoices
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
            new_user=Users(first_name=first_name.capitalize(), last_name=last_name.capitalize(), email=email, phone_number=phone_number, role=role, password=hashed_password)

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

        #Creating a response dictionary
        response={
            "fullName": user.full_name(),
            "role": user_role
        }

        #Getting the number of properties the owner has
        if user_role == "Owner":
            #Getting the total number of properties the owner has
            properties=Properties.query.filter_by(owner_id=user_id).count()

            #Getting the total number of tenants the home owner has
            tenants=db.session.query(Leases.tenant_id).filter_by(owner_id=user_id).distinct().count()

            #Getting the total number of units available
            available_units=Properties.query.filter_by(owner_id=user_id, property_status ="Available").count()

            #Getting the total number of the owner's leased properties
            leased_properties=Properties.query.filter_by(owner_id=user_id, property_status ="Leased").count()

            #Getting the leases whose leases are expiring in less than 30 days, between 31 and 60 days and the ones that are expiring after 61+days from today
            today=datetime.today()

            # Get the leases expiring in less than 30 days
            expiring_leases_30_days = Leases.query.filter(Leases.owner_id == user_id, Leases.end_date <= today + timedelta(days=30)).count()

            # Get the leases expiring between 31 and 60 days
            expiring_leases_31_60_days = Leases.query.filter(Leases.owner_id == user_id,Leases.end_date > today + timedelta(days=30),Leases.end_date <= today + timedelta(days=60)).count()

            # Get the leases expiring after 61+ days
            expiring_leases_61_plus_days = Leases.query.filter(Leases.owner_id == user_id,Leases.end_date > today + timedelta(days=60)).count()

            #Adding to the response array
            response["type"]="success"
            response["properties"]=properties
            response["tenants"]=tenants
            response["vacant"]=available_units
            response["rented"]=leased_properties
            response["expiring_30_days"]=expiring_leases_30_days
            response["expiring_31_60_days"]=expiring_leases_31_60_days
            response["expiring_61_plus_days"]=expiring_leases_61_plus_days

        #Getting the number of tenants, properties and owners in the database for the admins
        elif user_role == "Admin":
            owners=Users.query.filter_by(role="Owner").count()
            tenants=Users.query.filter_by(role="Tenant").count()
            properties=Properties.query.count()

            #Getting the occupied and vacant properties
            occupied_properties=Properties.query.filter_by(property_status="Leased").count()
            vacant_properties=Properties.query.filter_by(property_status="Available").count()

            #Adding the data to the response dict
            response["type"]="success"
            response["owners"]=owners
            response["tenants"]=tenants
            response["properties"]=properties
            response["occupied"]=occupied_properties
            response["vacant"]=vacant_properties

        elif user_role == "Tenant":
            #Getting the pending invoices
            pending_invoices=Invoices.query.filter(Invoices.tenant_id==user_id, Invoices.balance > 0).all()

            #Adding together the pending amount
            pending_amount=0
            for invoice in pending_invoices:
                pending_amount+=invoice.amount

            #Getting the tenant's leased properties
            leased_properties=Properties.query.filter_by(tenant_id=user_id, property_status="Leased").count()

            #Getting the leases whose leases are expiring in less than 30 days, between 31 and 60 days and the ones that are expiring after 61+days from today
            today=datetime.today()

            # Get the leases expiring in less than 30 days
            expiring_leases_30_days = Leases.query.filter(Leases.tenant_id == user_id, Leases.end_date <= today + timedelta(days=30)).count()

            # Get the leases expiring between 31 and 60 days
            expiring_leases_31_60_days = Leases.query.filter(Leases.tenant_id == user_id,Leases.end_date > today + timedelta(days=30),Leases.end_date <= today + timedelta(days=60)).count()

            # Get the leases expiring after 61+ days
            expiring_leases_61_plus_days = Leases.query.filter(Leases.tenant_id == user_id,Leases.end_date > today + timedelta(days=60)).count()

            response["type"]="success"
            response["rent_due"]=pending_amount
            response["leased_properties"]=leased_properties
            response["expiring_30_days"]=expiring_leases_30_days
            response["expiring_31_60_days"]=expiring_leases_31_60_days
            response["expiring_61_plus_days"]=expiring_leases_61_plus_days
            
        else:
            #Adding to the response array
            response["type"]="success"
        
        return make_response(jsonify(response),200)
    
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
        if user_role != "Owner":
            return make_response(jsonify(
                {
                    "type" : "error",
                    "reason": "Invalid credentials",
                    "message" : "You are not an owner"
                }
            ),409)
        
        #Getting the properties of the said owner
        properties=Properties.query.filter_by(owner_id=user_id).all()

        #Creating a schema for the properties
        property_schema=PropertySchema(many=True, only=('id', 'name', 'description','images')).dump(properties)

        #Returning a response to the front end
        return make_response(jsonify(
        {
            "type" : "success",
            "properties" : property_schema
        }),200)
    
    def post(self):

        # Getting the session ID from the frontend
        session_data = get_session_data()

        # Extracting the user ID and role
        user_id = session_data["user_id"]
        user_role = session_data["user_role"]

        # If the role is not an owner, return an error
        if user_role != "Owner":
            return make_response(jsonify(
                {
                    "type": "error",
                    "message": "You are not an owner"
                }
            ), 409)

        # Getting the data from the front end
        name = request.form.get("name")
        description = request.form.get("description")
        property_type = request.form.get("property_type")
        location = request.form.get("location")
        rent = request.form.get("rent")
        images = request.files.getlist("images[]")  # Get a list of images
        deposit = request.form.get("deposit")

        # Checking if the property already exists in the database
        property = Properties.query.filter_by(name=name).first()

        if property:
            return make_response(jsonify(
                {
                    "type": "error",
                    "message": "Property already exists"
                }), 409)

        try:
            #Saving the deposit as a Boolean based on the form input
            if deposit == "Yes":
                deposit = True
            
            elif deposit == "No":
                deposit = False

            # Create a new property but do not commit yet
            new_property = Properties(name=name, property_type=property_type, description=description, location=location, rent=rent, owner_id=user_id, deposit_required=deposit)
            db.session.add(new_property)
            db.session.commit()

            # Iterate over each image and upload it to S3
            for image in images:
                # Getting the image file name
                image_name = secure_filename(image.filename)
                # Generating a unique ID for each image
                unique_image_name = str(uuid.uuid1()) + "_" + image_name

                # Setting the path to the images folder in the S3 bucket
                s3_path = f"products/{unique_image_name}"

                try:
                    # Uploading the image to the S3 bucket
                    s3.upload_fileobj(image, S3_BUCKET_NAME, s3_path)

                    # Add the image to the database if upload is successful
                    new_image = Images(property_id=new_property.id, image_url=s3_path)
                    db.session.add(new_image)
                except Exception as e:
                    print(f"Error uploading image {image_name}: {e}")
                    # If any image upload fails, rollback the entire transaction
                    db.session.rollback()
                    return make_response(jsonify(
                        {
                            "type": "error",
                            "message": "Error uploading images. Please try again later!"
                        }), 409)

            # Commit the images to the database after all images are successfully uploaded
            db.session.commit()

            # Returning a response to the frontend
            return make_response(jsonify(
                {
                    "type": "success",
                    "message": "Property added successfully!"
                }), 200)

        except Exception as e:
            print(f"Error processing property: {e}")
            # If there's any error during property creation, rollback the entire transaction
            db.session.rollback()
            return make_response(jsonify(
                {
                    "type": "error",
                    "message": "Error processing property. Please try again later!"
                }), 409)

api.add_resource(Property, "/properties")

#Getting a property by ID
class PropertyByID(Resource):
    def get(self, id):
        #Getting the session ID from the frontend
        session_data=get_session_data()

        #Extracting the user ID and role
        user_id=session_data["user_id"]
        user_role=session_data["user_role"]

        #If the role is not an owner, return an error
        if user_role != "Owner":
            return make_response(jsonify(
                {
                    "type" : "error",
                    "reason": "Invalid credentials",
                    "message" : "You are not an owner"
                }
            ),409)
        
        #Getting the property by ID
        property=Properties.query.filter_by(id=id).first()

        #Creating a schema for the properties
        property_schema=PropertySchema().dump(property)

        
        #Fetching the tenant and lease details if available for the property
        if property.property_status == "Leased":

            #Fetching the tenant from the database
            tenant=Users.query.filter_by(id=property.tenant_id).first()

            #Converting it into a JSON schema
            tenant_schema=UserSchema(only=('first_name', 'last_name' ,'email', 'phone_number')).dump(tenant)

            #Fetching the lease details from the database
            lease=Leases.query.filter_by(property_id=property.id).first()

            #Converting it into a JSON schema
            lease_schema=LeaseSchema(only=("start_date","end_date", "duration")).dump(lease)

            #Creating the response
            return make_response(jsonify(
            {
                "property" : property_schema,
                "tenant" : tenant_schema,
                "lease" : lease_schema
            }))

        #Creating the response
        return make_response(jsonify(
        {
            "property" : property_schema
        }))

api.add_resource(PropertyByID, "/properties/<int:id>")

#Getting all available properties for the tenants
class AvailableProperties(Resource):
    def get(self):

        #Getting the session ID from the frontend
        session_data=get_session_data()

        # Extracting the user ID and role
        user_role = session_data["user_role"]

        # If the role is not a tenant, return an error
        if user_role != "Tenant":
            return make_response(jsonify(
                {
                    "type": "error",
                    "reason": "Invalid credentials",
                    "message": "You are not a tenant"
                }
            ), 409)

        #Getting the list of available properties
        available_properties = Properties.query.filter_by(property_status="Available").all()

        #Creating a schema for the properties
        property_schema=PropertySchema(many=True).dump(available_properties)

        #Returning a response to the front end
        return make_response(jsonify(
        {
            "type" : "success",
            "properties" : property_schema
        }),200)

api.add_resource(AvailableProperties, "/available-properties")

#Getting the available properties by ID
class AvailablePropertiesByID(Resource):
    def get(self, id):

        #Getting the session ID from the frontend
        session_data=get_session_data()

        # Extracting the user ID and role
        user_role = session_data["user_role"]

        # If the role is not a tenant, return an error
        if user_role != "Tenant":
            return make_response(jsonify(
                {
                    "type": "error",
                    "reason": "Invalid credentials",
                    "message": "You are not a tenant"
                }
            ), 409)

        #Getting the individual property by ID
        property = Properties.query.filter_by(id=id).first()

        #If property doesn't exist, return an error
        if property is None:
            return make_response(jsonify(
                {
                    "type" : "error",
                    "reason" : "Not found",
                    "message" : "Property doesn't exist!"
                }
            ),404)

        #Creating the property schema
        property_schema=PropertySchema().dump(property)

        #Getting the owner's details
        owner = Users.query.filter_by(id=property.owner_id).first()

        #Creating a schema of the owner
        owner_schema=UserSchema(only=("first_name", "last_name", "email", "phone_number")).dump(owner)

        #Returning the response to the frontend
        return make_response(jsonify(
            {
                "type" : "success",
                "property" : property_schema,
                "owner": owner_schema
            }
        ), 200)

api.add_resource(AvailablePropertiesByID, "/available-properties/<int:id>")

#Creating a lease
class Lease(Resource):
    def get(self):
        #Getting the session details
        session_data = get_session_data()
        user_id = session_data["user_id"]
        user_role = session_data["user_role"]

        #If the role is not a tenant, return an error
        if user_role != "Tenant":
            return make_response(jsonify(
            {
                "type" : "error",
                "reason" : "Invalid credentials",
                "message" : "You are not a tenant"
            }),409)
        
        #Getting the tenants leases
        tenant_leases=Leases.query.filter_by(tenant_id=user_id).all()

        #Creating a schema to return the leases to the front-end
        tenant_leases_schema=LeaseSchema(many=True, only=("id", "property", "start_date", "duration", "rent_amount")).dump(tenant_leases)

        #Returning the response
        return make_response(jsonify(
            {
                "type" : "success",
                "leases": tenant_leases_schema
            }
        ),200)

    def post(self):

        #Getting the session data
        session_data = get_session_data()
        user_id = session_data["user_id"]
        user_role = session_data["user_role"]

        if user_role != "Tenant":
            return make_response(jsonify({
                "type": "error",
                "reason": "Invalid credentials",
                "message": "You are not a tenant"
            }), 409)

        # Get request data
        property_id = request.json.get("property_id")
        start_date = request.json.get("start_date")
        end_date = request.json.get("end_date")
        duration=request.json.get("duration")

        # Validate property
        property = Properties.query.filter_by(id=property_id).first()
        if not property:
            return make_response(jsonify({
                "type": "error",
                "message": "Property not found"
            }), 404)

        rent = property.rent
        deposit = rent if property.deposit_required else 0

        try:
            # Create lease
            new_lease = Leases(start_date=start_date, rent_amount=rent, deposit_amount=deposit, property_id=property_id, end_date=end_date, tenant_id=user_id, duration=duration, owner_id=property.owner.id)
            db.session.add(new_lease)

            # Update property status
            property.tenant_id = user_id
            property.property_status = "Leased"
            db.session.commit()

            # Create invoice if deposit is required
            if deposit > 0:
                new_invoice = Invoices(amount=deposit, invoice_date=datetime.utcnow(),
                due_date=datetime.utcnow() + timedelta(days=30),balance=deposit, description=f"Rent deposit for property {property_id}",property_id=property_id, tenant_id=user_id,lease_id=new_lease.id)

                db.session.add(new_invoice)
                db.session.commit()

            return make_response(jsonify(
            {
                "type": "success",
                "message": "Lease created successfully"
            }), 200)

        except Exception as e:
            print("Error creating lease:", str(e))
            db.session.rollback()  # Rollback changes on failure
            return make_response(jsonify(
            {
                "type": "error",
                "message": "Error when creating the lease. Please try again later",
                "details": str(e)
            }), 500)

api.add_resource(Lease, "/lease")

#Lease by ID resource
class LeaseByID(Resource):
    def get(self, id):

        #Getting the session ID from the frontend
        session_data=get_session_data()

        # Extracting the user ID and role
        user_role = session_data["user_role"]

        #If the logged in user is not a tenant, return an error
        if user_role != "Tenant":
            return make_response(jsonify({
                "type": "error",
                "reason": "Invalid credentials",
                "message": "You are not a tenant"
            }), 409)

        #QUerying the lease table based on the given ID
        lease = Leases.query.filter_by(id=id).first()

        #If the lease doesn't exist, return an error
        if not lease:
            return make_response(jsonify(
            {
                "type": "error",
                "message": "Lease could not be found",
                "reason" : "Lease not found"
            }),404)
        
        #Creating a schema of the lease details
        lease_schema = LeaseSchema().dump(lease)
        print(lease_schema)

        #Returning the lease to the frontend

        return make_response(jsonify(
            {
                "type": "success",
                "lease": lease_schema
            }
        ))

api.add_resource(LeaseByID, "/leases/<int:id>")

#Invoices resource
class Invoice(Resource):
    def get(self):

        #Getting the session data
        session_data = get_session_data()
        user_id = session_data["user_id"]
        user_role = session_data["user_role"]

        if user_role != "Tenant":
            return make_response(jsonify(
            {
                "type": "error",
                "reason": "Invalid credentials",
                "message": "You are not a tenant"
            }), 409)
        
        #Getting the invoices for the logged in tenant
        tenant_invoices=Invoices.query.filter_by(tenant_id=user_id).all()

        print(tenant_invoices)

        #Creating a schema for the invoices
        invoices_schema=InvoiceSchema(many=True).dump(tenant_invoices)

        #Creating a response
        return make_response(jsonify(
            {
                "type" : "success",
                "invoices": invoices_schema
            }
        ),200)
    
api.add_resource(Invoice, "/invoices")

#Generating invoices monthly
class GenerateInvoice(Resource):
    def get(self):
        generate_monthly_invoices()

api.add_resource(GenerateInvoice, "/generate-invoice")

#Admin end points

#Owners endpoint
class Owners(Resource):
    def get(self):

        #Getting the session data
        session_data = get_session_data()
        user_role = session_data["user_role"]

        if user_role != "Admin":
            return make_response(jsonify(
            {
                "type": "error",
                "reason": "Invalid credentials",
                "message": "You don't have the permissions to view this page"
            }), 409)

        #Querying the users table to get all the owners
        owners=Users.query.filter_by(role = "Owner").all()

        #Creating a JSON schema for the owners
        owners_schema = UserSchema(many=True).dump(owners)

        #Getting the number of properties for each owner
        for index, owner in enumerate(owners):
            owner_properties = Properties.query.filter_by(owner_id=owner.id).count()

            owners_schema[index]["properties_listed"] = owner_properties

        #Returning the response to the frontend
        return make_response(jsonify(
            {
                "type" : "success",
                "owners": owners_schema
            }
        ),200)
    
    def post(self):

        #Getting the session data
        session_data = get_session_data()
        user_role = session_data["user_role"]

        if user_role != "Admin":
            return make_response(jsonify(
            {
                "type": "error",
                "reason": "Invalid credentials",
                "message": "You don't have the permissions to view this page"
            }), 409)
        
        #Getting the data from the front end
        data = request.get_json()

        first_name=data.get("first_name")
        last_name=data.get("last_name")
        email=data.get("email")
        phone_number=data.get("phone_number")
        role=data.get("role")

        #Checking if an account with the given email exists
        existing_account = Users.query.filter_by(email=email).first()
        if existing_account:
            return make_response(jsonify(
                {
                    "type" : "error",
                    "message" : "An account with the given email already exists"
                }
            ), 409)
        
        #Checking if the phone number entered is in the database
        existing_phone_number = Users.query.filter_by(phone_number=phone_number).first()
        if existing_phone_number:
            return make_response(jsonify(
                {
                    "type" : "error",
                    "message" : "An account with the given phone number already exists"
                }
            ))
        
        try:
            #Generating a random password for the user
            password = str(uuid.uuid4())

            #Hashing the password
            hashed_password=hashlib.md5(password.encode("utf-8")).hexdigest()

            #If account doesn't exists, create the account
            new_owner=Users(first_name=first_name, last_name=last_name, email=email, phone_number=phone_number, role=role, password=hashed_password)

            db.session.add(new_owner)
            db.session.commit()

            try:
                #Sending the login credentials via email
                send_login_credentials(first_name=first_name,last_name=last_name, email=email, password=password)

                #Returning the response
                return make_response(jsonify(
                    {
                        "type" : "success",
                        "message" : "Owner account created successfully",
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
    
api.add_resource(Owners, "/owners")

#Owner by ID resource
class OwnerByID(Resource):
    def patch(self, id):

        #Getting the session data
        session_data = get_session_data()
        user_role = session_data["user_role"]

        if user_role != "Admin":
            return make_response(jsonify(
            {
                "type": "error",
                "reason": "Invalid credentials",
                "message": "You don't have the permissions to perform this action"
            }), 409)
        
        #Getting the owner from the database
        owner = Users.query.filter_by(id=id).first()

        #If no owner, return an error
        if not owner:
            return make_response(jsonify(
                {
                    "type" : "error",
                    "message" : "The owner account could not be found"
                }
            ), 404)

        #Getting the data from the frontend
        data = request.get_json()  # Get the entire JSON payload
        email = data.get("email")  # Extract email as a string
        phone_number = data.get("phone_number")

        try:

            #Updating the owner's details
            owner.email = email
            owner.phone_number = phone_number
            db.session.commit()

            return make_response(jsonify(
                {
                    "type" : "success",
                    "message" : "Owner details updated successfully"
                }
            ), 200)

        except Exception as e:
            print(e)
            #Roll back changes if error is encountered
            db.session.rollback()
            return make_response(jsonify(
                {
                    "type"  : "error",
                    "message" : "Error while updating details. Please try again later"
                }
            ), 500)
        
    def delete(self, id):
        
        #Getting the session data
        session_data = get_session_data()
        user_role = session_data["user_role"]

        if user_role != "Admin":
            return make_response(jsonify(
            {
                "type": "error",
                "reason": "Invalid credentials",
                "message": "You don't have the permissions to perform this action"
            }), 409)
        
        #Getting the owner from the database
        owner = Users.query.filter_by(id=id).first()

        #If no owner, return an error
        if not owner:
            return make_response(jsonify(
                {
                    "type" : "error",
                    "message" : "The owner account could not be found"
                }
            ), 404)

        try:
            # Deleting related properties
            owner_properties=Properties.query.filter_by(owner_id=id).all()

            #Deleting all leases related to the properties
            for prop in owner_properties:

                #Getting and deleting the leases for the properties
                leases = Leases.query.filter_by(property_id=prop.id).all()
                for lease in leases:
                    db.session.delete(lease)
                    db.session.commit()

                #Getting and deleting the invoices for the properties related to the owner
                invoices=Invoices.query.filter_by(property_id=prop.id).all()
                for invoice in invoices:
                    db.session.delete(invoice)
                    db.session.commit()

                #Getting and deleting the images for each property
                images = Images.query.filter_by(property_id=prop.id).all()
                for image in images:
                    db.session.delete(image)
                    db.session.commit()

                db.session.delete(prop)

            # Finally, deleting the owner
            db.session.delete(owner)
            db.session.commit()

            return make_response(jsonify(
                {
                    "type": "success",
                    "message": "User and related records deleted successfully"
                }), 200)

        except Exception as e:
            db.session.rollback()
            return make_response(jsonify(
                {
                    "type": "error",
                    "reason": "Database Error",
                    "message": str(e)
                }), 500)

api.add_resource(OwnerByID, "/owners/<int:id>")

#Admins endpoint
class Admins(Resource):
    def get(self):

        #Getting the session data
        session_data = get_session_data()
        user_role = session_data["user_role"]
        user_id = session_data["user_id"]

        if user_role != "Admin":
            return make_response(jsonify(
            {
                "type": "error",
                "reason": "Invalid credentials",
                "message": "You don't have the permissions to view this page"
            }), 409)

        #Querying the users table to get all the admins
        admins=Users.query.filter(Users.role == "Admin", Users.id!= user_id).all()

        #Creating a JSON schema for the admins
        admins_schema = UserSchema(many=True, only=('id', 'first_name', 'last_name', 'email', 'phone_number')).dump(admins)

        #Returning the response to the frontend
        return make_response(jsonify(
            {
                "type" : "success",
                "admins": admins_schema
            }
        ),200)
    
    def post(self):

        #Getting the session data
        session_data = get_session_data()
        user_role = session_data["user_role"]

        if user_role != "Admin":
            return make_response(jsonify(
            {
                "type": "error",
                "reason": "Invalid credentials",
                "message": "You don't have the permissions to view this page"
            }), 409)
        
        #Getting the data from the front end
        data = request.get_json()

        first_name=data.get("first_name")
        last_name=data.get("last_name")
        email=data.get("email")
        phone_number=data.get("phone_number")
        role=data.get("role")

        #Checking if an account with the given email exists
        existing_account = Users.query.filter_by(email=email).first()
        if existing_account:
            return make_response(jsonify(
                {
                    "type" : "error",
                    "message" : "An account with the given email already exists"
                }
            ), 409)
        
        #Checking if the phone number entered is in the database
        existing_phone_number = Users.query.filter_by(phone_number=phone_number).first()
        if existing_phone_number:
            return make_response(jsonify(
                {
                    "type" : "error",
                    "message" : "An account with the given phone number already exists"
                }
            ))
        
        try:
            #Generating a random password for the user
            password = str(uuid.uuid4())

            #Hashing the password
            hashed_password=hashlib.md5(password.encode("utf-8")).hexdigest()

            #If account doesn't exists, create the account
            new_admin=Users(first_name=first_name, last_name=last_name, email=email, phone_number=phone_number, role=role, password=hashed_password)

            db.session.add(new_admin)
            db.session.commit()

            try:
                #Sending the login credentials via email
                send_login_credentials(first_name=first_name,last_name=last_name, email=email, password=password)

                #Returning the response
                return make_response(jsonify(
                    {
                        "type" : "success",
                        "message" : "Owner account created successfully",
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
        
api.add_resource(Admins, "/admins")

#Admin by ID resource
class AdminByID(Resource):
    def patch(self, id):

        #Getting the session data
        session_data = get_session_data()
        user_role = session_data["user_role"]

        if user_role != "Admin":
            return make_response(jsonify(
            {
                "type": "error",
                "reason": "Invalid credentials",
                "message": "You don't have the permissions to perform this action"
            }), 409)
        
        #Getting the owner from the database
        admin = Users.query.filter_by(id=id).first()

        #If no owner, return an error
        if not admin:
            return make_response(jsonify(
                {
                    "type" : "error",
                    "message" : "The admin account could not be found"
                }
            ), 404)

        #Getting the data from the frontend
        data = request.get_json()  # Get the entire JSON payload
        email = data.get("email")  # Extract email as a string
        phone_number = data.get("phone_number")

        try:

            #Updating the owner's details
            admin.email = email
            admin.phone_number = phone_number
            db.session.commit()

            return make_response(jsonify(
                {
                    "type" : "success",
                    "message" : "Admin details updated successfully"
                }
            ), 200)

        except Exception as e:
            print(e)
            #Roll back changes if error is encountered
            db.session.rollback()
            return make_response(jsonify(
                {
                    "type"  : "error",
                    "message" : "Error while updating details. Please try again later"
                }
            ), 500)
        
    def delete(self, id):
        
        #Getting the session data
        session_data = get_session_data()
        user_role = session_data["user_role"]

        if user_role != "Admin":
            return make_response(jsonify(
            {
                "type": "error",
                "reason": "Invalid credentials",
                "message": "You don't have the permissions to perform this action"
            }), 409)
        
        #Getting the owner from the database
        admin = Users.query.filter_by(id=id).first()

        #If no owner, return an error
        if not admin:
            return make_response(jsonify(
                {
                    "type" : "error",
                    "message" : "The admin account could not be found"
                }
            ), 404)

        try:

            # Finally, deleting the owner
            db.session.delete(admin)
            db.session.commit()

            return make_response(jsonify(
                {
                    "type": "success",
                    "message": "User and related records deleted successfully"
                }), 200)

        except Exception as e:
            db.session.rollback()
            return make_response(jsonify(
                {
                    "type": "error",
                    "reason": "Database Error",
                    "message": str(e)
                }), 500)

api.add_resource(AdminByID, "/admins/<int:id>")

#Tenants endpoint
class Tenants(Resource):
    def get(self):

        #Getting the session data
        session_data = get_session_data()
        user_role = session_data["user_role"]

        if user_role != "Admin":
            return make_response(jsonify(
            {
                "type": "error",
                "reason": "Invalid credentials",
                "message": "You don't have the permissions to view this page"
            }), 409)

        #Querying the users table to get all the tenants
        tenants=Users.query.filter_by(role = "Tenant").all()

        #Creating a JSON schema for the owners
        tenants_schema = UserSchema(many=True).dump(tenants)

        #Getting the number of properties for each tenant
        for index, tenant in enumerate(tenants):
            tenant_properties = Properties.query.filter_by(tenant_id=tenant.id).count()

            tenants_schema[index]["properties_leased"] = tenant_properties

        #Returning the response to the frontend
        return make_response(jsonify(
            {
                "type" : "success",
                "tenants": tenants_schema
            }
        ),200)
    
    def post(self):
        #Getting the session data
        session_data = get_session_data()
        user_role = session_data["user_role"]

        if user_role != "Admin":
            return make_response(jsonify(
            {
                "type": "error",
                "reason": "Invalid credentials",
                "message": "You don't have the permissions to view this page"
            }), 409)
        
        #Getting the data from the front end
        data = request.get_json()

        first_name=data.get("first_name")
        last_name=data.get("last_name")
        email=data.get("email")
        phone_number=data.get("phone_number")
        role=data.get("role")

        #Checking if an account with the given email exists
        existing_account = Users.query.filter_by(email=email).first()
        if existing_account:
            return make_response(jsonify(
                {
                    "type" : "error",
                    "message" : "An account with the given email already exists"
                }
            ), 409)
        
        #Checking if the phone number entered is in the database
        existing_phone_number = Users.query.filter_by(phone_number=phone_number).first()
        if existing_phone_number:
            return make_response(jsonify(
                {
                    "type" : "error",
                    "message" : "An account with the given phone number already exists"
                }
            ))
        
        try:
            #Generating a random password for the user
            password = str(uuid.uuid4())

            #Hashing the password
            hashed_password=hashlib.md5(password.encode("utf-8")).hexdigest()

            #If account doesn't exists, create the account
            new_tenant=Users(first_name=first_name, last_name=last_name, email=email, phone_number=phone_number, role=role, password=hashed_password)

            db.session.add(new_tenant)
            db.session.commit()

            try:
                #Sending the login credentials via email
                send_login_credentials(first_name=first_name,last_name=last_name, email=email, password=password)

                #Returning the response
                return make_response(jsonify(
                    {
                        "type" : "success",
                        "message" : "Tenant account created successfully",
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

api.add_resource(Tenants, "/tenants")

#Individual tenant endpoint
class TenantByID(Resource):
    def patch(self, id):

        #Getting the session data
        session_data = get_session_data()
        user_role = session_data["user_role"]

        if user_role != "Admin":
            return make_response(jsonify(
            {
                "type": "error",
                "reason": "Invalid credentials",
                "message": "You don't have the permissions to perform this action"
            }), 409)
        
        #Getting the tenant from the database
        tenant = Users.query.filter_by(id=id).first()

        #If no tenant, return an error
        if not tenant:
            return make_response(jsonify(
                {
                    "type" : "error",
                    "message" : "The tenant account could not be found"
                }
            ), 404)

        #Getting the data from the frontend
        data = request.get_json()  # Get the entire JSON payload
        email = data.get("email")  # Extract email as a string
        phone_number = data.get("phone_number")

        try:

            #Updating the owner's details
            tenant.email = email
            tenant.phone_number = phone_number
            db.session.commit()

            return make_response(jsonify(
                {
                    "type" : "success",
                    "message" : "Tenant details updated successfully"
                }
            ), 200)

        except:

            #Roll back changes if error is encountered
            db.session.rollback()
            return make_response(jsonify(
                {
                    "type"  : "error",
                    "message" : "Error while updating details. Please try again later"
                }
            ), 500)
        
    def delete(self, id):
        
        #Getting the session data
        session_data = get_session_data()
        user_role = session_data["user_role"]

        if user_role != "Admin":
            return make_response(jsonify(
            {
                "type": "error",
                "reason": "Invalid credentials",
                "message": "You don't have the permissions to perform this action"
            }), 409)
        
        #Getting the owner from the database
        tenant = Users.query.filter_by(id=id).first()

        #If no owner, return an error
        if not tenant:
            return make_response(jsonify(
                {
                    "type" : "error",
                    "message" : "The tenant account could not be found"
                }
            ), 404)

        try:
            #Getting and deleting the leases related to the tenant
            leases = Leases.query.filter_by(tenant_id=id).all()
            for lease in leases:
                #Deleting the leases
                db.session.delete(lease)
                db.session.commit()

            #Getting the invoices for the tenant
            invoices = Invoices.query.filter_by(tenant_id=id).all()

            for invoice in invoices:
                #Getting the payments for each invoice
                payments = Payments.query.filter_by(invoice_ref_no=invoice.ef_no).all()

                #Deleting all the payments
                for payment in payments:
                    db.session.delete(payment)
                    db.session.commit()

                #Deleting the invoices
                db.session.delete(invoice)
                db.session.commit()
            
            #Deleting the tenant
            db.session.delete(tenant)
            db.session.commit()

            return make_response(jsonify(
                {
                    "type" : "success",
                    "message" : "Tenant details updated successfully"
                }
            ), 200)

        except Exception as e:
            db.session.rollback()
            return make_response(jsonify(
                {
                    "type": "error",
                    "reason": "Database Error",
                    "message": str(e)
                }), 500)
        
api.add_resource(TenantByID, "/tenants/<int:id>")

#Properties resource
class AdminProperties(Resource):
    def get(self):

        #Getting the session data
        session_data = get_session_data()
        user_role = session_data["user_role"]

        if user_role != "Admin":
            return make_response(jsonify(
            {
                "type": "error",
                "reason": "Invalid credentials",
                "message": "You don't have the permissions to view this page"
            }), 409)
        
        #Getting the list of all properties
        all_properties = Properties.query.all()

        #Creating a schema for the properties
        property_schema=PropertySchema(many=True, only=('id', 'name', 'description','images', 'rent')).dump(all_properties)

        #Getting a list of all home owners
        all_home_owners = Users.query.filter_by(role = "Owner").all()

        #Creating a schema for the owners
        owner_schema=UserSchema(many=True, only=('id', 'first_name', 'last_name')).dump(all_home_owners)

        #Returning a response to the front end
        return make_response(jsonify(
        {
            "type" : "success",
            "properties" : property_schema,
            "owners" : owner_schema
        }),200)
    
    def post(self):

        # Getting the session ID from the frontend
        session_data = get_session_data()

        # Extracting the user ID and role
        user_role = session_data["user_role"]

        # If the role is not an owner, return an error
        if user_role != "Admin":
            return make_response(jsonify(
                {
                    "type": "error",
                    "message": "You are not an owner"
                }
            ), 409)

        # Getting the data from the front end
        name = request.form.get("name")
        description = request.form.get("description")
        property_type = request.form.get("property_type")
        location = request.form.get("location")
        rent = request.form.get("rent")
        images = request.files.getlist("images[]")  # Get a list of images
        deposit = request.form.get("deposit")
        owner_id=request.form.get("owner_id")

        # Checking if the property already exists in the database
        property = Properties.query.filter_by(name=name).first()

        if property:
            return make_response(jsonify(
                {
                    "type": "error",
                    "message": "Property already exists"
                }), 409)

        try:
            #Saving the deposit as a Boolean based on the form input
            if deposit == "Yes":
                deposit = True
            
            elif deposit == "No":
                deposit = False

            # Create a new property but do not commit yet
            new_property = Properties(name=name, property_type=property_type, description=description, location=location, rent=rent, owner_id=owner_id, deposit_required=deposit)
            db.session.add(new_property)
            db.session.commit()

            # Iterate over each image and upload it to S3
            for image in images:
                # Getting the image file name
                image_name = secure_filename(image.filename)
                # Generating a unique ID for each image
                unique_image_name = str(uuid.uuid1()) + "_" + image_name

                # Setting the path to the images folder in the S3 bucket
                s3_path = f"products/{unique_image_name}"

                try:
                    # Uploading the image to the S3 bucket
                    s3.upload_fileobj(image, S3_BUCKET_NAME, s3_path)

                    # Add the image to the database if upload is successful
                    new_image = Images(property_id=new_property.id, image_url=s3_path)
                    db.session.add(new_image)
                except Exception as e:
                    print(f"Error uploading image {image_name}: {e}")
                    # If any image upload fails, rollback the entire transaction
                    db.session.rollback()
                    return make_response(jsonify(
                        {
                            "type": "error",
                            "message": "Error uploading images. Please try again later!"
                        }), 409)

            # Commit the images to the database after all images are successfully uploaded
            db.session.commit()

            # Returning a response to the frontend
            return make_response(jsonify(
                {
                    "type": "success",
                    "message": "Property added successfully!"
                }), 200)

        except Exception as e:
            print(f"Error processing property: {e}")
            # If there's any error during property creation, rollback the entire transaction
            db.session.rollback()
            return make_response(jsonify(
                {
                    "type": "error",
                    "message": "Error processing property. Please try again later!"
                }), 409)

api.add_resource(AdminProperties, "/all-properties")

#Profile resource
class Profile(Resource):
    def get(self):

        #Getting the session data
        session_data = get_session_data()
        user_id = session_data["user_id"]

        #Getting the user's details
        user=Users.query.filter_by(id=user_id).first()

        #If user doesn't exist, return an error
        if not user:
            return make_response(jsonify(
            {
                "type": "error",
                "reason": "User not found",
                "message": "User account not found"
            }), 404)

        #Creating the schema
        user_schema=UserSchema(only=('first_name','last_name','email','phone_number', 'role', 'profile_picture')).dump(user)

        #Returning the result to the frontend
        return make_response(jsonify(
        {
            "type" : "success",
            "user_details" : user_schema
        },200))
    
    #Updating the user password
    def post(self):
        #Getting the session data
        session_data = get_session_data()
        user_id = session_data["user_id"]

        #Getting the user's details
        user=Users.query.filter_by(id=user_id).first()

        #If user doesn't exist, return an error
        if not user:
            return make_response(jsonify(
            {
                "type": "error",
                "reason": "User not found",
                "message": "User account not found"
            }), 404)
        
        #Getting the details to be updated
        current_password=request.json.get("current_password")
        new_password=request.json.get("new_password")
        confirm_password=request.json.get("confirm_password")

        #Checking if the old password matches the password in the database
        current_password=hashlib.md5(current_password.encode("utf-8")).hexdigest()

        if current_password != user.password:
            return make_response(jsonify(
                {
                    "type" : "error",
                    "message" : "The value of the current password provided does not match your current password"
                }
            ),409)
        
        #Checking if the new password and confirm password match
        if new_password != confirm_password:
            return make_response(jsonify(
                {
                    "type" : "error",
                    "message" : "The new password and confirm password values do not match"
                }
            ),409)
        
        #Hashing the password
        new_password=hashlib.md5(new_password.encode("utf-8")).hexdigest()

        #Updating the password
        user.password=new_password
        db.session.add(user)
        db.session.commit()

        #Returning the response to the frontend
        return make_response(jsonify(
            {
                "type" : "success",
                "message" : "Password updated successfully"
            }
        ))
    
    #Updating the profile image
    def patch(self):
        #Getting the session data
        session_data = get_session_data()
        user_id = session_data["user_id"]

        #Getting the user's details
        user=Users.query.filter_by(id=user_id).first()

        #If user doesn't exist, return an error
        if not user:
            return make_response(jsonify(
            {
                "type": "error",
                "reason": "User not found",
                "message": "User account not found"
            }), 404)
        
        #Getting the image 
        profile_image = request.files.get("profile_image")

        #Extracting the file name
        image_file_name=profile_image.filename

        #Generating a unique file name
        unique_profile_image_name = str(uuid.uuid1()) + "_" + image_file_name

        #Path to the folder in the s3 bucket
        s3_path = f"images/{unique_profile_image_name}"

        #Checking if the user has a profile image. If image exists, delete it from the database and from the S3 bucket
        if user.profile_picture:
            old_s3_path = f"images/{user.profile_picture}"

            # Delete the old image from S3
            try:
                s3.delete_object(Bucket=S3_BUCKET_NAME, Key=old_s3_path)

            except Exception as e:
                return make_response(jsonify(
                    {
                        "type": "error",
                        "message": "Error deleting old profile image. Please try again later!"
                    }), 500)
            
        #Upload the image to S3 and add the URL to the database
        try:
            s3.upload_fileobj(profile_image, S3_BUCKET_NAME, s3_path)

            user.profile_picture=unique_profile_image_name
            db.session.add(user)
            db.session.commit()

            #Returning the response
            return make_response(jsonify(
                {
                    "type": "success",
                    "message": "Profile picture updated successfully!"
                }), 200)
        except Exception as e:
            return make_response(jsonify(
                {
                    "type": "error",
                    "message": "Error uploading file. Please try again later!"
                }), 500)
            
api.add_resource(Profile, "/profile")

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