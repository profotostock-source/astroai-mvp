from types import SimpleNamespace
from bot import _format_star_amount

def test_format_whole_star_amount():
    assert _format_star_amount(SimpleNamespace(amount=99, nanostar_amount=0)) == "99"

def test_format_fractional_star_amount():
    amount = SimpleNamespace(amount=99, nanostar_amount=250_000_000)
    assert _format_star_amount(amount) == "99.25"