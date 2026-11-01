"""Winner-steers-generation: proven pairs reproduce first, moments stay distinct."""

from feedback import build_angle_feedback_section, summarize_angle_feedback


def test_winner_pairs_get_reproduce_instruction():
    summary = summarize_angle_feedback(
        [{"kind": "problem_solution", "objective": "address_user_problem",
          "event": "thumb_up", "step": "goal", "created_at": "2026-10-30T00:00:00Z"}],
        posted_rows=[{"kind": "problem_solution", "objective": "address_user_problem",
                       "views": 12400, "at": "2026-10-30T00:00:00Z"}],
    )
    section = build_angle_feedback_section(summary)
    assert "PROVEN WINNERS" in section
    assert "reproduce their argument first" in section


def test_no_winners_no_reproduce_line():
    section = build_angle_feedback_section(summarize_angle_feedback([], posted_rows=[]))
    assert "PROVEN WINNERS" not in section
