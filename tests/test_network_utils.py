import unittest

from network_utils import (
    handle_error_response,
    ProcessedResponse,
    ReturnStatus,
)


class TestHandleErrorResponse(unittest.TestCase):
    def test_server_error(self):
        url = "https://example.com"
        response = handle_error_response(url, 503, 0.12)
        expected = {
            "status": "50x",
            "data": "HTTP error 503 at https://example.com",
            "latency": 0.12,
        }
        self.assertEqual(response, expected)

    def test_rate_limit_exceeded(self):
        url = "https://example.com"
        response = handle_error_response(url, 429, 0.25)
        expected = {
            "status": "429",
            "data": "Rate limit exceeded (429) at https://example.com.",
            "latency": 0.25,
        }
        self.assertEqual(response, expected)

    def test_unauthorized(self):
        url = "https://example.com"
        response = handle_error_response(url, 401, 0.30)
        expected = {
            "status": "401",
            "data": "Unauthorized (401) at https://example.com.",
            "latency": 0.30,
        }
        self.assertEqual(response, expected)

    def test_unhandled_status_code(self):
        url = "https://example.com"
        response = handle_error_response(url, 418, 0.40)  # Example: 418 I'm a Teapot
        expected = {
            "status": "418",
            "data": "Unhandled HTTP status code 418 at https://example.com.",
            "latency": 0.40,
        }
        self.assertEqual(response, expected)

    def test_status_code_in_500_range(self):
        url = "https://example.com"
        response = handle_error_response(url, 501, 0.50)
        expected = {
            "status": "50x",
            "data": "HTTP error 501 at https://example.com",
            "latency": 0.50,
        }
        self.assertEqual(response, expected)


class TestReturnStatus(unittest.TestCase):
    def test_match_statement(self):
        response = ProcessedResponse(status=ReturnStatus.SUCCESS, data={}, latency=0.1)
        self.assertEqual(response.status, "SUCCESS")


if __name__ == "__main__":
    unittest.main()
