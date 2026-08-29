from student_api import detect_distribution


def test_extreme_mean_shift_detected():
    baseline = [9, 10, 11, 10, 10]
    current = [190, 200, 210, 205]
    assert detect_distribution(current, baseline)["is_anomaly"] is True
