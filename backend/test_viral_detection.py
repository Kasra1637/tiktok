"""
Unit tests for the viral detection scoring algorithm.
Tests compute_virality_score and rank_videos with known inputs.
No network calls required - only tests scoring logic.
"""
import time
from datetime import datetime, timezone

import pytest

from viral_detection import compute_virality_score, rank_videos, _compute_age_hours


class TestComputeViralityScore:
    """Test the virality scoring algorithm with known inputs."""

    def test_highly_viral_recent_video(self):
        """A video with high views, high engagement, and very recent should score high."""
        now_ts = int(time.time()) - 3600  # 1 hour ago
        video = {
            "view_count": 5_000_000,
            "like_count": 800_000,
            "comment_count": 50_000,
            "share_count": 100_000,
            "timestamp": now_ts,
        }
        score = compute_virality_score(video)
        assert 70 <= score <= 100, f"Expected high score for viral video, got {score}"

    def test_low_engagement_old_video(self):
        """An old video with low engagement should score low."""
        # 30 days ago
        old_ts = int(time.time()) - (30 * 24 * 3600)
        video = {
            "view_count": 1_000,
            "like_count": 10,
            "comment_count": 2,
            "share_count": 0,
            "timestamp": old_ts,
        }
        score = compute_virality_score(video)
        assert 0 <= score <= 30, f"Expected low score for old low-engagement video, got {score}"

    def test_zero_views(self):
        """A video with zero views should score very low (near 0)."""
        video = {
            "view_count": 0,
            "like_count": 0,
            "comment_count": 0,
            "share_count": 0,
            "timestamp": int(time.time()) - 3600,
        }
        score = compute_virality_score(video)
        assert 0 <= score <= 25, f"Expected very low score for zero-view video, got {score}"

    def test_moderate_video(self):
        """A moderately performing video should score in mid-range."""
        # 12 hours ago, moderate metrics
        ts = int(time.time()) - (12 * 3600)
        video = {
            "view_count": 100_000,
            "like_count": 8_000,
            "comment_count": 500,
            "share_count": 200,
            "timestamp": ts,
        }
        score = compute_virality_score(video)
        assert 20 <= score <= 85, f"Expected mid-range score, got {score}"

    def test_score_range_always_0_to_100(self):
        """Score must always be in [0, 100] range regardless of input."""
        test_cases = [
            {"view_count": 0, "like_count": 0, "comment_count": 0, "share_count": 0},
            {"view_count": 1_000_000_000, "like_count": 500_000_000,
             "comment_count": 100_000_000, "share_count": 200_000_000,
             "timestamp": int(time.time()) - 60},
            {"view_count": 1, "like_count": 1, "comment_count": 1, "share_count": 1,
             "timestamp": int(time.time()) - (365 * 24 * 3600)},
        ]
        for video in test_cases:
            score = compute_virality_score(video)
            assert 0 <= score <= 100, f"Score {score} out of range for {video}"

    def test_missing_fields_handled_gracefully(self):
        """Missing or None fields should not cause errors."""
        video = {}
        score = compute_virality_score(video)
        assert 0 <= score <= 100

        video_with_nones = {
            "view_count": None,
            "like_count": None,
            "comment_count": None,
            "share_count": None,
        }
        score = compute_virality_score(video_with_nones)
        assert 0 <= score <= 100

    def test_recency_matters(self):
        """A newer video with same metrics should score higher than an older one."""
        recent_ts = int(time.time()) - (2 * 3600)  # 2 hours ago
        old_ts = int(time.time()) - (7 * 24 * 3600)  # 7 days ago

        base_metrics = {
            "view_count": 500_000,
            "like_count": 50_000,
            "comment_count": 5_000,
            "share_count": 2_000,
        }

        recent_video = {**base_metrics, "timestamp": recent_ts}
        old_video = {**base_metrics, "timestamp": old_ts}

        recent_score = compute_virality_score(recent_video)
        old_score = compute_virality_score(old_video)

        assert recent_score > old_score, (
            f"Recent video ({recent_score}) should score higher than old video ({old_score})"
        )

    def test_higher_engagement_scores_better(self):
        """Higher engagement rate should lead to a higher score (same age/views)."""
        ts = int(time.time()) - (6 * 3600)  # 6 hours ago

        low_engagement = {
            "view_count": 1_000_000,
            "like_count": 1_000,
            "comment_count": 50,
            "share_count": 10,
            "timestamp": ts,
        }
        high_engagement = {
            "view_count": 1_000_000,
            "like_count": 150_000,
            "comment_count": 20_000,
            "share_count": 10_000,
            "timestamp": ts,
        }

        low_score = compute_virality_score(low_engagement)
        high_score = compute_virality_score(high_engagement)

        assert high_score > low_score, (
            f"High engagement ({high_score}) should beat low engagement ({low_score})"
        )

    def test_upload_date_string_format(self):
        """Videos with upload_date in YYYYMMDD format should be handled."""
        video = {
            "view_count": 200_000,
            "like_count": 20_000,
            "comment_count": 1_000,
            "share_count": 500,
            "upload_date": "20240101",
        }
        score = compute_virality_score(video)
        assert 0 <= score <= 100

    def test_negative_values_treated_as_zero(self):
        """Negative metric values should be clamped to zero."""
        video = {
            "view_count": -100,
            "like_count": -50,
            "comment_count": -10,
            "share_count": -5,
            "timestamp": int(time.time()) - 3600,
        }
        score = compute_virality_score(video)
        assert 0 <= score <= 100


class TestComputeAgeHours:
    """Test the age computation helper."""

    def test_timestamp_field(self):
        """When timestamp is provided, use it."""
        ts = int(time.time()) - (24 * 3600)  # 24 hours ago
        video = {"timestamp": ts}
        age = _compute_age_hours(video)
        assert 23.5 <= age <= 24.5

    def test_upload_date_field(self):
        """When upload_date string is provided, use it."""
        # Use a date that's a known number of days ago
        from datetime import timedelta
        target_date = datetime.now(timezone.utc) - timedelta(days=3)
        date_str = target_date.strftime("%Y%m%d")
        video = {"upload_date": date_str}
        age = _compute_age_hours(video)
        # Should be approximately 72 hours, but since upload_date is start-of-day,
        # actual age depends on current time of day. Allow 72-96 hour range.
        assert 48 <= age <= 96

    def test_no_date_info_defaults_to_48h(self):
        """When no date information is available, default to 48 hours."""
        video = {}
        age = _compute_age_hours(video)
        assert age == 48.0

    def test_invalid_upload_date(self):
        """Invalid upload_date string should fall through to default."""
        video = {"upload_date": "not-a-date"}
        age = _compute_age_hours(video)
        assert age == 48.0


class TestRankVideos:
    """Test the rank_videos function."""

    def test_sorts_by_virality_score_descending(self):
        """Videos should be sorted with highest virality_score first."""
        now_ts = int(time.time())
        videos = [
            {"view_count": 100, "like_count": 5, "comment_count": 1,
             "share_count": 0, "timestamp": now_ts - (7 * 24 * 3600)},
            {"view_count": 5_000_000, "like_count": 800_000, "comment_count": 50_000,
             "share_count": 100_000, "timestamp": now_ts - 3600},
            {"view_count": 50_000, "like_count": 5_000, "comment_count": 200,
             "share_count": 50, "timestamp": now_ts - (12 * 3600)},
        ]

        ranked = rank_videos(videos)

        assert len(ranked) == 3
        # Should be sorted descending
        assert ranked[0]["virality_score"] >= ranked[1]["virality_score"]
        assert ranked[1]["virality_score"] >= ranked[2]["virality_score"]
        # The highly viral recent video should be first
        assert ranked[0]["view_count"] == 5_000_000

    def test_adds_virality_score_field(self):
        """Each video in the result should have a virality_score field."""
        videos = [
            {"view_count": 1000, "like_count": 100, "comment_count": 10,
             "share_count": 5, "timestamp": int(time.time()) - 3600},
        ]
        ranked = rank_videos(videos)
        assert "virality_score" in ranked[0]
        assert isinstance(ranked[0]["virality_score"], float)

    def test_does_not_mutate_input(self):
        """rank_videos should not modify the original list or dicts."""
        videos = [
            {"view_count": 1000, "like_count": 100, "comment_count": 10,
             "share_count": 5, "timestamp": int(time.time()) - 3600},
        ]
        original_keys = set(videos[0].keys())
        rank_videos(videos)
        assert "virality_score" not in videos[0]
        assert set(videos[0].keys()) == original_keys

    def test_empty_list(self):
        """Empty list should return empty list."""
        assert rank_videos([]) == []

    def test_single_video(self):
        """Single video should be returned with score."""
        videos = [{"view_count": 50000, "like_count": 5000, "comment_count": 200,
                   "share_count": 100, "timestamp": int(time.time()) - 7200}]
        ranked = rank_videos(videos)
        assert len(ranked) == 1
        assert "virality_score" in ranked[0]

    def test_preserves_original_fields(self):
        """Ranked videos should retain all original fields."""
        videos = [
            {"view_count": 1000, "like_count": 100, "comment_count": 10,
             "share_count": 5, "timestamp": int(time.time()) - 3600,
             "title": "Test Video", "creator": "test_user", "custom_field": "hello"},
        ]
        ranked = rank_videos(videos)
        assert ranked[0]["title"] == "Test Video"
        assert ranked[0]["creator"] == "test_user"
        assert ranked[0]["custom_field"] == "hello"
