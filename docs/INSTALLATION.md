# Local Installation Guide

Follow these steps to configure, build, and run the CampusHire AI portal locally.

## Prerequisites
- **Python 3.12** or higher
- **PostgreSQL 14** or higher
- **Git**

---

## 1. Clone & Set Up Directory
Clone the repository and navigate into the project workspace:
```bash
git clone https://github.com/hiteshk25/Campushire.git
cd CampusHire
```

---

## 2. Virtual Environment Setup
Initialize a Python virtual environment:
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

---

## 3. Package Dependencies Installation
Install all required libraries using the global production requirements script:
```bash
pip install -r requirements.txt
```

---

## 4. Environment Variables Configuration
Copy the sample environment file to create your active `.env` configuration:
```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` in a text editor and specify your local credentials:
- Set `FLASK_ENV=development` and `FLASK_DEBUG=true`.
- Update the `DATABASE_URL` link to match your local PostgreSQL server:
  `DATABASE_URL=postgresql://<username>:<password>@localhost:5432/<db_name>`

---

## 5. Database Initialization & Seeding
Execute the automation setup script to create database tables and seed sample data:
```bash
python scripts/init_db.py
```
This automatically:
1. Validates all tables structures.
2. Seeds test colleges (IITB, BITS) and engineering branches.
3. Populates matching skills tags pools.
4. Initializes companies (Google, Microsoft) and default credentials:
   - **System Administrator**: `admin@campushire.ai` (Password: `Demo@1234`)

---

## 6. Launch Application Dev Server
Start the local Flask development web server:
```bash
python run.py
```
The server starts on `http://127.0.0.1:8000/`. You can log in using `admin@campushire.ai` and `Demo@1234`.
