# 115-MCP-Server

基于 **FastMCP** 和 **p115client** 的 115 网盘 MCP 服务器。

## 项目来源与致谢

本项目是一个基于以下开源项目进行封装与扩展的 MCP 服务器：

- **p115client**：115 网盘 Python 客户端与接口封装
  - 文档：https://p115client.readthedocs.io/en/latest/
- **FastMCP**：用于快速构建 MCP 服务器的 Python 框架

本项目的大部分 115 能力都封装自 **p115client** 提供的客户端与文件系统接口，在此对原项目作者与贡献者表示感谢。

同时也感谢 **FastMCP** 提供了稳定、清晰的 MCP 服务构建能力，使这些 115 功能可以以 MCP 工具的形式对外提供。

## 快速开始

如果你想最快跑起来，可以按这个顺序：

1. 创建虚拟环境
2. 安装依赖
3. 配置 `P115_COOKIES` 或 `P115_COOKIES_PATH`
4. 启动 MCP 服务
5. 在 MCP 客户端里接入

最简命令：

```bash
python -m venv .venv
./.venv/Scripts/python -m pip install -e .
./.venv/Scripts/115-MCP-Server
```

## 功能

- 查询认证状态
- 列出目录与读取元数据
- 搜索文件/目录
- 创建目录
- 上传本地文件到 115
- 下载 115 文件到本地
- 移动、复制、重命名、删除文件或目录
- 批量移动、批量复制、批量删除
- 获取文件下载直链
- 查询空间信息
- 将目录路径解析为目录 ID
- 判断文件是否存在、统计目录数量、获取祖先链
- 按 glob 匹配文件、递归遍历目录、获取 stat 信息
- 离线下载任务创建、查询、清理、删除、BT 信息查询
- 离线下载默认目录查询/设置、任务重启、任务计数
- 离线任务高级筛选、批量删除、sign 信息、详细套餐/配额查询
- 回收站列表、详情、恢复
- 回收站清空或永久删除指定回收站条目
- 标签列表与标签设置
- 分享列表、分享详情、接收码、接收分享、分享下载链接、访问用户、分享下载配额
- 查询账号信息与索引首页统计
- 支持通过 MCP 发起二维码登录并保存 cookies

## 安装

### 环境要求

- Python 3.12 或更高版本
- Windows 环境已验证可用
- 需要能访问 115 相关接口

### 方式一：源码安装（推荐）

```bash
python -m venv .venv
./.venv/Scripts/python -m pip install --upgrade pip
./.venv/Scripts/python -m pip install -e .
```

安装完成后，可执行入口包括：

- `./.venv/Scripts/115-MCP-Server`
- `python -m mcp_115_server`（内部模块入口）

### 方式二：开发模式重新安装

如果你修改了源码并希望重新安装当前项目：

```bash
./.venv/Scripts/python -m pip install -e .
```

### 验证安装是否成功

```bash
./.venv/Scripts/115-MCP-Server --help
```

如果能看到命令行帮助，说明安装成功。

## 配置

### 认证方式

本项目支持三种认证方式：

1. 直接传入环境变量 `P115_COOKIES`
2. 通过环境变量 `P115_COOKIES_PATH` 指向 cookies 文件
3. 通过 MCP 工具执行二维码登录

> 本项目**不再支持**通过项目根目录 `.env` 文件自动加载配置，以避免和客户端自身的 MCP 环境配置混淆。

推荐使用环境变量 + cookies 文件：

```env
P115_COOKIES_PATH=~/115-cookies.txt
P115_CHECK_FOR_RELOGIN=true
P115_ALLOW_QRCODE_LOGIN=false
P115_CONSOLE_QRCODE=false
```

也支持直接通过环境变量传入 cookies：

```env
P115_COOKIES=UID=...; CID=...; SEID=...; KID=...
```

说明：

- `P115_COOKIES` 优先级高于 `P115_COOKIES_PATH`
- 未配置 cookies 时，默认不会触发扫码登录
- 若要允许 `p115client` 在需要时尝试扫码登录，请设置 `P115_ALLOW_QRCODE_LOGIN=true`

- ### Cookie 平台自动推断

服务默认依赖 `p115client` 根据 cookie 自动推断首选登录平台。

当前行为：

1. 不需要手动配置 cookie 平台。
2. 服务会优先使用 `P115Client` 从 cookie 推断出的平台。
3. 如果某个接口在当前平台下失败，服务只做最小必要的接口级回退，而不会对大量平台进行轮询。
4. 这样可以减少失败请求数量，降低触发风控的风险。

### 推荐的环境变量写法

```env
P115_COOKIES_PATH=C:\Users\your-name\115-cookies.txt
P115_CHECK_FOR_RELOGIN=true
P115_ALLOW_QRCODE_LOGIN=false
P115_CONSOLE_QRCODE=false
FASTMCP_TRANSPORT=stdio
```

这些变量应通过以下任一方式提供：

- MCP 客户端配置中的 `environment`
- 当前终端 / 系统环境变量
- 进程启动器（如 OpenCode、Claude Desktop、Cursor 等）的环境注入

## 启动

### stdio

适用于绝大多数 MCP 桌面客户端。

```bash
./.venv/Scripts/115-MCP-Server
```

### HTTP

适用于需要通过 URL 接入 MCP 的客户端或调试场景。

```bash
./.venv/Scripts/115-MCP-Server --transport http --host 127.0.0.1 --port 8000 --path /mcp
```

也可以使用安装后的命令：

```bash
115-MCP-Server
```

Windows 也可以直接运行脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-stdio.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\run-http.ps1
```

或：

```cmd
scripts\run-stdio.cmd
scripts\run-http.cmd
```

### 启动参数说明

- `--transport`：`stdio` / `http` / `streamable-http` / `sse`
- `--host`：HTTP 监听地址
- `--port`：HTTP 监听端口
- `--path`：HTTP MCP 路径
- `--log-level`：日志级别

例如：

```bash
./.venv/Scripts/115-MCP-Server --transport http --host 127.0.0.1 --port 8010 --path /mcp --log-level debug
```

## MCP 客户端接入示例

在开始之前，先准备这几个信息：

- Python 可执行文件：`C:\Users\flami\Downloads\115-MCP\.venv\Scripts\python.exe`
- 备用模块入口：`python -m mcp_115_server`
- 推荐环境变量：

```text
P115_COOKIES_PATH=C:\Users\your-name\115-cookies.txt
P115_CHECK_FOR_RELOGIN=true
P115_ALLOW_QRCODE_LOGIN=false
P115_CONSOLE_QRCODE=false
```

### 通用 stdio 模板

如果某个客户端支持以 `command + args + env` 的方式添加 MCP 服务，可直接套用：

```json
{
  "mcpServers": {
    "115-MCP-Server": {
      "command": "C:\\Users\\flami\\Downloads\\115-MCP\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_115_server"],
      "env": {
        "P115_COOKIES_PATH": "C:\\Users\\your-name\\115-cookies.txt",
        "P115_CHECK_FOR_RELOGIN": "true",
        "P115_ALLOW_QRCODE_LOGIN": "false",
        "P115_CONSOLE_QRCODE": "false"
      }
    }
  }
}
```

大多数支持 MCP 的客户端，本质上都只需要以下两种接入方式之一：

- `stdio`
- `http`

无论你使用的是 OpenCode、Claude Code、Claude Desktop、Cursor、Gemini、Kiro、Antigravity、Cherry Studio，还是其它支持 MCP 的客户端，都建议优先按下面的通用模板配置。

### HTTP 模式接入

如果客户端支持通过 URL 连接 MCP，可使用 HTTP 模式。

先启动服务：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-http.ps1
```

默认地址：

```text
http://127.0.0.1:8000/mcp
```

然后在客户端中填入这个地址即可。

### 接入排查建议

如果某个客户端接入失败，优先检查：

1. 客户端版本是否真的支持 MCP
2. 是否选择了 `stdio` 或 HTTP MCP 模式
3. Python 路径是否正确
4. 是否使用了正确的 `python.exe` 与 `-m mcp_115_server` 入口
5. cookies 是否已正确配置
6. HTTP 模式下端口和路径是否为 `127.0.0.1:8000/mcp`

## 使用方式

### 常见使用流程 1：已有 cookies，直接使用

1. 配置环境变量
2. 启动服务
3. 在客户端中调用：
   - `auth_status`
   - `list_directory`
   - `search_entries`
   - `offline_add_urls`

### 常见使用流程 2：没有 cookies，先扫码登录

1. 启动服务
2. 调用 `start_qrcode_login`
3. 打开返回的 `qrcode_url` 并扫码
4. 调用 `get_qrcode_login_status` 轮询状态
5. 状态变成 `signed_in` 后，调用 `finish_qrcode_login`
6. 保存返回的 cookies，后续直接复用

### 常见使用流程 3：离线下载资源到 115

1. 先用 `create_directory` 创建目标目录
2. 用 `offline_add_urls` 添加下载链接
3. 用 `offline_list_tasks` 或 `offline_list_tasks_advanced` 查询进度
4. 必要时用：
   - `offline_restart_task`
   - `offline_remove_task`
   - `offline_remove_tasks`
   - `offline_clear_tasks`

### 常见使用流程 4：整理和管理文件

可组合调用：

- `list_directory`
- `search_entries`
- `move_entry` / `batch_move_entries`
- `rename_entry`
- `set_entry_labels`
- `get_download_url`

## 项目结构

```text
src/mcp_115_server/
  config.py      # 环境变量与服务配置
  service.py     # 115 业务封装层
  server.py      # FastMCP 工具注册与服务入口
tests/
  test_service.py
scripts/
  run-stdio.ps1
  run-http.ps1
  run-stdio.cmd
  run-http.cmd
```

## MCP 工具

- `auth_status`
- `list_directory`
- `get_metadata`
- `search_entries`
- `create_directory`
- `resolve_directory`
- `get_storage_info`
- `start_qrcode_login`
- `get_qrcode_login_status`
- `finish_qrcode_login`
- `get_account_info`
- `get_index_info`
- `path_exists`
- `count_directory`
- `get_ancestors`
- `glob_entries`
- `walk_directory`
- `get_stat`
- `offline_add_urls`
- `offline_get_torrent_info`
- `offline_add_torrent`
- `offline_list_tasks`
- `offline_remove_task`
- `offline_clear_tasks`
- `offline_get_quota_info`
- `offline_get_download_paths`
- `offline_set_download_path`
- `offline_restart_task`
- `offline_get_task_count`
- `offline_list_tasks_advanced`
- `offline_remove_tasks`
- `offline_get_sign_info`
- `offline_get_quota_package_array`
- `offline_get_quota_package_info`
- `list_recycle_bin`
- `get_recycle_bin_entry`
- `restore_recycle_bin_entries`
- `clear_recycle_bin`
- `list_labels`
- `set_entry_labels`
- `list_shares`
- `get_share_info`
- `get_share_receive_code`
- `receive_share_entries`
- `get_share_download_url`
- `list_share_access_users`
- `get_share_download_quota`
- `upload_local_file`
- `download_file`
- `move_entry`
- `batch_move_entries`
- `copy_entry`
- `batch_copy_entries`
- `rename_entry`
- `remove_entry`
- `batch_remove_entries`
- `get_download_url`

## 关键返回约定

- `get_download_url` 始终返回对象，而不是裸字符串，包含：
  - `url`: 当前下载地址
  - `target`: 目标文件的元数据

- `auth_status(validate_remote=true)` 在远端校验失败时会返回：
  - `remote_logged_in: false`
  - `remote_error`: 规范化后的错误消息

- 批量操作工具统一支持两种来源之一：
  - `source_ids: list[int]`
  - `source_paths: list[str]`

  两者只能传一个。

- `get_share_download_url` 始终返回对象，包含：
  - `url`
  - `file_id`
  - `mode`

## 新增能力说明

### 1. 批量移动

一次移动多个文件或目录到目标目录：

- `batch_move_entries(source_ids=[...], destination_dir_path="/目标目录")`
- `batch_move_entries(source_paths=["/a.txt", "/b"], destination_dir_id=123456)`

### 2. 批量复制

一次复制多个文件或目录到目标目录：

- `batch_copy_entries(source_ids=[...], destination_dir_path="/目标目录")`

### 3. 批量删除

一次删除多个文件或目录：

- `batch_remove_entries(source_ids=[...])`
- `batch_remove_entries(source_paths=["/旧文件.txt", "/旧目录"])`

### 4. 查询目录 ID

如果你手里是一个目录路径，可以先调用：

- `resolve_directory(remote_path="/文档/项目")`

### 5. 查询空间信息

获取当前账号空间配额信息：

- `get_storage_info()`

### 5.1 扫码登录获取 cookies

现在可以直接通过 MCP 工具完成二维码登录，不必预先手动准备 cookies。

步骤 1：启动扫码会话

- `start_qrcode_login(app="alipaymini")`

返回：

- `session_id`
- `uid`
- `qrcode_url`
- `app`

步骤 2：轮询扫码状态

- `get_qrcode_login_status(session_id="...")`

可能的 `status_name`：

- `waiting`
- `scanned`
- `signed_in`
- `expired`
- `canceled`

步骤 3：完成登录并保存 cookies

- `finish_qrcode_login(session_id="...", output_path="C:\\Users\\your-name\\115-cookies.txt")`

返回：

- `cookies`
- `saved_to`
- `session_id`

完成后，这个 MCP 服务实例会立即切换到新的 cookies。

### 6. 路径/目录辅助查询

- `path_exists(remote_path="/文档")`
- `count_directory(remote_path="/文档")`
- `get_ancestors(remote_path="/文档/项目/demo.txt")`
- `glob_entries("*.txt", directory_path="/文档")`
- `walk_directory(remote_path="/文档", max_depth=2)`
- `get_stat(remote_path="/文档/demo.txt")`

### 7. 离线下载（重点能力）

已实现的离线下载工具：

- `offline_add_urls(urls=[...], remote_dir_id=123)`
- `offline_add_urls(urls=[...], remote_dir_id=123, duplicate_policy="error")`
- `offline_get_torrent_info(torrent_sha1="...", pick_code="...")`
- `offline_add_torrent(torrent_sha1="...", pick_code="...", wanted_indexes=[0,1])`
- `offline_list_tasks(page=1)`
- `offline_find_tasks(query="字幕组", status="completed")`
- `offline_remove_task(info_hash="...", delete_source_file=false)`
- `offline_clear_tasks(scope="completed")`
- `offline_get_quota_info()`
- `offline_get_download_paths()`
- `offline_set_download_path(remote_dir_path="/文档/离线")`
- `offline_restart_task(info_hash="...")`
- `offline_get_task_count(flag=0)`
- `offline_list_tasks_advanced(page=1, page_size=30, status="completed")`
- `offline_remove_tasks(info_hashes=["...", "..."], delete_source_file=false)`
- `offline_get_sign_info()`
- `offline_get_quota_package_array()`
- `offline_get_quota_package_info()`

`offline_clear_tasks` 支持的 `scope`：

- `completed`
- `all`
- `failed`
- `in_progress`
- `completed_and_delete_source`
- `all_and_delete_source`

说明：

- `offline_add_urls` 适合 HTTP / HTTPS / FTP / magnet / ed2k
- `offline_add_urls` 支持 `duplicate_policy`：
  - `error`：如果检测到相同磁链 / 相同 `info_hash` 的云下载任务已存在，立即返回明确错误
  - `skip`：跳过重复任务，只提交新的 URL
- 默认推荐使用 `duplicate_policy="error"`，这样可以避免重复磁链导致的卡住或误判
- `offline_get_torrent_info` 可先查看 BT 内容，再配合 `wanted_indexes` 精选文件
- `offline_list_tasks` 已经对 Open API 的响应结构做了整形，直接返回 `count / page_count / tasks`
- `offline_find_tasks` 会在 MCP 层基于分页结果执行本地搜索/过滤，支持：
  - `query`
  - `info_hash`
  - `status`
  - `limit`
  - `offset`
- `offline_set_download_path` 可以用 `remote_dir_id` 或 `remote_dir_path` 指定默认离线目录
- `offline_restart_task` 适合失败后的任务重试
- `offline_get_task_count` 直接返回后端的离线任务计数信息
- `offline_list_tasks_advanced` 支持传统离线任务状态筛选，当前支持：
  - `failed`
  - `completed`
  - `in_progress`
- `offline_remove_tasks` 用于按 `info_hash` 批量删除离线任务
- `offline_get_sign_info` 返回低层离线接口会用到的 `sign/time` 等信息
- `offline_get_quota_package_array` / `offline_get_quota_package_info` 返回更详细的离线套餐/配额信息

#### 目录落位校验与 warnings

`offline_add_urls` 和 `offline_add_torrent` 现在会返回 `warnings` 字段。

用途：

- 当你传入 `remote_dir_id` 时，MCP 会尽量根据任务元数据检查它是否真的落到了预期目录
- 如果无法确认，或者任务元数据里显示的目录和预期目录不一致，就会在 `warnings` 中给出提示

重要说明：

- 这是一种**最佳努力校验**，不是后端强保证
- 115 后端在某些接口分支下，可能不会稳定回传足够的目录信息
- 因此 `warnings` 能帮助你发现可疑情况，但不能替代最终目录核验

### 8. 回收站

- `list_recycle_bin(limit=32, offset=0)`
- `get_recycle_bin_entry(rid=123)`
- `restore_recycle_bin_entries(entry_ids=[1,2,3])`
- `clear_recycle_bin(entry_ids=[1,2], password="123456")`

说明：

- 不传 `entry_ids` 时表示清空整个回收站
- 如果你的 115 账号开启了安全密钥校验，需传 `password`

### 9. 标签

- `list_labels(keyword="项目")`
- `set_entry_labels(remote_id=123456, label_ids=[1,2])`

注意：`set_entry_labels` 是**替换**当前标签集合，不是追加。

- 传 `label_ids=[]` 表示清空这个条目的全部标签

### 10. 分享

- `list_shares(limit=32, offset=0)`
- `get_share_info(share_code="xxxx")`
- `get_share_receive_code(share_code="xxxx")`
- `receive_share_entries(share_code="xxxx", receive_code="abcd", file_ids=[1,2], remote_dir_path="/接收目录")`
- `get_share_download_url(file_id=123, share_code="xxxx", receive_code="abcd")`
- `list_share_access_users(share_code="xxxx")`
- `get_share_download_quota()`

说明：

- `get_share_download_url` 支持两种方式：
  - 显式传 `share_code + receive_code + file_id`
  - 或直接传 `share_url + file_id`
- `get_share_download_url` 始终返回对象：
  - `url`: 下载地址
  - `file_id`: 请求的分享文件 id
  - `mode`: `share_code` 或 `share_url`
- `receive_share_entries` 会把分享中的指定文件/目录接收到你自己的网盘目录中

### 11. 账号与首页统计

- `get_account_info()`
- `get_index_info(include_space_numbers=true)`

## 目标定位规则

大多数工具都支持以下两种方式之一：

- `remote_id`: 115 文件/目录 ID
- `remote_path`: 115 路径，例如 `/文档/项目`

两者只能传一个；目录类工具若都不传，则默认根目录。

### 远程 ID 传参规则（重要）

所有远程 ID 都建议并推荐按**字符串**传入，不要按 JSON number / 数值传入。

正确示例：

```json
{
  "remote_id": "3398357158620823140"
}
```

不推荐示例：

```json
{
  "remote_id": 3398357158620823140
}
```

原因：

- 115 的很多远程 ID 很长
- 在某些客户端、语言运行时、JSON 处理中，超长整数可能发生精度丢失
- 一旦被改写，例如尾数被截断或归整，就会导致操作到错误的文件或目录

因此：

- `remote_id`
- `parent_id`
- `directory_id`
- `remote_dir_id`
- `source_id`
- `destination_dir_id`
- `file_id`
- `rid`
- `source_ids`
- `entry_ids`
- `file_ids`
- `label_ids`

都应优先按字符串或字符串数组传入。

## 测试

```bash
./.venv/Scripts/python -m unittest discover -s tests -v
```

## 本地打包为 Windows exe

如果你需要在本地构建 Windows 可执行文件：

```powershell
./.venv/Scripts/python -m pip install pyinstaller
powershell -ExecutionPolicy Bypass -File .\scripts\build-exe.ps1
```

构建完成后输出位于：

```text
dist\115-MCP-Server.exe
```

说明：

- 这是基于当前虚拟环境依赖打包出的 Windows 可执行文件
- 配置仍然通过环境变量或 MCP 客户端 `environment` 传入

## 部署建议

- 本地桌面客户端优先使用 `stdio`
- 需要多客户端共享时使用 `http`
- cookies 推荐放在本机文件中，通过 `P115_COOKIES_PATH` 引用
- 不建议把真实 cookies 直接写进公开配置文件

## 常见问题

### 1. 提示未配置认证

说明没有设置 `P115_COOKIES` 或 `P115_COOKIES_PATH`。

### 2. 提示 cookies 文件不存在

确认 `P115_COOKIES_PATH` 指向真实文件，路径需要是运行客户端那台机器上的本地路径。

### 3. 客户端连不上 MCP

检查：

- Python 路径是否正确
- 虚拟环境是否已安装 `pip install -e .`
- 客户端配置里的 `args` 是否为 `-m mcp_115_server`

### 4. HTTP 模式无法访问

检查端口是否被占用，以及客户端填写的地址是否为：

```text
http://127.0.0.1:8000/mcp
```
