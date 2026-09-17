#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#pylint:disable=W0301
#  
#  Copyright 2018- William Martinez Bas <metfar@gmail.com>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
import argparse;
import os;
import shlex;
import signal;
import shutil;
import subprocess;
import sys;
import time;

from sumkeyboard.hotkeys import uninstall_global_shortcut;

from . import __version__;
from .config import config_path, load_preferences, save_preferences;
from .crashlog import crash_log_path, install_faulthandler, log_message;
from .errors import TerminalError;
from .gui import GuiTerminalView;
from .ipc import send_command;
from .preferences import install_dropdown_shortcut, show_preferences;
from .session import TerminalSession, default_shell_command;
from .theme import available_terminal_themes, canonical_theme_name;
from .view import HostTerminalView;


_ACTION_ID="sumterminal.dropdown";


def parser():
    value=argparse.ArgumentParser(prog="sumterminal",description="SUM terminal/session host; GUI and sumbash are the defaults.");
    value.add_argument("--version",action="version",version="sumterminal {}".format(__version__));
    value.add_argument("--cwd",default=None,help="initial SUM logical/native working directory");
    value.add_argument("--shell",default=None,help="explicit shell command line instead of default sumbash");
    value.add_argument("--rows",type=int,default=24,help="initial PTY rows before frontend resize");
    value.add_argument("--columns",type=int,default=80,help="initial PTY columns before frontend resize");
    value.add_argument("--theme",default=None,help="SUM theme for this launch (built-in or user theme)");
    value.add_argument("--list-themes",action="store_true",help="list available SUM themes and exit");
    value.add_argument("--font",default=None,help="GUI font family/name for this launch");
    value.add_argument("--font-size",type=int,default=None,help="GUI font size for this launch");
    modes=value.add_mutually_exclusive_group(); modes.add_argument("--gui",action="store_true",help="force the SUM graphical terminal frontend"); modes.add_argument("--host",action="store_true",help="bridge the session through the current host terminal");
    value.add_argument("--drop-down",action="store_true",help="open the graphical drop-down terminal");
    value.add_argument("--toggle",action="store_true",help="toggle the installed/running drop-down terminal");
    value.add_argument("--preferences",action="store_true",help="open SUM Terminal preferences");
    value.add_argument("--install",action="store_true",help="install/update the global drop-down shortcut from preferences");
    value.add_argument("--uninstall",action="store_true",help="remove the global drop-down shortcut when supported");
    value.add_argument("--no-raw",action="store_true",help="do not put host stdin in raw mode with --host");
    value.add_argument("--trace-input",action="store_true",help="trace GUI keyboard modes and bytes written to the PTY on stderr");
    value.add_argument("--no-crash-restart",action="store_true",help="do not restart the GUI worker after a fatal native crash");
    value.add_argument("--print-crash-log",action="store_true",help="print the terminal crash-log path and exit");
    value.add_argument("--print-default-shell",action="store_true",help="print the resolved default shell command and exit");
    value.add_argument("--_worker",action="store_true",help=argparse.SUPPRESS);
    value.add_argument("command",nargs=argparse.REMAINDER,help="command after --; default is sumbash");
    return value;


def _launcher_command(*extra):
    executable=shutil.which("sumterminal");
    return [executable,*extra] if executable else [sys.executable,"-m","sumterminal",*extra];


def _configured_shell_command(preferences):
    text=str(preferences.general.shell or "sumbash").strip();
    if not text or text.casefold()=="sumbash": return default_shell_command();
    command=shlex.split(text);
    return command or default_shell_command();


def _toggle_dropdown():
    if send_command("toggle"): return 0;
    command=_launcher_command("--drop-down");
    try: subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True);
    except OSError as exc: raise TerminalError("could not start drop-down terminal: {}".format(exc)) from exc;
    deadline=time.monotonic()+2.0;
    while time.monotonic()<deadline:
        if send_command("show"): break;
        time.sleep(0.05);
    return 0;


def _install(preferences):
    path=config_path();
    if not path.exists(): save_preferences(preferences,path);
    result=install_dropdown_shortcut(preferences,apply=True);
    print("sumterminal: preferences {}".format(path));
    print("sumterminal: {}".format(result.detail));
    return 0 if result.installed else 2;


def _fatal_native_returncode(code):
    value=int(code or 0);
    if os.name=="posix" and value<0:
        fatal=set();
        for name in ("SIGSEGV","SIGBUS","SIGILL","SIGABRT","SIGFPE"):
            signum=getattr(signal,name,None);
            if signum is not None: fatal.add(-int(signum));
        return value in fatal;
    if os.name=="nt":
        unsigned=value & 0xFFFFFFFF;
        return unsigned in (0xC0000005,0xC000001D,0xC0000094,0xC0000409);
    return False;


def _supervise_gui(raw_argv):
    command=[sys.executable,"-m","sumterminal","--_worker",*list(raw_argv or [])];
    crashes=[];
    while True:
        started=time.monotonic();
        code=subprocess.call(command);
        if not _fatal_native_returncode(code):
            return int(code or 0);
        now=time.monotonic();
        crashes=[stamp for stamp in crashes if now-stamp<20.0];
        crashes.append(now);
        detail="GUI worker crashed with status {}; restarting (crash log: {})".format(code,crash_log_path());
        print("sumterminal: {}".format(detail),file=sys.stderr);
        log_message(detail);
        if len(crashes)>=3:
            detail="GUI worker crashed 3 times within 20 seconds; automatic restart stopped";
            print("sumterminal: {}".format(detail),file=sys.stderr);
            log_message(detail);
            return 1;
        if time.monotonic()-started<0.5:
            time.sleep(0.25);


def main(argv=None):
    raw_argv=list(sys.argv[1:] if argv is None else argv);
    args=parser().parse_args(raw_argv); preferences=load_preferences();
    if args.list_themes:
        for name in available_terminal_themes(): print(name);
        return 0;
    if args.print_crash_log:
        print(crash_log_path());
        return 0;
    if args.theme is not None: preferences.general.theme=canonical_theme_name(args.theme,strict=True);
    if args.font is not None: preferences.general.font_name=str(args.font);
    if args.font_size is not None: preferences.general.font_size=int(args.font_size);
    preferences.normalized();
    try:
        if args.print_default_shell:
            print(" ".join(shlex.quote(value) for value in _configured_shell_command(preferences))); return 0;
        if args.toggle: return _toggle_dropdown();
        if args.install: return _install(preferences);
        if args.uninstall:
            removed=uninstall_global_shortcut(_ACTION_ID,preferences.dropdown.shortcut,apply=True); print("sumterminal: shortcut removed" if removed else "sumterminal: no automatic shortcut backend available"); return 0 if removed else 2;
        if args.preferences: return show_preferences(preferences);
        if args.drop_down and send_command("show"): return 0;
        command=list(args.command or []);
        if command and command[0]=="--": command=command[1:];
        if args.shell and command: print("sumterminal: use either --shell or a command after --, not both",file=sys.stderr); return 2;
        if args.shell: command=shlex.split(args.shell);
        elif not command and preferences.general.shell.casefold()!="sumbash": command=shlex.split(preferences.general.shell);
        force_gui=bool(args.gui or args.drop_down); frontend="host" if args.host else ("gui" if force_gui else preferences.general.frontend);
        if frontend=="gui" and not args._worker and not args.no_crash_restart and GuiTerminalView.available():
            return _supervise_gui(raw_argv);
        session=TerminalSession(command=command or None,cwd=args.cwd,rows=args.rows,columns=args.columns);
        if frontend=="gui":
            if GuiTerminalView.available():
                install_faulthandler();
                return GuiTerminalView(session,preferences=preferences,drop_down=args.drop_down,trace_input=args.trace_input).run();
            if force_gui: raise TerminalError("graphical frontend requested but sumGUI/Pygame is unavailable");
            if sys.stdin.isatty() and sys.stdout.isatty(): print("sumterminal: GUI unavailable; falling back to host terminal",file=sys.stderr); return HostTerminalView(session,raw=not args.no_raw).run();
            raise TerminalError("GUI unavailable and no host TTY is available");
        return HostTerminalView(session,raw=not args.no_raw).run();
    except (OSError,RuntimeError,TerminalError,ValueError) as exc:
        print("sumterminal: {}".format(exc),file=sys.stderr); return 1;


if __name__=="__main__": raise SystemExit(main());
