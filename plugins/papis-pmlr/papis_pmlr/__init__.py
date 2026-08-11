"""A Papis downloader for PMLR (``proceedings.mlr.press``).

PMLR — Proceedings of Machine Learning Research, which publishes ICML, AISTATS,
CoLT, CoRL and many other venues — has no dedicated downloader shipped with
Papis. Without one, its abstract pages fall through to Papis' generic HTML
scraper (``FallbackDownloader``), which only understands a fixed whitelist of
``citation_*`` meta tags. That whitelist omits ``citation_conference_title`` /
``citation_inbook_title``, so the venue is dropped, and since nothing supplies a
document type the paper is exported as ``@article`` instead of
``@inproceedings``.

Every PMLR abstract page, however, embeds a correct, complete ``@InProceedings``
BibTeX entry in an element with ``id="bibtex"`` (this is what the page's own
"BibTeX" button copies). This downloader extracts that block and hands it to
Papis' BibTeX machinery, which yields the right type, ``booktitle``, ``volume``,
``series``, ``editor``, ``publisher`` and the full abstract.

Registered as a ``papis.downloader`` entry point named ``pmlr`` (see
``pyproject.toml``), so Papis picks it up automatically for any
``proceedings.mlr.press`` URL once this package is installed.
"""

from __future__ import annotations

import re

from papis.downloaders import Downloader

#: Matches PMLR abstract-page URLs, e.g.
#: ``https://proceedings.mlr.press/v235/chen24e.html``.
_PMLR_URL_RE = re.compile(r"^https?://proceedings\.mlr\.press/", re.IGNORECASE)


class PMLRDownloader(Downloader):
    """Retrieve metadata from `PMLR <https://proceedings.mlr.press>`__.

    Metadata comes solely from the page's embedded ``@InProceedings`` BibTeX
    (see :meth:`download_bibtex`); we deliberately do not scrape the generic
    ``citation_*`` meta tags, which is what mislabels these papers.
    """

    def __init__(self, url: str) -> None:
        super().__init__(url, name="pmlr", expected_document_extension="pdf")

    @classmethod
    def match(cls, url: str) -> "Downloader | None":
        return PMLRDownloader(url) if _PMLR_URL_RE.match(url) else None

    def download_bibtex(self) -> None:
        """Store the ``@InProceedings`` BibTeX embedded in the PMLR page.

        Papis' :meth:`~papis.downloaders.Downloader.fetch_data` parses this via
        :func:`papis.bibtex.bibtex_to_dict` and merges it into the document, so
        the resulting entry carries the correct ``type`` and venue fields.
        """
        soup = self._get_soup()
        node = soup.find(id="bibtex")
        if node is None:
            self.logger.warning(
                "No BibTeX block (id='bibtex') found on PMLR page '%s'.", self.uri)
            return

        bibtex = node.get_text().strip()
        if bibtex:
            self.logger.info("Using BibTeX embedded in the PMLR page.")
            self.bibtex_data = bibtex

    def get_document_url(self) -> "str | None":
        """The PDF link advertised in the page's ``citation_pdf_url`` tag."""
        soup = self._get_soup()
        meta = soup.find("meta", attrs={"name": "citation_pdf_url"})
        if meta is None:
            return None

        url = meta.get("content", "")
        return str(url).strip() or None
