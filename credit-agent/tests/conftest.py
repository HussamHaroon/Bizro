import os

# Tests are offline-deterministic (bizro-testability). BIZRO_OFFLINE=1 is
# process-wide on purpose: other suites' .env loaders may re-inject a locally
# configured DASHSCOPE_API_KEY into os.environ mid-session, and the narrative
# builder must never turn that into a live call from a test.
os.environ["BIZRO_OFFLINE"] = "1"
os.environ.pop("DASHSCOPE_API_KEY", None)
