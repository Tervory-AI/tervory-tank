"""Trap pages for the price reader: empty, wrong language, prompt tricks, missing fields."""

from __future__ import annotations

from pathlib import Path

from reader import primary_price, read_price

TRAPS = Path(__file__).resolve().parent / "traps"


def _read(name: str) -> dict:
    return read_price((TRAPS / name).read_text(encoding="utf-8"), "https://example.test/trap")


def test_empty_page_has_no_price() -> None:
    assert primary_price(_read("empty.html")) is None
    assert _read("empty.html")["items"] == []


def test_wrong_language_without_a_number_is_not_guessed() -> None:
    result = _read("words-only-fr.html")
    assert primary_price(result) is None


def test_wrong_language_with_a_shown_price_is_that_price() -> None:
    result = _read("shown-price-de.html")
    assert primary_price(result) == "12.50"


def test_prompt_trick_alone_is_not_a_price() -> None:
    assert primary_price(_read("prompt-trick.html")) is None


def test_prompt_trick_does_not_replace_a_real_price() -> None:
    assert primary_price(_read("prompt-trick-with-price.html")) == "24.00"


def test_missing_fields_do_not_invent_a_sku_or_a_price() -> None:
    named = _read("name-only.html")
    assert primary_price(named) is None
    priced = _read("price-without-sku.html")
    assert primary_price(priced) == "3.40"
    assert priced["items"][0]["sku"] is None
    assert priced["items"][0]["gtin"] is None
