from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from horulince.__main__ import main
from horulince.storage import AlertStore


class CLITests(unittest.TestCase):
    def test_iphone_uses_current_frame_defaults_and_does_not_load_default_video(self):
        with patch("horulince.phone.phone_source", return_value="rtsp://192.168.1.8:8554/live"), patch("horulince.pipeline.run") as run:
            self.assertEqual(main(["iphone", "--sem-ocr"]), 0)
        args = run.call_args.args[0]
        self.assertEqual(args.fonte, "rtsp://192.168.1.8:8554/live")
        self.assertEqual(args.a_cada, 1)
        self.assertEqual(args.origem, "iphone13")
        self.assertTrue(args.mostrar)

    def test_completed_zero_alert_run_evaluates_and_unknown_run_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            database = folder / "test.sqlite3"
            store = AlertStore(database)
            store.record_run({"execucao": "test", "origem": "video", "alertas": 0}, {})
            reference = folder / "reference.json"
            reference.write_text(json.dumps([{"id": "e", "alvo_id": "alvo", "origem": "video", "inicio": 0, "fim": 2}]), encoding="utf-8")
            output = folder / "metrics.json"
            arguments = ["avaliar", "--banco", str(database), "--referencia", str(reference), "--saida", str(output), "--execucao"]
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main(arguments + ["test"]), 0)
                self.assertEqual(main(arguments + ["unknown"]), 1)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["falsos_negativos"], 1)
            self.assertEqual(result["revocacao_eventos"], 0)
            self.assertIsNone(result["precisao_eventos"])
