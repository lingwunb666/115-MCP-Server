from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastmcp.exceptions import ToolError
from p115client import P115Client

from mcp_115_server.config import Settings
from mcp_115_server.service import DEFAULT_PLATFORM_CANDIDATES, P115Service


class FakeClient:
    def __init__(self) -> None:
        self.search_payload: dict | None = None
        self.dir_getid_payload: str | None = None
        self.move_payload: tuple[list[int], int] | None = None
        self.copy_payload: tuple[list[int], int] | None = None
        self.delete_payload: list[int] | None = None
        self.offline_urls_payload: dict | None = None
        self.offline_torrent_payload: dict | None = None
        self.offline_list_payload: int | None = None
        self.offline_list_legacy_payload: dict | None = None
        self.offline_urls_legacy_payload: dict | None = None
        self.offline_remove_payload: dict | None = None
        self.offline_remove_legacy_payload: dict | None = None
        self.fail_offline_remove_open: bool = False
        self.offline_clear_payload: int | None = None
        self.offline_download_path_set_payload: int | None = None
        self.offline_restart_payload: str | None = None
        self.offline_task_count_payload: int | None = None
        self.recyclebin_info_payload: int | None = None
        self.recyclebin_revert_payload: list[int] | None = None
        self.recyclebin_clean_payload: dict | None = None
        self.share_info_payload: str | None = None
        self.share_access_payload: str | None = None
        self.share_recvcode_payload: str | None = None
        self.share_receive_payload: dict | None = None
        self.share_download_url_payload: tuple[dict, str, bool, str] | None = None
        self.fs_mkdir_payload: tuple[dict, int | str] | None = None
        self.fs_mkdir_app_payload: tuple[dict, int | str, str] | None = None
        self.fs_files_payload: dict | None = None
        self.fs_files_app_payload: tuple[dict, str] | None = None
        self.fail_offline_open: bool = False
        self.fail_fs_mkdir_web: bool = False
        self.offline_tasks = [{"info_hash": "abc", "status": 1}, {"info_hash": "def", "status": 1}]
        self.offline_pages: list[list[dict]] | None = None

    def login_status(self) -> bool:
        return True

    def fs_search(self, payload: dict) -> dict:
        self.search_payload = payload
        return {"state": True, "data": {"count": 1, "data": [{"id": 7, "name": "demo.txt"}]}}

    def fs_storage_info(self) -> dict:
        return {"state": True, "data": {"total": "1024", "used": "128", "available": "896"}}

    def fs_dir_getid(self, payload: str) -> dict:
        self.dir_getid_payload = payload
        return {"state": True, "id": 12, "path": payload}

    def fs_dir_getid_app(self, payload: str, app: str = "android") -> dict:
        self.dir_getid_payload = payload
        return {"state": True, "id": 12, "path": payload, "app": app}

    def fs_mkdir(self, payload: dict, pid: int | str = 0) -> dict:
        if self.fail_fs_mkdir_web:
            raise RuntimeError("web mkdir failed")
        self.fs_mkdir_payload = (payload, pid)
        return {"state": True, "cid": 3, "cname": payload.get("cname", ""), "pid": pid}

    def fs_mkdir_app(self, payload: dict, pid: int | str = 0, app: str = "android") -> dict:
        self.fs_mkdir_app_payload = (payload, pid, app)
        return {"state": True, "cid": 3, "cname": payload.get("cname", ""), "pid": pid, "app": app}

    def fs_files(self, payload: dict) -> dict:
        self.fs_files_payload = payload
        return {"state": True, "data": [{"id": 1, "name": "a", "is_dir": False}, {"id": 2, "name": "b", "is_dir": True}]}

    def fs_files_app(self, payload: dict, app: str = "android") -> dict:
        self.fs_files_app_payload = (payload, app)
        return {"state": True, "data": [{"id": 1, "name": "a", "is_dir": False}, {"id": 2, "name": "b", "is_dir": True}]}

    def fs_move(self, payload: list[int], pid: int = 0) -> dict:
        self.move_payload = (payload, pid)
        return {"state": True, "data": {"moved": payload, "pid": pid}}

    def fs_copy(self, payload: list[int], pid: int = 0) -> dict:
        self.copy_payload = (payload, pid)
        return {"state": True, "data": {"copied": payload, "pid": pid}}

    def fs_delete(self, payload: list[int]) -> dict:
        self.delete_payload = payload
        return {"state": True, "data": {"deleted": payload}}

    def user_info(self) -> dict:
        return {"state": True, "data": {"user_id": 11500, "nickname": "demo-user"}}

    def fs_index_info(self, payload: int = 0) -> dict:
        return {"state": True, "data": {"include_space_numbers": payload, "files": 99}}

    def offline_add_urls_open(self, payload: dict) -> dict:
        if self.fail_offline_open:
            raise RuntimeError("authorization")
        self.offline_urls_payload = payload
        return {"state": True, "data": {"task_ids": [1], "payload": payload}}

    def offline_torrent_info_open(self, payload: dict) -> dict:
        return {"state": True, "data": {"files": [{"index": 0, "name": "demo.mkv"}], "payload": payload}}

    def offline_add_torrent_open(self, payload: dict) -> dict:
        self.offline_torrent_payload = payload
        return {"state": True, "data": {"created": True, "payload": payload}}

    def offline_list_open(self, payload: int = 1) -> dict:
        self.offline_list_payload = payload
        if self.offline_pages is not None:
            page = max(int(payload), 1)
            page_count = len(self.offline_pages)
            page_tasks = list(self.offline_pages[page - 1]) if page <= page_count else []
            total = sum(len(items) for items in self.offline_pages)
            return {"state": True, "data": {"count": total, "page_count": page_count, "tasks": page_tasks}}
        return {"state": True, "data": {"count": len(self.offline_tasks), "page_count": 1, "tasks": list(self.offline_tasks)}}

    def offline_list(self, payload: dict, type: str = "web") -> dict:
        self.offline_list_legacy_payload = payload
        if self.offline_pages is not None:
            page = max(int(payload.get("page", 1)), 1)
            page_count = len(self.offline_pages)
            page_tasks = list(self.offline_pages[page - 1]) if page <= page_count else []
            total = sum(len(items) for items in self.offline_pages)
            return {"state": True, "count": total, "page_count": page_count, "tasks": page_tasks}
        return {"state": True, "count": len(self.offline_tasks), "page_count": 1, "tasks": list(self.offline_tasks)}

    def offline_add_urls(self, payload: dict, method: str = "POST", type: str = "ssp") -> dict:
        self.offline_urls_legacy_payload = {**payload, "__type__": type}
        return {"state": True, "data": {"added": True, "payload": payload, "type": type}}

    def offline_remove_open(self, payload: dict) -> dict:
        if self.fail_offline_remove_open:
            raise RuntimeError("authorization")
        self.offline_remove_payload = payload
        info_hash = payload.get("info_hash", "")
        self.offline_tasks = [task for task in self.offline_tasks if task.get("info_hash") != info_hash]
        return {"state": True, "data": {"removed": True}}

    def offline_remove(self, payload: dict, method: str = "POST", type: str = "web") -> dict:
        self.offline_remove_legacy_payload = payload
        hashes = [value for key, value in payload.items() if key.startswith("hash[")]
        self.offline_tasks = [task for task in self.offline_tasks if task.get("info_hash") not in hashes]
        return {"state": True, "data": {"removed": True, "count": 2}}

    def offline_clear_open(self, payload: int = 0) -> dict:
        self.offline_clear_payload = payload
        return {"state": True, "data": {"cleared": True, "flag": payload}}

    def offline_quota_info_open(self) -> dict:
        return {"state": True, "data": {"quota": 5, "used": 1}}

    def offline_sign(self) -> dict:
        return {"state": True, "data": {"sign": "sig", "time": 123}}

    def offline_quota_package_array(self) -> dict:
        return {"state": True, "data": [{"package": "basic"}]}

    def offline_quota_package_info(self) -> dict:
        return {"state": True, "data": {"package": "basic", "remaining": 1}}

    def offline_download_path(self) -> dict:
        return {"state": True, "data": [{"file_id": 12, "file_name": "docs"}]}

    def offline_download_path_set(self, payload: int) -> dict:
        self.offline_download_path_set_payload = payload
        return {"state": True, "data": {"file_id": payload}}

    def offline_restart(self, payload: str) -> dict:
        self.offline_restart_payload = payload
        return {"state": True, "data": {"restarted": payload}}

    def offline_task_count(self, payload: int = 0) -> dict:
        self.offline_task_count_payload = payload
        return {"state": True, "data": {"count": 2, "flag": payload}}

    def recyclebin_list(self, payload: dict) -> dict:
        return {"state": True, "data": [{"rid": 1, "name": "trash.txt"}], "offset": payload["offset"], "limit": payload["limit"]}

    def recyclebin_info(self, payload: int) -> dict:
        self.recyclebin_info_payload = payload
        return {"state": True, "data": {"rid": payload, "name": "trash.txt"}}

    def recyclebin_revert(self, payload: list[int]) -> dict:
        self.recyclebin_revert_payload = payload
        return {"state": True, "data": {"restored": payload}}

    def recyclebin_clean(self, payload: dict) -> dict:
        self.recyclebin_clean_payload = payload
        return {"state": True, "data": {"cleaned": True, "payload": payload}}

    def fs_label_list(self, payload: dict) -> dict:
        return {"state": True, "data": [{"id": 1, "name": "important"}], "payload": payload}

    def fs_label_set(self, payload: int, label: str = "") -> dict:
        return {"state": True, "data": {"file_id": payload, "label": label}}

    def share_list(self, payload: dict) -> dict:
        return {"state": True, "data": [{"share_code": "code1"}], "payload": payload}

    def share_info(self, payload: str) -> dict:
        self.share_info_payload = payload
        return {"state": True, "data": {"share_code": payload}}

    def share_recvcode(self, payload: str) -> dict:
        self.share_recvcode_payload = payload
        return {"state": True, "data": {"receive_code": "abcd"}}

    def share_receive(self, payload: dict) -> dict:
        self.share_receive_payload = payload
        return {"state": True, "data": {"received": True}}

    def share_download_url(self, payload: dict, url: str = "", strict: bool = True, app: str = "") -> str:
        self.share_download_url_payload = (payload, url, strict, app)
        return "https://example.com/share-download"

    def share_access_user_list(self, payload: str) -> dict:
        self.share_access_payload = payload
        return {"state": True, "data": [{"user": "demo"}]}

    def share_notlogin_dl_quota(self) -> dict:
        return {"state": True, "data": {"quota": 3}}


class FakeFS:
    def __init__(self) -> None:
        self.fail_message: str | None = None
        self.fail_during_glob: str | None = None
        self.fail_during_walk: str | None = None

    def _maybe_fail(self):
        if self.fail_message:
            raise RuntimeError(self.fail_message)

    def get_attr(self, target, refresh: bool = False):
        self._maybe_fail()
        if target in ("", "/"):
            return {"id": 0, "name": "/", "is_dir": True}
        if target == "/docs":
            return {"id": 12, "name": "docs", "is_dir": True}
        if target == "/docs/demo.txt":
            return {"id": 21, "name": "demo.txt", "is_dir": False, "pickcode": "abc", "size": 10}
        return {"id": 99, "name": "file.txt", "is_dir": False}

    def readdir(self, target, refresh: bool = False):
        self._maybe_fail()
        return [{"id": 1, "name": "a", "is_dir": False}, {"id": 2, "name": "b", "is_dir": True}]

    def mkdir(self, parent, name: str, refresh: bool = False):
        self._maybe_fail()
        return {"id": 3, "name": name, "parent_id": 0, "is_dir": True}

    def upload(self, remote_dir, file: str, filename: str = "", refresh: bool = False):
        self._maybe_fail()
        return {"id": 4, "name": filename or Path(file).name, "parent_id": 0, "is_dir": False}

    def download(self, target, path: str, mode: str, refresh: bool = False):
        self._maybe_fail()
        return path, 128

    def move(self, source, to_dir="", refresh: bool = False):
        self._maybe_fail()
        return {"source": source, "to_dir": to_dir, "moved": True}

    def copy(self, source, to_dir="", refresh: bool = False):
        self._maybe_fail()
        return {"source": source, "to_dir": to_dir, "copied": True}

    def rename(self, target, name: str, refresh: bool = False):
        self._maybe_fail()
        return {"id": 5, "name": name, "is_dir": False}

    def remove(self, target, refresh: bool = False):
        self._maybe_fail()
        return {"id": 6, "removed": True}

    def get_url(self, target, refresh: bool = False):
        self._maybe_fail()
        return "https://example.com/file"

    def exists(self, target, refresh: bool = False):
        self._maybe_fail()
        return target in ("", "/", "/docs", "/docs/demo.txt", 12, 21)

    def dirlen(self, target, refresh: bool = False):
        self._maybe_fail()
        return 2

    def get_ancestors(self, target, refresh: bool = False):
        self._maybe_fail()
        return [{"id": 0, "name": "/"}, {"id": 12, "name": "docs"}]

    def glob(self, pattern: str = "*", top="", ignore_case: bool = False, refresh: bool = False):
        self._maybe_fail()
        yield {"id": 21, "name": "demo.txt", "is_dir": False}
        if self.fail_during_glob:
            raise RuntimeError(self.fail_during_glob)
        yield {"id": 22, "name": "demo-2.txt", "is_dir": False}

    def walk(self, top="", topdown: bool = True, min_depth: int = 1, max_depth: int = -1, refresh: bool = False):
        self._maybe_fail()
        yield (
            {"id": 12, "name": "docs", "is_dir": True},
            [{"id": 13, "name": "subdir", "is_dir": True}],
            [{"id": 21, "name": "demo.txt", "is_dir": False}],
        )
        if self.fail_during_walk:
            raise RuntimeError(self.fail_during_walk)

    def stat(self, target, refresh: bool = False):
        self._maybe_fail()
        return {"st_mode": 33188, "st_size": 10}


class P115ServiceTests(unittest.TestCase):
    def make_service(self) -> P115Service:
        service = P115Service(Settings(P115_COOKIES="UID=dummy; CID=dummy; SEID=dummy; KID=dummy"))
        fake_client = FakeClient()
        fake_fs = FakeFS()
        service._client_instance = fake_client
        service._fs_instance = fake_fs
        for platform in [None, "web", "desktop", "harmony", "android", "apple_tv"]:
            service._client_cache[platform] = fake_client
            service._fs_cache[platform] = fake_fs
        service._active_platform = "web"
        service._cookie_source_signature = ("inline", "UID=dummy; CID=dummy; SEID=dummy; KID=dummy")
        return service

    def test_cookie_file_change_rebuilds_cached_client(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cookie_file = Path(temp_dir) / "115-cookies.txt"
            cookie_file.write_text("UID=old; CID=old; SEID=old; KID=old", encoding="utf-8")
            class CapturingClient:
                def __init__(self, cookies=None, check_for_relogin=False, app=None, console_qrcode=True):
                    self.cookies = cookies
                    self.app = app

            with patch.dict(os.environ, {"P115_COOKIES": "", "P115_COOKIES_PATH": ""}, clear=False), patch("mcp_115_server.service.P115Client", CapturingClient):
                service = P115Service(Settings(P115_COOKIES_PATH=str(cookie_file), P115_COOKIES=None))
                first = service._get_client_for_platform("web")
                cookie_file.write_text("UID=new; CID=new; SEID=new; KID=new", encoding="utf-8")
                second = service._get_client_for_platform("web")

            self.assertIsNot(first, second)
            self.assertEqual(str(first.cookies), str(cookie_file))
            self.assertEqual(str(second.cookies), str(cookie_file))

    def test_remember_active_platform_uses_client_inferred_login_app(self) -> None:
        service = P115Service(Settings(P115_COOKIES="UID=dummy; CID=dummy; SEID=dummy; KID=dummy"))

        class DummyCookies:
            login_app = "web"

        class DummyClient:
            cookies_str = DummyCookies()

        service._remember_active_platform(None, client=DummyClient())
        self.assertEqual(service._active_platform, "web")

    def test_auth_status_reports_missing_configuration(self) -> None:
        service = P115Service(Settings())
        status = service.auth_status()
        self.assertFalse(status["configured"])
        self.assertEqual(status["cookies_source"], "missing")

    def test_resolve_remote_rejects_conflicting_inputs(self) -> None:
        with self.assertRaises(ToolError):
            P115Service._resolve_remote(remote_id=1, remote_path="/docs", allow_root_default=False)

    def test_parse_remote_id_accepts_long_decimal_string(self) -> None:
        parsed = P115Service._parse_remote_id("3398357158620823140", "remote_id")
        self.assertEqual(parsed, 3398357158620823140)

    def test_parse_remote_id_rejects_unsafe_long_number(self) -> None:
        with self.assertRaises(ToolError):
            P115Service._parse_remote_id(3398357158620823140, "remote_id")

    def test_parse_remote_id_rejects_non_decimal_string(self) -> None:
        with self.assertRaises(ToolError):
            P115Service._parse_remote_id("3398abc", "remote_id")

    def test_list_directory_defaults_to_root(self) -> None:
        service = self.make_service()
        result = service.list_directory()
        self.assertEqual(result["directory"]["id"], "0")
        self.assertEqual(result["count"], 2)
        self.assertEqual(service.client().fs_files_payload["cid"], 0)

    def test_search_uses_directory_id_scope(self) -> None:
        service = self.make_service()
        result = service.search_entries("demo", directory_path="/docs", limit=10, offset=0)
        self.assertEqual(result["scope"]["id"], "12")
        self.assertEqual(service.client().search_payload["cid"], 12)

    def test_upload_validates_local_file(self) -> None:
        service = self.make_service()
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            temp_path = handle.name
        try:
            result = service.upload_local_file(temp_path)
            self.assertEqual(result["uploaded"]["name"], Path(temp_path).name)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_download_returns_written_size(self) -> None:
        service = self.make_service()
        with tempfile.TemporaryDirectory() as temp_dir:
            target = str(Path(temp_dir) / "out.txt")
            result = service.download_file(target, remote_path="/docs/file.txt")
            self.assertEqual(result["bytes_written"], 128)

    def test_get_download_url_returns_stable_object_shape(self) -> None:
        service = self.make_service()
        result = service.get_download_url(remote_path="/docs/demo.txt")
        self.assertEqual(result["url"], "https://example.com/file")
        self.assertEqual(result["target"]["name"], "demo.txt")
        self.assertEqual(result["target"]["id"], "21")

    def test_missing_cookies_file_fails_fast(self) -> None:
        settings = Settings(P115_COOKIES_PATH="C:/definitely-missing/115-cookies.txt")
        service = P115Service(settings)
        with self.assertRaises(ToolError):
            service.client()

    def test_auth_status_normalizes_remote_error(self) -> None:
        service = self.make_service()

        class BrokenClient(FakeClient):
            def login_status(self) -> bool:
                raise RuntimeError("remote failed")

        broken = BrokenClient()
        service._client_instance = broken
        for platform in [None, *DEFAULT_PLATFORM_CANDIDATES]:
            service._client_cache[platform] = broken
        status = service.auth_status(validate_remote=True)
        self.assertFalse(status["remote_logged_in"])
        self.assertIn("remote failed", status["remote_error"])

    def test_backend_errors_are_wrapped_as_tool_errors(self) -> None:
        service = self.make_service()
        service._fs_instance.fail_message = "backend boom"
        with self.assertRaises(ToolError):
            service.list_directory()

    def test_resolve_directory_returns_lookup_result(self) -> None:
        service = self.make_service()
        result = service.resolve_directory(remote_path="/docs")
        self.assertEqual(result["result"]["id"], 12)
        self.assertEqual(service.client().dir_getid_payload, "/docs")

    def test_create_directory_uses_web_mkdir_when_platform_is_web_like(self) -> None:
        service = self.make_service()
        result = service.create_directory("demo", parent_id=12)
        self.assertEqual(service.client().fs_mkdir_payload, ({"cname": "demo"}, 12))
        self.assertEqual(result["cid"], "3")

    def test_create_directory_prefers_web_mkdir_even_when_active_platform_is_android(self) -> None:
        service = self.make_service()
        service._active_platform = "android"
        result = service.create_directory("demo", parent_id=12)
        self.assertEqual(service.client().fs_mkdir_payload, ({"cname": "demo"}, 12))
        self.assertIsNone(service.client().fs_mkdir_app_payload)
        self.assertEqual(result["cid"], "3")

    def test_create_directory_stops_on_authorization_error_without_cross_platform_retry(self) -> None:
        service = self.make_service()
        service.client().fail_fs_mkdir_web = False

        def fail_web_mkdir(payload: dict, pid: int | str = 0) -> dict:
            raise RuntimeError("authorization")

        service.client().fs_mkdir = fail_web_mkdir  # type: ignore[method-assign]
        with self.assertRaises(ToolError):
            service.create_directory("demo", parent_id=12)

    def test_get_storage_info_returns_normalized_payload(self) -> None:
        service = self.make_service()
        result = service.get_storage_info()
        self.assertEqual(result["data"]["available"], "896")

    def test_batch_move_entries_with_paths(self) -> None:
        service = self.make_service()
        result = service.batch_move_entries(source_paths=["/docs/demo.txt"], destination_dir_path="/docs")
        self.assertEqual(result["source_ids"], [21])
        self.assertEqual(service.client().move_payload, ([21], 12))

    def test_batch_copy_entries_with_ids(self) -> None:
        service = self.make_service()
        result = service.batch_copy_entries(source_ids=["21", "22"], destination_dir_path="/docs")
        self.assertEqual(result["source_ids"], [21, 22])
        self.assertEqual(service.client().copy_payload, ([21, 22], 12))

    def test_move_and_copy_entry_use_fs_fallback_calls(self) -> None:
        service = self.make_service()
        moved = service.move_entry(source_path="/docs/demo.txt", destination_dir_path="/docs")
        copied = service.copy_entry(source_path="/docs/demo.txt", destination_dir_path="/docs")
        self.assertTrue(moved["moved"])
        self.assertTrue(copied["copied"])

    def test_batch_remove_entries_with_ids(self) -> None:
        service = self.make_service()
        result = service.batch_remove_entries(source_ids=["21", "22"])
        self.assertEqual(result["source_ids"], [21, 22])
        self.assertEqual(service.client().delete_payload, [21, 22])

    def test_batch_operations_require_sources(self) -> None:
        service = self.make_service()
        with self.assertRaises(ToolError):
            service.batch_remove_entries()

    def test_path_exists_returns_boolean(self) -> None:
        service = self.make_service()
        result = service.path_exists(remote_path="/docs")
        self.assertTrue(result["exists"])

    def test_count_directory_returns_count(self) -> None:
        service = self.make_service()
        result = service.count_directory(remote_path="/docs")
        self.assertEqual(result["count"], 2)

    def test_get_ancestors_returns_chain(self) -> None:
        service = self.make_service()
        result = service.get_ancestors(remote_path="/docs/demo.txt")
        self.assertEqual(result["ancestors"][0]["id"], "0")

    def test_glob_entries_returns_bounded_results(self) -> None:
        service = self.make_service()
        result = service.glob_entries("*.txt", directory_path="/docs", limit=1)
        self.assertEqual(result["count"], 1)

    def test_walk_directory_returns_nodes(self) -> None:
        service = self.make_service()
        result = service.walk_directory(remote_path="/docs", max_depth=2, limit=10)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["nodes"][0]["directory"]["name"], "docs")

    def test_get_stat_returns_stat_payload(self) -> None:
        service = self.make_service()
        result = service.get_stat(remote_path="/docs/demo.txt")
        self.assertEqual(result["stat"]["st_size"], 10)

    def test_get_account_info_returns_user_payload(self) -> None:
        service = self.make_service()
        result = service.get_account_info()
        self.assertEqual(result["data"]["nickname"], "demo-user")

    def test_get_index_info_forwards_flag(self) -> None:
        service = self.make_service()
        result = service.get_index_info(include_space_numbers=True)
        self.assertEqual(result["data"]["include_space_numbers"], 1)

    def test_offline_add_urls_creates_payload(self) -> None:
        service = self.make_service()
        service.settings.p115_debug_logging = True
        result = service.offline_add_urls(["magnet:?xt=urn:btih:test"], remote_dir_id=12)
        self.assertEqual(service.client().offline_urls_legacy_payload["wp_path_id"], 12)
        self.assertEqual(result["urls"][0], "magnet:?xt=urn:btih:test")

    def test_offline_add_urls_falls_back_to_legacy_interface(self) -> None:
        service = self.make_service()
        service.settings.p115_debug_logging = True
        service.client().fail_offline_open = True
        result = service.offline_add_urls(["magnet:?xt=urn:btih:test"], remote_dir_id=12)
        self.assertEqual(result["result"]["state"], True)
        self.assertEqual(service.client().offline_urls_legacy_payload["wp_path_id"], 12)

    def test_offline_get_torrent_info_returns_data(self) -> None:
        service = self.make_service()
        result = service.offline_get_torrent_info(torrent_sha1="sha1", pick_code="pick")
        self.assertEqual(result["data"]["files"][0]["name"], "demo.mkv")

    def test_offline_add_torrent_serializes_wanted_indexes(self) -> None:
        service = self.make_service()
        service.settings.p115_debug_logging = True
        result = service.offline_add_torrent(torrent_sha1="sha1", pick_code="pick", wanted_indexes=[0, 2], remote_dir_id=12)
        self.assertEqual(service.client().offline_torrent_payload["wanted"], "0,2")
        self.assertTrue(result["data"]["created"])

    def test_offline_list_tasks_unwraps_data(self) -> None:
        service = self.make_service()
        result = service.offline_list_tasks(page=2)
        self.assertEqual(service.client().offline_list_legacy_payload["page"], 2)
        self.assertEqual(result["count"], 2)

    def test_offline_list_tasks_advanced_maps_status(self) -> None:
        service = self.make_service()
        result = service.offline_list_tasks_advanced(page=1, page_size=20, status="completed")
        self.assertEqual(service.client().offline_list_legacy_payload["stat"], 11)
        self.assertEqual(result["count"], 2)

    def test_offline_find_tasks_filters_by_query(self) -> None:
        service = self.make_service()
        result = service.offline_find_tasks(query="abc", limit=10, offset=0)
        self.assertEqual(result["total_matches"], 1)
        self.assertEqual(result["tasks"][0]["info_hash"], "abc")

    def test_offline_find_tasks_filters_by_status(self) -> None:
        service = self.make_service()
        result = service.offline_find_tasks(status="completed", limit=10, offset=0)
        self.assertEqual(result["total_matches"], 2)

    def test_offline_find_tasks_stops_after_collecting_requested_window(self) -> None:
        service = self.make_service()
        service.client().offline_pages = [
            [{"info_hash": "match-1", "name": "episode 1"}],
            [{"info_hash": "match-2", "name": "episode 2"}],
            [{"info_hash": "match-3", "name": "episode 3"}],
        ]

        result = service.offline_find_tasks(query="episode", limit=1, offset=0)

        self.assertEqual([task["info_hash"] for task in result["tasks"]], ["match-1"])
        self.assertFalse(result["scan_complete"])
        self.assertIsNone(result["total_matches"])
        self.assertEqual(service.client().offline_list_legacy_payload["page"], 1)

    def test_offline_find_tasks_continues_until_offset_window_is_filled(self) -> None:
        service = self.make_service()
        service.client().offline_pages = [
            [{"info_hash": "match-1", "name": "episode 1"}],
            [{"info_hash": "match-2", "name": "episode 2"}],
            [{"info_hash": "match-3", "name": "episode 3"}],
        ]

        result = service.offline_find_tasks(query="episode", limit=1, offset=1)

        self.assertEqual([task["info_hash"] for task in result["tasks"]], ["match-2"])
        self.assertFalse(result["scan_complete"])
        self.assertIsNone(result["total_matches"])
        self.assertEqual(service.client().offline_list_legacy_payload["page"], 2)

    def test_offline_remove_task_forwards_delete_flag(self) -> None:
        service = self.make_service()
        result = service.offline_remove_task("abc", delete_source_file=True)
        self.assertTrue(result["removed"])
        self.assertEqual(service.client().offline_remove_legacy_payload["flag"], 1)

    def test_offline_remove_tasks_builds_legacy_payload(self) -> None:
        service = self.make_service()
        result = service.offline_remove_tasks(["abc", "def"], delete_source_file=True)
        self.assertEqual(result["removed"], ["abc", "def"])
        self.assertEqual(result["remaining"], [])
        self.assertEqual(result["info_hashes"], ["abc", "def"])

    def test_offline_remove_task_falls_back_when_open_delete_fails(self) -> None:
        service = self.make_service()
        service._active_platform = "android"
        service.client().fail_offline_remove_open = True
        result = service.offline_remove_task("abc")
        self.assertTrue(result["removed"])

    def test_offline_clear_tasks_maps_scope(self) -> None:
        service = self.make_service()
        result = service.offline_clear_tasks("failed")
        self.assertEqual(service.client().offline_clear_payload, 2)
        self.assertEqual(result["scope"], "failed")

    def test_offline_get_quota_info_returns_payload(self) -> None:
        service = self.make_service()
        result = service.offline_get_quota_info()
        self.assertEqual(result["data"]["quota"], 5)

    def test_offline_get_sign_info_returns_payload(self) -> None:
        service = self.make_service()
        result = service.offline_get_sign_info()
        self.assertEqual(result["data"]["sign"], "sig")

    def test_offline_get_quota_package_array_returns_payload(self) -> None:
        service = self.make_service()
        result = service.offline_get_quota_package_array()
        self.assertEqual(result["data"][0]["package"], "basic")

    def test_offline_get_quota_package_info_returns_payload(self) -> None:
        service = self.make_service()
        result = service.offline_get_quota_package_info()
        self.assertEqual(result["data"]["remaining"], 1)

    def test_list_recycle_bin_returns_payload(self) -> None:
        service = self.make_service()
        result = service.list_recycle_bin(limit=10, offset=1)
        self.assertEqual(result["offset"], 1)

    def test_get_recycle_bin_entry_returns_entry(self) -> None:
        service = self.make_service()
        result = service.get_recycle_bin_entry(9)
        self.assertEqual(service.client().recyclebin_info_payload, 9)
        self.assertEqual(result["data"]["rid"], "9")

    def test_restore_recycle_bin_entries_returns_ids(self) -> None:
        service = self.make_service()
        result = service.restore_recycle_bin_entries([1, 2])
        self.assertEqual(service.client().recyclebin_revert_payload, [1, 2])
        self.assertEqual(result["entry_ids"], ["1", "2"])

    def test_list_labels_returns_payload(self) -> None:
        service = self.make_service()
        result = service.list_labels(keyword="imp", limit=10)
        self.assertEqual(result["data"][0]["name"], "important")

    def test_set_entry_labels_returns_mapping(self) -> None:
        service = self.make_service()
        result = service.set_entry_labels(remote_id=21, label_ids=[1, 2])
        self.assertEqual(result["label_ids"], ["1", "2"])

    def test_set_entry_labels_allows_empty_list_for_clear(self) -> None:
        service = self.make_service()
        result = service.set_entry_labels(remote_id=21, label_ids=[])
        self.assertEqual(result["label_ids"], [])

    def test_glob_entries_wraps_iteration_failures(self) -> None:
        service = self.make_service()
        service._fs_instance.fail_during_glob = "glob broke"
        with self.assertRaises(ToolError):
            service.glob_entries("*.txt", directory_path="/docs", limit=5)

    def test_walk_directory_wraps_iteration_failures(self) -> None:
        service = self.make_service()
        service._fs_instance.fail_during_walk = "walk broke"
        with self.assertRaises(ToolError):
            service.walk_directory(remote_path="/docs", max_depth=2, limit=10)

    def test_list_shares_returns_payload(self) -> None:
        service = self.make_service()
        result = service.list_shares(limit=10)
        self.assertEqual(result["data"][0]["share_code"], "code1")

    def test_get_share_info_returns_payload(self) -> None:
        service = self.make_service()
        result = service.get_share_info("code1")
        self.assertEqual(service.client().share_info_payload, "code1")
        self.assertEqual(result["data"]["share_code"], "code1")

    def test_list_share_access_users_returns_payload(self) -> None:
        service = self.make_service()
        result = service.list_share_access_users("code1")
        self.assertEqual(service.client().share_access_payload, "code1")
        self.assertEqual(result["data"][0]["user"], "demo")

    def test_get_share_download_quota_returns_payload(self) -> None:
        service = self.make_service()
        result = service.get_share_download_quota()
        self.assertEqual(result["data"]["quota"], 3)

    def test_offline_get_download_paths_returns_payload(self) -> None:
        service = self.make_service()
        result = service.offline_get_download_paths()
        self.assertEqual(result["data"][0]["file_id"], "12")

    def test_offline_set_download_path_resolves_directory(self) -> None:
        service = self.make_service()
        result = service.offline_set_download_path(remote_dir_path="/docs")
        self.assertEqual(service.client().offline_download_path_set_payload, 12)
        self.assertEqual(result["directory"]["id"], "12")

    def test_offline_restart_task_forwards_info_hash(self) -> None:
        service = self.make_service()
        result = service.offline_restart_task("abc")
        self.assertEqual(service.client().offline_restart_payload, "abc")
        self.assertEqual(result["data"]["restarted"], "abc")

    def test_offline_get_task_count_returns_payload(self) -> None:
        service = self.make_service()
        result = service.offline_get_task_count(flag=1)
        self.assertEqual(service.client().offline_task_count_payload, 1)
        self.assertEqual(result["data"]["count"], 2)

    def test_clear_recycle_bin_accepts_specific_ids(self) -> None:
        service = self.make_service()
        result = service.clear_recycle_bin(entry_ids=[1, 2], password="123456")
        self.assertEqual(service.client().recyclebin_clean_payload["tid"], "1,2")
        self.assertEqual(result["entry_ids"], ["1", "2"])

    def test_get_share_receive_code_returns_payload(self) -> None:
        service = self.make_service()
        result = service.get_share_receive_code("code1")
        self.assertEqual(service.client().share_recvcode_payload, "code1")
        self.assertEqual(result["data"]["receive_code"], "abcd")

    def test_receive_share_entries_builds_payload(self) -> None:
        service = self.make_service()
        result = service.receive_share_entries(
            share_code="code1",
            receive_code="pass",
            file_ids=[21, 22],
            remote_dir_path="/docs",
            is_check=True,
        )
        self.assertEqual(service.client().share_receive_payload["file_id"], "21,22")
        self.assertEqual(service.client().share_receive_payload["cid"], 12)
        self.assertTrue(result["result"]["data"]["received"])

    def test_get_share_download_url_accepts_share_url(self) -> None:
        service = self.make_service()
        result = service.get_share_download_url(file_id=21, share_url="https://115.com/s/test")
        self.assertEqual(result["url"], "https://example.com/share-download")
        self.assertEqual(result["mode"], "share_url")

    def test_get_share_download_url_requires_receive_code_for_share_code_mode(self) -> None:
        service = self.make_service()
        with self.assertRaises(ToolError):
            service.get_share_download_url(file_id=21, share_code="code1")

    def test_start_qrcode_login_returns_session_and_url(self) -> None:
        service = P115Service(Settings())
        with patch.object(P115Client, "login_qrcode_token", return_value={"state": True, "data": {"uid": "u1", "time": 1, "sign": "sig", "qrcode": "https://qr.example"}}):
            result = service.start_qrcode_login(app="android")
        self.assertEqual(result["app"], "android")
        self.assertEqual(result["qrcode_url"], "https://qr.example")
        self.assertTrue(result["session_id"])

    def test_get_qrcode_login_status_uses_stored_session(self) -> None:
        service = P115Service(Settings())
        service._qrcode_sessions["s1"] = {"app": "android", "uid": "u1", "token": {"uid": "u1", "time": 1, "sign": "sig"}, "qrcode_url": "https://qr.example"}
        with patch.object(P115Client, "login_qrcode_scan_status", return_value={"state": True, "data": {"status": 1}}):
            result = service.get_qrcode_login_status("s1")
        self.assertEqual(result["status_name"], "scanned")

    def test_finish_qrcode_login_returns_cookies_and_saves_file(self) -> None:
        service = P115Service(Settings())
        service._qrcode_sessions["s1"] = {"app": "android", "uid": "u1", "token": {"uid": "u1", "time": 1, "sign": "sig"}, "qrcode_url": "https://qr.example"}
        with tempfile.TemporaryDirectory() as temp_dir:
            out = str(Path(temp_dir) / "115-cookies.txt")
            with patch.object(P115Client, "login_qrcode_scan_result", return_value={"state": True, "data": {"cookie": "UID=1; CID=2; SEID=3; KID=4"}}):
                result = service.finish_qrcode_login("s1", output_path=out)
            self.assertEqual(result["cookies"], "UID=1; CID=2; SEID=3; KID=4")
            self.assertTrue(Path(out).exists())

    def test_finish_qrcode_login_activates_cookies_without_output_path(self) -> None:
        service = P115Service(Settings(P115_COOKIES="UID=old; CID=old; SEID=old; KID=old"))
        service._qrcode_sessions["s1"] = {"app": "android", "uid": "u1", "token": {"uid": "u1", "time": 1, "sign": "sig"}, "qrcode_url": "https://qr.example"}
        with patch.object(P115Client, "login_qrcode_scan_result", return_value={"state": True, "data": {"cookie": "UID=1; CID=2; SEID=3; KID=4"}}):
            result = service.finish_qrcode_login("s1")
        self.assertEqual(result["cookies"], "UID=1; CID=2; SEID=3; KID=4")
        self.assertIsNotNone(service._client_instance)

    def test_get_qrcode_login_status_rejects_unknown_session(self) -> None:
        service = P115Service(Settings())
        with self.assertRaises(ToolError):
            service.get_qrcode_login_status("missing")

    def test_offline_restart_task_rejects_blank_hash(self) -> None:
        service = self.make_service()
        with self.assertRaises(ToolError):
            service.offline_restart_task("   ")

    def test_receive_share_entries_requires_file_ids(self) -> None:
        service = self.make_service()
        with self.assertRaises(ToolError):
            service.receive_share_entries(share_code="code1", receive_code="pass", file_ids=[])

    def test_clear_recycle_bin_without_ids_is_allowed(self) -> None:
        service = self.make_service()
        result = service.clear_recycle_bin()
        self.assertEqual(result["entry_ids"], [])


if __name__ == "__main__":
    unittest.main()
