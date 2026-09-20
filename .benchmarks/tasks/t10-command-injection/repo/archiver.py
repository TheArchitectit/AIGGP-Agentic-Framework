import subprocess


def archive_logs(filename):
    """gzip one log file from the logs directory; returns the archive name."""
    # BUG: shell interpolation — filename like "x; rm -rf /" executes.
    cmd = f"gzip -k logs/{filename}"
    subprocess.run(cmd, shell=True, check=True)
    return filename + ".gz"
