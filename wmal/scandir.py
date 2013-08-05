"""scandir, a better directory iterator that exposes all file info OS provides

scandir is a generator version of os.listdir() that returns an iterator over
files in a directory, and also exposes the extra information most OSes provide
while iterating files in a directory.

See README.md or https://github.com/benhoyt/scandir for rationale and docs.

scandir is released under the new BSD 3-clause license. See LICENSE.txt for
the full license text.
"""

from __future__ import division

import collections
import ctypes
import fnmatch
import os
import stat
import sys
import warnings

__version__ = '0.1'
__all__ = ['scandir', 'walk']

try:
    unicode
except NameError:
    unicode = str

_join = os.path.join
_lstat = os.lstat
_stat_result = os.stat_result

DT_UNKNOWN = 0
DT_FIFO = 1
DT_CHR = 2
DT_DIR = 4
DT_BLK = 6
DT_REG = 8
DT_LNK = 10
DT_SOCK = 12

S_IFDIR = stat.S_IFDIR
S_IFREG = stat.S_IFREG
S_IFLNK = stat.S_IFLNK

Dirent = collections.namedtuple('Dirent', ['d_ino', 'd_type'])

class DirEntry(object):
    __slots__ = ('_path', 'name', 'dirent', '_lstat')

    def __init__(self, path, name, dirent, lstat):
        # TODO ben: make path absolute? Do this in scandir?
        self._path = path
        self.name = name
        self.dirent = dirent
        self._lstat = lstat

    def lstat(self):
        if self._lstat is None:
            self._lstat = _lstat(_join(self._path, self.name))
        return self._lstat

    # Ridiculous duplication between these is* functions -- helps a little bit
    # with os.walk() performance compared to calling another function. Won't
    # be an issue in C, but Python function calls are relatively expensive.
    def isdir(self):
        if self._lstat is None:
            d_type = getattr(self.dirent, 'd_type', DT_UNKNOWN)
            if d_type != DT_UNKNOWN:
                return d_type == DT_DIR
            else:
                try:
                    self.lstat()
                except OSError:
                    return False
        return self._lstat.st_mode & 0o170000 == S_IFDIR

    def isfile(self):
        if self._lstat is None:
            d_type = getattr(self.dirent, 'd_type', DT_UNKNOWN)
            if d_type != DT_UNKNOWN:
                return d_type == DT_REG
            else:
                try:
                    self.lstat()
                except OSError:
                    return False
        return self._lstat.st_mode & 0o170000 == S_IFREG

    def islink(self):
        if self._lstat is None:
            d_type = getattr(self.dirent, 'd_type', DT_UNKNOWN)
            if d_type != DT_UNKNOWN:
                return d_type == DT_LNK
            else:
                try:
                    self.lstat()
                except OSError:
                    return False
        return self._lstat.st_mode & 0o170000 == S_IFLNK

    def __str__(self):
        return '<{0}: {1!r}{2}{3}>'.format(
                self.__class__.__name__,
                self.name,
                ' dirent' if self.dirent else '',
                ' stat' if self._lstat else '')

    __repr__ = __str__


if sys.platform == 'win32':
    from ctypes import wintypes

    # Various constants from windows.h
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    ERROR_FILE_NOT_FOUND = 2
    ERROR_NO_MORE_FILES = 18
    FILE_ATTRIBUTE_READONLY = 1
    FILE_ATTRIBUTE_DIRECTORY = 16
    FILE_ATTRIBUTE_REPARSE_POINT = 1024

    # Numer of seconds between 1601-01-01 and 1970-01-01
    SECONDS_BETWEEN_EPOCHS = 11644473600

    kernel32 = ctypes.windll.kernel32

    # ctypes wrappers for (wide string versions of) FindFirstFile,
    # FindNextFile, and FindClose
    FindFirstFile = kernel32.FindFirstFileW
    FindFirstFile.argtypes = [
        wintypes.LPCWSTR,
        ctypes.POINTER(wintypes.WIN32_FIND_DATAW),
    ]
    FindFirstFile.restype = wintypes.HANDLE

    FindNextFile = kernel32.FindNextFileW
    FindNextFile.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.WIN32_FIND_DATAW),
    ]
    FindNextFile.restype = wintypes.BOOL

    FindClose = kernel32.FindClose
    FindClose.argtypes = [wintypes.HANDLE]
    FindClose.restype = wintypes.BOOL

    def filetime_to_time(filetime):
        """Convert Win32 FILETIME to time since Unix epoch in seconds."""
        # TODO ben: doesn't seem to match os.stat() exactly
        total = filetime.dwHighDateTime << 32 | filetime.dwLowDateTime
        return total / 10000000 - SECONDS_BETWEEN_EPOCHS

    def find_data_to_stat(data):
        """Convert Win32 FIND_DATA struct to stat_result."""
        # First convert Win32 dwFileAttributes to st_mode
        attributes = data.dwFileAttributes
        st_mode = 0
        if attributes & FILE_ATTRIBUTE_DIRECTORY:
            st_mode |= S_IFDIR | 0o111
        else:
            st_mode |= S_IFREG
        if attributes & FILE_ATTRIBUTE_READONLY:
            st_mode |= 0o444
        else:
            st_mode |= 0o666
        if attributes & FILE_ATTRIBUTE_REPARSE_POINT:
            st_mode |= S_IFLNK

        st_size = data.nFileSizeHigh << 32 | data.nFileSizeLow
        st_atime = filetime_to_time(data.ftLastAccessTime)
        st_mtime = filetime_to_time(data.ftLastWriteTime)
        st_ctime = filetime_to_time(data.ftCreationTime)
        # These are set to zero per CPython's posixmodule.c
        st_ino = 0
        st_dev = 0
        st_nlink = 0
        st_uid = 0
        st_gid = 0
        return _stat_result((st_mode, st_ino, st_dev, st_nlink, st_uid,
                             st_gid, st_size, st_atime, st_mtime, st_ctime))

    def win_error(error, filename):
        exc = WindowsError(error, ctypes.FormatError(error))
        exc.filename = filename
        return exc

    def scandir(path='.', windows_wildcard='*.*'):
        # Call FindFirstFile and handle errors
        data = wintypes.WIN32_FIND_DATAW()
        data_p = ctypes.byref(data)
        filename = _join(path, windows_wildcard)
        handle = FindFirstFile(filename, data_p)
        if handle == INVALID_HANDLE_VALUE:
            error = ctypes.GetLastError()
            if error == ERROR_FILE_NOT_FOUND:
                # No files, don't yield anything
                return
            raise win_error(error, path)

        # Call FindNextFile in a loop, stopping when no more files
        try:
            while True:
                # Skip '.' and '..' (current and parent directory), but
                # otherwise yield (filename, stat_result) tuple
                name = data.cFileName
                if name not in ('.', '..'):
                    yield DirEntry(path, name, None, find_data_to_stat(data))

                success = FindNextFile(handle, data_p)
                if not success:
                    error = ctypes.GetLastError()
                    if error == ERROR_NO_MORE_FILES:
                        break
                    raise win_error(error, path)
        finally:
            if not FindClose(handle):
                raise win_error(ctypes.GetLastError(), path)

    try:
        import _scandir
        def scandir(path='.'):
            for name, st in _scandir.scandir_helper(unicode(path)):
                yield DirEntry(path, name, None, st)
    except ImportError:
        warnings.warn('Using slow Python version of scandir()')


# Linux, OS X, and BSD implementation
elif sys.platform.startswith(('linux', 'darwin')) or 'bsd' in sys.platform:
    import ctypes.util

    DIR_p = ctypes.c_void_p

    # Rather annoying how the dirent struct is slightly different on each
    # platform. The only fields we care about are d_name and d_type.
    class dirent(ctypes.Structure):
        if sys.platform.startswith('linux'):
            _fields_ = (
                ('d_ino', ctypes.c_ulong),
                ('d_off', ctypes.c_long),
                ('d_reclen', ctypes.c_ushort),
                ('d_type', ctypes.c_byte),
                ('d_name', ctypes.c_char * 256),
            )
        else:
            _fields_ = (
                ('d_ino', ctypes.c_uint32),  # must be uint32, not ulong
                ('d_reclen', ctypes.c_ushort),
                ('d_type', ctypes.c_byte),
                ('d_namlen', ctypes.c_byte),
                ('d_name', ctypes.c_char * 256),
            )

    DT_UNKNOWN = 0

    dirent_p = ctypes.POINTER(dirent)
    dirent_pp = ctypes.POINTER(dirent_p)

    libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
    opendir = libc.opendir
    opendir.argtypes = [ctypes.c_char_p]
    opendir.restype = DIR_p

    readdir_r = libc.readdir_r
    readdir_r.argtypes = [DIR_p, dirent_p, dirent_pp]
    readdir_r.restype = ctypes.c_int

    closedir = libc.closedir
    closedir.argtypes = [DIR_p]
    closedir.restype = ctypes.c_int

    file_system_encoding = sys.getfilesystemencoding()

    def posix_error(filename):
        errno = ctypes.get_errno()
        exc = OSError(errno, os.strerror(errno))
        exc.filename = filename
        return exc

    def scandir(path='.'):
        dir_p = opendir(path.encode(file_system_encoding))
        if not dir_p:
            raise posix_error(path)
        try:
            entry = dirent()
            result = dirent_p()
            while True:
                if readdir_r(dir_p, entry, result):
                    raise posix_error(path)
                if not result:
                    break
                name = entry.d_name.decode(file_system_encoding)
                if name not in ('.', '..'):
                    scandir_dirent = Dirent(entry.d_ino, entry.d_type)
                    yield DirEntry(path, name, scandir_dirent, None)
        finally:
            if closedir(dir_p):
                raise posix_error(path)

    try:
        import _scandir
        def scandir(path='.'):
            for name, d_ino, d_type in _scandir.scandir_helper(path):
                scandir_dirent = Dirent(d_ino, d_type)
                yield DirEntry(path, name, scandir_dirent, None)
    except ImportError:
        warnings.warn('Using slow Python version of scandir(), please build _scandir.c using setup.py')


# Some other system -- no d_type or stat information
else:
    def scandir(path='.'):
        for name in os.listdir(path):
            yield DirEntry(path, name, None, None)


def walk(top, topdown=True, onerror=None, followlinks=False):
    """Just like os.walk(), but faster, as it uses scandir() internally."""
    # Determine which are files and which are directories
    dirs = []
    nondirs = []
    try:
        for entry in scandir(top):
            if entry.isdir():
                dirs.append(entry)
            else:
                nondirs.append(entry)
    except OSError as error:
        if onerror is not None:
            onerror(error)
        return

    # Yield before recursion if going top down
    if topdown:
        # Need to do some fancy footwork here as caller is allowed to modify
        # dir_names, and we really want them to modify dirs (list of DirEntry
        # objects) instead. Keep a mapping of entries keyed by name.
        dir_names = []
        entries_by_name = {}
        for entry in dirs:
            dir_names.append(entry.name)
            entries_by_name[entry.name] = entry

        yield top, dir_names, [e.name for e in nondirs]

        dirs = []
        for dir_name in dir_names:
            entry = entries_by_name.get(dir_name)
            if entry is None:
                entry = DirEntry(top, dir_name, None, None)
            dirs.append(entry)

    # Recurse into sub-directories, following symbolic links if "followlinks"
    for entry in dirs:
        if followlinks or not entry.islink():
            new_path = _join(top, entry.name)
            for x in walk(new_path, topdown, onerror, followlinks):
                yield x

    # Yield before recursion if going bottom up
    if not topdown:
        yield top, [e.name for e in dirs], [e.name for e in nondirs]
