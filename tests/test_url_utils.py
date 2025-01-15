import unittest

from url_utils import normalize_url, replace_ip_with_domain, add_api_path


class TestNormalizeUrl(unittest.TestCase):
    def test_normalize_url_empty(self):
        # 测试空字符串输入
        self.assertIsNone(normalize_url(""))

    def test_normalize_url_strip(self):
        # 测试输入字符串两端的空格是否被正确处理
        self.assertEqual(
            "https://example.com/translate",
            normalize_url("  https://example.com/translate  "),
        )

    def test_normalize_url_default_https(self):
        # 测试是否默认使用 https 协议
        self.assertEqual(
            "https://example.com/translate", normalize_url("example.com/translate")
        )

    def test_normalize_url_maintain_https(self):
        # 测试 https 协议是否被保持
        self.assertEqual(
            "https://example.com/translate",
            normalize_url("https://example.com/translate"),
        )

    def test_normalize_url_convert_http_to_https(self):
        # 测试 http 协议是否被转换为 https
        self.assertEqual(
            "https://example.com/translate",
            normalize_url("http://example.com/translate"),
        )

    def test_normalize_url_invalid_url(self):
        # 测试无效的 URL 输入
        self.assertIsNone(normalize_url("ht://example.com"))

    def test_normalize_url_query_parameters(self):
        # 测试查询参数的处理
        self.assertEqual(
            "https://example.com/translate?lang=en&mode=auto",
            normalize_url("example.com/translate?lang=en&mode=auto"),
        )

    def test_normalize_url_if_has_diff_endpoint(self):
        # 测试特殊端点
        self.assertEqual(
            "https://example.com/api",
            normalize_url("https://example.com/api"),
        )

    def test_normalize_url_if_has_diff_endpoint_and_allowed_path(self):
        # 测试特殊端点
        self.assertEqual(
            "https://example.com/v1/api",
            normalize_url("https://example.com/v1/api"),
        )

    def test_normalize_url_if_has_allowed_path(self):
        # 测试带有特殊路径的API
        self.assertEqual(
            "https://example.com/v1/translate",
            normalize_url("https://example.com/v1"),
        )

    def test_normalize_url_if_has_allowed_path_with_translate(self):
        # 特殊路径API但是有/translate端点
        self.assertEqual(
            "https://example.com/v1/translate",
            normalize_url("https://example.com/v1/translate"),
        )


class TestReplaceIpWithDomain(unittest.TestCase):
    def test_replace_with_port(self):
        self.assertEqual(
            "http://example.com:8080/path",
            replace_ip_with_domain("http://192.168.1.1:8080/path", "example.com"),
        )

    def test_replace_without_port(self):
        self.assertEqual(
            "http://example.com/path",
            replace_ip_with_domain("http://192.168.1.1/path", "example.com"),
        )

    def test_replace_hostname(self):
        self.assertEqual(
            "http://example.com/path",
            replace_ip_with_domain("http://example.org/path", "example.com"),
        )

    def test_replace_https(self):
        self.assertEqual(
            "https://example.com:8443/path",
            replace_ip_with_domain("https://192.168.1.1:8443/path", "example.com"),
        )


class TestAddApiPath(unittest.TestCase):
    def test_valid_input_with_translate(self):
        # 测试输入 URL 包含 '/translate' 且提供了有效的 API 路径。
        url = "https://example.com/translate"
        api_paths = ["v1", "v2"]
        result = add_api_path(url, api_paths)
        expected = [
            "https://example.com/v1/translate",
            "https://example.com/v2/translate",
        ]
        self.assertCountEqual(expected, result)

    def test_invalid_path_not_translate(self):
        # 测试输入 URL 路径不以 '/translate' 结尾时应返回空列表。
        url = "https://example.com/no-translate"
        api_paths = ["v1", "v2"]
        result = add_api_path(url, api_paths)
        self.assertEqual([], result)

    def test_invalid_path_not_translate_with_api_path(self):
        # 测试输入 URL 路径不以 '/translate' 结尾时而且有 api_path 作为路径应返回空列表。
        url = "https://example.com/v1/no-translate"
        api_paths = ["v1", "v2"]
        result = add_api_path(url, api_paths)
        self.assertEqual([], result)

    def test_empty_api_paths(self):
        # 测试当 `api_paths` 为空时返回空列表。
        url = "https://example.com/translate"
        api_paths = []
        result = add_api_path(url, api_paths)
        self.assertEqual([], result)

    def test_empty_url(self):
        # 测试当 URL 为空时返回空列表。
        url = ""
        api_paths = ["v1", "v2"]
        result = add_api_path(url, api_paths)
        self.assertEqual([], result)

    def test_valid_with_query_params(self):
        # 测试包含查询参数的 URL。
        url = "https://example.com/translate?lang=en"
        api_paths = ["v1"]
        result = add_api_path(url, api_paths)
        expected = ["https://example.com/v1/translate?lang=en"]
        self.assertEqual(expected, result)

    def test_duplicate_api_paths(self):
        # 测试重复的 API 路径去重效果。
        url = "https://example.com/translate"
        api_paths = ["v1", "v1"]
        result = add_api_path(url, api_paths)
        expected = ["https://example.com/v1/translate"]
        self.assertEqual(expected, result)

    def test_path_have_default_api_paths(self):
        # 测试当 url 已经有 api_path 的路径。
        url = "https://example.com/v1/translate"
        api_paths = ["v1"]
        result = add_api_path(url, api_paths)
        expected = ["https://example.com/v1/translate"]
        self.assertEqual(expected, result)


if __name__ == "__main__":
    unittest.main()
