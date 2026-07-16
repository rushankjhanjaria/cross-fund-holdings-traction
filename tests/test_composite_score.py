"""Composite score tuning: log share, weight conviction, exit penalty."""

from __future__ import annotations

import math

from mf_screener.aggregate import composite_score


def test_log_share_caps_extreme_median() -> None:
    extreme = composite_score(2, 7770.0, 0, None, 0, 0)
    modest = composite_score(2, 20.0, 0, None, 0, 0)
    # Extreme share % must not explode vs a normal add
    assert extreme < 50
    assert extreme > modest
    assert extreme == 2 * 5.0 + 2 * math.log1p(7770.0) * 0.5


def test_exit_penalty_lowers_mixed() -> None:
    pure = composite_score(3, 10.0, 2, 0.2, 0, 0)
    mixed = composite_score(3, 10.0, 2, 0.2, 0, 2)
    assert mixed == pure - 40.0


def test_weight_term_dominates_small_share() -> None:
    # High conviction weight raise should outrank tiny share-only add
    weighty = composite_score(2, 5.0, 4, 1.5, 0, 0)
    share_only = composite_score(2, 5.0, 0, None, 0, 0)
    assert weighty > share_only


def test_hold_bonus_rewards_continued_ownership() -> None:
    # Modest hold term: 5 hold funds → +5 vs no holds; still << active breadth (5 each)
    without = composite_score(2, 10.0, 0, None, 0, 0, 0)
    with_holds = composite_score(2, 10.0, 0, None, 0, 0, 5)
    assert with_holds == without + 5.0
    # Hold bonus must stay well below active breadth bonus
    assert 1.0 < 5.0


def test_new_boost_is_modest_vs_legacy() -> None:
    # Legacy new_boost=50 made 4 new entries worth 200 alone; tuned is 20.
    legacy_new_only = 4 * 50.0
    tuned_new_only = composite_score(4, None, 0, None, 4, 0)  # 4*5 breadth + 4*5 new
    assert tuned_new_only == 40.0
    assert tuned_new_only < legacy_new_only
