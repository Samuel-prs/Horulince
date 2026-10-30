import unittest

from horulince.core import PlateVotes, Tracker, candidate, normalize_plate, plate_relation, valid_plate


def detection(x=0, kind="carro"):
    return {"box": (x, 0, x + 100, 100), "tipo": kind}


class PlateTests(unittest.TestCase):
    def test_formats_and_relations(self):
        for value in ("ABC1234", "ABC1D23"):
            self.assertTrue(valid_plate(value))
        for value in ("", "ABC1D2", "123ABCD", "ABC1DD3"):
            self.assertFalse(valid_plate(value))
        self.assertEqual(normalize_plate(" abc-1d23 "), "ABC1D23")
        self.assertEqual(plate_relation("abc-1d23", "ABC1D23"), "exata")
        self.assertEqual(plate_relation("ABC1D28", "ABC1D23"), "aproximada")
        self.assertEqual(plate_relation("ABC1E28", "ABC1D23"), "diferente")
        self.assertEqual(plate_relation("", ""), "invalida")

    def test_consensus_requires_distinct_observations(self):
        votes = PlateVotes()
        for _ in range(2):
            votes.add("ABC1D23", 80)
        self.assertIsNone(votes.consensus())
        votes.add("ABC1D23", 70)
        self.assertEqual(votes.consensus()["placa"], "ABC1D23")
        self.assertEqual(votes.consensus()["leituras"], 3)

    def test_missing_or_conflicting_readings_expire_consensus(self):
        votes = PlateVotes()
        for _ in range(3):
            votes.add("ABC1D23", 80)
        for _ in range(3):
            votes.add("ABC1D28", 80)
        self.assertIsNone(votes.consensus())
        for _ in range(8):
            votes.add(None, 0)
        self.assertIsNone(votes.consensus())

    def test_plate_target_has_no_attribute_fallback(self):
        target = {"tipo": "carro", "cor": "branco", "placa": "ABC1D23"}
        self.assertIsNone(candidate("carro", [("branco", 1)], None, target))
        match = candidate("carro", [("branco", 1)], {"placa": "ABC1D28"}, target)
        self.assertEqual(match["correspondencia"], "aproximada")
        self.assertNotIn("confianca", match)


class TrackingTests(unittest.TestCase):
    def test_ids_and_readings_do_not_leak_between_vehicles(self):
        tracker = Tracker()
        first = tracker.update([detection(0), detection(200)], 1)
        first[0].votes.add("ABC1D23", 80)
        second = tracker.update([detection(205), detection(5)], 2)
        self.assertEqual([t.id for t in second], [first[1].id, first[0].id])
        self.assertFalse(second[0].votes.readings)
        self.assertEqual(len(second[1].votes.readings), 1)

    def test_ambiguous_crossing_drops_history(self):
        tracker = Tracker()
        previous = tracker.update([detection(0), detection(80)], 1)
        for track in previous:
            track.votes.add("ABC1D23", 80)
        current = tracker.update([detection(40)], 2)
        self.assertNotIn(current[0].id, [t.id for t in previous])
        self.assertFalse(current[0].votes.readings)
        self.assertTrue(all(t.id not in tracker.tracks for t in previous))

    def test_expired_track_cannot_donate_plate(self):
        tracker = Tracker(max_age=2)
        old = tracker.update([detection()], 1)[0]
        new = tracker.update([detection()], 4)[0]
        self.assertNotEqual(old.id, new.id)


if __name__ == "__main__":
    unittest.main()
