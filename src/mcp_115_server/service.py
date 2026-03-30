from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastmcp.exceptions import ToolError
from p115client import P115Client, check_response
from p115client.fs import P115FileSystem
from yarl import URL

from .config import Settings


DEFAULT_PLATFORM_CANDIDATES = (
    "web",
    "desktop",
    "harmony",
    "apple_tv",
    "android",
    "qandroid",
    "ios",
    "115ios",
    "ipad",
    "115ipad",
    "wechatmini",
    "alipaymini",
    "tv",
    "windows",
    "mac",
    "linux",
    "os_windows",
    "os_mac",
    "os_linux",
)

WEB_LIKE_PLATFORMS = {
    "web",
    "desktop",
    "harmony",
    "windows",
    "mac",
    "linux",
    "os_windows",
    "os_mac",
    "os_linux",
}


class OfflineClearScope(StrEnum):
    COMPLETED = "completed"
    ALL = "all"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"
    COMPLETED_AND_DELETE_SOURCE = "completed_and_delete_source"
    ALL_AND_DELETE_SOURCE = "all_and_delete_source"


OFFLINE_CLEAR_SCOPE_TO_FLAG = {
    OfflineClearScope.COMPLETED: 0,
    OfflineClearScope.ALL: 1,
    OfflineClearScope.FAILED: 2,
    OfflineClearScope.IN_PROGRESS: 3,
    OfflineClearScope.COMPLETED_AND_DELETE_SOURCE: 4,
    OfflineClearScope.ALL_AND_DELETE_SOURCE: 5,
}


class OfflineTaskStatus(StrEnum):
    FAILED = "failed"
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"


OFFLINE_TASK_STATUS_TO_FLAG = {
    OfflineTaskStatus.FAILED: 9,
    OfflineTaskStatus.COMPLETED: 11,
    OfflineTaskStatus.IN_PROGRESS: 12,
}


class P115Service:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self._client_instance: P115Client | None = None
        self._fs_instance: P115FileSystem | None = None
        self._client_cache: dict[str | None, P115Client] = {}
        self._fs_cache: dict[str | None, P115FileSystem] = {}
        self._active_platform: str | None = None
        self._qrcode_sessions: dict[str, dict[str, Any]] = {}

    def auth_status(self, validate_remote: bool = False) -> dict[str, Any]:
        status: dict[str, Any] = {
            "configured": self.settings.has_auth_configuration,
            "cookies_source": self.settings.cookies_source,
            "preferred_platform": self.settings.preferred_platform,
            "fallback_platforms": self.settings.fallback_platforms,
            "active_platform": self._active_platform,
            "check_for_relogin": self.settings.p115_check_for_relogin,
            "allow_qrcode_login": self.settings.p115_allow_qrcode_login,
            "console_qrcode": self.settings.p115_console_qrcode,
            "client_initialized": self._client_instance is not None,
        }
        if self.settings.cookies_path is not None:
            status["cookies_path"] = str(self.settings.cookies_path)
            status["cookies_path_exists"] = self.settings.cookies_path.exists()

        if validate_remote:
            try:
                status["remote_logged_in"] = self._with_client_fallback(
                    "validate_remote_login",
                    lambda client, _platform: bool(self._call_backend(client.login_status)),
                )
            except Exception as exc:  # noqa: BLE001
                status["remote_logged_in"] = False
                status["remote_error"] = self._format_backend_error(exc)

        if not status["configured"]:
            status["hint"] = (
                "Set P115_COOKIES or P115_COOKIES_PATH. "
                "Enable P115_ALLOW_QRCODE_LOGIN only if your runtime can display the QR flow."
            )

        return status

    def start_qrcode_login(self, app: str = "alipaymini") -> dict[str, Any]:
        selected_app = app.strip() or "alipaymini"
        response = self._call_backend(check_response, P115Client.login_qrcode_token())
        token = response["data"]
        session_id = uuid4().hex
        uid = str(token["uid"])
        qrcode_url = token.get("qrcode") or f"https://115.com/scan/dg-{uid}"
        self._qrcode_sessions[session_id] = {
            "app": selected_app,
            "uid": uid,
            "token": {
                "uid": token["uid"],
                "time": token["time"],
                "sign": token["sign"],
            },
            "qrcode_url": qrcode_url,
        }
        return {
            "session_id": session_id,
            "app": selected_app,
            "uid": uid,
            "qrcode_url": qrcode_url,
        }

    def get_qrcode_login_status(self, session_id: str) -> dict[str, Any]:
        session = self._get_qrcode_session(session_id)
        response = self._call_backend(check_response, P115Client.login_qrcode_scan_status(session["token"]))
        status = int(response["data"].get("status", 0))
        status_name = {
            0: "waiting",
            1: "scanned",
            2: "signed_in",
            -1: "expired",
            -2: "canceled",
        }.get(status, f"unknown_{status}")
        return {
            "session_id": session_id,
            "app": session["app"],
            "uid": session["uid"],
            "status": status,
            "status_name": status_name,
            "result": self._normalize(response),
        }

    def finish_qrcode_login(self, session_id: str, output_path: str = "") -> dict[str, Any]:
        session = self._get_qrcode_session(session_id)
        response = self._call_backend(
            check_response,
            P115Client.login_qrcode_scan_result(session["uid"], app=session["app"]),
        )
        cookies = str(response["data"]["cookie"])
        saved_to = ""
        if output_path.strip():
            destination = Path(output_path).expanduser().resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(cookies, encoding="utf-8")
            saved_to = str(destination)
        preferred_platform = session["app"] if session["app"] else self.settings.preferred_platform
        self._client_instance = None
        self._fs_instance = None
        self._client_cache.clear()
        self._fs_cache.clear()
        self._with_client_fallback(
            "activate_qrcode_cookies",
            lambda client, _platform: bool(self._call_backend(client.login_status)) or True,
            preferred_platform=preferred_platform,
            cookies_source=cookies,
        )
        self._qrcode_sessions.pop(session_id, None)
        return {
            "session_id": session_id,
            "app": session["app"],
            "uid": session["uid"],
            "cookies": cookies,
            "saved_to": saved_to,
            "result": self._normalize(response),
        }

    def list_directory(
        self,
        *,
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        target = self._resolve_remote(remote_id=remote_id, remote_path=remote_path, allow_root_default=True)
        directory = self._fs_call("get_attr", target, refresh=refresh)
        if not directory["is_dir"]:
            raise ToolError("Target is not a directory.")
        entries = self._list_directory_entries(int(directory["id"]))
        return {
            "directory": self._normalize(directory),
            "entries": [self._normalize(entry) for entry in entries],
            "count": len(entries),
        }

    def get_metadata(
        self,
        *,
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        target = self._resolve_remote(remote_id=remote_id, remote_path=remote_path, allow_root_default=False)
        return self._normalize(self._fs_call("get_attr", target, refresh=refresh))

    def search_entries(
        self,
        query: str,
        *,
        directory_id: int | None = None,
        directory_path: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        if not query.strip():
            raise ToolError("query must not be empty.")
        if limit <= 0:
            raise ToolError("limit must be positive.")
        if offset < 0:
            raise ToolError("offset must be non-negative.")
        if limit + offset > 10_000:
            raise ToolError("p115client search only supports limit + offset <= 10000.")

        target = self._resolve_remote(remote_id=directory_id, remote_path=directory_path, allow_root_default=True)
        cid = 0
        scope: dict[str, Any] | None = None
        if target != "":
            scope = self._fs_call("get_attr", target)
            if not scope["is_dir"]:
                raise ToolError("Search scope must be a directory.")
            cid = int(scope["id"])

        response = self._client_call(
            "fs_search",
            {
                "cid": cid,
                "limit": limit,
                "offset": offset,
                "search_value": query,
                "show_dir": 1,
            },
        )
        data = response.get("data", response)
        return {
            "scope": self._normalize(scope) if scope is not None else {"id": 0, "name": "/", "is_dir": True},
            "query": query,
            "offset": offset,
            "limit": limit,
            "result": self._normalize(data),
        }

    def create_directory(
        self,
        name: str,
        *,
        parent_id: int | None = None,
        parent_path: str | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        if not name.strip():
            raise ToolError("name must not be empty.")
        parent_directory_id = self._resolve_directory_id(remote_id=parent_id, remote_path=parent_path, allow_root_default=True)
        payload = {"cname": name.strip()}

        def attempt(client: P115Client, platform: str | None):
            if self._is_web_like_platform(platform):
                return self._call_backend(check_response, self._call_backend(client.fs_mkdir, payload, pid=parent_directory_id))
            return self._call_backend(
                check_response,
                self._call_backend(client.fs_mkdir_app, payload, pid=parent_directory_id, app=platform or "android"),
            )

        response = self._with_client_fallback("create_directory", attempt)
        return self._normalize(response)

    def resolve_directory(
        self,
        *,
        remote_path: str,
    ) -> dict[str, Any]:
        if not remote_path.strip():
            raise ToolError("remote_path must not be empty.")
        directory_id = self._resolve_directory_id(remote_path=remote_path, remote_id=None, allow_root_default=False)
        return {
            "remote_path": remote_path,
            "result": {"id": directory_id, "path": remote_path},
        }

    def get_storage_info(self) -> dict[str, Any]:
        response = self._client_call("fs_storage_info")
        return self._normalize(response)

    def get_account_info(self) -> dict[str, Any]:
        response = self._client_call("user_info")
        return self._normalize(response)

    def get_index_info(self, include_space_numbers: bool = False) -> dict[str, Any]:
        payload = 1 if include_space_numbers else 0
        response = self._client_call("fs_index_info", payload)
        return self._normalize(response)

    def path_exists(
        self,
        *,
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        target = self._resolve_remote(remote_id=remote_id, remote_path=remote_path, allow_root_default=True)
        exists = self._fs_call("exists", target, refresh=refresh)
        return {
            "target": {"remote_id": remote_id, "remote_path": remote_path or ("/" if target == "" else None)},
            "exists": bool(exists),
        }

    def count_directory(
        self,
        *,
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        target = self._resolve_remote(remote_id=remote_id, remote_path=remote_path, allow_root_default=True)
        metadata = self._fs_call("get_attr", target, refresh=refresh)
        if not metadata["is_dir"]:
            raise ToolError("Target is not a directory.")
        count = self._fs_call("dirlen", target, refresh=refresh)
        return {
            "directory": self._normalize(metadata),
            "count": int(count),
        }

    def get_ancestors(
        self,
        *,
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        target = self._resolve_remote(remote_id=remote_id, remote_path=remote_path, allow_root_default=False)
        ancestors = self._fs_call("get_ancestors", target, refresh=refresh)
        return {
            "target": self.get_metadata(remote_id=remote_id, remote_path=remote_path, refresh=refresh),
            "ancestors": self._normalize(ancestors),
        }

    def glob_entries(
        self,
        pattern: str,
        *,
        directory_id: int | None = None,
        directory_path: str | None = None,
        ignore_case: bool = False,
        limit: int = 100,
        refresh: bool = False,
    ) -> dict[str, Any]:
        if not pattern.strip():
            raise ToolError("pattern must not be empty.")
        if limit <= 0:
            raise ToolError("limit must be positive.")
        target = self._resolve_remote(remote_id=directory_id, remote_path=directory_path, allow_root_default=True)
        entries_iter = self._fs_call(
            "glob",
            pattern=pattern,
            top=target,
            ignore_case=ignore_case,
            refresh=refresh,
        )
        entries: list[Any] = []
        try:
            for entry in entries_iter:
                entries.append(self._normalize(entry))
                if len(entries) >= limit:
                    break
        except Exception as exc:  # noqa: BLE001
            raise ToolError(self._format_backend_error(exc)) from exc
        scope = self._normalize(self._fs_call("get_attr", target, refresh=refresh)) if target != "" else {"id": 0, "name": "/", "is_dir": True}
        return {
            "pattern": pattern,
            "scope": scope,
            "entries": entries,
            "count": len(entries),
            "limit": limit,
            "ignore_case": ignore_case,
        }

    def walk_directory(
        self,
        *,
        remote_id: int | None = None,
        remote_path: str | None = None,
        max_depth: int = 2,
        topdown: bool = True,
        limit: int = 200,
        refresh: bool = False,
    ) -> dict[str, Any]:
        if limit <= 0:
            raise ToolError("limit must be positive.")
        if max_depth < 1:
            raise ToolError("max_depth must be at least 1.")
        target = self._resolve_remote(remote_id=remote_id, remote_path=remote_path, allow_root_default=True)
        root_meta = self._fs_call("get_attr", target, refresh=refresh)
        if not root_meta["is_dir"]:
            raise ToolError("Target is not a directory.")
        walk_iter = self._fs_call(
            "walk",
            target,
            topdown=topdown,
            min_depth=1,
            max_depth=max_depth,
            refresh=refresh,
        )
        nodes: list[dict[str, Any]] = []
        try:
            for directory, dirs, files in walk_iter:
                nodes.append(
                    {
                        "directory": self._normalize(directory),
                        "dirs": self._normalize(dirs),
                        "files": self._normalize(files),
                    }
                )
                if len(nodes) >= limit:
                    break
        except Exception as exc:  # noqa: BLE001
            raise ToolError(self._format_backend_error(exc)) from exc
        return {
            "root": self._normalize(root_meta),
            "nodes": nodes,
            "count": len(nodes),
            "max_depth": max_depth,
            "limit": limit,
            "topdown": topdown,
        }

    def get_stat(
        self,
        *,
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        target = self._resolve_remote(remote_id=remote_id, remote_path=remote_path, allow_root_default=False)
        return {
            "target": self.get_metadata(remote_id=remote_id, remote_path=remote_path, refresh=refresh),
            "stat": self._normalize(self._fs_call("stat", target, refresh=refresh)),
        }

    def offline_add_urls(
        self,
        urls: list[str],
        *,
        remote_dir_id: int | None = None,
    ) -> dict[str, Any]:
        normalized_urls = [item.strip() for item in urls if item.strip()]
        if not normalized_urls:
            raise ToolError("urls must contain at least one non-empty entry.")
        payload: dict[str, Any] = {"urls": "\n".join(normalized_urls)}
        if remote_dir_id is not None:
            payload["wp_path_id"] = remote_dir_id
        open_payload: dict[str, Any] = {"urls": "\n".join(normalized_urls)}
        legacy_payload: dict[str, Any] = {f"url[{index}]": value for index, value in enumerate(normalized_urls)}
        return {
            "urls": normalized_urls,
            "result": self._normalize(
                self._with_client_fallback(
                    "offline_add_urls",
                    lambda client, platform: self._offline_add_urls_with_platform(
                        client,
                        platform,
                        open_payload=open_payload | ({"wp_path_id": remote_dir_id} if remote_dir_id is not None else {}),
                        legacy_payload=legacy_payload | ({"wp_path_id": remote_dir_id} if remote_dir_id is not None else {}),
                    ),
                )
            ),
        }

    def offline_get_torrent_info(self, torrent_sha1: str, pick_code: str) -> dict[str, Any]:
        if not torrent_sha1.strip():
            raise ToolError("torrent_sha1 must not be empty.")
        if not pick_code.strip():
            raise ToolError("pick_code must not be empty.")
        payload = {"torrent_sha1": torrent_sha1.strip(), "pick_code": pick_code.strip()}
        response = self._client_call("offline_torrent_info_open", payload)
        return self._normalize(response)

    def offline_add_torrent(
        self,
        *,
        torrent_sha1: str,
        pick_code: str,
        info_hash: str = "",
        wanted_indexes: list[int] | None = None,
        remote_dir_id: int | None = None,
        save_path: str = "",
    ) -> dict[str, Any]:
        if not torrent_sha1.strip():
            raise ToolError("torrent_sha1 must not be empty.")
        if not pick_code.strip():
            raise ToolError("pick_code must not be empty.")
        payload: dict[str, Any] = {
            "torrent_sha1": torrent_sha1.strip(),
            "pick_code": pick_code.strip(),
        }
        if info_hash.strip():
            payload["info_hash"] = info_hash.strip()
        if wanted_indexes:
            payload["wanted"] = ",".join(str(int(index)) for index in wanted_indexes)
        if remote_dir_id is not None:
            payload["wp_path_id"] = remote_dir_id
        if save_path.strip():
            payload["save_path"] = save_path.strip()
        response = self._client_call("offline_add_torrent_open", payload)
        return self._normalize(response)

    def offline_list_tasks(self, page: int = 1) -> dict[str, Any]:
        if page <= 0:
            raise ToolError("page must be positive.")
        response = self._with_client_fallback(
            "offline_list_tasks",
            lambda client, platform: self._offline_list_tasks_with_platform(client, platform, page),
        )
        data = response.get("data", response)
        return {
            "page": page,
            "count": data.get("count"),
            "page_count": data.get("page_count"),
            "tasks": self._normalize(data.get("tasks", [])),
            "result": self._normalize(data),
        }

    def offline_list_tasks_advanced(
        self,
        *,
        page: int = 1,
        page_size: int = 30,
        status: str = "",
    ) -> dict[str, Any]:
        if page <= 0:
            raise ToolError("page must be positive.")
        if page_size <= 0:
            raise ToolError("page_size must be positive.")
        payload: dict[str, Any] = {"page": page, "page_size": page_size}
        if status:
            try:
                payload["stat"] = OFFLINE_TASK_STATUS_TO_FLAG[OfflineTaskStatus(status)]
            except ValueError as exc:
                raise ToolError(f"Invalid offline task status: {status}") from exc
        response = self._with_client_fallback(
            "offline_list_tasks_advanced",
            lambda client, platform: self._call_backend(
                check_response,
                self._call_backend(client.offline_list, payload, type="web" if self._is_web_like_platform(platform) else "ssp"),
            ),
        )
        return {
            "page": page,
            "page_size": page_size,
            "status": status or None,
            "count": response.get("count"),
            "page_count": response.get("page_count"),
            "tasks": self._normalize(response.get("tasks", [])),
            "result": self._normalize(response),
        }

    def offline_remove_task(self, info_hash: str, delete_source_file: bool = False) -> dict[str, Any]:
        if not info_hash.strip():
            raise ToolError("info_hash must not be empty.")
        payload = {"info_hash": info_hash.strip(), "del_source_file": int(delete_source_file)}
        response = self._client_call("offline_remove_open", payload)
        return self._normalize(response)

    def offline_remove_tasks(self, info_hashes: list[str], delete_source_file: bool = False) -> dict[str, Any]:
        normalized_hashes = [item.strip() for item in info_hashes if item.strip()]
        if not normalized_hashes:
            raise ToolError("info_hashes must contain at least one non-empty value.")
        payload: dict[str, Any] = {f"hash[{index}]": value for index, value in enumerate(normalized_hashes)}
        payload["flag"] = int(delete_source_file)
        response = self._client_call("offline_remove", payload)
        return {
            "info_hashes": normalized_hashes,
            "delete_source_file": delete_source_file,
            "result": self._normalize(response),
        }

    def offline_clear_tasks(self, scope: str = OfflineClearScope.COMPLETED.value) -> dict[str, Any]:
        try:
            clear_scope = OfflineClearScope(scope)
        except ValueError as exc:
            raise ToolError(f"Invalid scope: {scope}") from exc
        response = self._client_call("offline_clear_open", OFFLINE_CLEAR_SCOPE_TO_FLAG[clear_scope])
        return {
            "scope": clear_scope.value,
            "result": self._normalize(response),
        }

    def offline_get_quota_info(self) -> dict[str, Any]:
        response = self._client_call("offline_quota_info_open")
        return self._normalize(response)

    def offline_get_sign_info(self) -> dict[str, Any]:
        response = self._client_call("offline_sign")
        return self._normalize(response)

    def offline_get_quota_package_array(self) -> dict[str, Any]:
        response = self._client_call("offline_quota_package_array")
        return self._normalize(response)

    def offline_get_quota_package_info(self) -> dict[str, Any]:
        response = self._client_call("offline_quota_package_info")
        return self._normalize(response)

    def offline_get_download_paths(self) -> dict[str, Any]:
        response = self._client_call("offline_download_path")
        return self._normalize(response)

    def offline_set_download_path(
        self,
        *,
        remote_dir_id: int | None = None,
        remote_dir_path: str | None = None,
    ) -> dict[str, Any]:
        target = self._resolve_remote(remote_id=remote_dir_id, remote_path=remote_dir_path, allow_root_default=False)
        metadata = self._fs_call("get_attr", target)
        if not metadata["is_dir"]:
            raise ToolError("Offline download path must be a directory.")
        response = self._client_call("offline_download_path_set", int(metadata["id"]))
        return {
            "directory": self._normalize(metadata),
            "result": self._normalize(response),
        }

    def offline_restart_task(self, info_hash: str) -> dict[str, Any]:
        if not info_hash.strip():
            raise ToolError("info_hash must not be empty.")
        response = self._client_call("offline_restart", info_hash.strip())
        return self._normalize(response)

    def offline_get_task_count(self, flag: int = 0) -> dict[str, Any]:
        response = self._client_call("offline_task_count", int(flag))
        return self._normalize(response)

    def list_recycle_bin(self, limit: int = 32, offset: int = 0) -> dict[str, Any]:
        if limit <= 0:
            raise ToolError("limit must be positive.")
        if offset < 0:
            raise ToolError("offset must be non-negative.")
        response = self._client_call("recyclebin_list", {"limit": limit, "offset": offset})
        return self._normalize(response)

    def get_recycle_bin_entry(self, rid: int) -> dict[str, Any]:
        response = self._client_call("recyclebin_info", rid)
        return self._normalize(response)

    def restore_recycle_bin_entries(self, entry_ids: list[int]) -> dict[str, Any]:
        if not entry_ids:
            raise ToolError("entry_ids must not be empty.")
        response = self._client_call("recyclebin_revert", entry_ids)
        return {
            "entry_ids": [int(item) for item in entry_ids],
            "result": self._normalize(response),
        }

    def clear_recycle_bin(self, entry_ids: list[int] | None = None, password: str = "") -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if entry_ids:
            payload["tid"] = ",".join(str(int(item)) for item in entry_ids)
        if password:
            payload["password"] = password
        response = self._client_call("recyclebin_clean", payload)
        return {
            "entry_ids": [int(item) for item in entry_ids] if entry_ids else [],
            "result": self._normalize(response),
        }

    def list_labels(
        self,
        *,
        keyword: str = "",
        limit: int = 100,
        offset: int = 0,
        sort: str = "",
        order: str = "",
    ) -> dict[str, Any]:
        if limit <= 0:
            raise ToolError("limit must be positive.")
        if offset < 0:
            raise ToolError("offset must be non-negative.")
        payload: dict[str, Any] = {"limit": limit, "offset": offset}
        if keyword.strip():
            payload["keyword"] = keyword.strip()
        if sort.strip():
            payload["sort"] = sort.strip()
        if order.strip():
            payload["order"] = order.strip()
        response = self._client_call("fs_label_list", payload)
        return self._normalize(response)

    def set_entry_labels(self, remote_id: int, label_ids: list[int]) -> dict[str, Any]:
        normalized_label_ids = [int(item) for item in label_ids]
        response = self._client_call("fs_label_set", int(remote_id), label=",".join(str(item) for item in normalized_label_ids))
        return {
            "remote_id": int(remote_id),
            "label_ids": normalized_label_ids,
            "result": self._normalize(response),
        }

    def list_shares(self, limit: int = 32, offset: int = 0, include_cancelled: bool = False) -> dict[str, Any]:
        if limit <= 0:
            raise ToolError("limit must be positive.")
        if offset < 0:
            raise ToolError("offset must be non-negative.")
        payload = {"limit": limit, "offset": offset, "show_cancel_share": int(include_cancelled)}
        response = self._client_call("share_list", payload)
        return self._normalize(response)

    def get_share_info(self, share_code: str) -> dict[str, Any]:
        if not share_code.strip():
            raise ToolError("share_code must not be empty.")
        response = self._client_call("share_info", share_code.strip())
        return self._normalize(response)

    def get_share_receive_code(self, share_code: str) -> dict[str, Any]:
        if not share_code.strip():
            raise ToolError("share_code must not be empty.")
        response = self._client_call("share_recvcode", share_code.strip())
        return self._normalize(response)

    def receive_share_entries(
        self,
        *,
        share_code: str,
        receive_code: str,
        file_ids: list[int],
        remote_dir_id: int | None = None,
        remote_dir_path: str | None = None,
        is_check: bool = False,
    ) -> dict[str, Any]:
        if not share_code.strip():
            raise ToolError("share_code must not be empty.")
        if not receive_code.strip():
            raise ToolError("receive_code must not be empty.")
        if not file_ids:
            raise ToolError("file_ids must not be empty.")
        payload: dict[str, Any] = {
            "share_code": share_code.strip(),
            "receive_code": receive_code.strip(),
            "file_id": ",".join(str(int(item)) for item in file_ids),
            "is_check": int(is_check),
        }
        if remote_dir_id is not None or remote_dir_path:
            target = self._resolve_remote(remote_id=remote_dir_id, remote_path=remote_dir_path, allow_root_default=False)
            metadata = self._fs_call("get_attr", target)
            if not metadata["is_dir"]:
                raise ToolError("Share receive destination must be a directory.")
            payload["cid"] = int(metadata["id"])
        response = self._client_call("share_receive", payload)
        return {
            "file_ids": [int(item) for item in file_ids],
            "result": self._normalize(response),
        }

    def get_share_download_url(
        self,
        *,
        file_id: int,
        share_code: str = "",
        receive_code: str = "",
        share_url: str = "",
        strict: bool = True,
        app: str = "",
    ) -> dict[str, Any]:
        if not share_url.strip() and not share_code.strip():
            raise ToolError("Provide share_url or share_code.")
        if share_code.strip() and not receive_code.strip() and not share_url.strip():
            raise ToolError("receive_code is required when share_code is provided without share_url.")
        payload: dict[str, Any] = {"file_id": int(file_id)}
        if share_code.strip():
            payload["share_code"] = share_code.strip()
            payload["receive_code"] = receive_code.strip()
        url = self._with_client_fallback(
            "share_download_url",
            lambda client, platform: self._call_backend(
                client.share_download_url,
                payload,
                url=share_url.strip(),
                strict=strict,
                app=app or (platform or ""),
            ),
            preferred_platform=app or None,
        )
        return {
            "url": self._normalize(url),
            "file_id": int(file_id),
            "mode": "share_url" if share_url.strip() else "share_code",
        }

    def list_share_access_users(self, share_code: str) -> dict[str, Any]:
        if not share_code.strip():
            raise ToolError("share_code must not be empty.")
        response = self._client_call("share_access_user_list", share_code.strip())
        return self._normalize(response)

    def get_share_download_quota(self) -> dict[str, Any]:
        response = self._client_call("share_notlogin_dl_quota")
        return self._normalize(response)

    def upload_local_file(
        self,
        local_path: str,
        *,
        remote_dir_id: int | None = None,
        remote_dir_path: str | None = None,
        remote_filename: str = "",
        refresh: bool = False,
    ) -> dict[str, Any]:
        source = Path(local_path).expanduser().resolve()
        if not source.exists():
            raise ToolError(f"Local file does not exist: {source}")
        if not source.is_file():
            raise ToolError(f"Local path is not a file: {source}")
        remote_dir = self._resolve_remote(
            remote_id=remote_dir_id,
            remote_path=remote_dir_path,
            allow_root_default=True,
        )
        result = self._fs_call(
            "upload",
            remote_dir,
            file=str(source),
            filename=remote_filename,
            refresh=refresh,
        )
        return {
            "local_path": str(source),
            "uploaded": self._normalize(result),
        }

    def download_file(
        self,
        local_path: str,
        *,
        remote_id: int | None = None,
        remote_path: str | None = None,
        overwrite: bool = False,
        refresh: bool = False,
    ) -> dict[str, Any]:
        target = self._resolve_remote(remote_id=remote_id, remote_path=remote_path, allow_root_default=False)
        self._fs_call("get_attr", target, refresh=refresh)
        destination = Path(local_path).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        saved_path, written = self._fs_call(
            "download",
            target,
            path=str(destination),
            mode="w" if overwrite else "x",
            refresh=refresh,
        )
        return {
            "local_path": saved_path,
            "bytes_written": written,
        }

    def move_entry(
        self,
        *,
        source_id: int | None = None,
        source_path: str | None = None,
        destination_dir_id: int | None = None,
        destination_dir_path: str | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        source = self._resolve_remote(remote_id=source_id, remote_path=source_path, allow_root_default=False)
        destination = self._resolve_remote(
            remote_id=destination_dir_id,
            remote_path=destination_dir_path,
            allow_root_default=True,
        )
        return self._normalize(self._fs_call("move", source, to_dir=destination, refresh=refresh))

    def batch_move_entries(
        self,
        *,
        source_ids: list[int] | None = None,
        source_paths: list[str] | None = None,
        destination_dir_id: int | None = None,
        destination_dir_path: str | None = None,
    ) -> dict[str, Any]:
        source_entry_ids = self._resolve_many_sources(source_ids=source_ids, source_paths=source_paths)
        destination = self._resolve_remote(
            remote_id=destination_dir_id,
            remote_path=destination_dir_path,
            allow_root_default=True,
        )
        destination_meta = self._fs_call("get_attr", destination)
        if not destination_meta["is_dir"]:
            raise ToolError("Destination must be a directory.")
        response = self._client_call("fs_move", source_entry_ids, pid=int(destination_meta["id"]))
        return {
            "source_ids": source_entry_ids,
            "destination": self._normalize(destination_meta),
            "result": self._normalize(response),
        }

    def copy_entry(
        self,
        *,
        source_id: int | None = None,
        source_path: str | None = None,
        destination_dir_id: int | None = None,
        destination_dir_path: str | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        source = self._resolve_remote(remote_id=source_id, remote_path=source_path, allow_root_default=False)
        destination = self._resolve_remote(
            remote_id=destination_dir_id,
            remote_path=destination_dir_path,
            allow_root_default=True,
        )
        return self._normalize(self._fs_call("copy", source, to_dir=destination, refresh=refresh))

    def batch_copy_entries(
        self,
        *,
        source_ids: list[int] | None = None,
        source_paths: list[str] | None = None,
        destination_dir_id: int | None = None,
        destination_dir_path: str | None = None,
    ) -> dict[str, Any]:
        source_entry_ids = self._resolve_many_sources(source_ids=source_ids, source_paths=source_paths)
        destination = self._resolve_remote(
            remote_id=destination_dir_id,
            remote_path=destination_dir_path,
            allow_root_default=True,
        )
        destination_meta = self._fs_call("get_attr", destination)
        if not destination_meta["is_dir"]:
            raise ToolError("Destination must be a directory.")
        response = self._client_call("fs_copy", source_entry_ids, pid=int(destination_meta["id"]))
        return {
            "source_ids": source_entry_ids,
            "destination": self._normalize(destination_meta),
            "result": self._normalize(response),
        }

    def rename_entry(
        self,
        new_name: str,
        *,
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        if not new_name.strip():
            raise ToolError("new_name must not be empty.")
        target = self._resolve_remote(remote_id=remote_id, remote_path=remote_path, allow_root_default=False)
        return self._normalize(self._fs_call("rename", target, name=new_name, refresh=refresh))

    def remove_entry(
        self,
        *,
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        target = self._resolve_remote(remote_id=remote_id, remote_path=remote_path, allow_root_default=False)
        return self._normalize(self._fs_call("remove", target, refresh=refresh))

    def batch_remove_entries(
        self,
        *,
        source_ids: list[int] | None = None,
        source_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        source_entry_ids = self._resolve_many_sources(source_ids=source_ids, source_paths=source_paths)
        response = self._client_call("fs_delete", source_entry_ids)
        return {
            "source_ids": source_entry_ids,
            "result": self._normalize(response),
        }

    def get_download_url(
        self,
        *,
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        target = self._resolve_remote(remote_id=remote_id, remote_path=remote_path, allow_root_default=False)
        metadata = self._fs_call("get_attr", target, refresh=refresh)
        if metadata["is_dir"]:
            raise ToolError("Download URL is only available for files.")
        url = self._fs_call("get_url", target, refresh=refresh)
        return {
            "url": self._normalize(url),
            "target": self._normalize(metadata),
        }

    def server_info(self) -> dict[str, Any]:
        return {
            "name": "115-MCP-Server",
            "description": "FastMCP server for 115 cloud storage using p115client.",
            "auth": self.auth_status(validate_remote=False),
            "targeting_rules": {
                "remote_id": "Use a numeric 115 file or directory id.",
                "remote_path": "Use an absolute 115 path such as /文档/项目.",
                "default_directory": "Directory-scoped tools default to the root directory when both id and path are omitted.",
            },
        }

    def client(self) -> P115Client:
        if self._client_instance is None:
            cookies_source: str | Path | None = self.settings.p115_cookies or self.settings.cookies_path
            if self.settings.cookies_path is not None and not self.settings.cookies_path.exists():
                raise ToolError(f"Configured cookies file does not exist: {self.settings.cookies_path}")
            if cookies_source is None and not self.settings.p115_allow_qrcode_login:
                raise ToolError(
                    "115 authentication is not configured. Set P115_COOKIES or P115_COOKIES_PATH first."
                )
            self._with_client_fallback(
                "initialize_client",
                lambda client, _platform: bool(self._call_backend(client.login_status)) or True,
                cookies_source=cookies_source,
            )
        return self._client_instance

    def fs(self) -> P115FileSystem:
        if self._fs_instance is None:
            self._fs_instance = self._get_fs_for_platform(self._active_platform)
        return self._fs_instance

    def _normalize_platform(self, platform: str | None) -> str | None:
        if platform is None:
            return None
        normalized = platform.strip()
        return normalized or None

    def _platform_candidates(self, preferred_platform: str | None = None) -> list[str | None]:
        ordered: list[str | None] = []
        for platform in (preferred_platform, self.settings.preferred_platform, *self.settings.fallback_platforms, *DEFAULT_PLATFORM_CANDIDATES):
            normalized = self._normalize_platform(platform)
            if normalized not in ordered:
                ordered.append(normalized)
        return ordered

    def _is_web_like_platform(self, platform: str | None) -> bool:
        return platform is None or platform in WEB_LIKE_PLATFORMS

    def _cookies_source(self, cookies_source: str | Path | None = None) -> str | Path | None:
        resolved = cookies_source if cookies_source is not None else self.settings.p115_cookies or self.settings.cookies_path
        if isinstance(resolved, Path) and not resolved.exists():
            raise ToolError(f"Configured cookies file does not exist: {resolved}")
        if resolved is None and not self.settings.p115_allow_qrcode_login:
            raise ToolError("115 authentication is not configured. Set P115_COOKIES or P115_COOKIES_PATH first.")
        return resolved

    def _get_client_for_platform(self, platform: str | None, cookies_source: str | Path | None = None) -> P115Client:
        normalized = self._normalize_platform(platform)
        if normalized not in self._client_cache:
            self._client_cache[normalized] = P115Client(
                self._cookies_source(cookies_source),
                check_for_relogin=self.settings.p115_check_for_relogin,
                app=normalized,
                console_qrcode=self.settings.p115_console_qrcode,
            )
        return self._client_cache[normalized]

    def _get_fs_for_platform(self, platform: str | None, cookies_source: str | Path | None = None) -> P115FileSystem:
        normalized = self._normalize_platform(platform)
        if normalized not in self._fs_cache:
            self._fs_cache[normalized] = P115FileSystem(self._get_client_for_platform(normalized, cookies_source=cookies_source))
        return self._fs_cache[normalized]

    def _remember_active_platform(self, platform: str | None, client: P115Client | None = None) -> None:
        normalized = self._normalize_platform(platform)
        self._active_platform = normalized
        self._client_instance = client or self._get_client_for_platform(normalized)
        self._fs_instance = self._get_fs_for_platform(normalized)

    def _with_client_fallback(self, operation: str, callback, *, preferred_platform: str | None = None, cookies_source: str | Path | None = None):
        errors: list[str] = []
        for platform in self._platform_candidates(preferred_platform):
            client = self._get_client_for_platform(platform, cookies_source=cookies_source)
            try:
                result = callback(client, platform)
                self._remember_active_platform(platform, client=client)
                return result
            except Exception as exc:  # noqa: BLE001
                formatted = self._format_backend_error(exc)
                errors.append(f"{platform or 'default'}: {formatted}")
                if not self._should_retry_platform(exc):
                    raise ToolError(formatted) from exc
        raise ToolError(f"{operation} failed across platforms: {' | '.join(errors)}")

    def _with_fs_fallback(self, operation: str, callback, *, preferred_platform: str | None = None):
        return self._with_client_fallback(
            operation,
            lambda _client, platform: callback(self._get_fs_for_platform(platform), platform),
            preferred_platform=preferred_platform,
        )

    def _client_call(self, method_name: str, *args, preferred_platform: str | None = None, check: bool = True, **kwargs):
        def attempt(client: P115Client, _platform: str | None):
            response = self._call_backend(getattr(client, method_name), *args, **kwargs)
            return self._call_backend(check_response, response) if check else response

        return self._with_client_fallback(method_name, attempt, preferred_platform=preferred_platform)

    def _fs_call(self, method_name: str, *args, preferred_platform: str | None = None, **kwargs):
        return self._with_fs_fallback(
            method_name,
            lambda fs, _platform: self._call_backend(getattr(fs, method_name), *args, **kwargs),
            preferred_platform=preferred_platform,
        )

    def _resolve_directory_id(self, *, remote_id: int | None, remote_path: str | None, allow_root_default: bool) -> int:
        if remote_id is not None and remote_path:
            raise ToolError("Provide either an id or a path, not both.")
        if remote_id is not None:
            return int(remote_id)
        if remote_path:
            if remote_path == "/":
                return 0

            def attempt(client: P115Client, platform: str | None):
                if self._is_web_like_platform(platform):
                    response = self._call_backend(client.fs_dir_getid, remote_path)
                else:
                    response = self._call_backend(client.fs_dir_getid_app, remote_path, app=platform or "android")
                checked = self._call_backend(check_response, response)
                return int(checked.get("id") or checked.get("cid") or checked["file_id"])

            return self._with_client_fallback("resolve_directory_id", attempt)
        if allow_root_default:
            return 0
        raise ToolError("A target id or path is required.")

    def _offline_add_urls_with_platform(self, client: P115Client, platform: str | None, *, open_payload: dict[str, Any], legacy_payload: dict[str, Any]):
        if self._is_web_like_platform(platform):
            try:
                return self._call_backend(check_response, self._call_backend(client.offline_add_urls, legacy_payload, type="web"))
            except Exception:
                return self._call_backend(check_response, self._call_backend(client.offline_add_urls, legacy_payload, type="ssp"))
        try:
            return self._call_backend(check_response, self._call_backend(client.offline_add_urls_open, open_payload))
        except Exception:
            try:
                return self._call_backend(check_response, self._call_backend(client.offline_add_urls, legacy_payload, type="ssp"))
            except Exception:
                return self._call_backend(check_response, self._call_backend(client.offline_add_urls, legacy_payload, type="web"))

    def _offline_list_tasks_with_platform(self, client: P115Client, platform: str | None, page: int):
        if self._is_web_like_platform(platform):
            return self._call_backend(check_response, self._call_backend(client.offline_list, {"page": page, "page_size": 1150}, type="web"))
        try:
            return self._call_backend(check_response, self._call_backend(client.offline_list_open, page))
        except Exception:
            return self._call_backend(check_response, self._call_backend(client.offline_list, {"page": page, "page_size": 1150}, type="ssp"))

    def _list_directory_entries(self, directory_id: int) -> list[dict[str, Any]]:
        payload = {"cid": directory_id, "limit": 7000, "offset": 0, "show_dir": 1}

        response = self._with_client_fallback(
            "list_directory_entries",
            lambda client, platform: self._call_backend(
                check_response,
                self._call_backend(
                    client.fs_files if self._is_web_like_platform(platform) else client.fs_files_app,
                    payload,
                    **({} if self._is_web_like_platform(platform) else {"app": platform or "android"}),
                ),
            ),
        )
        data = response.get("data", [])
        if isinstance(data, list):
            return data
        return []

    @classmethod
    def _should_retry_platform(cls, exc: Exception) -> bool:
        message = cls._format_backend_error(exc).lower()
        retry_markers = (
            "authorization",
            "请重新登录",
            "重新登录",
            "ip登录异常",
            "login",
            "cookie",
            "sign",
            "sso",
            "token",
            "forbidden",
            "401",
            "403",
            "99",
        )
        return any(marker in message for marker in retry_markers)

    @staticmethod
    def _normalize(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, URL):
            return str(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if isinstance(value, Mapping):
            return {str(key): P115Service._normalize(item) for key, item in value.items()}
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [P115Service._normalize(item) for item in value]
        attrs = getattr(value, "__dict__", None)
        if isinstance(attrs, dict) and attrs:
            normalized = {str(key): P115Service._normalize(item) for key, item in attrs.items()}
            if isinstance(value, str):
                normalized.setdefault("value", str(value))
            return normalized
        return repr(value)

    @staticmethod
    def _format_backend_error(exc: Exception) -> str:
        message = str(exc).strip()
        if message:
            return message
        return exc.__class__.__name__

    @classmethod
    def _call_backend(cls, func, /, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ToolError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ToolError(cls._format_backend_error(exc)) from exc

    def _resolve_many_sources(
        self,
        *,
        source_ids: list[int] | None,
        source_paths: list[str] | None,
    ) -> list[int]:
        if source_ids and source_paths:
            raise ToolError("Provide either source_ids or source_paths, not both.")
        if source_ids:
            return [int(item) for item in source_ids]
        if source_paths:
            resolved_ids: list[int] = []
            for path in source_paths:
                if not path.strip():
                    raise ToolError("source_paths must not contain empty values.")
                metadata = self._fs_call("get_attr", path)
                resolved_ids.append(int(metadata["id"]))
            return resolved_ids
        raise ToolError("Provide at least one source id or source path.")

    def _get_qrcode_session(self, session_id: str) -> dict[str, Any]:
        normalized_id = session_id.strip()
        if not normalized_id:
            raise ToolError("session_id must not be empty.")
        try:
            return self._qrcode_sessions[normalized_id]
        except KeyError as exc:
            raise ToolError(f"Unknown qrcode login session: {normalized_id}") from exc

    @staticmethod
    def _resolve_remote(
        *,
        remote_id: int | None,
        remote_path: str | None,
        allow_root_default: bool,
    ) -> int | str:
        if remote_id is not None and remote_path:
            raise ToolError("Provide either an id or a path, not both.")
        if remote_id is not None:
            return remote_id
        if remote_path:
            return remote_path
        if allow_root_default:
            return ""
        raise ToolError("A target id or path is required.")
