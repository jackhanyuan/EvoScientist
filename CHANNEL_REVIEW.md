# Channel Module Review

## 一、Bug / 潜在风险（高优先级）

### 1. `_build_inbound` 的线程池同步包装器存在线程安全问题

**文件:** `EvoScientist/channels/base.py:816-838`

在已有运行中的 event loop 时，开启新线程调用 `asyncio.run()` 创建全新的 event loop。这不仅性能差（每次创建/销毁线程池），更关键的是，如果 middleware 内部持有的状态（如 `DedupCache`、`GroupHistoryBuffer`）不是线程安全的，会产生竞态条件。

**建议:** 删除这个同步包装器，或改用 `asyncio.run_coroutine_threadsafe()` 指向已有的 loop。

### 2. `TypingManager.stop()` 不等待 task 取消完成

**文件:** `EvoScientist/channels/middleware.py:192-196`

```python
async def stop(self, chat_id: str) -> None:
    task = self._tasks.pop(chat_id, None)
    if task:
        task.cancel()
        # 缺少: await task (suppress CancelledError)
```

`task.cancel()` 之后没有 `await task`，任务可能还在运行。对比 `base.py:381-390` 中 debounce task 的处理（先 cancel 再 await），应保持一致。

### 3. `PairingMiddleware` 使用 `asyncio.ensure_future` 且未保存引用

**文件:** `EvoScientist/channels/middleware.py:812`

```python
asyncio.ensure_future(self._send_response_fn(raw.chat_id, text))
```

返回的 future 没有被保存，如果抛出异常会成为 "unhandled exception" 并在 GC 时打印警告。

**建议:** 改用 `asyncio.create_task()` 并保存引用或添加 done callback 处理异常。

### 4. `_send_locks` LRU 驱逐可能导致无限增长

**文件:** `EvoScientist/channels/base.py:420-437`

```python
while len(self._send_locks) > self._send_locks_max:
    oldest_key, oldest_lock = next(iter(self._send_locks.items()))
    if oldest_lock.locked():
        break  # 最旧的被锁住就整体放弃
    del self._send_locks[oldest_key]
```

如果最旧的 lock 正被持有，`break` 直接退出，导致 dict 无限增长超过 `_send_locks_max`。

**建议:** 跳过被锁的条目继续检查后续的，而非整体放弃。

### 5. `GroupHistoryBuffer` 混用 `time.time()` 和 `time.monotonic()`

**文件:** `EvoScientist/channels/middleware.py:138-139` vs `middleware.py:746-750`

`GroupHistoryBuffer.get_recent()` 用 `time.time()` 作基准计算过期，但 `DedupCache` 一致使用 `time.monotonic()`。在系统时钟调整（NTP 同步等）时可能造成消息被错误过期或永远不过期。

**建议:** 统一使用 `time.monotonic()`。

---

## 二、架构设计问题（中优先级）

### 6. Debounce 逻辑存在两份实现

**文件:** `EvoScientist/channels/base.py:279-289`（Channel 自身 6 个 dict）+ `EvoScientist/channels/middleware.py:357-448`（`DebounceMiddleware`）

`Channel.queue_message()` 内嵌了一整套去抖逻辑（`_message_buffers`, `_message_metadata`, `_message_media`, `_message_ids`, `_message_is_group`, `_message_was_mentioned`），同时 `DebounceMiddleware` 也实现了几乎相同的功能。6 个并行的 dict 需要手动同步（`_message_is_group` / `_message_was_mentioned` 明显是后补的）。

**建议:** 将 `Channel.queue_message()` 的 debounce 逻辑替换为 `DebounceMiddleware`。

### 7. `OutboundPipeline` 目前是空壳

**文件:** `EvoScientist/channels/channel_manager.py:274-284`

```python
def build_outbound_pipeline(plugin, config):
    middlewares: list[OutboundMiddlewareBase] = []
    return OutboundPipeline(plugin, middlewares)
```

永远返回空的 middleware 列表，使得 `_dispatch_outbound()` 中对 pipeline 的判断和调用完全是多余的空转。

**建议:** 实现真正的 outbound middleware 组装逻辑，或移除 pipeline 相关代码减少复杂度。

### 8. `_should_process` 在 `Channel` 和 `MentionGatingMiddleware` 中重复

**文件:** `EvoScientist/channels/base.py:757-767` + `EvoScientist/channels/middleware.py:669-677`

两者逻辑完全相同。`Channel._should_process()` 已不再被框架直接调用（被 middleware pipeline 取代），但仍存在，可能导致开发者混淆。

**建议:** 移除 `Channel._should_process()`。

### 9. `is_allowed` / `is_channel_allowed` 与 `AllowListMiddleware` 重复

**文件:** `EvoScientist/channels/base.py:1023-1053` + `EvoScientist/channels/middleware.py:682-723`

`Channel.is_allowed()` 和 `Channel.is_channel_allowed()` 与 `AllowListMiddleware._is_sender_allowed()` 是同一逻辑的不同实现。

**建议:** 标记 Channel 上的方法为 deprecated 或移除。

### 10. `MessageBus` 同时有两种 outbound 消费路径

**文件:** `EvoScientist/channels/bus/message_bus.py:61-84` vs `EvoScientist/channels/channel_manager.py:801-873`

`MessageBus` 自带 `dispatch_outbound()` 方法（用 subscriber callback），同时 `ChannelManager` 也有 `_dispatch_outbound()` 直接消费 outbound queue。两个入口不能同时工作，否则会互相抢消息。目前实际只用了 `ChannelManager._dispatch_outbound()`。

**建议:** 移除 `MessageBus.dispatch_outbound()` 和 `subscribe_outbound()` 避免误用。

---

## 三、健壮性改进（中优先级）

### 11. `WebSocketMixin` 重连使用固定延迟而非指数退避

**文件:** `EvoScientist/channels/mixins.py:237`

```python
await asyncio.sleep(self._ws_reconnect_delay)  # 固定 5s
```

对比 `Channel.run()` 中的指数退避（`base.py:988-1021`，1s -> 60s），WebSocket 用固定 5s。服务端长时间故障时会产生不必要的频繁重连。

**建议:** 改为指数退避，与 `Channel.run()` 保持一致。

### 12. `_HealthServer` 和 `SharedWebhookServer` 绑定 `0.0.0.0` 无安全控制

**文件:** `EvoScientist/channels/channel_manager.py:320-321`

health endpoint 和 webhook server 默认绑定 `0.0.0.0`，在公网暴露内部状态信息。

**建议:** 增加 bind address 配置，health server 默认 `127.0.0.1`。

### 13. `download_attachment` 缺少文件名碰撞处理

**文件:** `EvoScientist/channels/base.py:168-204`

同一 channel 内两个同名文件会互相覆盖。

**建议:** 加入 UUID 或时间戳后缀。

### 14. `_api_post` / `_api_get` 不检查 HTTP 状态码

**文件:** `EvoScientist/channels/mixins.py:132-140`

```python
async def _api_post(self, url, body, headers=None):
    resp = await self._http_client.post(url, json=body, headers=headers)
    return resp.json()  # 不管 status code 直接解析
```

即使返回 4xx/5xx 也直接 `resp.json()` 返回，调用方可能误以为请求成功。

**建议:** 加入 `resp.raise_for_status()` 或至少返回状态码信息。

### 15. Queue 满时的背压处理

**文件:** `EvoScientist/channels/base.py:263`

当 queue 满时 `_enqueue_raw` 中的 `await self._queue.put(msg)` 会阻塞，上游的 webhook handler 可能有自己的超时限制。

**建议:** 用 `put_nowait()` + 溢出告警，或使用带超时的 `put`。

---

## 四、代码质量 / 可维护性（低优先级）

### 16. 废弃别名缺少 deprecation warning

**文件:** `EvoScientist/channels/base.py:206-208`

```python
IncomingMessage = InboundMessage
OutgoingMessage = OutboundMessage
```

裸别名没有 deprecation 提示，使用者无法得知应迁移。

**建议:** 用 `warnings.warn` 或直接移除。

### 17. `RawIncoming.metadata` 类型不精确

**文件:** `EvoScientist/channels/base.py:227`

```python
metadata: dict = field(default_factory=dict)
```

**建议:** 改为 `dict[str, Any]`，与其他类型注解保持一致。

### 18. `ChannelPlugin` 类属性定义位置不规范

**文件:** `EvoScientist/channels/plugin.py:191-196`

`security`、`groups` 等类属性声明被插在 `__init__` 方法之后，看起来像局部变量。

**建议:** 将所有类属性集中在方法定义之前。

### 19. `ChannelManager.start_all()` 阻塞语义未文档化

**文件:** `EvoScientist/channels/channel_manager.py:682`

```python
await asyncio.gather(*self._tasks, return_exceptions=True)
```

`start_all()` 不会返回直到所有 channel 都停止。如果这是设计意图（作为主运行循环），应在文档中明确说明。

### 20. `consumer.py` 的 `_evict_chat_locks` 策略过于粗糙

**文件:** `EvoScientist/channels/consumer.py:403-407`

驱逐一半未锁定的 lock，但没有基于时间的 LRU 逻辑，可能造成频繁创建/销毁同一个 lock。

**建议:** 引入 last-used 时间戳，优先驱逐长时间未使用的。

---

## 五、功能增强建议

| # | 建议 | 说明 |
|---|------|------|
| 21 | **Middleware 可配置化** | `_build_inbound_middlewares()` 硬编码了 middleware 顺序，建议支持通过配置文件增删 middleware |
| 22 | **Retry 预设覆盖不足** | `RETRY_PRESETS` 只有 Telegram 一条，WeChat/Feishu/DingTalk 等有不同限速策略，应各自配置 |
| 23 | **Channel 级别 metrics** | `ChannelHealth` 只跟踪 send 成功/失败，缺少 inbound 计数、延迟直方图、消息大小等 |
| 24 | **Graceful shutdown 信号** | `stop_all()` drain 期间没有通知 channel "即将关闭"，channel 可能继续接收新消息 |
| 25 | **Formatter 缺少表格支持** | `UnifiedFormatter` 未处理 Markdown 表格，表格在 HTML channel 中可以良好呈现 |

---

## 总结优先级

| 优先级 | 项目 | 影响 |
|--------|------|------|
| **高** | #1 线程安全, #2 typing task 泄漏, #4 send lock 无限增长 | 运行时 bug |
| **中高** | #3 未处理异常, #5 时钟不一致, #11 WS 重连策略 | 稳定性 |
| **中** | #6-#10 代码重复/死代码, #12-#15 健壮性 | 可维护性和安全性 |
| **低** | #16-#20 代码规范, #21-#25 功能增强 | 代码质量 |
