import queue
import threading
import time
import unittest
from dataclasses import replace

from horulince.sources import LatestStream, is_network, validate_phone_url


class FakeCapture:
    def __init__(self, opened=True):
        self.frames = queue.Queue()
        self.opened = opened
        self.released = False
        self.owner = None

    def isOpened(self):
        return self.opened

    def get(self, prop):
        return 30

    def read(self):
        self.owner = threading.get_ident()
        try:
            frame = self.frames.get(timeout=.1)
            return (frame is not None), frame
        except queue.Empty:
            return False, None

    def release(self):
        if self.owner is not None:
            assert self.owner == threading.get_ident(), "Somente a thread de captura pode liberar o backend"
        self.released = True


def wait_for(stream, predicate):
    deadline = time.monotonic() + 2
    with stream.condition:
        while not predicate():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError("A thread não produziu o estado esperado")
            stream.condition.wait(remaining)


class SourceTests(unittest.TestCase):
    def test_phone_urls_and_local_files(self):
        self.assertEqual(validate_phone_url(" rtsp://192.168.1.8:8554/live "), "rtsp://192.168.1.8:8554/live")
        self.assertTrue(is_network("http://127.0.0.1:8080/video"))
        self.assertFalse(is_network(r"C:\videos\teste.mp4"))
        for value in ("", "192.168.1.8", "file:///etc/passwd", "rtsp://", "rtsp://host:bad/live"):
            with self.assertRaises(ValueError):
                validate_phone_url(value)

    def test_slow_consumer_receives_latest_frame_only(self):
        capture = FakeCapture()
        stream = LatestStream("rtsp://test/live", factory=lambda _: capture, retries=0, read_timeout=.03)
        try:
            for n in range(3):
                capture.frames.put({"number": n})
            wait_for(stream, lambda: stream.sequence == 3)
            ok, image = stream.read()
            self.assertTrue(ok)
            self.assertEqual(image["number"], 2)
            self.assertEqual(stream.read(), (False, None))
        finally:
            stream.release()
        self.assertTrue(capture.released)
        self.assertFalse(stream.thread.is_alive())

    def test_reconnect_discards_previous_session_frame(self):
        first, second = FakeCapture(), FakeCapture()
        factories = iter([first, second])
        stream = LatestStream("rtsp://test/live", factory=lambda _: next(factories), retries=1, retry_delay=.001, read_timeout=.5)
        try:
            first.frames.put({"number": 1})
            self.assertTrue(stream.isOpened())
            self.assertEqual(stream.read()[1]["number"], 1)
            first.frames.put(None)
            second.frames.put({"number": 2})
            ok, image = stream.read()
            self.assertTrue(ok)
            self.assertEqual(image["number"], 2)
            self.assertGreater(stream.delivered_generation, 0)
            self.assertEqual(stream.reconnections, 1)
        finally:
            stream.release()
        self.assertTrue(first.released)
        self.assertTrue(second.released)

    def test_unavailable_camera_has_bounded_retries(self):
        opened = []
        def factory(_):
            capture = FakeCapture(opened=False)
            opened.append(capture)
            return capture
        stream = LatestStream("rtsp://test/live", factory=factory, retries=1, retry_delay=.001, read_timeout=.5)
        try:
            self.assertFalse(stream.isOpened())
            self.assertEqual(len(opened), 2)
            self.assertEqual(stream.read(), (False, None))
            self.assertIsNotNone(stream.failure)
        finally:
            stream.release()
        self.assertTrue(all(c.released for c in opened))

    def test_stale_frames_are_never_delivered(self):
        capture = FakeCapture()
        stream = LatestStream("rtsp://test/live", factory=lambda _: capture, read_timeout=.01, max_age=1, retries=0)
        try:
            capture.frames.put({"number": 1})
            wait_for(stream, lambda: stream.sequence == 1)
            with stream.condition:
                stream.packet = replace(stream.packet, captured=time.monotonic() - 10)
            self.assertEqual(stream.read(), (False, None))
        finally:
            stream.release()
