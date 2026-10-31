from pathlib import Path
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest

from horulince.storage import AlertStore, ReviewConflict


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = AlertStore(Path(self.temp.name) / "alerts.db")

    def create(self, writer=None):
        def success(path):
            Path(path).write_bytes(b"test evidence")
            return True
        return self.store.create(run="run", track=1, target="alvo", source="teste", video_seconds=1, payload={"placa": "ABC1D23"}, write_evidence=writer or success)

    def test_duplicate_is_not_saved_twice(self):
        first, created = self.create()
        second, duplicate = self.create()
        self.assertTrue(created)
        self.assertFalse(duplicate)
        self.assertEqual(first, second)
        self.assertEqual(len(self.store.list()), 1)
        self.assertEqual(len(self.store.audit()), 1)

    def test_review_requires_operator_and_reason_and_audits(self):
        alert, _ = self.create()
        for actor, reason in [("", "justificativa"), ("Ana", " ")]:
            with self.assertRaises(ValueError):
                self.store.review(alert, "confirmado_para_analise", actor, reason)
        self.assertEqual(self.store.list()[0]["state"], "pendente")
        self.store.review(alert, "revisao_solicitada", "Ana", "Placa pouco legível")
        self.store.review(alert, "descartado", "João", "Revisão da evidência")
        self.assertEqual(self.store.list()[0]["state"], "descartado")
        self.assertEqual(len(self.store.audit(alert)), 3)

    def test_failed_evidence_does_not_create_alert(self):
        with self.assertRaises(OSError):
            self.create(lambda _: False)
        self.assertEqual(self.store.list(), [])
        self.assertEqual(self.store.audit(), [])

    def test_nonexistent_review_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store.review("missing", "descartado", "Ana", "Teste")

    def test_completed_empty_run_can_be_distinguished_from_unknown_run(self):
        self.assertIsNone(self.store.get_run("unknown"))
        self.store.record_run({"execucao": "empty", "alertas": 0}, {"limiar": .7})
        self.assertEqual(self.store.get_run("empty")["summary"]["alertas"], 0)

    def test_final_decision_is_preserved_without_an_extra_audit_event(self):
        for final in ("descartado", "confirmado_para_analise"):
            with self.subTest(final=final):
                alert, _ = self.store.create(run=final, track=1, target="teste", source="teste", video_seconds=0,
                                            payload={}, write_evidence=lambda path: Path(path).write_bytes(b"test") > 0)
                self.store.review(alert, final, "Ana", "Decisão final do teste")
                before = self.store.audit(alert)
                with self.assertRaises(ReviewConflict):
                    self.store.review(alert, "revisao_solicitada", "João", "Tentativa de alterar decisão")
                self.assertEqual(self.store.audit(alert), before)
                self.assertEqual(next(a for a in self.store.list() if a["id"] == alert)["state"], final)

    def test_stale_open_state_is_rejected_and_null_identity_is_invalid(self):
        alert, _ = self.create()
        self.store.review(alert, "revisao_solicitada", "Ana", "Conferir evidência", expected_state="pendente")
        with self.assertRaises(ReviewConflict):
            self.store.review(alert, "descartado", "João", "Tela antiga", expected_state="pendente")
        self.assertEqual(len(self.store.audit(alert)), 2)
        for actor, reason in ((None, "teste"), ("Ana", None), (" ", "teste"), ("Ana", " ")):
            with self.assertRaises(ValueError):
                self.store.review(alert, "descartado", actor, reason)

    def test_two_concurrent_final_reviews_have_only_one_winner(self):
        alert, _ = self.create()
        barrier = threading.Barrier(2)
        def review(state):
            barrier.wait(timeout=3)
            try:
                self.store.review(alert, state, "operador_teste", "Decisão concorrente", expected_state="pendente")
                return "saved"
            except ReviewConflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(review, ["descartado", "confirmado_para_analise"]))
        self.assertCountEqual(results, ["saved", "conflict"])
        self.assertEqual(len(self.store.audit(alert)), 2)

    def test_plate_read_is_independent_of_alerts_and_can_gain_consensus(self):
        def evidence(path):
            Path(path).write_bytes(b"synthetic plate evidence")
            return True
        payload={"placa":"ABC1D23","estado_leitura":"pendente_consenso","confianca_ocr":80,"quadro":1}
        args=dict(run="run",track=1,source="teste",video_seconds=0,payload=payload,write_evidence=evidence)
        identifier,created=self.store.record_plate(**args)
        self.assertTrue(created)
        self.assertEqual(self.store.plate_count(),1)
        self.assertEqual(self.store.list(),[])
        payload=payload | {"estado_leitura":"consolidada","quadro":5,
                           "consolidacao":{"leituras":3,"tentativas":3,"confianca_ocr_media":80}}
        second,created=self.store.record_plate(**(args | {"payload":payload}))
        self.assertEqual(identifier,second)
        self.assertFalse(created)
        with self.store.connect() as db:
            import json
            saved=json.loads(db.execute("SELECT payload FROM plate_reads WHERE id=?",(identifier,)).fetchone()[0])
        self.assertEqual(saved["estado_leitura"],"consolidada")
        self.assertEqual(saved["quadro"],1)
        self.assertEqual(saved["quadro_confirmacao"],5)

    def test_uncertain_plate_and_failed_image_do_not_create_a_record(self):
        args=dict(run="run",track=1,source="teste",video_seconds=0,
                  payload={"placa":"ABC1D23","estado_leitura":"pendente_consenso","confianca_ocr":20},
                  write_evidence=lambda _:False)
        with self.assertRaises(ValueError):
            self.store.record_plate(**args)
        args["payload"]["confianca_ocr"]=80
        with self.assertRaises(OSError):
            self.store.record_plate(**args)
        self.assertEqual(self.store.plate_count(),0)
