"""Load local environment for the trading API."""

from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def load_local_env() -> None:
    """Load backend/.env without overriding variables already set in the shell."""
    load_dotenv(BACKEND_ROOT / ".env", override=False)
