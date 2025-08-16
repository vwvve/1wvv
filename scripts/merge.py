# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
@Project ：1wvv 
@File    ：merge.py
@Author  ：venus
@Date    ：2025/8/16 下午1:44:47
@Des     ：merge
"""

import json
from urllib.parse import quote

import requests
from packaging import version
import re
import os
from pprint import pprint

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
headers = {
    "user-agent": "Forward/316 CFNetwork/3826.600.41 Darwin/24.6.0"
}


def is_url_accessible(url: str) -> bool:
    try:
        resp = requests.head(url, allow_redirects=True, timeout=10)
        return 200 <= resp.status_code < 400
    except requests.RequestException:
        return False


def check_url_final(url: str):
    """
    检测 URL 最终是否可访问。
    自动跟随跳转，并返回最终状态码和最终 URL。

    返回:
        (is_accessible, final_url, status_code)
    """
    try:
        # 跟随重定向直到最终页面
        resp = requests.head(url, headers=headers, allow_redirects=True, timeout=10)

        # 如果服务器不支持 HEAD，则尝试 GET（只获取头部，避免下载全部内容）
        if resp.status_code == 405:
            resp = requests.get(url, headers=headers, allow_redirects=True, stream=True, timeout=10)
            resp.close()

        final_url = resp.url
        status_code = resp.status_code
        is_accessible = 200 <= status_code < 300

        return is_accessible, final_url, status_code

    except requests.RequestException:
        return False, None, None


def url_to_repo(raw_url: str) -> str:
    m = re.match(r"https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/", raw_url)
    if m:
        user, repo = m.groups()
        return f"https://github.com/{user}/{repo}"
    return raw_url


def get_repo(repo_path: str):
    """
    将仓库转换为json
    :param repo_path: 路径
    :return: json对象
    """

    widgets_path = os.path.join(BASE_DIR, repo_path.split("/")[0] + "/widgets")

    if not os.path.exists(widgets_path):
        os.makedirs(widgets_path)

    with open(os.path.join(BASE_DIR, repo_path), "r", encoding="utf-8") as f:
        repo_json = json.load(f)

        all_widgets = []
        thanks = []

        for name, url in repo_json.items():
            print(f"正在获取: {name} -> {url}")
            try:
                resp = requests.get(url, timeout=15, headers=headers)
                resp.raise_for_status()
                text = re.sub(r",\s*([]}])", r"\1", resp.text)
                data = json.loads(text)
                widgets = data.get("widgets", [])

                all_widgets.extend(widgets)

                repo_link = url_to_repo(url)

                thanks.append(f"- [{name}]({repo_link})")
                print(f"  ✅ 已加载 {len(widgets)} 个 widgets")

                # 创建每个name 将当前repo下的widget下载保存到name/widgets目录下

            except Exception as e:
                print(f"  ⚠️ 无法读取 {name}: {e}")
    return all_widgets, thanks


def try_decode(text):
    """尝试用不同的编码解码字符串"""
    try:
        return text.encode('latin1').decode('utf-8')
    except:
        return text


def normalize_version(v: str):
    if not v:
        return version.parse("0.0.0")
    v_clean = re.sub(r"^[vV]", "", v.strip())
    try:
        return version.parse(v_clean)
    except Exception:
        return version.parse("0.0.0")


def get_name_after_last_slash(url):
    """
    获取 URL 中最后一个  "/"  后的名字.
    Args:
      url: URL 字符串.
    Returns:
      最后一个  "/"  后的名字.  如果 URL 中没有  "/" , 则返回整个 URL.
    """
    last_slash_index = url.rfind("/")
    if last_slash_index == -1:
        return url
    else:
        return url[last_slash_index + 1:]


def change_repo_to_myself(file_path, owner="vwvve", repo="1wvv", branch="main"):
    return f"https://raw.githubusercontent.com/{owner}/{repo}/refs/heads/{branch}/{quote(file_path)}"


def download_widgets_script(widgets: list, widgets_path: str):
    merged = {}
    if widgets is not None:
        for widget in widgets:

            wid = widget.get("id")
            url = widget.get("url")

            w_author = widget.get("author")
            w_title = widget.get("title")

            if not wid or not url or not w_author:
                continue

            w_author = try_decode(widget.get("author"))

            w_path = os.path.join(widgets_path, w_author)
            if not os.path.exists(w_path):
                os.makedirs(w_path)

            ok, final_url, code = check_url_final(url)

            js_name = get_name_after_last_slash(url)
            js_path = os.path.join(w_path, js_name)

            if not ok:
                print(f"  ⚠️ widget 被移除: {widget.get('id', '')} (最终 URL: {final_url}, 状态码: {code})")
                continue

            # 全部重新编码下
            widget["id"] = widget.get("title").replace("🔞", "").strip()
            widget["title"] = try_decode(widget.get("title"))
            widget["description"] = try_decode(widget.get("description"))
            widget["author"] = w_author

            try:
                # download
                resp = requests.get(final_url, timeout=15, headers=headers)
                resp.raise_for_status()
                with open(js_path, "wb") as f:
                    f.write(resp.content)  # 使用 resp.content 获取二进制内容
                print(f"文件 '{js_name}' 已成功下载并保存到 '{js_path}'")
            except Exception as e:
                print(f"  ⚠️ 无法下载 {url}: {e}")

            # 这是原始URL
            # widget["url"] = final_url
            widget["url"] = change_repo_to_myself(f"repo/widgets/{w_author}/{js_name}")

            cur_ver = normalize_version(widget.get("version", "0.0.0"))

            if w_title not in merged:
                # 之前没有这个 id，直接放进去
                merged[wid] = widget

            else:
                # 已有相同 id，比较版本号
                old_ver = normalize_version(merged[wid].get("version", "0.0.0"))
                if cur_ver > old_ver:
                    merged[wid] = widget
    return merged


def main():
    repo_path = "repo/repo.json"
    all_widgets, thanks = get_repo(repo_path)
    widgets_path = os.path.join(BASE_DIR, repo_path.split("/")[0] + "/widgets")
    merged = download_widgets_script(widgets=all_widgets, widgets_path=widgets_path)

    result = {
        "title": "1Wvv's AllInOne Widgets",
        "description": "合并自FW Widgets源(50% off code: 1w5.5)",
        "icon": "https://avatars.githubusercontent.com/u/225779571",
        "widgets": list(merged.values())
    }

    output_file = os.path.join(BASE_DIR, "allInOne.fwd")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 合并完成，共 {len(result['widgets'])} 个 widget，已生成 {output_file}")

    readme_content = "# 1Wvv's AllInOne Widgets\n\n" \
                     "本仓库自动合并多个 ForwardWidgets 源，方便统一使用。(50% off code: 1w5.5)\n\n" \
                     "自动检测链接是否有效, 最终生成集合不包含无效模块\n\n" \
                     f"👉 [allinone.fwd](https://github.com/vwvve/1wvv/blob/main/allInOne.fwd)\n\n" \
                     "## 感谢以下原始仓库作者\n" \
                     + "\n".join(thanks) + "\n"

    readme_file = os.path.join(BASE_DIR, "README.md")
    with open(readme_file, "w", encoding="utf-8") as f:
        f.write(readme_content)

    print("✅ README.md 已更新")


if __name__ == '__main__':
    main()
