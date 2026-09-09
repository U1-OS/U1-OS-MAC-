"""Synthetic temporary data only: complete exports, quota, integrity and privacy."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from utils import prism_workspace as workspace
from utils import u1_personal_core as personal
from utils import u1_recovery as recovery


class DataBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="u1-data-boundary-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for obj, name, value in ((workspace, "DATA", self.root / "prism"),
                                 (recovery, "ROOT", self.root / "recovery")):
            guard = patch.object(obj, name, value)
            guard.start()
            self.addCleanup(guard.stop)

    def start(self, size=1):
        return workspace.handle_post("upload-start", {"name": "synthetic.txt", "size": size})["id"]

    def chunk(self, file_id, raw, offset=0):
        return workspace.handle_post("upload-chunk", {"id": file_id, "offset": offset,
                                    "content": base64.b64encode(raw).decode("ascii")})

    def upload(self, raw=b"synthetic owned fixture"):
        file_id = self.start(len(raw))
        self.chunk(file_id, raw)
        return file_id

    def row(self, file_id):
        with workspace.database() as conn:
            return dict(conn.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone())

    def storage(self):
        with workspace.database() as conn:
            return workspace._storage(conn)

    def test_2000_public_uploads_export_completely_and_restore_2002_members(self):
        ids = {self.upload(b"x") for _ in range(2000)}
        exported = workspace.handle_get("export", {})
        self.assertTrue(exported["complete"])
        self.assertEqual({row["id"] for row in exported["files"]}, ids)
        result = recovery.make_backup()
        with zipfile.ZipFile(recovery.ROOT / "backups" / (result["backup_id"] + ".zip")) as archive:
            self.assertEqual(len(archive.infolist()), 2002)
        restored = recovery.restore_backup(result["backup_id"])
        self.assertEqual(restored["files"], 2000)
        self.assertFalse(restored["active_workspace_changed"])
        self.assertEqual((Path(restored["path"]) / "files" / next(iter(ids))).read_bytes(), b"x")

    def test_backup_over_file_cap_is_rejected_before_publication(self):
        self.upload()
        with patch.object(recovery, "MAX_MANAGED_FILES", 0):
            with self.assertRaisesRegex(ValueError, "managed-file limit"):
                recovery.make_backup()
        self.assertEqual(list((recovery.ROOT / "backups").iterdir()), [])

    def test_backup_manifest_and_aggregate_limits_fail_without_publication(self):
        self.upload()
        for attribute, limit in (("MAX_MANIFEST_BYTES", 1), ("LIMIT", 1)):
            with self.subTest(attribute=attribute), patch.object(recovery, attribute, limit):
                with self.assertRaises(ValueError):
                    recovery.make_backup()
                self.assertEqual(list((recovery.ROOT / "backups").iterdir()), [])

    def test_restore_uses_shared_member_and_manifest_caps(self):
        self.upload()
        backup = recovery.make_backup()
        for attribute, limit in (("MAX_MEMBERS", 2), ("MAX_MANIFEST_BYTES", 1)):
            with self.subTest(attribute=attribute), patch.object(recovery, attribute, limit):
                with self.assertRaises(ValueError):
                    recovery.restore_backup(backup["backup_id"])
        self.assertEqual(list((recovery.ROOT / "restores").iterdir()), [])

    def test_metadata_export_limits_reject_instead_of_truncating(self):
        self.upload()
        for attribute, limit in (("MAX_EXPORT_ITEMS", 0), ("MAX_EXPORT_BYTES", 1)):
            with self.subTest(attribute=attribute), patch.object(workspace, attribute, limit):
                with self.assertRaisesRegex(ValueError, "Nothing was exported"):
                    workspace.handle_get("export", {})

    def test_file_trash_is_in_complete_metadata_and_backup(self):
        file_id = self.upload()
        workspace.handle_post("trash", {"kind": "file", "id": file_id})
        exported = workspace.handle_get("export", {})
        self.assertEqual(exported["files"], [])
        self.assertEqual(exported["file_trash"][0]["id"], file_id)
        result = recovery.restore_backup(recovery.make_backup()["backup_id"])
        self.assertEqual(result["files"], 1)

    def test_41_zero_byte_abandoned_reservations_are_reclaimed_without_deletion(self):
        ids, remaining = [], workspace.MAX_STORAGE
        while remaining:
            size = min(remaining, workspace.MAX_FILE)
            ids.append(self.start(size))
            remaining -= size
        self.assertEqual(len(ids), 41)
        self.assertEqual(self.storage()["allocated"], workspace.MAX_STORAGE)
        with self.assertRaisesRegex(ValueError, "pending file imports"):
            recovery.make_backup()
        for file_id in ids:
            workspace.handle_post("trash", {"kind": "file", "id": file_id})
        self.assertEqual(self.storage()["allocated"], 0)
        self.assertTrue(all((workspace.DATA / "files" / fid).exists() for fid in ids))
        result = recovery.make_backup()
        self.assertEqual(result["excluded_uploads"], {"count": 41, "retained_bytes": 0})
        self.assertEqual(recovery.restore_backup(result["backup_id"])["files"], 0)
        self.upload(b"x")

    def test_cancel_retains_partial_bytes_is_idempotent_and_refuses_ready_files(self):
        file_id = self.start(10)
        self.chunk(file_id, b"abc")
        for _ in range(2):
            result = workspace.handle_post("upload-abort", {"id": file_id})
            self.assertEqual(result["retained_bytes"], 3)
        self.assertEqual(self.storage()["allocated"], 3)
        self.assertEqual((workspace.DATA / "files" / file_id).read_bytes(), b"abc")
        with self.assertRaises(ValueError):
            self.chunk(file_id, b"d", 3)
        with self.assertRaises(ValueError):
            workspace.handle_post("restore", {"kind": "file", "id": file_id})
        ready = self.upload()
        with self.assertRaises(ValueError):
            workspace.handle_post("upload-abort", {"id": ready})
        self.assertEqual(workspace.read_verified_file(ready)[1], b"synthetic owned fixture")

    def test_idle_expiry_and_historical_trashed_uploads_reclaim_only_unused_quota(self):
        old, trashed, active = self.start(10), self.start(10), self.start(10)
        self.chunk(old, b"abc")
        with workspace.database() as conn:
            conn.execute("UPDATE file_upload_sessions SET touched=? WHERE file_id=?", (time.time() - workspace.UPLOAD_IDLE_SECONDS - 1, old))
            conn.execute("DELETE FROM file_upload_sessions WHERE file_id=?", (trashed,))
            conn.execute("UPDATE files SET deleted=? WHERE id=?", (time.time(), trashed))
        self.assertEqual(workspace.expire_uploads(), 2)
        self.assertEqual(self.row(active)["status"], "uploading")
        self.assertEqual(self.storage()["allocated"], 13)
        self.assertEqual((workspace.DATA / "files" / old).read_bytes(), b"abc")

    def test_chunk_activity_extends_lease_without_changing_creation_time(self):
        file_id = self.start(10)
        created = self.row(file_id)["created"]
        with workspace.database() as conn:
            conn.execute("UPDATE files SET created=? WHERE id=?", (created - 2 * workspace.UPLOAD_IDLE_SECONDS, file_id))
        self.chunk(file_id, b"abc")
        self.assertEqual(workspace.expire_uploads(), 0)
        self.assertEqual(self.row(file_id)["created"], created - 2 * workspace.UPLOAD_IDLE_SECONDS)

    def test_quota_counts_ready_trash_and_actual_partial_bytes(self):
        file_id = self.upload(b"abc")
        workspace.handle_post("trash", {"kind": "file", "id": file_id})
        pending = self.start(10)
        self.chunk(pending, b"de")
        self.assertEqual(self.storage()["used"], 5)
        self.assertEqual(self.storage()["reserved"], 8)
        workspace.handle_post("upload-abort", {"id": pending})
        self.assertEqual(self.storage()["allocated"], 5)

    def test_verified_read_matches_exact_returned_bytes_and_download_contract(self):
        file_id = self.upload()
        metadata, raw = workspace.read_verified_file(file_id)
        self.assertEqual(metadata["checksum"], hashlib.sha256(raw).hexdigest())
        response = workspace.handle_get("file", {"id": [file_id]})
        self.assertEqual(base64.b64decode(response["content"]), raw)
        self.assertEqual(response["checksum"], metadata["checksum"])

    def test_same_size_corruption_is_rejected_by_download_handoff_helper_and_backup(self):
        file_id = self.upload(b"abc")
        (workspace.DATA / "files" / file_id).write_bytes(b"XYZ")
        for call in (lambda: workspace.read_verified_file(file_id),
                     lambda: workspace.handle_get("file", {"id": [file_id]}), recovery.make_backup):
            with self.assertRaisesRegex(ValueError, "checksum"):
                call()

    def test_missing_checksum_and_wrong_size_are_not_treated_as_verified(self):
        file_id = self.upload(b"abc")
        with workspace.database() as conn:
            conn.execute("UPDATE files SET checksum=NULL WHERE id=?", (file_id,))
        with self.assertRaisesRegex(ValueError, "checksum"):
            workspace.read_verified_file(file_id)
        other = self.upload(b"abc")
        (workspace.DATA / "files" / other).write_bytes(b"x")
        with self.assertRaisesRegex(ValueError, "size"):
            workspace.read_verified_file(other)

    def test_traversal_symlink_hardlink_and_fifo_sources_are_rejected(self):
        with self.assertRaises(ValueError):
            workspace.read_verified_file("../outside")
        outside = self.root / "outside.txt"
        outside.write_bytes(b"abc")
        for kind in ("symlink", "hardlink", "fifo"):
            file_id = self.upload(b"abc")
            path = workspace.DATA / "files" / file_id
            path.unlink()
            if kind == "symlink":
                path.symlink_to(outside)
            elif kind == "hardlink":
                os.link(outside, path)
            else:
                os.mkfifo(path)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                workspace.read_verified_file(file_id)
            path.unlink()
        self.assertEqual(outside.read_bytes(), b"abc")

    def test_managed_directory_symlink_is_rejected_for_read_and_new_upload(self):
        file_id = self.upload(b"abc")
        directory = workspace.DATA / "files"
        moved = self.root / "moved-files"
        directory.rename(moved)
        directory.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(ValueError):
            workspace.read_verified_file(file_id)
        with self.assertRaises((ValueError, OSError)):
            self.start()
        self.assertEqual((moved / file_id).read_bytes(), b"abc")

    def test_link_swap_between_metadata_lookup_and_open_is_rejected(self):
        file_id = self.upload(b"abc")
        outside = self.root / "outside.txt"
        outside.write_bytes(b"abc")
        original = os.open
        def swapped(path, flags, *args, **kwargs):
            if path == file_id:
                target = workspace.DATA / "files" / file_id
                target.unlink()
                target.symlink_to(outside)
            return original(path, flags, *args, **kwargs)
        with patch.object(workspace.os, "open", side_effect=swapped):
            with self.assertRaises(ValueError):
                workspace.read_verified_file(file_id)

    def test_strict_chunk_offsets_and_changed_partial_bytes_are_rejected(self):
        file_id = self.start(3)
        for offset in (False, 0.0, "0", -1):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                self.chunk(file_id, b"a", offset)
        (workspace.DATA / "files" / file_id).write_bytes(b"unexpected")
        with self.assertRaisesRegex(ValueError, "bytes changed"):
            self.chunk(file_id, b"a")

    def account(self, title):
        row = personal.action({"action": "create", "kind": "paper_account", "title": title,
                               "payload": {"starting_cash": "1000"}})["record"]
        return personal.action({"action": "paper_trade", "id": row["id"], "expected_version": row["version"],
                                "reviewed": True, "side": "buy", "quantity": "1", "fees": "0",
                                "quote": {"symbol": "TEST", "currency": "AUD", "price": "10", "observed_at": time.time(),
                                          "source": title + " PRIVATE SOURCE", "basis": "manual"}})["record"]

    def test_product_export_omits_unrelated_paper_balances_and_trades(self):
        product = personal.action({"action": "create", "kind": "product", "title": "Public product", "payload": {}})["record"]
        self.account("UNRELATED")
        for query in ({"kind": "product"}, {"id": product["id"]}, {"q": "Public product"}):
            with self.subTest(query=query):
                exported = personal.snapshot(query, export=True)
                self.assertEqual(exported["paper_balances"], {})
                self.assertEqual(exported["paper_trades"], [])
                self.assertNotIn("UNRELATED", json.dumps(exported))

    def test_filtered_account_export_and_archive_filter_preserve_scope(self):
        first, second = self.account("FIRST"), self.account("SECOND")
        one = personal.snapshot({"id": first["id"]}, export=True)
        self.assertEqual(set(one["paper_balances"]), {first["id"]})
        self.assertEqual({row["account_id"] for row in one["paper_trades"]}, {first["id"]})
        personal.action({"action": "archive", "id": second["id"], "expected_version": second["version"]})
        active = personal.snapshot({"archived": "active"}, export=True)
        self.assertNotIn("SECOND", json.dumps(active))
        complete = personal.snapshot(export=True)
        self.assertEqual(len(complete["paper_balances"]), 2)
        self.assertEqual(len(complete["paper_trades"]), 2)

    def test_personal_export_rejects_record_and_trade_overflow(self):
        self.account("FIRST")
        for name in ("MAX_RECORDS", "MAX_PAPER_TRADES"):
            with self.subTest(name=name), patch.object(personal, name, 0):
                with self.assertRaisesRegex(personal.PersonalError, "nothing was exported"):
                    personal.snapshot(export=True)


if __name__ == "__main__":
    unittest.main()
