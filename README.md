# sumTerminal 0.1.0a2

`sumTerminal` is the reusable terminal/session layer for SUM. It is intentionally separate from `sumbash`: the shell supplies commands and language semantics; the terminal supplies PTY/session ownership and presentation.

The default experience is now graphical when `sumGUI`/Pygame is available, with **sumbash** as the default shell:

```sh
sumterminal
sumterminal --gui
sumterminal --host
sumterminal -- bash
sumterminal -- python
sumterminal -- ssh host
```

When graphical support is unavailable, plain `sumterminal` may fall back to the host terminal when stdin/stdout are attached to a TTY. `--gui` is strict and reports an error instead of silently changing frontend.

## Drop-down terminal

```sh
sumterminal --drop-down
sumterminal --toggle
```

The default global toggle is:

```text
Ctrl+F12
```

`--toggle` communicates with the running drop-down instance. Hiding the window does **not** terminate `sumbash` or the PTY. If no drop-down instance exists, `--toggle` starts one.

Install/update the desktop shortcut with:

```sh
sumterminal --install
```

Open preferences with:

```sh
sumterminal --preferences
```

Current drop-down preferences are persisted in `~/.config/sum/terminal.toml` on normal XDG/POSIX systems:

- global shortcut (default `Ctrl+F12`);
- height percentage (default `45%`);
- width percentage (default `100%`);
- opacity (default `94%`);
- top/bottom position and focus-loss behavior in the configuration model.

The graphical preference view exposes shortcut, height, width and opacity now. Applying preferences also asks `sumKeyboard` to refresh the global shortcut where the desktop backend supports it.

## Graphical terminal screen

`TerminalScreen` is the first SUM-owned VT/xterm screen model. It currently handles the normal shell/application subset needed for a usable GUI terminal:

- cursor positioning and movement;
- line/display erase operations;
- scrolling regions;
- ANSI SGR colours;
- 256-colour and true-colour SGR;
- bold, underline and inverse state;
- alternate-screen switching;
- OSC terminal title updates;
- cursor visibility.

The renderer consumes the same `TerminalSession` used by the host-terminal frontend. Terminal bytes still arrive through the PTY and `sumIO`; graphical presentation does not create a second session implementation.

## Global shortcut integration

The shortcut-installation contract belongs to `sumKeyboard`. The initial Linux backends cover:

- GNOME custom keybindings via `gsettings`;
- XFCE keyboard shortcuts via `xfconf-query`;
- `xbindkeys` when present.

If no supported automatic backend is found, installation reports that fact explicitly so the user can assign `Ctrl+F12` to `sumterminal --toggle` in the desktop keyboard settings.

## Current platform scope

Implemented now:

- POSIX PTY local sessions;
- `sumbash` default shell;
- arbitrary explicit local executable;
- GUI default / strict `--gui` / `--host`;
- SUM-owned VT screen and GUI renderer;
- persistent drop-down session;
- `Ctrl+F12` toggle design and desktop integration;
- preferences for shortcut, height, width and opacity;
- logical cwd via `sumFSA`;
- PTY byte transport via `sumIO`.

Still later slices:

- Windows ConPTY;
- native Windows global-hotkey registration;
- Android terminal presentation;
- tabs and split panes;
- saved session/SSH/serial profiles;
- embedding the same terminal view in `sumIDE`;
- broader VT/xterm compatibility for highly specialised full-screen applications.

<p align=center><b>- oOo -</b></p>
