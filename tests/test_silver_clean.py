"""
tests/test_silver_clean.py
Unit tests for Silver layer cleaning functions.
"""

import pytest
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.silver_clean import (
    parse_price,
    parse_date,
    normalize_room_type,
    normalize_property_type,
    parse_amenities,
)


class TestParsePrice:
    """Tests for the price parsing utility."""

    def test_dollar_sign_removed(self):
        s = pd.Series(["$150.00"])
        result = parse_price(s)
        assert result[0] == pytest.approx(150.0)

    def test_comma_removed(self):
        s = pd.Series(["$1,200.00"])
        result = parse_price(s)
        assert result[0] == pytest.approx(1200.0)

    def test_plain_number(self):
        s = pd.Series(["75"])
        result = parse_price(s)
        assert result[0] == pytest.approx(75.0)

    def test_invalid_returns_nan(self):
        s = pd.Series(["N/A", "not a price", ""])
        result = parse_price(s)
        assert result.isna().all()

    def test_negative_price_parsed(self):
        # Negative prices should parse — validator flags them, not cleaner
        s = pd.Series(["-50"])
        result = parse_price(s)
        assert result[0] == pytest.approx(-50.0)

    def test_mixed_series(self):
        s = pd.Series(["$100", "$1,500.50", "N/A", None])
        result = parse_price(s)
        assert result[0] == pytest.approx(100.0)
        assert result[1] == pytest.approx(1500.50)
        assert pd.isna(result[2])
        assert pd.isna(result[3])


class TestParseDate:
    """Tests for the date parsing utility."""

    def test_iso_date(self):
        s = pd.Series(["2023-01-15"])
        result = parse_date(s)
        assert result[0] == pd.Timestamp("2023-01-15")

    def test_invalid_returns_nat(self):
        s = pd.Series(["not-a-date", "9999-99-99", ""])
        result = parse_date(s)
        assert result.isna().all()

    def test_none_returns_nat(self):
        s = pd.Series([None])
        result = parse_date(s)
        assert pd.isna(result[0])


class TestNormalizeRoomType:
    """Tests for room type normalization."""

    def test_entire_home(self):
        s = pd.Series(["Entire home/apt"])
        result = normalize_room_type(s)
        assert result[0] == "Entire home/apt"

    def test_lowercase_normalization(self):
        s = pd.Series(["entire home/apt", "PRIVATE ROOM", "Shared Room"])
        result = normalize_room_type(s)
        assert result[0] == "Entire home/apt"
        assert result[1] == "Private room"
        assert result[2] == "Shared room"

    def test_hotel_room(self):
        s = pd.Series(["Hotel room"])
        result = normalize_room_type(s)
        assert result[0] == "Hotel room"


class TestParseAmenities:
    """Tests for amenity string parsing."""

    def test_json_array_string(self):
        s = pd.Series(['["Wifi", "Kitchen", "Air conditioning"]'])
        result = parse_amenities(s)
        assert "Wifi" in result[0]
        assert "Kitchen" in result[0]

    def test_empty_returns_empty_list(self):
        s = pd.Series(["", None])
        result = parse_amenities(s)
        assert result[0] == []
        assert result[1] == []

    def test_single_amenity(self):
        s = pd.Series(['["Wifi"]'])
        result = parse_amenities(s)
        assert len(result[0]) == 1


class TestNormalizePropertyType:
    """Tests for property type normalization."""

    def test_apartment(self):
        s = pd.Series(["Entire apartment"])
        result = normalize_property_type(s)
        assert result[0] == "Apartment"

    def test_unknown_maps_to_other(self):
        s = pd.Series(["Some weird unknown type xyz"])
        result = normalize_property_type(s)
        assert result[0] == "Other"

    def test_house(self):
        s = pd.Series(["Entire house"])
        result = normalize_property_type(s)
        assert result[0] == "House"
