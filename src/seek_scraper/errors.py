"""Errors raised by the scraper."""

from __future__ import annotations


class SeekError(Exception):
    """Base class for scraper errors."""


class JobNotFoundError(SeekError):
    """The site has no job with that id (it answers 404)."""


class ParseError(SeekError):
    """A response was not the SEEK data the scraper expected."""


class InputError(SeekError, ValueError):
    """A market, job reference, filter or sort order could not be used."""
