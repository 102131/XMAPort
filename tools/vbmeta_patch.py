#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vbmeta 禁验补丁工具
#
# AVB flags 是位于 rollback_index 之后、release string 之前的 4 字节大端字段。
# 已验证的 Android 实现通过下面 16 字节特征定位并替换，而不是写固定偏移：
#   00000000 00000000 "avbtool " -> 00000002 00000000 "avbtool "
# 其中 0x00000002 表示 AVB_VBMETA_IMAGE_FLAGS_VERIFICATION_DISABLED。
#
# 用法:
#     python vbmeta_patch.py <文件或目录> [<文件或目录> ...]
#
# 目录参数会自动扫描其中的 vbmeta*.img 文件（不区分大小写）。
# 非 vbmeta 文件会被警告并跳过，不影响其他文件处理。

import os
import sys

AVB_MAGIC = b"AVB0"
AVB_MAGIC_LEN = 4
UNPATCHED_PATTERN = bytes.fromhex("0000000000000000617662746F6F6C20")
PATCHED_PATTERN = bytes.fromhex("0000000200000000617662746F6F6C20")


def patch_one(path):
    # 对单个 vbmeta 文件打补丁。
    # 返回: (status, msg)  status: 'patched' | 'skipped' | 'invalid' | 'error'
    try:
        with open(path, "r+b") as f:
            data = f.read()
            if len(data) < AVB_MAGIC_LEN or data[:AVB_MAGIC_LEN] != AVB_MAGIC:
                return ("invalid", "not a vbmeta image (magic mismatch)")
            has_unpatched = UNPATCHED_PATTERN in data
            has_patched = PATCHED_PATTERN in data
            if not has_unpatched:
                if has_patched:
                    return ("skipped", "flags already 0x00000002 (idempotent)")
                return ("error", "expected flags/avbtool pattern not found")
            data = data.replace(UNPATCHED_PATTERN, PATCHED_PATTERN)
            f.seek(0)
            f.write(data)
            f.truncate()
            f.flush()
            os.fsync(f.fileno())
            return ("patched", "flags 0x00000000 -> 0x00000002")
    except OSError as e:
        return ("error", str(e))


def collect_files(args):
    # 从参数列表收集待处理的 vbmeta 文件清单。
    files = []
    for arg in args:
        if os.path.isdir(arg):
            for name in sorted(os.listdir(arg)):
                low = name.lower()
                if low.startswith("vbmeta") and low.endswith(".img"):
                    files.append(os.path.join(arg, name))
        elif os.path.isfile(arg):
            files.append(arg)
        else:
            print("  [warn] not found: %s" % arg)
    return files


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python vbmeta_patch.py <file|dir> [<file|dir> ...]")

    files = collect_files(sys.argv[1:])
    if not files:
        sys.exit("No vbmeta*.img found to patch.")

    n_patch = n_skip = n_invalid = n_err = 0
    for path in files:
        status, msg = patch_one(path)
        name = os.path.basename(path)
        if status == "patched":
            n_patch += 1
            print("  [OK]   %s : patched (%s)" % (name, msg))
        elif status == "skipped":
            n_skip += 1
            print("  [SKIP] %s : %s" % (name, msg))
        elif status == "invalid":
            n_invalid += 1
            print("  \033[93m[WARN]\033[0m %s : %s (skipped)" % (name, msg))
        else:
            n_err += 1
            print("  [ERR]  %s : %s" % (name, msg))

    print("")
    print("Summary: %d patched, %d skipped, %d invalid, %d error"
          % (n_patch, n_skip, n_invalid, n_err))
    sys.exit(0 if (n_err == 0) else 1)


if __name__ == "__main__":
    main()
