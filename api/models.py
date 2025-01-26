from flask_sqlalchemy import SQLAlchemy

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
    deposit_required=db.Column(db.Boolean, default=False)
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
    start_date=db.Column(db.DateTime, nullable=False)
    end_date=db.Column(db.DateTime, nullable=False)
    rent_amount=db.Column(db.Float, nullable=False)
    deposit_amount=db.Column(db.Float, nullable=False)
    tenant_id=db.Column(db.Integer, db.ForeignKey('users.id'))
    property_id=db.Column(db.Integer, db.ForeignKey('properties.id'))

class Invoices(db.Model):

    __tablename__ = "invoices"

    ref_no=db.Column(db.String, primary_key=True)
    amount=db.Column(db.Float, nullable=False)
    invoice_date=db.Column(db.DateTime, nullable=False)
    due_date=db.Column(db.DateTime, nullable=False)
    balance=db.Column(db.Float, nullable=True)
    property_id=db.Column(db.Integer, db.ForeignKey('properties.id'))
    lease_id=db.Column(db.Integer, db.ForeignKey('leases.id'))

    payments=db.relationship("Payments", backref="invoice", uselist=True)

class Payments(db.Model):

    __tablename__ = "payments"

    payment_ref_no=db.Column(db.String, primary_key=True)
    invoice_ref_no=db.Column(db.String, db.ForeignKey('invoices.ref_no'))
    mode_of_payment=db.Column(db.String, nullable=False)
    payment_date=db.Column(db.DateTime, nullable=False)
    amount=db.Column(db.Float, nullable=False)