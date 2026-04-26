import ctypes
import os
from ctypes import wintypes

ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    def __init__(self, name):
        self.name = f"Local\\{name}"
        self.handle = None

    def acquire(self):
        if os.name != "nt":
            return True

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.CreateMutexW(None, False, self.name)
        if not handle:
            raise OSError(ctypes.get_last_error(), "Could not create the Tiamat mutex.")

        already_exists = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
        if already_exists:
            kernel32.CloseHandle(handle)
            return False

        self.handle = handle
        return True

    def release(self):
        if os.name != "nt" or not self.handle:
            return

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.CloseHandle(self.handle)
        self.handle = None
