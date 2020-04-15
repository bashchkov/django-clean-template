try:
    from .prod import *
except ImportError:
    from .dev import *
