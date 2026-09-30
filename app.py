"""WSGI entrypoint: `gunicorn app:app` (production) or `python app.py` (local)."""

import os

from dotenv import load_dotenv

load_dotenv()

from predictor import create_app  # noqa: E402  (env must be loaded first)

app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
