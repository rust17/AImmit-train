import subprocess
import os
import datasets

def run_git_command(command, cwd_path):
    """
    在指定目录下运行一个 Git 命令并返回其标准输出。
    如果命令执行出错，打印错误信息并返回 None。
    """
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore'  # 忽略解码错误，以防遇到非UTF-8字符
        )
        stdout, stderr = process.communicate()
        if stderr.strip():
            print(f"执行 Git 命令 '{' '.join(command)}' 时发生异常: {stderr.strip()}")
            return None
        return stdout.strip()
    except FileNotFoundError:
        print("错误：找不到 Git 命令。请确保 Git 已安装并在系统 PATH 中。")
        return None
    except Exception as e:
        print(f"执行 Git 命令 '{' '.join(command)}' 时发生异常: {e}")
        return None

def get_commit_data(repo_path, max_commits=None):
    """
    从指定的 Git 仓库路径提取 commit 数据。

    为每个非合并 commit 提取：
    - diff 信息
    - 完整的 commit message (主题 + 正文)

    参数:
    - repo_path (str): Git 仓库的本地路径。
    - max_commits (int, optional): 要提取的最大 commit 数量。默认为 None (提取所有)。

    返回:
    - list: 一个字典列表，每个字典包含 "diff" 和 "commit_message"。
    """
    dataset = []
    if not os.path.isdir(os.path.join(repo_path, ".git")):
        print(f"错误：路径 '{repo_path}' 不是一个有效的 Git 仓库。")
        return dataset

    # 1. 获取 commit 哈希、主题和正文
    # 使用 %H (哈希), %s (主题), %b (正文)，并用 \x00 (空字节) 分隔
    log_format = "%H%x00%s%x00%b%x00"
    git_log_command = ["git", "log", "--no-merges", f"--pretty=format:{log_format}"]
    if max_commits is not None and isinstance(max_commits, int) and max_commits > 0:
        git_log_command.append(f"-n {max_commits}")

    log_output = run_git_command(git_log_command, cwd_path=repo_path)
    if not log_output:
        print(f"未能从仓库 '{repo_path}' 获取到 commit 日志。")
        return dataset

    # commit 条目由 \x00 分隔。每个条目包含哈希、主题、正文。
    # 注意：正文本身可能包含换行符。
    commit_entries_raw = log_output.strip('\x00').split('\x00')

    num_fields_per_commit = 3 # 哈希, 主题, 正文

    for i in range(0, len(commit_entries_raw), num_fields_per_commit):
        commit_hash = commit_entries_raw[i].strip()
        subject = commit_entries_raw[i+1]
        body = commit_entries_raw[i+2].strip() if i + 2 < len(commit_entries_raw) else ""

        # 组合主题和正文，符合标准的 commit message 格式
        full_commit_message = subject
        if body: # 仅当正文非空时才添加
            full_commit_message += "\n\n" + body # 规范：主题和正文间通常空一行

        # 2. 获取该 commit 的 diff 信息
        # `git show --pretty=format:"" --patch <hash>` 只输出 patch 内容
        # 这能较好地处理初始 commit 的情况。
        git_diff_command = ["git", "show", "--pretty=format:\"\"", "--patch", commit_hash]
        diff_output = run_git_command(git_diff_command, cwd_path=repo_path)

        if len(diff_output) > 5000:  # 如果 diff 输出超过 32KB，跳过
            continue

        # if diff_output is not None: # diff_output 可能是空字符串（例如，空提交或仅修改消息）
        dataset.append({
            "diff": diff_output,
            "commit_message": full_commit_message.strip(), # 确保最终消息也去除首尾空白
        })

    return dataset

if __name__ == "__main__":
    actual_repo_path = "/home/circle/code/ollama"

    if actual_repo_path:
        print(f"\n正在从仓库 '{os.path.abspath(actual_repo_path)}' 提取数据...")
        # 为了演示，只提取少量 commit，移除 max_commits 以获取所有数据
        dataset = get_commit_data(actual_repo_path, max_commits=500)

        if dataset:
            print(f"\n成功提取 {len(dataset)} 条 commit 数据。\n")
            for i, entry in enumerate(dataset):
                print(f"--- 数据条目 {i+1} ---")
                print("Commit Message:")
                print(entry["commit_message"])
                print("\nDiff:")
                print(entry["diff"])
                print("----------------------\n")
            ds = datasets.Dataset.from_list(dataset)
            ds.save_to_disk("/home/circle/code/AImmit_ai/dataset_generation")
        else:
            print(f"未能从仓库 '{os.path.abspath(actual_repo_path)}' 提取到数据。请检查仓库是否有效且包含 commit。")
