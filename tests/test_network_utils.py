import unittest
from unittest.mock import MagicMock

import requests

from network_utils import (
    handle_error_response,
    process_successful_response,
    generate_urls,
)


class TestProcessSuccessfulResponse(unittest.TestCase):
    def setUp(self):
        # 通用的测试 URL 和默认规则
        self.url = "https://example.com/api"
        self.rules = {"include_words": ["success", "data"], "fail_regex": r"error|fail"}

    def test_successful_response(self):
        # 模拟成功的响应
        mock_response = MagicMock(spec=requests.Response)
        mock_response.json.return_value = {"data": "success: this is valid data"}
        mock_response.text = "success: this is valid data"
        latency = 0.123

        result = process_successful_response(
            self.url, mock_response, latency, self.rules
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("success", result["data"])
        self.assertAlmostEqual(result["latency"], latency)

    def test_invalid_content_due_to_regex(self):
        # 模拟响应数据匹配 fail_regex 的情况
        mock_response = MagicMock(spec=requests.Response)
        mock_response.json.return_value = {"data": "success: error in data"}
        mock_response.text = "success: error in data"
        latency = 0.456

        result = process_successful_response(
            self.url, mock_response, latency, self.rules
        )
        self.assertEqual(result["status"], "invalid_content")
        self.assertIn("error in data", result["data"])
        self.assertAlmostEqual(result["latency"], latency)

    def test_unexpected_content(self):
        # 模拟响应内容不包含 include_words 的情况
        mock_response = MagicMock(spec=requests.Response)
        mock_response.json.return_value = {"data": "random unrelated data"}
        mock_response.text = "random unrelated data"
        latency = 0.789

        result = process_successful_response(
            self.url, mock_response, latency, self.rules
        )
        self.assertEqual(result["status"], "unexpected_content")
        self.assertIn("random unrelated data", result["data"])
        self.assertAlmostEqual(result["latency"], latency)

    def test_failed_to_parse_json(self):
        # 模拟响应无法解析为 JSON 的情况
        mock_response = MagicMock(spec=requests.Response)
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "plain text response"
        latency = 0.321

        result = process_successful_response(
            self.url, mock_response, latency, self.rules
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["data"], "Failed to parse JSON")
        self.assertAlmostEqual(result["latency"], latency)

    def test_cloudflare_blocked(self):
        # 模拟被 Cloudflare 阻止的情况
        mock_response = MagicMock(spec=requests.Response)
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Attention Required! Cloudflare"
        latency = 0.654

        result = process_successful_response(
            self.url, mock_response, latency, self.rules
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["data"], "Failed to parse JSON")
        self.assertAlmostEqual(result["latency"], latency)


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


class TestGenerateUrls(unittest.TestCase):
    def test_generate_urls_http(self):
        # 测试 HTTP URL
        http_url, https_url = generate_urls("http://example.com:80/api")
        self.assertEqual(http_url, "http://example.com:80/api")
        self.assertEqual(https_url, "https://example.com:443/api")

    def test_generate_urls_https(self):
        # 测试 HTTPS URL
        http_url, https_url = generate_urls("https://example.com:443/api")
        self.assertEqual(http_url, "http://example.com:80/api")
        self.assertEqual(https_url, "https://example.com:443/api")

    def test_generate_urls_invalid(self):
        # 测试无效 URL
        with self.assertRaises(ValueError):
            generate_urls("ftp://example.com")


if __name__ == "__main__":
    unittest.main()
