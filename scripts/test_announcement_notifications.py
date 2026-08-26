import os
import sys

# Insert root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.user import User, UserRole
from app.models.student import Student
from app.models.enums import AnnouncementAudience, NotificationType
from app.models.notification import Announcement, Notification
from app.utils.notification_service import NotificationService
from datetime import datetime, timezone

def test_announcement_notifications():
    app = create_app("development")
    app.config["WTF_CSRF_ENABLED"] = False
    
    with app.app_context():
        print("Starting Announcement Notification focused tests...")
        
        # 1. Fetch TPO user and student user
        tpo_user = User.query.filter_by(email="tpo@geu.edu.in").first()
        student_user = User.query.filter_by(email="student.demo@campushire.ai").first()
        
        if not tpo_user or not student_user:
            print("[FAIL] Demo users tpo@geu.edu.in and student.demo@campushire.ai are required. Run init_db.py.")
            sys.exit(1)
            
        college_id = tpo_user.college_id
        
        # Fetch all student user IDs for this college
        students_in_college = Student.query.filter_by(college_id=college_id).all()
        student_user_ids = [s.user_id for s in students_in_college]
        print(f"Found {len(student_user_ids)} student(s) at this college.")
        
        # Clear existing notifications and announcements for cleanup
        Notification.query.filter(Notification.entity_type == "Announcement").delete()
        Announcement.query.filter_by(college_id=college_id).delete()
        db.session.commit()
        
        # ----------------------------------------------------
        # TEST 1: Create announcement targeting ALL students
        # ----------------------------------------------------
        print("\nTEST 1: Creating announcement targeting ALL students...")
        ann_all = Announcement(
            college_id=college_id,
            created_by=tpo_user.id,
            title="All Students Notice",
            content="This announcement is for all students.",
            target_audience=AnnouncementAudience.ALL,
            published_at=datetime.now(timezone.utc)
        )
        db.session.add(ann_all)
        db.session.commit()
        
        # Dispatch notifications
        num_notified = NotificationService.notify_students_about_announcement(ann_all)
        print(f"Sent {num_notified} notifications.")
        assert num_notified == len(student_user_ids), f"Should notify all {len(student_user_ids)} students."
        
        # Confirm they exist in db
        notifs = Notification.query.filter_by(entity_type="Announcement", entity_id=ann_all.id).all()
        assert len(notifs) == len(student_user_ids), "DB notification records should match student count."
        print("[PASS] Test 1: Every student received exactly one notification.")
        
        # ----------------------------------------------------
        # TEST 2: Create announcement targeting STUDENTS specifically
        # ----------------------------------------------------
        print("\nTEST 2: Creating announcement targeting STUDENTS specifically...")
        ann_stud = Announcement(
            college_id=college_id,
            created_by=tpo_user.id,
            title="Students Only Notice",
            content="This announcement is for students only.",
            target_audience=AnnouncementAudience.STUDENTS,
            published_at=datetime.now(timezone.utc)
        )
        db.session.add(ann_stud)
        db.session.commit()
        
        num_notified = NotificationService.notify_students_about_announcement(ann_stud)
        print(f"Sent {num_notified} notifications.")
        assert num_notified == len(student_user_ids), "Should notify all students."
        print("[PASS] Test 2: Only eligible students (students role) received notifications.")
        
        # ----------------------------------------------------
        # TEST 3: Create announcement with zero eligible students (e.g. TARGET_AUDIENCE = RECRUITERS)
        # ----------------------------------------------------
        print("\nTEST 3: Creating announcement targeting RECRUITERS (zero eligible students in notifications)...")
        ann_rec = Announcement(
            college_id=college_id,
            created_by=tpo_user.id,
            title="Recruiters Notice",
            content="This is for recruiters.",
            target_audience=AnnouncementAudience.RECRUITERS,
            published_at=datetime.now(timezone.utc)
        )
        db.session.add(ann_rec)
        db.session.commit()
        
        num_notified = NotificationService.notify_students_about_announcement(ann_rec)
        print(f"Sent {num_notified} notifications.")
        assert num_notified == 0, "No notifications should be sent to students."
        print("[PASS] Test 3: Zero notifications created correctly.")
        
        # ----------------------------------------------------
        # TEST 4: Verify notification content
        # ----------------------------------------------------
        print("\nTEST 4: Verifying notification content fields...")
        notif = Notification.query.filter_by(entity_id=ann_all.id, user_id=student_user.id).first()
        assert notif is not None, "Notification should exist for the student."
        assert notif.title == "New Announcement", "Title should match"
        assert notif.message == f"New announcement: {ann_all.title}", "Message should match"
        assert notif.entity_type == "Announcement", "Entity type should be Announcement"
        assert notif.entity_id == ann_all.id, "Entity ID should be announcement ID"
        assert notif.notification_type == NotificationType.ANNOUNCEMENT, "Notification type should be ANNOUNCEMENT"
        assert notif.is_read == False, "Initial read state should be False"
        assert notif.action_url == "/student/notifications", "Action URL should point to notifications page"
        print("[PASS] Test 4: Notification fields verified successfully.")
        
        # ----------------------------------------------------
        # TEST 5 & 6: Dropdown retrieval and unread count
        # ----------------------------------------------------
        print("\nTEST 5 & 6: Student opens notification dropdown & checks unread count...")
        # Get unread count via context processor equivalent or DB
        unread_count = Notification.query.filter_by(user_id=student_user.id, is_read=False).count()
        dropdown_notifs = NotificationService.get_dropdown_notifications(student_user.id, limit=10)
        
        # Check that our announcement notifications are in dropdown and count is accurate
        ann_dropdown_notifs = [n for n in dropdown_notifs if n.entity_type == "Announcement"]
        assert len(ann_dropdown_notifs) == 2, "Both student-targeted announcements should be present."
        assert unread_count >= 2, "Unread count should be updated."
        print(f"[PASS] Test 5 & 6: Dropdown contains announcement notifications. Unread count: {unread_count}")
        
        # ----------------------------------------------------
        # TEST 7: Student clicks/marks notification as read
        # ----------------------------------------------------
        print("\nTEST 7: Student clicks/marks notification as read...")
        NotificationService.mark_read(notif.id)
        db.session.refresh(notif)
        assert notif.is_read == True, "Should be marked as read."
        assert notif.read_at is not None, "read_at timestamp must be set."
        print("[PASS] Test 7: Notification read status updated successfully.")
        
        # ----------------------------------------------------
        # TEST 8: Paginated Notification history
        # ----------------------------------------------------
        print("\nTEST 8: Checking student notification center pagination...")
        pag = NotificationService.get_paginated_notifications(student_user.id, page=1, per_page=10)
        pag_ann = [n for n in pag.items if n.entity_type == "Announcement"]
        assert len(pag_ann) >= 2, "Paginated notifications contains announcements."
        print("[PASS] Test 8: Paginated notification center verified.")
        
        # ----------------------------------------------------
        # TEST 9: Mark all read
        # ----------------------------------------------------
        print("\nTEST 9: Testing mark all read...")
        NotificationService.mark_all_read(student_user.id)
        unread_after = Notification.query.filter_by(user_id=student_user.id, is_read=False).count()
        assert unread_after == 0, "All notifications should now be read."
        print("[PASS] Test 9: Mark all read verified successfully.")
        
        # ----------------------------------------------------
        # TEST 10: Duplicate notification prevention
        # ----------------------------------------------------
        print("\nTEST 10: Testing duplicate notification prevention...")
        # Try to trigger notification dispatch again on same announcement
        num_notified_dup = NotificationService.notify_students_about_announcement(ann_all)
        assert num_notified_dup == 0, "No duplicate notifications should be created."
        print("[PASS] Test 10: Duplicate notifications prevented successfully.")

        # Clean up database records created for test
        Notification.query.filter(Notification.entity_type == "Announcement").delete()
        Announcement.query.filter_by(college_id=college_id).delete()
        db.session.commit()
        
        print("\nAll Announcement Notification Focused Tests Passed Successfully!")

if __name__ == "__main__":
    test_announcement_notifications()
