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
# venue downloaders (register Papis plugins); install the ones you need:
pip install -e plugins/papis-pmlr             # PMLR: ICML, AISTATS, CoLT, …
pip install -e plugins/papis-proceedings-cc   # NeurIPS & ICLR .cc proceedings
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
bin/groupbib add opsahl-ong-emnlp2024a https://aclanthology.org/2024.emnlp-main.525/
```

A URL is only accepted if Papis has a **dedicated downloader** for that venue
(arXiv, ACL Anthology, PMLR, Springer, IEEE, …). The generic HTML scraper is
disabled on purpose: rather than guess metadata from arbitrary pages (which
produced wrong types and fake abstracts), `groupbib add` **fails** when no
dedicated parser matches. In that case, supply a DOI / arXiv id, or add a
downloader for the venue (see `plugins/papis-pmlr` for a template).

Each `add`/`update` runs the full pipeline:

```
git pull --rebase → refresh papis cache → add/update metadata
  → validate (duplicate keys / DOIs) → export references.bib
  → show the references.bib diff and ask [y/N]
  → commit (only library/ + references.bib) → git push
```

Before anything is committed, `groupbib` prints the `references.bib` diff and
asks for confirmation. Answer `n` (the default) and it rolls back — the entry
and the regenerated `references.bib` are restored, nothing is committed or
pushed. Pass `-y`/`--yes` to skip the prompt (e.g. in scripts); in a
non-interactive shell the prompt defaults to *no* unless `--yes` is given.

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

### NeurIPS & ICLR (`.cc` proceedings)

`papers.nips.cc` / `proceedings.neurips.cc` and `proceedings.iclr.cc` also lack
a built-in Papis downloader but link a ready-made BibTeX file on each page. The
`plugins/papis-proceedings-cc` downloader reads it. Install it once
(`pip install -e plugins/papis-proceedings-cc`), then:

```bash
bin/groupbib add feurer-neurips2015a https://papers.nips.cc/paper_files/paper/2015/hash/11d0e6287202fced83f79975ec59a3a6-Abstract.html
bin/groupbib add agrawal-iclr2026a   https://proceedings.iclr.cc/paper_files/paper/2026/hash/0e9e708b6f48e14fd0ac29e167413f76-Abstract-Conference.html
```

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
