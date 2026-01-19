import sys
sys.path.insert(0, 'C:/Users/au646858/OneDrive - Aarhus Universitet/Documents/_repositories/sea-anemone/app')

from panels import *
from typing import List

@nosj
class SessionSettings:
    map: MapSettings
    sounding: dbdtSoundingSettings
    table: TableSettings
    linked_settings: List[str] = None

        

if __name__ == "__main__":
    
    map_settings = MapSettings(id='map')
    sounding_settings = dbdtSoundingSettings(id='sounding')
    table_settings = TableSettings(id='table')

    settings = SessionSettings(
        map=map_settings,
        sounding=sounding_settings,
        table=table_settings
    )

    import time
    bt = time.time()
    settings.save('default_session.json')
    et = time.time()
    print(f"Saved session in {et - bt} seconds")
    print(settings)

    settings2 = SessionSettings.load('default_session.json')
    print(settings2)
    