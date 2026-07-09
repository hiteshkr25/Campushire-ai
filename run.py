import os

from dotenv import load_dotenv

from app import create_app

load_dotenv()

app = create_app(os.environ.get("FLASK_ENV", "development"))

if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=int(os.environ.get("FLASK_PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "true").lower() == "true",
    )
