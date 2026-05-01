import json
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from bookings import BookingsClient
from guide_generator import GuideGenerator

load_dotenv()

app = FastAPI(title="RMH Meals of Love Guide Generator")
app.mount("/static", StaticFiles(directory="static"), name="static")

RESIDENT_DATA_FILE = Path("resident_data.json")

DEFAULT_RESIDENTS = {
    "num_families": 0,
    "total_people": 0,
    "children_breakdown": "",
    "dietary_restrictions": "",
    "cultural_preferences": "",
    "families_joining_dinner": 0,
    "volunteer_notes": "",
    "last_updated": None,
}


def load_residents() -> dict:
    if RESIDENT_DATA_FILE.exists():
        return json.loads(RESIDENT_DATA_FILE.read_text())
    return DEFAULT_RESIDENTS.copy()


def _bookings_client() -> BookingsClient:
    return BookingsClient(
        client_id=os.getenv("AZURE_CLIENT_ID"),
        client_secret=os.getenv("AZURE_CLIENT_SECRET"),
        tenant_id=os.getenv("AZURE_TENANT_ID"),
        business_id=os.getenv("BOOKING_BUSINESS_ID"),
    )


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/api/residents")
async def get_residents():
    return load_residents()


class ResidentData(BaseModel):
    num_families: int = 0
    total_people: int = 0
    children_breakdown: str = ""
    dietary_restrictions: str = ""
    cultural_preferences: str = ""
    families_joining_dinner: int = 0
    volunteer_notes: str = ""


@app.post("/api/residents")
async def update_residents(data: ResidentData):
    resident_dict = data.model_dump()
    resident_dict["last_updated"] = datetime.now().isoformat()
    RESIDENT_DATA_FILE.write_text(json.dumps(resident_dict, indent=2))
    return {"status": "saved", "last_updated": resident_dict["last_updated"]}


@app.get("/api/bookings")
async def get_bookings():
    client = _bookings_client()
    try:
        appointments = await client.get_upcoming_appointments(days=14)
        return {"appointments": appointments}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SendGuideRequest(BaseModel):
    to_email: str
    subject: str
    guide_text: str
    group_name: str


@app.post("/api/send-guide")
async def send_guide(req: SendGuideRequest):
    smtp_host = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    from_email = os.getenv("EMAIL_FROM", "")
    password = os.getenv("EMAIL_PASSWORD", "")

    if not from_email or not password:
        raise HTTPException(
            status_code=500,
            detail="Email not configured. Add EMAIL_FROM and EMAIL_PASSWORD to .env"
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = req.subject
    msg["From"] = f"Ronald McDonald House OC <{from_email}>"
    msg["To"] = req.to_email

    # Plain text part
    msg.attach(MIMEText(req.guide_text, "plain"))

    # HTML part — render markdown-ish formatting into basic HTML
    html_body = _guide_to_html(req.guide_text, req.group_name)
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(from_email, password)
            server.sendmail(from_email, req.to_email, msg.as_string())
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(
            status_code=401,
            detail="Email authentication failed. Check EMAIL_FROM and EMAIL_PASSWORD."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {e}")

    return {"status": "sent", "to": req.to_email}


def _guide_to_html(text: str, group_name: str) -> str:
    """Convert the guide markdown to a clean HTML email."""
    import html as html_module
    lines = text.split("\n")
    body_lines = []

    for line in lines:
        escaped = html_module.escape(line)
        if escaped.startswith("# "):
            body_lines.append(f'<h1 style="color:#DA291C;font-size:22px;margin:0 0 4px">{escaped[2:]}</h1>')
        elif escaped.startswith("## "):
            body_lines.append(f'<h2 style="color:#666;font-size:13px;font-weight:400;margin:0 0 20px">{escaped[3:]}</h2>')
        elif escaped.startswith("### "):
            body_lines.append(
                f'<h3 style="color:#b31e12;font-size:15px;margin:28px 0 8px;'
                f'padding-bottom:6px;border-bottom:2px solid #f5dedd">{escaped[4:]}</h3>'
            )
        elif escaped.startswith("#### "):
            body_lines.append(f'<h4 style="font-size:13px;margin:16px 0 6px">{escaped[5:]}</h4>')
        elif escaped.startswith("---"):
            body_lines.append('<hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0">')
        elif escaped.startswith("- ") or escaped.startswith("* "):
            content = _inline_md(escaped[2:])
            body_lines.append(f'<li style="margin-bottom:4px">{content}</li>')
        elif escaped.strip() == "":
            body_lines.append("<br>")
        else:
            body_lines.append(f'<p style="margin:0 0 10px;line-height:1.6">{_inline_md(escaped)}</p>')

    body_html = "\n".join(body_lines)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             max-width:640px;margin:0 auto;padding:24px;color:#111827;font-size:14px">
  <div style="background:#DA291C;padding:16px 24px;border-radius:8px 8px 0 0;margin-bottom:0">
    <span style="color:white;font-weight:800;font-size:18px">🏠 Ronald McDonald House Orange County</span>
  </div>
  <div style="background:#fff8e1;border:1px solid #FFC72C;border-top:none;
              padding:10px 24px;margin-bottom:24px;border-radius:0 0 8px 8px;
              font-size:12px;color:#7c5a00">
    Volunteer Preparation Guide for <strong>{html_module.escape(group_name)}</strong>
  </div>
  {body_html}
  <div style="margin-top:40px;padding-top:20px;border-top:1px solid #e5e7eb;
              font-size:12px;color:#6b7280;text-align:center">
    Ronald McDonald House Charities of Orange County · Sent via Coordinator Dashboard
  </div>
</body>
</html>"""


def _inline_md(text: str) -> str:
    """Convert bold/italic markdown to HTML inline."""
    import re
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    return text


@app.post("/api/generate-guide/{booking_id}")
async def generate_guide(booking_id: str):
    client = _bookings_client()
    try:
        booking = await client.get_appointment(booking_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bookings API error: {e}")

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    residents = load_residents()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    generator = GuideGenerator(api_key=api_key)

    return StreamingResponse(
        generator.stream_guide(booking, residents),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
