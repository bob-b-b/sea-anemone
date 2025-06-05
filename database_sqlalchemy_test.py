from sqlalchemy import Column, Integer, Float, Boolean, String
import json
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


Base = declarative_base()

class SweepModel(Base):
    __tablename__ = 'sweeps'
    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(String)
    time = Column(String)
    error = Column(String)
    quality = Column(String)
    tx_ramp = Column(String)
    tx_ramp_time = Column(String)
    current = Column(Float)
    frequency = Column(Float)
    is_noise = Column(Boolean)
    field_shift_factor = Column(Float)
    time_delay = Column(Float)
    ramp_time = Column(Float)
    tx_turnontime = Column(Float)
    ramp_time_on = Column(Float)
    number = Column(Integer)
    low_pass = Column(String)
    points = Column(Integer)

    @classmethod
    def from_sweep(cls, sweep):
        return cls(
            data=json.dumps(sweep.data.tolist()),
            time=json.dumps(sweep.time.tolist()),
            error=json.dumps(sweep.error.tolist()),
            quality=json.dumps(sweep.quality.tolist()),
            tx_ramp=json.dumps(sweep.tx_ramp.tolist()),
            tx_ramp_time=json.dumps(sweep.tx_ramp_time.tolist()),
            current=sweep.current,
            frequency=sweep.frequency,
            is_noise=sweep.is_noise,
            field_shift_factor=sweep.field_shift_factor,
            time_delay=sweep.time_delay,
            ramp_time=sweep.ramp_time,
            tx_turnontime=sweep.tx_turnontime,
            ramp_time_on=sweep.ramp_time_on,
            number=sweep.number,
            low_pass=json.dumps(sweep.low_pass.tolist()),
            points=sweep.points
        )

# Create an engine and a session
engine = create_engine('sqlite:///sweeps.db')
Session = sessionmaker(bind=engine)
session = Session()

# Create the table
Base.metadata.create_all(engine)

# Create two sweep instances
sweep1 = SweepModel(
    data=json.dumps([1.0, 2.0, 3.0]),
    time=json.dumps([0.1, 0.2, 0.3]),
    error=json.dumps([0.01, 0.02, 0.03]),
    quality=json.dumps([0.9, 0.8, 0.7]),
    tx_ramp=json.dumps([1.1, 1.2, 1.3]),
    tx_ramp_time=json.dumps([0.11, 0.12, 0.13]),
    current=0.5,
    frequency=50.0,
    is_noise=False,
    field_shift_factor=1.0,
    time_delay=0.05,
    ramp_time=0.1,
    tx_turnontime=0.01,
    ramp_time_on=0.02,
    number=1,
    low_pass=json.dumps([0.1, 0.2, 0.3]),
    points=100
)

sweep2 = SweepModel(
    data=json.dumps([4.0, 5.0, 6.0]),
    time=json.dumps([0.4, 0.5, 0.6]),
    error=json.dumps([0.04, 0.05, 0.06]),
    quality=json.dumps([0.6, 0.5, 0.4]),
    tx_ramp=json.dumps([1.4, 1.5, 1.6]),
    tx_ramp_time=json.dumps([0.14, 0.15, 0.16]),
    current=0.6,
    frequency=60.0,
    is_noise=True,
    field_shift_factor=1.1,
    time_delay=0.06,
    ramp_time=0.2,
    tx_turnontime=0.02,
    ramp_time_on=0.03,
    number=2,
    low_pass=json.dumps([0.4, 0.5, 0.6]),
    points=200
)

sweep3 = SweepModel(
    data=json.dumps([1.0, 2.0, 3.0]),
    time=json.dumps([0.1, 0.2, 0.3]),
    error=json.dumps([0.01, 0.02, 0.03]),
    quality=json.dumps([0.9, 0.8, 0.7]),
    tx_ramp=json.dumps([1.1, 1.2, 1.3]),
    tx_ramp_time=json.dumps([0.11, 0.12, 0.13]),
    current=0.5,
    frequency=50.0,
    is_noise=False,
    field_shift_factor=1.0,
    time_delay=0.05,
    ramp_time=0.1,
    tx_turnontime=0.01,
    ramp_time_on=0.02,
    number=1,
    low_pass=json.dumps([0.1, 0.2, 0.3]),
    points=100
)

# Add the instances to the session and commit
session.add(sweep1)
session.add(sweep2)
# Check if sweep3 is unique before adding it to the session
existing_sweep = session.query(SweepModel).filter_by(
    data=sweep3.data,
    time=sweep3.time,
    error=sweep3.error,
    quality=sweep3.quality,
    tx_ramp=sweep3.tx_ramp,
    tx_ramp_time=sweep3.tx_ramp_time,
    current=sweep3.current,
    frequency=sweep3.frequency,
    is_noise=sweep3.is_noise,
    field_shift_factor=sweep3.field_shift_factor,
    time_delay=sweep3.time_delay,
    ramp_time=sweep3.ramp_time,
    tx_turnontime=sweep3.tx_turnontime,
    ramp_time_on=sweep3.ramp_time_on,
    number=sweep3.number,
    low_pass=sweep3.low_pass,
    points=sweep3.points
).first()

if not existing_sweep:
    session.add(sweep3)
session.commit()

# Query the database
second_sweep = session.query(SweepModel).filter_by(id=2).first()
print(f"Time delay of the second sweep entry: {second_sweep.time_delay}")
# Query the number of entries in the database
entry_count = session.query(SweepModel).count()
print(f"Number of entries in the database: {entry_count}")

# second_sweep = session.query(SweepModel).filter_by(id=7).first()
# print(f"Time delay of the second sweep entry: {second_sweep.time_delay}")

# Remove all entries from the table
session.query(SweepModel).delete()
session.commit()

# Verify that the table is empty
entry_count = session.query(SweepModel).count()
print(f"Number of entries in the database after deletion: {entry_count}")