# Switch Remote Control — sys-botbase GUI Client

一个基于 Python + customtkinter 的桌面客户端，用于通过 [sys-botbase](https://github.com/olliz0r/sys-botbase) 远程控制运行自制系统 (CFW) 的 Nintendo Switch。

## 功能概览

| 标签页 | 功能 |
|--------|------|
| **设置与连接** | 手动输入 IP 连接、局域网自动扫描 (端口 6000)、查看 Switch 信息、配置 sys-botbase 参数 |
| **控制器** | 模拟全部按键 (A/B/X/Y/L/R/ZL/ZR/±/HOME/CAPTURE)、十字键、左右摇杆 (可视化拖拽)、Detach |
| **内存工具** | Peek (Heap/Absolute/Main)、Poke 写入、指针链读取、Freeze/UnFreeze 管理 |
| **屏幕捕捉** | 截取 Switch 当前画面 (pixelPeek → JPG)、自动刷新、保存到本地 |
| **宏序列** | 编辑/执行 clickSeq 宏、预设模板、快速按键构建器、循环执行、保存/加载宏文件 |

## 前提条件

1. **Nintendo Switch** 已安装 [Atmosphère](https://github.com/Atmosphere-NX/Atmosphere) CFW
2. **sys-botbase** 已安装到 `sd:/atmosphere/contents/` 并重启
   - 安装成功标志：底座上的 Joy-Con HOME 键会发光
3. Switch 和 Windows 电脑处于 **同一局域网**
4. **Python 3.10+**（Windows 安装版自带 tkinter）

## 安装与运行

```bash
# 1. 克隆或下载项目
git clone <repo-url>
cd remote-switch-stats

# 2. 创建虚拟环境
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动
python main.py
```

## 打包为 Windows .exe

### 方式一：一键打包（推荐，零基础可用）

直接双击 `build_windows.bat`，脚本会自动完成全部流程：

1. 检测 Python 是否已安装，版本是否 >= 3.10
2. 检测 tkinter 是否可用
3. 创建虚拟环境 `.venv`
4. 安装所有项目依赖 + PyInstaller
5. 执行打包
6. 询问是否立即运行

> 如果电脑上还没有 Python，脚本会提示你去
> [python.org](https://www.python.org/downloads/) 下载安装，
> **安装时务必勾选 "Add Python to PATH" 和 "tcl/tk and IDLE"**。

### 方式二：手动打包

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
python build.py              # 单文件模式 → dist\SwitchRemote.exe
python build.py --onedir     # 文件夹模式 → dist\SwitchRemote\（启动更快）
```

生成的 `dist\SwitchRemote.exe` 可复制到任意 Windows 电脑运行，无需安装 Python。

## 项目结构

```
├── main.py                      # 入口文件
├── requirements.txt             # Python 依赖
├── src/
│   ├── app.py                   # 主窗口 & 标签页布局
│   ├── protocol.py              # sys-botbase TCP 协议封装
│   ├── scanner.py               # 局域网扫描器
│   ├── views/
│   │   ├── setup_view.py        # 设置与连接页面
│   │   ├── controller_view.py   # 控制器模拟页面
│   │   ├── memory_view.py       # 内存工具页面
│   │   ├── screen_view.py       # 屏幕捕捉页面
│   │   └── macro_view.py        # 宏序列页面
│   └── widgets/
│       ├── status_bar.py        # 底部状态栏
│       ├── joystick.py          # 虚拟摇杆组件
│       └── dpad.py              # 虚拟十字键组件
```

## sys-botbase 指令参考

所有指令以 ASCII 文本发送，`\r\n` 结尾，响应以 `\n` 结尾。

### 控制器

| 指令 | 说明 | 示例 |
|------|------|------|
| `click <button>` | 按下并释放按键 | `click A` |
| `press <button>` | 按住按键 | `press B` |
| `release <button>` | 释放按键 | `release B` |
| `setStick <L/R> <X> <Y>` | 设置摇杆位置 (-0x8000 ~ 0x7FFF) | `setStick LEFT 0x7FFF 0x0` |
| `clickSeq <seq>` | 按键序列 (逗号分隔) | `clickSeq A,W500,B` |
| `detachController` | 分离虚拟控制器 | |

### 内存

| 指令 | 说明 |
|------|------|
| `peek <addr> <size>` | 读取 Heap 相对地址 |
| `peekAbsolute <addr> <size>` | 读取绝对地址 |
| `peekMain <addr> <size>` | 读取 Main NSO 相对地址 |
| `poke <addr> <hex>` | 写入 Heap 相对地址 |
| `freeze <addr> <hex>` | 冻结内存值 |
| `pointerPeek <size> <jumps...>` | 指针链读取 |

### 屏幕 & 工具

| 指令 | 说明 |
|------|------|
| `pixelPeek` | 截取当前画面 (JPG) |
| `getTitleID` | 当前运行的 Title ID |
| `getVersion` | sys-botbase 版本 |
| `configure <key> <value>` | 修改运行参数 |

## 许可声明

本项目仅供学习和自动化开发使用。使用者需自行承担由此产生的任何风险。
