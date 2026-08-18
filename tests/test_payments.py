import config
from services.payments import PRODUCTS, make_payload, parse_payload


def test_launch_prices_are_99_stars_for_all_paid_products():
    assert set(PRODUCTS) == {"natal", "year", "together"}
    assert config.REPORT_PRICES_XTR == {"natal": 99, "year": 99, "together": 99}


def test_invoice_payload_round_trip_is_bound_to_user():
    for product in PRODUCTS:
        payload = make_payload(product, 382403468)
        assert parse_payload(payload) == (product, 382403468)


def test_invalid_payloads_are_rejected():
    assert parse_payload("inner_compass:natal:not-a-user") is None
    assert parse_payload("inner_compass:unknown:123") is None
    assert parse_payload("natal:123") is None
