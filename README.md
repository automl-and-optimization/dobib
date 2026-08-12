# dobib — shared group bibliography

A single, canonical BibTeX file for the whole working group, so that every
`\cite{...}` across all our papers resolves to the same, correct reference.

The **source of truth** is a metadata-only [Papis](https://papis.readthedocs.io)
library under `library/`. Each paper has a stable, group-wide **citation key**
(stored in the Papis `ref` field). A small wrapper script, `bin/groupbib`,
fetches metadata via Papis, regenerates `references.bib`, and commits/pushes —
all synchronously on your machine. There is **no CI/build step**.

```
dobib/
├── library/                 # source of truth: one folder per paper
│   ├── vaswani-neurips2017a/
│   │   └── info.yaml
│   └── ...
├── references.bib           # GENERATED — do not edit by hand
├── bin/groupbib             # the wrapper script
├── config/config.py         # shared Papis configuration (loaded via PAPIS_CONFIG_DIR)
├── plugins/papis-pmlr/      # Papis downloader for PMLR (proceedings.mlr.press)
└── README.md
```

## Requirements

- [Papis](https://papis.readthedocs.io) (`pipx install papis` or `pip install papis`)
- `git`, `python3`

## Setup

```bash
git clone <this-repo-url> dobib
cd dobib
# optional: put groupbib on your PATH
ln -s "$PWD/bin/groupbib" ~/.local/bin/groupbib
# required only for PMLR (ICML/AISTATS/…) URLs — registers a Papis downloader:
pip install -e plugins/papis-pmlr
```

`bin/groupbib` locates the repository from its own path, so it works from
anywhere inside the repo (or via the symlink above).

## Everyday use

Add a new reference (DOI, arXiv id, or URL). The **first argument is the
citation key you want** — that key is authoritative and never changes, even if
upstream metadata changes later.

**Citation keys must follow the scheme** `lastname-venueYYYYx`:

- `lastname` — first author's last name, lowercase (may be hyphenated, e.g.
  `opsahl-ong`);
- `venue` — lowercase conference/journal abbreviation (`icml`, `neurips`,
  `cvpr`, `emnlp`, …);
- `YYYY` — 4-digit publication year;
- `x` — a single letter disambiguating same author/venue/year (`…2024a`,
  `…2024b`).

`groupbib add` refuses a key that doesn't match, and `groupbib check` flags any
existing key that doesn't.

```bash
bin/groupbib add vaswani-neurips2017a 10.48550/arXiv.1706.03762
bin/groupbib add he-cvpr2016a          arxiv:1512.03385
bin/groupbib add smith-icml2024b       https://example.org/paper
```

Each `add`/`update` runs the full pipeline:

```
git pull --rebase → refresh papis cache → add/update metadata
  → validate (duplicate keys / DOIs) → export references.bib
  → commit (only library/ + references.bib) → git push
```

Refresh an existing entry. `update` is a **clean re-fetch**: it re-imports from
the entry's own stored identifier (or one you pass) and never does a fuzzy
title search, so it can't silently swap in an unrelated paper. Any manual edits
to that entry's `info.yaml` are discarded by the re-fetch.

```bash
bin/groupbib update he-cvpr2016a                 # re-fetch from its stored id
bin/groupbib update he-cvpr2016a arxiv:1512.03385  # or from an explicit one
```

### PMLR (ICML, AISTATS, CoLT, …)

PMLR has no built-in Papis downloader, so plain scraping mislabels its papers
as `@article` and drops the venue. This repo ships a downloader
(`plugins/papis-pmlr`) that reads the correct `@InProceedings` BibTeX embedded
in each PMLR page. Install it once (`pip install -e plugins/papis-pmlr`), then:

```bash
bin/groupbib add chen-icml2024a https://proceedings.mlr.press/v235/chen24e.html
```

If the plugin isn't installed, `groupbib` refuses PMLR URLs rather than commit a
broken entry.

Other commands:

```bash
bin/groupbib list             # show citation keys and DOIs
bin/groupbib check            # validate without changing anything
bin/groupbib export           # regenerate references.bib only
bin/groupbib export --commit  # ...and commit + push it
```

## Rules of the road

- **Humans edit only the metadata.** `references.bib` is a build artifact.
  Never edit it by hand — regenerate it with `bin/groupbib export`.
- **One canonical citation key per paper**, chosen by you and stored in `ref`.
  `groupbib` refuses to create duplicate keys or duplicate DOIs.
- To hand-edit metadata, use
  `PAPIS_CONFIG_DIR=$PWD/config papis -l group edit ref:<key>`,
  then `bin/groupbib export --commit`.
- If two people race and Git reports a **conflict in `references.bib`**, do
  **not** merge it by hand. Resolve the `library/*/info.yaml` changes, then
  regenerate: `bin/groupbib export --commit`.

## Using it in Overleaf

Make this repository (or at least `references.bib`) reachable via a raw,
unauthenticated URL — e.g. a **public** GitHub repo:

```
https://raw.githubusercontent.com/<org>/dobib/main/references.bib
```

In Overleaf: **Add file → From External URL**, paste that URL, and name it
`references.bib`. After anyone pushes an update, Overleaf users just click
**Refresh** on the linked file — it is not a live include. The generated file
carries a `@comment{Generated <date> ...}` banner so a stale copy is obvious.
