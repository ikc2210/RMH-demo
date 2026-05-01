import httpx
import os
from datetime import datetime, timezone, timedelta
from typing import Optional
import msal


SERVICE_TYPE_MAP = {
    "meal of love": "Meal of Love",
    "meals of love": "Meal of Love",
    "happy snacks": "Happy Snacks",
    "mcbakers": "McBakers",
    "mc bakers": "McBakers",
    "bakers": "McBakers",
}


def _normalize_service_type(name: str) -> str:
    lower = name.lower()
    for key, value in SERVICE_TYPE_MAP.items():
        if key in lower:
            return value
    return name


def _parse_custom_answers(answers: list[dict]) -> dict:
    """Extract structured fields from Microsoft Bookings custom question answers."""
    parsed = {
        "num_volunteers": None,
        "volunteer_dietary": "",
        "first_time": False,
        "group_notes": "",
    }
    for item in answers:
        q = item.get("question", "").lower()
        a = item.get("answer", "").strip()
        if not a:
            continue
        if any(k in q for k in ("how many", "number of volunteer", "group size")):
            try:
                parsed["num_volunteers"] = int("".join(filter(str.isdigit, a))) or None
            except (ValueError, TypeError):
                pass
        elif any(k in q for k in ("dietary", "allergy", "allergies", "restriction")):
            parsed["volunteer_dietary"] = a
        elif any(k in q for k in ("first time", "first visit", "never been")):
            parsed["first_time"] = a.lower() in ("yes", "true", "1", "y")
        elif any(k in q for k in ("note", "comment", "additional", "anything else")):
            parsed["group_notes"] = a
    return parsed


class BookingsClient:
    GRAPH_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(
        self,
        client_id: Optional[str],
        client_secret: Optional[str],
        tenant_id: Optional[str],
        business_id: Optional[str],
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.business_id = business_id
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    def _is_configured(self) -> bool:
        values = [self.client_id, self.client_secret, self.tenant_id, self.business_id]
        return all(v and not v.startswith("your-") for v in values)

    def _get_token(self) -> str:
        now = datetime.now(timezone.utc)
        if self._token and self._token_expiry and now < self._token_expiry:
            return self._token

        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )
        result = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            error = result.get("error_description", result.get("error", "Unknown auth error"))
            raise RuntimeError(f"MSAL token acquisition failed: {error}")

        self._token = result["access_token"]
        expires_in = result.get("expires_in", 3600)
        self._token_expiry = now + timedelta(seconds=expires_in - 60)
        return self._token

    async def get_upcoming_appointments(self, days: int = 14) -> list[dict]:
        if not self._is_configured():
            return _mock_appointments()

        token = self._get_token()
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days)

        start_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = end.strftime("%Y-%m-%dT%H:%M:%SZ")

        url = (
            f"{self.GRAPH_BASE}/solutions/bookingBusinesses"
            f"/{self.business_id}/appointments"
            f"?$filter=startDateTime/dateTime ge '{start_str}'"
            f" and startDateTime/dateTime le '{end_str}'"
        )

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                url, headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            data = response.json()

        appointments = []
        for appt in data.get("value", []):
            appointments.append(_parse_appointment(appt))

        appointments.sort(key=lambda a: a["start_dt"])
        return appointments

    async def get_appointment(self, appointment_id: str) -> Optional[dict]:
        if not self._is_configured():
            mocks = _mock_appointments()
            return next((a for a in mocks if a["id"] == appointment_id), None)

        token = self._get_token()
        url = (
            f"{self.GRAPH_BASE}/solutions/bookingBusinesses"
            f"/{self.business_id}/appointments/{appointment_id}"
        )
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                url, headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return _parse_appointment(response.json())


def _parse_appointment(appt: dict) -> dict:
    service_name = appt.get("serviceName", appt.get("displayName", "Unknown Service"))
    service_type = _normalize_service_type(service_name)

    # startDateTime and endDateTime come as {"dateTime": "...", "timeZone": "..."}
    start_raw = appt.get("startDateTime", {})
    end_raw = appt.get("endDateTime", {})
    start_str = start_raw.get("dateTime", "") if isinstance(start_raw, dict) else str(start_raw)
    end_str = end_raw.get("dateTime", "") if isinstance(end_raw, dict) else str(end_raw)

    try:
        start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        start_dt = datetime.now(timezone.utc)

    try:
        end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        end_dt = start_dt + timedelta(hours=2)

    # Customer info (first customer = booking contact / group lead)
    customers = appt.get("customers", [])
    customer = customers[0] if customers else {}
    group_name = customer.get("name") or appt.get("customerName", "Volunteer Group")
    customer_email = customer.get("emailAddress") or appt.get("customerEmailAddress", "")

    # Custom question answers
    raw_answers = customer.get("customQuestionAnswers", [])
    parsed = _parse_custom_answers(raw_answers)

    return {
        "id": appt.get("id", ""),
        "service_type": service_type,
        "service_name": service_name,
        "group_name": group_name,
        "customer_email": customer_email,
        "start_dt": start_dt.isoformat(),
        "end_dt": end_dt.isoformat(),
        "start_display": start_dt.strftime("%A, %B %-d, %Y at %-I:%M %p"),
        "duration_hours": round((end_dt - start_dt).total_seconds() / 3600, 1),
        "num_volunteers": parsed["num_volunteers"],
        "volunteer_dietary": parsed["volunteer_dietary"],
        "first_time": parsed["first_time"],
        "group_notes": parsed["group_notes"] or appt.get("customerNotes", ""),
        "staff_notes": appt.get("staffMembersEmailAddresses", []),
    }


def _mock_appointments() -> list[dict]:
    """Demo data shown when Azure credentials are not configured."""
    base = datetime.now(timezone.utc).replace(hour=17, minute=0, second=0, microsecond=0)

    def make(offset_days, service, group, email, volunteers, dietary="", first_time=False, notes=""):
        start = base + timedelta(days=offset_days)
        hours = 4 if service == "Meal of Love" else 2
        end = start + timedelta(hours=hours)
        return {
            "id": f"mock-{offset_days}",
            "service_type": service,
            "service_name": service,
            "group_name": group,
            "customer_email": email,
            "start_dt": start.isoformat(),
            "end_dt": end.isoformat(),
            "start_display": start.strftime("%A, %B %-d, %Y at %-I:%M %p"),
            "duration_hours": hours,
            "num_volunteers": volunteers,
            "volunteer_dietary": dietary,
            "first_time": first_time,
            "group_notes": notes,
            "staff_notes": [],
        }

    return [
        make(2, "Meal of Love", "St. Andrew's Presbyterian Church Youth Group",
             "youthgroup@standrewsoc.org", 12,
             dietary="one volunteer is vegetarian",
             first_time=True,
             notes="We're so excited to serve! We have a few experienced cooks."),
        make(5, "Happy Snacks", "Salesforce OC Team Volunteers",
             "volunteer-oc@salesforce.com", 8,
             dietary="one team member has a gluten intolerance",
             notes="Office team outing — mixed cooking experience."),
        make(8, "McBakers", "UCI Nursing Students Club",
             "nursingclub@uci.edu", 6,
             first_time=False,
             notes="We've baked for RMH twice before and love it."),
        make(11, "Meal of Love", "Newport Beach Junior League",
             "volunteers@nbjl.org", 15,
             dietary="two volunteers are vegan",
             first_time=True),
    ]
