from urllib.request import urlopen
from datetime import datetime, timezone, timedelta
from utilities.calendar_feed import _to_aware, _FLIGHT_RE, _WINDOW_PAST_HOURS, _WINDOW_FUTURE_HOURS
from icalendar import Calendar

URL = "YOUR_CALENDAR_URL_HERE"  # <-- replace this

with urlopen(URL, timeout=15) as resp:
    raw = resp.read()

cal = Calendar.from_ical(raw)
now = datetime.now(timezone.utc)
window_start = now - timedelta(hours=_WINDOW_PAST_HOURS)
window_end   = now + timedelta(hours=_WINDOW_FUTURE_HOURS)
print(f"Window: {window_start}  →  {window_end}\n")

for component in cal.walk():
    if component.name != "VEVENT":
        continue
    dtstart = component.get("dtstart")
    summary = str(component.get("summary", ""))
    if not dtstart:
        continue
    start = _to_aware(dtstart.dt)
    in_window = window_start <= start <= window_end
    print(f"Event : '{summary}'")
    print(f"Start : {start}  |  in_window={in_window}")
    if in_window:
        text = (summary + " " + str(component.get("description", ""))).upper()
        matches = [f"{m.group(1)}{m.group(2)}" for m in _FLIGHT_RE.finditer(text)]
        print(f"Matches: {matches}")
    print()
