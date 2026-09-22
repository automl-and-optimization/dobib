"""A Papis downloader for JMLR (``jmlr.org``).

The Journal of Machine Learning Research publishes without DOIs, so its papers
cannot be imported through the Crossref route that ``groupbib add <doi>`` uses.
Papis ships no downloader for the site either, which leaves its pages to the
generic HTML scraper -- disabled in this repository on purpose (see
``config/config.py``), so a JMLR URL simply fails.

Every JMLR paper page links a ready-made ``@article`` BibTeX file from an
anchor with ``id="bib"``. This downloader follows that link, fetches the
BibTeX and hands it to Papis' machinery, yielding a correct ``@article`` entry
with authors, journal, volume, number, pages and year.

Registered as a ``papis.downloader`` entry point named ``jmlr`` (see
``pyproject.toml``), so Papis picks it up automatically once installed.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from papis.downloaders import Downloader

#: Matches JMLR paper pages, e.g.
#: ``https://jmlr.org/papers/v11/strumbelj10a.html``. The site is served from
#: both the bare domain and ``www``; ``/papers/`` keeps the match to papers
#: rather than the journal's many other pages.
_JMLR_URL_RE = re.compile(
    r"^https?://(?:www\.)?jmlr\.org/papers/", re.IGNORECASE)


class JMLRDownloader(Downloader):
    """Retrieve metadata from `JMLR <https://jmlr.org>`__.

    Metadata comes solely from the BibTeX file the page links (see
    :meth:`download_bibtex`), not from the generic ``citation_*`` meta tags:
    the BibTeX is what the journal itself considers the canonical citation.
    """

    def __init__(self, url: str) -> None:
        super().__init__(url, name="jmlr", expected_document_extension="pdf")

    @classmethod
    def match(cls, url: str) -> "Downloader | None":
        return JMLRDownloader(url) if _JMLR_URL_RE.match(url) else None

    def get_bibtex_url(self) -> "str | None":
        """Resolve the URL behind the page's "bib" link.

        JMLR marks it with ``id="bib"``, which is a more precise anchor than
        the link text; the href is relative, so resolve it against the page.
        """
        node = self._get_soup().find("a", id="bib", href=True)
        if node is None:
            self.logger.warning(
                "No 'bib' link (id='bib') found on JMLR page '%s'.", self.uri)
            return None

        return urljoin(self.uri, node["href"])

    def download_bibtex(self) -> None:
        url = self.get_bibtex_url()
        if url is None:
            return

        self.logger.info("Downloading BibTeX from '%s'.", url)
        response = self.session.get(url, cookies=self.cookies)
        bibtex = response.content.decode().strip()
        if bibtex.startswith("@"):
            self.bibtex_data = bibtex
        else:
            self.logger.warning(
                "Content at '%s' does not look like BibTeX.", url)

    def get_document_url(self) -> "str | None":
        """The PDF link advertised in the page's ``citation_pdf_url`` tag."""
        soup = self._get_soup()
        meta = soup.find("meta", attrs={"name": "citation_pdf_url"})
        if meta is not None and meta.get("content"):
            return str(meta["content"]).strip()
        return None
