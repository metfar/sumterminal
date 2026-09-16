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
import shlex;
import sys;

from . import __version__;
from .errors import TerminalError;
from .session import TerminalSession, default_shell_command;
from .view import HostTerminalView;


def parser():
    value=argparse.ArgumentParser(prog="sumterminal",description="SUM terminal/session host; sumbash is the default shell.");
    value.add_argument("--version",action="version",version="sumterminal {}".format(__version__));
    value.add_argument("--cwd",default=None,help="initial SUM logical/native working directory");
    value.add_argument("--shell",default=None,help="explicit shell command line instead of default sumbash");
    value.add_argument("--rows",type=int,default=24,help="initial PTY rows before host resize");
    value.add_argument("--columns",type=int,default=80,help="initial PTY columns before host resize");
    value.add_argument("--no-raw",action="store_true",help="do not put host stdin in raw mode");
    value.add_argument("--print-default-shell",action="store_true",help="print the resolved default shell command and exit");
    value.add_argument("command",nargs=argparse.REMAINDER,help="command after --; default is sumbash");
    return value;


def main(argv=None):
    args=parser().parse_args(argv);
    try:
        if args.print_default_shell:
            print(" ".join(shlex.quote(value) for value in default_shell_command()));
            return 0;
        command=list(args.command or []);
        if command and command[0]=="--": command=command[1:];
        if args.shell and command:
            print("sumterminal: use either --shell or a command after --, not both",file=sys.stderr);
            return 2;
        if args.shell: command=shlex.split(args.shell);
        session=TerminalSession(command=command or None,cwd=args.cwd,rows=args.rows,columns=args.columns);
        return HostTerminalView(session,raw=not args.no_raw).run();
    except (OSError,TerminalError,ValueError) as exc:
        print("sumterminal: {}".format(exc),file=sys.stderr);
        return 1;


if __name__=="__main__": raise SystemExit(main());
