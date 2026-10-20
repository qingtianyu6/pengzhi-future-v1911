from datetime import datetime, UTC
from sqlalchemy import DateTime, JSON, String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class GreenhouseSimulationScenario(Base):
    __tablename__='greenhouse_simulation_scenarios'
    id: Mapped[int]=mapped_column(primary_key=True)
    session_key: Mapped[str]=mapped_column(String(100),index=True)
    name: Mapped[str]=mapped_column(String(60))
    environment: Mapped[dict]=mapped_column(JSON)

class GreenhouseSimulationEvent(Base):
    __tablename__='greenhouse_simulation_events'
    id: Mapped[int]=mapped_column(primary_key=True)
    session_key: Mapped[str]=mapped_column(String(100),index=True)
    owner_user_id: Mapped[int | None]=mapped_column(Integer,nullable=True,index=True)
    source: Mapped[str]=mapped_column(String(20),default='simulation')
    event: Mapped[str]=mapped_column(String(40))
    payload: Mapped[dict]=mapped_column(JSON)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(UTC))
