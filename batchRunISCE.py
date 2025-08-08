import os
import subprocess
from threading import Thread
import psutil
import time
import argparse

# 获取当前CPU和内存使用率，并包含错误处理
def get_system_usage():
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        return cpu_percent, memory_percent
    except Exception as e:
        print(f"Error getting system usage: {e}")
        return None, None

# 检查是否可以添加更多任务
def can_add_task():
    cpu_percent, memory_percent = get_system_usage()
    if cpu_percent is None or memory_percent is None:
        # 如果获取系统资源失败，默认不允许添加新任务
        return False
    # 如果CPU和内存使用均低于70%，则可以添加新任务
    if cpu_percent < 70 and memory_percent < 70:
        return True
    return False

# 执行单个命令，并包含错误处理
def execute_command(command):
    try:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print(f"Command failed with error: {stderr.decode()}")
    except Exception as e:
        print(f"Failed to execute command '{command}': {e}")

# 解析命令行参数
parser = argparse.ArgumentParser(description="Parallel execution of ISCE InSAR unwrap commands.")
parser.add_argument('path', type=str, help='Path to the run_11_unwrap.txt file containing unwrap commands.')

args = parser.parse_args()

# 从文件中读取命令，并包含错误处理
commands_file_path = args.path
if not os.path.isfile(commands_file_path):
    print(f"Error: The file {commands_file_path} does not exist.")
    exit(1)

try:
    with open(commands_file_path, 'r') as file:
        commands = file.readlines()
except IOError as e:
    print(f"Error reading file {commands_file_path}: {e}")
    exit(1)

running_processes = []
for command in commands:
    command = command.strip()  # 移除行末空白字符
    while not can_add_task() or len(running_processes) >= 5:  # 控制同时运行的任务数不超过5个
        running_processes = [proc for proc in running_processes if proc.is_alive()]  # 更新正在运行的任务列表
        time.sleep(2)  # 等待一段时间后重试

    # 创建并启动新线程来执行命令
    thread = Thread(target=execute_command, args=(command,))
    try:
        thread.start()
        running_processes.append(thread)
        # --- 新增：打印当前并行任务数量 ---
        print(f"已启动新任务: {command}")
        print(f"当前正在并行计算的任务数量: {len(running_processes)}")
        # ---
    except RuntimeError as e:
        print(f"Failed to start thread for command '{command}': {e}")

# 等待所有任务完成
for proc in running_processes:
    try:
        proc.join()
    except RuntimeError as e:
        print(f"Thread join failed: {e}")

print("所有解缠任务已完成。")