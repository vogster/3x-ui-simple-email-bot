import os
from dotenv import load_dotenv

load_dotenv()

XUI_URL = os.getenv("XUI_URL", "http://localhost:2053").rstrip("/")
XUI_USERNAME = os.getenv("XUI_USERNAME", "admin")
XUI_PASSWORD = os.getenv("XUI_PASSWORD", "")
XUI_API_TOKEN = os.getenv("XUI_API_TOKEN", "").strip()
inbounds_raw = os.getenv("XUI_INBOUND_IDS") or os.getenv("XUI_INBOUND_ID") or "1"
XUI_INBOUND_IDS = [int(x.strip()) for x in inbounds_raw.split(",") if x.strip()]
XUI_SUBSCRIPTION_BASE_URL = os.getenv("XUI_SUBSCRIPTION_BASE_URL", f"{XUI_URL}/sub").rstrip("/")
XUI_FLOW = os.getenv("XUI_FLOW", "")

IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.yandex.ru")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.yandex.ru")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
CODEWORD = os.getenv("CODEWORD", "START_VPN").strip()
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "15"))

LIMIT_GB = int(os.getenv("LIMIT_GB", "50"))
EXPIRE_DAYS = int(os.getenv("EXPIRE_DAYS", "30"))
SERVICE_NAME = os.getenv("SERVICE_NAME", "My VPN").strip()

# Gotify Configuration
GOTIFY_URL = os.getenv("GOTIFY_URL", "").strip()
GOTIFY_TOKEN = os.getenv("GOTIFY_TOKEN", "").strip()
try:
    GOTIFY_PRIORITY = int(os.getenv("GOTIFY_PRIORITY", "5"))
except ValueError:
    GOTIFY_PRIORITY = 5

# App Urls Config
HAPP_URL = os.getenv("HAPP_URL", "")
INCY_URL = os.getenv("INCY_URL", "")
