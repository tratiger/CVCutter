from pathlib import Path
from unittest.mock import MagicMock, patch

from cvcutter.data.external import MetadataService


def test_parse_local_csv(tmp_path):
    csv_path = tmp_path / "test.csv"
    csv_path.write_text("performer,title,public\nAlice,Song A,Yes\nBob,Song B,No\n", encoding='utf-8')

    service = MetadataService()
    data = service.parse_local_csv(csv_path)

    assert len(data) == 2
    assert data[0]["performer"] == "Alice"
    assert data[1]["title"] == "Song B"

@patch('cvcutter.data.external.genai.Client')
def test_parse_pdf_program(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.text = '```json\n[{"order": 1, "title": "Test", "performer": "Dev"}]\n```'
    mock_client.models.generate_content.return_value = mock_response

    service = MetadataService()
    result = service.parse_pdf_program(Path("dummy.pdf"), "dummy_key")

    assert len(result) == 1
    assert result[0]["title"] == "Test"

def test_map_performances():
    program = [{"title": "A"}, {"title": "B"}]
    segments = [(10.0, 20.0), (30.0, 40.0)]

    service = MetadataService()
    mapped = service.map_performances(program, segments, [])

    assert len(mapped) == 2
    assert mapped[0]["title"] == "A"
    assert mapped[0]["start_time"] == 10.0
    assert mapped[1]["end_time"] == 40.0
