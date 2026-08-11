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
# Make Papis' generic `fallback` scraper behave like a *true* fallback.
#
# `papis add <url>` runs EVERY downloader whose match() accepts the URL and
# merges them, later ones overwriting earlier ones. The catch-all `fallback`
# downloader sorts last, so its Open Graph scrape (og:type, og:description)
# clobbers correct data from a dedicated, site-specific downloader. Example:
# aclanthology.org — the `acl` downloader deliberately drops the bogus
# og:description "abstract" and takes the type from the BibTeX
# (@inproceedings), but `fallback` then re-adds og:description as `abstract`
# and overwrites the type with og:type ("article").
#
# Papis has no setting to disable a downloader, so we patch the fallback's
# match() to decline whenever any dedicated downloader matches the same URL.
# `fallback` and `get` (the latter only grabs direct file links) count as
# generic, so a plain URL with no dedicated handler still uses the fallback.
# --------------------------------------------------------------------------- #
import papis.downloaders            # noqa: E402
import papis.downloaders.fallback   # noqa: E402

_GENERIC_DOWNLOADERS = {"fallback", "get"}


def _fallback_match_if_alone(cls, url):
    from papis.plugin import get_plugins
    for name, dcls in get_plugins(
            papis.downloaders.DOWNLOADERS_EXTENSION_NAME).items():
        if name in _GENERIC_DOWNLOADERS:
            continue
        try:
            if dcls.match(url) is not None:
                # A dedicated downloader handles this URL; stay out of its way.
                return None
        except Exception:
            continue
    return papis.downloaders.fallback.FallbackDownloader(url)


papis.downloaders.fallback.FallbackDownloader.match = classmethod(
    _fallback_match_if_alone)
