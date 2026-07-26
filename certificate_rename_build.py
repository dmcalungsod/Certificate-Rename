#!/usr/bin/env python3
"""
certificate_rename_build.py — Build, sign, verify signature, and generate release hashes
for Certificate Rename.

Usage examples:
  python certificate_rename_build.py                # build, sign if .pfx present, generate hashes
  python certificate_rename_build.py --no-sign      # build but skip signing
  python certificate_rename_build.py --sign --password SECRET   # force signing and provide password
  python certificate_rename_build.py --verify-sign  # verify existing signature on the built EXE
  python certificate_rename_build.py --clean-only   # clean build artifacts and exit
"""

from __future__ import annotations
import sys
import os
import subprocess
import shutil
import glob
import argparse
import getpass
import hashlib
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# -----------------------------
# Configuration
# -----------------------------

MAIN_SCRIPT = "gui_app.py"
APP_NAME = "Certificate Renamer"
EXE_NAME = f"{APP_NAME}.exe"
VERSION_FILE = "assets/version_info.txt"
ICON_FILE = "assets/favicon.ico"

DIST_PATH = Path("dist")
BUILD_PATH = Path("build")
EXE_PATH = DIST_PATH / EXE_NAME

# -----------------------------
# Utilities
# -----------------------------


def clean_build_artifacts() -> None:
    """Remove previous build artifacts."""
    console.print("Cleaning previous build artifacts...")
    try:
        if DIST_PATH.exists():
            shutil.rmtree(DIST_PATH)
        if BUILD_PATH.exists():
            shutil.rmtree(BUILD_PATH)
        for spec in glob.glob("*.spec"):
            try:
                Path(spec).unlink()
            except Exception:
                pass
        console.print("[green][+] Cleanup complete.[/green]")
    except Exception as e:
        console.print(f"[yellow][!] Cleanup warning: {e}[/yellow]")


def _get_pyinstaller_args() -> list[str]:
    """Constructs the list of arguments for PyInstaller."""
    args = []

    if Path(VERSION_FILE).exists():
        console.print(f"   [green][+] Found version information[/green]")
        args.append(f"--version-file={VERSION_FILE}")
    else:
        console.print(
            f"   [yellow][!] Version file '{VERSION_FILE}' not found.[/yellow]"
        )

    if Path(ICON_FILE).exists():
        console.print(f"   [green][+] Found the icon file[/green]")
        args.append(f"--icon={ICON_FILE}")
    else:
        console.print(f"   [yellow][!] Icon file '{ICON_FILE}' not found.[/yellow]")

    # Bundle the entire assets folder
    args.append("--add-data=assets;assets")

    args.extend(
        [
            "--onefile",
            "--windowed",
            f"--name={EXE_NAME.replace('.exe', '')}",
            "--clean",
            "--noconfirm",
            # SAGA-DTR Helper dependencies
            "--hidden-import=PySide6",
            "--hidden-import=plyer",
            "--hidden-import=plyer.platforms.win.notification",
            "--hidden-import=pystray",
            "--hidden-import=PIL",
            "--hidden-import=openpyxl",
            "--hidden-import=zoneinfo",
            "--hidden-import=tzdata",
            # Bundle timezone data
            "--collect-data=tzdata",
            # Exclude test/dev modules
            "--exclude-module=tests",
            "--exclude-module=pytest",
            "--exclude-module=docutils",
            MAIN_SCRIPT,
        ]
    )
    return args


def build_exe() -> bool:
    """Run the PyInstaller build process for SAGA-DTR Helper."""
    console.rule("Building Executable with PyInstaller", style="bold cyan")

    if not Path(MAIN_SCRIPT).exists():
        console.print(f"[red][-] Entry script not found: {MAIN_SCRIPT}[/red]")
        return False

    console.print("Verifying required files...")
    pyinstaller_args = _get_pyinstaller_args()
    pyinstaller_cmd = [sys.executable, "-m", "PyInstaller"] + pyinstaller_args

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(f"Building {EXE_NAME}...", total=None)
            proc = subprocess.run(
                pyinstaller_cmd,
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
            )
            progress.update(
                task, completed=True, description="[green][+] Build complete[/green]"
            )

        if not EXE_PATH.exists():
            console.print(
                f"[red][-] Build finished, but EXE not found at '{EXE_PATH}'[/red]"
            )
            return False
        console.print(
            f"[bold green][+] Build successful! Executable at: {EXE_PATH}[/bold green]"
        )
        return True
    except subprocess.CalledProcessError as e:
        console.print("[red][-] Build failed[/red]")
        console.print(
            Panel(
                e.stdout + "\n---\n" + e.stderr,
                title="PyInstaller Error",
                style="red",
                border_style="red",
            )
        )
        return False
    except FileNotFoundError:
        console.print(
            "[red][-] PyInstaller not found. Install it: pip install pyinstaller[/red]"
        )
        return False
    except Exception as e:
        console.print(f"[red][-] An unexpected error occurred: {e}")
        return False


def find_signtool() -> Path | None:
    """Automatically find the path to signtool.exe."""
    pf86 = os.environ.get("ProgramFiles(x86)")
    if not pf86:
        return None
    base = Path(pf86) / "Windows Kits" / "10" / "bin"
    if not base.exists():
        return None
    paths = list(base.rglob("signtool.exe"))
    if not paths:
        return None
    # prefer x64
    for p in paths:
        if "x64" in str(p).lower():
            return p
    return paths[0]


def locate_pfx() -> list[Path]:
    """Find .pfx files in repo root (recursively)."""
    return list(Path(".").rglob("*.pfx"))


def run_signing(exe_path: Path, password: str | None = None) -> bool:
    """Signs the exe using signtool + .pfx. Returns True on success or if skipped."""
    console.rule("Code Signing", style="bold yellow")

    pfx_files = locate_pfx()
    if not pfx_files:
        console.print(
            "[yellow][!] No .pfx certificate found; signing skipped.[/yellow]"
        )
        return True
    if len(pfx_files) > 1:
        console.print(
            "[red][-] Multiple .pfx files found. Keep only one in project root for automated signing.[/red]"
        )
        return False

    pfx = pfx_files[0]
    signtool = find_signtool()
    if not signtool:
        console.print(
            "[yellow][!] signtool.exe not found in Windows Kits; signing skipped.[/yellow]"
        )
        return True

    console.print(f"   [green][+] Certificate:[/green] {pfx}")
    console.print(f"   [green][+] signtool:[/green] {signtool}")

    pw = password or getpass.getpass("Enter .pfx password: ")

    cmd = [
        str(signtool),
        "sign",
        "/f",
        str(pfx),
        "/p",
        pw,
        "/fd",
        "sha256",
        "/tr",
        "http://timestamp.digicert.com",
        "/td",
        "sha256",
        str(exe_path),
    ]

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as p:
            t = p.add_task("Signing executable...", total=None)
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            p.update(t, description="[green][+] Signed[/green]")

        console.print("[bold green][+] Signing complete[/bold green]")
        return True
    except subprocess.CalledProcessError as e:
        console.print("[red][-] signtool failed to sign[/red]")
        console.print(
            Panel(
                e.stdout + "\n---\n" + e.stderr,
                title="signtool output",
                border_style="red",
            )
        )
        return False
    except Exception as e:
        console.print(f"[red][-] Signing error: {e}[/red]")
        return False


def verify_signature(exe_path: Path) -> bool:
    """Verify code signature using signtool. Returns True when signature verified or skipped."""
    console.rule("Verify Signature", style="bold magenta")

    signtool = find_signtool()
    if not signtool:
        console.print(
            "[yellow][!] signtool not available on PATH — cannot verify signature.[/yellow]"
        )
        return False

    cmd = [str(signtool), "verify", "/pa", "/v", str(exe_path)]
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as p:
            t = p.add_task("Verifying signature...", total=None)
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            p.update(t, description="[green][+] Signature verified[/green]")

        console.print("[bold green][+] Signature verified successfully[/bold green]")
        return True
    except subprocess.CalledProcessError as e:
        console.print("[red][-] Signature verification failed[/red]")
        console.print(
            Panel(
                e.stdout + "\n---\n" + e.stderr,
                title="signtool verify output",
                border_style="red",
            )
        )
        return False
    except Exception as e:
        console.print(f"[red][-] Signature verify error: {e}[/red]")
        return False


def generate_and_save_hashes(exe_path: Path) -> None:
    """Generates SHA-256, SHA-512, SHA3-256 and SHA3-512 and writes:
    - internal full log hashes_<timestamp>.txt
    - public hash.txt (SHA-256 only)
    - <EXE>.sha256 (sha256sum format)
    """
    console.rule("Generating File Hashes", style="bold blue")

    if not exe_path.exists():
        console.print(f"[red][-] File not found: {exe_path}[/red]")
        return

    algorithms = {
        "SHA-256": hashlib.sha256,
        "SHA-512": hashlib.sha512,
        "SHA3-256": hashlib.sha3_256,
        "SHA3-512": hashlib.sha3_512,
    }

    hash_results: dict[str, str] = {}

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as p:
            task = p.add_task("Computing hashes...", total=len(algorithms))
            for name, ctor in algorithms.items():
                p.update(task, description=f"Calculating {name}...")
                h = ctor()
                with open(exe_path, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        h.update(chunk)
                hash_results[name] = h.hexdigest()
                p.update(task, advance=1)
            p.update(task, description="[green][+] Hashes calculated[/green]")

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        internal = exe_path.parent / f"hashes_{ts}.txt"

        with open(internal, "w", encoding="utf-8") as fh:
            fh.write(f"File: {exe_path.name}\nGenerated: {datetime.now()}\n\n")
            for k, v in hash_results.items():
                fh.write(f"{k:<10}: {v}\n")

        sha256_value = hash_results["SHA-256"]

        public_txt = exe_path.parent / "hash.txt"
        with open(public_txt, "w", encoding="utf-8") as fh:
            fh.write(f"SHA-256: {sha256_value}\n")

        sha256_file = exe_path.parent / f"{exe_path.name}.sha256"
        with open(sha256_file, "w", encoding="utf-8") as fh:
            fh.write(f"{sha256_value}  {exe_path.name}\n")

        console.print(f"[green][+] Internal log: {internal}")
        console.print(f"[green][+] Public hash file: {public_txt}")
        console.print(f"[green][+] .sha256 file: {sha256_file}")

    except Exception as e:
        console.print(f"[red][-] Hash generation error: {e}[/red]")


# -----------------------------
# Main entry
# -----------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build, sign, verify signature, and hash SAGA-DTR Helper release"
    )
    p.add_argument(
        "--no-sign", action="store_true", help="Skip the signing step entirely"
    )
    p.add_argument("--sign", action="store_true", help="Force signing if a .pfx exists")
    p.add_argument(
        "--password",
        "-p",
        help="PFX password. WARNING: Using this is insecure as it may be saved in shell history.",
    )
    p.add_argument(
        "--verify-sign",
        action="store_true",
        help="Verify signature on the built EXE (skip sign)",
    )
    p.add_argument("--no-hash", action="store_true", help="Skip generating hash files")
    p.add_argument(
        "--clean-only", action="store_true", help="Clean build artifacts and exit"
    )
    return p.parse_args()


def _determine_signing_strategy(
    args: argparse.Namespace, pfx_files: list[Path]
) -> bool:
    """Decides whether to sign the executable based on args and pfx availability."""
    if args.no_sign:
        return False
    elif args.sign:
        return True
    else:
        # default: sign if a pfx is present
        return bool(pfx_files)


def _handle_verification() -> None:
    if not verify_signature(EXE_PATH):
        console.print(
            "[red][-] Signature verification failed or could not be performed.[/red]"
        )


def _handle_signing(args: argparse.Namespace) -> None:
    if not run_signing(EXE_PATH, password=args.password):
        console.print("[yellow][!] Signing failed or was skipped.[/yellow]")


def _process_signing(args: argparse.Namespace, want_sign: bool) -> None:
    """Handles the signing process and verification."""
    if args.verify_sign:
        _handle_verification()
        return

    if want_sign:
        _handle_signing(args)


def main() -> int:
    args = parse_args()
    console.clear()
    console.rule(f"{APP_NAME} - Build & Release", style="bold cyan")

    if args.clean_only:
        clean_build_artifacts()
        console.print("Exiting after cleaning.")
        return 0

    clean_build_artifacts()

    # ---------------------------------------------------------
    # 2. Build
    # ---------------------------------------------------------
    # Build SAGA-DTR Helper executable
    built = build_exe()
    if not built:
        console.print("[red][-] Build failed — aborting.[/red]")
        return 1

    # Copy License and Terms of Use to dist/
    for text_file in ["LICENSE", "TERMS_OF_USE.md"]:
        if Path(text_file).exists():
            shutil.copy(text_file, DIST_PATH / text_file)
            console.print(f"   [green][+] Copied {text_file} to dist/[/green]")

    # Decide signing
    pfx_files = locate_pfx()
    want_sign = _determine_signing_strategy(args, pfx_files)

    _process_signing(args, want_sign)

    # Hash generation
    if args.no_hash:
        console.print("[yellow][!] Hash generation skipped (--no-hash).[/yellow]")
    else:
        generate_and_save_hashes(EXE_PATH)

    console.rule("Build pipeline completed", style="bold green")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        console.print("\n[red]Interrupted by user[/red]")
        sys.exit(1)
