from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert

from app.config import Settings
from app.models import Station

engine = create_engine(Settings().database_url)
with engine.begin() as connection:
    connection.execute(insert(Station).values(
        id="station-01", name="Trạm thử nghiệm (tọa độ minh họa)",
        latitude=10.7701, longitude=106.7001, warning_threshold_cm=10,
        danger_threshold_cm=20, exclusion_radius_m=40, is_active=True,
    ).on_conflict_do_nothing(index_elements=["id"]))
engine.dispose()
print("station-01 ready; replace demo coordinates before real use.")
