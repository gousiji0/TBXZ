import os
import sys
from dataclasses import dataclass
from typing import Dict, Tuple, Optional

import requests
from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


@dataclass
class JobConfig:
    base_url: str
    level: int
    x_start: int
    x_end: int
    y_start: int
    y_end: int
    ext: str
    output_dir: str
    output_name: str


class TileWorker(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    done_signal = Signal(str)
    error_signal = Signal(str)

    def __init__(self, config: JobConfig):
        super().__init__()
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://digicol.dpm.org.cn/",
            }
        )

    def run(self) -> None:
        try:
            output_path = self.download_and_merge()
            self.done_signal.emit(output_path)
        except Exception as exc:  # 顶层兜底，防止线程静默退出
            self.error_signal.emit(f"任务失败：{exc}")

    def build_tile_url(self, x: int, y: int) -> str:
        return f"{self.config.base_url}/{self.config.level}/{x}_{y}.{self.config.ext}"

    def tile_cache_path(self, cache_dir: str, x: int, y: int) -> str:
        return os.path.join(cache_dir, f"{self.config.level}_{x}_{y}.{self.config.ext}")

    def fetch_tile(self, url: str, cache_path: str) -> Optional[Image.Image]:
        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            with open(cache_path, "wb") as f:
                f.write(response.content)
            return Image.open(cache_path).convert("RGB")
        except Exception as exc:
            self.log_signal.emit(f"下载失败：{url}，原因：{exc}")
            return None

    def read_or_download_tile(self, cache_dir: str, x: int, y: int) -> Optional[Image.Image]:
        cache_path = self.tile_cache_path(cache_dir, x, y)
        if os.path.exists(cache_path):
            try:
                self.log_signal.emit(f"读取缓存 {x}_{y}.{self.config.ext}")
                return Image.open(cache_path).convert("RGB")
            except Exception as exc:
                self.log_signal.emit(f"缓存损坏，重新下载 {x}_{y}.{self.config.ext}：{exc}")

        tile_url = self.build_tile_url(x, y)
        self.log_signal.emit(f"正在下载 {x}_{y}.{self.config.ext}")
        return self.fetch_tile(tile_url, cache_path)

    def download_and_merge(self) -> str:
        cfg = self.config
        os.makedirs(cfg.output_dir, exist_ok=True)
        cache_dir = os.path.join(cfg.output_dir, "tiles")
        os.makedirs(cache_dir, exist_ok=True)

        x_values = list(range(cfg.x_start, cfg.x_end + 1))
        y_values = list(range(cfg.y_start, cfg.y_end + 1))
        total = len(x_values) * len(y_values)

        tiles: Dict[Tuple[int, int], Optional[Image.Image]] = {}
        finished = 0

        # 先下载全部瓦片（或读取缓存）
        for y in y_values:
            for x in x_values:
                tiles[(x, y)] = self.read_or_download_tile(cache_dir, x, y)
                finished += 1
                self.progress_signal.emit(int(finished * 100 / total))

        self.log_signal.emit("下载完成")

        # 自动检测尺寸，支持边缘瓦片尺寸不一致
        col_widths = {x: 0 for x in x_values}
        row_heights = {y: 0 for y in y_values}
        default_w, default_h = 256, 256

        # 找一张成功图片作为默认黑块尺寸
        for img in tiles.values():
            if img is not None:
                default_w, default_h = img.size
                break

        for y in y_values:
            for x in x_values:
                img = tiles[(x, y)]
                if img is not None:
                    w, h = img.size
                    col_widths[x] = max(col_widths[x], w)
                    row_heights[y] = max(row_heights[y], h)

        # 若某整列或整行都失败，则退回默认尺寸
        for x in x_values:
            if col_widths[x] == 0:
                col_widths[x] = default_w
        for y in y_values:
            if row_heights[y] == 0:
                row_heights[y] = default_h

        total_width = sum(col_widths[x] for x in x_values)
        total_height = sum(row_heights[y] for y in y_values)

        self.log_signal.emit("正在拼接")
        canvas = Image.new("RGB", (total_width, total_height), (0, 0, 0))

        y_offset = 0
        for y in y_values:
            x_offset = 0
            for x in x_values:
                img = tiles[(x, y)]
                if img is None:
                    # 缺失瓦片用黑色块补位，块大小按该格实际目标尺寸
                    img = Image.new("RGB", (col_widths[x], row_heights[y]), (0, 0, 0))
                canvas.paste(img, (x_offset, y_offset))
                x_offset += col_widths[x]
            y_offset += row_heights[y]

        output_path = os.path.join(cfg.output_dir, cfg.output_name)
        canvas.save(output_path, format="PNG")
        self.log_signal.emit("导出完成")
        return output_path


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tile Downloader & Merger")
        self.resize(850, 650)
        self.worker: Optional[TileWorker] = None

        self.base_url_input = QLineEdit(
            "https://shuziwenwu-1259446244.cos.ap-beijing.myqcloud.com/relic/2011048128297697280/image-bundle"
        )
        self.level_input = QLineEdit("13")
        self.x_start_input = QLineEdit("0")
        self.x_end_input = QLineEdit("5")
        self.y_start_input = QLineEdit("0")
        self.y_end_input = QLineEdit("9")
        self.ext_input = QLineEdit("png")
        self.output_name_input = QLineEdit("merged_image.png")
        self.output_dir_input = QLineEdit(os.getcwd())

        self.select_dir_btn = QPushButton("选择输出目录")
        self.start_btn = QPushButton("开始下载并拼接")

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        self.init_ui()
        self.bind_events()

    def init_ui(self) -> None:
        form = QFormLayout()
        form.addRow("base_url", self.base_url_input)
        form.addRow("level", self.level_input)
        form.addRow("起始 x", self.x_start_input)
        form.addRow("结束 x", self.x_end_input)
        form.addRow("起始 y", self.y_start_input)
        form.addRow("结束 y", self.y_end_input)
        form.addRow("图片格式", self.ext_input)
        form.addRow("输出文件名", self.output_name_input)

        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.output_dir_input)
        dir_layout.addWidget(self.select_dir_btn)
        form.addRow("输出目录", dir_layout)

        form.addRow(self.start_btn)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(QLabel("日志"))
        layout.addWidget(self.log_output)
        layout.addWidget(self.progress_bar)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def bind_events(self) -> None:
        self.select_dir_btn.clicked.connect(self.select_output_dir)
        self.start_btn.clicked.connect(self.start_task)

    def select_output_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_dir_input.text())
        if selected:
            self.output_dir_input.setText(selected)

    def append_log(self, text: str) -> None:
        self.log_output.append(text)

    def parse_config(self) -> JobConfig:
        try:
            level = int(self.level_input.text().strip())
            x_start = int(self.x_start_input.text().strip())
            x_end = int(self.x_end_input.text().strip())
            y_start = int(self.y_start_input.text().strip())
            y_end = int(self.y_end_input.text().strip())
        except ValueError as exc:
            raise ValueError("level/x/y 必须是整数") from exc

        if x_start > x_end or y_start > y_end:
            raise ValueError("起始坐标不能大于结束坐标")

        output_name = self.output_name_input.text().strip()
        if not output_name:
            raise ValueError("输出文件名不能为空")

        if not output_name.lower().endswith(".png"):
            output_name += ".png"

        return JobConfig(
            base_url=self.base_url_input.text().strip().rstrip("/"),
            level=level,
            x_start=x_start,
            x_end=x_end,
            y_start=y_start,
            y_end=y_end,
            ext=self.ext_input.text().strip().lstrip("."),
            output_dir=self.output_dir_input.text().strip(),
            output_name=output_name,
        )

    def start_task(self) -> None:
        try:
            cfg = self.parse_config()
        except Exception as exc:
            QMessageBox.critical(self, "参数错误", str(exc))
            return

        self.progress_bar.setValue(0)
        self.log_output.clear()
        self.start_btn.setEnabled(False)
        self.append_log("任务开始")

        self.worker = TileWorker(cfg)
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.done_signal.connect(self.on_done)
        self.worker.error_signal.connect(self.on_error)
        self.worker.start()

    def on_done(self, output_path: str) -> None:
        self.append_log(f"任务完成：{output_path}")
        self.start_btn.setEnabled(True)
        QMessageBox.information(self, "完成", f"导出完成：\n{output_path}")

    def on_error(self, message: str) -> None:
        self.append_log(message)
        self.start_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
