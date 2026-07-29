# ArbPlus Extension Example (Python)
# @arbplus-meta name="ext_example"
# @arbplus-meta version="1.0"
# @arbplus-meta author="ArbPlus"
# @arbplus-meta description="Python extension demonstrating the ArbPlus extension ABI"
# @arbplus-meta dependencies="urllib"
# @arbplus-meta languages="python"
# This file demonstrates the Python extension ABI for ArbPlus.
# It registers a function that fetches data via HTTP.

import urllib.request
import json

def fetch_url(args, kwargs):
    """Fetch a URL and return the response as a string."""
    url = args[0].py() if args else ""
    try:
        req = urllib.request.urlopen(url, timeout=10)
        data = req.read().decode('utf-8')
        return data
    except Exception as e:
        return f"Error: {e}"


def say_hello(args, kwargs):
    """A simple greeting function."""
    name = args[0].py() if args else "World"
    return f"Hello from Python extension, {name}!"


# Hook mechanism: extend snap.time with higher-resolution timing
def highres_time_hook(args, kwargs, original_func):
    """Hook that adds microsecond precision to snap.time."""
    import datetime
    now = datetime.datetime.now()
    if not args and not kwargs:
        return now.strftime("%Y-%m-%d %H:%M:%S.%f")
    return None  # None means use original


def register(engine):
    """Registration entry point — called by loadExt()."""
    engine.register_extension("ext.fetchUrl", fetch_url)
    engine.register_extension("ext.sayHello", say_hello)
    engine.register_hook("snap.time", highres_time_hook)
