#!/usr/bin/env python3
"""Make Plasma's lock screen usable with a finger.

The lock screen shows the password field when the mouse moves and hides it when the mouse leaves. A finger arrives as a mouse that is
pressed and then leaves at once, so on a tablet the password field shows while swiping and is gone the moment the finger lifts. This
changes the lock screen so that after a touch
  - lifting the finger does not hide the password field, which goes away after the usual ten seconds without input, and
  - it stays for as long as the on-screen keyboard is open or something is typed, as it does with a mouse over the screen.
It also adds Restart, Shut Down and Log Out to the actions of the lock screen (Plasma offers Sleep and Switch User only).

The file belongs to Fedora's plasma-desktop package, so it is edited in the image build. When its layout changes the file is left as it
is and the build goes on with a warning: the lock screen then behaves like the stock one.

usage: patch_lockscreen.py [path]
"""
import sys
from pathlib import Path

DEFAULT = "/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen/LockScreenUi.qml"
MARK = "// Surface Overdrive:"

CHANGES = [
    ("""        property bool blockUI: containsMouse && (""",
     """        %s a finger leaves no pointer behind, so once the screen was touched, lifting the finger is not the mouse going away
        property bool touched: false
        // which of Restart / Shut Down / Log Out was tapped once and waits for the second tap that confirms it
        property string armed: ""
        property bool blockUI: (containsMouse || touched) && (""" % MARK),
    ("""        onExited: {
            uiVisible = false;
        }
""",
     """        onExited: {
            if (!touched) {
                uiVisible = false;
            }
        }
        PointHandler {
            acceptedDevices: PointerDevice.TouchScreen
            onActiveChanged: {
                if (active) {
                    lockScreenRoot.touched = true;
                    lockScreenRoot.uiVisible = true;
                }
                fadeoutTimer.restart();
            }
        }
        Timer { id: disarm; interval: 4000; onTriggered: lockScreenRoot.armed = "" }
"""),
    # Restart, Shut Down and Log Out next to Sleep and Switch User. Nobody has typed the password at this point, so each
    # asks for a second tap within four seconds: a touch by accident (the tablet in a bag) does not switch it off.
    ("""                        visible: sessionManagement.canSwitchUser
                    }
                ]
""",
     """                        visible: sessionManagement.canSwitchUser
                    },
                    ActionButton {
                        text: lockScreenRoot.armed === "reboot" ? "Tap Again to Restart" : "Restart"
                        icon.name: "system-reboot"
                        visible: sessionManagement.canReboot
                        onClicked: {
                            if (lockScreenRoot.armed === "reboot") sessionManagement.requestReboot(SessionManagement.ConfirmationMode.Skip);
                            else { lockScreenRoot.armed = "reboot"; disarm.restart(); }
                        }
                    },
                    ActionButton {
                        text: lockScreenRoot.armed === "shutdown" ? "Tap Again to Shut Down" : "Shut Down"
                        icon.name: "system-shutdown"
                        visible: sessionManagement.canShutdown
                        onClicked: {
                            if (lockScreenRoot.armed === "shutdown") sessionManagement.requestShutdown(SessionManagement.ConfirmationMode.Skip);
                            else { lockScreenRoot.armed = "shutdown"; disarm.restart(); }
                        }
                    },
                    ActionButton {
                        text: lockScreenRoot.armed === "logout" ? "Tap Again to Log Out" : "Log Out"
                        icon.name: "system-log-out"
                        visible: sessionManagement.canLogout
                        onClicked: {
                            if (lockScreenRoot.armed === "logout") sessionManagement.requestLogout(SessionManagement.ConfirmationMode.Skip);
                            else { lockScreenRoot.armed = "logout"; disarm.restart(); }
                        }
                    }
                ]
"""),
    ("""                    lockScreenRoot.uiVisible = false;
                }
            }
        }
""",
     """                    lockScreenRoot.uiVisible = false;
                    lockScreenRoot.touched = false;
                }
            }
        }
"""),
    # With a finger the on-screen keyboard opens at once and covers the large action buttons. The strip at the very bottom stays
    # in sight under the keyboard: while the keyboard is open, the same actions sit there as small buttons.
    ("""            Item {
                Layout.fillWidth: true
            }

            Battery {}
""",
     """            Item {
                Layout.fillWidth: true
            }
            Repeater {
                model: !inputPanel.keyboardActive ? [] : [
                    { id: "sleep", text: "Sleep", icon: "system-suspend", can: sessionManagement.canSuspend },
                    { id: "reboot", text: "Restart", icon: "system-reboot", can: sessionManagement.canReboot },
                    { id: "shutdown", text: "Shut Down", icon: "system-shutdown", can: sessionManagement.canShutdown },
                    { id: "logout", text: "Log Out", icon: "system-log-out", can: sessionManagement.canLogout }
                ].filter(a => a.can)
                delegate: PlasmaComponents3.ToolButton {
                    focusPolicy: Qt.TabFocus
                    Layout.fillHeight: true
                    icon.name: modelData.icon
                    text: lockScreenRoot.armed === modelData.id ? "Tap Again" : modelData.text
                    onClicked: {
                        if (modelData.id === "sleep") { sessionManagement.suspend(); return; }
                        if (lockScreenRoot.armed !== modelData.id) { lockScreenRoot.armed = modelData.id; disarm.restart(); return; }
                        if (modelData.id === "reboot") sessionManagement.requestReboot(SessionManagement.ConfirmationMode.Skip);
                        else if (modelData.id === "shutdown") sessionManagement.requestShutdown(SessionManagement.ConfirmationMode.Skip);
                        else sessionManagement.requestLogout(SessionManagement.ConfirmationMode.Skip);
                    }
                }
            }
            Item {
                Layout.fillWidth: true
            }

            Battery {}
"""),
]


def patch(text):
    """The changed text, or None when the file does not look like the one this was written for."""
    if MARK in text:
        return text                                   # already done
    for old, new in CHANGES:
        if text.count(old) != 1:
            return None
        text = text.replace(old, new)
    return text


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
    original = path.read_text()
    patched = patch(original)
    if patched is None:
        print("WARNING: the layout of %s changed, the lock screen is left as it is (password field hides when the finger lifts)" % path)
    elif patched != original:
        path.write_text(patched)
        print("patched", path)
    else:
        print("already patched", path)


if __name__ == "__main__":
    main()
