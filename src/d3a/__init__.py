import os

import d3a


# *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
VERSION = "1.0.0a0"

TIME_FORMAT = "%H:%M"
PENDULUM_TIME_FORMAT = "HH:mm"
TIME_ZONE = "UTC"

DEFAULT_PRECISION = 8


def limit_float_precision(number):
    return round(number, DEFAULT_PRECISION)


def get_project_root():
    return os.path.dirname(d3a.__file__)
