# papis-pmlr

A [Papis](https://papis.readthedocs.io) downloader for
[PMLR](https://proceedings.mlr.press) (Proceedings of Machine Learning
Research: ICML, AISTATS, CoLT, CoRL, …).

## Why

PMLR ships no downloader with Papis, so its pages fall through to the generic
HTML scraper. That scraper ignores `citation_conference_title` and does not set
a document type, so PMLR papers import as `@article` with no venue. This plugin
instead reads the correct `@InProceedings` BibTeX that every PMLR page embeds
(the block behind the page's "BibTeX" button), yielding the right type,
`booktitle`, `volume`, `series`, `editor`, `publisher`, and full abstract.

## Install

Papis discovers downloaders through installed entry-point metadata, so the
plugin must be installed into the same environment as `papis`:

```sh
pip install -e plugins/papis-pmlr
```

(Run from the repository root. The editable install keeps the source in the
repo, so edits take effect without reinstalling.)

Verify it registered (`papis exec` runs a file in Papis' own environment):

```sh
papis exec <(echo 'import papis.plugin as p; print("pmlr" in p.get_plugin_names("papis.downloader"))')
```

Once installed, Papis (and therefore `groupbib add <pmlr-url>`) routes any
`proceedings.mlr.press` URL through this downloader automatically.
