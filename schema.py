from marshmallow import Schema, fields

class UserSchema(Schema):
    id = fields.Int(required=True)
    first_name=fields.Str(required=True)
    last_name=fields.Str(required=True)
    email=fields.Email(required=True)
    phone_number=fields.Str(required=True)
    role=fields.Str(required=True)

class ImageSchema(Schema):
    id = fields.Int(required=True)
    image_url=fields.Str(required=True)
    property_id=fields.Integer(required=True)

class PropertySchema(Schema):
    id=fields.Integer()
    name=fields.Str(required=True)
    description=fields.Str(required=True)
    property_status=fields.Str(required=True)
    property_type=fields.Str(required=True)
    location=fields.Str(required=True)
    rent=fields.Float(required=True)
    deposit_required=fields.Boolean(required=True)
    images=fields.List(fields.Nested(ImageSchema(only=("id", "image_url"))))

class InvoiceSchema(Schema):
    ref_no=fields.Str(required=True)
    amount=fields.Float(required=True)
    invoice_date=fields.Date(required=True)
    due_date=fields.Date(required=True)
    balance=fields.Float(required=True)
    description=fields.Str(required=True)
    
class LeaseSchema(Schema):
    id=fields.Integer(required=True)
    start_date=fields.Date(required=True)
    end_date=fields.Date(required=True)
    duration=fields.Str(required=True)
    rent_amount=fields.Float(required=True)
    deposit_amount=fields.Float(required=True)
    tenant=fields.Nested(UserSchema(only=("id", "first_name", "last_name", "email", "phone_number")))
    owner=fields.Nested(UserSchema(only=("id", "first_name", "last_name", "email", "phone_number")))
    property=fields.Nested(PropertySchema(only=("id", "name", "description","location", "images", "property_type")))