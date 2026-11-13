"""Cover tiles for categories that have no box art (News, Devotional, Music, Other ...): a coloured 3:4 tile with a
line icon, served as /caticon/<section>.svg. Used by every page and share card instead of two-letter initials."""

# (gradient top, gradient bottom, icon stroke paths on a 24x24 grid)
ICONS = {
    "news": ("#7fb2ff", "#3a63d6", "M4 5h13v14H6a2 2 0 0 1-2-2zM17 9h3v8a2 2 0 0 1-2 2M7 9h7M7 12h7M7 15h4"),
    "devotional": ("#ffc35a", "#e0731f", "M12 3c2.5 3 4 5.2 4 7.5a4 4 0 0 1-8 0C8 8.2 9.5 6 12 3zM12 9.5c1 1.2 1.6 2 1.6 3a1.6 1.6 0 0 1-3.2 0c0-1 .6-1.8 1.6-3zM5 17h14l-2 4H7z"),
    "music": ("#ff8ab4", "#d6336c", "M9 18V6l11-2v12M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0zM20 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0zM9 10l11-2"),
    "podcasts": ("#c39bff", "#7a4fe0", "M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3zM5 11a7 7 0 0 0 14 0M12 18v3M8 21h8"),
    "just-chatting": ("#9ae6ff", "#2a9fd4", "M4 5h16v11H9l-5 4zM8 9h8M8 12h5"),
    "irl": ("#8ff0b4", "#1fae6b", "M4 8h3l2-3h6l2 3h3v11H4zM12 16a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z"),
    "sports": ("#d4f26a", "#5fb31f", "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM6 6c3 3 3 9 0 12M18 6c-3 3-3 9 0 12"),
    "esports": ("#ffe066", "#e0a800", "M7 4h10v5a5 5 0 0 1-10 0zM7 6H4v1a3 3 0 0 0 3 3M17 6h3v1a3 3 0 0 1-3 3M12 14v4M8 21h8M9 18h6"),
    "gaming": ("#b6f23a", "#4f9a1a", "M7 8h10a4 4 0 0 1 4 4l.5 4a2.5 2.5 0 0 1-4.4 1.8L15 15H9l-2.1 2.8A2.5 2.5 0 0 1 2.5 16L3 12a4 4 0 0 1 4-4zM7 11v3M5.5 12.5h3M15.5 11.5h.01M17.5 13.5h.01"),
    "other": ("#b9b8cc", "#5d5c75", "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z"),
}


def svg(section: str) -> str:
    top, bot, d = ICONS.get(section) or ICONS["other"]
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="120" height="160" viewBox="0 0 120 160">'
            f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{top}"/>'
            f'<stop offset="1" stop-color="{bot}"/></linearGradient></defs><rect width="120" height="160" fill="url(#g)"/>'
            '<g transform="translate(30 50) scale(2.5)" fill="none" stroke="#0b0b12" stroke-width="1.7" '
            f'stroke-linecap="round" stroke-linejoin="round"><path d="{d}"/></g></svg>')


def url(section: str) -> str:
    return f"/caticon/{section if section in ICONS else 'other'}.svg"
