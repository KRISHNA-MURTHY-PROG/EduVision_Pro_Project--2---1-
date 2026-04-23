# EduVision Pro — Attention Tracker with Auto Email Reports (Streamlit)

This upgraded EduVision saves session reports and can email them via Gmail automatically after a session ends.

## Quick setup (Windows)
1. Unzip and open in VS Code.
2. Create & activate venv:
   ```powershell
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install requirements:
   ```powershell
   pip install -r requirements.txt
   ```
4. Create `config.json` in the project folder with this structure (replace placeholders):
   ```json
   {
     "sender_email": "your_sender@gmail.com",
     "app_password": "your_app_password_here",
     "recipient_email": "admin_recipient@gmail.com",
     "subject": "EduVision Session Report",
     "body": "Attached is the session report."
   }
   ```
   **Important:** For Gmail, create an App Password (recommended) or enable "Less secure app access" (not recommended). See Google account security settings.
5. Run the app:
   ```powershell
   streamlit run app.py
   ```
6. Click **Start Camera**, run your session, then **Stop Camera** to end session and auto-send the report (if enabled).

## Notes
- The app writes CSV reports into `reports/`. Emails attach the CSV file.
- If email fails, the app shows an error message but still saves the report locally.
- For privacy, the app processes video locally and does not upload raw video to the cloud.

## Troubleshooting
- If camera not found, check which device index to use (CAM_INDEX) and change it in `app.py`.
- If SMTP login fails, verify your Gmail credentials and app password, and ensure internet connectivity.

## License
Educational/demo use only.
