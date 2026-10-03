"""
Tests for internal analytics.

analytics is pure arithmetic, so it is tested directly. The numbers that
matter are the honest ones: cost must not silently average down when a
provider reported none, and a rate must not count in-flight work as failure.
"""
import analytics as an
import pytest


def gen(status="completed", cost=0.25, **overrides):
    row = {
        "id": overrides.pop("id", "g1"),
        "status": status,
        "cost_usd": cost,
        "model": overrides.pop("model", "minimax-h3"),
        "brand_profile_id": overrides.pop("brand_profile_id", "p1"),
        "template_id": overrides.pop("template_id", "t1"),
        "duration": overrides.pop("duration", 20),
        "attempt": overrides.pop("attempt", 1),
        "parent_generation_id": overrides.pop("parent_generation_id", None),
        "studio_project_id": overrides.pop("studio_project_id", "proj1"),
        "cost_source": "usage.cost",
    }
    row.update(overrides)
    return row


class TestGenerationMetrics:
    def test_empty_input(self):
        m = an.generation_metrics([])
        assert m["videos_created"] == 0
        assert m["success_rate"] is None
        assert m["total_usd"] == 0

    def test_counts_by_status(self):
        m = an.generation_metrics([
            gen("completed", id="a"), gen("completed", id="b"),
            gen("failed", id="c"), gen("generating", id="d"),
        ])
        assert m["videos_created"] == 4
        assert m["completed"] == 2
        assert m["failed"] == 1
        assert m["in_flight"] == 1

    def test_success_rate_ignores_in_flight(self):
        """
        A queued generation is not a failure. Counting it would make a healthy
        pipeline look broken. Rates are rounded for display, hence the tolerance.
        """
        m = an.generation_metrics([
            gen("completed", id="a"), gen("completed", id="b"),
            gen("failed", id="c"), gen("generating", id="d"),
        ])
        assert m["success_rate"] == pytest.approx(2 / 3, abs=1e-3)
        assert m["failure_rate"] == pytest.approx(1 / 3, abs=1e-3)

    def test_rate_is_none_when_nothing_finished(self):
        m = an.generation_metrics([gen("generating", id="a"), gen("submitted", id="b")])
        assert m["success_rate"] is None

    def test_unpriced_runs_do_not_lower_the_total(self):
        """
        The honesty test. A run with no reported cost must be counted as
        unpriced, never treated as 0.0, or the average spend silently drops.
        """
        m = an.generation_metrics([
            gen(cost=1.00, id="a"), gen(cost=None, id="b"),
        ])
        assert m["total_usd"] == pytest.approx(1.00)
        assert m["priced_runs"] == 1
        assert m["unpriced_runs"] == 1
        assert m["complete"] is False

    def test_all_priced_reports_complete(self):
        m = an.generation_metrics([gen(cost=0.5, id="a"), gen(cost=0.25, id="b")])
        assert m["complete"] is True
        assert m["total_usd"] == pytest.approx(0.75)

    def test_average_duration_uses_parsed_timestamps(self):
        m = an.generation_metrics([
            gen(id="a", started_at="2026-01-01T00:00:00+00:00", completed_at="2026-01-01T00:00:30+00:00"),
            gen(id="b", started_at="2026-01-01T00:00:00+00:00", completed_at="2026-01-01T00:00:10+00:00"),
        ])
        assert m["avg_generation_seconds"] == pytest.approx(20.0)

    def test_unparseable_timestamps_are_skipped(self):
        m = an.generation_metrics([gen(id="a", started_at="nonsense", completed_at="also bad")])
        assert m["avg_generation_seconds"] is None

    def test_naive_timestamps_are_treated_as_utc(self):
        m = an.generation_metrics([
            gen(id="a", started_at="2026-01-01T00:00:00", completed_at="2026-01-01T00:00:05")
        ])
        assert m["avg_generation_seconds"] == pytest.approx(5.0)

    def test_backwards_timestamps_are_ignored(self):
        m = an.generation_metrics([
            gen(id="a", started_at="2026-01-01T00:01:00+00:00", completed_at="2026-01-01T00:00:00+00:00")
        ])
        assert m["avg_generation_seconds"] is None


class TestDimensions:
    def test_grouping_counts_and_orders_by_volume(self):
        rows = [
            gen(model="minimax-h3", id="a"), gen(model="minimax-h3", id="b"),
            gen(model="aleph-2", id="c"),
        ]
        out = an.by_dimension(rows, "model")
        assert [e["key"] for e in out] == ["minimax-h3", "aleph-2"]
        assert out[0]["count"] == 2

    def test_missing_values_group_as_none(self):
        out = an.by_dimension([gen(model=None, id="a")], "model")
        assert out[0]["key"] == "(none)"

    def test_each_bucket_carries_its_own_totals(self):
        rows = [gen(cost=1.0, id="a"), gen(cost=0.0, id="b"), gen(cost=2.0, id="c")]
        out = an.by_dimension(rows, "model")
        by_key = {e["key"]: e for e in out}
        assert by_key["minimax-h3"]["total_usd"] == pytest.approx(3.0)


class TestRework:
    def test_counts_retries_and_variations(self):
        rows = [
            gen(id="a", attempt=1),
            gen(id="b", attempt=2, parent_generation_id="a"),
            gen(id="c", attempt=2, parent_generation_id="a"),
        ]
        m = an.regeneration_metrics(rows)
        assert m["variations"] == 2
        assert m["parents_with_variations"] == 1
        assert m["max_variations_of_one_video"] == 2

    def test_no_rework(self):
        m = an.regeneration_metrics([gen(id="a", attempt=1)])
        assert m["variations"] == 0
        assert m["max_variations_of_one_video"] == 0


class TestPerformanceSummary:
    def test_always_reports_manual_and_unverified(self):
        s = an.manual_performance_summary([{"views": 100, "likes": 5}])
        assert s["source"] == "manual"
        assert s["verified"] is False

    def test_sums_and_averages(self):
        s = an.manual_performance_summary([
            {"views": 100, "likes": 5, "outcome": "successful"},
            {"views": 300, "likes": 7, "outcome": "unsuccessful"},
        ])
        assert s["views"] == 400
        assert s["likes"] == 12
        assert s["avg_views"] == pytest.approx(200.0)
        assert s["marked_successful"] == 1
        assert s["marked_unsuccessful"] == 1

    def test_empty(self):
        s = an.manual_performance_summary([])
        assert s["entries"] == 0
        assert s["avg_views"] is None


class TestTemplateUsage:
    def test_annotates_names_and_ranks_by_volume(self):
        templates = [
            {"id": "t1", "name": "Fast Tutorial", "category": "tutorial", "origin": "curated"},
            {"id": "t2", "name": "POV", "category": "pov", "origin": "curated"},
        ]
        rows = [
            gen(template_id="t1", id="a"), gen(template_id="t1", id="b"),
            gen(template_id="t2", id="c"),
        ]
        out = an.template_usage(templates, rows)
        assert out[0]["name"] == "Fast Tutorial"
        assert out[0]["used"] == 2

    def test_deleted_template_is_labelled_not_hidden(self):
        rows = [gen(template_id="gone", id="a")]
        out = an.template_usage([], rows)
        assert out[0]["name"] == "(deleted template)"


class TestBuildReport:
    def test_joins_objective_and_audience_from_the_project(self):
        report = an.build_report(
            generations=[gen(studio_project_id="proj1")],
            profiles=[{"id": "p1", "brand_name": "Taskly"}],
            project_lookup={"proj1": {
                "id": "proj1", "objective": "demonstrate_feature",
                "audience": "Students", "content_angle_id": "angle1",
            }},
        )
        assert report["by_objective"][0]["key"] == "demonstrate_feature"
        assert report["by_audience"][0]["key"] == "Students"
        assert report["by_angle"][0]["key"] == "angle1"
        assert report["by_app"][0]["label"] == "Taskly"

    def test_feedback_summary_counts_fixed_reasons(self):
        report = an.build_report(
            generations=[],
            feedback=[
                {"event": "video_regenerated", "reason": "pacing_too_slow"},
                {"event": "video_regenerated", "reason": "pacing_too_slow"},
                {"event": "template_rejected", "reason": "hook_too_weak"},
            ],
        )
        assert report["feedback"]["total"] == 3
        assert report["feedback"]["by_event"]["video_regenerated"] == 2
        assert report["feedback"]["top_reasons"][0]["reason"] == "pacing_too_slow"


class TestModelRequestSummary:
    def test_counts_modalities_models_and_cost_honestly(self):
        summary = an.model_request_summary([
            {"modality": "text", "model": "text-model", "status": "completed", "cost_usd": 0.02},
            {"modality": "vision", "model": "vision-model", "status": "completed", "cost_usd": None},
            {"modality": "video", "model": "video-model", "status": "failed", "cost_usd": 0.10},
        ])
        assert summary["total"] == 3
        assert summary["completed"] == 2
        assert summary["failed"] == 1
        assert summary["total_usd"] == pytest.approx(0.12)
        assert summary["priced_runs"] == 2
        assert summary["unpriced_runs"] == 1
        assert summary["by_modality"]["text"]["completed"] == 1
        assert summary["by_model"]["video-model"]["failed"] == 1
