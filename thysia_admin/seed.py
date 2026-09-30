"""Seed the database with sample data (SQLite-compatible)."""
import os, sys

# Force SQLite — skip Supabase entirely
os.environ['DATABASE_URL'] = ''
os.environ['DATABASE_POOLER_URL'] = ''

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db
from app.models import (Account, Guest, Facility, Reservation, Payment,
                        Staff, AttendanceLog, Payroll, ShiftHandover,
                        AIChatLog, AuditLog)
from datetime import datetime, date, timedelta, time
import random
import string
import uuid

app = create_app()


def random_receipt():
    return 'RCP-' + ''.join(random.choices(string.digits, k=8))


with app.app_context():
    db.drop_all()
    db.create_all()

    # Accounts
    super_admin = Account(
        username='superadmin',
        email='superadmin@adthysia.com',
        first_name='Joanna',
        last_name='Dela Cruz',
        role='super_admin',
        status='active'
    )
    super_admin.set_password('admin123')

    admin = Account(
        username='admin',
        email='admin@adthysia.com',
        first_name='Maria',
        last_name='Santos',
        role='admin',
        status='active'
    )
    admin.set_password('admin123')

    db.session.add_all([super_admin, admin])
    db.session.commit()

    # Facilities
    facilities_data = [
        ('Main Pool Area', 'pool', 80, 8000, 'Large swimming pool with lounge area and poolside bar.'),
        ('Grand Event Center', 'event_center', 300, 25000, 'Air-conditioned hall for grand events, weddings, and corporate meetings.'),
        ('Garden Pavilion', 'pavilion', 150, 15000, 'Open-air pavilion surrounded by lush tropical gardens.'),
        ('Cabana Suite A', 'cabana', 20, 5000, 'Private cabana with dedicated pool access and concierge service.'),
        ('Cabana Suite B', 'cabana', 20, 5000, 'Private cabana with beach view and personal butler.'),
        ('Conference Room', 'event_center', 50, 8000, 'Fully-equipped conference room with AV system.'),
    ]

    facilities = []
    for name, ftype, cap, base, desc in facilities_data:
        f = Facility(
            id=str(uuid.uuid4()),
            facility_name=name, facility_type=ftype, capacity=cap,
            base_price=base, description=desc,
            is_available=True
        )
        db.session.add(f)
        facilities.append(f)
    db.session.commit()

    # Guests
    guest_data = [
        ('Andrea Reyes', 'andrea.reyes@email.com', '09171234567'),
        ('Brent Aquino', 'brent.aquino@email.com', '09181234567'),
        ('Carla Navarro', 'carla.navarro@email.com', '09191234567'),
        ('Diego Lim', 'diego.lim@email.com', '09201234567'),
        ('Elena Cruz', 'elena.cruz@email.com', '09211234567'),
        ('Fernando Tan', 'fernando.tan@email.com', '09221234567'),
        ('Grace Dela Rosa', 'grace.delarosa@email.com', '09231234567'),
        ('Harold Mendoza', 'harold.mendoza@email.com', '09241234567'),
        ('Isabel Garcia', 'isabel.garcia@email.com', '09251234567'),
        ('Jose Villanueva', 'jose.villanueva@email.com', '09261234567'),
    ]

    guests = []
    for name, email, phone in guest_data:
        g = Guest(full_name=name, email=email, phone=phone)
        db.session.add(g)
        guests.append(g)
    db.session.commit()

    # Reservations & Payments
    statuses = ['confirmed', 'confirmed', 'confirmed', 'pending', 'cancelled']
    payment_modes = ['cash', 'gcash', 'bank', 'card']
    today = date.today()

    for i in range(30):
        guest = random.choice(guests)
        facility = random.choice(facilities)
        event_date = today + timedelta(days=random.randint(-15, 30))
        start_h = random.choice([8, 10, 13, 15])
        status = random.choice(statuses)

        res = Reservation(
            guest_id=guest.id,
            facility_id=facility.id,
            event_date=event_date,
            start_time=time(start_h, 0),
            end_time=time(start_h + 4, 0),
            guest_count=random.randint(10, facility.capacity),
            status=status,
            notes='Sample reservation.'
        )
        db.session.add(res)
        db.session.flush()

        pay_status = 'paid' if status == 'confirmed' else 'pending'
        pay = Payment(
            reservation_id=res.id,
            amount=facility.base_price,
            payment_mode=random.choice(payment_modes),
            status=pay_status,
            receipt_number=random_receipt(),
            paid_at=datetime.utcnow() if pay_status == 'paid' else None
        )
        db.session.add(pay)

    # Today's reservations
    for i in range(3):
        guest = random.choice(guests)
        facility = random.choice(facilities)
        res = Reservation(
            guest_id=guest.id,
            facility_id=facility.id,
            event_date=today,
            start_time=time(9, 0),
            end_time=time(13, 0),
            guest_count=random.randint(20, 80),
            status='confirmed'
        )
        db.session.add(res)
        db.session.flush()
        pay = Payment(
            reservation_id=res.id,
            amount=facility.base_price,
            payment_mode='gcash',
            status='paid',
            receipt_number=random_receipt(),
            paid_at=datetime.utcnow()
        )
        db.session.add(pay)

    db.session.commit()

    # Staff
    staff_data = [
        ('Mark Reyes', 'front_desk', 'morning', 'RFID001'),
        ('Lisa Santos', 'housekeeping', 'morning', 'RFID002'),
        ('Ryan Cruz', 'security', 'afternoon', 'RFID003'),
        ('Anna Lim', 'concierge', 'morning', 'RFID004'),
        ('Ben Torres', 'maintenance', 'morning', 'RFID005'),
        ('Cathy Ramos', 'kitchen', 'afternoon', 'RFID006'),
        ('Dan Morales', 'security', 'evening', 'RFID007'),
        ('Eva Flores', 'front_desk', 'afternoon', 'RFID008'),
        ('Frank Dela Cruz', 'housekeeping', 'evening', 'RFID009'),
        ('Grace Aguilar', 'concierge', 'morning', 'RFID010'),
        ('Hector Bautista', 'kitchen', 'morning', 'RFID011'),
        ('Iris Castillo', 'maintenance', 'afternoon', 'RFID012'),
        ('Jake Domingo', 'security', 'morning', 'RFID013'),
        ('Karen Espinosa', 'front_desk', 'evening', 'RFID014'),
        ('Leo Fernandez', 'housekeeping', 'morning', 'RFID015'),
        ('Maya Guerrero', 'concierge', 'afternoon', 'RFID016'),
        ('Noel Herrera', 'kitchen', 'evening', 'RFID017'),
        ('Olivia Ibarra', 'maintenance', 'morning', 'RFID018'),
        ('Pablo Jimenez', 'security', 'afternoon', 'RFID019'),
        ('Queenie Kho', 'front_desk', 'morning', 'RFID020'),
        ('Ramon Luna', 'housekeeping', 'afternoon', 'RFID021'),
        ('Sofia Mendez', 'concierge', 'morning', 'RFID022'),
    ]

    staff_objects = []
    for name, role, shift, rfid in staff_data:
        s = Staff(full_name=name, role=role, shift=shift, rfid_tag=rfid, status='active')
        db.session.add(s)
        staff_objects.append(s)
    db.session.commit()

    # Attendance logs (last 14 days)
    for staff in staff_objects:
        for day_offset in range(14):
            d = today - timedelta(days=day_offset)
            if d.weekday() < 6:  # Mon-Sat
                time_in_h = 8 if staff.shift == 'morning' else (14 if staff.shift == 'afternoon' else 20)
                delay = random.choice([0, 0, 0, random.randint(15, 60)])
                time_in = datetime.combine(d, time(time_in_h, delay % 60))
                time_out = time_in + timedelta(hours=8 + random.choice([0, 0, 1, 2]))
                status = 'late' if delay >= 15 else 'on_time'
                log = AttendanceLog(
                    staff_id=staff.id,
                    time_in=time_in,
                    time_out=time_out if day_offset > 0 else None,
                    status=status,
                    rfid_tap_in=staff.rfid_tag
                )
                db.session.add(log)
    db.session.commit()

    # Shift handovers
    for i in range(5):
        out_staff = random.choice(staff_objects)
        in_staff = random.choice([s for s in staff_objects if s.id != out_staff.id])
        handover = ShiftHandover(
            outgoing_staff_id=out_staff.id,
            incoming_staff_id=in_staff.id,
            notes=f'Completed {random.choice(["pool maintenance", "guest check-ins", "security rounds", "cleaning schedule"])}. All clear.',
            pending_tasks=f'{random.choice(["Refill towel supply", "Check room 12 A/C", "Restock bar", "Update reservation logs"])}',
            acknowledged=random.choice([True, False]),
            created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 48))
        )
        db.session.add(handover)
    db.session.commit()

    # AI Chat Logs
    inquiries = [
        ('Andrea Reyes', 'Is the Grand Event Center available on December 20?', True, False),
        ('Brent Aquino', 'What are the rates for the Main Pool Area for a birthday party?', True, False),
        ('Carla Navarro', 'Can we bring our own catering?', True, False),
        ('Diego Lim', 'I need to cancel my reservation for Jan 5.', True, False),
        ('Elena Cruz', "Do you have a children's pool area?", True, True),
        ('Fernando Tan', 'What time does the resort open?', False, True),
        ('Grace Dela Rosa', 'Can I do a same-day booking?', True, False),
        ('Harold Mendoza', 'Is parking available for large groups?', False, True),
    ]

    for guest_name, inquiry, escalated, resolved in inquiries:
        log = AIChatLog(
            guest_name=guest_name,
            inquiry=inquiry,
            ai_response='Thank you for reaching out! A member of our team will assist you shortly.' if escalated else 'Our resort is open from 7 AM to 10 PM daily. For reservations, please book through our website.',
            escalated=escalated,
            resolved=resolved,
            created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 72))
        )
        db.session.add(log)
    db.session.commit()

    print('Database seeded successfully!')
    print('   Super Admin: superadmin / admin123')
    print('   Admin:       admin      / admin123')
