# Tile Downloader App

一个用于下载并拼接 OpenSeadragon / Deep Zoom 瓦片图片的 Windows 桌面应用（PySide6 GUI）。

## 1. 安装运行依赖

```bash
pip install -r requirements.txt
```

## 2. 运行

```bash
python main.py
```

## 3. 一键补齐环境并打包 EXE（Windows）

### 方式 A：双击脚本（推荐）

- `build_exe.bat`（cmd）
- `build_exe.ps1`（PowerShell）

脚本会自动：

1. 升级 `pip`
2. 安装 `requirements-build.txt`（包含运行依赖 + PyInstaller）
3. 输出单文件 GUI 程序 `dist/TileDownloader.exe`

### 方式 B：手动命令

```bash
pip install -r requirements-build.txt
pyinstaller --noconfirm --clean --onefile --windowed --name TileDownloader main.py
```

生成结果：`dist/TileDownloader.exe`


## 4. 示例参数

- base_url:  
  `https://shuziwenwu-1259446244.cos.ap-beijing.myqcloud.com/relic/2011048128297697280/image-bundle`
- level: `13`
- x: `0-5`
- y: `0-9`
- ext: `png`

## 功能说明

- 按规则生成瓦片地址：`{base_url}/{level}/{x}_{y}.{ext}`
- 使用 `requests` 下载瓦片，并设置：
  - `User-Agent: Mozilla/5.0`
  - `Referer: https://digicol.dpm.org.cn/`
- 下载失败不会中断任务，缺失瓦片会以黑色块补位。
- 自动识别瓦片尺寸，支持最后一行/列尺寸不一致。
- 拼接时按“每列最大宽度 + 每行最大高度”计算位置。
- 下载缓存保存在输出目录下的 `tiles/` 文件夹，重复运行优先读取缓存。
- 下载过程在 `QThread` 中执行，界面不会卡死。
