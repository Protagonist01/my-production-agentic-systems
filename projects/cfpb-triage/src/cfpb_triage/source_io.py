"""External-only source files, bounded official acquisition and byte pins."""

import hashlib
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from cfpb_triage.source_contracts import ARCHIVE_URL, TAXONOMY_URL, SourcePin


def external_path(path: Path) -> Path:
    """Reject raw storage below any checkout, including the caller's different worktree."""
    resolved = path.expanduser().resolve()
    if any((parent / ".git").exists() for parent in (resolved, *resolved.parents)):
        raise ValueError("Source and prepared records must be outside Git checkouts")
    return resolved


def digest_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_sources(archive: Path, taxonomy: Path, pin: SourcePin) -> tuple[Path, Path]:
    archive, taxonomy = external_path(archive), external_path(taxonomy)
    if digest_file(archive) != pin.archive_sha256:
        raise ValueError("Archive differs from independently supplied source pin")
    if digest_file(taxonomy) != pin.taxonomy_sha256:
        raise ValueError("Taxonomy differs from independently supplied source pin")
    if not taxonomy.read_bytes().startswith(b"%PDF-"):
        raise ValueError("Taxonomy source is not a PDF")
    return archive, taxonomy


class OfficialRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: object, code: int, msg: str, headers: object, newurl: str
    ) -> Request | None:
        parsed = urlparse(newurl)
        if parsed.scheme != "https" or parsed.hostname != "files.consumerfinance.gov":
            raise ValueError("Source redirect leaves the official HTTPS host")
        return super().redirect_request(req, fp, code, msg, headers, newurl)  # type: ignore[arg-type]


def acquire_file(url: str, destination: Path, digest: str, maximum_bytes: int) -> None:
    destination = external_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if destination.exists():
        if digest_file(destination) != digest:
            raise ValueError("Existing source differs from pin; no overwrite")
        return
    descriptor, temporary = tempfile.mkstemp(dir=destination.parent, suffix=".partial")
    try:
        with (
            os.fdopen(descriptor, "wb") as output,
            build_opener(OfficialRedirect()).open(url, timeout=60) as response,
        ):
            size = 0
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > maximum_bytes:
                    raise ValueError("Official source exceeds acquisition byte cap")
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if digest_file(Path(temporary)) != digest:
            raise ValueError("Downloaded source differs from pin; nothing published")
        os.link(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def acquire_sources(directory: Path, pin: SourcePin) -> tuple[Path, Path]:
    directory = external_path(directory)
    archive, taxonomy = directory / "source.zip", directory / "taxonomy.pdf"
    acquire_file(ARCHIVE_URL, archive, pin.archive_sha256, 150_000_000)
    acquire_file(TAXONOMY_URL, taxonomy, pin.taxonomy_sha256, 10_000_000)
    return verify_sources(archive, taxonomy, pin)
