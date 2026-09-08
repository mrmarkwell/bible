"""Tests package for Bible Engine."""
import os

# Guarantee hermetic, offline test isolation during all test runs
os.environ.setdefault("BIBLE_TEST_MODE", "1")
os.environ.setdefault("BIBLE_OFFLINE", "1")
