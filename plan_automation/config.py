from pathlib import Path
import os

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

SERVICE_ACCOUNT_PATH = Path(
    os.environ.get(
        "PLAN_AUTOMATION_SA",
        WORKSPACE_ROOT / ".secrets" / "plan-automation.json",
    )
)

TEMPLATE_PRESENTATION_ID = os.environ.get("PLAN_AUTOMATION_TEMPLATE_ID", "")

STORE_DIR = WORKSPACE_ROOT / "raw" / "auto"
WIKI_DIR = WORKSPACE_ROOT / "wiki"

SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
]
