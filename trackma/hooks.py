__path__ = []


def iter():
    """Return an iterator over the modules in __path__."""
    if not __path__:
        return ()

    from pkgutil import iter_modules
    return (name for _, name, _ in iter_modules(__path__))


def load(name, attr=None):
    if not __path__:
        raise ImportError(f"Cannot load hook '{name}'")

    from importlib import import_module
    return import_module(f'trackma.hooks.{name}')


def init():
    from os import path
    from trackma import utils

    hooks = utils.to_config_path('hooks')
    if not path.exists(hooks):
        return False

    if not hooks in __path__:
        __path__.append(hooks)
    return True

# vim: et:ts=4:ft=python3
