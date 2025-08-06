import os
import re
# 配置参数
# 包含下载链接的Python代码文件
download_list_file = r'D:\lzp\des\download-all-2025-08-01_02-43-26.py'
# 本地已下载数据存放路径
local_folder = r'F:\DES\62'
 # 输出：待下载链接
output_file = r'D:\lzp\des\\needtoDownload.txt'
# 创建快捷方式的目标文件夹
symlink_folder = r'F:\lzpdes'
def extract_links_from_code(file_path):
    """
    从包含 self.files = [ "https://...", ... ] 的 Python 文件中提取所有 .zip 下载链接
    支持跨行、缩进、双引号
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='latin1') as f:
            content = f.read()

    # 移除换行和多余空格，把多行合并成一行（便于匹配）
    # 保留引号和完整 URL
    one_line = re.sub(r'\s+', ' ', content)  # 所有空白字符替换为空格
    one_line = one_line.strip()

    # 匹配 self.files = [ ... ] 中的所有 "https://...zip"
    # 支持中间有空格、换行、缩进
    pattern = r'["\']https://[^\s"\']+\.zip["\']'
    matches = re.findall(pattern, one_line)

    # 去掉引号
    links = [m.strip(' "\'') for m in matches]
    return list(set(links))  # 去重


# 主逻辑
if __name__ == "__main__":
    # 提取所有下载链接
    all_download_links = extract_links_from_code(download_list_file)

    # 提取远程文件名 -> 链接 的映射
    remote_filenames = {os.path.basename(link): link for link in all_download_links}

    # 获取本地已存在的 zip 文件名（仅 .zip）
    if not os.path.exists(local_folder):
        os.makedirs(local_folder)
    local_files = set(os.listdir(local_folder))

    # 创建快捷方式的目录
    os.makedirs(symlink_folder, exist_ok=True)

    # 分类：已存在 和 需要下载
    missing_links = []
    existing_count = 0

    for filename, link in remote_filenames.items():
        if filename in local_files:
            # 已存在，创建快捷方式
            src_path = os.path.join(os.path.abspath(local_folder), filename)
            dst_link = os.path.join(symlink_folder, filename)
            # 替换原来的 os.symlink(...) 为 os.link(...)（硬链接）
            try:
                if os.path.exists(dst_link):
                    os.remove(dst_link)
                os.link(src_path, dst_link)  # 创建硬链接
                print(f"✅ 已创建硬链接: {dst_link}")
            except Exception as e:
                print(f"❌ 创建硬链接失败 {dst_link}: {e}")
            existing_count += 1
        else:
            # 未下载
            missing_links.append(link)

    # 写入需要下载的列表
    with open(output_file, 'w', encoding='utf-8') as f:
        for link in missing_links:
            f.write(link + '\n')

    # 输出结果
    print("\n任务完成！")
    print(f"总共链接数: {len(all_download_links)}")
    print(f"已存在并创建快捷方式: {existing_count} 个 -> 存放于 '{symlink_folder}'")
    print(f"尚未下载: {len(missing_links)} 个 -> 已写入 '{output_file}'")