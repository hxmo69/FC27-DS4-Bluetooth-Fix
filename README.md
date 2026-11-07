# FC 27 DualShock 4 Bluetooth Fix (DS4 → Xbox 360 bridge)

Fixes the **random inputs / controller stops working** problem when playing EA SPORTS FC 27 on PC with a **PS4 DualShock 4 over Bluetooth**.

> **Read this first**
> - This is an unofficial community tool. It is **not made by or affiliated with EA**.
> - It only passes your button presses through 1:1. It adds no macros, turbo or gameplay changes and never touches the game's files or memory.
> - Even so, EA's anti-cheat could treat virtual-controller tools differently from one day to the next, and EA reportedly blocked DS4Windows in an earlier FC release. **I cannot promise it is safe for your account. Use it at your own risk.** If FC 27 shows any warning about it, stop using it.
> - It worked on the author's PC with a DualShock 4 over Bluetooth. Your results may vary.

☕ **Free and open source.** If it saved your match night, you can [support me on Ko-fi](https://ko-fi.com/xmo07). Thank you!

---

## The problem

In FC 27 on PC, a DualShock 4 connected over **Bluetooth** can send random inputs or stop responding (the light bar even turns off). The same controller works over **USB**, and works over Bluetooth in FC 26 and other games. So the problem is in how FC 27 handles the Bluetooth DS4, and only EA can fix it properly.

## What this tool does

```
DualShock 4 (Bluetooth)  →  this bridge  →  virtual Xbox 360 controller  →  FC 27
```

FC 27 never talks to the Bluetooth DS4. It sees a normal Xbox 360 controller instead (so you will see Xbox button icons in the game). A second tool, **HidHide**, hides your real DS4 from the game so that it only sees the virtual one.

---

## What you need

- Windows 10 or 11
- Your DualShock 4, paired with your PC over Bluetooth
- **Python 3.12 or 3.13** from [https://www.python.org/downloads/windows/). OR The Microsoft Store version, which can confuse HidHide."worked with me just fine" ) Tick **"Add python.exe to PATH"** during setup.
- **HidHide**: <https://github.com/nefarius/HidHide/releases> (download and install the latest setup)
- **ViGEmBus**: installed automatically in step 3 below. If that fails, install it manually from <https://github.com/nefarius/ViGEmBus/releases>

None of these are included in this download, and each has its own license.

---

## Easiest way: use the window (recommended)

1. Install **Python 3.12 or 3.13** (tick "Add python.exe to PATH").
2. Double-click **`Start-DS4-Bridge-GUI.bat`**. A window opens with two tabs.
3. On the **Setup** tab, follow steps 1 to 6 from top to bottom. The window installs the Python packages for you, shows what is already installed, gives you the exact path to paste into HidHide, and opens the Windows controller test for you.
4. On the **Play** tab, press **Start bridge**. When both lights are green, launch FC 27.

Next time you just open the window: it goes straight to the Play tab. You can tick "Start the bridge automatically" so you only have to open it and launch the game. The **Create desktop shortcut** button puts a shortcut with the controller icon on your Desktop. Keep the window open while you play.

You still need to install **HidHide** yourself (the window gives you the download button) and **restart Windows** once afterwards.

## Manual way (console version, no window)

Prefer the black console window? Use `Start-DS4-Bridge.bat` and follow these steps instead.

### Setup (do this once)

**1. Install Python.** Install Python 3.12 or 3.13 and tick "Add python.exe to PATH".

**2. Install HidHide.** Run its setup and **restart your PC** when it asks.

**3. Start the bridge for the first time.** Put this folder anywhere (for example your Desktop) and double-click **`Start-DS4-Bridge.bat`**.
- The first run downloads the Python packages it needs (a minute or two). It may also open a **ViGEmBus installer**. Accept it, and restart your PC if it asks, then run the `.bat` again.
- When it works, the window says: **"Virtual Xbox 360 controller created."**
- Near the top it prints a line that looks like `...\python.exe`. **Copy that path**. You need it in the next step.

**4. Turn the DS4 on over Bluetooth** (press the PS button). The window should print **"Connected: PS4 Controller"**. Keep this window open.

**5. Set up HidHide.** Open **HidHide Configuration Client** from the Start menu.
1. **Applications** tab → click **+** → paste the `python.exe` path from step 3 and add it. (This lets the bridge still see your real controller.)
2. **Devices** tab → under the gaming devices, tick your **DualShock 4** (it shows as "Wireless Controller" or "PS4 Controller"). If there are two entries for it, tick both. Do **not** tick any Xbox 360 entry.
3. Tick **Enable device hiding**.

**6. Reconnect the controller.** Turn the DS4 off (hold the PS button) and on again. The bridge window should print **"Connected: PS4 Controller"** again.

**7. Check it.** Press **Win+R**, type `joy.cpl` and press Enter. You should see **only "Xbox 360 Controller for Windows"**. Open Properties and move the sticks to make sure the bars react.

If it matches, you are done.

---

### Every time you play (console version)

1. Turn on your DS4 (Bluetooth).
2. Double-click **`Start-DS4-Bridge.bat`** and wait for "Connected: PS4 Controller".
3. Launch FC 27.
4. When you finish, close the game, then press **Ctrl+C** in the bridge window (or just close it).

Keep the bridge window open while you play. If you close it, the game loses the controller.

## How to undo everything

- Open **HidHide Configuration Client** and **untick "Enable device hiding"**. Your DS4 works normally again.
- Close the bridge window. You can uninstall HidHide and ViGEmBus from Windows "Apps" settings.

---

## Troubleshooting

| What you see | What to do |
|---|---|
| **"No DualShock 4 visible"** (after enabling HidHide) | The bridge is not whitelisted. In HidHide, check the **Applications** tab contains the exact `python.exe` path the bridge prints. If you use Microsoft Store Python, install Python from python.org instead and use the new path. |
| **"Could not create the virtual Xbox controller"** | ViGEmBus is missing. Install it from the link above, restart, and run the bridge again. |
| `joy.cpl` shows **two controllers** (DS4 + Xbox) | Hiding is not working. Make sure the DS4 is ticked on the Devices tab and **Enable device hiding** is ticked. Then turn the controller off and on. |
| The game still sees the old behaviour | Close the game fully, check `joy.cpl` as in step 7, and start the bridge **before** the game. Also close DS4Windows, InputMapper, reWASD and turn off Steam Input for FC 27. |
| No rumble | Rumble forwarding is best-effort. Tell me which game mode and I will look at it. |
| Controller disconnects by itself | That is a Bluetooth or battery issue. Charge it and keep the adapter close. |
| `python` / `py` not found | Install Python (step 1) and tick "Add python.exe to PATH". |
| Windows SmartScreen or antivirus warns about the `.bat` | The `.bat` only installs two Python packages and runs `ds4_xbox_bridge.py`. You can open both files in Notepad to read them. |

Only tested with the official **DualShock 4**. A DualSense (PS5) might work, but I have not tested it.

---

## Support

This tool is free. If it helped you, you can [buy me a coffee on Ko-fi](https://ko-fi.com/xmo07). It is never required, and I will keep fixing things either way. If something does not work, open an Issue on this page and include the text from the window's Activity log.

## Credits and licenses

- Built on [pygame-ce](https://github.com/pygame-community/pygame-ce) (reads the DS4 through SDL), [vgamepad](https://github.com/yannbouteiller/vgamepad) (virtual controller), [ViGEmBus](https://github.com/nefarius/ViGEmBus) and [HidHide](https://github.com/nefarius/HidHide) by Nefarius Software Solutions.
- This tool's own code is under the MIT License (see `LICENSE`).
- "EA SPORTS FC", "PlayStation", "DualShock" and "Xbox" are trademarks of their respective owners. This project is not affiliated with or endorsed by them.
