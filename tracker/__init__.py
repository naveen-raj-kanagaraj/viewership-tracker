"""Live viewership tracker for esports events.

Counts concurrent viewers across every YouTube stream carrying an event: the
official broadcast, permitted watch parties and community restreams. Produces
peak viewers, average viewers, hours watched and airtime, broken down by day
and by channel.

Entry points:
    tracker.events.run_fast_forever()   live counter thread, every FAST_SEC
    tracker.events.run_all()            stream discovery, every POLL_SEC
    tracker.web.run()                   the public dashboard
"""
__version__ = "1.0.0"
