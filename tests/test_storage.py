from pathlib import Path
import tempfile
import unittest

from horulince.storage import AlertStore


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
