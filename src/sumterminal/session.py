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
from __future__ import annotations;

import importlib.util;
import os;
import shlex;
import shutil;
import sys;

from sumfsa import FileSystem;

from .decoder import TerminalDecoder;
from .errors import SessionStateError, TerminalError, UnsupportedPlatformError;
from .model import SessionInfo, SessionState, TerminalEvent, TerminalSize;


def default_shell_command(env=None):
    values=os.environ if env is None else env;
    configured=str(values.get("SUM_TERMINAL_SHELL","") or "").strip();
    if configured: return shlex.split(configured);
    executable=shutil.which("sumbash");
    if executable: return [executable];
    if importlib.util.find_spec("sumbash") is not None: return [sys.executable,"-m","sumbash"];
    raise TerminalError("sumbash is the default SUM terminal shell but it is not installed");


class TerminalSession:
    """Presentation-neutral local terminal session.""";

    def __init__(self,command=None,cwd=None,env=None,rows=24,columns=80,filesystem=None,encoding="utf-8"):
        self.filesystem=filesystem or FileSystem();
        self.logical_cwd=self.filesystem.normalize(cwd or self.filesystem.cwd);
        self.native_cwd=self.filesystem.native_path(self.logical_cwd);
        self.env=dict(env or {});
        # A terminal emulator must advertise its own capabilities instead of
        # inheriting whatever TERM happened to belong to the launcher.  This
        # is especially important for desktop/global-hotkey launches, where
        # there may be no parent terminal at all.
        self.env.setdefault("TERM","xterm-256color");
        self.env.setdefault("COLORTERM","truecolor");
        self.env.setdefault("TERM_PROGRAM","sumterminal");
        self.env.setdefault("SUM_TERMINAL","1");
        using_default=not command;
        self.argv=tuple(str(value) for value in (command or default_shell_command(self.env or None)));
        if using_default and len(self.argv)>=3 and self.argv[0]==sys.executable and self.argv[1:3]==("-m","sumbash"):
            search=[];
            for value in sys.path:
                native=os.path.abspath(value or os.getcwd());
                if native not in search: search.append(native);
            self.env.setdefault("PYTHONPATH",os.pathsep.join(search));
        self.size=TerminalSize(rows,columns).normalized();
        self.decoder=TerminalDecoder(encoding=encoding);
        self.adapter=None;
        self.state=SessionState.CREATED;
        self._eof_reported=False;
        self._exit_reported=False;

    def start(self):
        if self.state is not SessionState.CREATED: raise SessionStateError("terminal session can only be started once");
        if os.name!="posix": raise UnsupportedPlatformError("sumTerminal 0.1.0a1 implements POSIX PTY sessions; Windows ConPTY is the next platform adapter");
        from .posix import PosixPTYAdapter;
        self.adapter=PosixPTYAdapter().start(self.argv,cwd=self.native_cwd,env=self.env,size=self.size);
        self.state=SessionState.RUNNING;
        return self;

    @property
    def pid(self):
        return None if self.adapter is None else self.adapter.pid;

    @property
    def fileno(self):
        if self.adapter is None: raise SessionStateError("terminal session is not running");
        return self.adapter.fileno;

    def info(self):
        return SessionInfo(self.argv,self.logical_cwd,self.native_cwd,self.pid,self.state,self.size);

    def resize(self,rows,columns):
        if self.adapter is None: raise SessionStateError("terminal session is not running");
        self.size=self.adapter.resize(rows,columns);
        return TerminalEvent("resize",size=self.size);

    def write(self,data):
        if self.adapter is None: raise SessionStateError("terminal session is not running");
        return self.adapter.write(data);

    def read_result(self,size=65536):
        if self.adapter is None: raise SessionStateError("terminal session is not running");
        return self.adapter.read_result(size);

    def read_event(self,size=65536):
        if self.adapter is None: raise SessionStateError("terminal session is not running");
        result=self.adapter.read_result(size);
        if result.data:
            return TerminalEvent("output",raw=bytes(result.data),text=self.decoder.feed(result.data,False));
        if result.eof and not self._eof_reported:
            self._eof_reported=True;
            return TerminalEvent("eof",text=self.decoder.feed(b"",True));
        code=self.adapter.poll();
        if code is not None:
            self.state=SessionState.EXITED;
            if not self._exit_reported:
                self._exit_reported=True;
                return TerminalEvent("exit",exit_code=int(code));
        return None;

    def poll(self):
        if self.adapter is None: return None;
        code=self.adapter.poll();
        if code is not None and self.state is SessionState.RUNNING: self.state=SessionState.EXITED;
        return code;

    def wait(self,timeout=None):
        if self.adapter is None: raise SessionStateError("terminal session is not running");
        code=self.adapter.wait(timeout=timeout);
        self.state=SessionState.EXITED;
        return code;

    def terminate(self):
        if self.adapter is not None: self.adapter.terminate();

    def kill(self):
        if self.adapter is not None: self.adapter.kill();

    def close(self,terminate=False):
        if self.state is SessionState.CLOSED: return;
        if terminate and self.adapter is not None and self.adapter.poll() is None: self.adapter.terminate();
        if self.adapter is not None: self.adapter.close();
        self.state=SessionState.CLOSED;

    def __enter__(self):
        return self.start();

    def __exit__(self,exc_type,exc_value,traceback):
        self.close(terminate=True);
        return False;
