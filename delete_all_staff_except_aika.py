"""
Delete all STAFF records EXCEPT Aika Diego
"""
from app import create_app
from app.models import Staff, AttendanceLog, Payroll, ShiftHandover
from app.extensions import db

app = create_app()

with app.app_context():
    print("\n" + "="*60)
    print("DELETE ALL STAFF RECORDS EXCEPT AIKA DIEGO")
    print("="*60 + "\n")
    
    # Find Aika Diego
    keep_staff = Staff.query.filter(Staff.full_name.ilike('%aika diego%')).first()
    
    if not keep_staff:
        print("❌ Aika Diego not found! Searching for similar names...")
        all_staff = Staff.query.order_by(Staff.full_name).all()
        print("\n📋 All staff in database:")
        for s in all_staff:
            print(f"   ID {s.id}: {s.full_name} ({s.role})")
        print("\nPlease check the correct name.")
        exit(1)
    
    print(f"🔒 KEEPING Staff Record:")
    print(f"   ID: {keep_staff.id}")
    print(f"   Full Name: {keep_staff.full_name}")
    print(f"   Role: {keep_staff.role}")
    print(f"   Email: {keep_staff.email}")
    print(f"   Status: {keep_staff.status}")
    print()
    
    # Get all OTHER staff
    staff_to_delete = Staff.query.filter(Staff.id != keep_staff.id).all()
    
    print(f"🗑️  DELETING {len(staff_to_delete)} staff records:\n")
    
    for staff in staff_to_delete:
        print(f"   ❌ ID {staff.id}: {staff.full_name} ({staff.role})")
    
    if len(staff_to_delete) == 0:
        print("   ✅ No other staff to delete!")
        exit(0)
    
    # Delete
    print(f"\n{'='*60}")
    print("⚠️  Deleting staff records and related data...")
    print(f"{'='*60}\n")
    
    deleted_count = 0
    
    for staff in staff_to_delete:
        staff_id = staff.id
        staff_name = staff.full_name
        
        try:
            # Delete related shift handovers first
            shift_handovers_out = ShiftHandover.query.filter_by(outgoing_staff_id=staff_id).all()
            shift_handovers_in = ShiftHandover.query.filter_by(incoming_staff_id=staff_id).all()
            for handover in shift_handovers_out + shift_handovers_in:
                db.session.delete(handover)
            
            # Delete related attendance logs
            attendance_logs = AttendanceLog.query.filter_by(staff_id=staff_id).all()
            for log in attendance_logs:
                db.session.delete(log)
            
            # Delete related payroll records
            payrolls = Payroll.query.filter_by(staff_id=staff_id).all()
            for payroll in payrolls:
                db.session.delete(payroll)
            
            # Now delete the staff record
            db.session.delete(staff)
            db.session.flush()
            deleted_count += 1
            print(f"   ✅ Deleted: {staff_name}")
            
        except Exception as e:
            print(f"   ⚠️  Failed to delete {staff_name}: {e}")
            db.session.rollback()
    
    db.session.commit()
    
    print(f"\n{'='*60}")
    print(f"✅ Successfully deleted {deleted_count} staff records!")
    print(f"✅ Kept 1 staff record: {keep_staff.full_name} (ID {keep_staff.id})")
    
    # Verify
    remaining = Staff.query.count()
    print(f"\n📊 Remaining staff in database: {remaining}")
    
    if remaining == 1:
        print("✅ Perfect! Only Aika Diego remains!")
    else:
        print(f"⚠️  Expected 1, but found {remaining} staff records")
        remaining_staff = Staff.query.all()
        print("\nRemaining staff:")
        for s in remaining_staff:
            print(f"   - {s.full_name} (ID {s.id})")
