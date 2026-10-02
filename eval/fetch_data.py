"""Download FLORES-200 and extract the four languages we evaluate on.

    python eval/fetch_data.py            # downloads ~25 MB, writes eval/data/flores200/...

FLORES-200 (Meta AI) has 1,012 devtest sentences, aligned across 200 languages, including
san_Deva, hin_Deva, eng_Latn and zho_Hans. Source: https://github.com/facebookresearch/flores
(the dataset link there points to the tarball used below).
"""

from __future__ import annotations

import argparse
import io
import sys
import tarfile
import urllib.request
from pathlib import Path

URLS = [
    "https://tinyurl.com/flores200dataset",  # the link given in the FLORES README
    "https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz",
]
CODES = ("san_Deva", "hin_Deva", "eng_Latn", "zho_Hans")
SPLITS = {"dev": "dev", "devtest": "devtest"}


def extract(tar_bytes: bytes, out_dir: Path, codes=CODES) -> list[Path]:
    """Pull `<code>.dev` / `<code>.devtest` files out of the tarball, whatever the folder layout."""
    written: list[Path] = []
    wanted = {f"{c}.{s}" for c in codes for s in SPLITS}
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tar:
        for member in tar.getmembers():
            name = Path(member.name).name
            if member.isfile() and name in wanted:
                split = name.rsplit(".", 1)[1]
                dest = out_dir / split / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(tar.extractfile(member).read())  # type: ignore[union-attr]
                written.append(dest)
    missing = wanted - {p.name for p in written}
    if missing:
        raise SystemExit(f"Tarball is missing expected files: {sorted(missing)}")
    return written


def download() -> bytes:
    last: Exception | None = None
    for url in URLS:
        try:
            print(f"Downloading {url} ...")
            with urllib.request.urlopen(url, timeout=120) as r:
                return r.read()
        except Exception as exc:  # try the next mirror
            last = exc
            print(f"  failed: {exc}", file=sys.stderr)
    raise SystemExit(
        f"Could not download FLORES-200 ({last}).\nDownload it manually from "
        "https://github.com/facebookresearch/flores (see its README), unpack it, and copy the "
        "devtest files for san_Deva, hin_Deva, eng_Latn and zho_Hans into eval/data/flores200/devtest/."
    )


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "data" / "flores200")
    args = ap.parse_args()
    files = extract(download(), args.out)
    print(f"Wrote {len(files)} files under {args.out}")


if __name__ == "__main__":
    main()
