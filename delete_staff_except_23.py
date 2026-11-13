"""
Delete all STAFF records EXCEPT row #23 (ID 24 - v&t's H2O)
"""
from app import create_app
from app.models import Staff
from app.extensions import db

app = create_app()

with app.app_context():
    print("\n" + "="*60)
    print("DELETE ALL STAFF RECORDS EXCEPT ROW #23 (ID 24)")
    print("="*60 + "\n")
    
    # Find the staff to KEEP (ID 24)
    keep_staff = Staff.query.filter_by(id=24).first()
    
    if not keep_staff:
        print("❌ Staff ID 24 not found! Showing all staff...")
        all_staff = Staff.query.order_by(Staff.id).all()
        for s in all_staff:
            print(f"   ID {s.id}: {s.full_name} ({s.role})")
        print("\nPlease check the correct ID to keep.")
        exit(1)
    
    print(f"🔒 KEEPING Staff Record:")
    print(f"   ID: {keep_staff.id}")
    print(f"   Full Name: {keep_staff.full_name}")
    print(f"   Role: {keep_staff.role}")
    print(f"   Email: {keep_staff.email}")
    print(f"   Status: {keep_staff.status}")
    print()
    
    # Get all OTHER staff
    staff_to_delete = Staff.query.filter(Staff.id != 24).all()
    
    print(f"🗑️  DELETING {len(staff_to_delete)} staff records:\n")
    
    for staff in staff_to_delete:
        print(f"   ❌ ID {staff.id}: {staff.full_name} ({staff.role})")
    
    if len(staff_to_delete) == 0:
        print("   ✅ No other staff to delete!")
    else:
        # Auto-delete without confirmation since it's just staff table
        print(f"\n{'='*60}")
        print("⚠️  Deleting staff records and related data...")
        print(f"{'='*60}\n")
        
        deleted_count = 0
        from app.models import AttendanceLog, Payroll, ShiftHandover
        
        for staff in staff_to_delete:
            staff_id = staff.id
            staff_name = staff.full_name
            
            try:
                # Delete related shift handovers first
                shift_handovers_out = ShiftHandover.query.filter_by(outgoing_staff_id=staff_id).all()
                shift_handovers_in = ShiftHandover.query.filter_by(incoming_staff_id=staff_id).all()
                for handover in shift_handovers_out + shift_handovers_in:
                    db.session.delete(handover)
                print(f"   🗑️  Deleted {len(shift_handovers_out + shift_handovers_in)} shift handovers for {staff_name}")
                
                # Delete related attendance logs
                attendance_logs = AttendanceLog.query.filter_by(staff_id=staff_id).all()
                for log in attendance_logs:
                    db.session.delete(log)
                print(f"   🗑️  Deleted {len(attendance_logs)} attendance logs for {staff_name}")
                
                # Delete related payroll records
                payrolls = Payroll.query.filter_by(staff_id=staff_id).all()
                for payroll in payrolls:
                    db.session.delete(payroll)
                print(f"   🗑️  Deleted {len(payrolls)} payroll records for {staff_name}")
                
                # Now delete the staff record
                db.session.delete(staff)
                db.session.flush()  # Flush immediately
                deleted_count += 1
                print(f"   ✅ Deleted staff: {staff_name}\n")
                
            except Exception as e:
                print(f"   ⚠️  Failed to delete {staff_name}: {e}\n")
                db.session.rollback()
                # Continue with next staff
        
        db.session.commit()
        
        print(f"\n✅ Successfully deleted {deleted_count} staff records!")
        print(f"✅ Kept 1 staff record: {keep_staff.full_name} (ID {keep_staff.id})")
        
        # Verify
        remaining = Staff.query.count()
        print(f"\n📊 Remaining staff in database: {remaining}")
        
        if remaining == 1:
            print("✅ Perfect! Only 1 staff record remains (row #23)")
        else:
            print(f"⚠️  Expected 1, but found {remaining} staff records")
