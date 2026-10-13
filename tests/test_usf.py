import numpy as np

from app.usf import Sweep


def test_from_usf_text_parses_sweep_fields():
    text = """\
/SWEEP_POINTS: 2
/SWEEP_TX_RAMP: 0, 0, 0.00001, 1, 0.00002, 0
/SWEEP_CURRENT: 2
/SWEEP_FREQUENCY: 25
/SWEEP_IS_NOISE: 0
/SWEEP_FIELD_SHIFT_FACTOR: 1
/SWEEP_TIME_DELAY: 0
/SWEEP_RAMP_TIME: 0.00001
/SWEEP_TX_TURNONTIME: 0.00001
/SWEEP_RAMP_TIME_ON: 0.00002
/SWEEP_NUMBER: 1
/SWEEP_CHANNEL: 1
/SWEEP_LOW_PASS: 1000, 2
/END


0.00001, 2.5, 5, 1
0.00002, 1.25, 10, 0
"""

    sweep = Sweep.from_usf_text(text)

    assert sweep.points == 2
    assert sweep.current == 2
    np.testing.assert_array_equal(sweep.time, [0.00001, 0.00002])
    np.testing.assert_array_equal(sweep.data, [2.5, 1.25])
    np.testing.assert_array_equal(sweep.error, [5, 10])
    np.testing.assert_array_equal(sweep.quality, [True, False])
    np.testing.assert_array_equal(sweep.tx_ramp_time, [0, 0.00001, 0.00002])
    np.testing.assert_array_equal(sweep.tx_ramp, [0, 1, 0])