from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.orm import validates
from datetime import datetime
import psycopg2

db=SQLAlchemy()

class Users(db.Model):

    __tablename__= "users"

    id=db.Column(db.Integer, primary_key=True)
    first_name=db.Column(db.String, nullable=False)
    last_name=db.Column(db.String, nullable=False)
    email=db.Column(db.String, nullable=False, unique=True)
    phone_number=db.Column(db.String, unique=True, nullable=False)
    role=db.Column(db.String, nullable=False)
    password=db.Column(db.String, nullable=False)
    created_at=db.Column(db.DateTime, server_default=db.func.now())
    updated_at=db.Column(db.DateTime, server_default=db.func.now())

    properties=db.relationship("Properties", backref="owner", uselist=True, foreign_keys="[Properties.owner_id]")
    leases=db.relationship("Leases", backref="tenant", uselist=True, foreign_keys="[Leases.tenant_id]")
    invoices=db.relationship("Invoices", backref="tenant", uselist=True, foreign_keys="[Invoices.tenant_id]")

    def __repr__(self):
        return f"User('{self.first_name}', '{self.last_name}', '{self.email}')"
    
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

class Properties(db.Model):

    __tablename__ = "properties"

    id=db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String, nullable=False)
    description=db.Column(db.String, nullable=False)
    property_status=db.Column(db.Enum("Available", "Leased", name="property_status_enum"),nullable=False, default="Available")
    property_type=db.Column(db.String, nullable=False)
    location=db.Column(db.String, nullable=False)
    rent=db.Column(db.Integer, nullable=False)
    deposit_required=db.Column(db.Boolean, nullable=False, default=False)
    owner_id=db.Column(db.Integer, db.ForeignKey('users.id'))
    tenant_id=db.Column(db.Integer, db.ForeignKey('users.id'))

    images=db.relationship("Images", backref="property", uselist=True)

class Images(db.Model):

    __tablename__ = "images"

    id=db.Column(db.Integer, primary_key=True)
    image_url=db.Column(db.String, nullable=False)
    property_id=db.Column(db.Integer, db.ForeignKey('properties.id'))

class Leases(db.Model):

    __tablename__ = 'leases'

    id=db.Column(db.Integer, primary_key=True)
    start_date=db.Column(db.Date, nullable=False)
    end_date=db.Column(db.Date, nullable=False)
    duration=db.Column(db.String, nullable=False)
    rent_amount=db.Column(db.Float, nullable=False)
    deposit_amount=db.Column(db.Float, nullable=False)
    tenant_id=db.Column(db.Integer, db.ForeignKey('users.id'))
    owner_id=db.Column(db.Integer, db.ForeignKey('users.id'))
    property_id=db.Column(db.Integer, db.ForeignKey('properties.id'))

    # Relationship to fetch property details
    property = db.relationship("Properties", backref="leases")

class Invoices(db.Model):

    __tablename__ = "invoices"

    ref_no = db.Column(db.String, primary_key=True)
    amount=db.Column(db.Float, nullable=False)
    invoice_date=db.Column(db.Date, nullable=False)
    due_date=db.Column(db.Date, nullable=False)
    balance=db.Column(db.Float, nullable=True)
    description=db.Column(db.String, nullable=False)
    property_id=db.Column(db.Integer, db.ForeignKey('properties.id'), nullable=False)
    tenant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    lease_id=db.Column(db.Integer, db.ForeignKey('leases.id'), nullable=False)

    payments=db.relationship("Payments", backref="invoice", uselist=True)

#Function to generate the invoice no
def generate_invoice_no():
    last_invoice=db.session.query(Invoices).order_by(Invoices.ref_no.desc()).first()
    if last_invoice:
        last_ref_no=last_invoice.ref_no
        last_number=int(last_ref_no[3:])
        new_number = last_number + 1
    else:
        new_number=1

    return f"INV{new_number:04}"

#Listener for the Invoices model to automatically generate ref no before inserting the data
@event.listens_for(Invoices, 'before_insert')
def generate_ref_no(mapper, connection, target):
    target.ref_no=generate_invoice_no()
    
class Payments(db.Model):

    __tablename__ = "payments"

    payment_ref_no=db.Column(db.String, primary_key=True)
    invoice_ref_no=db.Column(db.String, db.ForeignKey('invoices.ref_no'))
    mode_of_payment=db.Column(db.String, nullable=False)
    payment_date=db.Column(db.DateTime, nullable=False)
    amount=db.Column(db.Float, nullable=False)