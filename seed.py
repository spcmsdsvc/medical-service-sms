from app import app, db, Engineer, Client, Product, Shift
from datetime import datetime, timedelta

def seed_database():
    with app.app_context():
        print("Resetting database...")
        db.drop_all()
        db.create_all()

        # 1. Engineers
        e1 = Engineer(name="Robert Wong Rio", initials="RWR")
        e2 = Engineer(name="Sarah Jane Doe", initials="SJD")
        db.session.add_all([e1, e2])
        
        # 2. Clients
        c1 = Client(name="Mercy Hospital", address="123 Med St", contact_person="Dr. House", contact_number="555-0101", email_address="house@mercy.com")
        db.session.add(c1)
        db.session.commit() # Save to get ID

        # 3. Products (Using Serial Number as Primary Key)
        p1 = Product(serial_number="SN-X100", name="Ventilator", client_id=c1.id)
        p2 = Product(serial_number="SN-M500", name="MRI Scanner", client_id=c1.id)
        db.session.add_all([p1, p2])

        db.session.commit()
        print("Database Seeded Successfully!")

if __name__ == "__main__":
    seed_database()