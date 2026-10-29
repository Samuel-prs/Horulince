import unittest
from horulince.evaluation import evaluate


def alert(identifier, seconds, plate="ABC1D23"):
    return {"id": identifier, "target": "alvo", "source": "video", "video_seconds": seconds, "payload": {"placa": plate}}


def event(identifier, start, end):
    return {"id": identifier, "alvo_id": "alvo", "origem": "video", "inicio": start, "fim": end, "placa": "ABC1D23"}


class EvaluationTests(unittest.TestCase):
    def test_one_event_is_not_counted_twice(self):
        result = evaluate([alert("a", 1), alert("b", 1.5), alert("c", 9)], [event("e", 0, 2), event("f", 4, 6)])
        self.assertEqual(result["verdadeiros_positivos"], 1)
        self.assertEqual(result["falsos_positivos"], 2)
        self.assertEqual(result["falsos_negativos"], 1)
        self.assertEqual(result["revocacao_eventos"], .5)

    def test_maximum_matching_is_not_greedy(self):
        result = evaluate([alert("a", 2), alert("b", 1)], [event("wide", 0, 3), event("narrow", 2, 2.5)])
        self.assertEqual(result["verdadeiros_positivos"], 2)

    def test_plate_accuracy_is_separate_from_event_retrieval(self):
        result = evaluate([alert("a", 1, "ABC1D28")], [event("e", 0, 2)])
        self.assertEqual(result["precisao_eventos"], 1)
        self.assertEqual(result["acerto_placa_completa_em_eventos_pareados"], 0)

    def test_no_data_does_not_fabricate_performance(self):
        result = evaluate([], [])
        self.assertIsNone(result["precisao_eventos"])
        self.assertIsNone(result["revocacao_eventos"])
        self.assertIsNone(result["acerto_placa_completa_em_eventos_pareados"])

    def test_reference_validation(self):
        with self.assertRaises(ValueError):
            evaluate([], [event("e", 4, 2)])
        with self.assertRaises(ValueError):
            evaluate([], [event("e", 1, 2), event("e", 1, 2)])
