import os
import pytest

os.environ["DB_PATH"] = ":memory:"
os.environ.setdefault("YOUTUBE_API_KEY", "test-key")
os.environ.setdefault("AWS_REGION", "us-east-1")
