# @file test_logger_setup.py
# @brief LogManager 单元测试：验证视觉/TCP 日志隔离落盘与控制台开关。

import logging
import logging.handlers
import os
import sys
import tempfile
import unittest

# 将 src 加入 path，复刻 main.py 的运行期导入方式
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from logger_setup import LogManager


class TestLogManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # 清空全局日志状态，避免用例间串扰
        root = logging.getLogger()
        for h in list(root.handlers):
            root.removeHandler(h)
        root.setLevel(logging.WARNING)
        tcp = logging.getLogger("tcp_comm")
        for h in list(tcp.handlers):
            tcp.removeHandler(h)
        tcp.propagate = True

    def tearDown(self):
        # 还原全局日志状态，避免污染其它测试套件
        root = logging.getLogger()
        for h in list(root.handlers):
            root.removeHandler(h)
        tcp = logging.getLogger("tcp_comm")
        for h in list(tcp.handlers):
            tcp.removeHandler(h)
        tcp.propagate = True

    def _make(self, console=False, level="INFO"):
        return LogManager(
            log_level=level, output_dir=self.tmp,
            vision_file="vision.log", tcp_file="tcp.log",
            max_bytes=1024, backup_count=3, console_enable=console)

    def test_setup_creates_both_log_files(self):
        # 建连后 vision.log 与 tcp.log 均生成（验收 #1）
        self._make().setup()
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "vision.log")))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "tcp.log")))

    def test_tcp_logger_isolated_from_vision(self):
        # tcp_comm 日志只进 tcp.log，绝不污染 vision.log（验收 #2/#3）
        self._make().setup()
        tcp = logging.getLogger("tcp_comm")
        self.assertFalse(tcp.propagate)
        tcp.info("comm-line")
        for h in tcp.handlers:
            h.flush()
        with open(os.path.join(self.tmp, "tcp.log"), encoding="utf-8") as f:
            self.assertIn("comm-line", f.read())
        with open(os.path.join(self.tmp, "vision.log"), encoding="utf-8") as f:
            self.assertNotIn("comm-line", f.read())

    def test_console_disabled_by_default(self):
        # 默认不向控制台输出：根节点仅 vision_handler（验收 #4）
        self._make(console=False).setup()
        root = logging.getLogger()
        self.assertEqual(len(root.handlers), 1)
        self.assertIsInstance(root.handlers[0], logging.handlers.RotatingFileHandler)

    def test_console_enabled_adds_stream_handler(self):
        # 开启控制台：根节点追加 StreamHandler
        self._make(console=True).setup()
        root = logging.getLogger()
        self.assertEqual(len(root.handlers), 2)

    def test_invalid_level_raises(self):
        # 非法级别直接抛异常暴露，不写兜底
        with self.assertRaises(AttributeError):
            self._make(level="NOTALEVEL").setup()


if __name__ == "__main__":
    unittest.main()
