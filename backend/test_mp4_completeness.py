"""
The MP4 completeness check: finding the index, and proving there is video.

The bug these exist for
-----------------------
The check used to search the first and last 4KB of a file for the bytes "moov".
A provider render is not faststart, so its sample index is written LAST -- and
those four bytes are the START of that box. On a real 20-second 720x1280 clip the
index is ~7.7KB, so its tag sits further than 4KB from the end, outside the
window. Every finished render was therefore reported as
"download was truncated (not a complete MP4)", its durable copy was deleted, and
the founder was told there was nothing to play -- for a clip that played
perfectly in a browser.

Two independent questions are now asked, and both have to pass:

  structural - is the index actually there? Found by walking the box chain by
               declared size, so no fixed window can miss it.
  depth      - does anything decode? ffprobe counts video packets, which is the
               one thing a box walk cannot tell you.

The fixtures matter more than usual here. A hand-assembled byte string cannot
reproduce this bug, which is why it survived a test called "a large file with
moov at the end passes" whose moov was eight bytes long. The large-index cases
below assert that the fixture really does defeat the old window probe, so they
cannot quietly stop reproducing it.
"""

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import mp4_samples  # noqa: E402
import storage_service  # noqa: E402

pytestmark = pytest.mark.skipif(
    not mp4_samples.ffmpeg_available(),
    reason="ffmpeg is required: the completeness check probes decodable packets",
)


def write(tmp_path, data, name="clip.mp4"):
    p = tmp_path / name
    p.write_bytes(data)
    return p


def old_window_probe(data: bytes) -> bool:
    """The check as it was, so a fixture can be proven to defeat it."""
    return b"moov" in (data[:4096] + data[-4096:])


class TestFindingTheIndex:
    def test_a_real_render_with_a_distant_index_is_found(self, tmp_path):
        data = mp4_samples.real_mp4()
        tag_at = data.rfind(b"moov")
        assert len(data) - tag_at > 4096, "fixture drifted: index is no longer distant"
        assert old_window_probe(data) is False, "fixture drifted: old probe would pass"
        assert storage_service.mp4_has_moov(write(tmp_path, data)) is True

    def test_a_leading_index_is_still_found(self, tmp_path):
        """
        Faststart puts the index up front. It was never the problem, and a walk
        that only worked for the broken layout would be a fix that works for
        nobody.
        """
        leading = mp4_samples.box(b"moov", b"\x00" * 9000) + mp4_samples.box(
            b"ftyp", b"isom" + b"\x00" * 12
        )
        assert leading.index(b"moov") < 4096
        assert storage_service.mp4_has_moov(write(tmp_path, bytes(leading))) is True

    def test_a_synthetic_large_index_is_found(self, tmp_path):
        data = mp4_samples.synthetic_mp4(moov_body=9000, media_bytes=200_000)
        assert old_window_probe(data) is False
        assert storage_service.mp4_has_moov(write(tmp_path, data)) is True

    def test_a_64_bit_box_size_is_followed(self, tmp_path):
        """
        The 32-bit size field reads 1 and the real 64-bit length follows. A walk
        that treats 1 as a one-byte box stops immediately and misses an index a
        real writer legitimately placed after a large mdat.
        """
        ftyp = mp4_samples.box(b"ftyp", b"isom" + b"\x00" * 12)
        payload = b"\x00" * 5000
        mdat = (
            (1).to_bytes(4, "big")
            + b"mdat"
            + (16 + len(payload)).to_bytes(8, "big")
            + payload
        )
        moov = mp4_samples.box(b"moov", b"\x00" * 32)
        assert storage_service.mp4_has_moov(write(tmp_path, ftyp + mdat + moov)) is True

    def test_a_zero_size_index_is_still_found(self, tmp_path):
        """
        Size 0 means "this box extends to the end of the file", and an index
        written that way is the last thing in the file. The type is read before
        the size is expanded, so it is recognised rather than skipped.
        """
        ftyp = mp4_samples.box(b"ftyp", b"isom" + b"\x00" * 12)
        mdat = mp4_samples.box(b"mdat", b"\x00" * 500)
        data = ftyp + mdat + (0).to_bytes(4, "big") + b"moov" + b"\x00" * 64
        assert storage_service.mp4_has_moov(write(tmp_path, data)) is True

    def test_a_box_claiming_to_run_to_the_end_swallows_what_follows(self, tmp_path):
        """
        The other half of the same rule, and the reason the walk cannot be
        naive. A size-0 box extends to EOF, so anything written after it lies
        INSIDE its span rather than beside it -- and a moov in there is not a
        top-level index. Reading it as one would let a truncated file pass.
        """
        ftyp = mp4_samples.box(b"ftyp", b"isom" + b"\x00" * 12)
        moov = mp4_samples.box(b"moov", b"\x00" * 32)
        data = ftyp + (0).to_bytes(4, "big") + b"mdat" + moov
        assert storage_service.mp4_has_moov(write(tmp_path, data)) is False

    def test_a_malformed_size_stops_the_walk_without_hanging(self, tmp_path):
        """
        A box smaller than its own header would move the offset backwards or
        nowhere. The walk must give up rather than spin.

        The layout is chosen so the guard is the only thing making this pass.
        With the guard removed the offset would advance by 4, the next 8 bytes
        read would be b"junkmoov", and the type field would come out as "moov" --
        so a walk that trusted the size would report a truncated file as
        complete. A test that only checked "no hang" would not have noticed.
        """
        ftyp = mp4_samples.box(b"ftyp", b"isom" + b"\x00" * 12)
        broken = (4).to_bytes(4, "big") + b"junk"
        # No box header here: the bare word, which is what the misaligned re-read
        # above would mistake for a type.
        data = ftyp + broken + b"moov" + b"\x00" * 64
        assert storage_service.mp4_has_moov(write(tmp_path, data)) is False

    def test_a_64_bit_size_smaller_than_its_own_header_is_rejected(self, tmp_path):
        """
        The 64-bit length is a real length, but it cannot describe a box that
        does not have room for the 16 bytes the 64-bit form itself occupies.
        """
        ftyp = mp4_samples.box(b"ftyp", b"isom" + b"\x00" * 12)
        bad = (1).to_bytes(4, "big") + b"mdat" + (8).to_bytes(8, "big")
        data = ftyp + bad + mp4_samples.box(b"moov", b"\x00" * 32)
        assert storage_service.mp4_has_moov(write(tmp_path, data)) is False

    def test_a_truncated_64_bit_header_is_rejected(self, tmp_path):
        """Declared 64-bit size, but the file ends before the length field."""
        ftyp = mp4_samples.box(b"ftyp", b"isom" + b"\x00" * 12)
        data = ftyp + (1).to_bytes(4, "big") + b"mdat" + b"\x00" * 3
        assert storage_service.mp4_has_moov(write(tmp_path, data)) is False

    def test_an_index_nested_inside_another_box_does_not_count(self, tmp_path):
        """
        Top-level only. A stray "moov" in some other box's payload must not pass
        a truncated file on a coincidence.
        """
        inner = mp4_samples.box(b"moov", b"\x00" * 32)
        ftyp = mp4_samples.box(b"ftyp", b"isom" + b"\x00" * 12)
        udta = mp4_samples.box(b"udta", b"junk" + inner)
        assert storage_service.mp4_has_moov(write(tmp_path, ftyp + udta)) is False

    @pytest.mark.parametrize("data", [b"", b"\x00", b"ftyp", b"\x00" * 7])
    def test_something_too_short_to_be_a_file_is_rejected(self, tmp_path, data):
        assert storage_service.mp4_has_moov(write(tmp_path, data)) is False

    def test_a_missing_file_is_rejected(self, tmp_path):
        assert storage_service.mp4_has_moov(tmp_path / "nope.mp4") is False


class TestProvingThereIsVideo:
    def test_a_real_render_passes_both_checks(self, tmp_path):
        assert storage_service.is_usable_video(write(tmp_path, mp4_samples.real_mp4()))

    def test_a_real_render_cut_short_is_rejected(self, tmp_path):
        cut = mp4_samples.truncate(mp4_samples.real_mp4(), 0.4)
        assert not storage_service.is_usable_video(write(tmp_path, cut))

    def test_a_valid_container_holding_no_video_is_rejected(self, tmp_path):
        """
        What the box walk alone cannot catch, and the reason ffprobe is asked at
        all: structurally perfect, plays nothing.
        """
        hollow = mp4_samples.synthetic_mp4(moov_body=9000, media_bytes=200_000)
        path = write(tmp_path, hollow)
        assert storage_service.mp4_has_moov(path) is True
        assert storage_service.is_usable_video(path) is False

    def test_an_html_error_page_is_not_a_video(self, tmp_path):
        page = write(tmp_path, b"<html>404</html>" * 60, name="page.mp4")
        assert not storage_service.is_usable_video(page)


class TestWhenFfprobeCannotAnswer:
    """
    An absent ffprobe must not start discarding finished renders.

    The two containers resolve an unknown differently, and the asymmetry is the
    point rather than an inconsistency:

      MP4  - a real structural check stands behind the probe, so an unknown
             probe costs depth and keeps the file.
      WebM - no equivalent structural gate exists (MediaRecorder output can
             carry no duration header at all), so the probe is the only evidence
             and an unknown has to fail closed.
    """

    def _no_ffprobe(self, monkeypatch):
        def boom(*args, **kwargs):
            raise FileNotFoundError("ffprobe")

        monkeypatch.setattr(storage_service.subprocess, "run", boom)

    def test_mp4_survives_an_unavailable_probe(self, tmp_path, monkeypatch):
        path = write(tmp_path, mp4_samples.real_mp4())
        self._no_ffprobe(monkeypatch)
        assert storage_service.is_usable_video(path) is True

    def test_mp4_still_fails_closed_on_a_structural_problem(self, tmp_path, monkeypatch):
        """An unknown probe must not quietly become "accept anything"."""
        self._no_ffprobe(monkeypatch)
        # ftyp only: no index at all, so the structural gate rejects it even
        # though the probe could not be run.
        hollow = write(
            tmp_path, mp4_samples.box(b"ftyp", b"isom" + b"\x00" * 12), name="noindex.mp4"
        )
        assert storage_service.is_usable_video(hollow) is False

    def test_webm_fails_closed_when_the_probe_cannot_answer(self, tmp_path, monkeypatch):
        webm = b"\x1a\x45\xdf\xa3" + b"\x00" * 512
        path = write(tmp_path, webm, name="clip.webm")
        assert storage_service.video_content_type(path) == "video/webm"
        self._no_ffprobe(monkeypatch)
        assert storage_service.is_usable_video(path) is False

    def test_a_probe_reporting_zero_packets_is_a_no_not_an_unknown(self, tmp_path, monkeypatch):
        """ffprobe present and reporting zero packets is a real answer."""

        class Result:
            returncode = 0
            stdout = '{"streams": [{"nb_read_packets": "0"}]}'

        monkeypatch.setattr(storage_service.subprocess, "run", lambda *a, **k: Result())
        assert storage_service.is_usable_video(
            write(tmp_path, mp4_samples.real_mp4())
        ) is False

    def test_malformed_probe_output_is_an_unknown(self, tmp_path, monkeypatch):
        class Result:
            returncode = 0
            stdout = "not json at all"

        monkeypatch.setattr(storage_service.subprocess, "run", lambda *a, **k: Result())
        # MP4: an unknown keeps a structurally sound file.
        assert storage_service.is_usable_video(
            write(tmp_path, mp4_samples.real_mp4())
        ) is True
        # WebM: an unknown discards it.
        webm = write(tmp_path, b"\x1a\x45\xdf\xa3" + b"\x00" * 512, name="c.webm")
        assert storage_service.is_usable_video(webm) is False


class TestServerDelegates:
    def test_the_server_helper_is_the_same_check(self, tmp_path, monkeypatch):
        """
        One source of truth. Two copies of this logic is how they drifted apart
        in the first place, so the server helper must not grow its own again.
        """
        import server

        calls = []
        real = storage_service.is_usable_video

        def spy(path):
            calls.append(Path(path))
            return real(path)

        monkeypatch.setattr(storage_service, "is_usable_video", spy)
        good = write(tmp_path, mp4_samples.real_mp4(), name="good.mp4")
        bad = write(
            tmp_path,
            mp4_samples.truncate(mp4_samples.real_mp4(), 0.3),
            name="bad.mp4",
        )
        assert server._is_complete_mp4(good) is True
        assert server._is_complete_mp4(bad) is False
        assert len(calls) == 2, "the server helper stopped delegating to storage_service"

    def test_the_server_helper_still_rejects_the_usual_junk(self, tmp_path):
        import server

        assert server._is_complete_mp4(tmp_path / "missing.mp4") is False
        assert server._is_complete_mp4(write(tmp_path, b"")) is False
        assert server._is_complete_mp4(write(tmp_path, b"<html>404</html>" * 60)) is False


def test_the_probe_is_really_ffprobe_counting_packets(tmp_path, monkeypatch):
    """Guards against the probe quietly becoming a no-op that always says yes."""
    seen = {}

    def spy(args, **kwargs):
        seen["args"] = args
        raise AssertionError("stop here")

    monkeypatch.setattr(storage_service.subprocess, "run", spy)
    with pytest.raises(AssertionError):
        storage_service.is_usable_video(write(tmp_path, mp4_samples.real_mp4()))
    assert seen["args"][0] == "ffprobe"
    assert "-count_packets" in seen["args"]
