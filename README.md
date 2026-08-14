# HeritageGuard Flask Site

This workspace now includes a Flask-based dynamic site using SQLite.

## Run locally

1. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

2. Start the app:

   ```bash
   python app.py
   ```

3. Open `http://127.0.0.1:5000` in your browser.

## Default credentials

- Admin: `admin` / `Heritage@123`
- Reporter: `reporter` / `Report@123`

## Notes

- The app initializes `heritageguard.db` automatically when it starts.
- Public APIs are available at `/api/public/stats` and `/api/public/reports`.
- The site now uses dynamic routes and templates under `templates/`.
