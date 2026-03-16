"""
builder.py — Main entry point for the Build Engine.

Member 2's job: Orchestrate the entire build process.

This is the function that Member 1's CLI calls via interfaces.py:
    from build_engine.builder import build_image
"""

import os
import json
import hashlib
import datetime
import time

from build_engine import parser, cache, executor
from storage.layer_store import create_layer
from storage.image_store import save_image

DOCKSMITH_DIR = os.path.expanduser("~/.docksmith")
IMAGES_DIR    = os.path.join(DOCKSMITH_DIR, "images")
LAYERS_DIR    = os.path.join(DOCKSMITH_DIR, "layers")


def build_image(tag: str, context_path: str, no_cache: bool = False) -> dict:

    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(LAYERS_DIR, exist_ok=True)

    instructions = parser.parse(context_path)

    if ":" in tag:
        image_name, image_tag = tag.split(":", 1)
    else:
        image_name, image_tag = tag, "latest"

    current_layers = []
    prev_digest    = ""
    workdir        = ""
    env_state      = {}
    cmd            = []

    steps        = []
    cascade_miss = False

    total_steps = len(instructions)

    for step_index, instr in enumerate(instructions, start=1):

        keyword = instr["instruction"]
        args    = instr["args"]
        raw     = instr["raw"]

        if keyword == "FROM":

            manifest = executor.load_base_image(args)

            for layer_entry in manifest.get("layers", []):
                current_layers.append(layer_entry["digest"])

            prev_digest = manifest.get("digest", "")

            base_config = manifest.get("config", {})

            for env_pair in base_config.get("Env", []):
                if "=" in env_pair:
                    k, _, v = env_pair.partition("=")
                    env_state[k] = v

            if base_config.get("WorkingDir"):
                workdir = base_config["WorkingDir"]

            steps.append({
                "instruction": raw,
                "cache_hit": None,
                "duration": None
            })

            continue


        elif keyword == "WORKDIR":

            workdir = args

            steps.append({
                "instruction": raw,
                "cache_hit": None,
                "duration": None
            })

            continue


        elif keyword == "ENV":

            if "=" in args:
                k, _, v = args.partition("=")
                env_state[k.strip()] = v.strip()
            else:
                parts = args.split(None, 1)
                if len(parts) == 2:
                    env_state[parts[0]] = parts[1]

            steps.append({
                "instruction": raw,
                "cache_hit": None,
                "duration": None
            })

            continue


        elif keyword == "CMD":

            try:
                cmd = json.loads(args)
            except json.JSONDecodeError:
                raise SyntaxError("CMD must be JSON array")

            steps.append({
                "instruction": raw,
                "cache_hit": None,
                "duration": None
            })

            continue


        elif keyword in ("COPY", "RUN"):

            start_time = time.time()
            hit        = False

            copy_src_hash = ""

            if keyword == "COPY":
                src_pattern = args.split()[0]
                copy_src_hash = cache.hash_copy_sources(src_pattern, context_path)

            cache_key = cache.compute_cache_key(
                prev_digest=prev_digest,
                instruction_raw=raw,
                workdir=workdir,
                env_state=env_state,
                copy_src_hash=copy_src_hash
            )

            cached_digest = None

            if not no_cache and not cascade_miss:
                cached_digest = cache.lookup(cache_key)

            if cached_digest is not None:

                hit          = True
                layer_digest = cached_digest
                layer_size   = _get_layer_size(layer_digest)

            else:

                hit          = False
                cascade_miss = True

                if keyword == "COPY":

                    src, dest = _parse_copy_args(args)

                    layer_digest, layer_size = executor.execute_copy(
                        src_pattern=src,
                        dest=dest,
                        context_path=context_path,
                        current_layers=current_layers,
                        workdir=workdir
                    )

                else:

                    layer_digest, layer_size = executor.execute_run(
                        command=args,
                        current_layers=current_layers,
                        workdir=workdir,
                        env_state=env_state
                    )

                if not no_cache:
                    cache.store(cache_key, layer_digest)

            current_layers.append(layer_digest)
            prev_digest = layer_digest

            duration = time.time() - start_time

            steps.append({
                "instruction": raw,
                "cache_hit": hit,
                "duration": round(duration, 2),
                "layer_digest": layer_digest,
                "layer_size": layer_size,
                "created_by": raw
            })


    manifest_path = os.path.join(IMAGES_DIR, f"{image_name}_{image_tag}.json")

    created_ts = datetime.datetime.utcnow().isoformat() + "Z"

    layer_entries = []

    for s in steps:
        if "layer_digest" in s:
            layer_entries.append({
                "digest": s["layer_digest"],
                "size": s.get("layer_size", 0),
                "createdBy": s.get("created_by", "")
            })

    base_layers = _get_base_layers(instructions)

    all_layer_entries = base_layers + layer_entries

    manifest_data = {
        "name": image_name,
        "tag": image_tag,
        "digest": "",
        "created": created_ts,
        "config": {
            "Env": [f"{k}={v}" for k, v in sorted(env_state.items())],
            "Cmd": cmd,
            "WorkingDir": workdir
        },
        "layers": all_layer_entries
    }

    canonical = json.dumps(manifest_data, separators=(",", ":"), sort_keys=True)

    manifest_digest = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

    manifest_data["digest"] = manifest_digest

    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f, indent=2)


    # MEMBER 3 STORAGE INTEGRATION
    try:

        layer_digest = create_layer(context_path)

        save_image(
            image_name,
            image_tag,
            current_layers + [layer_digest],
            manifest_data["config"]
        )

    except Exception as e:

        print("[storage warning]", e)


    cli_steps = []

    for s in steps:
        cli_steps.append({
            "instruction": s["instruction"],
            "cache_hit": s["cache_hit"],
            "duration": s.get("duration")
        })

    return {
        "steps": cli_steps,
        "image_digest": manifest_digest
    }



def _parse_copy_args(args: str) -> tuple:

    parts = args.split()

    if len(parts) < 2:
        raise SyntaxError("COPY requires <src> <dest>")

    src  = " ".join(parts[:-1])
    dest = parts[-1]

    return src, dest



def _get_layer_size(layer_digest: str) -> int:

    hex_digest = layer_digest.replace("sha256:", "")

    layer_path = os.path.join(LAYERS_DIR, hex_digest + ".tar")

    if os.path.isfile(layer_path):
        return os.path.getsize(layer_path)

    return 0



def _get_base_layers(instructions: list) -> list:

    base_layers = []

    for instr in instructions:

        if instr["instruction"] == "FROM":

            try:

                manifest = executor.load_base_image(instr["args"])

                for layer in manifest.get("layers", []):
                    base_layers.append(layer)

            except Exception:
                pass

            break

    return base_layers