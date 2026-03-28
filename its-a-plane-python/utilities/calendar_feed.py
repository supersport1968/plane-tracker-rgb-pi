"""
CalendarFeed: fetches and parses an iCal/ICS feed, extracting IATA flight
numbers from events that started within the last 16 hours or depart within
the next 2 hours.

Requires the 'icalendar' package:  pip install icalendar
If the package is absent the feed is simply ignored.
"""
import re
import threading
from datetime import datetime, date, timezone, timedelta

try:
    from icalendar import Calendar
    _ICAL_AVAILABLE = True
except ImportError:
    _ICAL_AVAILABLE = False
    print("Warning: 'icalendar' package not found — calendar feed disabled. "
          "Install with: pip install icalendar")

# Matches IATA airline codes (exactly 2 uppercase letters) + flight number
# (1-4 digits), with an optional space between, e.g.: AA1234  BA 456  DL33
# Exactly 2 letters avoids false positives from dates (MAR28), gates (E10) etc.
_FLIGHT_RE = re.compile(r'\b([A-Z]{2})\s?(\d{1,4})\b')

# How far back / forward to look for relevant calendar events
_WINDOW_PAST_HOURS   = 16
_WINDOW_FUTURE_HOURS = 2


def _to_aware(dt):
    """Convert a date or naive datetime to a UTC-aware datetime."""
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    if hasattr(dt, "tzinfo") and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class CalendarFeed:
    """
    Periodically downloads an iCal feed and extracts IATA flight numbers
    from events whose start time falls inside the activity window.

    Usage:
        feed = CalendarFeed(url="https://example.com/calendar.ics")
        feed.start()
        ...
        numbers = feed.flight_numbers  # e.g. ["AA1234", "BA456"]
    """

    def __init__(self, url: str, check_interval: int = 3600):
        self._url = url
        self._check_interval = check_interval
        self._lock = threading.Lock()
        self._flight_numbers: list = []
        self._timer = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def start(self):
        """Begin periodic fetching (runs immediately, then every check_interval)."""
        self._run()

    def stop(self):
        """Cancel the background timer."""
        if self._timer:
            self._timer.cancel()
            self._timer = None

    @property
    def flight_numbers(self) -> list:
        """Return a copy of the current list of active IATA flight numbers."""
        with self._lock:
            return list(self._flight_numbers)

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _run(self):
        self._parse()
        self._timer = threading.Timer(self._check_interval, self._run)
        self._timer.daemon = True
        self._timer.start()

    def _parse(self):
        if not _ICAL_AVAILABLE or not self._url:
            return
        try:
            from urllib.request import urlopen
            with urlopen(self._url, timeout=15) as resp:
                raw = resp.read()

            cal = Calendar.from_ical(raw)
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(hours=_WINDOW_PAST_HOURS)
            window_end   = now + timedelta(hours=_WINDOW_FUTURE_HOURS)

            found = set()
            for component in cal.walk():
                if component.name != "VEVENT":
                    continue
                dtstart = component.get("dtstart")
                if dtstart is None:
                    continue
                start = _to_aware(dtstart.dt)
                if not (window_start <= start <= window_end):
                    continue

                summary     = str(component.get("summary", ""))
                description = str(component.get("description", ""))
                text = (summary + " " + description).upper()

                for m in _FLIGHT_RE.finditer(text):
                    found.add(f"{m.group(1)}{m.group(2)}")

            with self._lock:
                self._flight_numbers = list(found)

            if found:
                print(f"Calendar: monitoring flights {found}")

        except Exception as exc:
            print(f"Calendar feed error: {exc}")
