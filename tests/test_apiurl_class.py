import unittest
from urllib.parse import urlparse

from config import ACCESS_TOKEN_PATH, SERVICE_DEFAULT_PORT
from url_class import ApiURL


class TestApiURL(unittest.TestCase):
    def setUp(self):
        # 测试用例的初始化
        self.valid_url = "https://example.com:8080/v1/translate?token=666666"
        self.invalid_url = "https://****.mak****.net"
        self.empty_url = ""
        self.no_scheme_url = "example.com/v1/translate"
        self.http_url = "http://example.com/v1/translate"
        self.custom_path_url = "https://example.com/api"
        self.token_path_url = f"https://example.com/{ACCESS_TOKEN_PATH[0]}"
        self.ip_url = "https://192.168.1.1/v1/translate"

    def test_from_url_valid(self):
        # 测试从有效 URL 创建实例
        api_url = ApiURL.from_url(self.valid_url)
        self.assertEqual(api_url.host, "example.com")
        self.assertEqual(api_url.scheme, "https")
        self.assertEqual(
            api_url.port_set, {8080, SERVICE_DEFAULT_PORT}
        )  # 默认端口 443 被添加
        self.assertEqual({"/v1/translate"}, api_url.path_set)
        self.assertEqual({"token": ["666666"]}, api_url.param_dict)

    def test_from_url_invalid(self):
        # 测试从无效 URL 创建实例
        with self.assertRaises(ValueError):
            ApiURL.from_url(self.invalid_url)

    def test_from_url_empty(self):
        # 测试从空 URL 创建实例
        with self.assertRaises(ValueError):
            ApiURL.from_url(self.empty_url)

    def test_from_url_no_scheme(self):
        # 测试从无协议 URL 创建实例
        api_url = ApiURL.from_url(self.no_scheme_url)
        self.assertEqual("https", api_url.scheme)  # 默认协议为 https

    def test_from_url_http(self):
        # 测试从 HTTP URL 创建实例
        api_url = ApiURL.from_url(self.http_url)
        self.assertEqual("https", api_url.scheme)  # HTTP 被转换为 HTTPS

    def test_from_url_custom_path(self):
        # 测试自定义路径
        api_url = ApiURL.from_url(self.custom_path_url)
        self.assertEqual({"/api"}, api_url.path_set)

    def test_from_url_token_path(self):
        # 测试令牌路径
        api_url = ApiURL.from_url(self.token_path_url)
        self.assertIn("/access_token/translate", api_url.path_set)

    def test_from_url_ip(self):
        # 测试 IP 地址作为主机
        api_url = ApiURL.from_url(self.ip_url)
        self.assertEqual("192.168.1.1", api_url.host)
        self.assertFalse(api_url.has_domain)  # IP 地址不应标记为域名

    def test_replace_domain_valid(self):
        # 测试替换域名
        original = ApiURL.from_url(self.valid_url)
        new_domain = "newdomain.com"
        new_api_url = ApiURL.replace_domain(original, new_domain)
        self.assertEqual(new_api_url.host, new_domain)
        self.assertTrue(new_api_url.has_domain)
        self.assertEqual(new_api_url.scheme, original.scheme)
        self.assertEqual(new_api_url.port_set, original.port_set)
        self.assertEqual(new_api_url.path_set, original.path_set)
        self.assertEqual(new_api_url.param_dict, original.param_dict)

    def test_replace_domain_invalid(self):
        # 测试替换为无效域名
        original = ApiURL.from_url(self.valid_url)
        with self.assertRaises(ValueError):
            ApiURL.replace_domain(original, "****.asu****.today")

    def test_replace_domain_empty(self):
        # 测试替换为空域名
        original = ApiURL.from_url(self.valid_url)
        with self.assertRaises(ValueError):
            ApiURL.replace_domain(original, "")

    def test_generate_url_list(self):
        # 测试生成 URL 列表
        api_url = ApiURL.from_url(self.valid_url)
        url_list = api_url.generate_url_list()
        self.assertGreater(len(url_list), 0)
        for url in url_list:
            parsed_url = urlparse(url)
            self.assertIn(parsed_url.scheme, ["http", "https"])
            self.assertIn(parsed_url.hostname, ["example.com"])
            self.assertIn(parsed_url.path, ["/api/v1/translate"])

    def test_add_same_host(self):
        # 测试相同主机的加法运算
        url1 = ApiURL.from_url("https://example.com/api/v1?param1=value1")
        url2 = ApiURL.from_url("https://example.com/api/v2?param2=value2")
        combined = url1 + url2
        self.assertEqual(combined.host, "example.com")
        self.assertEqual(combined.path_set, {"/api/v1", "/api/v2"})
        self.assertEqual(
            combined.param_dict, {"param1": ["value1"], "param2": ["value2"]}
        )

    def test_add_different_host(self):
        # 测试不同主机的加法运算
        url1 = ApiURL.from_url("https://example1.com/api/v1")
        url2 = ApiURL.from_url("https://example2.com/api/v2")
        with self.assertRaises(ValueError):
            _ = url1 + url2

    def test_hash(self):
        # 测试哈希值计算
        url1 = ApiURL.from_url("https://example.com/api/v1")
        url2 = ApiURL.from_url("https://example.com/api/v2")
        self.assertEqual(hash(url1), hash(url2))  # 相同主机，哈希值应相同

    def test_parse_query(self):
        # 测试查询参数解析
        query = "param1=value1&param2=value2&param1=value3"
        parsed = ApiURL._parse_query(query)
        self.assertEqual(parsed, {"param1": ["value1", "value3"], "param2": ["value2"]})

    def test_parse_path_default(self):
        # 测试默认路径解析
        path = ""
        parsed = ApiURL._parse_path(path)
        self.assertIn("/translate", parsed)

    def test_parse_path_token(self):
        # 测试令牌路径解析
        path = "/access_token"
        parsed = ApiURL._parse_path(path)
        self.assertIn("/access_token/translate", parsed)

    def test_parse_path_custom(self):
        # 测试自定义路径解析
        path = "/custom/path"
        parsed = ApiURL._parse_path(path)
        self.assertIn("/custom/path", parsed)


if __name__ == "__main__":
    unittest.main()
