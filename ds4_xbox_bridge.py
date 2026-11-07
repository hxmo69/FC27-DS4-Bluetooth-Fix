"""
DS4 -> Xbox 360 bridge for FC 27 (Bluetooth DualShock 4 workaround)

What it does
  Reads your DualShock 4 (SDL handles the Bluetooth report format correctly) and
  presents it to Windows as a virtual Xbox 360 controller. FC 27 then talks to the
  virtual pad instead of the Bluetooth DS4.

What it does NOT do
  Strictly 1:1 mapping. No macros, no turbo, no deadzone tricks, no timing changes,
  nothing that touches the game process.

Requirements (the .bat installs the Python packages for you)
  - Python 3.10+ on Windows
  - ViGEmBus driver (virtual Xbox pad)   -> usually installed by `pip install vgamepad`
  - HidHide driver (hides the real DS4 from the game, otherwise FC 27 still sees it)
"""
import os
import sys
import time

# These must be set BEFORE SDL starts.
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"   # keep reading while the game has focus
os.environ["SDL_JOYSTICK_HIDAPI_PS4"] = "1"
os.environ["SDL_JOYSTICK_HIDAPI_PS4_RUMBLE"] = "1"
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

# SDL controller button names we forward, and the XUSB (Xbox 360) button each becomes.
BUTTON_MAP = {
    "A": "XUSB_GAMEPAD_A",
    "B": "XUSB_GAMEPAD_B",
    "X": "XUSB_GAMEPAD_X",
    "Y": "XUSB_GAMEPAD_Y",
    "BACK": "XUSB_GAMEPAD_BACK",
    "GUIDE": "XUSB_GAMEPAD_GUIDE",
    "START": "XUSB_GAMEPAD_START",
    "LEFTSTICK": "XUSB_GAMEPAD_LEFT_THUMB",
    "RIGHTSTICK": "XUSB_GAMEPAD_RIGHT_THUMB",
    "LEFTSHOULDER": "XUSB_GAMEPAD_LEFT_SHOULDER",
    "RIGHTSHOULDER": "XUSB_GAMEPAD_RIGHT_SHOULDER",
    "DPAD_UP": "XUSB_GAMEPAD_DPAD_UP",
    "DPAD_DOWN": "XUSB_GAMEPAD_DPAD_DOWN",
    "DPAD_LEFT": "XUSB_GAMEPAD_DPAD_LEFT",
    "DPAD_RIGHT": "XUSB_GAMEPAD_DPAD_RIGHT",
}

REAL_PAD_WORDS = ("ps4", "ps5", "dualshock", "dualsense", "wireless controller")
VIRTUAL_PAD_WORDS = ("xbox", "x360", "vigem", "virtual")


# ---------- pure conversion helpers (tested without any hardware) ----------
def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def stick(v):
    """SDL stick (-32768..32767) -> XInput stick, same direction."""
    return _clamp(int(v), -32768, 32767)


def stick_inverted(v):
    """SDL Y is 'down = positive'; XInput Y is 'up = positive'. Flip it."""
    return _clamp(-int(v), -32768, 32767)


def trigger(v):
    """SDL trigger (0..32767) -> XInput trigger (0..255)."""
    return _clamp(int(round(int(v) * 255 / 32767)), 0, 255)


def make_snapshot(pressed, lx, ly, rx, ry, l2, r2):
    """Everything the virtual pad needs, as one comparable tuple."""
    return (frozenset(pressed), stick(lx), stick_inverted(ly), stick(rx), stick_inverted(ry),
            trigger(l2), trigger(r2))


def is_real_ds4_name(name):
    n = (name or "").lower()
    if any(w in n for w in VIRTUAL_PAD_WORDS):
        return False
    return any(w in n for w in REAL_PAD_WORDS)


def rumble_args(large_motor, small_motor):
    """XInput motors (0..255) -> SDL (low_freq, high_freq) in 0.0..1.0."""
    return (_clamp(large_motor, 0, 255) / 255.0, _clamp(small_motor, 0, 255) / 255.0)


# ---------- runtime ----------
def main():
    try:
        import pygame
        from pygame._sdl2 import controller as sdl_controller
    except ImportError:
        print("Missing package. Run:  py -m pip install pygame-ce vgamepad")
        return 1
    try:
        import vgamepad as vg
    except Exception as e:  # noqa: BLE001
        print("Could not load vgamepad:", e)
        print("Run:  py -m pip install vgamepad")
        return 1

    print("=" * 60)
    print(" DS4 -> Xbox 360 bridge")
    print("=" * 60)
    print("If you use HidHide, whitelist THIS program (add it under 'Applications'):")
    print("   ", sys.executable)
    print()
    print("Free tool. Support it on Ko-fi: https://ko-fi.com/xmo07")
    print()

    try:
        vpad = vg.VX360Gamepad()
    except Exception as e:  # noqa: BLE001
        print("Could not create the virtual Xbox controller:", e)
        print("The ViGEmBus driver is probably missing. Install it, reboot, and run again.")
        print("(Download: github.com/nefarius/ViGEmBus/releases)")
        return 1

    pygame.init()
    pygame.joystick.init()
    sdl_controller.init()

    button_consts = {n: getattr(pygame, "CONTROLLER_BUTTON_" + n)
                     for n in BUTTON_MAP if hasattr(pygame, "CONTROLLER_BUTTON_" + n)}
    xusb = {}
    for n, attr in BUTTON_MAP.items():
        b = getattr(vg.XUSB_BUTTON, attr, None)
        if b is not None:
            xusb[n] = b

    AX = {k: getattr(pygame, "CONTROLLER_AXIS_" + k) for k in
          ("LEFTX", "LEFTY", "RIGHTX", "RIGHTY", "TRIGGERLEFT", "TRIGGERRIGHT")}

    state = {"ctrl": None}

    def on_rumble(client, target, large_motor, small_motor, led_number, user_data):
        """Game -> virtual pad rumble -> real DS4 rumble."""
        c = state["ctrl"]
        if c is None:
            return
        try:
            if large_motor or small_motor:
                low, high = rumble_args(large_motor, small_motor)
                c.rumble(low, high, 10000)
            else:
                c.stop_rumble()
        except Exception:  # noqa: BLE001
            pass

    try:
        vpad.register_notification(callback_function=on_rumble)
    except Exception as e:  # noqa: BLE001
        print("Rumble forwarding unavailable:", e)

    def find_ds4():
        for i in range(sdl_controller.get_count()):
            if not sdl_controller.is_controller(i):
                continue
            try:
                j = pygame.joystick.Joystick(i)
                name = j.get_name()
                j.quit()
            except Exception:  # noqa: BLE001
                continue
            if is_real_ds4_name(name):
                return i, name
        return None, None

    def read(c):
        pressed = [n for n, const in button_consts.items() if c.get_button(const)]
        g = c.get_axis
        return make_snapshot(pressed, g(AX["LEFTX"]), g(AX["LEFTY"]), g(AX["RIGHTX"]), g(AX["RIGHTY"]),
                             g(AX["TRIGGERLEFT"]), g(AX["TRIGGERRIGHT"]))

    def push(snap):
        pressed, lx, ly, rx, ry, lt, rt = snap
        for n, b in xusb.items():
            if n in pressed:
                vpad.press_button(button=b)
            else:
                vpad.release_button(button=b)
        vpad.left_joystick(x_value=lx, y_value=ly)
        vpad.right_joystick(x_value=rx, y_value=ry)
        vpad.left_trigger(value=lt)
        vpad.right_trigger(value=rt)
        vpad.update()

    print("Virtual Xbox 360 controller created. Waiting for a DualShock 4...")
    print("(Press Ctrl+C to stop.)")
    last = None
    next_scan = 0.0
    waiting_msg = False
    try:
        while True:
            pygame.event.pump()
            ctrl = state["ctrl"]
            if ctrl is not None and not ctrl.attached():
                print("DualShock 4 disconnected. Waiting for it to come back...")
                try:
                    ctrl.quit()
                except Exception:  # noqa: BLE001
                    pass
                state["ctrl"] = ctrl = None
                vpad.reset()
                vpad.update()
                last = None
            if ctrl is None:
                now = time.time()
                if now >= next_scan:
                    next_scan = now + 1.0
                    idx, name = find_ds4()
                    if idx is not None:
                        try:
                            state["ctrl"] = ctrl = sdl_controller.Controller(idx)
                            print("Connected:", name)
                            waiting_msg = False
                        except Exception as e:  # noqa: BLE001
                            print("Could not open controller:", e)
                    elif not waiting_msg:
                        waiting_msg = True
                        print("No DualShock 4 visible. Turn it on / pair it. If it is hidden with HidHide,")
                        print("make sure the path above is whitelisted.")
                if ctrl is None:
                    time.sleep(0.05)
                    continue
            snap = read(ctrl)
            if snap != last:
                push(snap)
                last = snap
            time.sleep(0.004)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            vpad.reset()
            vpad.update()
        except Exception:  # noqa: BLE001
            pass
        print("Stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
