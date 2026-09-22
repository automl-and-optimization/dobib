# papis-jmlr

A [Papis](https://papis.readthedocs.io) downloader for the
[Journal of Machine Learning Research](https://jmlr.org) (`jmlr.org/papers/…`).

## Why

JMLR publishes without DOIs, so its papers cannot be imported through the
Crossref route that `groupbib add <doi>` uses, and Papis ships no downloader for
the site. That leaves only the generic HTML scraper, which this repository
disables on purpose — so a JMLR URL fails outright.

Each paper page links a ready-made `@article` BibTeX file from an anchor with
`id="bib"`. This plugin follows that link, fetches it, and lets Papis parse it —
giving a correct `@article` entry (authors, journal, volume, number, pages,
year).

## Install

Papis discovers downloaders through installed entry-point metadata, so install
into the same environment as `papis`:

```sh
pip install -e plugins/papis-jmlr
```

(Run from the repository root.)

Verify it registered:

```sh
papis exec <(echo 'import papis.plugin as p; print("jmlr" in p.get_plugin_names("papis.downloader"))')
```

Once installed, Papis (and `groupbib add <url>`) routes any JMLR paper URL
through this downloader automatically.

## Note on TMLR

Transactions on Machine Learning Research (`jmlr.org/tmlr/`) is a different site
with a different page layout and is **not** handled here. TMLR papers are hosted
on OpenReview; import those from their OpenReview URL or DOI instead.
