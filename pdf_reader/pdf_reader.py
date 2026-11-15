import sys
import os
import pymupdf as fitz

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPixmap, QKeyEvent, QMouseEvent, QImage


# ========== 配置区 ==========
WINDOW_WIDTH  = 800
WINDOW_HEIGHT = 300
PDF_PRIMARY   = r"1.pdf"   # p 键回到这里
PDF_SECONDARY = r"2.pdf"   # g 键切到这里

# 高清渲染倍率
RENDER_SCALE  = 2.0

# 窗口透明度：0.0 = 全透明，1.0 = 完全不透明
WINDOW_OPACITY = 0.7
# =============================


class PDFReader(QWidget):
    def __init__(self, primary_path, secondary_path):
        super().__init__()

        # 窗口设置：无边框 + 固定尺寸 + 透明背景
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint  # 置顶，方便半透明时看后面内容
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setWindowOpacity(WINDOW_OPACITY)

        # PDF 文档
        self.docs = []
        self.doc_names = [primary_path, secondary_path]
        for path in [primary_path, secondary_path]:
            if path and os.path.exists(path):
                self.docs.append(fitz.open(path))
            else:
                self.docs.append(None)

        self.current_doc = 0
        self.page_index = [0, 0]
        self.scroll_y   = [0.0, 0.0]

        # 渲染缓存
        self._cached_pixmap = None
        self._cached_page   = -1
        self._cached_doc    = -1
        self._cached_size   = (0, 0)

        self._scale = 1.0

        # 鼠标拖动窗口
        self._drag_pos = None

        self._recalc_scale()
        self._render_page()

    # ========== 缩放计算 ==========
    def _recalc_scale(self):
        doc = self.docs[self.current_doc]
        if not doc:
            self._scale = 1.0
            return
        page = doc[self.page_index[self.current_doc]]
        base = self.width() / page.rect.width
        dpr = self.devicePixelRatioF()
        self._scale = base * dpr * RENDER_SCALE

    # ========== 渲染 ==========
    def _render_page(self):
        doc_idx = self.current_doc
        doc = self.docs[doc_idx]
        if not doc:
            self._cached_pixmap = None
            self.update()
            return

        page_num = self.page_index[doc_idx]
        page = doc[page_num]
        win_w, win_h = self.width(), self.height()

        if (self._cached_doc == doc_idx and
            self._cached_page == page_num and
            self._cached_size == (win_w, win_h) and
            self._cached_pixmap is not None):
            return

        matrix = fitz.Matrix(self._scale, self._scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False, colorspace="rgb")

        image = QImage(pix.samples, pix.width, pix.height,
                       pix.stride, QImage.Format.Format_RGB888)
        pm = QPixmap.fromImage(image)

        display_w = win_w
        display_h = int(page.rect.height * (win_w / page.rect.width))
        self._cached_pixmap = pm.scaled(
            display_w, display_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self._cached_page = page_num
        self._cached_doc  = doc_idx
        self._cached_size = (win_w, win_h)
        self.update()

    # ========== 绘制 ==========
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 半透明背景（比 setWindowOpacity 更精细的控制）
        painter.setOpacity(1.0)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)

        if self._cached_pixmap is None or self._cached_pixmap.isNull():
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "无文档 / 文档加载失败")
            return

        pm = self._cached_pixmap
        pm_w, pm_h = pm.width(), pm.height()

        offset_x = 0

        max_scroll = max(0, pm_h - self.height())
        sy = self.scroll_y[self.current_doc]
        sy = max(0, min(sy, max_scroll))
        self.scroll_y[self.current_doc] = sy

        offset_y = -int(sy)

        painter.drawPixmap(offset_x, offset_y, pm)

        # 滚动条指示
        if max_scroll > 0:
            bar_h = max(30, int(self.height() * self.height() / pm_h))
            bar_y = int(sy / max_scroll * (self.height() - bar_h))
            painter.fillRect(self.width() - 8, bar_y, 6, bar_h,
                             Qt.GlobalColor.darkGray)

    # ========== 滚动 ==========
    def _scroll_up(self, step=80):
        doc = self.docs[self.current_doc]
        if not doc:
            return
        page_num = self.page_index[self.current_doc]
        page = doc[page_num]
        pm_h = int(page.rect.height * (self.width() / page.rect.width))

        self.scroll_y[self.current_doc] -= step

        if self.scroll_y[self.current_doc] < 0:
            if page_num > 0:
                self.page_index[self.current_doc] -= 1
                self._recalc_scale()
                page = doc[self.page_index[self.current_doc]]
                pm_h = int(page.rect.height * (self.width() / page.rect.width))
                self.scroll_y[self.current_doc] = max(0, pm_h - self.height())
                self._cached_pixmap = None
                self._render_page()
            else:
                self.scroll_y[self.current_doc] = 0
                self.update()
        else:
            self.update()

    def _scroll_down(self, step=80):
        doc = self.docs[self.current_doc]
        if not doc:
            return
        page_num = self.page_index[self.current_doc]
        page = doc[page_num]
        pm_h = int(page.rect.height * (self.width() / page.rect.width))

        self.scroll_y[self.current_doc] += step

        if self.scroll_y[self.current_doc] > max(0, pm_h - self.height()):
            if page_num < len(doc) - 1:
                self.page_index[self.current_doc] += 1
                self.scroll_y[self.current_doc] = 0
                self._recalc_scale()
                self._cached_pixmap = None
                self._render_page()
            else:
                self.scroll_y[self.current_doc] = max(0, pm_h - self.height())
                self.update()
        else:
            self.update()

    # ========== 键盘 ==========
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()

        if key == Qt.Key.Key_Q:
            self.close()

        elif key == Qt.Key.Key_G:
            if self.docs[1] is not None:
                self.current_doc = 1
                self._recalc_scale()
                self.scroll_y[self.current_doc] = 0
                self._cached_pixmap = None
                self._render_page()

        elif key == Qt.Key.Key_P:
            if self.docs[0] is not None:
                self.current_doc = 0
                self._recalc_scale()
                self.scroll_y[self.current_doc] = 0
                self._cached_pixmap = None
                self._render_page()

        elif key == Qt.Key.Key_Up:
            self._scroll_up(80)

        elif key == Qt.Key.Key_Down:
            self._scroll_down(80)

        # 透明度调节：[ / ] 键
        elif key == Qt.Key.Key_BracketLeft:
            new_opacity = max(0.1, self.windowOpacity() - 0.1)
            self.setWindowOpacity(new_opacity)

        elif key == Qt.Key.Key_BracketRight:
            new_opacity = min(1.0, self.windowOpacity() + 0.1)
            self.setWindowOpacity(new_opacity)

    # ========== 鼠标拖动窗口 ==========
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None


# ========== 入口 ==========
if __name__ == "__main__":
    app = QApplication(sys.argv)

    if len(sys.argv) >= 3:
        primary   = sys.argv[1]
        secondary = sys.argv[2]
    elif len(sys.argv) == 2:
        primary   = sys.argv[1]
        secondary = PDF_SECONDARY
    else:
        primary   = PDF_PRIMARY
        secondary = PDF_SECONDARY

    window = PDFReader(primary, secondary)
    window.show()
    sys.exit(app.exec())
