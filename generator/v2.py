# -*- coding: utf-8 -*-
import config
import requests
import json
import os
from urllib.parse import urlparse


GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

# 存储所有 issue 数据的文件
ALL_ISSUES_FILE = 'v2/all_issues.json'

print('> rate_limit: \n', requests.get('https://api.github.com/rate_limit', headers=headers).content.decode())
print('> start')


def load_all_issues():
    """加载所有已保存的 issue 数据"""
    if os.path.exists(ALL_ISSUES_FILE):
        try:
            with open(ALL_ISSUES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"> 加载 all_issues.json 失败: {e}")
    return []


def save_all_issues(all_issues):
    """保存所有 issue 数据到单个文件"""
    # 创建目录
    dir_path = os.path.dirname(ALL_ISSUES_FILE)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path)
    
    with open(ALL_ISSUES_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_issues, f, ensure_ascii=False, indent=2)


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


def parse_repo_from_url(html_url):
    """从 html_url 解析仓库信息"""
    parts = html_url.replace('https://github.com/', '').split('/')
    return parts[0], parts[1]


def fetch_issue_detail(owner, repo, issue_number):
    """获取 issue 详细信息"""
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
    print(f"> 获取: {api_url}")
    
    req = requests.get(api_url, headers=headers)
    if req.status_code == 200:
        return json.loads(req.content.decode())
    else:
        print(f"> 获取失败: {req.status_code}")
        return None


def issue_exists(all_issues, issue_number):
    """检查 issue 是否已存在列表中"""
    for issue in all_issues:
        if issue['number'] == issue_number:
            return True
    return False


def process_issue(issue_info, all_issues):
    """处理单个 issue，获取其详细信息并添加到列表"""
    owner, repo = parse_repo_from_url(issue_info['html_url'])
    issue_number = issue_info['number']
    
    # 检查是否已存在
    if issue_exists(all_issues, issue_number):
        print(f"> Issue #{issue_number} 已存在，跳过")
        return all_issues
    
    # 获取 issue 详情
    issue_data = fetch_issue_detail(owner, repo, issue_number)
    
    if issue_data:
        # 提取需要的字段并添加到列表
        issue_summary = {
            'number': issue_data['number'],
            'title': issue_data['title'],
            'body': issue_data['body'],
            'state': issue_data['state'],
            'labels': [label['name'] for label in issue_data.get('labels', [])],
            'html_url': issue_data['html_url'],
            'created_at': issue_data['created_at'],
            'updated_at': issue_data['updated_at'],
            'closed_at': issue_data.get('closed_at'),
            'user': issue_data['user']['login'] if issue_data.get('user') else None
        }
        
        all_issues.append(issue_summary)
        print(f"> Issue #{issue_number} 已添加到列表")
    
    return all_issues


def process_config_links():
    """处理 config.yml 中配置的链接"""
    print('> 处理 config.yml 中的链接')
    for link in config.read('links'):
        print('> get: ', link)
        url = urlparse(link)
        req = requests.get(link, headers=headers)
        
        # 创建目录和保存文件
        root = 'v2'
        path = url.path
        if url.query:
            path = path + '?' + url.query
        dir_path = root + path + '/'
        file_path = dir_path + 'data.json'
        
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(json.loads(req.content.decode()), f, ensure_ascii=False, indent=2)


def main():
    # 加载已存在的 issue 数据
    all_issues = load_all_issues()
    print(f"> 已加载 {len(all_issues)} 个 issue")
    
    issue_info = get_triggered_issue()

    if issue_info:
        # 由 issue 事件触发
        print(f"> 由 Issue #{issue_info['number']} 触发")
        
        if not should_process_issue(issue_info):
            print("> Issue 条件不满足（需要同时满足：已关闭 + 有标签）")
            print("> 不执行任何操作，保持现有数据不变")
            return
        
        # 条件满足，处理该 issue
        print(f"> Issue 条件满足，开始处理")
        all_issues = process_issue(issue_info, all_issues)
        
        # 保存更新后的所有 issue
        save_all_issues(all_issues)
        print(f"> 总共保存了 {len(all_issues)} 个 issue")
        
    else:
        # 手动触发或非 Actions 环境
        print("> 手动触发或非 Actions 环境")
        process_config_links()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print('> exception: ', e)
        import traceback
        traceback.print_exc()

    print('\n> rate_limit: \n', requests.get('https://api.github.com/rate_limit', headers=headers).content.decode())
    print('> end')
