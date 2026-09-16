"""
Dedicated thread pool for blocking network calls (copernicusmarine, erddapy)
that have NO reliable internal timeout — a call that hangs at the OS socket
level cannot actually be killed when an asyncio.wait_for wrapper times out
in Python; the underlying thread just keeps running forever.

If those zombie threads shared Python's *default* executor, they would
eventually starve it — and asyncio's own internals (DNS resolution via
getaddrinfo) also run through that same default executor. A stuck
Copernicus call would then silently break unrelated, healthy calls like
Open-Meteo. This dedicated pool keeps that blast radius contained: worst
case, THIS pool exhausts and slow-source calls start queuing — everything
else (DNS, other adapters) keeps working.
"""
import threading
from concurrent.futures import ThreadPoolExecutor

network_executor = ThreadPoolExecutor(max_workers=16, thread_name_prefix="jaljeev-net")

# Serialises every netCDF4/HDF5 read that happens off the event loop.
#
# WHY (27 Aug 2026): the server started dying mid-request with NO Python
# traceback — the process simply disappeared, nothing in stdout or stderr.
# That is a native crash, not an exception. Cause: the HDF5 C library
# underneath netCDF4 is not thread-safe, and this pool runs several readers
# concurrently:
#   * pyTMD's EOT20 tide reader (confirmed netCDF4-backed),
#   * copernicusmarine / xarray dataset opens,
#   * erddapy's to_xarray for NOAA OISST.
# Before the tide adapter moved to background computation those rarely
# overlapped, because the tide call was being cancelled at 20s and never got
# far. Making tide actually complete is what started overlapping them, and
# what surfaced this.
#
# Holding one process-wide lock across all of them costs concurrency between
# these three specific sources only — every other source (Open-Meteo, the
# PostGIS lookups, Redis) is untouched and still fully parallel. A crashed
# server is not a faster server.
netcdf_lock = threading.Lock()
