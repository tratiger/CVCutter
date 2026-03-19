from cvcutter.presentation.flet_app.views.segment_review_view import SegmentReviewView


def test_tuning_mode_actions_present() -> None:
    view = SegmentReviewView()
    assert "adjust" in view.decision_actions()
    assert view.tuning_mode == "simple"
    assert "noise_reduction_slider" in view.tuning_controls()
    view.switch_tuning_mode("waveform")
    assert view.tuning_mode == "waveform"
    assert "waveform_offset_drag" in view.tuning_controls()
    view.apply_decision("adjust")
    summary = view.summary()
    assert summary["review_status"] == "adjusted"
    assert summary["selected_action"] == "adjust"
