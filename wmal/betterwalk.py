"""BetterWalk, a better and faster os.walk() for Python.

BetterWalk is a somewhat better and significantly faster version of Python's
os.walk(), as well as a generator version of os.listdir(). See README.md or
https://github.com/benhoyt/betterwalk for rationale and documentation.

BetterWalk is released under the new BSD 3-clause license. See LICENSE.txt for
the full license text.

"""

import ctypes
import fnmatch
import os
import stat
import sys

__version__ = '0.6'
__all__ = ['iterdir', 'iterdir_stat', 'walk']


# Windows implementation
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

    # The conversion functions below are taken more or less straight from
    # CPython's Modules/posixmodule.c

    def attributes_to_mode(attributes):
        """Convert Win32 dwFileAttributes to st_mode."""
        mode = 0
        if attributes & FILE_ATTRIBUTE_DIRECTORY:
            mode |= stat.S_IFDIR | 0o111
        else:
            mode |= stat.S_IFREG
        if attributes & FILE_ATTRIBUTE_READONLY:
            mode |= 0o444
        else:
            mode |= 0o666
        if attributes & FILE_ATTRIBUTE_REPARSE_POINT:
            mode |= stat.S_IFLNK
        return mode

    def filetime_to_time(filetime):
        """Convert Win32 FILETIME to time since Unix epoch in seconds."""
        total = filetime.dwHighDateTime << 32 | filetime.dwLowDateTime
        return total / 10000000.0 - SECONDS_BETWEEN_EPOCHS

    def find_data_to_stat(data):
        """Convert Win32 FIND_DATA struct to stat_result."""
        st_mode = attributes_to_mode(data.dwFileAttributes)
        st_size = data.nFileSizeHigh << 32 | data.nFileSizeLow
        st_atime = filetime_to_time(data.ftLastAccessTime)
        st_mtime = filetime_to_time(data.ftLastWriteTime)
        st_ctime = filetime_to_time(data.ftCreationTime)
        # These are set to zero rather than None, per CPython's posixmodule.c
        st_ino = 0
        st_dev = 0
        st_nlink = 0
        st_uid = 0
        st_gid = 0
        return os.stat_result((st_mode, st_ino, st_dev, st_nlink, st_uid,
                               st_gid, st_size, st_atime, st_mtime, st_ctime))

    def win_error(error, filename):
        exc = WindowsError(error, ctypes.FormatError(error))
        exc.filename = filename
        return exc

    def iterdir_stat(path='.', pattern='*', fields=None):
        """See iterdir_stat.__doc__ below for docstring."""
        # We can ignore "fields" in Windows, as FindFirst/Next gives full stat

        if '[' in pattern or pattern.endswith('?'):
            # Windows FindFirst/Next doesn't support bracket matching, and it
            # doesn't handle ? at the end patterns as per fnmatch; use fnmatch
            wildcard = '*'
        else:
            # Otherwise use built-in FindFirst/Next wildcard matching
            wildcard = pattern
            pattern = None

        # Call FindFirstFile and handle errors
        data = wintypes.WIN32_FIND_DATAW()
        data_p = ctypes.byref(data)
        filename = os.path.join(path, wildcard)
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
                    if pattern is None or fnmatch.fnmatch(name, pattern):
                        st = find_data_to_stat(data)
                        yield (name, st)

                success = FindNextFile(handle, data_p)
                if not success:
                    error = ctypes.GetLastError()
                    if error == ERROR_NO_MORE_FILES:
                        break
                    raise win_error(error, path)
        finally:
            if not FindClose(handle):
                raise win_error(ctypes.GetLastError(), path)


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

    def type_to_stat(d_type):
        """Convert dirent.d_type value to stat_result."""
        st_mode = d_type << 12
        return os.stat_result((st_mode,) + (None,) * 9)

    def posix_error(filename):
        errno = ctypes.get_errno()
        exc = OSError(errno, os.strerror(errno))
        exc.filename = filename
        return exc

    def iterdir_stat(path='.', pattern='*', fields=None):
        """See iterdir_stat.__doc__ below for docstring."""
        # If we need more than just st_mode_type (dirent.d_type), we need to
        # call stat() on each file
        need_stat = fields is not None and set(fields) != set(['st_mode_type'])

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
                    if pattern == '*' or fnmatch.fnmatch(name, pattern):
                        if need_stat or entry.d_type == DT_UNKNOWN:
                            st = os.stat(os.path.join(path, name))
                        else:
                            st = type_to_stat(entry.d_type)
                        yield (name, st)
        finally:
            if closedir(dir_p):
                raise posix_error(path)


# Some other system -- have to fall back to using os.listdir() and os.stat()
else:
    def iterdir_stat(path='.', pattern='*', fields=None):
        """See iterdir_stat.__doc__ below for docstring."""
        names = os.listdir(path)
        if pattern != '*':
            names = fnmatch.filter(names, pattern)
        for name in names:
            if fields is not None:
                st = os.stat(os.path.join(path, name))
            else:
                st = os.stat_result((None,) * 10)
            yield (name, st)


iterdir_stat.__doc__ = """
Yield tuples of (filename, stat_result) for each filename that matches
"pattern" in the directory given by "path". Like os.listdir(), '.' and '..'
are skipped, and the values are yielded in system-dependent order.

Pattern matching is done as per fnmatch.fnmatch(), but is more efficient if
the system's directory iteration supports pattern matching (like Windows).

The "fields" parameter specifies which fields to provide in each stat_result.
If None, only the fields the operating system can get "for free" are present
in stat_result. Otherwise "fields" must be an iterable of 'st_*' attribute
names that the caller wants in each stat_result. The only special attribute
name is 'st_mode_type', which means the type bits in the st_mode field.

In practice, all fields are provided for free on Windows; whereas only the
st_mode_type information is provided for free on Linux, Mac OS X, and BSD.
"""


def iterdir(path='.', pattern='*'):
    """Like iterdir_stat(), but only yield the filenames."""
    for name, st in iterdir_stat(path, pattern=pattern):
        yield name


def walk(top, topdown=True, onerror=None, followlinks=False):
    """Just like os.walk(), but faster, as it uses iterdir_stat internally."""
    # Determine which are files and which are directories
    dirs = []
    dir_stats = []
    nondirs = []
    try:
        for name, st in iterdir_stat(top, fields=['st_mode_type']):
            if stat.S_ISDIR(st.st_mode):
                dirs.append(name)
                dir_stats.append(st)
            else:
                nondirs.append(name)
    except OSError as err:
        if onerror is not None:
            onerror(err)
        return

    # Yield before recursion if going top down
    if topdown:
        yield top, dirs, nondirs

    # Recurse into sub-directories, following symbolic links if "followlinks"
    for name, st in zip(dirs, dir_stats):
        new_path = os.path.join(top, name)
        if followlinks or not stat.S_ISLNK(st.st_mode):
            for x in walk(new_path, topdown, onerror, followlinks):
                yield x

    # Yield before recursion if going bottom up
    if not topdown:
        yield top, dirs, nondirs
