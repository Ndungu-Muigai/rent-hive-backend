from marshmallow import Schema, fields

class UserSchema(Schema):
    id = fields.Int(required=True)
    first_name=fields.Str(required=True)
    last_name=fields.Str(required=True)
    email=fields.Email(required=True)
    phone_number=fields.Str(required=True)

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
    images=fields.List(fields.Nested(ImageSchema))