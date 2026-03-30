import sys,os
fpath = os.path.dirname(os.path.abspath(__file__))
if fpath not in sys.path:
    sys.path.append(fpath)

import session
global sesh
sesh = session.Session()

import app


print("app successfully loaded")
