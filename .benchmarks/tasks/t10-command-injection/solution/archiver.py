import os
import re
import subprocess

_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.log\Z")


def archive_logs(filename):
    """gzip one log file from the logs directory; returns the archive name.

    Security contract: the filename is validated BEFORE any process runs —
    only plain log names inside logs/ are accepted; everything else
    (metacharacters, separators, option-leading, wrong extension,
    nonexistent) raises ValueError. The child runs as an argv list with
    shell=False, so even a validation bypass could not inject a command.
    """
    if not isinstance(filename, str) or not filename:
        raise ValueError("log filename must be a non-empty string")
    if not _SAFE_NAME.fullmatch(filename):
        raise ValueError(f"unsafe log filename: {filename!r}")
    target = os.path.join("logs", filename)
    if not os.path.isfile(target):
        raise ValueError(f"log file does not exist: {filename!r}")
    subprocess.run(["gzip", "-k", target], check=True)
    return filename + ".gz"
