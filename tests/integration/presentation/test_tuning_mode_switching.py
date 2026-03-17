from cvcutter.presentation.flet_app.views.segment_review_view import SegmentReviewView


def test_tuning_mode_actions_present() -> None:
    assert "adjust" in SegmentReviewView().decision_actions()
