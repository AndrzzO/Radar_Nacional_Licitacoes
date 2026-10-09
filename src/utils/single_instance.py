"""Trava de processo no Windows, liberada pelo sistema até após falhas."""
import ctypes
import os
from ctypes import wintypes


class SingleInstance:
    def __init__(self, name=r"Local\RadarNacionalLicitacoes.Application"):
        self.handle = None
        if os.name != "nt":
            raise RuntimeError("A trava de instância única requer Windows.")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel.CreateMutexW.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        ctypes.set_last_error(0)
        handle = self.kernel.CreateMutexW(None, False, name)
        error = ctypes.get_last_error()
        if not handle:
            raise ctypes.WinError(error)
        self.acquired = error != 183  # ERROR_ALREADY_EXISTS
        if self.acquired:
            self.handle = handle
        else:
            self.kernel.CloseHandle(handle)

    def close(self):
        if self.handle is not None:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
