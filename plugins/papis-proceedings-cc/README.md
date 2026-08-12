# papis-proceedings-cc

A [Papis](https://papis.readthedocs.io) downloader for the NeurIPS- and
ICLR-style `.cc` proceedings sites:

- NeurIPS — `papers.nips.cc`, `proceedings.neurips.cc`
- ICLR — `proceedings.iclr.cc`

## Why

Papis ships no downloader for these sites. Each abstract page, however, links a
ready-made `@InProceedings` BibTeX file behind a "Bibtex" button. This plugin
finds that link, fetches it, and lets Papis parse it — giving a correct
`@inproceedings` entry (authors, booktitle, editor, pages, volume, year).

## Install

Papis discovers downloaders through installed entry-point metadata, so install
into the same environment as `papis`:

```sh
pip install -e plugins/papis-proceedings-cc
```

(Run from the repository root.)

Verify it registered:

```sh
papis exec <(echo 'import papis.plugin as p; print("proceedingscc" in p.get_plugin_names("papis.downloader"))')
```

Once installed, Papis (and `groupbib add <url>`) routes any NeurIPS/ICLR `.cc`
proceedings URL through this downloader automatically.
