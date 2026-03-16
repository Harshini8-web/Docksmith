import os
import json
import shutil
import tarfile
import tempfile
import subprocess
import platform
import shlex

DOCKSMITH_DIR = os.path.expanduser("~/.docksmith")
IMAGES_DIR    = os.path.join(DOCKSMITH_DIR, "images")
LAYERS_DIR    = os.path.join(DOCKSMITH_DIR, "layers")


def run_container(image: str, env_overrides: dict = None, cmd_override: list = None) -> int:
    if env_overrides is None:
        env_overrides = {}

    manifest  = _load_manifest(image)
    command   = _resolve_command(manifest, cmd_override)
    env       = _build_env(manifest, env_overrides)
    workdir   = manifest.get("config", {}).get("WorkingDir", "") or "/"

    raw_layers = manifest.get("layers", [])
    digests = []
    for layer in raw_layers:
        if isinstance(layer, dict):
            digests.append(layer["digest"])
        elif isinstance(layer, str):
            digests.append(layer)

    tmp_root = tempfile.mkdtemp(prefix="docksmith_run_")
    try:
        _assemble_filesystem(digests, tmp_root)
        exit_code = _run_isolated(command, tmp_root, workdir, env)
    finally:
        _cleanup(tmp_root)

    return exit_code

def _load_manifest(image: str) -> dict:
    if ":" in image:
        name, tag = image.split(":", 1)
    else:
        name, tag = image, "latest"

    path = os.path.join(IMAGES_DIR, f"{name}_{tag}.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Image '{image}' not found.\n"
            f"Build it first: docksmith build -t {image} ."
        )
    with open(path) as f:
        return json.load(f)


def _resolve_command(manifest: dict, cmd_override: list = None) -> list:
    if cmd_override:
        return cmd_override
    image_cmd = manifest.get("config", {}).get("Cmd", [])
    if image_cmd:
        return image_cmd
    raise RuntimeError(
        "No CMD defined in image and no command given.\n"
        "Add CMD to your Docksmithfile or run: docksmith run myapp:latest /bin/sh"
    )


def _build_env(manifest: dict, env_overrides: dict) -> dict:
    env = {}
    for pair in manifest.get("config", {}).get("Env", []):
        if "=" in pair:
            k, _, v = pair.partition("=")
            env[k] = v
    env.update(env_overrides)
    return env


def _assemble_filesystem(layer_digests: list, root: str):
    for digest in layer_digests:
        hex_digest = digest.replace("sha256:", "")
        layer_path = os.path.join(LAYERS_DIR, hex_digest + ".tar")

        if not os.path.isfile(layer_path):
            raise RuntimeError(
                f"Layer '{digest}' missing from ~/.docksmith/layers/.\n"
                f"Rebuild the image."
            )

        with tarfile.open(layer_path, "r") as tar:
            members = []
            for member in tar.getmembers():
                member.name = member.name.lstrip("/").lstrip("\\")
                if member.name:
                    members.append(member)
            tar.extractall(path=root, members=members)


def _run_isolated(command: list, rootfs: str, workdir: str, env: dict) -> int:
    if platform.system() == "Windows":
        print("  [Windows] Isolation requires Linux. Use WSL2.")
        return 0

    env_exports = " ".join(f'export {k}="{v}";' for k, v in env.items())

    if workdir and workdir != "/":
        os.makedirs(os.path.join(rootfs, workdir.lstrip("/")), exist_ok=True)

    cmd_str = " ".join(shlex.quote(str(c)) for c in command)
    inner   = f"cd {workdir} 2>/dev/null || cd /; {env_exports} {cmd_str}"
    outer   = f"chroot {rootfs} /bin/sh -c '{inner}'"

    result = subprocess.run(
        ["unshare", "--mount", "--pid", "--fork", "sh", "-c", outer]
    )
    return result.returncode


def _cleanup(tmp_root: str):
    if not os.path.isdir(tmp_root):
        return
    proc_path = os.path.join(tmp_root, "proc")
    if os.path.ismount(proc_path):
        try:
            subprocess.run(["umount", "-l", proc_path], capture_output=True, timeout=5)
        except Exception:
            pass
    shutil.rmtree(tmp_root, ignore_errors=True)
