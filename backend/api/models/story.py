from enum import Enum


class StoryStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ComicStyle(str, Enum):
    MANGA = "manga"          # B&W, screen tones, right-to-left
    MANHWA = "manhwa"        # Full color, webtoon vertical
    WESTERN = "western"      # Full color, traditional panels
