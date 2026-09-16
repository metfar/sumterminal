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
from .modes import TerminalModes;


_CURSOR_FINALS={"up":"A","down":"B","right":"C","left":"D","home":"H","end":"F"};
_TILDE_CODES={"insert":2,"delete":3,"pageup":5,"pagedown":6,"f5":15,"f6":17,"f7":18,"f8":19,"f9":20,"f10":21,"f11":23,"f12":24};
_SS3_FINALS={"f1":"P","f2":"Q","f3":"R","f4":"S"};
_KEYPAD_APPLICATION={"kp0":"p","kp1":"q","kp2":"r","kp3":"s","kp4":"t","kp5":"u","kp6":"v","kp7":"w","kp8":"x","kp9":"y","kp_period":"n","kp_divide":"o","kp_multiply":"j","kp_minus":"m","kp_plus":"k","kp_enter":"M","kp_equals":"X"};
_KEYPAD_NORMAL={"kp0":"0","kp1":"1","kp2":"2","kp3":"3","kp4":"4","kp5":"5","kp6":"6","kp7":"7","kp8":"8","kp9":"9","kp_period":".","kp_divide":"/","kp_multiply":"*","kp_minus":"-","kp_plus":"+","kp_enter":"\r","kp_equals":"="};


class TerminalInputEncoder:
    """Encode semantic key events according to current VT/xterm modes.""";

    def __init__(self,modes=None):
        self.modes=modes if modes is not None else TerminalModes();

    @staticmethod
    def modifier_parameter(shift=False,alt=False,ctrl=False):
        return 1+(1 if shift else 0)+(2 if alt else 0)+(4 if ctrl else 0);

    def encode_key(self,key,shift=False,alt=False,ctrl=False,text=""):
        name=str(key or "").casefold(); modifier=self.modifier_parameter(shift,alt,ctrl); printable=str(text or "");
        if name in _CURSOR_FINALS:
            final=_CURSOR_FINALS[name];
            if modifier!=1: return "\x1b[1;{}{}".format(modifier,final).encode("ascii");
            prefix="\x1bO" if self.modes.application_cursor else "\x1b[";
            return (prefix+final).encode("ascii");
        if name in _TILDE_CODES:
            code=_TILDE_CODES[name];
            if modifier!=1: return "\x1b[{};{}~".format(code,modifier).encode("ascii");
            return "\x1b[{}~".format(code).encode("ascii");
        if name in _SS3_FINALS:
            final=_SS3_FINALS[name];
            if modifier!=1: return "\x1b[1;{}{}".format(modifier,final).encode("ascii");
            return ("\x1bO"+final).encode("ascii");
        if name in _KEYPAD_NORMAL:
            if modifier!=1:
                normal=_KEYPAD_NORMAL[name];
                if normal=="\r": return b"\r";
                value=normal.encode("utf-8");
                return (b"\x1b"+value) if alt else value;
            if self.modes.application_keypad: return ("\x1bO"+_KEYPAD_APPLICATION[name]).encode("ascii");
            return _KEYPAD_NORMAL[name].encode("utf-8");
        if name=="shift-tab" or (name=="tab" and shift): return b"\x1b[Z";
        special={"return":b"\r","backspace":b"\x7f","tab":b"\t","escape":b"\x1b"};
        if name in special:
            data=special[name]; return b"\x1b"+data if alt and data!=b"\x1b" else data;
        if ctrl:
            data=None;
            if len(name)==1 and "a"<=name<="z": data=bytes([ord(name)-96]);
            elif name in ("space","@"): data=b"\x00";
            elif name=="[": data=b"\x1b";
            elif name=="\\": data=b"\x1c";
            elif name=="]": data=b"\x1d";
            elif name=="^": data=b"\x1e";
            elif name=="_": data=b"\x1f";
            if data is not None: return (b"\x1b"+data) if alt else data;
        if alt:
            value=printable if printable and all(ord(char)>=32 for char in printable) else (name if len(name)==1 and ord(name)>=32 else "");
            if value: return b"\x1b"+value.encode("utf-8");
        return b"";

    def encode_paste(self,data):
        value=data.encode("utf-8") if isinstance(data,str) else bytes(data or b"");
        if self.modes.bracketed_paste: return b"\x1b[200~"+value+b"\x1b[201~";
        return value;
