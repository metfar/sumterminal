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
import argparse;
import ctypes;
import ctypes.util;
from importlib import resources;
import os;
from pathlib import Path;

from .ipc import send_command;


def tray_icon_path():
    try: return str(resources.files("sumterminal").joinpath("assets/sumterminal-tray.png"));
    except Exception: return str(Path(__file__).with_name("assets")/"sumterminal-tray.png");


class GtkTray:
    """Tiny dependency-free GTK3 legacy tray bridge for X11/XFCE.

    XFCE's Status Tray plugin accepts both StatusNotifier items and legacy
    XEmbed icons.  This fallback uses GtkStatusIcon so SUM does not require a
    Python GI binding merely to expose the tray control.
    """
    def __init__(self,socket_path,parent_pid=0,icon_path=None):
        self.socket_path=str(socket_path); self.parent_pid=int(parent_pid or 0); self.icon_path=str(icon_path or tray_icon_path()); self.callbacks=[];
        gtk_name=ctypes.util.find_library("gtk-3"); gobj_name=ctypes.util.find_library("gobject-2.0"); glib_name=ctypes.util.find_library("glib-2.0");
        if not gtk_name or not gobj_name: raise RuntimeError("GTK3 tray backend is unavailable");
        self.gtk=ctypes.CDLL(gtk_name); self.gobj=ctypes.CDLL(gobj_name); self.glib=ctypes.CDLL(glib_name) if glib_name else None;
        self._bind(); self.icon=None; self.menu=None;

    def _bind(self):
        g=self.gtk;
        g.gtk_init_check.argtypes=[ctypes.c_void_p,ctypes.c_void_p]; g.gtk_init_check.restype=ctypes.c_int;
        g.gtk_status_icon_new_from_file.argtypes=[ctypes.c_char_p]; g.gtk_status_icon_new_from_file.restype=ctypes.c_void_p;
        g.gtk_status_icon_set_tooltip_text.argtypes=[ctypes.c_void_p,ctypes.c_char_p];
        g.gtk_status_icon_set_visible.argtypes=[ctypes.c_void_p,ctypes.c_int];
        g.gtk_menu_new.restype=ctypes.c_void_p;
        g.gtk_menu_item_new_with_label.argtypes=[ctypes.c_char_p]; g.gtk_menu_item_new_with_label.restype=ctypes.c_void_p;
        g.gtk_separator_menu_item_new.restype=ctypes.c_void_p;
        g.gtk_menu_shell_append.argtypes=[ctypes.c_void_p,ctypes.c_void_p];
        g.gtk_widget_show_all.argtypes=[ctypes.c_void_p];
        g.gtk_menu_popup.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint,ctypes.c_uint32];
        g.gtk_main.argtypes=[]; g.gtk_main_quit.argtypes=[];
        self.gobj.g_signal_connect_data.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int]; self.gobj.g_signal_connect_data.restype=ctypes.c_ulong;
        if self.glib is not None:
            self.glib.g_timeout_add_seconds.argtypes=[ctypes.c_uint,ctypes.c_void_p,ctypes.c_void_p]; self.glib.g_timeout_add_seconds.restype=ctypes.c_uint;

    def _connect(self,obj,name,callback,signature):
        fn=signature(callback); self.callbacks.append(fn); self.gobj.g_signal_connect_data(obj,name.encode("ascii"),ctypes.cast(fn,ctypes.c_void_p),None,None,0); return fn;

    def _send(self,command):
        return send_command(command,path=self.socket_path,timeout=0.25);

    def _menu_item(self,label,command):
        item=self.gtk.gtk_menu_item_new_with_label(str(label).encode("utf-8"));
        callback_type=ctypes.CFUNCTYPE(None,ctypes.c_void_p,ctypes.c_void_p);
        self._connect(item,"activate",lambda _item,_data:self._send(command),callback_type); self.gtk.gtk_menu_shell_append(self.menu,item); return item;

    def run(self):
        if not self.gtk.gtk_init_check(None,None): return 2;
        if not Path(self.icon_path).exists(): return 2;
        self.icon=self.gtk.gtk_status_icon_new_from_file(self.icon_path.encode("utf-8"));
        if not self.icon: return 2;
        self.gtk.gtk_status_icon_set_tooltip_text(self.icon,b"SUM Terminal (\xce\xa3tl)"); self.gtk.gtk_status_icon_set_visible(self.icon,1);
        self.menu=self.gtk.gtk_menu_new(); self._menu_item("Show / Hide","toggle"); self._menu_item("New terminal tab","new-tab"); self._menu_item("Preferences","preferences");
        separator=self.gtk.gtk_separator_menu_item_new(); self.gtk.gtk_menu_shell_append(self.menu,separator); self._menu_item("Quit","quit"); self.gtk.gtk_widget_show_all(self.menu);
        activate_type=ctypes.CFUNCTYPE(None,ctypes.c_void_p,ctypes.c_void_p); self._connect(self.icon,"activate",lambda _icon,_data:self._send("toggle"),activate_type);
        popup_type=ctypes.CFUNCTYPE(None,ctypes.c_void_p,ctypes.c_uint,ctypes.c_uint32,ctypes.c_void_p);
        def popup(status_icon,button,activate_time,_data):
            try: position=ctypes.cast(self.gtk.gtk_status_icon_position_menu,ctypes.c_void_p);
            except Exception: position=None;
            self.gtk.gtk_menu_popup(self.menu,None,None,position,status_icon,int(button),int(activate_time));
        self._connect(self.icon,"popup-menu",popup,popup_type);
        if self.parent_pid>0 and self.glib is not None:
            timer_type=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p);
            def parent_watch(_data):
                try: os.kill(self.parent_pid,0); return 1;
                except OSError: self.gtk.gtk_main_quit(); return 0;
            watcher=timer_type(parent_watch); self.callbacks.append(watcher); self.glib.g_timeout_add_seconds(2,ctypes.cast(watcher,ctypes.c_void_p),None);
        self.gtk.gtk_main(); return 0;


def parser():
    value=argparse.ArgumentParser(prog="sumterminal-tray"); value.add_argument("--socket",required=True); value.add_argument("--parent-pid",type=int,default=0); value.add_argument("--icon",default=None); return value;


def main(argv=None):
    args=parser().parse_args(argv);
    try: return GtkTray(args.socket,args.parent_pid,args.icon).run();
    except Exception: return 2;


if __name__=="__main__": raise SystemExit(main());
