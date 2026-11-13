"""
Delete ALL staff records (no exceptions)
"""
from app import create_app
from app.models import Staff, AttendanceLog, Payroll, ShiftHandover
from app.extensions import db

app = create_app()

with app.app_context():
    print("\n" + "="*60)
    print("DELETE ALL STAFF RECORDS")
    print("="*60 + "\n")
    
    # Get all staff
    all_staff = Staff.query.all()
    
    if len(all_staff) == 0:
        print("✅ No staff records found. Database is already clean!")
        exit(0)
    
    print(f"🗑️  DELETING {len(all_staff)} staff records:\n")
    
    for staff in all_staff:
        print(f"   ❌ ID {staff.id}: {staff.full_name} ({staff.role})")
    
    print(f"\n{'='*60}")
    print("⚠️  Deleting all staff and related data...")
    print(f"{'='*60}\n")
    
    deleted_count = 0
    
    for staff in all_staff:
        staff_id = staff.id
        staff_name = staff.full_name
        
        try:
            # Delete related shift handovers
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
            
            # Delete the staff record
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
    
    # Verify
    remaining = Staff.query.count()
    print(f"\n📊 Remaining staff in database: {remaining}")
    
    if remaining == 0:
        print("✅ Perfect! All staff records have been deleted!")
    else:
        print(f"⚠️  Warning: {remaining} staff records still remain")
        remaining_staff = Staff.query.all()
        for s in remaining_staff:
            print(f"   - {s.full_name} (ID {s.id})")
