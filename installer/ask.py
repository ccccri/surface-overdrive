#!/usr/bin/env python3
"""The installer's two password windows (PySide6, when the system has it: Fedora Kinoite shipped it until November 2026), each one window:

  ask.py admin [--wrong]   the administrator password, "to install Surface Overdrive" (pkexec's own window could only
                           say "to run /tmp/.../install-surface-overdrive as the super user")
  ask.py mok               the one-time password of the signing key: two fields in one window, typed twice

The password goes to stdout, one line; status 1 when the window was cancelled, 3 when PySide6 is missing (the installer
then falls back to pkexec and kdialog). Each field has one large "show" button and no "clear" button: on the tablet the
two small buttons kdialog puts side by side were hard to hit apart.
"""
import getpass
import os
import pwd
import sys

MOK_MIN = 8


def mok_problem(first, second):
    """What is still wrong with the two entries of the one-time password ("" when they are fine)."""
    if len(first) < MOK_MIN:
        return "At least %d characters." % MOK_MIN
    if not all(32 < ord(c) < 127 for c in first):
        return "Letters, digits and signs of the English keyboard only, no spaces."
    if first != second:
        return "The two entries differ." if second else "Type it again in the second field."
    return ""


def who():
    name = getpass.getuser()
    try:
        full = pwd.getpwnam(name).pw_gecos.split(",")[0]
    except KeyError:
        full = ""
    return "%s (%s)" % (full, name) if full else name


def build(mode, wrong=False):
    """(dialog, function returning the password) — made apart from main() so that a test can build and grab it."""
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QToolButton,
                                   QVBoxLayout)

    dialog = QDialog()
    dialog.setWindowTitle("Surface Overdrive")
    dialog.setWindowIcon(QIcon.fromTheme("dialog-password"))
    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(20, 20, 20, 16)
    outer.setSpacing(14)

    top = QHBoxLayout()
    top.setSpacing(16)
    icon = QLabel()
    icon.setPixmap(QIcon.fromTheme("dialog-password").pixmap(56, 56))
    top.addWidget(icon, 0, Qt.AlignTop)
    text = QLabel()
    text.setWordWrap(True)
    text.setMinimumWidth(440)
    text.setTextFormat(Qt.RichText)
    top.addWidget(text, 1)
    outer.addLayout(top)

    grid = QGridLayout()
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(10)
    outer.addLayout(grid)
    fields = []

    def add_field(row, label):
        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.Password)
        edit.setClearButtonEnabled(False)
        edit.setMinimumHeight(40)
        edit.setInputMethodHints(Qt.ImhHiddenText | Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText | Qt.ImhSensitiveData)
        show = QToolButton()
        show.setCheckable(True)
        show.setIcon(QIcon.fromTheme("view-visible"))
        show.setIconSize(QSize(24, 24))
        show.setFixedSize(48, 40)
        show.setToolTip("Show what is typed")
        show.setFocusPolicy(Qt.NoFocus)

        def toggled(on):
            edit.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password)
            show.setIcon(QIcon.fromTheme("view-hidden" if on else "view-visible"))
        show.toggled.connect(toggled)
        grid.addWidget(QLabel(label), row, 0)
        grid.addWidget(edit, row, 1)
        grid.addWidget(show, row, 2)
        fields.append(edit)
        return edit

    note = QLabel()
    note.setWordWrap(True)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    ok = buttons.button(QDialogButtonBox.Ok)
    for b in buttons.buttons():
        b.setMinimumSize(110, 40)
    buttons.rejected.connect(dialog.reject)

    if mode == "admin":
        text.setText("<b>Enter your password to install Surface Overdrive.</b><br><br>"
                     "It is needed once, to change the system: the install then runs by itself.<br>"
                     "<small>Authenticating as %s</small>" % who())
        first = add_field(0, "Password:")
        ok.setText("Install")
        note.setText("That password was not right. Try again." if wrong else "")

        def check():
            ok.setEnabled(bool(first.text()))
        first.textChanged.connect(check)
        buttons.accepted.connect(dialog.accept)
    else:
        text.setText("<b>Choose a one-time password for the Surface's signing key.</b><br><br>"
                     "You will type it once, at the next start, on a blue screen \"Perform MOK management\": "
                     "Enroll MOK, Continue, Yes, this password, Reboot.<br><br>"
                     "That screen has an English keyboard: small letters and digits are the safe choice. "
                     "At least %d characters." % MOK_MIN)
        first = add_field(0, "Password:")
        second = add_field(1, "Again:")
        ok.setText("OK")

        def check():
            problem = mok_problem(first.text(), second.text())
            ok.setEnabled(not problem)
            # nothing is complained about before something was typed
            note.setText(problem if first.text() else "")
        first.textChanged.connect(check)
        second.textChanged.connect(check)
        buttons.accepted.connect(lambda: None if mok_problem(first.text(), second.text()) else dialog.accept())
        first.returnPressed.connect(second.setFocus)

    outer.addWidget(note)
    outer.addWidget(buttons)
    check()
    fields[0].setFocus()
    return dialog, fields[0].text


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    mode = argv[0] if argv and argv[0] in ("admin", "mok") else None
    if mode is None:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        from PySide6.QtWidgets import QApplication, QDialog
    except ImportError:
        return 3
    app = QApplication(["surface-overdrive-installer"])
    app.setDesktopFileName("org.kde.konsole")        # no desktop file of ours before the install: Konsole's icon
    dialog, password = build(mode, "--wrong" in argv)
    if os.environ.get("OVERDRIVE_ASK_GRAB"):           # for the checks: a picture of the window, nothing asked
        dialog.show()
        app.processEvents()
        dialog.grab().save(os.environ["OVERDRIVE_ASK_GRAB"])
        return 0
    if dialog.exec() != QDialog.Accepted:
        return 1
    sys.stdout.write(password() + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
