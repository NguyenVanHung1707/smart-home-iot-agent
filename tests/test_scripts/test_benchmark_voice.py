from scripts.benchmark_voice import edit_distance, error_rate, percentile


def test_edit_distance_and_error_rates():
    assert edit_distance(list("abc"), list("adc")) == 1
    assert error_rate("bật đèn", "bật đèn", words=True) == 0
    assert error_rate("bật đèn", "bật quạt", words=True) == 0.5


def test_percentile_uses_nearest_rank_in_bounded_list():
    assert percentile([10, 20, 30, 40], 0.5) == 30
    assert percentile([10, 20, 30, 40], 0.95) == 40
    assert percentile([], 0.95) == 0
