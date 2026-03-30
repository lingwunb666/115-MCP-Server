from __future__ import annotations

import argparse
import json

from fastmcp import FastMCP
from fastmcp.resources import ResourceContent, ResourceResult

from .config import Settings
from .service import P115Service


SERVER_INSTRUCTIONS = """
This server exposes 115 cloud-storage operations backed by p115client.
Use remote_id for numeric 115 ids, or remote_path for absolute cloud paths.
Directory-scoped tools default to the root directory when both id and path are omitted.
Configure authentication with P115_COOKIES or P115_COOKIES_PATH before calling stateful tools.
""".strip()


def create_server(service: P115Service | None = None) -> FastMCP:
    bound_service = service or P115Service()
    mcp = FastMCP(
        name="mcp-115-server",
        instructions=SERVER_INSTRUCTIONS,
        version="0.1.0",
        website_url="https://p115client.readthedocs.io/en/latest/",
    )

    @mcp.resource("info://server")
    def server_info_resource() -> ResourceResult:
        payload = json.dumps(bound_service.server_info(), ensure_ascii=False, indent=2)
        return ResourceResult([ResourceContent(payload, mime_type="application/json")])

    @mcp.tool
    def auth_status(validate_remote: bool = False) -> dict:
        """Return local configuration status and optionally verify remote login state."""
        return bound_service.auth_status(validate_remote=validate_remote)

    @mcp.tool
    def start_qrcode_login(app: str = "alipaymini") -> dict:
        """Start a 115 QR-code login session and return a URL for scanning."""
        return bound_service.start_qrcode_login(app=app)

    @mcp.tool
    def get_qrcode_login_status(session_id: str) -> dict:
        """Check the current status of a previously started QR-code login session."""
        return bound_service.get_qrcode_login_status(session_id=session_id)

    @mcp.tool
    def finish_qrcode_login(session_id: str, output_path: str = "") -> dict:
        """Finish a signed QR-code login session and optionally save cookies to a file."""
        return bound_service.finish_qrcode_login(session_id=session_id, output_path=output_path)

    @mcp.tool
    def list_directory(
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict:
        """List entries under a 115 directory. Defaults to the root directory when no target is provided."""
        return bound_service.list_directory(remote_id=remote_id, remote_path=remote_path, refresh=refresh)

    @mcp.tool
    def get_metadata(
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict:
        """Get metadata for a single 115 file or directory."""
        return bound_service.get_metadata(remote_id=remote_id, remote_path=remote_path, refresh=refresh)

    @mcp.tool
    def search_entries(
        query: str,
        directory_id: int | None = None,
        directory_path: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Search files and directories under a 115 directory tree."""
        return bound_service.search_entries(
            query,
            directory_id=directory_id,
            directory_path=directory_path,
            limit=limit,
            offset=offset,
        )

    @mcp.tool
    def create_directory(
        name: str,
        parent_id: int | None = None,
        parent_path: str | None = None,
        refresh: bool = False,
    ) -> dict:
        """Create a directory under the specified parent directory."""
        return bound_service.create_directory(
            name,
            parent_id=parent_id,
            parent_path=parent_path,
            refresh=refresh,
        )

    @mcp.tool
    def resolve_directory(remote_path: str) -> dict:
        """Resolve a 115 directory path to backend lookup information such as directory id."""
        return bound_service.resolve_directory(remote_path=remote_path)

    @mcp.tool
    def get_storage_info() -> dict:
        """Return 115 storage/quota information for the current account."""
        return bound_service.get_storage_info()

    @mcp.tool
    def get_account_info() -> dict:
        """Return account information for the current 115 user."""
        return bound_service.get_account_info()

    @mcp.tool
    def get_index_info(include_space_numbers: bool = False) -> dict:
        """Return dashboard/index information for the current account."""
        return bound_service.get_index_info(include_space_numbers=include_space_numbers)

    @mcp.tool
    def path_exists(
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict:
        """Check whether a file or directory exists."""
        return bound_service.path_exists(remote_id=remote_id, remote_path=remote_path, refresh=refresh)

    @mcp.tool
    def count_directory(
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict:
        """Count entries in a directory without returning a full listing."""
        return bound_service.count_directory(remote_id=remote_id, remote_path=remote_path, refresh=refresh)

    @mcp.tool
    def get_ancestors(
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict:
        """Return the ancestor chain for a file or directory."""
        return bound_service.get_ancestors(remote_id=remote_id, remote_path=remote_path, refresh=refresh)

    @mcp.tool
    def glob_entries(
        pattern: str,
        directory_id: int | None = None,
        directory_path: str | None = None,
        ignore_case: bool = False,
        limit: int = 100,
        refresh: bool = False,
    ) -> dict:
        """Find entries by glob pattern under a directory."""
        return bound_service.glob_entries(
            pattern,
            directory_id=directory_id,
            directory_path=directory_path,
            ignore_case=ignore_case,
            limit=limit,
            refresh=refresh,
        )

    @mcp.tool
    def walk_directory(
        remote_id: int | None = None,
        remote_path: str | None = None,
        max_depth: int = 2,
        topdown: bool = True,
        limit: int = 200,
        refresh: bool = False,
    ) -> dict:
        """Walk a directory tree with bounded depth and result count."""
        return bound_service.walk_directory(
            remote_id=remote_id,
            remote_path=remote_path,
            max_depth=max_depth,
            topdown=topdown,
            limit=limit,
            refresh=refresh,
        )

    @mcp.tool
    def get_stat(
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict:
        """Return a stat-like view for a file or directory."""
        return bound_service.get_stat(remote_id=remote_id, remote_path=remote_path, refresh=refresh)

    @mcp.tool
    def offline_add_urls(urls: list[str], remote_dir_id: int | None = None) -> dict:
        """Create one or more offline download tasks from URLs, magnets, FTP, or ed2k links."""
        return bound_service.offline_add_urls(urls, remote_dir_id=remote_dir_id)

    @mcp.tool
    def offline_get_torrent_info(torrent_sha1: str, pick_code: str) -> dict:
        """Inspect torrent metadata before creating an offline BT task."""
        return bound_service.offline_get_torrent_info(torrent_sha1=torrent_sha1, pick_code=pick_code)

    @mcp.tool
    def offline_add_torrent(
        torrent_sha1: str,
        pick_code: str,
        info_hash: str = "",
        wanted_indexes: list[int] | None = None,
        remote_dir_id: int | None = None,
        save_path: str = "",
    ) -> dict:
        """Create an offline BT task, optionally selecting torrent file indexes."""
        return bound_service.offline_add_torrent(
            torrent_sha1=torrent_sha1,
            pick_code=pick_code,
            info_hash=info_hash,
            wanted_indexes=wanted_indexes,
            remote_dir_id=remote_dir_id,
            save_path=save_path,
        )

    @mcp.tool
    def offline_list_tasks(page: int = 1) -> dict:
        """List current offline download tasks."""
        return bound_service.offline_list_tasks(page=page)

    @mcp.tool
    def offline_list_tasks_advanced(page: int = 1, page_size: int = 30, status: str = "") -> dict:
        """List offline tasks with page size and optional status filtering."""
        return bound_service.offline_list_tasks_advanced(page=page, page_size=page_size, status=status)

    @mcp.tool
    def offline_remove_task(info_hash: str, delete_source_file: bool = False) -> dict:
        """Remove an offline task by info hash."""
        return bound_service.offline_remove_task(info_hash=info_hash, delete_source_file=delete_source_file)

    @mcp.tool
    def offline_remove_tasks(info_hashes: list[str], delete_source_file: bool = False) -> dict:
        """Remove multiple offline tasks by info hash."""
        return bound_service.offline_remove_tasks(info_hashes=info_hashes, delete_source_file=delete_source_file)

    @mcp.tool
    def offline_clear_tasks(scope: str = "completed") -> dict:
        """Bulk-clear offline tasks by named scope."""
        return bound_service.offline_clear_tasks(scope=scope)

    @mcp.tool
    def offline_get_quota_info() -> dict:
        """Return offline download quota/capacity information."""
        return bound_service.offline_get_quota_info()

    @mcp.tool
    def offline_get_sign_info() -> dict:
        """Return sign/time information required by low-level offline APIs."""
        return bound_service.offline_get_sign_info()

    @mcp.tool
    def offline_get_quota_package_array() -> dict:
        """Return detailed offline quota package array information."""
        return bound_service.offline_get_quota_package_array()

    @mcp.tool
    def offline_get_quota_package_info() -> dict:
        """Return detailed offline quota package information."""
        return bound_service.offline_get_quota_package_info()

    @mcp.tool
    def offline_get_download_paths() -> dict:
        """Return current default offline download directory choices."""
        return bound_service.offline_get_download_paths()

    @mcp.tool
    def offline_set_download_path(
        remote_dir_id: int | None = None,
        remote_dir_path: str | None = None,
    ) -> dict:
        """Set the default directory used by offline downloads."""
        return bound_service.offline_set_download_path(remote_dir_id=remote_dir_id, remote_dir_path=remote_dir_path)

    @mcp.tool
    def offline_restart_task(info_hash: str) -> dict:
        """Restart a failed or paused offline task by info hash."""
        return bound_service.offline_restart_task(info_hash=info_hash)

    @mcp.tool
    def offline_get_task_count(flag: int = 0) -> dict:
        """Return the current offline task count for a given backend flag."""
        return bound_service.offline_get_task_count(flag=flag)

    @mcp.tool
    def list_recycle_bin(limit: int = 32, offset: int = 0) -> dict:
        """List recycle-bin entries."""
        return bound_service.list_recycle_bin(limit=limit, offset=offset)

    @mcp.tool
    def get_recycle_bin_entry(rid: int) -> dict:
        """Get a single recycle-bin entry by recycle id."""
        return bound_service.get_recycle_bin_entry(rid=rid)

    @mcp.tool
    def restore_recycle_bin_entries(entry_ids: list[int]) -> dict:
        """Restore entries from the recycle bin."""
        return bound_service.restore_recycle_bin_entries(entry_ids=entry_ids)

    @mcp.tool
    def clear_recycle_bin(entry_ids: list[int] | None = None, password: str = "") -> dict:
        """Clear the recycle bin or permanently delete specific recycle-bin entries."""
        return bound_service.clear_recycle_bin(entry_ids=entry_ids, password=password)

    @mcp.tool
    def list_labels(
        keyword: str = "",
        limit: int = 100,
        offset: int = 0,
        sort: str = "",
        order: str = "",
    ) -> dict:
        """List available labels/tags."""
        return bound_service.list_labels(keyword=keyword, limit=limit, offset=offset, sort=sort, order=order)

    @mcp.tool
    def set_entry_labels(remote_id: int, label_ids: list[int]) -> dict:
        """Replace the labels assigned to an entry."""
        return bound_service.set_entry_labels(remote_id=remote_id, label_ids=label_ids)

    @mcp.tool
    def list_shares(limit: int = 32, offset: int = 0, include_cancelled: bool = False) -> dict:
        """List the current user's shares."""
        return bound_service.list_shares(limit=limit, offset=offset, include_cancelled=include_cancelled)

    @mcp.tool
    def get_share_info(share_code: str) -> dict:
        """Get information about a share by share code."""
        return bound_service.get_share_info(share_code=share_code)

    @mcp.tool
    def get_share_receive_code(share_code: str) -> dict:
        """Get the receive code for a share."""
        return bound_service.get_share_receive_code(share_code=share_code)

    @mcp.tool
    def receive_share_entries(
        share_code: str,
        receive_code: str,
        file_ids: list[int],
        remote_dir_id: int | None = None,
        remote_dir_path: str | None = None,
        is_check: bool = False,
    ) -> dict:
        """Receive files or directories from a share into your own drive."""
        return bound_service.receive_share_entries(
            share_code=share_code,
            receive_code=receive_code,
            file_ids=file_ids,
            remote_dir_id=remote_dir_id,
            remote_dir_path=remote_dir_path,
            is_check=is_check,
        )

    @mcp.tool
    def get_share_download_url(
        file_id: int,
        share_code: str = "",
        receive_code: str = "",
        share_url: str = "",
        strict: bool = True,
        app: str = "",
    ) -> dict:
        """Get the download URL for a file inside a share."""
        return bound_service.get_share_download_url(
            file_id=file_id,
            share_code=share_code,
            receive_code=receive_code,
            share_url=share_url,
            strict=strict,
            app=app,
        )

    @mcp.tool
    def list_share_access_users(share_code: str) -> dict:
        """List access users for a share."""
        return bound_service.list_share_access_users(share_code=share_code)

    @mcp.tool
    def get_share_download_quota() -> dict:
        """Return public-share download quota information."""
        return bound_service.get_share_download_quota()

    @mcp.tool
    def upload_local_file(
        local_path: str,
        remote_dir_id: int | None = None,
        remote_dir_path: str | None = None,
        remote_filename: str = "",
        refresh: bool = False,
    ) -> dict:
        """Upload a local file into a 115 directory."""
        return bound_service.upload_local_file(
            local_path,
            remote_dir_id=remote_dir_id,
            remote_dir_path=remote_dir_path,
            remote_filename=remote_filename,
            refresh=refresh,
        )

    @mcp.tool
    def download_file(
        local_path: str,
        remote_id: int | None = None,
        remote_path: str | None = None,
        overwrite: bool = False,
        refresh: bool = False,
    ) -> dict:
        """Download a 115 file to a local path."""
        return bound_service.download_file(
            local_path,
            remote_id=remote_id,
            remote_path=remote_path,
            overwrite=overwrite,
            refresh=refresh,
        )

    @mcp.tool
    def move_entry(
        source_id: int | None = None,
        source_path: str | None = None,
        destination_dir_id: int | None = None,
        destination_dir_path: str | None = None,
        refresh: bool = False,
    ) -> dict:
        """Move a file or directory into another directory."""
        return bound_service.move_entry(
            source_id=source_id,
            source_path=source_path,
            destination_dir_id=destination_dir_id,
            destination_dir_path=destination_dir_path,
            refresh=refresh,
        )

    @mcp.tool
    def batch_move_entries(
        source_ids: list[int] | None = None,
        source_paths: list[str] | None = None,
        destination_dir_id: int | None = None,
        destination_dir_path: str | None = None,
    ) -> dict:
        """Move multiple files or directories into another directory in one operation."""
        return bound_service.batch_move_entries(
            source_ids=source_ids,
            source_paths=source_paths,
            destination_dir_id=destination_dir_id,
            destination_dir_path=destination_dir_path,
        )

    @mcp.tool
    def copy_entry(
        source_id: int | None = None,
        source_path: str | None = None,
        destination_dir_id: int | None = None,
        destination_dir_path: str | None = None,
        refresh: bool = False,
    ) -> dict:
        """Copy a file or directory into another directory."""
        return bound_service.copy_entry(
            source_id=source_id,
            source_path=source_path,
            destination_dir_id=destination_dir_id,
            destination_dir_path=destination_dir_path,
            refresh=refresh,
        )

    @mcp.tool
    def batch_copy_entries(
        source_ids: list[int] | None = None,
        source_paths: list[str] | None = None,
        destination_dir_id: int | None = None,
        destination_dir_path: str | None = None,
    ) -> dict:
        """Copy multiple files or directories into another directory in one operation."""
        return bound_service.batch_copy_entries(
            source_ids=source_ids,
            source_paths=source_paths,
            destination_dir_id=destination_dir_id,
            destination_dir_path=destination_dir_path,
        )

    @mcp.tool
    def rename_entry(
        new_name: str,
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict:
        """Rename a file or directory."""
        return bound_service.rename_entry(
            new_name,
            remote_id=remote_id,
            remote_path=remote_path,
            refresh=refresh,
        )

    @mcp.tool
    def remove_entry(
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict:
        """Remove a file or directory from 115."""
        return bound_service.remove_entry(remote_id=remote_id, remote_path=remote_path, refresh=refresh)

    @mcp.tool
    def batch_remove_entries(
        source_ids: list[int] | None = None,
        source_paths: list[str] | None = None,
    ) -> dict:
        """Remove multiple files or directories in one operation."""
        return bound_service.batch_remove_entries(source_ids=source_ids, source_paths=source_paths)

    @mcp.tool
    def get_download_url(
        remote_id: int | None = None,
        remote_path: str | None = None,
        refresh: bool = False,
    ) -> dict:
        """Return the current download URL and related metadata for a 115 file."""
        return bound_service.get_download_url(remote_id=remote_id, remote_path=remote_path, refresh=refresh)

    return mcp


def main() -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(description="Run the 115 FastMCP server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "streamable-http", "sse"],
        default=settings.fastmcp_transport,
    )
    parser.add_argument("--host", default=settings.fastmcp_host)
    parser.add_argument("--port", type=int, default=settings.fastmcp_port)
    parser.add_argument("--path", default=settings.fastmcp_path)
    parser.add_argument("--log-level", default=settings.fastmcp_log_level)
    args = parser.parse_args()

    server = create_server(P115Service(settings=settings))
    if args.transport == "stdio":
        server.run(transport="stdio", show_banner=False, log_level=args.log_level)
        return

    server.run(
        transport=args.transport,
        show_banner=False,
        host=args.host,
        port=args.port,
        path=args.path,
        log_level=args.log_level,
    )
