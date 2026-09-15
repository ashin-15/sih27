from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .runtime import git_revision, is_kaggle


def get_kaggle_secret(label: str) -> str:
    from kaggle_secrets import UserSecretsClient  # type: ignore

    return UserSecretsClient().get_secret(label)


def _auth_url(repo_url: str) -> tuple[str, str]:
    parts = urlsplit(repo_url.strip())
    if parts.scheme != "https" or not parts.netloc or not parts.path:
        raise ValueError("Repository URL must be an HTTPS Git URL without embedded credentials")
    if "@" in parts.netloc or parts.username or parts.password:
        raise ValueError("Repository URL must not embed credentials")
    clean = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    authenticated = urlunsplit((parts.scheme, f"x-access-token@{parts.netloc}", parts.path, "", ""))
    return clean, authenticated


def clone_private_repo(
    repo_url: str,
    destination: str | Path,
    ref: str = "main",
    token: str | None = None,
) -> dict[str, str]:
    destination = Path(destination)
    token = token if token is not None else get_kaggle_secret("GITHUB_READ_TOKEN")
    clean_url, authenticated_url = _auth_url(repo_url)

    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="foveamap-git-") as temp_dir:
        askpass = Path(temp_dir) / "askpass.sh"
        askpass.write_text('#!/bin/sh\nprintf "%s\\n" "$GITHUB_READ_TOKEN"\n', encoding="utf-8")
        askpass.chmod(0o700)
        env = os.environ.copy()
        env["GIT_ASKPASS"] = str(askpass)
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GITHUB_READ_TOKEN"] = token
        try:
            subprocess.run(
                ["git", "clone", authenticated_url, str(destination)],
                check=True,
                env=env,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(destination), "remote", "set-url", "origin", clean_url],
                check=True,
                env=env,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(destination), "checkout", ref],
                check=True,
                env=env,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            if destination.exists():
                shutil.rmtree(destination)
            stderr = exc.stderr.replace(token, "***") if exc.stderr else "git command failed"
            raise RuntimeError(f"Private repository checkout failed: {stderr}") from exc

    commit = git_revision(destination)
    if not commit:
        raise RuntimeError("Repository cloned but its Git commit could not be resolved")
    return {"repo_path": str(destination), "ref": ref, "commit": commit}


def install_requirements(requirements_path: str | Path) -> None:
    requirements_path = Path(requirements_path)
    if not requirements_path.exists():
        raise FileNotFoundError(f"Missing requirements file: {requirements_path}")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(requirements_path),
        ],
        check=True,
    )


def activate_source(repo_path: str | Path) -> Path:
    src_path = Path(repo_path) / "src"
    if not src_path.exists():
        raise FileNotFoundError(f"Missing source directory: {src_path}")
    source = str(src_path.resolve())
    if source not in sys.path:
        sys.path.insert(0, source)
    return src_path


def prepare_kaggle_source(
    repo_url: str,
    destination: str | Path = "/kaggle/working/sih-foveamap",
    ref: str = "main",
    token_label: str = "GITHUB_READ_TOKEN",
) -> dict[str, str]:
    if not is_kaggle():
        raise RuntimeError("prepare_kaggle_source is intended for the Kaggle runtime")
    token = get_kaggle_secret(token_label)
    checkout = clone_private_repo(repo_url, destination, ref=ref, token=token)
    activate_source(destination)
    return checkout
