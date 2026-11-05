import sys
from types import SimpleNamespace

import numpy as np

from app import usf

sys.modules["usf"] = usf
from app import temframe


def make_sweep(points, data, daytime, longitude):
    sweep = usf.Sweep(
        data=np.asarray(data, dtype=float),
        time=np.array([1e-5, 2e-5]),
        error=np.array([5.0, 5.0]),
        quality=np.array([True, True]),
        tx_ramp=np.array([0.0, 1.0, 0.0]),
        tx_ramp_time=np.array([0.0, 1e-5, 2e-5]),
        current=1.0,
        frequency=25.0,
        is_noise=False,
        field_shift_factor=1.0,
        time_delay=0.0,
        ramp_time=1e-5,
        tx_turnontime=1e-5,
        ramp_time_on=2e-5,
        number=1,
        channel=1,
        low_pass=np.array([1000.0, 2.0]),
        points=points,
    )
    sweep.date = 20261013
    sweep.daytime = daytime
    sweep.location = np.array([longitude, 56.0, 10.0])
    return sweep


def test_combine_sweeps_stacks_site_data():
    first = make_sweep(2, [10, 20], daytime=100, longitude=10.0)
    second = make_sweep(2, [30, 40], daytime=200, longitude=10.001)

    combined = usf.Sweep.combine_sweeps([first, second])

    assert combined.data.shape == (2, 2)
    np.testing.assert_array_equal(combined.data, [[10, 20], [30, 40]])
    np.testing.assert_array_equal(combined.time, [[1e-5, 2e-5], [1e-5, 2e-5]])
    np.testing.assert_array_equal(combined.daytime, [100, 200])


def test_from_sweeps_preserves_measurement_table_invariants(monkeypatch):
    sweeps = [
        make_sweep(2, [10, 20], daytime=100, longitude=10.0),
        make_sweep(2, [30, 40], daytime=200, longitude=10.001),
        make_sweep(3, [100, 200], daytime=100, longitude=10.0),
        make_sweep(3, [300, 400], daytime=200, longitude=10.001),
    ]
    monkeypatch.setattr(
        usf,
        "sweep2fwr",
        lambda _: [
            SimpleNamespace(source=None, receiver=None, filterfunc=None),
            SimpleNamespace(source=None, receiver=None, filterfunc=None),
        ],
    )

    data, forwards = temframe.from_sweeps(sweeps)

    assert len(forwards) == 2
    assert len(data) == 8
    assert set(data["site_id"]) == {0, 1}
    assert set(data["system_id"]) == {0, 1}
    assert set(data["gate_id"]) == {0, 1}
    assert not data.duplicated(["site_id", "system_id", "gate_id"]).any()
    assert data.groupby(["site_id", "system_id"]).size().eq(2).all()

    values = data.set_index(["site_id", "system_id", "gate_id"])["dbdt"]
    np.testing.assert_array_equal(values.loc[0, 0].to_numpy(), [10, 20])
    np.testing.assert_array_equal(values.loc[1, 0].to_numpy(), [30, 40])
    np.testing.assert_array_equal(values.loc[0, 1].to_numpy(), [100, 200])
    np.testing.assert_array_equal(values.loc[1, 1].to_numpy(), [300, 400])