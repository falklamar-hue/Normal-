import unittest

from kystvakt_varsel import Facility, Vessel, find_alerts, haversine_km, is_relevant_coast_guard


class KystvaktVarselTest(unittest.TestCase):
    def test_haversine_short_distance(self):
        dist = haversine_km(63.4305, 10.3951, 63.4405, 10.4051)
        self.assertGreater(dist, 1.0)
        self.assertLess(dist, 2.0)

    def test_relevant_vessel_keywords(self):
        vessel = Vessel("257123000", "KV Sortland", 63.0, 8.0, "Patrol")
        self.assertTrue(is_relevant_coast_guard(vessel, ["kystvakt", "kv "]))

    def test_find_alerts_within_radius(self):
        facilities = [Facility("Anlegg A", 63.700, 8.740)]
        vessels = [
            Vessel("257111111", "KV Test", 63.702, 8.744, "Coast Guard"),
            Vessel("257222222", "Fraktebåt", 63.701, 8.741, "Cargo"),
        ]
        alerts = find_alerts(facilities, vessels, ["kv", "coast guard"], radius_km=2.0)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].vessel.mmsi, "257111111")


if __name__ == "__main__":
    unittest.main()
