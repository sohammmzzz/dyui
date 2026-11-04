"""Media components: image, gallery, video, audio, file, link_preview."""
from __future__ import annotations

from typing import Optional, Union

from .base import Component, Model
from .types import OptUrl, Url

__all__ = ["Image", "GalleryImage", "Gallery", "Video", "Audio", "File", "LinkPreview"]


class Image(Component):
    """A single image.

    Example:
        ``ui.Image("https://example.com/lisbon.jpg", alt="Lisbon at dusk")``
    """

    group = "media"
    positional = ("src",)
    examples = [{"src": "https://example.com/photo.jpg", "alt": "Tram 28 in Alfama"}]

    src: Url
    alt: Optional[str] = None
    caption: Optional[str] = None


class GalleryImage(Model):
    """One image inside a ``gallery``."""

    __positional__ = ("src", "alt", "caption")
    __str_field__ = "src"

    src: Url
    alt: Optional[str] = None
    caption: Optional[str] = None


class Gallery(Component):
    """A grid of images.

    Example:
        ``ui.Gallery("https://example.com/a.jpg", "https://example.com/b.jpg")``
    """

    group = "media"
    varargs = "images"

    images: list[GalleryImage]


class Video(Component):
    """A video; YouTube/Vimeo links are embedded.

    Example:
        ``ui.Video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")``
    """

    group = "media"
    positional = ("src",)

    src: Url
    poster: OptUrl = None
    caption: Optional[str] = None


class Audio(Component):
    """An audio player.

    Example:
        ``ui.Audio("https://example.com/episode.mp3", title="Episode 12")``
    """

    group = "media"
    positional = ("src",)

    src: Url
    title: Optional[str] = None


class File(Component):
    """A downloadable file.

    Example:
        ``ui.File("report.pdf", "/api/files/f_123", size=48213, type="application/pdf")``
    """

    group = "media"
    positional = ("name", "url")

    name: str
    url: Url
    size: Optional[Union[int, str]] = None
    type: Optional[str] = None


class LinkPreview(Component):
    """A rich preview card for one link.

    Example:
        ``ui.LinkPreview("https://example.com", title="Example", site="example.com")``
    """

    group = "media"
    positional = ("url",)

    url: Url
    title: Optional[str] = None
    description: Optional[str] = None
    image: OptUrl = None
    site: Optional[str] = None
