import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from scripts.demo_data import DEMO_ACCOUNTS

app = create_app(os.environ.get('FLASK_ENV', 'development'))
app.config['WTF_CSRF_ENABLED'] = False
app.config['TESTING'] = True

with app.app_context():
    with app.test_client() as client:
        # Login
        creds = DEMO_ACCOUNTS['tpo']
        res = client.post('/auth/login', data={'email': creds['email'], 'password': creds['password']}, follow_redirects=True)
    print('Login status code:', res.status_code)
    # Request drives page
    res2 = client.get('/tpo/drives')
    print('Drives status code:', res2.status_code)
    print(res2.get_data(as_text=True)[:1000])

    # Try viewing a specific demo drive if exists
    from app.models.drive import PlacementDrive
    from scripts.demo_data import DEMO_DRIVE

    drive = PlacementDrive.query.filter_by(title=DEMO_DRIVE['title']).first()
    if drive:
        res3 = client.get(f'/tpo/drives/{drive.id}')
        print('Drive detail status:', res3.status_code)
        print(res3.get_data(as_text=True)[:1000])
    else:
        print('Demo drive not found in DB')
