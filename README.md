# sumTerminal 0.1.0a7

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

## Tabs

The graphical frontend owns multiple independent PTY sessions in one window.
A new tab starts the shell configured in Preferences and keeps the existing
tabs running in the background.

```text
Ctrl+Shift+T    new tab
```

Tabs can also be selected with the mouse, closed with the `×` on the tab, or
created with the `+` button.  Background tabs continue to drain their PTYs so
long-running commands do not block merely because another tab is visible.

Themes are shared with the SUM theme system (`sumtheme` / `sumTUI`) rather than maintained as a terminal-only theme database.  Built-in and user themes can be selected in Preferences, listed from the command line, or overridden for one launch:

```sh
sumterminal --list-themes
sumterminal --theme Dark
sumterminal --theme DOS
```

The application chrome uses the theme's normal SUM roles (`bg`, `panel`, `line`, `text`, selection and cursor colours).  The terminal surface uses `viewer_bg` / `viewer_text`, the cursor colour and the theme palette.  ANSI indexes 0-15 are themeable; xterm colours 16-255 retain the standard colour cube/greyscale and true-colour SGR values are rendered exactly as requested by the application.  Theme changes are hot-reloaded into existing tabs without restarting their PTYs or shells.

One-shot font overrides are also available:

```sh
sumterminal --font "DejaVu Sans Mono" --font-size 16
```

Terminal fonts are treated as a fixed cell grid.  If the selected family is
proportional, the renderer falls back to the system monospace family rather
than letting glyph widths and the cursor drift apart.  Cursor geometry is
derived from the actual font glyph height and line spacing.

Current drop-down preferences are persisted in `~/.config/sum/terminal.toml` on normal XDG/POSIX systems:

- global shortcut (default `Ctrl+F12`);
- height percentage (default `45%`);
- width percentage (default `100%`);
- opacity (default `94%`);
- top/bottom position and focus-loss behavior in the configuration model.

The graphical preference view exposes the SUM theme, default shell command, font family/name, font size, shortcut, height, width and opacity.  The default shell is `sumbash`; values such as `bash -l`, `zsh`, `python` or an explicit executable/argument line are also accepted.  Changing the default shell affects subsequently created tabs and future terminal launches; it does not replace shells already running in existing tabs. Applying preferences preserves the PTY and `sumbash`, and also asks `sumKeyboard` to refresh the global shortcut where the desktop backend supports it.  When Preferences is opened by a running drop-down, display changes are deferred until that Preferences process closes so SDL does not recreate a hidden window while another Pygame window is active.

When Preferences is opened from the drop-down, the terminal window is hidden
while the preference window is active and restored afterwards.  The PTY and
shell remain alive.  The terminal now avoids unconditional display recreation when Preferences closes.  Theme/font-only changes keep the existing SDL window; `pygame.display.set_mode()` is used only when the requested geometry actually changed.  This avoids the hidden-window recreation path that can crash in some distro Pygame/SDL combinations.

## Graphical terminal screen

`TerminalScreen` is the first SUM-owned VT/xterm screen model. It currently handles the normal shell/application subset needed for a usable GUI terminal:

- cursor positioning and movement;
- line/display erase operations;
- scrolling regions;
- ANSI SGR colours, including bright/bold base-colour rendering;
- 256-colour and true-colour SGR;
- bold, underline and inverse state;
- alternate-screen switching;
- OSC terminal title updates;
- cursor visibility.

The renderer consumes the same `TerminalSession` used by the host-terminal frontend. Terminal bytes still arrive through the PTY and `sumIO`; graphical presentation does not create a second session implementation.

Every PTY session advertises `TERM=xterm-256color`, `COLORTERM=truecolor`,
`TERM_PROGRAM=sumterminal` and `SUM_TERMINAL=1` unless the caller explicitly
overrides a value.  This makes a session started from a desktop hotkey behave
the same as one started from an existing terminal emulator.

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
- preferences for font family/name, font size, shortcut, height, width and opacity;
- logical cwd via `sumFSA`;
- PTY byte transport via `sumIO`.

Still later slices:

- Windows ConPTY;
- native Windows global-hotkey registration;
- Android terminal presentation;
- split panes;
- saved session/SSH/serial profiles;
- embedding the same terminal view in `sumIDE`;
- broader VT/xterm compatibility for highly specialised full-screen applications.

<p align=center><b>- oOo -</b></p>
