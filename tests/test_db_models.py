
import pytest

from cvcutter.data.models import Performance, Project, ProjectStatus, get_engine, get_session_maker


@pytest.fixture
def db_session(tmp_path):
    db_file = tmp_path / "test.db"
    engine = get_engine(db_file)
    Session = get_session_maker(engine)
    session = Session()
    yield session
    session.close()

def test_create_project(db_session):
    project = Project(name="Test Concert", video_path="/tmp/vid.mp4")
    db_session.add(project)
    db_session.commit()

    saved = db_session.query(Project).filter_by(name="Test Concert").first()
    assert saved is not None
    assert saved.status == ProjectStatus.CREATED
    assert saved.video_path == "/tmp/vid.mp4"

def test_project_performance_relationship(db_session):
    project = Project(name="Test Concert 2")
    perf1 = Performance(title="Song A", performer="Alice")
    perf2 = Performance(title="Song B", performer="Bob")
    project.performances.extend([perf1, perf2])

    db_session.add(project)
    db_session.commit()

    saved_project = db_session.query(Project).filter_by(name="Test Concert 2").first()
    assert len(saved_project.performances) == 2
    assert saved_project.performances[0].title == "Song A"

    # Test cascade delete
    db_session.delete(saved_project)
    db_session.commit()

    assert db_session.query(Performance).count() == 0
