"""Env and provider settings. Keys come from the environment only."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "finance.db"

PROVIDERS = ("Ollama", "OpenAI", "Agnes AI", "Google")

OPENAI_MODELS = ("gpt-5.6-luna", "gpt-5.6-terra")
OPENAI_EFFORT = "medium"

AGNES_MODEL = "agnes-2.5-flash"
AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"

GOOGLE_MODELS = ("gemini-3.5-flash-lite", "gemini-3.7-flash")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

ACCOUNT_KINDS = ("asset", "liability")
GOAL_KINDS = ("savings", "debt")

TRAVEL_NEEDLES = (
    "irctc",
    "flight",
    "airbnb",
    "hotel",
    "makemytrip",
    "goibibo",
    "indigo",
    "air india",
    "yatra",
    "airport",
    "booking.com",
    "outstation",
    "railway",
    "uber intercity",
)

CATEGORIES = (
    "FOOD",
    "GROCERIES",
    "TRANSPORT",
    "UTILITIES",
    "RENT",
    "SHOPPING",
    "HEALTH",
    "ENTERTAINMENT",
    "TRANSFER",
    "INCOME",
    "FEES",
    "OTHER",
)


def env(name: str) -> str:
    return os.getenv(name, "").strip()
