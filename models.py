from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Pincode(db.Model):
    __tablename__ = 'pincodes'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pincode = db.Column(db.String(6), index=True, nullable=False)
    post_office = db.Column(db.String(100), nullable=True)
    delivery_status = db.Column(db.String(20), nullable=True)
    division = db.Column(db.String(100), nullable=True)
    region = db.Column(db.String(100), nullable=True)
    circle = db.Column(db.String(100), nullable=True)
    taluk = db.Column(db.String(100), nullable=True)
    district_name = db.Column(db.String(100), nullable=True)
    state_name = db.Column(db.String(100), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "pincode": self.pincode,
            "post_office": self.post_office,
            "delivery_status": self.delivery_status,
            "division": self.division,
            "region": self.region,
            "circle": self.circle,
            "taluk": self.taluk,
            "district_name": self.district_name,
            "state_name": self.state_name
        }

class ApiLog(db.Model):
    __tablename__ = 'api_logs'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pincode_queried = db.Column(db.String(6), nullable=True)
    endpoint = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ip_address = db.Column(db.String(45), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "pincode_queried": self.pincode_queried,
            "endpoint": self.endpoint,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "ip_address": self.ip_address
        }
