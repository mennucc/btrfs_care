#!/usr/bin/env python3
import importlib.util
from importlib.machinery import SourceFileLoader
import pathlib
import unittest


def load_btrfs_care():
    root = pathlib.Path(__file__).resolve().parents[1]
    path = root / "btrfs_care"
    loader = SourceFileLoader("btrfs_care_test", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


BC = load_btrfs_care()


class TestJournalParsing(unittest.TestCase):
    def test_normalize_block_device(self):
        device, token, markers = BC._normalize_block_device("/dev/nvme0n1p5[/@ubuntu]")
        self.assertEqual(device, "/dev/nvme0n1p5")
        self.assertEqual(token, "nvme0n1p5")
        self.assertIn("device /dev/nvme0n1p5", markers)
        self.assertIn("device nvme0n1p5", markers)

    def test_parse_btrfs_line_filters_info(self):
        _, token, markers = BC._normalize_block_device("/dev/nvme0n1p5")
        line = "2025-11-07T14:11:11+01:00 host kernel: BTRFS info (device nvme0n1p5): disk space caching is enabled"
        entry = BC._parse_btrfs_line(line, markers, token)
        self.assertIsNone(entry, "INFO lines should be ignored")

    def test_parse_btrfs_line_warning(self):
        _, token, markers = BC._normalize_block_device("/dev/nvme0n1p5")
        line = (
            "2025-11-08T13:47:01+01:00 host kernel: BTRFS warning (device /dev/nvme0n1p5): "
            "checksum error at logical 2225761812480 on dev /dev/sdh1, physical 2244023812096, "
            "root 7533, inode 184392, offset 684032, length 4096, links 1 "
            "(path: foo/bar)"
        )
        entry = BC._parse_btrfs_line(line, markers, token)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["level"], "WARNING")
        self.assertEqual(entry["root"], 7533)
        self.assertEqual(entry["inode"], 184392)
        self.assertEqual(entry["rel_path"], "foo/bar")
        self.assertEqual(entry["timestamp"], "2025-11-08T13:47:01+01:00")
        self.assertEqual(entry["host"], "host")

    def test_summarize_entry_with_subvolume(self):
        entry = {
            "timestamp": "2025-11-08T13:47:01+01:00",
            "host": "host",
            "level": "WARNING",
            "device": "nvme0n1p5",
            "root": 7533,
            "inode": 184392,
            "logical": None,
            "physical": None,
            "offset": None,
            "length": None,
            "rel_path": "foo/bar",
            "body": "checksum error",
        }
        summary = BC._summarize_btrfs_entry(entry, {7533: "snapshots/home"})
        self.assertIn("root 7533 (snapshots/home)", summary)
        self.assertIn("foo/bar", summary)
        self.assertIn("WARNING nvme0n1p5 (UUID ?)", summary)
        self.assertIn("root 7533 (snapshots/home)", summary)


if __name__ == "__main__":
    unittest.main()
