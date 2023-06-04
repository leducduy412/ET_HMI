import distutils.spawn
import os
import sys

from setuptools import find_packages
from setuptools import setup


def get_install_requires():
    install_requires = [
        "imgviz>=0.11",
        "matplotlib",
        "natsort>=7.1.0",
        "numpy",
        "Pillow>=2.8",
        "PyYAML",
        "qtpy!=1.11.2",
        "termcolor",
    ]

    # Find python binding for qt with priority:
    # PyQt5 -> PySide2
    # and PyQt5 is automatically installed on Python3.
    QT_BINDING = None

    try:
        import PyQt5  # NOQA
        QT_BINDING = "pyqt5"
    except ImportError:
        pass

    if QT_BINDING is None:
        try:
            import PySide2  # NOQA
            QT_BINDING = "pyside2"
        except ImportError:
            pass

    if QT_BINDING is None:
        # PyQt5 can be installed via pip for Python3
        # 5.15.3, 5.15.4 won't work with PyInstaller
        install_requires.append("PyQt5!=5.15.3,!=5.15.4")
        QT_BINDING = "pyqt5"

    del QT_BINDING

    if os.name == "nt":  # Windows
        install_requires.append("colorama")

    return install_requires


def main():
    if sys.argv[1] == "release":
        try:
            import github2pypi  # NOQA
        except ImportError:
            print(
                "Please install github2pypi\n\n\tpip install github2pypi\n",
                file=sys.stderr,
            )
            sys.exit(1)

        if not distutils.spawn.find_executable("twine"):
            print(
                "Please install twine:\n\n\tpip install twine\n",
                file=sys.stderr,
            )
            sys.exit(1)

    setup(
        name="et_label_app",
        packages=find_packages(),
        description="Eye tracking Annotation with Python",
        author="Ta Dang Khoa",
        install_requires=get_install_requires(),
        package_data={"et_label_app": ["icons/*", "config/*.yaml"]},
        entry_points={
            "console_scripts": [
                "et_label_app=et_label_app.cli.main:main"
            ],
        },
    )


if __name__ == "__main__":
    main()
