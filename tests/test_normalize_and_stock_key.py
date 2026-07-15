from mf_screener.load import canonical_holding_display_name, stock_key
from mf_screener.symbol_map import normalize_company_name


def test_limited_and_ltd_same_key() -> None:
    a = stock_key("", "", "Wockhardt Limited")
    b = stock_key("", "", "Wockhardt Ltd.")
    assert a == b
    assert normalize_company_name("Wockhardt Limited") == normalize_company_name(
        "Wockhardt Ltd."
    )


def test_canonical_display_prefers_longer() -> None:
    name = canonical_holding_display_name(
        ["Welspun Corp Ltd.", "Welspun Corp Limited"]
    )
    assert name == "Welspun Corp Limited"


def test_clean_holding_strips_rupeevest_markers() -> None:
    from mf_screener.load import _clean_holding_name

    assert _clean_holding_name("HDFC Bank Ltd $$~~") == "HDFC Bank Ltd"
    assert _clean_holding_name("IndusInd Bank Limited ^^^") == "IndusInd Bank Limited"
    assert _clean_holding_name("Jubilant Foodworks Limited ‡") == "Jubilant Foodworks Limited"
    assert _clean_holding_name("Talwandi Sabo Power Limited **") == "Talwandi Sabo Power Limited"
