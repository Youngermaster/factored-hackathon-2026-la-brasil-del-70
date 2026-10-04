"""Private artifact transfer with the VM managed identity; tokens stay in process memory."""

import argparse
import base64
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

CHUNK = 4 * 1024 * 1024


def _token() -> str:
    request = urllib.request.Request(  # nosec B310 (fixed Azure IMDS address)
        "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https%3A%2F%2Fstorage.azure.com%2F",
        headers={"Metadata": "true"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310  # nosec B310
        return str(json.load(response)["access_token"])


def transfer(action: str, account: str, name: str, path: Path, expected: str | None = None) -> None:
    if not re.fullmatch(r"[a-z0-9]{3,24}", account) or ".." in name.split("/"):
        raise ValueError("invalid artifact address")
    url = f"https://{account}.blob.core.windows.net/artifacts/{quote(name, safe='/')}"
    token = _token()

    def request(method: str, suffix: str = "", data: bytes | None = None) -> bytes:
        headers = {"Authorization": f"Bearer {token}", "x-ms-version": "2023-11-03"}
        if method == "PUT":
            headers["Content-Type"] = "application/octet-stream"
        req = urllib.request.Request(url + suffix, data=data, headers=headers, method=method)  # noqa: S310  # nosec B310
        with urllib.request.urlopen(req, timeout=120) as response:  # noqa: S310  # nosec B310
            return bytes(response.read())

    if action == "download":
        path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(  # nosec B310
            url, headers={"Authorization": f"Bearer {token}", "x-ms-version": "2023-11-03"}
        )
        digest = hashlib.sha256()
        partial = path.with_suffix(path.suffix + ".partial")
        with urllib.request.urlopen(req, timeout=120) as response, partial.open("wb") as handle:  # noqa: S310  # nosec B310
            while chunk := response.read(CHUNK):
                handle.write(chunk)
                digest.update(chunk)
        if expected is None or digest.hexdigest() != expected:
            partial.unlink()
            raise ValueError("artifact SHA-256 mismatch")
        partial.replace(path)
    else:
        blocks: list[str] = []
        with path.open("rb") as upload_handle:
            while chunk := upload_handle.read(CHUNK):
                block = base64.b64encode(f"{len(blocks):08d}".encode()).decode()
                request("PUT", f"?comp=block&blockid={quote(block, safe='')}", chunk)
                blocks.append(f"<Latest>{block}</Latest>")
        request("PUT", "?comp=blocklist", ("<BlockList>" + "".join(blocks) + "</BlockList>").encode())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("upload", "download"))
    parser.add_argument("account")
    parser.add_argument("name")
    parser.add_argument("path", type=Path)
    parser.add_argument("--sha256")
    args = parser.parse_args()
    try:
        transfer(args.action, args.account, args.name, args.path, args.sha256)
    except (OSError, ValueError, KeyError, urllib.error.URLError) as error:
        sys.stderr.write(f"Artifact transfer failed ({type(error).__name__}); no credentials logged.\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
