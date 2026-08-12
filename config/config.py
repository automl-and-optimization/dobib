import os
import papis.config

_cfg = os.environ.get("PAPIS_CONFIG_DIR")
_root = os.path.dirname(os.path.abspath(_cfg)) if _cfg else None

opts = {
    "settings": {
        "default-library": "group",
        "database-backend": "papis",
        "info-name": "info.yaml",
        "add-folder-name": "{doc[ref]}",
        "add-file-name": "{doc[ref]}",
        # Drop `month` from the exported references.bib. Papis normalises month
        # inconsistently across sources (e.g. "6" vs "21--27 Jul"), and it is
        # noise for citations; keep it out of the merged bibliography.
        "bibtex-ignore-keys": ["month"],
    },
}
if _root:
    opts["group"] = {"dir": os.path.join(_root, "library")}

papis.config.register_default_settings(opts)


# --------------------------------------------------------------------------- #
# Disable Papis' generic `fallback` scraper entirely.
#
# `papis add <url>` runs EVERY downloader whose match() accepts the URL and
# merges them. The catch-all `fallback` downloader scrapes arbitrary Open Graph
# / Dublin Core meta tags and routinely produces wrong metadata (e.g.
# og:type -> "article", og:description -> "abstract"). We only trust dedicated,
# site-specific downloaders (arxiv, acl, pmlr, springer, ieee, ...).
#
# If no dedicated parser matches a URL, we would rather FAIL than commit a
# scraped guess. Papis has no setting to disable a downloader, so we patch the
# fallback's match() to always decline. With no importer producing metadata,
# `groupbib add` sees an empty entry and rolls back with an error, prompting us
# to add a proper downloader (or supply a DOI / arXiv id) instead.
# --------------------------------------------------------------------------- #
import papis.downloaders.fallback   # noqa: E402

papis.downloaders.fallback.FallbackDownloader.match = classmethod(
    lambda cls, url: None)
