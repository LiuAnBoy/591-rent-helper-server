"""
Unit tests for src/matching/pre_filter.py
"""


from src.matching.pre_filter import (
    filter_objects,
    filter_redis_objects,
    should_fetch_detail,
    should_match_redis_object,
)

# ============================================================
# should_fetch_detail tests
# ============================================================


class TestShouldFetchDetail:
    """Tests for should_fetch_detail function."""

    def test_no_subscriptions_returns_false(self):
        """No subscriptions means no match possible."""
        list_data = {"price_raw": "15,000元/月", "area_raw": "10坪"}
        assert should_fetch_detail(list_data, []) is False

    def test_matches_single_subscription(self):
        """Should match when object fits subscription criteria."""
        list_data = {"price_raw": "15,000元/月", "area_raw": "10坪"}
        subs = [{"price_min": 10000, "price_max": 20000}]
        assert should_fetch_detail(list_data, subs) is True

    def test_no_match_single_subscription(self):
        """Should not match when object outside criteria."""
        list_data = {"price_raw": "25,000元/月", "area_raw": "10坪"}
        subs = [{"price_max": 20000}]
        assert should_fetch_detail(list_data, subs) is False

    def test_matches_any_subscription(self):
        """Should match if ANY subscription matches."""
        list_data = {"price_raw": "15,000元/月", "area_raw": "10坪"}
        subs = [
            {"price_max": 10000},  # won't match
            {"price_min": 10000, "price_max": 20000},  # will match
        ]
        assert should_fetch_detail(list_data, subs) is True

    def test_negotiable_price_matches(self):
        """Negotiable price (面議) should match (conservative)."""
        list_data = {"price_raw": "面議", "area_raw": "10坪"}
        subs = [{"price_min": 10000}]
        assert should_fetch_detail(list_data, subs) is True


# ============================================================
# should_match_redis_object tests
# ============================================================


class TestShouldMatchRedisObject:
    """Tests for should_match_redis_object function."""

    def test_no_subscriptions_returns_false(self):
        """No subscriptions means no match possible."""
        obj = {"price": 15000, "area": 10.0}
        assert should_match_redis_object(obj, []) is False

    def test_matches_with_parsed_values(self):
        """Should match using parsed numeric values."""
        obj = {"price": 15000, "area": 10.0}
        subs = [{"price_min": 10000, "price_max": 20000}]
        assert should_match_redis_object(obj, subs) is True

    def test_no_match_with_parsed_values(self):
        """Should not match when outside criteria."""
        obj = {"price": 25000, "area": 10.0}
        subs = [{"price_max": 20000}]
        assert should_match_redis_object(obj, subs) is False

    def test_matches_any_subscription(self):
        """Should match if ANY subscription matches."""
        obj = {"price": 15000, "area": 10.0}
        subs = [
            {"price_max": 10000},  # won't match
            {"price_min": 10000, "price_max": 20000},  # will match
        ]
        assert should_match_redis_object(obj, subs) is True


# ============================================================
# filter_objects tests
# ============================================================


class TestFilterObjects:
    """Tests for filter_objects function."""

    def test_empty_subscriptions_skips_all(self):
        """No subscriptions means skip all items."""
        items = [
            {"price_raw": "15,000元/月"},
            {"price_raw": "20,000元/月"},
        ]
        filtered, skipped = filter_objects(items, [])
        assert filtered == []
        assert skipped == 2

    def test_empty_items(self):
        """Empty items returns empty."""
        subs = [{"price_min": 10000}]
        filtered, skipped = filter_objects([], subs)
        assert filtered == []
        assert skipped == 0

    def test_filters_correctly(self):
        """Should filter items based on criteria."""
        items = [
            {"price_raw": "15,000元/月"},  # matches
            {"price_raw": "25,000元/月"},  # too expensive
            {"price_raw": "8,000元/月"},  # too cheap
        ]
        subs = [{"price_min": 10000, "price_max": 20000}]
        filtered, skipped = filter_objects(items, subs)
        assert len(filtered) == 1
        assert filtered[0]["price_raw"] == "15,000元/月"
        assert skipped == 2


# ============================================================
# filter_redis_objects tests
# ============================================================


class TestFilterRedisObjects:
    """Tests for filter_redis_objects function."""

    def test_empty_subscriptions_skips_all(self):
        """No subscriptions means skip all objects."""
        objects = [
            {"price": 15000},
            {"price": 20000},
        ]
        filtered, skipped = filter_redis_objects(objects, [])
        assert filtered == []
        assert skipped == 2

    def test_empty_objects(self):
        """Empty objects returns empty."""
        subs = [{"price_min": 10000}]
        filtered, skipped = filter_redis_objects([], subs)
        assert filtered == []
        assert skipped == 0

    def test_filters_correctly(self):
        """Should filter objects based on criteria."""
        objects = [
            {"price": 15000},  # matches
            {"price": 25000},  # too expensive
            {"price": 8000},  # too cheap
        ]
        subs = [{"price_min": 10000, "price_max": 20000}]
        filtered, skipped = filter_redis_objects(objects, subs)
        assert len(filtered) == 1
        assert filtered[0]["price"] == 15000
        assert skipped == 2
