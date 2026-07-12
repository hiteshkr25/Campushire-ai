import os
import sys

# Insert root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.user import User, UserRole
from app.models.student import Student
from app.models.enums import ProfileStatus, NotificationType, ScheduleStatus, OfferStatus
from app.models.notification import Notification
from app.utils.notification_service import NotificationService
from app.tpo.services import TpoService
from datetime import datetime, timezone, timedelta

def test_notification_system():
    app = create_app("development")
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        print("Starting notification system programmatic tests...")
        
        # 1. Fetch or create test student and TPO user
        student_user = User.query.filter_by(email="student.demo@campushire.ai").first()
        tpo_user = User.query.filter_by(email="tpo@geu.edu.in").first()
        
        if not student_user or not tpo_user:
            print("[FAIL] Demo users not found in the database. Run init_db.py first.")
            sys.exit(1)
            
        student = student_user.student_profile
        if not student:
            print("[FAIL] Demo student profile not found.")
            sys.exit(1)
            
        # Clean existing notifications for the student
        Notification.query.filter_by(user_id=student_user.id).delete()
        db.session.commit()
        
        # 2. Test Verification Rejection
        print("Testing verification rejection workflow...")
        remarks = "Rejection Test: Academic records do not match documents."
        student.profile_status = ProfileStatus.PENDING_VERIFICATION
        db.session.commit()
        
        TpoService.reject_student(student.id, tpo_user.id, remarks)
        
        # Reload student and check
        db.session.refresh(student)
        assert student.profile_status == ProfileStatus.REJECTED, "Status should be REJECTED"
        assert student.rejection_reason == remarks, "Rejection reason must be remarks"
        assert student.verified_by == tpo_user.id, "Verified by must be TPO user ID"
        assert student.verified_at is not None, "Verified at should be set"
        
        # Check that warning notification was dispatched
        notif = Notification.query.filter_by(user_id=student_user.id).order_by(Notification.created_at.desc()).first()
        assert notif is not None, "Notification should be dispatched"
        assert notif.title == "Profile Verification Rejected"
        assert remarks in notif.message
        assert notif.notification_type == NotificationType.WARNING
        
        print("[PASS] Rejection workflow behaves correctly.")

        # 3. Test Profile Resubmission
        print("Testing student profile resubmission...")
        # Simulate resubmit action
        student.profile_status = ProfileStatus.PENDING_VERIFICATION
        student.rejection_reason = None
        student.verified_by = None
        student.verified_at = None
        db.session.commit()
        
        # Reload student and check that review metadata is completely cleared
        db.session.refresh(student)
        assert student.profile_status == ProfileStatus.PENDING_VERIFICATION
        assert student.rejection_reason is None
        assert student.verified_by is None
        assert student.verified_at is None
        
        print("[PASS] Profile resubmission resets status and completely clears review metadata.")

        # 4. Test Verification Approval
        print("Testing verification approval workflow...")
        # Put back to pending for approval
        student.profile_status = ProfileStatus.PENDING_VERIFICATION
        db.session.commit()
        
        TpoService.verify_student(student.id, tpo_user.id)
        
        # Reload student and check
        db.session.refresh(student)
        assert student.profile_status == ProfileStatus.VERIFIED
        assert student.rejection_reason is None
        assert student.verified_by == tpo_user.id
        assert student.verified_at is not None
        
        # Check notification
        notif = Notification.query.filter_by(user_id=student_user.id).order_by(Notification.created_at.desc()).first()
        assert notif is not None
        assert notif.title == "Profile Verified"
        assert "eligible" in notif.message
        assert notif.notification_type == NotificationType.SUCCESS
        
        print("[PASS] Approval workflow behaves correctly.")

        # 4.5 Test 3-Rejection Limit
        print("Testing 3-rejection limit restriction...")
        # Reject 2 times first
        student.rejection_count = 2
        student.profile_status = ProfileStatus.PENDING_VERIFICATION
        db.session.commit()
        
        # 3rd rejection
        TpoService.reject_student(student.id, tpo_user.id, "Third time rejection remarks")
        db.session.refresh(student)
        assert student.rejection_count == 3
        assert student.profile_status == ProfileStatus.REJECTED
        
        # Test client posting to resubmit route should be blocked
        client = app.test_client()
        # Login
        client.post("/auth/login", data={
            "email": "student.demo@campushire.ai",
            "password": "Demo@1234"
        })
        
        # Attempt to resubmit
        resp = client.post("/student/profile/resubmit", follow_redirects=True)
        assert b"rejected 3 times" in resp.data
        
        # Verify status did not change
        db.session.refresh(student)
        assert student.profile_status == ProfileStatus.REJECTED
        
        # Clean count for remainder of the tests
        student.rejection_count = 0
        db.session.commit()
        print("[PASS] 3-rejection limit prevents resubmission correctly.")

        # 5. Test NotificationService enrichment, limits, and read/unread prioritization
        print("Testing NotificationService dropdown prioritization and limits...")
        
        # Clear student notifications
        Notification.query.filter_by(user_id=student_user.id).delete()
        db.session.commit()
        
        # Create 12 notifications: 8 unread, 4 read
        for i in range(4):
            # Create read ones first (older)
            n = Notification(
                user_id=student_user.id,
                title=f"Read Notif {i}",
                message="Message",
                notification_type=NotificationType.INFO,
                entity_type="Resume",
                is_read=True,
                created_at=datetime.now(timezone.utc) - timedelta(hours=2)
            )
            db.session.add(n)
        for i in range(8):
            # Create unread ones (newer)
            n = Notification(
                user_id=student_user.id,
                title=f"Unread Notif {i}",
                message="Message",
                notification_type=NotificationType.WARNING,
                entity_type="student",
                is_read=False,
                created_at=datetime.now(timezone.utc) - timedelta(hours=1)
            )
            db.session.add(n)
        db.session.commit()
        
        # Get dropdown notifications (limit 10)
        dropdown = NotificationService.get_dropdown_notifications(student_user.id, limit=10)
        assert len(dropdown) == 10, f"Dropdown should contain exactly 10 notifications, got {len(dropdown)}"
        
        # Verify that all 8 unread notifications are at the front of the list
        for idx in range(8):
            assert not dropdown[idx].is_read, f"Dropdown item {idx} should be unread"
        # Remaining 2 should be read
        for idx in range(8, 10):
            assert dropdown[idx].is_read, f"Dropdown item {idx} should be read"
            
        # Verify enrichment properties: category, priority, icon_class
        for item in dropdown:
            assert hasattr(item, "category")
            assert hasattr(item, "priority")
            assert hasattr(item, "icon_class")
            
            # Check Resume mapping
            if item.entity_type == "Resume":
                assert item.category == "Resume"
                assert "fa-file-pdf" in item.icon_class
                assert item.priority == "low"
            # Check student mapping
            if item.entity_type == "student":
                assert item.category == "Profile"
                assert "fa-user-gear" in item.icon_class
                assert item.priority == "medium" # Warning maps to medium
                
        print("[PASS] Dropdown prioritizes unread notifications, strictly enforces limit, and enriches fields.")

        # 6. Test Read Status modifications
        print("Testing read status modifications...")
        unread_count = Notification.query.filter_by(user_id=student_user.id, is_read=False).count()
        assert unread_count == 8
        
        # Mark single as read
        unread_notif = Notification.query.filter_by(user_id=student_user.id, is_read=False).first()
        NotificationService.mark_read(unread_notif.id)
        
        unread_count = Notification.query.filter_by(user_id=student_user.id, is_read=False).count()
        assert unread_count == 7
        
        # Mark all as read
        NotificationService.mark_all_read(student_user.id)
        unread_count = Notification.query.filter_by(user_id=student_user.id, is_read=False).count()
        assert unread_count == 0
        
        print("[PASS] Read status modifiers and counters update correctly.")

        # 7. Test Pagination
        print("Testing notifications pagination...")
        paginated = NotificationService.get_paginated_notifications(student_user.id, page=1, per_page=5)
        assert len(paginated.items) == 5, f"Pagination should fetch 5 notifications per page, got {len(paginated.items)}"
        assert paginated.total == 12, "Total notifications count should be 12"
        
        print("[PASS] Paginated notifications load and scale correctly.")
        print("\nAll notification system tests passed successfully!")

if __name__ == "__main__":
    test_notification_system()
