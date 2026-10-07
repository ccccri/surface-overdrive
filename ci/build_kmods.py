#!/usr/bin/env python3
"""Build, sign and stage the out-of-tree kernel modules for one exact kernel.

Inputs (all downloaded beforehand, see the Containerfile):
  --srpm-dir   directory with the kernel SRPM contents (linux-<ver>.tar.xz and patch-*-redhat.patch)
  --kver       full kernel version, e.g. 7.2.8-200.fc44.x86_64
  --key/--cert module signing key and certificate
Output: a tree rooted at --out with usr/lib/modules/<kver>/updates/*.ko and usr/share/surface-overdrive/kmods.json
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sh(cmd, **kw):
    kw.setdefault("check", True)
    return subprocess.run(cmd, text=True, **kw)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def files_touched_by(patch_file):
    """Paths a unified diff or git patch modifies (both sides, a/ and b/ prefixes stripped)."""
    out = set()
    for line in Path(patch_file).read_text(errors="replace").splitlines():
        m = re.match(r"^(?:\+\+\+|---) [ab]/(\S+)", line)
        if m:
            out.add(m.group(1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kver", required=True)
    ap.add_argument("--srpm-dir", required=True, type=Path)
    ap.add_argument("--work", default="/work", type=Path)
    ap.add_argument("--out", default="/out", type=Path)
    ap.add_argument("--key", required=True, type=Path)
    ap.add_argument("--cert", required=True, type=Path)
    args = ap.parse_args()

    upstream_ver = args.kver.split("-")[0]
    kdir = Path("/usr/src/kernels") / args.kver
    if not kdir.is_dir():
        fail(f"{kdir} not found: install kernel-devel for exactly {args.kver}")

    manifest = tomllib.loads((ROOT / "kmods" / "modules.toml").read_text())
    modules = manifest["module"]

    tarball = args.srpm_dir / f"linux-{upstream_ver}.tar.xz"
    if not tarball.is_file():
        fail(f"{tarball} missing")
    redhat_patches = sorted(args.srpm_dir.glob("patch-*-redhat.patch"))

    # Guard: the source of the running kernel is the vanilla tarball plus Fedora's patch. If that patch changes one of the
    # files we build from, the tarball no longer matches what runs and the build must not go on silently.
    ours = {s for m in modules for s in m["sources"]}
    for p in redhat_patches:
        hit = files_touched_by(p) & ours
        if hit:
            fail(f"Fedora's {p.name} modifies files we build from: {sorted(hit)}")

    tree = args.work / "tree"
    shutil.rmtree(tree, ignore_errors=True)
    tree.mkdir(parents=True)
    prefix = f"linux-{upstream_ver}/"
    wanted = {prefix + s for s in ours}
    with tarfile.open(tarball, "r:xz") as tf:
        members = [m for m in tf if m.name in wanted]
        found = {m.name for m in members}
        if found != wanted:
            fail(f"missing in the tarball: {sorted(wanted - found)}")
        for m in members:
            m.name = m.name[len(prefix):]
            tf.extract(m, tree, filter="data")

    report = {"kernel": args.kver, "source_tarball_sha256": sha256(tarball),
              "fedora_patches": [p.name for p in redhat_patches], "modules": []}
    updates = args.out / "usr/lib/modules" / args.kver / "updates"
    updates.mkdir(parents=True, exist_ok=True)

    for m in modules:
        name = m["name"]
        print(f"== {name}")
        applied, skipped = [], []
        for p in sorted((ROOT / "patches/kernel" / m["patches"]).iterdir()):
            if sh(["git", "apply", "-p1", "--reverse", "--check", str(p)], cwd=tree, capture_output=True, check=False).returncode == 0:
                print(f"   {p.name}: already in the kernel source, skipped")
                skipped.append(p.name)
                continue
            r = sh(["git", "apply", "-p1", str(p)], cwd=tree, capture_output=True, check=False)
            if r.returncode != 0:
                fail(f"patch {p.name} does not apply to {args.kver}:\n{r.stderr}")
            applied.append({"name": p.name, "sha256": sha256(p)})
        bdir = tree / m["build_dir"]
        (bdir / "Kbuild").write_text("\n".join(m["kbuild"]) + "\n")
        sh(["make", "-C", str(kdir), f"M={bdir}", "modules", f"-j{os.cpu_count()}"])
        for mod in m["modules"]:
            ko = bdir / f"{mod}.ko"
            if not ko.is_file():
                fail(f"{ko} was not produced")
            sh([str(kdir / "scripts/sign-file"), "sha256", str(args.key), str(args.cert), str(ko)])
            vermagic = sh(["modinfo", "-F", "vermagic", str(ko)], capture_output=True).stdout.split()[0]
            if vermagic != args.kver:
                fail(f"{mod}: vermagic {vermagic} != {args.kver}")
            dest = updates / f"{mod}.ko"
            shutil.copy2(ko, dest)
            report["modules"].append({"name": mod, "group": name, "sha256": sha256(dest),
                                      "patches": applied, "skipped_patches": skipped})
            print(f"   {mod}.ko  vermagic ok, signed")

    info = args.out / "usr/share/surface-overdrive"
    info.mkdir(parents=True, exist_ok=True)
    (info / "kmods.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    shutil.copy2(args.cert, info / "mok.der")
    (info / "mok.der").chmod(0o644)      # a public certificate: the health check and mokutil read it without privileges


if __name__ == "__main__":
    main()
