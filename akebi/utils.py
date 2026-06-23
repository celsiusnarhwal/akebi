import ctypes
import platform
import subprocess
import typing as t
from contextlib import contextmanager
from pathlib import Path

import httpx2 as httpx
import kokomikke
import platformdirs
from sqlitedict import SqliteDict


def github_client(*, api: bool = False, **kwargs) -> httpx.Client:
    """
    Return an ``httpx.Client`` for GitHub.

    Parameters
    ----------
    api: bool, default=False
        If True, return an `httpx.Client` for the GitHub API.

    kwargs: dict, default={}
        Arbitrary keyword arguments to pass to ``httpx.Client``.
    """
    return httpx.Client(
        base_url="https://api.github.com" if api else "https://github.com",
        event_hooks={
            "request": [_github_client_request_token_hook],
            "response": [_github_client_rate_limit_hook],
        },
        **kwargs,
    )


def get_cache_dir() -> Path:
    """
    Return Akebi's cache directory.
    """
    path = platformdirs.user_cache_path("akebi", appauthor=False)
    path.mkdir(exist_ok=True, parents=True)

    return path


def get_data_dir() -> Path:
    """
    Return Akebi's data directory.
    """
    path = platformdirs.user_data_path("akebi", appauthor=False)
    path.mkdir(parents=True, exist_ok=True)

    return path


def get_bun_dir(app_name: str = None) -> Path:
    """
    Return the directory where Akebi-managed Bun installs are located.
    """
    if app_name:
        path = get_cache_dir() / "isolated" / app_name / "bun"
    else:
        path = get_cache_dir() / "shared" / "bun"

    path.mkdir(parents=True, exist_ok=True)

    return path


def guess_libc() -> t.Literal["gnu", "musl"] | None:
    """
    Make a best-effort attempt at determining the C standard library implementation on a Linux system.
    """
    if platform.system().lower() != "linux":
        return None

    # Check os-release for known musl distributions
    try:
        os_release = platform.freedesktop_os_release()
    except OSError:
        pass
    else:
        identities = {os_release.get("ID")}.union(os_release.get("ID_LIKE", "").split())

        if identities.intersection({"alpine", "postmarketos", "chimera"}):
            return "musl"

    # Read the output of `ldd --version`
    try:
        ldd_command = subprocess.run(
            ["ldd", "--version"], capture_output=True, text=True
        )
    except FileNotFoundError:
        pass
    else:
        # `ldd --version` on musl systems exits nonzero and writes to stderr. why? you tell me
        ldd_info = ldd_command.stdout + ldd_command.stderr

        if "gnu" in ldd_info.casefold():
            return "gnu"
        elif "musl" in ldd_info.casefold():
            return "musl"

    # Check which libc the Python interpreter is linked against
    match platform.libc_ver()[0]:
        case "glibc":
            return "gnu"
        case "musl":
            return "musl"

    # Check /lib and /lib64 for files beginning with ld-linux- or ld-musl-
    for directory in ["/lib", "/lib64"]:
        for prefix, libc in zip(["ld-linux-", "ld-musl-"], ["gnu", "musl"]):
            if next(Path(directory).glob(f"{prefix}*"), None):
                return libc

    # If all else fails, assume glibc and hope for the best
    return "gnu"


def needs_baseline_build() -> bool:
    """
    Determine whether the host machine requires a baseline build of Bun.
    """

    if platform.machine() in ["arm64", "aarch64"]:
        return False

    match platform.system().lower():
        case "darwin":
            try:
                sysctl = subprocess.check_output(["sysctl", "-a"], text=True)
            except FileNotFoundError, subprocess.CalledProcessError:
                return True
            else:
                return "avx2" not in sysctl.casefold()

        case "linux":
            cpu_info = Path("/proc/cpuinfo")
            return not (
                cpu_info.is_file() and "avx2" in cpu_info.read_text().casefold()
            )

        case "windows":
            return not bool(ctypes.windll.kernel32.IsProcessorFeaturePresent(40))

    return True


@contextmanager
def state(table: str = "unnamed") -> SqliteDict:
    """
    Context manager for accessing Akebi's key-value store.

    Parameters
    ----------
    table: str, default="unnamed"
        The table to access.
    """
    with SqliteDict(get_data_dir() / "akebi.db", tablename=table) as db:
        yield db
        db.commit()


def _github_client_request_token_hook(request: httpx.Request) -> None:
    """
    HTTPX event hook to attach a GitHub access token, if one can be found, to requests to GitHub.
    """
    if token := kokomikke.search():
        request.headers["Authorization"] = f"Bearer {token}"


def _github_client_rate_limit_hook(response: httpx.Response) -> None:
    """
    HTTPX event hook to handle HTTP 429 errors in responses from GitHub.
    """
    if response.status_code == 429:
        raise Exception(
            "GitHub is rate limiting you. You can probably fix this by setting the "
            "GITHUB_TOKEN environment variable or logging into the GitHub CLI (https://cli.github.com); your "
            "credentials will automatically be attached to future GitHub requests."
        )
