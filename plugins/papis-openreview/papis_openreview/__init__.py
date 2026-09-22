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

Signing in is the scarce operation here: both generations share one ``/login``
endpoint, which allows only three requests per half-minute, while ordinary
reads are not limited that tightly. A client that logs in per API generation
therefore exhausts the budget after two ``groupbib`` runs, and the second run
fails with a rate-limit error that looks like "the paper does not exist". So we
log in once, share that token with both generations, and cache it on disk
between runs (see :func:`_login`).

Registered as a ``papis.downloader`` entry point named ``openreview`` (see
``pyproject.toml``), so Papis picks it up automatically once installed.
"""

from __future__ import annotations

import os
import re
import time
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

#: Appended to a sign-in failure, so the separator belongs to the phrase.
_RATE_LIMIT_HELP = (
    " -- OpenReview allows only a few sign-ins per half-minute; wait a minute "
    "and try again."
)

#: Errors that mean the token we presented is no good -- as opposed to
#: ``ForbiddenError``, which also covers notes that exist but are not ours to
#: read, and which must not cost another sign-in.
_STALE_TOKEN_ERRORS = {"TokenExpiredError", "UnauthorizedError"}

#: The login token for this process, once we have one.
_TOKEN = None


def forum_id(url: str) -> "str | None":
    """Extract the ``id`` query parameter identifying the paper."""
    ids = parse_qs(urlparse(url).query).get("id")
    return ids[0] if ids else None


def _token_cache_path() -> str:
    """Where the login token is kept between runs."""
    base = (os.environ.get("XDG_CACHE_HOME")
            or os.path.join(os.path.expanduser("~"), ".cache"))
    return os.path.join(base, "papis-openreview", "token")


def _cached_token() -> "str | None":
    """The stored token, if it is still good for the lookup ahead."""
    try:
        with open(_token_cache_path(), encoding="utf-8") as handle:
            token = handle.read().strip()
    except OSError:
        return None
    if not token:
        return None

    try:
        import jwt
        expiry = jwt.decode(token, options={"verify_signature": False}).get("exp")
    except Exception:
        return None

    # A minute of leeway, so a token cannot expire between this check and the
    # request it is used for. An unreadable expiry counts as expired: a fresh
    # sign-in is cheaper than a rejected lookup.
    return token if expiry and expiry - 60 > time.time() else None


def _store_token(token: str) -> None:
    """Cache the token for later runs, readable only by this user."""
    path = _token_cache_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(token)
        # The token authenticates as the user, so tighten the mode even if the
        # file already existed with a wider one.
        os.chmod(path, 0o600)
    except OSError:
        pass  # Caching is an optimisation; an unwritable cache is not an error.


def _login(refresh: bool = False) -> "str | None":
    """A login token: from this process, from the cache, or from a sign-in.

    Pass ``refresh`` to skip both caches after the API rejected the token we
    had. May raise whatever ``openreview-py`` raises on a failed sign-in.
    """
    global _TOKEN

    if refresh:
        _TOKEN = None
    elif _TOKEN is None:
        _TOKEN = _cached_token()
    if _TOKEN is not None:
        return _TOKEN

    import openreview.api

    # Constructing a client without a token signs in with the environment's
    # credentials; the generation does not matter, the token works on both.
    client = openreview.api.OpenReviewClient(baseurl=_API_BASE_URLS[0][1])
    _TOKEN = client.token
    if _TOKEN:
        _store_token(_TOKEN)
    return _TOKEN


def _api_error(exc: Exception) -> dict:
    """The API's own error payload, which ``OpenReviewException`` wraps."""
    args = getattr(exc, "args", ())
    return args[0] if args and isinstance(args[0], dict) else {}


def _describe(exc: Exception) -> str:
    """One readable line for an API error; ``str(exc)`` is a JSON dump."""
    error = _api_error(exc)
    name, message = error.get("name"), error.get("message")
    return f"{name}: {message}" if name and message else str(exc)


def _is_rate_limit(exc: Exception) -> bool:
    error = _api_error(exc)
    return error.get("name") == "RateLimitError" or error.get("status") == 429


def _is_stale_token(exc: Exception) -> bool:
    error = _api_error(exc)
    return error.get("name") in _STALE_TOKEN_ERRORS or error.get("status") == 401


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

    def _ask_apis(self, paper_id: str, token: "str | None"):
        """Ask both API generations for the note; the first hit wins.

        Returns the note (or ``None``) together with the errors each
        generation raised, so the caller can tell "no such note" apart from
        "we never got an answer".
        """
        import openreview
        import openreview.api

        errors = []
        for label, baseurl in _API_BASE_URLS:
            client_cls = (openreview.api.OpenReviewClient if label == "v2"
                          else openreview.Client)
            try:
                client = client_cls(baseurl=baseurl, token=token)
                note = client.get_note(paper_id)
            except Exception as exc:
                errors.append((label, exc))
                continue

            if note is not None:
                self.logger.info("Found '%s' on the OpenReview %s API.",
                                 paper_id, label)
                return note, errors

        return None, errors

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

        try:
            token = _login()
        except Exception as exc:
            self.logger.error(
                "Could not sign in to OpenReview: %s%s", _describe(exc),
                _RATE_LIMIT_HELP if _is_rate_limit(exc) else "")
            return None

        note, errors = self._ask_apis(paper_id, token)
        if note is None and any(_is_stale_token(exc) for _, exc in errors):
            # The cached token was rejected even though it looked unexpired;
            # spend one sign-in on a fresh one, then take the answer as final.
            try:
                note, errors = self._ask_apis(paper_id, _login(refresh=True))
            except Exception as exc:
                self.logger.error(
                    "Could not sign in to OpenReview: %s%s", _describe(exc),
                    _RATE_LIMIT_HELP if _is_rate_limit(exc) else "")
                return None

        detail = "; ".join(f"{label}: {_describe(exc)}" for label, exc in errors)
        if note is None:
            throttled = [label for label, exc in errors if _is_rate_limit(exc)]
            if throttled:
                # Never report this as a missing paper: the API we were cut off
                # from is exactly the one that would have known.
                self.logger.warning(
                    "OpenReview throttled the %s lookup of '%s', so whether "
                    "the note exists is still unknown; try again in a minute "
                    "(%s).", "/".join(throttled), paper_id, detail)
            else:
                self.logger.warning(
                    "Could not retrieve OpenReview note '%s' (%s).",
                    paper_id, detail or "not found on either API")
            return None

        self._note = note
        return note

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
