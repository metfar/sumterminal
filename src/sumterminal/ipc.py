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
import os;
from pathlib import Path;
import queue;
import socket;
import tempfile;
import threading;


def socket_path(env=None):
    values=os.environ if env is None else env; root=values.get("XDG_RUNTIME_DIR") or tempfile.gettempdir();
    uid=getattr(os,"getuid",lambda:0)();
    return Path(root)/"sumterminal-{}-dropdown.sock".format(uid);


def send_command(command,path=None,timeout=0.35):
    target=str(path or socket_path()); client=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); client.settimeout(float(timeout));
    try:
        client.connect(target); client.sendall((str(command).strip()+"\n").encode("utf-8")); return True;
    except (OSError,ValueError): return False;
    finally: client.close();


class DropdownIPCServer:
    def __init__(self,path=None):
        self.path=Path(path or socket_path()); self.commands=queue.Queue(); self.socket=None; self.thread=None; self.running=False;

    def start(self):
        if not hasattr(socket,"AF_UNIX"): return False;
        self.path.parent.mkdir(parents=True,exist_ok=True);
        try: self.path.unlink();
        except FileNotFoundError: pass;
        self.socket=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); self.socket.bind(str(self.path)); self.socket.listen(4); self.socket.settimeout(0.25); self.running=True;
        self.thread=threading.Thread(target=self._serve,name="sumterminal-dropdown-ipc",daemon=True); self.thread.start(); return True;

    def _serve(self):
        while self.running and self.socket is not None:
            try: client,_address=self.socket.accept();
            except socket.timeout: continue;
            except OSError: break;
            try:
                data=client.recv(4096).decode("utf-8","replace");
                for line in data.splitlines():
                    command=line.strip();
                    if command: self.commands.put(command);
            finally: client.close();

    def pending(self):
        values=[];
        while True:
            try: values.append(self.commands.get_nowait());
            except queue.Empty: return values;

    def close(self):
        self.running=False;
        if self.socket is not None:
            try: self.socket.close();
            except OSError: pass;
            self.socket=None;
        try: self.path.unlink();
        except FileNotFoundError: pass;
