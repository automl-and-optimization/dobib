"""A Papis downloader for NeurIPS- and ICLR-style ``.cc`` proceedings sites.

These sites share the same software and each abstract page links a ready-made
``@InProceedings`` BibTeX file behind a "Bibtex" button:

* NeurIPS — ``papers.nips.cc`` / ``proceedings.neurips.cc``
* ICLR    — ``proceedings.iclr.cc``

Papis ships no downloader for them, so without this plugin their URLs have no
dedicated parser. This downloader locates the "Bibtex" link, fetches it, and
hands the BibTeX to Papis' machinery, yielding a correct ``@inproceedings``
entry with authors, booktitle, editor, pages, volume and year.

Registered as a ``papis.downloader`` entry point named ``proceedingscc`` (see
``pyproject.toml``), so Papis uses it automatically once installed.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from papis.downloaders import Downloader

#: Hosts served by the shared NeurIPS/ICLR proceedings software.
_HOST_RE = re.compile(
    r"^https?://("
    r"papers\.nips\.cc|proceedings\.neurips\.cc|papers\.neurips\.cc"
    r"|proceedings\.iclr\.cc"
    r")/",
    re.IGNORECASE,
)


class ProceedingsCCDownloader(Downloader):
    """Retrieve metadata from NeurIPS/ICLR ``.cc`` proceedings pages.

    Metadata comes solely from the BibTeX file the page links (see
    :meth:`download_bibtex`); the generic ``citation_*`` scrape is not used.
    """

    def __init__(self, url: str) -> None:
        super().__init__(url, name="proceedingscc",
                         expected_document_extension="pdf")

    @classmethod
    def match(cls, url: str) -> "Downloader | None":
        return ProceedingsCCDownloader(url) if _HOST_RE.match(url) else None

    def get_bibtex_url(self) -> "str | None":
        """Resolve the URL behind the page's "Bibtex" link.

        The link is relative and its shape differs per site (a ``/bibtex``
        endpoint on ICLR, a ``-Bibtex.bib`` file on NeurIPS), so we match on the
        link *text* rather than the href pattern.
        """
        for a in self._get_soup().find_all("a", href=True):
            if a.get_text(strip=True).lower() == "bibtex":
                return urljoin(self.uri, a["href"])

        self.logger.warning("No 'Bibtex' link found on page '%s'.", self.uri)
        return None

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
        soup = self._get_soup()
        meta = soup.find("meta", attrs={"name": "citation_pdf_url"})
        if meta is not None and meta.get("content"):
            return str(meta["content"]).strip()
        return None
