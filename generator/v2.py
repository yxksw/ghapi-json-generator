# -*- coding: utf-8 -*-
import config
import requests
import json
import os
from urllib.parse import urlparse


GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

print('> rate_limit: \n', requests.get('https://api.github.com/rate_limit', headers=headers).content.decode())
print('> start')


def save_json(path, content):
    root = 'v2'
    dir = root + path + '/'
    file = dir + 'data.json'
    # 创建路径
    isExists = os.path.exists(dir)
    if not isExists:
        os.makedirs(dir)
    # 写入文件
    with open(file, 'w', encoding='utf-8') as file_obj:
        json.dump(content, file_obj, ensure_ascii=False, indent=2)


def get_triggered_issue():
    """获取触发工作流的 issue 信息"""
    # GitHub Actions 提供的环境变量
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("> 非 GitHub Actions 环境，直接处理配置中的所有链接")
        return None

    try:
        with open(event_path, 'r', encoding='utf-8') as f:
            event_data = json.load(f)

        # 检查是否是 issue 事件
        if 'issue' in event_data:
            issue = event_data['issue']
            return {
                'number': issue['number'],
                'state': issue['state'],
                'labels': [label['name'] for label in issue.get('labels', [])],
                'url': issue['url'],
                'html_url': issue['html_url']
            }
    except Exception as e:
        print(f"> 读取事件数据失败: {e}")

    return None


def should_process_issue(issue_info):
    """检查 issue 是否应该被处理：已关闭且有标签"""
    if not issue_info:
        return False

    # 检查是否已关闭
    if issue_info['state'] != 'closed':
        print(f"> Issue #{issue_info['number']} 未关闭，跳过处理")
        return False

    # 检查是否有标签
    if not issue_info['labels']:
        print(f"> Issue #{issue_info['number']} 没有标签，跳过处理")
        return False

    print(f"> Issue #{issue_info['number']} 已关闭且有标签 {issue_info['labels']}，开始处理")
    return True


def main():
    issue_info = get_triggered_issue()

    # 如果有触发 issue，先检查条件
    if issue_info:
        if not should_process_issue(issue_info):
            print("> 条件不满足，退出")
            return

        # 条件满足，处理该 issue
        print(f"> 处理触发的 Issue #{issue_info['number']}")

        # 构建 API URL（从 html_url 提取）
        html_url = issue_info['html_url']
        # 解析仓库信息
        parts = html_url.replace('https://github.com/', '').split('/')
        owner = parts[0]
        repo = parts[1]

        # 获取该 issue 的详细信息
        api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_info['number']}"
        print(f"> 获取: {api_url}")

        req = requests.get(api_url, headers=headers)
        path = f"/repos/{owner}/{repo}/issues/{issue_info['number']}"
        save_json(path, json.loads(req.content.decode()))

        # 同时处理 config.yml 中配置的其他链接
        print('> 处理 config.yml 中的链接')
        for link in config.read('links'):
            print('> get: ', link)
            url = urlparse(link)
            req = requests.get(link, headers=headers)
            path = url.path
            if url.query:
                path = path + '?' + url.query
            save_json(path, json.loads(req.content.decode()))
    else:
        # 非 Actions 环境，直接处理配置中的链接
        print('> links: ', config.read('links'))
        for link in config.read('links'):
            print('> get: ', link)
            url = urlparse(link)
            req = requests.get(link, headers=headers)
            path = url.path
            if url.query:
                path = path + '?' + url.query
            save_json(path, json.loads(req.content.decode()))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print('> exception: ', e)
        import traceback
        traceback.print_exc()

    print('\n> rate_limit: \n', requests.get('https://api.github.com/rate_limit', headers=headers).content.decode())
    print('> end')
