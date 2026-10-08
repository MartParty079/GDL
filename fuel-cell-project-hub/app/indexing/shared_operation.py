"""Wrap existing catalog mutations in a closed-snapshot publication."""
from functools import wraps


def shared_write(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        catalog = getattr(self, 'catalog', self)
        shared = getattr(catalog, 'shared', None)
        if not shared or getattr(catalog._editing, 'path', None):
            return method(self, *args, **kwargs)
        if not shared.authority:
            if method.__name__ in ('viewed',):
                return None
            target = type(self).__name__ + '.' + method.__name__
            from app.services.shared_index import PENDING_METHODS
            if target in PENDING_METHODS:
                shared.submit('mutation', {'target': target, 'args': args, 'kwargs': kwargs})
                raise ValueError('Change queued for the project indexing authority. It will appear after the next published revision.')
            raise ValueError('This operation requires the configured project indexing authority.')
        with shared.working() as (path, base):
            catalog._editing.path = path
            try:
                result = method(self, *args, **kwargs)
                shared.publish(path, base)
                catalog.path = shared.path
                return result
            finally:
                catalog._editing.path = None
    return wrapped
