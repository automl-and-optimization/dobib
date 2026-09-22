import os
import re
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


# --------------------------------------------------------------------------- #
# Fix conference papers imported from Crossref.
#
# Papis decides the BibTeX entry type with a plain 1:1 lookup of the Crossref
# `type` field (papis.crossref.CROSSREF_TO_BIBTEX_CONVERTER). But Crossref's
# `type` records how the *publisher registered* the DOI, not what the item
# bibliographically *is*, and the big AI conferences all register themselves as
# something else:
#
#   AAAI     10.1609/aaai.*   -> "journal-article"    -> @article        (wrong)
#   Springer 10.1007/978-*_N  -> "book-chapter"       -> @inbook         (wrong)
#   IJCAI    10.24963/ijcai.* -> "proceedings-article"-> @inproceedings  (ok)
#
# A second, independent bug hits even the correctly-typed ones: Papis maps
# Crossref `container-title[0]` to `journal` unconditionally, so an
# @inproceedings is exported carrying a bogus `journal` field next to its
# `booktitle`. And for Springer, `container-title` is a *two*-element list --
# [series, proceedings title] -- of which Papis keeps only element 0, i.e. the
# series ("Communications in Computer and Information Science"), throwing the
# actual book title ("Explainable Artificial Intelligence") away entirely.
#
# We patch the single conversion function that turns a raw Crossref record into
# Papis data, so we still have the full record (`event`, the complete
# `container-title` list, ISBNs) to work with. This covers `groupbib add` and
# `groupbib update` alike, and -- unlike hand-editing info.yaml -- survives
# `update`, which is a clean re-fetch that discards manual edits.
# --------------------------------------------------------------------------- #
import papis.crossref   # noqa: E402

# Venues whose Crossref `type` is wrong (or whose fields need rewriting), keyed
# by DOI prefix. This is a curated table on purpose: a keyword heuristic on the
# container title would misfire on genuine journals that are called
# "Proceedings of ..." (PNAS, Proc. Royal Society, PACMPL/PACMHCI, ...).
#
# `booktitle` is the value to force; None keeps whatever the record provides.
_CONFERENCE_DOI_RULES = [
    # AAAI Press publishes all of its proceedings as pseudo-journals, with a
    # volume per year and an "issue" per track. The slugs are listed explicitly
    # rather than matching the whole 10.1609 prefix, so a genuine journal
    # appearing under it later cannot be swept up by accident.
    (re.compile(r"^10\.1609/(aaai|aaaiss|aiide|hcomp|icaps|icwsm|socs)\.", re.I),
     None),
]

# Words that mark a Springer book as a proceedings volume. Only ever applied to
# the *parent book* of a `book-chapter`, where the journal false-positives
# above cannot occur.
_PROCEEDINGS_SUBTITLE = re.compile(
    r"\b(conference|proceedings|workshop|symposium|congress)\b", re.I)

# Chapter DOIs are "<book doi><sep><chapter number>": Springer uses "_23",
# De Gruyter "-018". A journal DOI can end the same way (10.1038/s41586-024-6),
# but this is only ever consulted for records Crossref types as `book-chapter`,
# and a wrong guess just 404s and changes nothing.
_CHAPTER_DOI = re.compile(r"^(10\.\d{4,9}/[^/]*?)[-_]\d+$")

# Publishers that number chapters often prefix the number to the title, e.g.
# De Gruyter's "17. A Value for n-Person Games".
_CHAPTER_NUMBER_PREFIX = re.compile(r"^\d{1,3}\.\s+(?=\D)")


def _crossref_parent_book(doi):
    """Fetch the Crossref record of the book containing a chapter."""
    m = _CHAPTER_DOI.match(doi)
    if not m:
        return None
    try:
        data = papis.crossref._get_crossref_works(ids=[m.group(1)])
    except Exception:
        return None
    if isinstance(data, list):
        data = data[0] if data else None
    if isinstance(data, dict) and "message" in data:
        data = data["message"]
    return data if isinstance(data, dict) else None


# Characters publishers deposit that have no place in a BibTeX field. A literal
# U+00A0 in a title (Springer deposits one in "Interpretable Machine Learning
# for<NBSP>TabPFN") is invisible in the source and, with an older `inputenc`
# setup, aborts the LaTeX run with "Unicode character not set up for use with
# LaTeX". The zero-width ones are simply invisible damage.
#
# Cleaned when the BibTeX is written, not on import: info.yaml stays a faithful
# copy of the deposit, and entries already in the library are fixed without
# having to re-fetch them.
_INVISIBLE_CHARS = {
    " ": " ",   # no-break space
    " ": " ",   # narrow no-break space
    " ": " ",   # thin space
    "​": "",    # zero-width space
    "﻿": "",    # byte-order mark
    "­": "",    # soft hyphen
}


def _clean_text(value):
    """Replace invisible or non-breaking whitespace in a string value."""
    if not isinstance(value, str):
        return value
    for bad, good in _INVISIBLE_CHARS.items():
        value = value.replace(bad, good)
    return value


def _full_title(data):
    """Reassemble a title that Crossref split across `title` and `subtitle`.

    ACM (and others) deposit "XGBoost: A Scalable Tree Boosting System" as
    title "XGBoost" plus subtitle "A Scalable Tree Boosting System". Papis maps
    only `title`, so everything after the colon is silently dropped.
    """
    title = " ".join(t for t in data.get("title", []) if t).strip()
    subtitle = " ".join(s for s in data.get("subtitle", []) if s).strip()
    if not title or not subtitle:
        return title or None
    # Some publishers already end the title with the separator, or repeat the
    # subtitle inside it; don't produce "Foo:: Bar" or say it twice.
    if subtitle.lower() in title.lower():
        return title
    if title.endswith((":", "?", "!", ".", "-", "—")):
        return f"{title} {subtitle}"
    return f"{title}: {subtitle}"


def _normalise_crossref(data, new_data):
    """Rewrite type/booktitle/journal of a converted Crossref record in place."""
    doi = str(new_data.get("doi") or data.get("DOI") or "")
    containers = [c for c in data.get("container-title", []) if c]

    # Applies to every record, not just conference papers.
    title = _full_title(data)
    if title:
        if data.get("type") == "book-chapter":
            # Strip a leading chapter number the publisher folded into the
            # title; it belongs to the book's numbering, not to the paper.
            title = _CHAPTER_NUMBER_PREFIX.sub("", title, count=1)
        new_data["title"] = title

    booktitle = None
    # Crossref only deposits an `event` block for conference papers (IJCAI,
    # ACM's GECCO/KDD/FAccT, ...), so its presence is a reliable signal and
    # needs no per-venue rule. Note ACM's 10.1145 prefix carries its journals
    # (CACM, JACM, TOMS, PACMPL, ...) too, which is why we key off the record
    # rather than the prefix.
    is_conference = bool(data.get("event"))

    if not is_conference:
        for pattern, forced_booktitle in _CONFERENCE_DOI_RULES:
            if pattern.match(doi):
                is_conference = True
                booktitle = forced_booktitle
                break

    if data.get("type") == "book-chapter":
        # A chapter record never names the book it is in: `container-title` is
        # either just the series, or [series, book title]. What it *does* have
        # is a DOI of the form "<book doi>_<chapter number>", so we look the
        # parent book up to recover both the book title and -- for Springer's
        # LNCS/CCIS volumes, which are conference proceedings dressed as edited
        # books -- whether this is a conference paper at all. Crossref marks
        # that nowhere on the chapter; only the parent's subtitle says so
        # ("16th International Conference, PPSN 2020, ..., Proceedings, Part I").
        parent = _crossref_parent_book(doi)
        if parent is not None:
            parent_titles = [t for t in parent.get("title", []) if t]
            blurb = " ".join(parent_titles + list(parent.get("subtitle", [])))
            if _PROCEEDINGS_SUBTITLE.search(blurb):
                is_conference = True
            if len(containers) > 1:
                new_data["series"] = containers[0]
                booktitle = containers[-1]
            elif parent_titles:
                # container-title held only the series; the book title is the
                # parent's own title. Some books repeat their own title there
                # instead of naming a series -- don't emit that twice.
                booktitle = parent_titles[0]
                if containers and containers[0] != booktitle:
                    new_data["series"] = containers[0]

    if not is_conference:
        # A genuine @inbook still wants booktitle/series rather than `journal`,
        # which is where Papis puts the series for every record it converts.
        if booktitle:
            new_data["booktitle"] = booktitle
            new_data.pop("journal", None)
        return new_data

    new_data["type"] = "inproceedings"
    # Prefer Crossref's `container-title`: that is the title of the proceedings
    # volume, which is what `booktitle` means. Papis instead fills booktitle
    # from `event.name`, the name of the *event*, which is a different and
    # usually worse string -- "KDD '16: The 22nd ACM SIGKDD International
    # Conference on ..." rather than "Proceedings of the 22nd ACM SIGKDD
    # International Conference on ...", and for IJCAI one carrying literal
    # "{IJCAI-22}" braces. IEEE and ACL deposit the same string in both.
    event_title = new_data.get("booktitle")
    if not booktitle:
        booktitle = containers[-1] if containers else event_title
    if booktitle:
        new_data["booktitle"] = booktitle
    # Keep the event name rather than discard it; BibLaTeX has a field for it.
    if event_title and event_title != new_data.get("booktitle"):
        new_data["eventtitle"] = event_title

    # An @inproceedings has a booktitle, never a journal. Papis fills `journal`
    # from container-title for every record, regardless of type.
    #
    # `volume` and `issue` are deliberately left alone. AAAI's are an artefact
    # of its pseudo-journal registration, but they are still how the paper is
    # located (vol. 38, issue 12 == the track), and BibLaTeX accepts both on an
    # @inproceedings. Dropping metadata the DOI actually carries is not this
    # patch's job.
    new_data.pop("journal", None)

    return new_data


_crossref_data_to_papis_data = papis.crossref.crossref_data_to_papis_data


def _patched_crossref_data_to_papis_data(data):
    return _normalise_crossref(data, _crossref_data_to_papis_data(data))


papis.crossref.crossref_data_to_papis_data = _patched_crossref_data_to_papis_data


# --------------------------------------------------------------------------- #
# Fix author splitting on the word "and" inside a name.
#
# papis.document.split_authors_name splits an author string with
#
#     re.split(fr"\s*{sep}\s+", subauthors)
#
# and BibTeX passes sep="and". The leading `\s*` matches the EMPTY string, so
# the separator also matches the "and" inside a name: "Bertrand Thirion"
# becomes "Bertr" and "Thirion". Every BibTeX-sourced import is affected
# (PMLR, the .cc proceedings sites, JMLR) -- scikit-learn's author list is a
# real example.
#
# An alphabetic separator must be a whole word, so require whitespace on both
# sides of it. Punctuation separators (",", ";") keep the original pattern:
# there is legitimately no space before a comma.
# --------------------------------------------------------------------------- #
import papis.document   # noqa: E402


def _split_authors_name(authors, separator=None):
    from papis.document import guess_authors_separator, split_author_name

    if isinstance(authors, str):
        authors = [authors]

    author_list = []
    for subauthors in authors:
        sep = separator if separator else guess_authors_separator(subauthors)
        # `sep` may itself be a regex -- guess_authors_separator returns
        # r",\s*(?:and)?" for "Name, and Name" lists -- so it must be
        # interpolated raw, exactly as upstream does. Only a bare alphabetic
        # separator gets the tightened `\s+`; a punctuation one legitimately
        # has no space before it and keeps upstream's `\s*`.
        lead = r"\s+" if str(sep).isalpha() else r"\s*"
        author_list.extend([
            split_author_name(author)
            for author in re.split(fr"{lead}{sep}\s+", subauthors)
        ])

    return author_list


# papis.bibtex imports this name inside the function that builds its key
# conversion table, so rebinding it on papis.document is enough -- the lookup
# happens when that table is first built, which is after this config is loaded.
papis.document.split_authors_name = _split_authors_name


# --------------------------------------------------------------------------- #
# Fix names built with a space-terminated LaTeX command.
#
# In LaTeX a control word ends at whitespace, and that whitespace is a
# terminator rather than a space: "\L ukasz" is "Łukasz". bibtexparser's
# latex_to_unicode converts the command but keeps the space, giving "Ł ukasz",
# which is then re-escaped on export as "{\L} ukasz" and typeset with a gap in
# the middle of the name. NeurIPS deposits exactly this for Łukasz Kaiser, and
# every BibTeX-sourced downloader we use is affected (proceedingscc, pmlr,
# jmlr, openreview).
#
# Rewrite "\L ukasz" to "{\L}ukasz" before the BibTeX is parsed, which is the
# same character with the terminator made explicit. Only the closed set of
# commands that produce a single letter is touched, so constructs like
# "{\em text}" -- where the space really is a space -- are left alone.
# --------------------------------------------------------------------------- #
_LATEX_LETTER_COMMANDS = [
    "AA", "AE", "DH", "DJ", "NG", "OE", "SS", "TH", "L", "O",
    "aa", "ae", "dh", "dj", "ng", "oe", "ss", "th", "i", "j", "l", "o",
]
# Longest first, so "\AA " is not matched as "\A" + "A ".
_SPACE_TERMINATED_RE = re.compile(
    r"\\(" + "|".join(sorted(_LATEX_LETTER_COMMANDS, key=len, reverse=True))
    + r") +(?=[A-Za-z])"
)


def _brace_space_terminated_commands(bibtex):
    return _SPACE_TERMINATED_RE.sub(r"{\\\1}", bibtex)


# Every BibTeX-based downloader reaches Papis' parser through this one method,
# so it is the single place the raw BibTeX can be normalised. Patching
# papis.bibtex directly is not possible here -- it reads the configuration
# while being imported, which deadlocks on a circular import.
import papis.downloaders   # noqa: E402

_get_bibtex_data = papis.downloaders.Downloader.get_bibtex_data


def _patched_get_bibtex_data(self):
    bibtex = _get_bibtex_data(self)
    return _brace_space_terminated_commands(bibtex) if bibtex else bibtex


papis.downloaders.Downloader.get_bibtex_data = _patched_get_bibtex_data


# --------------------------------------------------------------------------- #
# Let `howpublished` hold a LaTeX command.
#
# The BibTeX exporter escapes every field that is not in
# papis.bibtex.bibtex_verbatim_fields, so a `howpublished` of
# "\url{https://...}" is exported as "\textbackslash url{https://...}" -- the
# command is destroyed. Web sources are cited as @misc with the URL in
# `howpublished` (see "Citing a web page" in the README), which is exactly the
# case where the field holds markup rather than prose, so treat it verbatim for
# the same reason `url` and `doi` already are.
# --------------------------------------------------------------------------- #
# `papis.bibtex` reads the configuration while it is being imported, so it
# cannot be imported from here -- doing so deadlocks on a circular import. The
# BibTeX *exporter* module, by contrast, touches neither config nor
# papis.bibtex at import time, so patch its entry point and apply the change on
# the first export, by which point papis.bibtex is safely loaded.
import papis.exporters.bibtex   # noqa: E402

_to_bibtex = papis.exporters.bibtex.to_bibtex


# --------------------------------------------------------------------------- #
# Per-entry corrections, applied when the BibTeX is generated.
#
# `groupbib update` is a clean re-fetch, so a hand-edit to info.yaml does not
# survive it -- which is what keeps an entry honest about its source, but also
# leaves no way to correct upstream metadata that is wrong or incomplete (a
# first-page-only JSTOR deposit, say). config/overrides.yaml holds those
# corrections and they are applied here, to the exported entry only. The
# library itself stays a faithful copy of what the publisher deposited.
#
# `groupbib check` fails on an override naming a key that is not in the
# library, so a stale correction cannot sit here unnoticed.
# --------------------------------------------------------------------------- #
OVERRIDES_FILE = os.path.join(_cfg, "overrides.yaml") if _cfg else None


def load_overrides():
    """Read config/overrides.yaml as {citation key: {field: value}}."""
    if not (OVERRIDES_FILE and os.path.isfile(OVERRIDES_FILE)):
        return {}

    import yaml
    with open(OVERRIDES_FILE, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(
            f"{OVERRIDES_FILE}: expected a mapping of citation key -> fields.")
    for ref, fields in data.items():
        if not isinstance(fields, dict):
            raise ValueError(
                f"{OVERRIDES_FILE}: entry {ref!r} must be a mapping of "
                f"BibTeX field -> value.")
    return data


_OVERRIDES = load_overrides()


def _overrides_for(ref):
    return _OVERRIDES.get(ref) or {}


def _patched_to_bibtex(document, *args, **kwargs):
    import papis.bibtex
    if "howpublished" not in papis.bibtex.bibtex_verbatim_fields:
        papis.bibtex.bibtex_verbatim_fields = (
            papis.bibtex.bibtex_verbatim_fields | frozenset({"howpublished"})
        )

    overrides = _overrides_for(document.get("ref"))
    if not overrides:
        return _clean_text(_to_bibtex(document, *args, **kwargs))

    # Some exported fields are regenerated from a structured source rather than
    # read straight off the document: the exporter rebuilds `author` from
    # `author_list` whenever that is present, which would silently ignore an
    # `author` override. Drop the source so the override is what gets written.
    shadowed = {"author": "author_list"}
    drop = {source for field, source in shadowed.items()
            if field in overrides and source in document}

    # Apply to the in-memory document only, then put it back: the library on
    # disk must stay a faithful copy of what the publisher deposited.
    # NOTE: `{*overrides}`, not `set(overrides)` -- Papis execs this file in
    # papis.config's own namespace, where `set` is its config-setter function
    # and shadows the builtin. `set` is the only builtin it shadows.
    touched = {*overrides} | drop
    saved = {key: document[key] for key in touched if key in document}
    try:
        for key in drop:
            document.pop(key, None)
        for key, value in overrides.items():
            if value is None:
                document.pop(key, None)
            else:
                document[key] = value
        return _clean_text(_to_bibtex(document, *args, **kwargs))
    finally:
        for key in touched:
            document.pop(key, None)
        document.update(saved)


papis.exporters.bibtex.to_bibtex = _patched_to_bibtex
