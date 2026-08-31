"""Keep the test suite deterministic and independent of developer credentials."""

import os


# Settings reads `.env` during module import.  An explicit environment value has
# higher priority, so tests never make paid/remote HCX calls by accident.
os.environ["HCX_API_KEY"] = ""
