from sqlalchemy import Column, Integer, Float, Boolean, String
import json
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import numpy as np


Base = declarative_base()


# # example file to be entered into the database
# file_contents = """
# //Data from TEMcompany instrument, TEMcompany.com
# //stb2UFS.exe version: 1.9.8
# //stb-file name: C:\Users\au646858\Downloads\2025_0303\2025_0303_112057\2025_0303_112057.stb
# //StackType: StationStack by stb2usf.exe
# //InstrumentType: sTEM
# //InstrumentID: sTEM00
# //stb-FileVersion: 4.4

# //USF: Universal Sounding Format
# //SOUNDING_GROUP_NAME: Dollow blue
# //SOUNDINGS: 1
# //EPSG: 4326
# //DUMMY: 99999
# //END

# /DATE: 20250303
# /DAYTIME:  11.35028
# /ARRAY: FIXED LOOP TEM
# /LOOP_SIZE:    3.00,   3.00
# /SOUNDING_NAME: Line000_094
# /SWEEPS: 2
# /LOCATION:    42.0626403,    4.1518025,   183.00
# /COIL_LOCATION:  -13.00,   0.00
# /Z_DIRECTION: DOWN
# /LENGTH_UNITS: M
# /VOLTAGE_UNITS: V/AM2

# /SWEEP_NUMBER: 1
# /CURRENT:    1.00
# /FREQUENCY:  2109.70
# /SWEEP_IS_NOISE: 0
# /FIELD_SHIFT_FACTOR:    0.9800
# /TIME_DELAY:  0.000e+00
# /RAMP_TIME:  4.000000e-06
# /TX_TURNONTIME: 99999
# /RAMP_TIME_ON: 99999
# /TX_RAMP:  -6.740000e-04, -0.0000, -6.609420e-04, -0.2044, -6.440060e-04, -0.3969, -6.245080e-04, -0.5688, -6.014190e-04, -0.7170, -5.788420e-04, -0.8105, -5.485690e-04, -0.8848, -5.198360e-04, -0.9445, -4.844320e-04, -0.9810, -4.757090e-04, -1.0000, -4.740000e-04, -1.0000, -4.738280e-04, -0.9666, -4.736830e-04, -0.8667, -4.735020e-04, -0.6630, -4.733210e-04, -0.4539, -4.731610e-04, -0.2925, -4.730160e-04, -0.1823, -4.727630e-04, -0.0626, -4.724220e-04, -0.0055, -4.700000e-04, -0.0000, -2.000000e-04,  0.0000, -1.869420e-04,  0.2044, -1.700060e-04,  0.3969, -1.505080e-04,  0.5688, -1.274190e-04,  0.7170, -1.048420e-04,  0.8105, -7.456930e-05,  0.8848, -4.583570e-05,  0.9445, -1.043180e-05,  0.9810, -1.709070e-06,  1.0000,  0.000000e+00,  1.0000,  1.717450e-07,  0.9666,  3.167110e-07,  0.8667,  4.979190e-07,  0.6630,  6.791270e-07,  0.4539,  8.385910e-07,  0.2925,  9.835570e-07,  0.1823,  1.237250e-06,  0.0626,  1.577920e-06,  0.0055,  4.000000e-06,  0.0000
# /POINTS: 6
# /LOW_PASS:    450000,  1.00,   800000,  1.00
# /CHANNEL: 1
# /END

#         TIME,      VOLTAGE, ERROR_BAR, QUALITY,     TIMEOPEN,    TIMECLOSE
#  1.09820e-05,  7.24326e-06,     3.00,      1,    9.61766e-06,  1.25398e-05
#  1.34004e-05,  5.56994e-06,     3.00,      1,    1.17357e-05,  1.53013e-05
#  1.63515e-05,  3.79033e-06,     3.00,      1,    1.43201e-05,  1.86710e-05
#  1.99524e-05,  2.44012e-06,     3.00,      1,    1.74736e-05,  2.27827e-05
#  2.43463e-05,  1.52228e-06,     3.00,      1,    2.13217e-05,  2.77999e-05
#  2.97078e-05,  9.31193e-07,     3.00,      1,    2.60171e-05,  3.39220e-05
# /END

# /SWEEP_NUMBER: 2
# /CURRENT:    9.99
# /FREQUENCY:  217.39
# /SWEEP_IS_NOISE: 0
# /FIELD_SHIFT_FACTOR:    1.0000
# /TIME_DELAY:  3.000e-07
# /RAMP_TIME:  5.000000e-06
# /TX_TURNONTIME: 99999
# /RAMP_TIME_ON: 99999
# /TX_RAMP:  -6.200000e-03, -0.0000, -6.177610e-03, -0.2595, -6.157480e-03, -0.4380, -6.125260e-03, -0.6358, -6.072900e-03, -0.8162, -6.008460e-03, -0.9191, -5.940000e-03, -0.9649, -5.847370e-03, -0.9872, -5.654050e-03, -0.9992, -5.158680e-03, -0.9998, -4.751910e-03, -0.9998, -4.610950e-03, -1.0000, -4.600000e-03, -1.0000, -4.599880e-03, -0.9894, -4.599710e-03, -0.9424, -4.599470e-03, -0.8164, -4.599210e-03, -0.6485, -4.598940e-03, -0.4510, -4.598680e-03, -0.2711, -4.598480e-03, -0.1732, -4.598280e-03, -0.1051, -4.597890e-03, -0.0414, -4.596880e-03, -0.0151, -4.595000e-03, -0.0000, -1.600000e-03,  0.0000, -1.577610e-03,  0.2595, -1.557480e-03,  0.4380, -1.525260e-03,  0.6358, -1.472900e-03,  0.8162, -1.408460e-03,  0.9191, -1.340000e-03,  0.9649, -1.247370e-03,  0.9872, -1.054050e-03,  0.9992, -5.586790e-04,  0.9998, -1.519100e-04,  0.9998, -1.095100e-05,  1.0000,  0.000000e+00,  1.0000,  1.210070e-07,  0.9894,  2.877180e-07,  0.9424,  5.341610e-07,  0.8164,  7.878520e-07,  0.6485,  1.063290e-06,  0.4510,  1.324230e-06,  0.2711,  1.519930e-06,  0.1732,  1.715640e-06,  0.1051,  2.114300e-06,  0.0414,  3.121810e-06,  0.0151,  5.000000e-06,  0.0000
# /POINTS: 22
# /LOW_PASS:    450000,  1.00,   800000,  1.00
# /CHANNEL: 2
# /END

#         TIME,      VOLTAGE, ERROR_BAR, QUALITY,     TIMEOPEN,    TIMECLOSE
#  2.24694e-05,  1.84931e-06,     3.00,      1,    1.93818e-05,  2.60488e-05
#  2.80485e-05,  1.07548e-06,     3.00,      1,    2.41943e-05,  3.25166e-05
#  3.50129e-05,  6.15350e-07,     3.00,      1,    3.02017e-05,  4.05904e-05
#  4.37065e-05,  3.48177e-07,     3.00,      1,    3.77007e-05,  5.06690e-05
#  5.45587e-05,  1.95286e-07,     3.00,      1,    4.70617e-05,  6.32500e-05
#  6.81055e-05,  1.08762e-07,     3.00,      1,    5.87471e-05,  7.89548e-05
#  8.50160e-05,  6.02503e-08,     3.00,      1,    7.33339e-05,  9.85592e-05
#  1.06125e-04,  3.33671e-08,     3.00,      1,    9.15426e-05,  1.23031e-04
#  1.32476e-04,  1.85465e-08,     3.00,      1,    1.14272e-04,  1.53580e-04
#  1.65370e-04,  1.04438e-08,     3.00,      1,    1.42646e-04,  1.91713e-04
#  2.06431e-04,  6.02683e-09,     3.00,      1,    1.78065e-04,  2.39315e-04
#  2.57687e-04,  3.57774e-09,     3.00,      1,    2.22278e-04,  2.98737e-04
#  3.21670e-04,  2.17899e-09,     3.01,      1,    2.77469e-04,  3.72913e-04
#  4.01540e-04,  1.34334e-09,     3.01,      1,    3.46364e-04,  4.65506e-04
#  5.01242e-04,  8.35168e-10,     3.03,      1,    4.32366e-04,  5.81090e-04
#  6.25700e-04,  5.08803e-10,     3.03,      1,    5.39721e-04,  7.25374e-04
#  7.81060e-04,  3.07125e-10,     3.10,      1,    6.73733e-04,  9.05483e-04
#  9.74995e-04,  1.86277e-10,     3.17,      1,    8.41020e-04,  1.13031e-03
#  1.21708e-03,  1.07722e-10,     3.59,      1,    1.04984e-03,  1.41097e-03
#  1.51928e-03,  6.03291e-11,     4.73,      1,    1.31052e-03,  1.76131e-03
#  1.89652e-03,  3.22872e-11,     6.59,      1,    1.63592e-03,  2.19864e-03
#  2.36742e-03,  1.67029e-11,    10.15,      1,    2.04211e-03,  2.74456e-03
# /END

# """

# class Setup(Base):
#     __tablename__ = 'setup'
#     id = Column(Integer, primary_key=True)
#     date = Column(String)
#     daytime = Column(Float)
#     array = Column(String)
#     loop_size = Column(String)
#     sounding_name = Column(String)
#     sweeps = Column(Integer)
#     location = Column(String)
#     coil_location = Column(String)
#     z_direction = Column(String)
#     length_units = Column(String)
#     voltage_units = Column(String)
#     current = Column(Float)
#     frequency = Column(Float)
#     sweep_is_noise = Column(Boolean)
#     field_shift_factor = Column(Float)
#     time_delay = Column(Float)
#     ramp_time = Column(Float)
#     tx_turnontime = Column(Integer)
#     ramp_time_on = Column(Integer)
#     tx_ramp = Column(String)
#     points = Column(Integer)
#     low_pass = Column(String)
#     channel = Column(Integer)

# class Data(Base):
#     __tablename__ = 'data'
#     id = Column(Integer, primary_key=True)
#     setup_id = Column(Integer)
#     time = Column(Float)
#     voltage = Column(Float)
#     error_bar = Column(Float)
#     quality = Column(Integer)
#     time_open = Column(Float)
#     time_close = Column(Float)

# Create an engine and a session
engine = create_engine('sqlite:///gis_viewer.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# # Parse the file contents and populate the tables
# lines = file_contents.split('\n')
# setup_data = {}
# data_entries = []

# for line in lines:
#     if line.startswith('/'):
#         key, value = line[1:].split(':', 1)
#         setup_data[key.strip().lower()] = value.strip()
#     elif line and not line.startswith('//'):
#         values = line.split(',')
#         if len(values) == 6:
#             data_entries.append({
#                 'time': float(values[0]),
#                 'voltage': float(values[1]),
#                 'error_bar': float(values[2]),
#                 'quality': int(values[3]),
#                 'time_open': float(values[4]),
#                 'time_close': float(values[5])
#             })

# setup_entry = Setup(
#     date=setup_data.get('date'),
#     daytime=float(setup_data.get('daytime', 0)),
#     array=setup_data.get('array'),
#     loop_size=setup_data.get('loop_size'),
#     sounding_name=setup_data.get('sounding_name'),
#     sweeps=int(setup_data.get('sweeps', 0)),
#     location=setup_data.get('location'),
#     coil_location=setup_data.get('coil_location'),
#     z_direction=setup_data.get('z_direction'),
#     length_units=setup_data.get('length_units'),
#     voltage_units=setup_data.get('voltage_units'),
#     current=float(setup_data.get('current', 0)),
#     frequency=float(setup_data.get('frequency', 0)),
#     sweep_is_noise=bool(int(setup_data.get('sweep_is_noise', 0))),
#     field_shift_factor=float(setup_data.get('field_shift_factor', 0)),
#     time_delay=float(setup_data.get('time_delay', 0)),
#     ramp_time=float(setup_data.get('ramp_time', 0)),
#     tx_turnontime=int(setup_data.get('tx_turnontime', 0)),
#     ramp_time_on=int(setup_data.get('ramp_time_on', 0)),
#     tx_ramp=setup_data.get('tx_ramp'),
#     points=int(setup_data.get('points', 0)),
#     low_pass=setup_data.get('low_pass'),
#     channel=int(setup_data.get('channel', 0))
# )

# session.add(setup_entry)
# session.commit()

# for entry in data_entries:
#     data_entry = Data(
#         setup_id=setup_entry.id,
#         time=entry['time'],
#         voltage=entry['voltage'],
#         error_bar=entry['error_bar'],
#         quality=entry['quality'],
#         time_open=entry['time_open'],
#         time_close=entry['time_close']
#     )
#     session.add(data_entry)

# session.commit()

# Example numpy array
example_array = np.array([1.0, 2.0, 3.0, 4.0])

# Convert numpy array to a string
array_string = json.dumps(example_array.tolist())

# Insert the numpy array as a string into the database
class NumpyData(Base):
    __tablename__ = 'numpy_data'
    id = Column(Integer, primary_key=True)
    array = Column(String)

Base.metadata.create_all(engine)

numpy_entry = NumpyData(array=array_string)
session.add(numpy_entry)
session.commit()

# To retrieve and convert back to numpy array
retrieved_entry = session.query(NumpyData).first()
retrieved_array = np.array(json.loads(retrieved_entry.array))
print(retrieved_array)