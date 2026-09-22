"""A Papis downloader for OpenReview (``openreview.net``).

OpenReview hosts TMLR, workshop papers and the submission records for most ML
conferences. Papis ships no downloader for it, and the site cannot be scraped:
unauthenticated requests to both the pages and the API are answered with a
browser-verification challenge (HTTP 403 ``ChallengeRequiredError``).

Signing in bypasses that challenge, so this downloader talks to the official
API through the ``openreview-py`` client. Every published note carries a
ready-made ``_bibtex`` field -- the citation OpenReview itself offers -- which
is handed to Papis' BibTeX machinery.

Credentials come from the environment, never from this repository::

    export OPENREVIEW_USERNAME='you@example.org'
    export OPENREVIEW_PASSWORD='...'

``openreview-py`` reads those two variables on its own; we only check that they
are set so we can fail with a useful message instead of a challenge error.

OpenReview runs two API generations -- ``api2`` for venues from 2023 on and
``api`` for older ones -- and a forum id is only valid on one of them, so both
are tried in turn.

Registered as a ``papis.downloader`` entry point named ``openreview`` (see
``pyproject.toml``), so Papis picks it up automatically once installed.
"""

from __future__ import annotations

import os
import re
from urllib.parse import parse_qs, urlparse

from papis.downloaders import Downloader

#: Matches the OpenReview URLs that identify a paper by a forum id, e.g.
#: ``https://openreview.net/forum?id=StSMBSZqxx``. ``pdf`` and ``attachment``
#: carry the same id, so a pasted PDF link works too.
_OPENREVIEW_URL_RE = re.compile(
    r"^https?://(?:www\.)?openreview\.net/(?:forum|pdf|attachment)\b",
    re.IGNORECASE,
)

#: The two API generations, newest first. A forum id exists on exactly one.
_API_BASE_URLS = [
    ("v2", "https://api2.openreview.net"),
    ("v1", "https://api.openreview.net"),
]

_CREDENTIALS_HELP = (
    "OpenReview requires signing in: unauthenticated requests are answered "
    "with a browser-verification challenge. Set OPENREVIEW_USERNAME and "
    "OPENREVIEW_PASSWORD in your environment and try again."
)


def forum_id(url: str) -> "str | None":
    """Extract the ``id`` query parameter identifying the paper."""
    ids = parse_qs(urlparse(url).query).get("id")
    return ids[0] if ids else None


def _content_value(content: dict, key: str) -> "str | None":
    """Read a note field, tolerating both API generations.

    API v2 wraps every field as ``{"value": ...}``; API v1 stores it directly.
    """
    entry = (content or {}).get(key)
    if isinstance(entry, dict):
        entry = entry.get("value")
    if entry is None:
        return None

    text = str(entry).strip()
    return text or None


class OpenReviewDownloader(Downloader):
    """Retrieve metadata from `OpenReview <https://openreview.net>`__.

    Metadata comes from the note's own ``_bibtex`` field (see
    :meth:`download_bibtex`), which is what the site's "BibTeX" button copies.
    """

    def __init__(self, url: str) -> None:
        super().__init__(url, name="openreview",
                         expected_document_extension="pdf")
        self._note = None
        self._note_fetched = False

    @classmethod
    def match(cls, url: str) -> "Downloader | None":
        if not _OPENREVIEW_URL_RE.match(url):
            return None
        # A URL without an id names no paper; decline rather than fail later.
        return OpenReviewDownloader(url) if forum_id(url) else None

    def get_note(self):
        """Fetch the forum's own note, trying both API generations.

        The result is cached: :meth:`download_bibtex` and
        :meth:`get_document_url` both need it.
        """
        if self._note_fetched:
            return self._note

        self._note_fetched = True
        paper_id = forum_id(self.uri)
        if paper_id is None:
            return None

        if not (os.environ.get("OPENREVIEW_USERNAME")
                and os.environ.get("OPENREVIEW_PASSWORD")):
            self.logger.error("%s", _CREDENTIALS_HELP)
            return None

        import openreview
        import openreview.api

        errors = []
        for label, baseurl in _API_BASE_URLS:
            client_cls = (openreview.api.OpenReviewClient if label == "v2"
                          else openreview.Client)
            try:
                client = client_cls(baseurl=baseurl)
                self._note = client.get_note(paper_id)
            except Exception as exc:
                errors.append(f"{label}: {exc}")
                continue

            if self._note is not None:
                self.logger.info("Found '%s' on the OpenReview %s API.",
                                 paper_id, label)
                return self._note

        self.logger.warning(
            "Could not retrieve OpenReview note '%s' (%s).",
            paper_id, "; ".join(errors) or "not found on either API")
        return None

    def download_bibtex(self) -> None:
        """Store the note's own ``_bibtex`` entry."""
        note = self.get_note()
        if note is None:
            return

        bibtex = _content_value(getattr(note, "content", None), "_bibtex")
        if bibtex is None:
            self.logger.warning(
                "OpenReview note '%s' carries no '_bibtex' field. Unpublished "
                "submissions often do not; cite it as an arXiv preprint "
                "instead.", forum_id(self.uri))
            return

        if bibtex.startswith("@"):
            self.bibtex_data = bibtex
        else:
            self.logger.warning(
                "The '_bibtex' field of note '%s' does not look like BibTeX.",
                forum_id(self.uri))

    def get_document_url(self) -> "str | None":
        """The PDF, which OpenReview stores as a path relative to the site."""
        note = self.get_note()
        if note is None:
            return None

        pdf = _content_value(getattr(note, "content", None), "pdf")
        if pdf is None:
            return None

        return f"https://openreview.net{pdf}" if pdf.startswith("/") else pdf
