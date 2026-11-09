# @file test_tcp_comm.py
# @brief tcp_comm.py 单元测试：覆盖 A3 帧编解码与 A1 连接/重连的全部分支，目标分支覆盖率 100%。
#
# @details 仅测试通信层新增逻辑，不依赖 vision_core / config_loader；TcpComm 以显式入参
#          构造，socket 收发由 FakeConn + monkeypatch 注入，避免真实网络阻塞。

import os
import sys
import socket
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from unittest import mock  # noqa: E402
import tcp_comm  # noqa: E402
from tcp_comm import TcpComm, FrameDecoder, FrameStats  # noqa: E402


# ---------------------------------------------------------------------------
# 测试夹具：构造器与假连接
# ---------------------------------------------------------------------------

def make_comm(**kw) -> TcpComm:
    """按默认值构造 TcpComm，kw 覆盖任意入参。"""
    base = dict(
        host="127.0.0.1",
        port=9,
        reconnect_backoff=[1, 2, 4, 8, 16, 30],
        connect_timeout=0.1,
        recv_poll_timeout=0.1,
        recv_buffer_size=4096,
        heartbeat_interval=3.0,
        periodic_type="periodic",
        camera_ids=["CAM1", "CAM2", "CAM3", "CAM4", "CAM5", "CAM6", "CAM7", "CAM8"],
        camera_status=["ok", "ok", "ok", "ok", "ok", "ok", "ok", "ok"],
        on_message=None,
        known_types=frozenset(["recognize", "version_query"]),
        max_frame_bytes=1048576,
        drop_log_head_bytes=8,
        dedup_types=["recognize"],
        dedup_cache_ttl=60.0,
        async_handlers={},
        offline_cache_max=100,
    )
    base.update(kw)
    return TcpComm(**base)


class FakeConn:
    """模拟已建连 socket：按序列回放 recv 结果，记录 sendall / close。"""

    def __init__(self, recv_seq=None, close_raises=False):
        self._recv = list(recv_seq or [])
        self._close_raises = close_raises
        self._closed = False
        self._sent = []
        self.settimeout_calls = 0

    def settimeout(self, t):
        self.settimeout_calls += 1

    def recv(self, bufsize):
        if self._recv:
            v = self._recv.pop(0)
            if isinstance(v, BaseException) or (
                isinstance(v, type) and issubclass(v, BaseException)
            ):
                raise v
            return v
        # 默认触发读超时分支（continue）
        raise socket.timeout("timed out")

    def sendall(self, data):
        self._sent.append(data)

    def close(self):
        self._closed = True
        if self._close_raises:
            raise OSError("close fail")


# ---------------------------------------------------------------------------
# A3：帧编解码器（FrameDecoder）分支覆盖
# ---------------------------------------------------------------------------

class TestFrameDecoder(unittest.TestCase):
    def setUp(self):
        # 小上限便于触发超长分支
        self.d = FrameDecoder(
            max_frame_bytes=20,
            known_types=frozenset(["recognize", "version_query"]),
            drop_log_head_bytes=8,
        )

    def _feed(self, data: bytes):
        return self.d.feed(data)

    def test_valid_frame(self):
        out = self._feed(b'{"type":"recognize"}\n')
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["type"], "recognize")
        s = self.d.get_stats()
        self.assertEqual(s.frames_ok, 1)
        self.assertEqual(s.recv_bytes, len(b'{"type":"recognize"}\n'))

    def test_sticky_frames(self):
        # 粘包：单批含两帧，需足够容量（本用例不测超长，故放大上限）
        d = FrameDecoder(100, frozenset(["recognize", "version_query"]), 8)
        out = d.feed(b'{"type":"recognize"}\n{"type":"version_query"}\n')
        self.assertEqual([m["type"] for m in out], ["recognize", "version_query"])

    def test_half_frame(self):
        # 半包：先收无换行，再收换行补齐（覆盖 nl==-1 且不超长的 break 分支）
        self.assertEqual(self._feed(b'{"type":"recognize"}'), [])
        self.assertEqual([m["type"] for m in self._feed(b'\n')], ["recognize"])

    def test_empty_line(self):
        # 空行：跳过且不计数（覆盖 _process_line 空行分支与 _feed_data 的 msg is None 分支）
        out = self._feed(b'\n')
        self.assertEqual(out, [])
        self.assertEqual(self.d.get_stats().drop_unknown_type, 0)

    def test_invalid_utf8(self):
        # 覆盖 decode 的 UnicodeDecodeError 分支
        out = self._feed(b'\xff\n')
        self.assertEqual(out, [])
        self.assertEqual(self.d.get_stats().drop_invalid_json, 1)

    def test_invalid_json(self):
        # 覆盖 json.loads 的 JSONDecodeError 分支
        out = self._feed(b'notjson\n')
        self.assertEqual(out, [])
        self.assertEqual(self.d.get_stats().drop_invalid_json, 1)

    def test_non_dict(self):
        # 覆盖 isinstance dict 的非 dict 分支
        out = self._feed(b'[1,2,3]\n')
        self.assertEqual(out, [])
        self.assertEqual(self.d.get_stats().drop_non_dict, 1)

    def test_unknown_type(self):
        # 覆盖 ftype 不在白名单分支（命中但未在 known_types）
        out = self._feed(b'{"type":"hack"}\n')
        self.assertEqual(out, [])
        self.assertEqual(self.d.get_stats().drop_unknown_type, 1)

    def test_missing_type(self):
        # 覆盖 ftype 缺失（None 不在白名单）分支
        out = self._feed(b'{"foo":1}\n')
        self.assertEqual(out, [])
        self.assertEqual(self.d.get_stats().drop_unknown_type, 1)

    def test_oversize_line(self):
        # 单帧整行超长（含 \n）：行超限分支
        big = b'x' * 30 + b'\n'
        out = self._feed(big)
        self.assertEqual(out, [])
        self.assertEqual(self.d.get_stats().drop_oversize, 1)

    def test_oversize_no_nl_then_recover(self):
        # 超长且无换行：进入丢弃态（nl==-1 且 buffer 超限 -> 丢弃）
        out1 = self._feed(b'x' * 30)
        self.assertEqual(out1, [])
        self.assertTrue(self.d._discarding)
        self.assertEqual(self.d.get_stats().drop_oversize, 1)
        # 丢弃态下继续喂无换行数据：nl==-1 -> 直接返回 []
        out2 = self._feed(b'y' * 10)
        self.assertEqual(out2, [])
        # 喂入换行 + 合法帧：丢弃态恢复并递归解析（nl!=-1 恢复分支）
        out3 = self._feed(b'\n{"type":"recognize"}\n')
        self.assertEqual([m["type"] for m in out3], ["recognize"])
        self.assertFalse(self.d._discarding)

    def test_reset(self):
        self._feed(b'{"type":"recognize"}\n')
        self.d.reset()
        self.assertEqual(self.d._buffer, bytearray())
        self.assertFalse(self.d._discarding)
        # reset 仅清缓存与丢弃态，统计保留
        self.assertEqual(self.d.get_stats().frames_ok, 1)

    def test_stats_accumulate(self):
        self.d.feed(b'{"type":"recognize"}\n')
        self.d.feed(b'bad\n')
        self.d.feed(b'{"type":"unknown"}\n')
        s = self.d.get_stats()
        self.assertEqual(s.frames_ok, 1)
        self.assertEqual(s.drop_invalid_json, 1)
        self.assertEqual(s.drop_unknown_type, 1)
        self.assertEqual(s.drop_oversize, 0)


# ---------------------------------------------------------------------------
# A1 + 集成：TcpComm 单元分支覆盖（构造 / send / recv / 退避 / periodic / start / stop）
# ---------------------------------------------------------------------------

class TestTcpCommUnit(unittest.TestCase):
    def test_construct(self):
        comm = make_comm()
        self.assertEqual(comm._host, "127.0.0.1")
        self.assertEqual(comm._reconnect_backoff, [1, 2, 4, 8, 16, 30])
        self.assertEqual(comm._periodic_type, "periodic")
        self.assertEqual(comm._backoff_idx, -1)
        self.assertIsInstance(comm._stop_event, threading.Event)
        self.assertIsInstance(comm._decoder, FrameDecoder)
        self.assertTrue(hasattr(comm, "_connect_timeout"))
        self.assertTrue(hasattr(comm, "_recv_poll_timeout"))
        self.assertTrue(hasattr(comm, "_recv_buffer_size"))

    def test_is_connected(self):
        comm = make_comm()
        self.assertFalse(comm.is_connected())
        comm._conn = FakeConn()
        self.assertTrue(comm.is_connected())

    def test_send_no_conn(self):
        # 覆盖 if conn is None 的 True 分支
        comm = make_comm()
        comm._conn = None
        self.assertFalse(comm.send({"type": "recognize"}))

    def test_send_ok(self):
        # 覆盖 if conn is None 的 False 分支 + sendall 成功返回 True
        comm = make_comm()
        fake = FakeConn()
        comm._conn = fake
        self.assertTrue(comm.send({"type": "recognize"}))
        self.assertEqual(len(fake._sent), 1)

    def test_send_oserror(self):
        # 覆盖 sendall 抛 OSError 的 except 分支
        comm = make_comm()
        fake = FakeConn()

        def boom(_data):
            raise OSError("boom")

        fake.sendall = boom
        comm._conn = fake
        self.assertFalse(comm.send({"type": "recognize"}))

    def test_recv_empty_nonblock(self):
        # timeout=0 -> if 分支 False + 队列空 -> except Empty
        comm = make_comm()
        self.assertIsNone(comm.recv())

    def test_recv_empty_block(self):
        # timeout>0 -> if 分支 True + 队列空 -> except Empty
        comm = make_comm()
        self.assertIsNone(comm.recv(timeout=0.05))

    def test_recv_item_nonblock(self):
        # if 分支 False + 取到数据（except 未触发）
        comm = make_comm()
        comm._recv_queue.put({"type": "recognize"})
        self.assertEqual(comm.recv()["type"], "recognize")

    def test_recv_item_block(self):
        # if 分支 True + 取到数据（except 未触发）
        comm = make_comm()
        comm._recv_queue.put({"type": "recognize"})
        self.assertEqual(comm.recv(timeout=0.05)["type"], "recognize")

    def test_get_stats(self):
        comm = make_comm()
        s = comm.get_stats()
        self.assertIsInstance(s, FrameStats)
        self.assertEqual(s.frames_ok, 0)

    def test_wait_first_start(self):
        # _backoff_idx == -1 -> 立即返回 False（不等待）
        comm = make_comm()
        comm._backoff_idx = -1
        self.assertFalse(comm._wait_before_retry())

    def test_wait_cap(self):
        # _backoff_idx 越界 -> min 封顶到末档（30s），且 wait 被调用
        comm = make_comm(reconnect_backoff=[1, 2, 4, 8, 16, 30])
        comm._backoff_idx = 10
        cap = {}
        comm._stop_event.wait = lambda s: (cap.update(sec=s) or False)
        comm._wait_before_retry()
        self.assertEqual(cap["sec"], 30)

    def test_wait_returns_true_on_stop(self):
        # _backoff_idx>=0 且 stop_event 已置位 -> wait 立即返回 True
        comm = make_comm(reconnect_backoff=[1, 2, 4, 8, 16, 30])
        comm._backoff_idx = 2
        comm._stop_event.set()
        self.assertTrue(comm._wait_before_retry())

    def test_periodic_first_frame(self):
        # periodic 首发正常发送一帧（payload 细节见 TestTcpCommHeartbeat）
        comm = make_comm()
        sent = {}
        comm.send = lambda obj: (sent.update(obj=obj) or True)
        comm.send_periodic_once()
        self.assertEqual(sent["obj"]["type"], "periodic")

    def test_start_guard(self):
        # 覆盖 start 的 if self._running 两分支：首次启动 / 已启动直接返回
        comm = make_comm()
        orig = comm._loop
        comm._loop = lambda: None  # 置空，线程立即结束，避免真实网络阻塞
        comm.start()
        self.assertTrue(comm._running)
        comm.start()  # 已运行 -> 直接返回
        comm.stop()
        comm._loop = orig

    def test_stop_no_conn(self):
        # 覆盖 if self._conn is not None 的 False 分支（无连接直接跳过 close）
        comm = make_comm()
        comm._conn = None
        comm.stop()
        self.assertIsNone(comm._conn)

    def test_stop_with_conn(self):
        # 覆盖 if self._conn is not None 的 True 分支 + close 正常（except 未触发）
        comm = make_comm()
        fake = FakeConn()
        comm._conn = fake
        comm.stop()
        self.assertTrue(fake._closed)
        self.assertIsNone(comm._conn)

    def test_stop_conn_close_raises(self):
        # 覆盖 finally 中 close 抛 OSError 的 except 分支
        comm = make_comm()
        fake = FakeConn(close_raises=True)
        comm._conn = fake
        comm.stop()  # 不应抛出
        self.assertIsNone(comm._conn)


# ---------------------------------------------------------------------------
# A1：_loop 时序闭环（退避状态机 + 收包内循环）分支覆盖
# ---------------------------------------------------------------------------

class TestTcpCommLoop(unittest.TestCase):
    def run_loop(self, comm, duration=0.2):
        """在后台线程运行 _loop，duration 秒后停掉 _running 使其自然退出。"""
        comm._running = True
        t = threading.Thread(target=comm._loop, daemon=True)
        t.start()
        time.sleep(duration)
        comm._running = False
        t.join(timeout=2)

    @mock.patch.object(tcp_comm.socket, "create_connection")
    def test_success_recv_onmessage(self, mock_conn):
        # 建连成功 + 收到合法帧 + on_message 回调（覆盖 if on_message is not None 的 True 分支）
        captured = []
        comm = make_comm(reconnect_backoff=[0] * 6, on_message=captured.append)
        fake = FakeConn(recv_seq=[b'{"type":"version_query"}\n'])
        mock_conn.return_value = fake
        self.run_loop(comm, 0.2)
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["type"], "version_query")
        # 建连成功首发 periodic 帧
        self.assertTrue(any(b"periodic" in s for s in fake._sent))

    @mock.patch.object(tcp_comm.socket, "create_connection")
    def test_success_recv_no_onmessage(self, mock_conn):
        # on_message 为 None（覆盖 if on_message is not None 的 False 分支），帧仍入队列
        comm = make_comm(reconnect_backoff=[0] * 6, on_message=None)
        fake = FakeConn(recv_seq=[b'{"type":"version_query"}\n'])
        mock_conn.return_value = fake
        self.run_loop(comm, 0.2)
        msg = comm.recv(timeout=0.5)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["type"], "version_query")

    @mock.patch.object(tcp_comm.socket, "create_connection")
    def test_recv_timeout_continue(self, mock_conn):
        # 读超时（socket.timeout）-> 覆盖 except timeout -> continue；退出时 running=False
        comm = make_comm(reconnect_backoff=[0] * 6)
        fake = FakeConn(recv_seq=[socket.timeout("timed out")])
        mock_conn.return_value = fake
        self.run_loop(comm, 0.2)

    @mock.patch.object(tcp_comm.socket, "create_connection")
    def test_recv_oserror_break(self, mock_conn):
        # 收包抛 OSError（连接重置）-> 覆盖 except OSError -> break -> 断线重连日志
        comm = make_comm(reconnect_backoff=[0] * 6)
        fake = FakeConn(recv_seq=[ConnectionResetError("reset")])
        mock_conn.return_value = fake
        self.run_loop(comm, 0.2)

    @mock.patch.object(tcp_comm.socket, "create_connection")
    def test_peer_closed(self, mock_conn):
        # 收到空字节 -> 覆盖 if not chunk -> break（对端正常关闭）
        comm = make_comm(reconnect_backoff=[0] * 6)
        fake = FakeConn(recv_seq=[b""])
        mock_conn.return_value = fake
        self.run_loop(comm, 0.2)

    @mock.patch.object(tcp_comm.socket, "create_connection")
    def test_finally_close_raises(self, mock_conn):
        # 覆盖 finally 中 close 抛 OSError 的 except (OSError, AttributeError) 分支
        comm = make_comm(reconnect_backoff=[0] * 6)
        fake = FakeConn(recv_seq=[ConnectionResetError("reset")], close_raises=True)
        mock_conn.return_value = fake
        self.run_loop(comm, 0.2)

    @mock.patch.object(tcp_comm.socket, "create_connection")
    def test_connect_fail_backoff(self, mock_conn):
        # 建连失败 -> 覆盖 except OSError + 退避封顶；wait 改不阻塞，靠 running=False 退出
        comm = make_comm(reconnect_backoff=[1, 2, 4, 8, 16, 30])
        comm._stop_event.wait = lambda s: False  # 避免真实等待
        mock_conn.side_effect = OSError("refused")
        self.run_loop(comm, 0.3)
        self.assertEqual(comm._backoff_idx, 5)  # 封顶到末档

    def test_wait_retry_break(self):
        # 覆盖 if self._wait_before_retry(): break 的 True 分支（被 stop 打断，不建连）
        comm = make_comm(reconnect_backoff=[0] * 6)
        comm._backoff_idx = 0
        comm._stop_event.set()
        comm._running = True
        t = threading.Thread(target=comm._loop, daemon=True)
        t.start()
        t.join(timeout=1)
        self.assertFalse(t.is_alive())

    def test_loop_not_running(self):
        # 覆盖外层 while self._running 首次即 False（循环体不进入）
        comm = make_comm()
        comm._running = False
        comm._loop()
        self.assertFalse(comm._running)

    def test_backoff_log_intervals(self):
        # 验证退避序列日志：1/2/4/8/16/30/30... 与建连失败日志
        comm = make_comm(reconnect_backoff=[1, 2, 4, 8, 16, 30])
        comm._stop_event.wait = lambda s: False  # 避免真实等待
        with mock.patch.object(
            tcp_comm.socket, "create_connection", side_effect=OSError("refused")
        ):
            with self.assertLogs("tcp_comm", level="WARNING") as cm:
                comm._running = True
                t = threading.Thread(target=comm._loop, daemon=True)
                t.start()
                time.sleep(0.3)
                comm._running = False
                t.join(timeout=2)
        logs = "\n".join(cm.output)
        self.assertIn("第 1 次重连，等待 1s", logs)
        self.assertIn("第 2 次重连，等待 2s", logs)
        self.assertIn("建连失败", logs)
        self.assertIn("等待 30s", logs)  # 封顶档


class TestTcpCommHeartbeat(unittest.TestCase):
    def test_periodic_payload(self):
        # periodic payload 构造正确（含 8 路 camera_status 配对）
        comm = make_comm()
        comm._start_monotonic = time.monotonic() - 5.0
        sent = {}
        comm.send = lambda obj: (sent.update(obj=obj) or True)
        comm.send_periodic_once()
        self.assertEqual(sent["obj"]["type"], "periodic")
        self.assertGreaterEqual(sent["obj"]["uptime_sec"], 5)
        cam = sent["obj"]["camera_status"]
        self.assertEqual(len(cam), 8)
        self.assertEqual(cam[0], {"camera_id": "CAM1", "status": "ok"})
        self.assertEqual(cam[7], {"camera_id": "CAM8", "status": "ok"})

    def test_periodic_disconnected(self):
        # 未连接时调用不抛异常（send 返回 False 被忽略）
        comm = make_comm()
        comm._conn = None
        try:
            comm.send_periodic_once()
        except Exception as exc:  # pragma: no cover
            self.fail(f"send_periodic_once 不应抛出异常: {exc}")

    def test_start_heartbeat_idempotent(self):
        # start_heartbeat 幂等：二次调用不新建线程
        comm = make_comm(heartbeat_interval=0.05)
        comm.send = lambda obj: True  # 避免真实网络
        comm.start_heartbeat()
        self.assertIsNotNone(comm._heartbeat_thread)
        first = comm._heartbeat_thread
        comm.start_heartbeat()
        self.assertIs(comm._heartbeat_thread, first)
        comm.stop_heartbeat()

    def test_stop_heartbeat_idempotent(self):
        # stop_heartbeat 幂等：未启动时调用直接返回不报错
        comm = make_comm()
        comm.stop_heartbeat()  # 未启动 -> 直接返回
        self.assertIsNone(comm._heartbeat_thread)
        comm.start_heartbeat()
        comm.stop_heartbeat()
        comm.stop_heartbeat()  # 已停止 -> 直接返回

    def test_update_camera_status(self):
        # update_camera_status 更新快照，下次 periodic 反映新状态
        comm = make_comm()
        new_status = ["offline"] * 8
        comm.update_camera_status(new_status)
        self.assertEqual(comm._camera_status, new_status)
        sent = {}
        comm.send = lambda obj: (sent.update(obj=obj) or True)
        comm.send_periodic_once()
        self.assertEqual([c["status"] for c in sent["obj"]["camera_status"]],
                         ["offline"] * 8)

    def test_update_camera_status_truncate(self):
        # camera_ids(8) 与 status(1) 长度不一致：zip 自然截断到 1，无异常
        comm = make_comm()
        comm.update_camera_status(["x"])
        sent = {}
        comm.send = lambda obj: (sent.update(obj=obj) or True)
        comm.send_periodic_once()
        self.assertEqual(len(sent["obj"]["camera_status"]), 1)
        self.assertEqual(sent["obj"]["camera_status"][0],
                         {"camera_id": "CAM1", "status": "x"})

    def test_heartbeat_loop_skip_when_disconnected(self):
        # 断线期 is_connected 为 False：跳过发送，不调用 send_periodic_once
        comm = make_comm(heartbeat_interval=0.02)
        comm.is_connected = lambda: False
        calls = []
        comm.send_periodic_once = lambda: calls.append(1)
        t = threading.Thread(target=comm._heartbeat_loop, daemon=True)
        t.start()
        time.sleep(0.08)            # 多个周期
        comm._heartbeat_stop_event.set()
        t.join(timeout=2)
        self.assertEqual(calls, [])

    def test_heartbeat_loop_send_then_stop(self):
        # 已连接：每周期发送一次；置位 stop 后本周期内退出
        comm = make_comm(heartbeat_interval=0.02)
        comm.is_connected = lambda: True
        calls = []
        comm.send_periodic_once = lambda: calls.append(1)
        t = threading.Thread(target=comm._heartbeat_loop, daemon=True)
        t.start()
        time.sleep(0.08)            # 约 4 个周期
        comm._heartbeat_stop_event.set()
        t.join(timeout=2)
        self.assertFalse(t.is_alive())
        self.assertGreaterEqual(len(calls), 1)


# ---------------------------------------------------------------------------
# A4：请求配对与去重（异步任务网关）分支覆盖
# ---------------------------------------------------------------------------

class TestTcpCommA4(unittest.TestCase):
    def _comm(self, handlers=None, dedup_types=None):
        kw = {}
        if dedup_types is not None:
            kw["dedup_types"] = dedup_types
        if handlers is not None:
            kw["async_handlers"] = handlers
        return make_comm(dedup_cache_ttl=60.0, **kw)

    def test_dispatch_non_async_goes_to_on_message(self):
        # 非去重类型（version_query）走原样回调分支
        captured = []
        comm = make_comm(on_message=captured.append,
                         dedup_types=["recognize"], async_handlers={})
        comm._dispatch_message({"type": "version_query"})
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["type"], "version_query")

    def test_dispatch_async_missing_request_id_dropped(self):
        # 异步任务缺 request_id：丢弃，不登记在途、不触发业务
        started = []
        comm = self._comm(handlers={"recognize": lambda m: started.append(1) or {"items": []}})
        comm._dispatch_message({"type": "recognize"})
        self.assertEqual(comm._in_flight, set())
        self.assertEqual(started, [])

    @unittest.mock.patch("tcp_comm.threading.Thread")
    def test_dispatch_async_first_registers_in_flight(self, mock_thread):
        # 首帧登记在途；同 request_id 重发直接丢弃，业务仅执行一次
        def _run(**kw):
            kw["target"]()
            return unittest.mock.MagicMock()
        mock_thread.side_effect = _run
        started = []
        comm = self._comm(handlers={"recognize": lambda m: started.append(1) or {"items": []}})
        comm._dispatch_message({"type": "recognize", "request_id": "R1"})
        self.assertIn("R1", comm._in_flight)
        comm._dispatch_message({"type": "recognize", "request_id": "R1"})
        self.assertEqual(started, [1])

    def test_dispatch_cache_hit_resent_immediately(self):
        # 缓存命中（未过期）：立即重发缓存响应，不触发业务
        sent = []
        comm = self._comm(handlers={"recognize": lambda m: {"items": [1]}})
        comm.send = lambda obj: (sent.append(obj) or True)
        comm._completed_cache["R1"] = (
            {"type": "recognize_ack", "request_id": "R1", "items": [9]},
            time.monotonic() + 60)
        comm._dispatch_message({"type": "recognize", "request_id": "R1"})
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["items"], [9])
        self.assertNotIn("R1", comm._in_flight)

    @unittest.mock.patch("tcp_comm.threading.Thread")
    def test_dispatch_cache_expired_then_redispatch(self, mock_thread):
        # 缓存过期：删除后按新请求处理（登记在途 + 触发业务）
        def _run(**kw):
            kw["target"]()
            return unittest.mock.MagicMock()
        mock_thread.side_effect = _run
        started = []
        comm = self._comm(handlers={"recognize": lambda m: started.append(1) or {"items": []}})
        comm._completed_cache["R1"] = (
            {"type": "recognize_ack", "request_id": "R1"},
            time.monotonic() - 1)
        comm._dispatch_message({"type": "recognize", "request_id": "R1"})
        self.assertIn("R1", comm._in_flight)
        self.assertEqual(started, [1])

    def test_send_caches_completed_response(self):
        # send() 发送成功后：清在途 + 落库响应（供上位机超时重发）
        comm = self._comm()
        comm._conn = FakeConn()
        comm._in_flight.add("R1")
        self.assertTrue(comm.send({"type": "recognize_ack", "request_id": "R1", "items": [1]}))
        self.assertNotIn("R1", comm._in_flight)
        self.assertIn("R1", comm._completed_cache)
        self.assertEqual(comm._completed_cache["R1"][0]["items"], [1])

    def test_send_without_request_id_skips_dedup(self):
        # 无 request_id 的帧（periodic / version_ack）：不触碰去重状态
        comm = self._comm()
        comm._conn = FakeConn()
        self.assertTrue(comm.send({"type": "periodic", "uptime_sec": 0}))
        self.assertEqual(comm._in_flight, set())
        self.assertEqual(comm._completed_cache, {})

    @unittest.mock.patch("tcp_comm.threading.Thread")
    def test_dispatch_async_success_acks_payload(self, mock_thread):
        # 业务正常：ack 自动补全 type/request_id 并合并 payload
        def _run(**kw):
            kw["target"]()
            return unittest.mock.MagicMock()
        mock_thread.side_effect = _run
        sent = []
        comm = self._comm(handlers={"recognize": lambda m: {"items": [7]}})
        comm._conn = FakeConn()   # 已连接：send_reliable 走 send 落库
        comm.send = lambda obj: (sent.append(obj) or True)
        comm._dispatch_message({"type": "recognize", "request_id": "R1"})
        self.assertEqual(sent[0]["type"], "recognize_ack")
        self.assertEqual(sent[0]["request_id"], "R1")
        self.assertEqual(sent[0]["items"], [7])

    @unittest.mock.patch("tcp_comm.threading.Thread")
    def test_dispatch_async_exception_acks_false(self, mock_thread):
        # 业务异常：兜底 success=false 的 ack，且在途状态被释放
        def _run(**kw):
            kw["target"]()
            return unittest.mock.MagicMock()
        mock_thread.side_effect = _run
        sent = []
        def boom(m):
            raise RuntimeError("boom")
        comm = self._comm(handlers={"recognize": boom})
        comm._conn = FakeConn()   # 已连接：send_reliable 走 send 落库
        comm.send = lambda obj: (sent.append(obj) or True)
        comm._dispatch_message({"type": "recognize", "request_id": "R1"})
        self.assertEqual(sent[0]["success"], False)
        self.assertEqual(sent[0]["error"], "boom")


# ---------------------------------------------------------------------------
# A6：断连缓存与补报（可靠投递）分支覆盖
# ---------------------------------------------------------------------------

class TestTcpCommA6(unittest.TestCase):
    def _comm(self, **kw):
        return make_comm(**kw)

    def test_send_reliable_when_connected(self):
        # 已连接：直接走 send，不进离线缓存
        comm = self._comm()
        comm._conn = FakeConn()
        sent = {}
        comm.send = lambda obj: (sent.update(obj=obj) or True)
        self.assertTrue(comm.send_reliable({"type": "x"}))
        self.assertIn("obj", sent)
        self.assertEqual(comm._offline_cache, [])

    def test_send_reliable_when_disconnected_caches(self):
        # 断网：缓存入队并返回 True
        comm = self._comm()
        comm._conn = None
        self.assertTrue(comm.send_reliable({"type": "x", "request_id": "R1"}))
        self.assertEqual(len(comm._offline_cache), 1)
        self.assertEqual(comm._offline_cache[0][0]["request_id"], "R1")

    def test_send_reliable_offline_overflow_drops_oldest(self):
        # 离线缓存超上限：丢弃最旧消息
        comm = self._comm(offline_cache_max=2)
        comm._conn = None
        comm.send_reliable({"type": "a"})
        comm.send_reliable({"type": "b"})
        comm.send_reliable({"type": "c"})
        self.assertEqual(len(comm._offline_cache), 2)
        types = [m[0]["type"] for m in comm._offline_cache]
        self.assertEqual(types, ["b", "c"])

    def test_flush_offline_cache_empty_noop(self):
        # 空缓存：直接返回，不调用 send
        comm = self._comm()
        comm._conn = FakeConn()
        sent = {}
        comm.send = lambda obj: (sent.update(obj=obj) or True)
        comm._flush_offline_cache()
        self.assertEqual(sent, {})

    def test_flush_offline_cache_sends_and_clears(self):
        # 非空缓存：逐条补发并清空
        comm = self._comm()
        comm._conn = FakeConn()
        sent = []
        comm.send = lambda obj: (sent.append(obj) or True)
        comm._offline_cache.append(({"type": "ack1"}, time.time()))
        comm._offline_cache.append(({"type": "ack2"}, time.time()))
        comm._flush_offline_cache()
        self.assertEqual(len(sent), 2)
        self.assertEqual(comm._offline_cache, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
