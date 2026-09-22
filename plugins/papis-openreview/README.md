# papis-openreview

A [Papis](https://papis.readthedocs.io) downloader for
[OpenReview](https://openreview.net) (`openreview.net/forum?id=…`).

## Why

OpenReview hosts TMLR, workshop papers and the submission records for most ML
conferences. Papis ships no downloader for it, and the site cannot be scraped:
unauthenticated requests to both the pages and the API are answered with a
browser-verification challenge (`403 ChallengeRequiredError`).

Signing in bypasses that challenge, so this plugin talks to the official API
through the [`openreview-py`](https://pypi.org/project/openreview-py/) client.
Every published note carries a ready-made `_bibtex` field — the citation
OpenReview itself offers — which Papis then parses.

OpenReview runs two API generations (`api2` for venues from 2023 on, `api` for
older ones) and a forum id is valid on only one of them, so both are tried.

## Install

```sh
pip install -e plugins/papis-openreview
```

(Run from the repository root. This pulls in `openreview-py`.)

Verify it registered:

```sh
papis exec <(echo 'import papis.plugin as p; print("openreview" in p.get_plugin_names("papis.downloader"))')
```

## Credentials

An OpenReview account is required. Credentials are read from the environment —
**never put them in this repository**, which is shared and pushed to Git:

```sh
export OPENREVIEW_USERNAME='you@example.org'
export OPENREVIEW_PASSWORD='...'
```

`openreview-py` reads these two variables itself. Put them in your shell profile
(or a password manager hook) rather than in a file under version control. A free
account is enough; no special permissions are needed to read published notes.

Without them the downloader stops with a clear message instead of failing on a
challenge error.

## Use

```sh
bin/groupbib add witter-tmlr2025a https://openreview.net/forum?id=StSMBSZqxx
```

`pdf` and `attachment` URLs carry the same id, so those work too.

## Limitations

- **Unpublished submissions often have no `_bibtex` field.** Rejected or
  still-under-review papers may carry none; cite the arXiv version instead.
- **For accepted ICLR papers, prefer `proceedings.iclr.cc`**, which
  `papis-proceedings-cc` handles. The proceedings record has editors and pages;
  the OpenReview one does not.
