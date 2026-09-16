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

import fcntl;
import os;
import pty;
import signal;
import struct;
import subprocess;
import termios;

from sumio import FDResource;

from .errors import SessionStateError;
from .model import TerminalSize;


class PosixPTYAdapter:
    """Local POSIX terminal session backed by a PTY master FDResource.""";

    def __init__(self):
        self.process=None;
        self.master=None;
        self.size=TerminalSize();

    @property
    def pid(self):
        return None if self.process is None else self.process.pid;

    @property
    def fileno(self):
        if self.master is None: raise SessionStateError("terminal session is not running");
        return self.master.fd;

    def start(self,argv,cwd=None,env=None,size=None):
        if self.process is not None: raise SessionStateError("terminal session already started");
        if not argv: raise ValueError("terminal command is empty");
        master_fd,slave_fd=pty.openpty();
        self.size=(size or TerminalSize()).normalized();
        self._set_winsize_fd(slave_fd,self.size);
        child_env=os.environ.copy();
        if env: child_env.update({str(key):str(value) for key,value in dict(env).items()});
        child_env.setdefault("TERM","xterm-256color");
        def child_setup():
            os.setsid();
            try: fcntl.ioctl(slave_fd,termios.TIOCSCTTY,0);
            except OSError: pass;
        try:
            self.process=subprocess.Popen(list(argv),stdin=slave_fd,stdout=slave_fd,stderr=slave_fd,cwd=cwd,env=child_env,close_fds=True,preexec_fn=child_setup);
        except Exception:
            os.close(master_fd); os.close(slave_fd); raise;
        os.close(slave_fd);
        os.set_blocking(master_fd,False);
        self.master=FDResource(master_fd,name="pty:{}".format(self.process.pid),readable=True,writable=True,close_fd=True,tty=True);
        return self;

    @staticmethod
    def _set_winsize_fd(fd,size):
        value=size.normalized();
        payload=struct.pack("HHHH",value.rows,value.columns,0,0);
        fcntl.ioctl(int(fd),termios.TIOCSWINSZ,payload);

    def resize(self,rows,columns):
        if self.master is None: raise SessionStateError("terminal session is not running");
        self.size=TerminalSize(rows,columns).normalized();
        self._set_winsize_fd(self.master.fd,self.size);
        if self.process is not None and self.process.poll() is None:
            try: os.killpg(self.process.pid,signal.SIGWINCH);
            except (OSError,ProcessLookupError): pass;
        return self.size;

    def read_result(self,size=65536):
        if self.master is None: raise SessionStateError("terminal session is not running");
        return self.master.read_result(size);

    def write(self,data):
        if self.master is None: raise SessionStateError("terminal session is not running");
        return self.master.write(data);

    def poll(self):
        return None if self.process is None else self.process.poll();

    def wait(self,timeout=None):
        if self.process is None: raise SessionStateError("terminal session is not running");
        return self.process.wait(timeout=timeout);

    def terminate(self):
        if self.process is None or self.process.poll() is not None: return;
        try: os.killpg(self.process.pid,signal.SIGTERM);
        except (OSError,ProcessLookupError): self.process.terminate();

    def kill(self):
        if self.process is None or self.process.poll() is not None: return;
        try: os.killpg(self.process.pid,signal.SIGKILL);
        except (OSError,ProcessLookupError): self.process.kill();

    def close(self):
        if self.master is not None:
            self.master.close();
            self.master=None;
