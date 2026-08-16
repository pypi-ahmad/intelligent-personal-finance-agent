"""Map messy statement text to a clean merchant name."""

from __future__ import annotations

# Longer needles first so "uber eats" wins over "uber".
ALIASES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("uber eats", "ubereats"), "Uber Eats"),
    (("swiggy",), "Swiggy"),
    (("zomato",), "Zomato"),
    (("amazon", "amzn"), "Amazon"),
    (("flipkart",), "Flipkart"),
    (("myntra",), "Myntra"),
    (("bigbasket",), "BigBasket"),
    (("blinkit",), "Blinkit"),
    (("zepto",), "Zepto"),
    (("netflix",), "Netflix"),
    (("spotify",), "Spotify"),
    (("uber",), "Uber"),
    (("ola",), "Ola"),
    (("rapido",), "Rapido"),
    (("irctc",), "IRCTC"),
    (("airtel",), "Airtel"),
    (("jio",), "Jio"),
    (("starbucks",), "Starbucks"),
    (("dominos", "domino's"), "Dominos"),
    (("bookmyshow",), "BookMyShow"),
    (("apollo",), "Apollo"),
    (("nykaa",), "Nykaa"),
    (("ajio",), "Ajio"),
)


def normalize_merchant(description: str) -> str | None:
    text = description.lower()
    for needles, name in ALIASES:
        if any(needle in text for needle in needles):
            return name
    return None


def merchant_key(description: str) -> str:
    return normalize_merchant(description) or " ".join(description.lower().split())[:80]
