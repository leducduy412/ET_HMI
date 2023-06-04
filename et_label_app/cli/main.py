import click
import sys

from qtpy import QtWidgets

from et_label_app import __appname__
from et_label_app.app import MainWindow
from et_label_app.config import get_config
from et_label_app.utils import newIcon


@click.group()
@click.version_option()
def root():
    """
    Command-line interface to manage MLServer models.
    """
    pass


@root.command("run")
def run():
    config = get_config()

    app = QtWidgets.QApplication([])
    app.setApplicationName(__appname__)
    app.setWindowIcon(newIcon("icon"))
    win = MainWindow(config=config)

    win.show()
    win.raise_()
    sys.exit(app.exec_())


def main():
    root()


if __name__ == "__main__":
    main()
