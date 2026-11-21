from src.normalize import CORE, EXCLUDED, GRAY_ZONE, normalize_title, row_hash, tag_title


def test_normalize_variants():
    assert normalize_title("MAXI DRESS WHITE") == "maxi dress white"
    assert normalize_title("Women's Maxi-Dress Floral") == "women s maxi dress floral"
    assert normalize_title("  Maxi   Dress  ") == "maxi dress"


def test_core():
    assert tag_title("maxi dress floral") == CORE
    assert tag_title("formal maxi dress") == CORE


def test_exclude_mini_midi():
    assert tag_title("summer mini dress") == EXCLUDED
    assert tag_title("midi dress black") == EXCLUDED


def test_exclude_maxi_without_dress():
    # maxi skirt ≠ maxi dress：含 maxi 但缺 dress 判 excluded
    assert tag_title("maxi skirt") == EXCLUDED


def test_gray_zone():
    assert tag_title("elegant long dress") == GRAY_ZONE


def test_row_hash_stable():
    row = {"product_id": 1, "title_norm": "maxi dress", "sales_count": 2,
           "dt_utc": "2024-01-01T07:00:00+00:00", "user_id": "U1",
           "category": "dress", "platform": "app"}
    assert row_hash(row) == row_hash(dict(row))
    other = dict(row, sales_count=3)
    assert row_hash(row) != row_hash(other)
