"""
EduVision Pro - Attention Tracker with Auto Email Reports (Streamlit)
Run:
    streamlit run app.py

Notes:
- This version saves session CSV reports and will attempt to send the report via Gmail SMTP
  after the session stops (or when you press "Send Report Now").
- You must configure `config.json` with your Gmail sender, app password, and recipient.
  See README.md for instructions and security notes.

Author: EduVision Pro Starter

"""

import streamlit as st
import cv2
import numpy as np
import pandas as pd
import time, threading, os, smtplib, ssl, json
from datetime import datetime
from pathlib import Path
from email.message import EmailMessage

st.set_page_config(layout="wide", page_title="EduVision Pro — Attention Tracker")

# --- Config ---
CAM_INDEX = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)
CONFIG_FILE = Path("config.json")  # user-provided config with Gmail creds

# Haar cascades (bundled with OpenCV)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

# Session state defaults
if "running" not in st.session_state:
    st.session_state.running = False
if "attention_history" not in st.session_state:
    st.session_state.attention_history = []
if "vc" not in st.session_state:
    st.session_state.vc = None

# Helper functions
def compute_attention(face_detected, eyes_detected, face_center_x, frame_w):
    if not face_detected:
        return 0, "absent"
    score = 100
    if not eyes_detected:
        score -= 50
    offset = abs(face_center_x - frame_w / 2) / (frame_w / 2)
    score -= int(offset * 50)
    score = max(0, min(100, score))
    if score >= 70:
        status = "attentive"
    elif score >= 40:
        status = "distracted"
    elif score > 0:
        status = "drowsy"
    else:
        status = "absent"
    return score, status

# Video capture thread (lightweight)
class VideoCaptureAsync:
    def __init__(self, idx=0):
        self.idx = idx
        self.cap = None
        self.running = False
        self.frame = None
        self.lock = threading.Lock()

    def start(self):
        if self.running:
            return
        self.cap = cv2.VideoCapture(self.idx, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        self.running = True
        threading.Thread(target=self._read_loop, daemon=True).start()

    def _read_loop(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                continue
            frame = cv2.flip(frame, 1)
            with self.lock:
                self.frame = frame
            time.sleep(0.01)

    def read(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def stop(self):
        self.running = False
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass

# Email sender (Gmail)
def send_report_via_gmail(report_path: Path, config_path: Path):
    if not config_path.exists():
        st.warning("No config.json found — cannot send email. Create config.json following README.")
        return False, "config_missing"
    try:
        cfg = json.loads(config_path.read_text())
        sender = cfg.get("sender_email")
        app_password = cfg.get("app_password")
        recipient = cfg.get("recipient_email")
        subject = cfg.get("subject", "EduVision Session Report")
        body = cfg.get("body", "Please find attached the session report from EduVision.")

        if not sender or not app_password or not recipient:
            return False, "incomplete_config"

        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.set_content(body)

        with open(report_path, "rb") as f:
            data = f.read()
        msg.add_attachment(data, maintype="text", subtype="csv", filename=report_path.name)

        context = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls(context=context)
            server.login(sender, app_password)
            server.send_message(msg)
        return True, "sent"
    except Exception as e:
        return False, str(e)

# UI layout
col1, col2 = st.columns((2,1))
with col1:
    st.header("EduVision Pro — Real-Time Attention Tracker (Auto Email Reports)")
    video_placeholder = st.image(np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8))
    start_btn = st.button("Start Camera")
    stop_btn = st.button("Stop Camera (End Session)")
    auto_send = st.checkbox("Auto-send report after session ends", value=True)
    log_toggle = st.checkbox("Log attention to CSV", value=True)
with col2:
    st.subheader("Live Status")
    status_text = st.empty()
    score_text = st.empty()
    st.subheader("Session Summary")
    summary_box = st.empty()
    if st.button("Send Last Report Now"):
        # send most recent report if exists
        reports = sorted(REPORTS_DIR.glob("session_*.csv"), reverse=True)
        if reports:
            ok, msg = send_report_via_gmail(reports[0], CONFIG_FILE)
            if ok:
                st.success("Report sent successfully.")
            else:
                st.error(f"Failed to send: {msg}")
        else:
            st.info("No reports available to send.")


# Start / stop handling
if start_btn:
    if st.session_state.vc is None:
        st.session_state.vc = VideoCaptureAsync(CAM_INDEX)
    st.session_state.vc.start()
    st.session_state.running = True
    st.success("Camera started.")

if stop_btn and st.session_state.running:
    # Stop camera and finalize session: save report and optionally send email
    st.session_state.vc.stop()
    st.session_state.running = False

    # build report
    hist = st.session_state.attention_history.copy()
    if len(hist) == 0:
        st.info("No data recorded in this session.")
    else:
        df = pd.DataFrame(hist, columns=["timestamp","score","status"])
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"session_{ts}.csv"
        df.to_csv(report_path, index=False)
        # summary
        total = len(df)
        attentive = (df["status"] == "attentive").sum()
        distracted = (df["status"] == "distracted").sum()
        drowsy = (df["status"] == "drowsy").sum()
        absent = (df["status"] == "absent").sum()
        summary = f"Entries: {total} | Attentive: {attentive} | Distracted: {distracted} | Drowsy: {drowsy} | Absent: {absent}"
        summary_box.markdown("**Session Summary:**")
        summary_box.text(summary)
        st.success(f"Report saved: {report_path.name}")
        # auto-send via Gmail
        if auto_send:
            ok, msg = send_report_via_gmail(report_path, CONFIG_FILE)
            if ok:
                st.success("Report emailed to admin.")
            else:
                st.error(f"Email failed: {msg}")

# Main loop
if st.session_state.running:
    frame = st.session_state.vc.read()
    if frame is None:
        st.warning("Waiting for camera...")
    else:
        display = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(120,120))

        face_detected = False
        eyes_detected = False
        face_center_x = FRAME_WIDTH / 2

        if len(faces) > 0:
            faces = sorted(faces, key=lambda x: x[2]*x[3], reverse=True)
            x,y,w,h = faces[0]
            face_detected = True
            face_center_x = x + w/2
            cv2.rectangle(display, (x,y), (x+w, y+h), (10,130,200), 2)
            roi_gray = gray[y:y+int(h*0.6), x:x+w]
            eyes = eye_cascade.detectMultiScale(roi_gray, scaleFactor=1.1, minNeighbors=3, minSize=(20,10))
            if len(eyes) > 0:
                eyes_detected = True
                for (ex,ey,ew,eh) in eyes:
                    cv2.rectangle(display, (x+ex, y+ey), (x+ex+ew, y+ey+eh), (50,255,50), 1)

        score, status = compute_attention(face_detected, eyes_detected, face_center_x, FRAME_WIDTH)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.attention_history.append((timestamp, score, status))
        st.session_state.attention_history = st.session_state.attention_history[-300:]

        # save CSV live if logging enabled
        if log_toggle:
            df = pd.DataFrame(st.session_state.attention_history, columns=["timestamp","score","status"])
            df.to_csv(REPORTS_DIR / "session_live.csv", index=False)

        # update UI
        video_placeholder.image(cv2.cvtColor(display, cv2.COLOR_BGR2RGB))
        status_text.markdown(f"**Status:** {status.upper()}")
        score_text.markdown(f"**Score:** {score}")

        # chart
        if len(st.session_state.attention_history) > 0:
            hist_df = pd.DataFrame(st.session_state.attention_history[-60:], columns=["timestamp","score","status"])
            hist_df["time"] = pd.to_datetime(hist_df["timestamp"])
            hist_df = hist_df.set_index("time")
            st.line_chart(hist_df["score"])
        # fast update
        try:
            st.rerun()
        except Exception:
            # fallback for older streamlit versions
            try:
                st.experimental_rerun()
            except Exception:
                pass

else:
    st.info("Camera is stopped. Click 'Start Camera' to begin.")

# final note: cleanup when the script exits
import atexit
def finalize():
    try:
        if st.session_state.vc:
            st.session_state.vc.stop()
    except Exception:
        pass
atexit.register(finalize)

