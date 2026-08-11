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
