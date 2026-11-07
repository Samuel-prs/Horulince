from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from horulince.dashboard import Dashboard, Jobs
from horulince.demonstration import DemoArchive, run_demo
from horulince.storage import AlertStore


class FakeVideo:
    def __init__(self, frames=2, opened=True):
        self.frames = frames
        self.opened = opened
        self.released = False

    def isOpened(self):
        return self.opened

    def get(self, _):
        return 900

    def read(self):
        if not self.frames:
            return False, None
        self.frames -= 1
        return True, np.zeros((240, 320, 3), dtype=np.uint8)

    def release(self):
        self.released = True


class Faces:
    def __init__(self, count):
        self.count = count

    def detectMultiScale(self, *_args, **_kwargs):
        return [(10, 10, 110, 110)] * self.count


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = AlertStore(Path(self.temp.name) / "test.sqlite3")
        self.archive = DemoArchive(self.store)

    def run_face(self, count=1, opened=True):
        job, video = Jobs(), FakeVideo(opened=opened)
        job.capture_requested.set()
        result = run_demo(self.archive, job, mode="facial", source="test.mp4", origin="teste_sintetico",
                          authorized=True, detector=Faces(count), capture_factory=lambda _: video)
        return result, job, video

    def test_requires_authorization_before_opening_source(self):
        with self.assertRaises(ValueError):
            run_demo(self.archive, Jobs(), mode="facial", source="0", origin="teste", authorized=False)
        app = Dashboard(self.store.path)
        with patch.object(app.jobs, "start") as start:
            for value in (False, "true", 1):
                with self.assertRaises(ValueError):
                    app.start_demo({"source_type": "webcam", "mode": "facial", "authorized": value})
            start.assert_not_called()

    def test_manual_capture_persists_only_with_exactly_one_face(self):
        summary, job, video = self.run_face()
        self.assertEqual(summary["imagens_salvas"], 1)
        self.assertTrue(video.released)
        self.assertFalse(job.capture_requested.is_set())
        result = self.archive.query({"kind": "captura_facial"})
        self.assertEqual(result["total"], 1)
        item = result["items"][0]
        self.assertTrue(item["has_image"])
        self.assertTrue(self.archive.image_path(item["id"]).is_file())
        self.assertEqual(item["payload"]["deteccoes"][0]["identidade"], "nao_analisada")
        self.assertEqual(self.archive.query({"kind": "deteccao_facial"})["total"], 2)

    def test_zero_and_multiple_faces_refuse_capture_but_keep_detection_events(self):
        for count in (0, 2):
            result, job, _ = self.run_face(count)
            self.assertEqual(result["imagens_salvas"], 0)
            self.assertIn("recusada", job.snapshot()["progress"]["captura_status"])
        self.assertEqual(self.archive.query({"images": "1"})["total"], 0)

    def test_failed_source_is_recorded_and_released(self):
        video = FakeVideo(opened=False)
        with self.assertRaises(RuntimeError):
            run_demo(self.archive, Jobs(), mode="facial", source="test.mp4", origin="teste",
                     authorized=True, detector=Faces(1), capture_factory=lambda _: video)
        self.assertTrue(video.released)
        self.assertEqual(self.archive.runs()[0]["state"], "erro")

    def test_stop_records_partial_run_and_does_not_read_new_frame(self):
        job, video = Jobs(), FakeVideo()
        job.stop_event.set()
        result = run_demo(self.archive, job, mode="facial", source="test.mp4", origin="teste",
                          authorized=True, detector=Faces(1), capture_factory=lambda _: video)
        self.assertEqual(result["estado_execucao"], "interrompida")
        self.assertEqual(result["quadros_lidos"], 0)
        self.assertTrue(video.released)

    def test_archive_unifies_alerts_audit_and_demo_with_parameterized_filters(self):
        self.run_face()
        def evidence(path):
            Path(path).write_bytes(b"synthetic evidence")
            return True
        self.store.create(run="pipeline", track=1, target="ficticio", source="video_teste", video_seconds=1,
                          payload={"placa": "ABC1D23"}, write_evidence=evidence)
        self.assertEqual(self.archive.query({"run": "pipeline"})["total"], 2)
        self.assertEqual(self.archive.query({"q": "ABC1D23"})["total"], 1)
        self.assertEqual(self.archive.query({"plate": "abc-1d23"})["total"], 1)
        self.assertEqual(self.archive.query({"plate": "XYZ1234"})["total"], 0)
        self.store.review(self.store.list()[0]["id"], "descartado", "Ana", "Cita XYZ1234 sem observar essa placa")
        self.assertEqual(self.archive.query({"plate": "XYZ1234"})["total"], 0)
        with self.assertRaises(ValueError):
            self.archive.query({"plate": "ABC!1D23"})
        self.assertEqual(self.archive.query({"source": "' OR 1=1 --"})["total"], 0)
        first = self.archive.query({"limit": "1"})
        second = self.archive.query({"limit": "1", "offset": "1"})
        self.assertNotEqual(first["items"][0]["id"], second["items"][0]["id"])
        self.assertEqual(len(self.archive.query({"limit": 1}, export=True)["items"]), first["total"])
        self.assertIsNone(self.archive.image_path("demo:../../secrets"))
        self.assertEqual(self.archive.query({"since": "2000-01-01", "until": "2000-01-02"})["total"], 0)
        for invalid in ({"since": "bad"}, {"limit": "0"}, {"offset": "-1"}):
            with self.assertRaises(ValueError):
                self.archive.query(invalid)

    def test_missing_capture_and_invalid_demo_cannot_start(self):
        app = Dashboard(self.store.path)
        with self.assertRaises(ValueError):
            app.request_face_capture()
        with self.assertRaises(ValueError):
            app.start_demo({"source_type": "webcam", "mode": "reconhecimento"})
        with self.assertRaises(ValueError):
            app.start_demo({"source_type": "webcam", "mode": "facial", "authorized": True, "max_frames": 0})

    def test_failed_image_leaves_no_event(self):
        run = self.archive.begin("facial", "teste", {})
        with patch("cv2.imwrite", return_value=False):
            with self.assertRaises(OSError):
                self.archive.event(run, "captura_facial", "teste", 0, {}, np.zeros((10,10,3),dtype=np.uint8))
        self.assertEqual(self.archive.query({})["total"], 0)


if __name__ == "__main__":
    unittest.main()
