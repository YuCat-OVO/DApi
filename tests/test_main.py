import unittest

from main import CategorizedResults


class TestCategorizedResults(unittest.TestCase):
    def setUp(self):
        self.results = CategorizedResults()
        self.results.available_https_endpoints = {
            "https://example.com": 0.5,
            "https://example.org": 0.3,
            "https://example.net": -1,
        }
        self.results.available_http_endpoints = {
            "http://example.com": 0.7,
            "http://example.org": 0.4,
        }
        self.results.timeout_or_unreachable = [
            "http://example.net",
            "http://example.edu",
        ]

    def test_sort_available_https_endpoints(self):
        self.results.sort("available_https_endpoints")
        expected = {
            "https://example.org": 0.3,
            "https://example.com": 0.5,
            "https://example.net": -1,
        }
        self.assertEqual(self.results.available_https_endpoints, expected)

    def test_sort_timeout_or_unreachable(self):
        self.results.sort("timeout_or_unreachable")
        expected = ["http://example.edu", "http://example.net"]
        self.assertEqual(self.results.timeout_or_unreachable, expected)

    def test_sort_invalid_field(self):
        with self.assertRaises(ValueError):
            self.results.sort("invalid_field")

    def test_sort_unsortable_field(self):
        with self.assertRaises(ValueError):
            self.results.sort("failed_urls")


class TestCategorizedResults(unittest.TestCase):
    def setUp(self):
        self.results = CategorizedResults(
            available_https_endpoints={
                "https://example.com": 0.3,
                "https://example.org": 0.1,
                "https://invalid.com": -1,
            },
            available_http_endpoints={
                "http://example.com": 0.2,
                "http://example.org": 0.4,
                "http://invalid.com": -1,
            },
            rate_limited={
                "http://rate-limited.com": 0.5,
                "http://rate-limited.org": 0.2,
                "http://invalid.com": -1,
            },
            timeout_or_unreachable=["http://timeout.com", "http://unreachable.com"],
            failed_urls=["http://failed.com", "http://error.com"],
        )

    def test_sort_dict_ascending_with_invalid_latency(self):
        self.results.sort("available_https_endpoints")
        expected = {
            "https://example.org": 0.1,
            "https://example.com": 0.3,
            "https://invalid.com": -1,
        }
        self.assertEqual(self.results.available_https_endpoints, expected)

    def test_sort_dict_descending_with_invalid_latency(self):
        self.results.sort("available_http_endpoints", reverse=True)
        expected = {
            "http://example.org": 0.4,
            "http://example.com": 0.2,
            "http://invalid.com": -1,
        }
        self.assertEqual(self.results.available_http_endpoints, expected)

    def test_sort_list_ascending(self):
        self.results.sort("timeout_or_unreachable")
        expected = ["http://timeout.com", "http://unreachable.com"]
        self.assertEqual(self.results.timeout_or_unreachable, expected)

    def test_sort_list_descending(self):
        self.results.sort("failed_urls", reverse=True)
        expected = ["http://failed.com", "http://error.com"]
        self.assertEqual(self.results.failed_urls, expected)

    def test_sort_invalid_field(self):
        with self.assertRaises(ValueError):
            self.results.sort("invalid_field")


if __name__ == "__main__":
    unittest.main()
