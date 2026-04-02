from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cvcutter.core.orchestrator import PipelineOrchestrator
from cvcutter.data.external import MetadataService
from cvcutter.data.models import Project, ProjectStatus, get_engine, get_session_maker


@pytest.fixture
def db_session(tmp_path):
    db_file = tmp_path / "test.db"
    engine = get_engine(db_file)
    Session = get_session_maker(engine)
    session = Session()
    yield session
    session.close()

def test_pipeline_generate_mapping(db_session, tmp_path):
    # Setup
    proj = Project(name="TestProj", output_dir=str(tmp_path), status=ProjectStatus.VIDEO_ANALYZED, pdf_path="fake.pdf")
    db_session.add(proj)
    db_session.commit()

    meta_service = MetadataService()
    meta_service.parse_pdf_program = MagicMock(return_value=[{"title": "Song1", "performer": "P1"}])

    orchestrator = PipelineOrchestrator(db_session, meta_service)

    # Execute Step 3
    orchestrator.generate_mapping(proj, [(10.0, 20.0)], "fake_key")

    # Verify
    # Because of object caching in sqlalchemy, we query it back
    db_session.refresh(proj)
    assert proj.status == ProjectStatus.MAPPED
    assert len(proj.performances) == 1
    assert proj.performances[0].title == "Song1"
    assert proj.performances[0].start_time == 10.0

@patch('cvcutter.core.orchestrator.build')
@patch('cvcutter.core.orchestrator.MediaFileUpload')
def test_pipeline_upload(mock_upload, mock_build, db_session, tmp_path):
    proj = Project(name="UploadProj", output_dir=str(tmp_path), status=ProjectStatus.RENDERED)
    db_session.add(proj)
    db_session.commit()

    meta_service = MetadataService()
    meta_service.creds = MagicMock()

    orchestrator = PipelineOrchestrator(db_session, meta_service)

    with patch.object(Path, 'exists', return_value=True):
        from cvcutter.data.models import Performance
        perf = Performance(title="A", performer="B", project_id=proj.id)
        db_session.add(perf)
        db_session.commit()

        mock_execute = MagicMock(return_value={"id": "dQw4w9WgXcQ"})
        mock_insert = MagicMock()
        mock_insert.execute = mock_execute
        mock_videos = MagicMock()
        mock_videos.insert = MagicMock(return_value=mock_insert)
        mock_youtube = MagicMock()
        mock_youtube.videos = MagicMock(return_value=mock_videos)
        mock_build.return_value = mock_youtube

        db_session.refresh(proj)
        orchestrator.upload_pending(proj)

        db_session.refresh(proj)
        assert proj.status == ProjectStatus.UPLOADED
        assert proj.performances[0].is_uploaded
        assert proj.performances[0].youtube_url == "https://youtu.be/dQw4w9WgXcQ"
