# flake8: noqa

from qtpy import QT_VERSION


__appname__ = "et_label_app"

# Semantic Versioning 2.0.0: https://semver.org/
# 1. MAJOR version when you make incompatible API changes;
# 2. MINOR version when you add functionality in a backwards-compatible manner;
# 3. PATCH version when you make backwards-compatible bug fixes.

__version__ = "0.1.0"

QT5 = QT_VERSION[0] == "5"
del QT_VERSION
