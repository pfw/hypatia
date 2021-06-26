import sys


def b(s):
    return s.encode("latin-1")


def u(s):
    return s


string_types = (str,)
text_type = str
binary_type = bytes
integer_types = (int,)


def non_native_string(x):
    if isinstance(x, bytes):
        return x
    return bytes(x, "unicode_escape")


def make_binary(x):
    if isinstance(x, bytes):
        return x
    return x.encode("ascii")


intern = sys.intern
xrange = range
_long = int


def _iteritems(x):
    return x.items()


def _items(x):
    return list(x.items())


def _maxint():
    return sys.maxsize
