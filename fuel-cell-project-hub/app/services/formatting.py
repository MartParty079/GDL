"""Shared UI units: decimal bytes, at most three significant figures."""


def format_file_size(value):
    size = max(0, float(value or 0))
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1000 or unit == 'TB':
            rounded = float(f'{size:.3g}')
            if rounded >= 1000 and unit != 'TB':
                size = rounded / 1000
                continue
            return f'{rounded:g} {unit}'
        size /= 1000


def format_duration(seconds):
    minutes = max(0, int(seconds) // 60)
    return f'{minutes // 60} h {minutes % 60:02d} min' if minutes >= 60 else f'{minutes} min'
