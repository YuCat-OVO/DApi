import unittest

from url_class import ApiURL
from url_utils import deduplicate_urls


class TestDeduplicateUrls(unittest.TestCase):
    def setUp(self):
        """设置测试数据"""
        # 创建一些测试用的 ApiURL 实例
        self.url1 = ApiURL(
            host="api.example.com",
            has_domain=True,
            scheme="https",
            port_set={443, 8443},
            path_set={"/v1/users", "/v1/auth"},
            param_dict={"api_key": ["123"], "version": ["1.0"]},
        )

        self.url2 = ApiURL(
            host="api.example.com",
            has_domain=True,
            scheme="https",
            port_set={8080},
            path_set={"/v1/products"},
            param_dict={"api_key": ["456"]},
        )

        self.url3 = ApiURL(
            host="api2.example.com",
            has_domain=True,
            scheme="https",
            port_set={443},
            path_set={"/v2/users"},
            param_dict={"token": ["xyz"]},
        )

    def test_empty_list(self):
        """测试空列表输入"""
        expected = []
        actual = deduplicate_urls([])
        self.assertEqual(expected, actual)

    def test_single_url(self):
        """测试单个 URL 的情况"""
        expected_length = 1
        actual_result = deduplicate_urls([self.url1])
        self.assertEqual(expected_length, len(actual_result))
        self.assertEqual(self.url1, actual_result[0])

    def test_different_hosts(self):
        """测试不同 host 的 URL"""
        expected_length = 2
        expected_hosts = {"api.example.com", "api2.example.com"}

        actual_result = deduplicate_urls([self.url1, self.url3])
        actual_hosts = {url.host for url in actual_result}

        self.assertEqual(expected_length, len(actual_result))
        self.assertEqual(expected_hosts, actual_hosts)

    def test_same_host_merge(self):
        """测试相同 host 的 URL 合并"""
        expected_length = 1
        expected_host = "api.example.com"
        expected_ports = {443, 8443, 8080}
        expected_paths = {"/v1/users", "/v1/auth", "/v1/products"}
        expected_params = {"api_key": ["123", "456"], "version": ["1.0"]}

        actual_result = deduplicate_urls([self.url1, self.url2])
        merged_url = actual_result[0]

        self.assertEqual(expected_length, len(actual_result))
        self.assertEqual(expected_host, merged_url.host)
        self.assertEqual(expected_ports, merged_url.port_set)
        self.assertEqual(expected_paths, merged_url.path_set)
        self.assertEqual(expected_params, merged_url.param_dict)

    def test_mixed_hosts(self):
        """测试混合场景：有相同和不同 host 的 URL"""
        url2_duplicate = ApiURL(
            host="api.example.com",
            has_domain=True,
            scheme="https",
            port_set={9090},
            path_set={"/v1/orders"},
            param_dict={"format": ["json"]},
        )

        expected_length = 2
        expected_ports = {443, 8443, 9090}
        expected_paths = {"/v1/users", "/v1/auth", "/v1/orders"}
        expected_params = {"api_key": ["123"], "version": ["1.0"], "format": ["json"]}

        actual_result = deduplicate_urls([self.url1, self.url3, url2_duplicate])
        merged_url = next(url for url in actual_result if url.host == "api.example.com")

        self.assertEqual(expected_length, len(actual_result))
        self.assertEqual(expected_ports, merged_url.port_set)
        self.assertEqual(expected_paths, merged_url.path_set)
        self.assertEqual(expected_params, merged_url.param_dict)

    def test_preserve_scheme_and_domain_flag(self):
        """测试合并时保留 scheme 和 has_domain 标志"""
        url1 = ApiURL(
            host="example.com",
            has_domain=True,
            scheme="https",
            port_set={443},
            path_set={"/path1"},
            param_dict={},
        )

        url2 = ApiURL(
            host="example.com",
            has_domain=True,
            scheme="http",
            port_set={80},
            path_set={"/path2"},
            param_dict={},
        )

        expected_length = 1
        expected_scheme = "https"
        expected_has_domain = True

        actual_result = deduplicate_urls([url1, url2])
        merged_url = actual_result[0]

        self.assertEqual(expected_length, len(actual_result))
        self.assertEqual(expected_scheme, merged_url.scheme)
        self.assertEqual(expected_has_domain, merged_url.has_domain)


if __name__ == "__main__":
    unittest.main()
