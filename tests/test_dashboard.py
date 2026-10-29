import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from horulince.dashboard import Dashboard, Jobs, Server, handler_for, number


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = Dashboard(Path(self.temp.name) / "test.sqlite3")

    def test_targets_use_real_rules_and_do_not_accept_empty_lists(self):
        targets = self.app.save_targets([{"id": "teste", "tipo": "carro", "cor": "branco", "placa": "abc-1d23"}])
        self.assertEqual(targets[0]["placa"], "ABC1D23")
        self.assertEqual(self.app.targets(), targets)
        for invalid in (None, [], [{"id": "x", "tipo": "carro", "cor": "branco", "placa": "invalid"}]):
            with self.assertRaises(ValueError):
                self.app.save_targets(invalid)

    def test_source_never_accepts_arbitrary_server_file_paths(self):
        for identifier in ("video:../../secrets.mp4", "upload:C:/secret.mp4", "missing"):
            with self.assertRaises(ValueError):
                self.app.source({"video": identifier})
        source, label = self.app.source({"source_type": "iphone", "url": "rtsp://192.168.1.8/live"})
        self.assertEqual(label, "iphone13")
        self.assertEqual(source, "rtsp://192.168.1.8/live")

    def test_plate_targets_cannot_start_with_ocr_disabled(self):
        self.app.save_targets([{"id": "teste", "tipo": "carro", "cor": "branco", "placa": "ABC1234"}])
        with self.assertRaisesRegex(ValueError, "Habilite OCR"):
            self.app.start({"source_type": "webcam", "camera": 0, "no_ocr": True})

    def test_evaluation_is_saved_and_error_runs_are_rejected(self):
        self.app.store.record_run({"execucao": "test", "origem": "video", "estado_execucao": "concluida"}, {})
        reference = [{"id": "passagem", "alvo_id": "alvo", "origem": "video", "inicio": 0, "fim": 2}]
        result = self.app.evaluate({"run": "test", "reference": reference})
        self.assertEqual(result["falsos_negativos"], 1)
        self.assertTrue((self.app.evaluations / "test.json").is_file())
        self.app.store.record_run({"execucao": "failed", "origem": "video", "estado_execucao": "erro"}, {})
        with self.assertRaises(ValueError):
            self.app.evaluate({"run": "failed", "reference": []})
        with self.assertRaises(ValueError):
            self.app.evaluate({"run": "test", "reference": [dict(reference[0], origem="wrong")]})

    def test_numeric_inputs_reject_nonfinite_fractional_and_boolean_values(self):
        for value in ("nan", "inf", -1, 1.5, True):
            with self.assertRaises(ValueError):
                number(value, "Campo", 0, 10)

    def test_job_manager_prevents_two_readers_and_cooperatively_stops(self):
        jobs = Jobs()
        started = threading.Event()
        def work(job):
            started.set()
            job.stop_event.wait(2)
            return {"estado_execucao": "interrompida"}
        jobs.start(work, mode="test", source_label="source")
        self.assertTrue(started.wait(1))
        try:
            with self.assertRaises(ValueError):
                jobs.start(work, mode="test", source_label="source")
            jobs.stop()
        finally:
            jobs.stop_event.set()
            jobs.thread.join(2)
        self.assertEqual(jobs.snapshot()["status"], "interrompida")


class DashboardHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Dashboard(Path(self.temp.name) / "test.sqlite3")
        self.server = Server(("127.0.0.1", 0), handler_for(self.app))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.temp.cleanup()

    def request(self, method, path, data=None, token=True, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        extra = dict(headers or {})
        if token:
            extra["X-Horulince-Token"] = self.app.token
        body = json.dumps(data) if data is not None else None
        connection.request(method, path, body, extra)
        response = connection.getresponse()
        result = (response.status, response.read())
        connection.close()
        return result

    def test_page_and_api_share_existing_database(self):
        status, page = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(self.app.token.encode(), page)
        self.assertNotIn(b"__TOKEN__", page)
        status, body = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["counts"]["runs"], 0)

    def test_writes_require_session_token_and_same_origin(self):
        status, _ = self.request("POST", "/api/targets", {"targets": []}, token=False)
        self.assertEqual(status, 403)
        status, _ = self.request("POST", "/api/stop", {}, headers={"Origin": "https://example.org"})
        self.assertEqual(status, 403)
        status, _ = self.request("GET", "/api/state", headers={"Host": "evil.example"})
        self.assertEqual(status, 403)

    def test_review_updates_storage_and_audit(self):
        def evidence(path):
            Path(path).write_bytes(b"evidence")
            return True
        identifier, _ = self.app.store.create(run="test", track=1, target="alvo", source="video", video_seconds=1, payload={}, write_evidence=evidence)
        status, _ = self.request("POST", "/api/review", {"id": identifier, "state": "descartado", "actor": "operador_teste", "reason": "Teste automatizado do painel"})
        self.assertEqual(status, 200)
        self.assertEqual(self.app.store.list()[0]["state"], "descartado")
        self.assertEqual(len(self.app.store.audit(identifier)), 2)
        status, body = self.request("GET", "/api/evidence/" + identifier)
        self.assertEqual(status, 200)
        self.assertEqual(body, b"evidence")

    def test_malformed_reference_and_missing_evidence_return_errors(self):
        status, _ = self.request("POST", "/api/evaluate", {"run": "missing", "reference": []})
        self.assertEqual(status, 400)
        status, _ = self.request("GET", "/api/evidence/missing")
        self.assertEqual(status, 404)

    def test_demo_endpoints_validate_and_archive_serves_only_registered_images(self):
        status, _ = self.request("POST", "/api/demo/start", {"source_type": "webcam", "mode": "facial", "authorized": False})
        self.assertEqual(status, 400)
        status, _ = self.request("POST", "/api/demo/capture", {})
        self.assertEqual(status, 400)
        run = self.app.archive.begin("veiculos", "teste_sintetico", {})
        event = self.app.archive.event(run, "deteccao_veiculo", "teste_sintetico", 2, {"tipo": "carro"})
        status, body = self.request("GET", "/api/captures?kind=deteccao_veiculo&limit=1")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["items"][0]["id"], "demo:" + event)
        status, body = self.request("GET", "/api/captures-export?source=teste_sintetico")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["total"], 1)
        status, _ = self.request("GET", "/api/capture-image/demo:" + event)
        self.assertEqual(status, 404)
        status, _ = self.request("GET", "/api/capture-image/demo:../../secrets")
        self.assertEqual(status, 404)
        status, _ = self.request("GET", "/api/captures?since=invalid")
        self.assertEqual(status, 400)
