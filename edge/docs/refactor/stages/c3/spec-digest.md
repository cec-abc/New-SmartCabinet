# c3 TCP 模块 spec-digest

## ① 范围与资料
- 交付 `edge/modules/tcp/` 五文件：`tcp_comm` / `tcp_reconnect_thread` / `tcp_heart_thread` / `tcp_decode_thread` / `tcp_control_layer`。
- 语义来源：INDEX §2.5/2.6/2.7（断线重连/心跳/帧解码）+ docx 外部协议（线上 JSON 键名以 docx 为准）。

## ② 命名裁决（图上 snake_case 不作 API）
- 落地 camelCase：`TcpControlLayer.transitionTo/onLinkDown/onLinkUp/onSignalDecoded`、`TcpComm.splitFrames/decodeAndParse/encodeFrame`；线程类 `TcpReconnectThread`/`TcpHeartThread`/`TcpDecodeThread`。
- 出网 JSON 键用协议原文（`type`/`uptime_sec`/`software_version`/`camera_status`），内部变量 `camelCase`，`reqId`/`hitResp` 不作线上键。

## ③ 契约与接口
- 依赖 `interfaces/i_socket`、`i_sinks`、`i_logger`、`i_thread`（经 `BaseThread`）、`base/base_thread`、`base/base_service`。
- 硬约束：`tcp/` 禁 `config`/`cv2`/`numpy`/`vision_core`/`IConfig.getValue()`；`maxFrameSize`、退避序列、心跳周期、心跳构造器全部构造注入。

## ④ 裁决落实
- **D-02** 非 UP 不启其他线程：`start()` 仅拉重连；`_onConnected` 后启心跳+解码；`onLinkDown` 停二者并重启重连。
- **D-03** 去重不做、`seq` 只填不用：本协议帧无 `seq` 字段，c3 不涉及；心跳失败/解码断线靠 `transitionTo` 返回值去重。

## ⑤ 遗留与待裁决
- 分帧按协议「一行 JSON」用 `\n` 切，`maxFrameSize` 作单帧字节上限两者并用、构造注入（用户拍板）。
- EventCache 存废归 **d**；错放判定归 **c5**；`camera_status` 默认值 + 连丢 5 条周期帧判离线归 **c4/d**，勿与 `linkState` 混（见 `decisions.md` 待裁决登记）。
