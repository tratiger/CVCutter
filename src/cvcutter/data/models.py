from enum import Enum as PyEnum
from pathlib import Path

from sqlalchemy import Boolean, Column, Enum, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from cvcutter.utils.logger import logger

Base = declarative_base()

class ProjectStatus(PyEnum):
    CREATED = "CREATED"
    AUDIO_SYNCED = "AUDIO_SYNCED"
    VIDEO_ANALYZED = "VIDEO_ANALYZED"
    MAPPED = "MAPPED"
    RENDERED = "RENDERED"
    UPLOADED = "UPLOADED"

class Project(Base):
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.CREATED)
    video_path = Column(String, nullable=True)
    audio_path = Column(String, nullable=True)
    pdf_path = Column(String, nullable=True)
    form_id = Column(String, nullable=True)
    output_dir = Column(String, nullable=True)

    performances = relationship("Performance", back_populates="project", cascade="all, delete-orphan")

class Performance(Base):
    __tablename__ = 'performances'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)

    title = Column(String, nullable=True)
    performer = Column(String, nullable=True)
    start_time = Column(Float, nullable=True)
    end_time = Column(Float, nullable=True)

    # Metadata for upload
    description = Column(String, nullable=True)
    is_public = Column(Boolean, default=False)

    # Upload status
    youtube_url = Column(String, nullable=True)
    is_uploaded = Column(Boolean, default=False)

    project = relationship("Project", back_populates="performances")

def get_engine(db_path: Path | str | None = None):
    if db_path is None:
        db_path = Path.home() / ".cvcutter" / "cvcutter.db"

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    logger.debug(f"Initialized database at {db_path}")
    return engine

def get_session_maker(engine):
    return sessionmaker(bind=engine)
