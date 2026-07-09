# Project Folder Structure Reference

This document maps the CampusHire AI codebase layout.

```directory
CampusHire/
├── app/                      # Main Flask application directory
│   ├── admin/                # System Administrator controllers, forms, and services
│   ├── auth/                 # Authentication, register, login controllers and services
│   ├── main/                 # Public landing controllers
│   ├── recruiter/            # Recruiter controllers, forms, and services
│   ├── student/              # Student controllers, forms, and services
│   │   ├── ats_service.py    # Rule-based weights matching and scikit-learn TF-IDF engine
│   │   ├── resume_parser.py  # pdfplumber/PyPDF2 PDF text parsers
│   │   └── services.py       # Core student DB methods
│   ├── tpo/                  # Training & Placement Officer controllers, forms, and services
│   ├── models/               # SQLAlchemy ORM schemas
│   ├── utils/                # Helper utilities and date formatters
│   ├── decorators.py         # Route role authorization checks
│   ├── errors.py             # Error blueprint registers
│   ├── exceptions.py         # Custom application exception definitions
│   └── extensions.py         # Flask plugins (WTF, Bcrypt, Login, CSRF, DB)
├── config.py                 # Environment configurations (Development, Production, Testing)
├── database/                 # Raw schema.sql reference models
├── docs/                     # Markdown system manuals
├── run.py                    # Application debug startup entry point
├── scripts/                  # Command-line utility scripts
│   ├── init_db.py            # DB initialization and baseline seeder
│   └── create_admin.py       # CLI admin account initializer
├── static/                   # Public static files
│   ├── css/                  # Stylesheets (main.css containing glassmorphism stylesheets)
│   ├── js/                   # Theme switcher and animations scripting
│   └── uploads/              # Dynamic file upload storage paths
├── templates/                # HTML Jinja template files
│   ├── admin/                # User directories, bulk uploads templates
│   ├── errors/               # Custom glassmorphic 403, 404, 500 error pages
│   ├── portals/              # Base base_portal shell and role dashboards templates
│   ├── recruiter/            # Candidates rosters, timelines, scheduler templates
│   ├── student/              # Drives, resumes parsing templates
│   └── tpo/                  # Campaign setup, verifications, analytics templates
├── requirements.txt          # Global production package dependencies script
├── gunicorn.conf.py          # Production Gunicorn HTTP server parameters script
└── wsgi.py                   # Production WSGI server launch loader
```
