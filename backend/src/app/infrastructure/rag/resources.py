import ctypes
import os

from app.application.ia.exceptions import IANoDisponible


def available_gib():
    if os.name!='nt':raise IANoDisponible()
    class Memory(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(name,ctypes.c_ulonglong) for name in
            ['total','available','pt','pa','vt','va','extended']]
    value=Memory();value.length=ctypes.sizeof(value)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):raise IANoDisponible()
    return value.available/2**30


def require_memory(minimum):
    if available_gib()<minimum:raise IANoDisponible()
