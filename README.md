# Deepl API 扫描器

## 概述

本程序是一个用 Python 编写的工具，旨在扫描本地列表中的 IP 和端口，进行端点可用性检查，并分析 HTTPS 证书。同时，它还会评估 API 返回数据的完整性，检测异常情况（如返回数据异常或乱码）。

## 功能

- 从本地文件加载 IP 和端口列表并执行可用性扫描。
- 分析 HTTPS 证书以提取关联的域名并将其添加到结果中。
- 验证 API 返回数据的正确性，并检查是否存在乱码。

## 待办事项

### Checklist

- [ ] `/v1` 端点检测
- [ ] 常用下一级域名检测，比如 d/deepl/deeplx/translate.example.com
- [ ] 扫描器 API（Fofa、Shodan）接入
- [ ] 常用列表下载
- [ ] IP 地址区域分析
- [ ] CloudFlare 检测
- [ ] QPS 测试
- [ ] 自动重试机制
- [ ] 守护进程支持
- [ ] 优化记录 URL 的数据结构
- [ ] 提升排序算法性能
- [ ] 部分 API token 的接入
- [ ] 非标准端点测试
- [ ] 网页查询?

## 快速开始

1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
2. 使用 IP 列表运行程序：
   ```bash
   python scanner.py --input ips.txt
   ```

## Thanks
- https://deeplx.smnet.io/urls
- https://dxpool.dattw.eu.org/all
- https://github.com/xiaozhou26/serch_deeplx
- https://github.com/benefit77/serch_deeplx
- https://github.com/ffreemt/deeplx-pool
- https://github.com/geek-yes/deeplx-api

- https://github.com/OwO-Network/DeepLX
- https://github.com/guobao2333/DeepLX-Serverless
- https://github.com/hominsu/deeplx-rs
- https://github.com/xiaozhou26/deeplx-pro
- https://github.com/ifyour/deeplx-for-cloudflare
- https://github.com/elviainfotech/DeepLX-Serverlesscc

## 贡献

欢迎贡献！请提交拉取请求或打开问题，提出改进建议或报告错误。

