PREDICO — Project README

Overview
--------
This repository contains a Django-based application (project name `disease_prediction`) that provides disease prediction and consultation features. The project was developed to use PostgreSQL in production but includes a safe local development configuration using SQLite when DEBUG=True.

This README contains instructions to set up the development environment, run the project locally, and notes about compatibility (Postgres vs SQLite) and a model compatibility warning.

Quick start (Windows, PowerShell)
---------------------------------
1. Create and activate a virtual environment (if not already present):

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Apply migrations and create the local SQLite DB (the project uses SQLite when DEBUG=True):

   ```powershell
   python manage.py migrate
   ```

4. Create a superuser (optional):

   ```powershell
   python manage.py createsuperuser
   ```

5. Run the dev server:

   ```powershell
   python manage.py runserver
   ```

6. Open http://127.0.0.1:8000/ in your browser.

Database notes
--------------
- Production: The project's original configuration uses PostgreSQL. See `disease_prediction/settings.py` for the `DATABASES` configuration under `DEBUG=False`.
- Local development: When `DEBUG=True`, `settings.py` uses a local SQLite database (`db.sqlite3`) to avoid requiring a Postgres server.
- Postgres-only fields: The app originally used `ArrayField` (Postgres-only). For local development migrations to run on SQLite, the code and initial migration were adjusted to use `JSONField` instead of `ArrayField`. If you prefer to run Postgres locally (recommended for parity with production), revert those migration changes and use a local Postgres instance.

Migrations
----------
- If you see errors about missing tables (e.g., `no such table: django_session`), run:

```powershell
python manage.py migrate
```

- If migrations fail due to DB-specific SQL (e.g., ArrayField), check `main_app/migrations/0001_initial.py` and `main_app/models.py`. For this repository, they have been updated to be compatible with SQLite.

Sklearn model warning
---------------------
- You may see a warning when starting the server about unpickling a scikit-learn model saved with an older version. For example:

  "Trying to unpickle estimator MultinomialNB from version 0.21.3 when using version 1.0.2. This might lead to breaking code or invalid results."

- Recommendations:
  - Re-save the trained model with your current scikit-learn version (recommended).
  - Or pin scikit-learn to the older version used when the model was created.

How to re-save the model safely
-------------------------------
1. Load the training script or notebook used to create `trained_model`.
2. Re-train or at least re-fit the model using the current scikit-learn version in your `venv`.
3. Save using `joblib.dump(model, 'trained_model/model.joblib')` or similar.

Troubleshooting
---------------
- "Couldn't import Django": make sure you activated the virtualenv and installed requirements.
- "password authentication failed for user 'postgres'": either configure correct Postgres credentials (in `settings.py`) and run Postgres locally, or use the SQLite fallback by ensuring `DEBUG=True`.
- Migration SQL errors: check for Postgres-specific fields (ArrayField). This repo includes migration edits to use JSONField for local DB compatibility.

Recommended next steps for contributors
--------------------------------------
- If you will run the project in production or on a staging environment, use PostgreSQL to match production. Update `disease_prediction/settings.py` accordingly and revert any migration edits made for local SQLite compatibility.
- Add tests for critical flows (signup, signin, model prediction endpoints).
- Consider adding a small script to validate the trained model on a holdout set and re-save it with the current sklearn version.

Contact
-------
If you need more help adapting this project to your environment (Postgres local setup, migrations, or model re-saving), tell me what you'd like me to take next and I can make the changes or provide step-by-step commands.