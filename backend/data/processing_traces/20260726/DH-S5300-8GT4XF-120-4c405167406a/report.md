# 文档处理报告：DH-S5300-8GT4XF-120.txt

## 概览
- 状态：失败
- 文件：DH-S5300-8GT4XF-120.txt
- 来源路径：uploads/upload-dcbf9ca7d35b44df9466da8ed78ed0fb/汇聚交换机/汇聚交换机/DH-S5300-8GT4XF-120.txt
- 文档 ID：4d4e1b1cfb17832283cbde27e0c1e433
- Trace ID：4c405167406a4e9ba63a6de84a6e8031
- 开始时间：2026-07-26T12:06:19.121Z
- 结束时间：2026-07-26T12:07:22.287Z
- 总耗时：63.17 s
- 文件大小：4.4 KB
- 文件类型：.txt

## 阶段时间线
| 阶段 | 状态 | 耗时 | 关键结果 |
|---|---:|---:|---|
| 文档加载 / 解析 | 完成 | 48 ms | 字符 2588，元素 253，图片 0 |
| 切片策略 | 完成 | 49 ms | 切片 8，类型 parent 1，child 7，长度 307/647.0/2588 |
| 索引写入 | 失败 | 62.95 s | Connection error. |

## 关键配置
- 解析引擎：builtin
- 切片策略：auto
- 父块大小：4096 字符
- 子块大小：384 字符
- 子块重叠：76 字符
- Dense 检索：开启
- Keyword 检索：开启
- OCR：关闭
- 多模态：关闭

## 产物说明
- `report.md`：当前这份面向人工排查的总览报告。
- `parsed.md`：解析器抽取后的正文，适合检查原文是否读对、是否乱码。
- `chunks_preview.md`：前若干个切片的可读预览，适合快速确认切片质量。
- `chunks.jsonl`：完整切片明细，适合程序读取或深度排查。
- `trace.json`：完整机器 trace，供前端 trace 抽屉和自动化分析使用。

## 错误
- 类型：APIConnectionError
- 信息：Connection error.

```text
Traceback (most recent call last):
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\httpx\_transports\default.py", line 101, in map_httpcore_exceptions
    yield
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\httpx\_transports\default.py", line 250, in handle_request
    resp = self._pool.handle_request(req)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\httpcore\_sync\connection_pool.py", line 256, in handle_request
    raise exc from None
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\httpcore\_sync\connection_pool.py", line 236, in handle_request
    response = connection.handle_request(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\httpcore\_sync\http_proxy.py", line 343, in handle_request
    return self._connection.handle_request(request)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\httpcore\_sync\http11.py", line 136, in handle_request
    raise exc
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\httpcore\_sync\http11.py", line 106, in handle_request
    ) = self._receive_response_headers(**kwargs)
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\httpcore\_sync\http11.py", line 177, in _receive_response_headers
    event = self._receive_event(timeout=timeout)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\httpcore\_sync\http11.py", line 231, in _receive_event
    raise RemoteProtocolError(msg)
httpcore.RemoteProtocolError: Server disconnected without sending a response.

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\openai\_base_client.py", line 955, in _request
    response = self._client.send(
               ^^^^^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\httpx\_client.py", line 914, in send
    response = self._send_handling_auth(
               ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\httpx\_client.py", line 942, in _send_handling_auth
    response = self._send_handling_redirects(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\httpx\_client.py", line 979, in _send_handling_redirects
    response = self._send_single_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\httpx\_client.py", line 1014, in _send_single_request
    response = transport.handle_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\httpx\_transports\default.py", line 249, in handle_request
    with map_httpcore_exceptions():
  File "D:\soft\anaconda\Lib\contextlib.py", line 155, in __exit__
    self.gen.throw(typ, value, traceback)
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\httpx\_transports\default.py", line 118, in map_httpcore_exceptions
    raise mapped_exc(message) from exc
httpx.RemoteProtocolError: Server disconnected without sending a response.

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "D:\python_project\new-rag-project\backend\app\services\rag_service.py", line 612, in parse_and_index_document
    replace_document_chunks(parsed.doc_id, chunks, scope=scope)
  File "D:\python_project\new-rag-project\backend\app\services\vector_store.py", line 179, in replace_document_chunks
    self.upsert_chunks(chunks)
  File "D:\python_project\new-rag-project\backend\app\services\vector_store.py", line 186, in upsert_chunks
    embeddings = self.embedding_provider.embed_batch([chunk.embedding_text for chunk in indexable])
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\app\services\embedding_provider.py", line 76, in embed_batch
    response = self.client.embeddings.create(model=self.model, input=texts)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\openai\resources\embeddings.py", line 128, in create
    return self._post(
           ^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\openai\_base_client.py", line 1242, in post
    return cast(ResponseT, self.request(cast_to, opts, stream=stream, stream_cls=stream_cls))
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\openai\_base_client.py", line 919, in request
    return self._request(
           ^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\openai\_base_client.py", line 964, in _request
    return self._retry_request(
           ^^^^^^^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\openai\_base_client.py", line 1057, in _retry_request
    return self._request(
           ^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\openai\_base_client.py", line 964, in _request
    return self._retry_request(
           ^^^^^^^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\openai\_base_client.py", line 1057, in _retry_request
    return self._request(
           ^^^^^^^^^^^^^^
  File "D:\python_project\new-rag-project\backend\.venv\Lib\site-packages\openai\_base_client.py", line 989, in _request
    raise APIConnectionError(request=request) from err
openai.APIConnectionError: Connection error.
```
