# Production Deployment Guide

This document describes how to deploy the CampusHire AI application to a production environment.

## 1. Production Settings
Ensure the following variables are configured in the host environment or `.env` file:
```ini
FLASK_ENV=production
FLASK_DEBUG=false
SECRET_KEY=generate-a-secure-64-byte-key
DATABASE_URL=postgresql://<prod_db_user>:<prod_db_pwd>@<prod_host>:5432/<prod_db>
```

---

## 2. Gunicorn WSGI Server Configuration
The platform contains a pre-configured `gunicorn.conf.py` script. The configuration automatically scales the worker threads depending on the processor core count:
```bash
# Start Gunicorn manually
gunicorn -c gunicorn.conf.py wsgi:app
```

---

## 3. Systemd Service Unit Configuration
To ensure the application runs continuously, configure a systemd service unit on Linux servers:

Create `/etc/systemd/system/campushire.service`:
```ini
[Unit]
Description=CampusHire AI Web Portal
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/CampusHire
ExecStart=/var/www/CampusHire/venv/bin/gunicorn -c gunicorn.conf.py wsgi:app
Restart=always
Environment=PATH=/var/www/CampusHire/venv/bin

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable campushire.service
sudo systemctl start campushire.service
```

---

## 4. Nginx Reverse Proxy Setup
Configure Nginx as a reverse proxy to handle external HTTP/HTTPS requests.

Create `/etc/nginx/sites-available/campushire`:
```nginx
server {
    listen 80;
    server_name campushire.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /var/www/CampusHire/static/;
        expires 30d;
        add_header Cache-Control "public";
    }

    client_max_body_size 12M;
}
```

Enable Nginx configuration and reload the service:
```bash
sudo ln -s /etc/nginx/sites-available/campushire /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 5. Directory Permissions Checklist
Ensure the following directories exist and have write permissions enabled for the web process user (e.g. `www-data`):
- `static/uploads/company_logos/`
- `static/uploads/resumes/`
- `static/uploads/offers/`
```bash
sudo chown -R www-data:www-data /var/www/CampusHire/static/uploads
```
