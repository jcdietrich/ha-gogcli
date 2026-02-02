"""Utilities for gogcli integration."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import stat
import tarfile
import zipfile
from io import BytesIO

import aiohttp
import yaml
from homeassistant.core import HomeAssistant

from .const import GOG_YAML_CONFIG

_LOGGER = logging.getLogger(__name__)

GOGCLI_VERSION = "0.9.0"
GITHUB_RELEASE_URL = "https://github.com/steipete/gogcli/releases/download/v{version}/gogcli_{version}_{os}_{arch}.{ext}"

def get_binary_path(hass: HomeAssistant) -> str:
    """Return the path to the gogcli binary."""
    return hass.config.path("custom_components/gogcli/bin/gog")

async def check_binary(path: str) -> str | None:
    """Check if the binary exists and return its version."""
    if not os.path.exists(path):
        return None
    
    try:
        proc = await asyncio.create_subprocess_exec(
            path,
            "version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            return stdout.decode().strip()
    except OSError:
        pass
    return None

def _get_system_info() -> tuple[str, str, str]:
    """Get OS and architecture info mapped to gogcli release names."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        os_name = "darwin"
    elif system == "linux":
        os_name = "linux"
    elif system == "windows":
        os_name = "windows"
    else:
        raise RuntimeError(f"Unsupported OS: {system}")

    if machine in ["x86_64", "amd64"]:
        arch = "amd64"
    elif machine in ["aarch64", "arm64"]:
        arch = "arm64"
    else:
        raise RuntimeError(f"Unsupported architecture: {machine}")

    ext = "zip" if os_name == "windows" else "tar.gz"
    return os_name, arch, ext

def _install_binary_sync(content: bytes, ext: str, target_path: str) -> None:
    """Synchronous helper to extract and write binary."""
    if ext == "tar.gz":
        with tarfile.open(fileobj=BytesIO(content), mode="r:gz") as tar:
            binary_member = None
            for member in tar.getmembers():
                if member.name.endswith("gogcli") or member.name.endswith("gogcli.exe") or member.name.endswith("gog") or member.name.endswith("gog.exe"):
                    binary_member = member
                    break
            
            if not binary_member:
                raise RuntimeError("Could not find gogcli binary in archive")
            
            f = tar.extractfile(binary_member)
            with open(target_path, "wb") as out:
                out.write(f.read())

    elif ext == "zip":
        with zipfile.ZipFile(BytesIO(content)) as zip_ref:
            binary_name = None
            for name in zip_ref.namelist():
                if name.endswith("gogcli.exe") or name.endswith("gogcli") or name.endswith("gog.exe") or name.endswith("gog"):
                    binary_name = name
                    break
            
            if not binary_name:
                raise RuntimeError("Could not find gogcli binary in archive")
            
            with zip_ref.open(binary_name) as source, open(target_path, "wb") as target:
                target.write(source.read())

    # Make executable
    st = os.stat(target_path)
    os.chmod(target_path, st.st_mode | stat.S_IEXEC)

async def install_binary(hass: HomeAssistant, version: str = GOGCLI_VERSION) -> str:
    """Download and install the gogcli binary."""
    os_name, arch, ext = _get_system_info()
    url = GITHUB_RELEASE_URL.format(version=version, os=os_name, arch=arch, ext=ext)
    
    target_path = get_binary_path(hass)
    target_dir = os.path.dirname(target_path)
    os.makedirs(target_dir, exist_ok=True)

    _LOGGER.info("Downloading gogcli from %s", url)

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise RuntimeError(f"Failed to download gogcli: {response.status}")
            content = await response.read()

    _LOGGER.info("Extracting gogcli to %s", target_path)
    
    await hass.async_add_executor_job(_install_binary_sync, content, ext, target_path)

    return target_path

def _get_config_path(config_dir: str) -> str:
    """Determine the gogcli config.json path based on OS."""
    system = platform.system().lower()
    if system == "darwin":
        return os.path.join(config_dir, "Library", "Application Support", "gogcli", "config.json")
    elif system == "windows":
        return os.path.join(config_dir, "AppData", "Roaming", "gogcli", "config.json")
    else:
        # Linux/Unix
        return os.path.join(config_dir, ".config", "gogcli", "config.json")

def sync_config(hass: HomeAssistant, config_dir: str):
    """Sync gogcli.yaml to config.json."""
    yaml_path = hass.config.path(GOG_YAML_CONFIG)
    
    config_data = {}
    if os.path.exists(yaml_path):
        try:
            with open(yaml_path, "r") as f:
                config_data = yaml.safe_load(f) or {}
        except Exception as e:
            _LOGGER.error("Error reading %s: %s", yaml_path, e)
            return

    # Ensure config data is a dict
    if not isinstance(config_data, dict):
        _LOGGER.error("%s must be a dictionary", GOG_YAML_CONFIG)
        return

    target_json = _get_config_path(config_dir)
    os.makedirs(os.path.dirname(target_json), exist_ok=True)
    
    try:
        with open(target_json, "w") as f:
            json.dump(config_data, f, indent=2)
    except Exception as e:
        _LOGGER.error("Error writing config.json: %s", e)

class GogWrapper:
    """Wrapper for gogcli commands."""
    
    def __init__(self, executable_path: str, config_dir: str | None = None):
        self.executable_path = executable_path
        self.config_dir = config_dir

    async def _run(self, *args) -> tuple[int, bytes, bytes]:
        env = os.environ.copy()
        if self.config_dir:
            env["HOME"] = self.config_dir
            env["XDG_CONFIG_HOME"] = os.path.join(self.config_dir, ".config")
        
        proc = await asyncio.create_subprocess_exec(
            self.executable_path,
            *args,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout, stderr

    async def version(self) -> str:
        code, stdout, _ = await self._run("version")
        if code != 0:
            raise RuntimeError("Failed to get version")
        return stdout.decode().strip()

    async def list_auth(self) -> str:
        code, stdout, stderr = await self._run("auth", "list", "--json")
        if code != 0:
            raise RuntimeError(f"Failed to list auth: {stderr.decode()}")
        return stdout.decode()

    async def set_credentials(self, credentials_path: str) -> None:
        code, _, stderr = await self._run("auth", "credentials", "set", credentials_path)
        if code != 0:
            raise RuntimeError(f"Failed to set credentials: {stderr.decode()}")

    async def search_messages(self, query: str, limit: int = 10, include_body: bool = False) -> list[dict]:
        args = ["gmail", "messages", "search", query, f"--max={limit}", "--json"]
        if include_body:
            args.append("--include-body")
            
        code, stdout, stderr = await self._run(*args)
        if code != 0:
            raise RuntimeError(f"Failed to search messages: {stderr.decode()}")
        
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return []

    async def get_thread(self, thread_id: str) -> dict:
        code, stdout, stderr = await self._run("gmail", "thread", "get", thread_id, "--json")
        if code != 0:
            raise RuntimeError(f"Failed to get thread {thread_id}: {stderr.decode()}")
        
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return {}

    async def start_auth(self, account: str) -> asyncio.subprocess.Process:
        """Start the interactive auth process."""
        env = os.environ.copy()
        if self.config_dir:
            env["HOME"] = self.config_dir
            env["XDG_CONFIG_HOME"] = os.path.join(self.config_dir, ".config")
            
        return await asyncio.create_subprocess_exec(
            self.executable_path,
            "auth", "add", account,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
