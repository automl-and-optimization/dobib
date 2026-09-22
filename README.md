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
├── references.bib           # GENERATED — BibLaTeX flavour, do not edit by hand
├── references-plain.bib     # GENERATED — plain-BibTeX flavour, same library
├── bin/groupbib             # the wrapper script
├── config/config.py         # shared Papis configuration (loaded via PAPIS_CONFIG_DIR)
├── plugins/papis-pmlr/      # Papis downloader for PMLR (proceedings.mlr.press)
├── plugins/papis-jmlr/      # Papis downloader for JMLR (jmlr.org)
├── plugins/papis-openreview/ # Papis downloader for OpenReview (needs login)
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
pip install -e plugins/papis-jmlr             # JMLR (jmlr.org)
pip install -e plugins/papis-openreview       # OpenReview (needs an account)
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
  `cvpr`, `emnlp`, …). It may contain digits after its first character, which
  workshop names often need (`fm4sciencews`, `ai4science`, `ml4h`); it must
  start with a letter, so that the 4-digit year stays unambiguous;
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
dedicated parser matches. In that case, supply a DOI / arXiv id, add a
downloader for the venue (see `plugins/papis-pmlr` for a template), or — for a
one-off web source — enter it by hand (see
[Citing a web page](#citing-a-web-page)).

Each `add`/`update` runs the full pipeline:

```
git pull --rebase → refresh papis cache → add/update metadata
  → validate (duplicate keys / DOIs) → export both .bib files
  → show the .bib diffs and ask [y/N]
  → commit (only library/ + the .bib files) → git push
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

`{papers,proceedings}.{nips,neurips}.cc` and `proceedings.iclr.cc` also lack
a built-in Papis downloader but link a ready-made BibTeX file on each page. The
`plugins/papis-proceedings-cc` downloader reads it. Install it once
(`pip install -e plugins/papis-proceedings-cc`), then:

```bash
bin/groupbib add feurer-neurips2015a https://papers.nips.cc/paper_files/paper/2015/hash/11d0e6287202fced83f79975ec59a3a6-Abstract.html
bin/groupbib add agrawal-iclr2026a   https://proceedings.iclr.cc/paper_files/paper/2026/hash/0e9e708b6f48e14fd0ac29e167413f76-Abstract-Conference.html
```

### JMLR

JMLR publishes without DOIs, so its papers cannot come in via the Crossref
route, and Papis ships no downloader for `jmlr.org`. Each paper page links a
ready-made `@article` BibTeX file (the `bib` button); the `plugins/papis-jmlr`
downloader follows it. Install it once (`pip install -e plugins/papis-jmlr`),
then:

```bash
bin/groupbib add strumbelj-jmlr2010a https://jmlr.org/papers/v11/strumbelj10a.html
```

TMLR (`jmlr.org/tmlr/`) is a separate site with a different layout and is not
handled; import those from OpenReview or by DOI.

### OpenReview (TMLR, workshop papers, submissions)

OpenReview cannot be scraped: unauthenticated requests to both its pages and its
API are answered with a browser-verification challenge (`403
ChallengeRequiredError`). Signing in bypasses it, so `plugins/papis-openreview`
talks to the official API through the `openreview-py` client and reads the
note's own `_bibtex` field. Install it once (`pip install -e
plugins/papis-openreview`) and put your credentials **in your environment, never
in this repository**:

```bash
export OPENREVIEW_USERNAME='you@example.org'
export OPENREVIEW_PASSWORD='...'
```

`openreview-py` reads those two variables itself; a free account suffices. Then:

```bash
bin/groupbib add witter-tmlr2025a https://openreview.net/forum?id=StSMBSZqxx
```

Both API generations are tried (`api2` for venues from 2023 on, `api` for older
ones), since a forum id is valid on only one. `pdf` and `attachment` URLs carry
the same id and work too.

For an **accepted ICLR paper, prefer the `proceedings.iclr.cc` URL** — that
record has editors and pages, which the OpenReview one lacks. Unpublished
submissions often carry no `_bibtex` at all; cite the arXiv version instead.

### Citing a web page

A blog post, a tech report on someone's homepage, a documentation page — these
have no DOI, no arXiv id, and no venue downloader, and their pages rarely carry
usable metadata (Keller Jordan's Muon post, for instance, has an *empty*
`<meta name="author">` and no `citation_*` tags). `groupbib add <url>` therefore
refuses them, by the same rule that disables the generic scraper: better to
fail than to commit an invented byline.

Enter these by hand. Add the entry with Papis directly, then regenerate the
bibliography:

```bash
PAPIS_CONFIG_DIR=$PWD/config papis -l group add --batch --no-download-files \
  --set ref          jordan-blog2024a \
  --set type         misc \
  --set author       "Jordan, Keller" \
  --set title        "Muon: An optimizer for hidden layers in neural networks" \
  --set howpublished '\url{https://kellerjordan.github.io/posts/muon/}' \
  --set url          "https://kellerjordan.github.io/posts/muon/" \
  --set urldate      "2026-09-22" \
  --set year         2024

bin/groupbib export --commit
```

which yields

```bibtex
@misc{jordan-blog2024a,
  author = {Jordan, Keller},
  howpublished = {\url{https://kellerjordan.github.io/posts/muon/}},
  title = {Muon: An optimizer for hidden layers in neural networks},
  url = {https://kellerjordan.github.io/posts/muon/},
  urldate = {2026-09-22},
  year = {2024},
}
```

Notes:

- **`@misc` + `howpublished`, not `@online`.** `@online` is BibLaTeX-only and
  renders as nothing under the plain BibTeX styles most conference templates
  use (`plainnat`, `unsrtnat`, venue `.bst` files). `@misc` with the URL in
  `howpublished` works everywhere.
- **`howpublished` is exported verbatim.** Papis escapes every field that is not
  on its verbatim list, which would turn `\url{...}` into
  `\textbackslash url{...}`; `config/config.py` adds `howpublished` to that list
  so the command survives. `\url` needs the `url` or `hyperref` package.
- **The key still follows the scheme**, so pick a venue slug — `blog` here.
  `groupbib check` validates these entries like any other.
- **`groupbib update` will not work on a manual entry**: it has no stored DOI or
  arXiv id to re-fetch from and fails with a clear message. That is deliberate —
  nothing can silently overwrite what you typed. To change it, edit and
  re-export:

  ```bash
  PAPIS_CONFIG_DIR=$PWD/config papis -l group edit ref:jordan-blog2024a
  bin/groupbib export --commit
  ```

### Conference papers imported by DOI

Papis derives the BibTeX entry type straight from Crossref's `type` field, but
that field says how the *publisher registered* the DOI, not what the paper is.
AAAI (and ICAPS, ICWSM, HCOMP, SoCS, …) register their proceedings as a
pseudo-journal, and Springer registers LNCS/CCIS proceedings papers as book
chapters, so a plain import yields `@article` and `@inbook` instead of
`@inproceedings`. Papis also copies Crossref's `container-title` into `journal`
for *every* record, leaving a stray `journal` field on conference entries.

`config/config.py` patches Papis' Crossref conversion to fix this: an entry is
treated as a conference paper if the Crossref record carries an `event` block
(IJCAI, ACM), if its DOI matches a curated venue rule, or — for Springer
chapters — if the parent book turns out to be a proceedings volume. Such an
entry gets `@inproceedings` plus a real `booktitle`/`series` and no `journal`.
The fix lives in the config, not in `info.yaml`, so it survives `groupbib
update` (which is a clean re-fetch and discards manual edits).

If a venue still imports with the wrong type, add its DOI prefix to
`_CONFERENCE_DOI_RULES` in `config/config.py` and re-run `groupbib update`.

Other commands:

```bash
bin/groupbib list             # show citation keys and DOIs
bin/groupbib check            # validate without changing anything
bin/groupbib export           # regenerate both .bib files only
bin/groupbib export --commit  # ...and commit + push it
```

## Correcting upstream metadata

`groupbib update` is a clean re-fetch, so hand-editing `library/<key>/info.yaml`
does not survive it. That is deliberate — it is what stops an entry drifting
silently from its source — but publishers do deposit metadata that is wrong or
incomplete. JSTOR registered Harsanyi (1963) with only its first page, for
instance, so Crossref reports `pages = 194` where the article runs 194–220.

Put such corrections in **`config/overrides.yaml`**. They are applied when
`references.bib` is generated, to the exported entry only, so `update` cannot
revert them and the library stays a faithful copy of the deposit:

```yaml
harsanyi-ier1963a:
  # Crossref has only the first page for 10.2307/2525487; JSTOR registered it
  # that way. Real extent: International Economic Review 4(2), 1963, 194-220.
  pages: 194--220
```

A field set to `null` is dropped from the exported entry instead. Always record
*why*, with a source — these override real publisher metadata, and the next
person needs to judge whether the reason still holds.

`groupbib check` fails on an override naming a citation key that is not in the
library, so a correction left behind by a deleted or renamed entry cannot sit
there unnoticed.

Separately, invisible characters that publishers deposit — non-breaking and
zero-width spaces, soft hyphens — are stripped from the generated BibTeX
automatically. Springer's record for `rundel-xai2024a` contains a literal
U+00A0, which is invisible in the source and aborts the LaTeX run under older
`inputenc` setups.

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

## Two generated files: which one to cite

`groupbib export` writes the same library twice. The entries are identical
except for arXiv preprints, and both carry every citation key, so `\cite{...}`
works against either.

| file | for | arXiv preprints |
| --- | --- | --- |
| `references.bib` | BibLaTeX (`\usepackage[backend=biber]{biblatex}`) | `eprint`, `eprinttype`, `eprintclass` |
| `references-plain.bib` | plain BibTeX — `plainnat`, `unsrtnat`, venue `.bst` files | folded into `journal` |

The split exists because plain BibTeX styles ignore the `eprint*` fields
entirely. A preprint would print as a bare author–title–year with nothing to say
it is a preprint at all:

```bibtex
% references.bib — BibLaTeX renders this as "arXiv:2505.16516v3 [cs.LG]"
@article{mohammadi-arxiv2025a,
  eprint = {2505.16516v3},
  eprintclass = {cs.LG},
  eprinttype = {arxiv},
  ...
}

% references-plain.bib — every style prints a journal
@article{mohammadi-arxiv2025a,
  journal = {arXiv:2505.16516v3 [cs.LG]},
  ...
}
```

A preprint that has since been published keeps its real venue: the fold only
applies when the entry has no `journal` of its own.

**Pick one file per paper** and link only that one — mixing both into a single
project would define every key twice.

## Using it in Overleaf

Make this repository (or at least the `.bib` file you use) reachable via a raw,
unauthenticated URL — e.g. a **public** GitHub repo:

```
https://raw.githubusercontent.com/<org>/dobib/main/references.bib
https://raw.githubusercontent.com/<org>/dobib/main/references-plain.bib
```

In Overleaf: **Add file → From External URL**, paste the URL of whichever
flavour your document class needs (see the table above), and name it
`references.bib`. After anyone pushes an update, Overleaf users just click
**Refresh** on the linked file — it is not a live include. The generated file
carries a `@comment{Generated <date> ...}` banner so a stale copy is obvious.
The date is only bumped when the bibliography itself changes, so it dates the
content rather than the last time someone happened to run `export`.
