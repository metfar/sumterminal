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

import os;
import selectors;
import signal;
import sys;
import termios;
import tty;

from .session import TerminalSession;


class HostTerminalView:
    """Bridge a TerminalSession to the terminal emulator already hosting SUM.""";

    def __init__(self,session,raw=True,stdin=None,stdout=None):
        self.session=session;
        self.raw=bool(raw);
        self.stdin=stdin or sys.stdin;
        self.stdout=stdout or sys.stdout;
        self._resize_pending=True;
        self._old_winch=None;
        self._old_attrs=None;

    def _terminal_size(self):
        try:
            size=os.get_terminal_size(self.stdout.fileno());
            return size.lines,size.columns;
        except OSError:
            return self.session.size.rows,self.session.size.columns;

    def _on_winch(self,signum,frame):
        self._resize_pending=True;

    def _enter(self):
        if self.raw and self.stdin.isatty():
            fd=self.stdin.fileno();
            self._old_attrs=termios.tcgetattr(fd);
            tty.setraw(fd);
        if hasattr(signal,"SIGWINCH"):
            self._old_winch=signal.getsignal(signal.SIGWINCH);
            signal.signal(signal.SIGWINCH,self._on_winch);

    def _leave(self):
        if self._old_attrs is not None:
            try: termios.tcsetattr(self.stdin.fileno(),termios.TCSADRAIN,self._old_attrs);
            except termios.error: pass;
            self._old_attrs=None;
        if hasattr(signal,"SIGWINCH") and self._old_winch is not None:
            signal.signal(signal.SIGWINCH,self._old_winch);
            self._old_winch=None;

    def _write_host(self,data):
        if not data: return;
        try: os.write(self.stdout.fileno(),bytes(data));
        except (AttributeError,OSError):
            stream=getattr(self.stdout,"buffer",self.stdout);
            stream.write(bytes(data)); stream.flush();

    def run(self):
        if self.session.state.value=="created": self.session.start();
        selector=selectors.DefaultSelector();
        selector.register(self.session.fileno,selectors.EVENT_READ,"pty");
        stdin_fd=None;
        try:
            stdin_fd=self.stdin.fileno();
            selector.register(stdin_fd,selectors.EVENT_READ,"stdin");
        except (AttributeError,OSError,ValueError): stdin_fd=None;
        pty_eof=False;
        self._enter();
        try:
            while True:
                if self._resize_pending:
                    rows,columns=self._terminal_size();
                    self.session.resize(rows,columns);
                    self._resize_pending=False;
                for key,_mask in selector.select(0.10):
                    if key.data=="stdin":
                        try: data=os.read(key.fd,65536);
                        except OSError: data=b"";
                        if data: self.session.write(data);
                        else:
                            try: selector.unregister(key.fd);
                            except Exception: pass;
                    else:
                        result=self.session.read_result(65536);
                        if result.data: self._write_host(result.data);
                        if result.eof:
                            pty_eof=True;
                            try: selector.unregister(key.fd);
                            except Exception: pass;
                code=self.session.poll();
                if code is not None and pty_eof: return int(code);
                if code is not None and not selector.get_map(): return int(code);
        finally:
            self._leave();
            selector.close();
            if self.session.poll() is None: self.session.terminate();
            try: self.session.wait(timeout=1.0);
            except Exception: pass;
            self.session.close();
