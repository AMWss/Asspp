#!/usr/bin/env python3
"""Create HTTPS OTA manifests and a Chinese installation page from the IPA."""
import argparse
import html
from pathlib import Path
import plistlib
from urllib.parse import quote, urlsplit

from verify_ipa import verify


def https_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment or parsed.username:
        raise ValueError("OTA URLs must be public HTTPS URLs without credentials, queries, or fragments")
    return url.rstrip("/")


def generate(output: Path, base: str, ipa_url: str, info: dict, source: str, variant: str = "ipad16") -> None:
    base, ipa_url = https_url(base), https_url(ipa_url)
    title = "Asspp iPad 16" if variant == "ipad16" else "Asspp iPhone"
    device = "iPad" if variant == "ipad16" else "iPhone"
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"items": [{"assets": [{"kind": "software-package", "url": ipa_url}], "metadata": {
        "bundle-identifier": info["CFBundleIdentifier"],
        "bundle-version": str(info["CFBundleVersion"]),
        "kind": "software", "title": title,
    }}]}
    (output / "manifest.plist").write_bytes(plistlib.dumps(manifest))
    ota = "itms-services://?action=download-manifest&url=" + quote(base + "/manifest.plist", safe="")
    page = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} 安装</title>
<style>body{{font:17px/1.7 system-ui;max-width:640px;margin:64px auto;padding:0 24px;color:#172234;background:#f5f7fa}}
.install{{display:inline-block;background:#145ee3;color:white;padding:12px 24px;border-radius:12px;text-decoration:none}}
code{{overflow-wrap:anywhere}}</style></head><body>
<h1>{title}</h1><p>适用于 iOS / iPadOS {html.escape(info['MinimumOSVersion'])} 及以上版本的 {device}。</p>
<p>版本 {html.escape(str(info['CFBundleShortVersionString']))} · 构建 {html.escape(str(info['CFBundleVersion']))}</p>
<p><a class="install" href="{html.escape(ota, quote=True)}">安装 / 更新</a></p>
<p>请用 {device} 的 Safari 打开。Ad Hoc 安装要求此设备的 UDID 已加入签名描述文件；证书必须有效。</p>
<p><a href="{html.escape(ipa_url, quote=True)}">下载已签名 IPA</a></p>
<p>已完成构建与包检查。登录、App Store 下载及安装效果仍以设备上的实际验证为准。</p>
<details><summary>构建来源</summary><code>{html.escape(source)}</code></details>
</body></html>'''
    (output / "install.html").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--ipa-url", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--variant", choices=["ipad16", "iphone"], default="ipad16")
    args = parser.parse_args()
    generate(args.output, args.base_url, args.ipa_url, verify(args.ipa, signed=True, variant=args.variant), args.source, args.variant)
