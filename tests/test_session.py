import os
import sys

import pandas as pd
from pandas.testing import assert_frame_equal

from app import usf

sys.modules.setdefault("usf", usf)
from app import temframe

sys.modules.setdefault("temframe", temframe)
from app import basepanel

sys.modules.setdefault("basepanel", basepanel)
from app.session import Session


def test_session_save_and_load_round_trip(tmp_path):
    data = pd.DataFrame(
        {
            "site_id": [0, 0],
            "system_id": [0, 0],
            "gate_id": [0, 1],
            "dbdt": [1.25, 2.5],
            "error": [5.0, 6.0],
            "time": [1e-5, 2e-5],
            "inuse_auto": [True, True],
            "inuse_manual": [False, True],
            "date": [20261013, 20261013],
            "daytime": [1010.0, 1010.0],
            "latitude": [56.0, 56.0],
            "longitude": [10.0, 10.0],
            "elevation": [12.0, 12.0],
            "utm_x": [562000.0, 562000.0],
            "utm_y": [6210000.0, 6210000.0],
            "distance": [0.0, 0.0],
        }
    )
    models = pd.DataFrame(
        {
            "site_id": [0],
            "doi": [100.0],
            "layer": [0],
            "resistivity": [50.0],
        }
    )
    session = Session(data=data, models=models)
    folder = str(tmp_path) + os.sep

    session.save(folder)
    loaded = Session.from_folder(folder)

    assert_frame_equal(loaded.data, data, check_dtype=False)
    assert_frame_equal(loaded.models, models, check_dtype=False)
    assert loaded.site.loc[0, "site_id"] == 0
    assert loaded.site.loc[0, "doi"] == 100.0