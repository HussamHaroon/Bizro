import os

# Tests are offline-deterministic (bizro-testability): never let a locally
# configured DASHSCOPE_API_KEY turn the narrative builder into a live call.
os.environ.pop("DASHSCOPE_API_KEY", None)
