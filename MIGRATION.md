---
title: 电池监测软件迁移启动说明
date: 2026-11-18
tags: [电池监测, 软件迁移]
---

# 新电脑使用方法

1. 将迁移 ZIP 复制到新电脑，完整解压到一个新文件夹。不要覆盖以前复制过来的项目，不要把旧 `.venv` 或 `.migration-env` 搬进去。
2. 新电脑需要已安装 Anaconda 或 Miniconda（截图中终端的 base 通常说明已有）。首次安装需要联网下载 Python 和依赖。
3. 双击 `START.cmd`。脚本自动寻找 Conda，在当前文件夹创建 `.migration-env`，安装 requirements.txt 并检查依赖，然后打开软件。首次较慢，后续直接启动。
4. 若提示找不到 Conda，输入新电脑实际的 `Scripts\conda.exe` 完整路径。可在能使用 conda 的 VS Code 终端执行 `$env:CONDA_EXE` 查看。若为空，可在 Anaconda Prompt 执行 `where conda` 寻找 exe 路径。不要填写 MSYS2 的 python.exe。
5. 软件打开后重新选择数据文件；迁移包没有附带原始实验数据或旧电脑的 settings.json。

脚本只向此项目的独立环境安装包，不更新 base，不关闭已有 VS Code/Jupyter。运行期间请保留启动的控制台窗口。脚本的 ExecutionPolicy Bypass 仅限本次 PowerShell 进程，不修改系统执行策略。

## 在 VS Code 中运行

打开解压后的项目文件夹，选择菜单“终端 → 运行任务 → 电池监测：安装并启动”。它调用同一个脚本，不受右下角解释器选择或 MSYS2 Python 影响。

如需使用 Python 扩展右上角的运行按钮，先运行一次 START.cmd 完成安装，再执行“Python: Select Interpreter”，输入新文件夹内 `.migration-env\python.exe` 的完整路径。不要选择旧 `.venv` 或 MSYS2 Python。Conda 环境的 python.exe 不在 Scripts 子文件夹中。

此启动方案使用 START.cmd 或上述 VS Code 任务；旧版 setup.ps1/run.ps1 使用另外的 .venv 环境，不要混用。

## 再次迁移与错误处理

- 再搬电脑或更换项目目录时，重新解压原始 ZIP，然后运行 START.cmd。创建后的环境不可直接移动。
- 安装中网络失败：保留错误信息，恢复网络后再次运行 START.cmd。
- 本包是自动安装版，不是免 Python 的 EXE，也不是离线安装包。新电脑的完整安装与界面仍需在目标机器验证。
- 软件依赖：Python 3.12（含 Tk）、NumPy、SciPy、pandas、Matplotlib、openpyxl、xlrd。版本范围见 requirements.txt。正常绘图不需要联网。
