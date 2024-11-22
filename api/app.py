from flask import Flask, make_response, jsonify
from flask_restful import Api, Resource
from flask_migrate import Migrate
from flask_cors import CORS
import os

from api.models import db

app = Flask(__name__)

#Initializing the migration
migrate=Migrate(app, db)
db.init_app(app)

#Initializing the API
api=Api(app)

#Configuring CORS
CORS(app, origins=["http://localhost:3000", "https://rental-hive.vercel.app"])

# Configuring the database
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI")

class Index(Resource):
    def get(self):
        return make_response(jsonify({"message": "Welcome to Rent Hive Rental Management System"}))
    
api.add_resource(Index, "/")

if __name__=="__main__":
    app.run(port=5555, debug=True)