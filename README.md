# sumTerminal

`sumTerminal` is the reusable terminal/session layer for SUM.

The first alpha deliberately separates the terminal session engine from its presentation. It provides a real POSIX PTY-backed `TerminalSession`, byte-safe I/O through `sumIO.FDResource`, SUM logical working-directory resolution through `sumFSA`, incremental UTF-8 output decoding, terminal resize propagation, process lifecycle control, and a standalone host-terminal bridge.

The default shell is **sumbash**. An explicit command can still be used so the terminal is process-agnostic:

```sh
sumterminal
sumterminal -- bash
sumterminal -- python
sumterminal -- ssh host
```

The current standalone frontend reuses the host terminal emulator: it enters raw mode, forwards keyboard bytes to the PTY, writes PTY output bytes back to the host terminal unchanged, and propagates window-size changes. This makes the engine useful now while keeping it ready for a later SUM-owned GUI/drop-down/embedded renderer.

Current scope:

- POSIX PTY local sessions;
- `sumbash` default shell;
- arbitrary explicit local executable;
- start/read/write/resize/wait/terminate/kill lifecycle;
- raw bytes plus incremental decoded-text events;
- host terminal bridge;
- logical cwd via sumFSA.

Not yet claimed:

- Windows ConPTY;
- VT/xterm screen emulation in a SUM-owned graphical view;
- tabs, split panes or saved profiles;
- SSH session management beyond running the host `ssh` command;
- serial session presentation;
- drop-down window presentation;
- embedding in sumIDE.

Those build on the session contract introduced here rather than replacing it.

<p align=center><b>- oOo -</b></p>
