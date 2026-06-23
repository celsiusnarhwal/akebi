import contextlib
import hashlib
import os
import platform
import shutil
import stat
import subprocess
import typing as t
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationInfo,
    field_validator,
    validate_call,
)
from pydantic_extra_types.semantic_version import SemanticVersion
from rich.status import Status

from akebi import utils


class Bun(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_name: str = None
    """
    An identifier under which Bun installations created by this object are to be isolated.
    """

    # In practice, this will always be a `SemanticVersion` object.
    version: SemanticVersion | t.Literal["latest"] = Field(None, validate_default=True)
    """
    The version of Bun to use. Leave empty to use the latest version locally available. Pass "latest" to use the
    latest version, period.
    """

    @field_validator("version", mode="before")
    @classmethod
    def validate_version(cls, v, info: ValidationInfo) -> SemanticVersion | str:
        if v is None:
            installed_versions = []

            for directory in utils.get_bun_dir(info.data.get("app_name")).glob("*/"):
                try:
                    installed_versions.append(
                        TypeAdapter(SemanticVersion).validate_python(directory.name)
                    )
                except ValueError:
                    pass

            if installed_versions:
                return max(installed_versions)
            else:
                v = "latest"

        if isinstance(v, str) and v == "latest":
            with utils.github_client(api=True) as gh:
                releases = (
                    gh.get("/repos/oven-sh/bun/releases").raise_for_status().json()
                )

            return releases[0]["tag_name"].split("-v")[-1]

        return v

    @property
    def bin_path(self) -> Path:
        """
        The absolute path to the Bun executable.

        This only returns where the executable *should* be; it does not guarantee that it exists.
        """
        path = utils.get_bun_dir(self.app_name) / str(self.version) / "bin" / "bun"

        if platform.system().lower() == "windows":
            path = path.with_suffix(".exe")

        return path

    @property
    def checksum(self) -> str | None:
        """
        The checksum of the file at the intended location of the Bun executable.
        """
        if self.bin_path.is_file():
            return hashlib.sha256(self.bin_path.read_bytes()).hexdigest()

    @property
    def stored_checksum(self) -> str | None:
        """
        The checksum of the Bun executable at the time it was downloaded.
        """
        with utils.state(table="bun") as bun_db:
            return bun_db.get(str(self.bin_path))

    @property
    def is_installed(self) -> bool:
        """
        Whether this Bun is installed.
        """
        return self.bin_path.is_file() and self.checksum == self.stored_checksum

    def setup(self, *, force: bool = False) -> t.Self:
        """
        Install this Bun if it isn't installed already.

        Parameters
        ----------
        force: bool, default=False
            Install this Bun even if it's already installed.

        Returns
        -------
        Bun
            This object.
        """
        if self.is_installed and not force:
            return self

        with Status(f"Installing Bun v{self.version}..."):
            target = {"host": platform.system().casefold()}

            architecture = platform.machine().casefold()

            match architecture:
                case "x86_64" | "amd64":
                    target["architecture"] = "x64"
                case "arm64":
                    target["architecture"] = "aarch64"
                case _:
                    target["architecture"] = architecture

            if target["host"] == "linux":
                libc = utils.guess_libc()

                if libc == "musl":
                    target["libc"] = libc

            if utils.needs_baseline_build():
                target["build"] = "baseline"

            asset = f"bun-{'-'.join(target.values())}.zip"

            with utils.github_client() as gh:
                asset_resp = gh.get(
                    f"/oven-sh/bun/releases/download/bun-v{self.version}/{asset}",
                    follow_redirects=True,
                )

            if asset_resp.status_code == 404:
                # noinspection PyArgumentList
                raise Exception(
                    f"No Bun {self.version} release with name {asset} could be found"
                )

            asset_resp.raise_for_status()

            with TemporaryDirectory() as tmpdir:
                with contextlib.chdir(tmpdir):
                    bun_zip = Path("bun.zip")
                    bun_zip.write_bytes(asset_resp.content)

                    ZipFile(bun_zip).extractall()

                    glob = "**/bun"

                    if target["host"] == "windows":
                        glob += ".exe"

                    bun_bin = next(Path.cwd().glob(glob))
                    bun_bin.chmod(bun_bin.stat().st_mode | stat.S_IEXEC)

                    self.bin_path.parent.mkdir(parents=True, exist_ok=True)

                    shutil.move(bun_bin, self.bin_path)

            with utils.state(table="bun") as bun_db:
                bun_db[str(self.bin_path)] = self.checksum

            return self

    @validate_call()
    def __call__(
        self,
        args: t.Annotated[list | str, Field(default_factory=list)],
        /,
        **kwargs,
    ) -> subprocess.CompletedProcess:
        """
        Invoke this Bun.

        Parameters
        ----------
        args: list or str, optional, default=[]
            Command-line arguments to pass to the invocation.

        kwargs: dict, default={}
            Arbitrary keyword arguments to pass to ``subprocess.run``.

        Returns
        -------
        subprocess.CompletedProcess
            The associated ``subprocess.CompletedProcess`` object.
        """
        self.setup()

        if isinstance(args, list):
            args = [self.bin_path] + args
        elif isinstance(args, str):
            args = f"{self.bin_path} {args}"

        env = kwargs.get("env", os.environ)

        # If the Bun binary isn't on PATH then things like create-next-app will be displeased.
        if isinstance(env, t.MutableMapping):
            kwargs["env"] = {
                **env,
                "PATH": str(self.bin_path.parent) + os.pathsep + env.get("PATH", ""),
            }

        return subprocess.run(args, **kwargs)
