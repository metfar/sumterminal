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
from dataclasses import dataclass;

from .modes import TerminalModes;


_ANSI16=((0,0,0),(205,0,0),(0,205,0),(205,205,0),(0,0,238),(205,0,205),(0,205,205),(229,229,229),(127,127,127),(255,0,0),(0,255,0),(255,255,0),(92,92,255),(255,0,255),(0,255,255),(255,255,255));


def _xterm_color(index,ansi16=None):
    palette=tuple(ansi16 or _ANSI16);
    index=max(0,min(255,int(index)));
    if index<16: return palette[index];
    if index<232:
        value=index-16; r=value//36; g=(value%36)//6; b=value%6; levels=(0,95,135,175,215,255); return (levels[r],levels[g],levels[b]);
    level=8+(index-232)*10; return (level,level,level);


@dataclass
class Cell:
    char: str=" ";
    fg: tuple=(229,229,229);
    bg: tuple=(0,0,0);
    bold: bool=False;
    underline: bool=False;
    inverse: bool=False;

    def copy(self):
        return Cell(self.char,self.fg,self.bg,self.bold,self.underline,self.inverse);


class TerminalScreen:
    """Small VT/xterm screen model used by the graphical SUM terminal frontend.""";

    def __init__(self,rows=24,columns=80,scrollback=5000):
        self.ansi16=tuple(_ANSI16); self.rows=max(1,int(rows)); self.columns=max(1,int(columns)); self.scrollback_limit=max(0,int(scrollback));
        self.default_fg=self.ansi16[7]; self.default_bg=self.ansi16[0]; self.scrollback=[]; self.title="SUM Terminal";
        self._alternate=False; self._saved_primary=None; self.reset();

    def set_palette(self,ansi16=None,default_fg=None,default_bg=None,remap=True):
        old_palette=tuple(self.ansi16); old_fg=tuple(self.default_fg); old_bg=tuple(self.default_bg);
        new_palette=tuple(tuple(color) for color in (ansi16 or old_palette));
        if len(new_palette)<16: new_palette=new_palette+tuple(_ANSI16[len(new_palette):]);
        new_palette=new_palette[:16]; new_fg=tuple(default_fg or new_palette[7]); new_bg=tuple(default_bg or new_palette[0]);
        def remap_color(color,is_background=False):
            value=tuple(color); old_default=old_bg if is_background else old_fg; new_default=new_bg if is_background else new_fg;
            if value==old_default: return new_default;
            try: index=old_palette.index(value);
            except ValueError: return value;
            return new_palette[index] if index<len(new_palette) else value;
        if remap:
            for line in list(self.lines)+list(self.scrollback):
                for cell in line:
                    cell.fg=remap_color(cell.fg,False); cell.bg=remap_color(cell.bg,True);
            self.fg=remap_color(self.fg,False); self.bg=remap_color(self.bg,True);
        self.ansi16=new_palette; self.default_fg=new_fg; self.default_bg=new_bg;
        return self;

    def _blank_cell(self):
        return Cell(" ",self.default_fg,self.default_bg,False,False,False);

    def _blank_line(self):
        return [self._blank_cell() for _ in range(self.columns)];

    def reset(self):
        self.lines=[self._blank_line() for _ in range(self.rows)]; self.row=0; self.col=0; self.saved=(0,0); self.scroll_top=0; self.scroll_bottom=self.rows-1;
        if hasattr(self,"modes"): self.modes.__dict__.update(TerminalModes().__dict__);
        else: self.modes=TerminalModes();
        self.fg=self.default_fg; self.bg=self.default_bg; self.bold=False; self.underline=False; self.inverse=False; self._state="normal"; self._buffer=""; self.pending_replies=[]; self._keyboard_flags_by_screen={False:0,True:0}; self._keyboard_stacks={False:[],True:[]};

    @property
    def application_cursor_keys(self):
        return self.modes.application_cursor;

    @application_cursor_keys.setter
    def application_cursor_keys(self,value):
        self.modes.application_cursor=bool(value);

    @property
    def application_keypad(self):
        return self.modes.application_keypad;

    @application_keypad.setter
    def application_keypad(self,value):
        self.modes.application_keypad=bool(value);

    @property
    def mouse_tracking(self):
        return self.modes.mouse_tracking;

    @mouse_tracking.setter
    def mouse_tracking(self,value):
        self.modes.mouse_tracking=int(value or 0);

    @property
    def mouse_sgr(self):
        return self.modes.mouse_sgr;

    @mouse_sgr.setter
    def mouse_sgr(self,value):
        self.modes.mouse_sgr=bool(value);

    @property
    def bracketed_paste(self):
        return self.modes.bracketed_paste;

    @bracketed_paste.setter
    def bracketed_paste(self,value):
        self.modes.bracketed_paste=bool(value);

    @property
    def keyboard_flags(self):
        return self.modes.keyboard_flags;

    @keyboard_flags.setter
    def keyboard_flags(self,value):
        self.modes.keyboard_flags=int(value or 0);

    @property
    def insert_mode(self):
        return self.modes.insert_mode;

    @insert_mode.setter
    def insert_mode(self,value):
        self.modes.insert_mode=bool(value);

    @property
    def origin_mode(self):
        return self.modes.origin_mode;

    @origin_mode.setter
    def origin_mode(self,value):
        self.modes.origin_mode=bool(value);

    @property
    def autowrap(self):
        return self.modes.autowrap;

    @autowrap.setter
    def autowrap(self,value):
        self.modes.autowrap=bool(value);

    @property
    def cursor_visible(self):
        return self.modes.cursor_visible;

    @cursor_visible.setter
    def cursor_visible(self,value):
        self.modes.cursor_visible=bool(value);

    def resize(self,rows,columns):
        rows=max(1,int(rows)); columns=max(1,int(columns));
        if columns!=self.columns:
            for line in self.lines:
                if len(line)<columns: line.extend(self._blank_cell() for _ in range(columns-len(line)));
                elif len(line)>columns: del line[columns:];
            self.columns=columns;
        if rows>self.rows: self.lines.extend(self._blank_line() for _ in range(rows-self.rows));
        elif rows<self.rows:
            removed=self.lines[:self.rows-rows];
            if not self._alternate: self._push_scrollback(removed);
            self.lines=self.lines[self.rows-rows:];
        self.rows=rows; self.row=max(0,min(self.row,self.rows-1)); self.col=max(0,min(self.col,self.columns-1)); self.scroll_top=0; self.scroll_bottom=self.rows-1;

    def _push_scrollback(self,lines):
        if self.scrollback_limit<=0: return;
        self.scrollback.extend([[cell.copy() for cell in line] for line in lines]);
        if len(self.scrollback)>self.scrollback_limit: del self.scrollback[:len(self.scrollback)-self.scrollback_limit];

    def _scroll_up(self,count=1):
        count=max(1,int(count));
        for _ in range(count):
            removed=self.lines.pop(self.scroll_top);
            if self.scroll_top==0 and self.scroll_bottom==self.rows-1 and not self._alternate: self._push_scrollback([removed]);
            self.lines.insert(self.scroll_bottom,self._blank_line());

    def _scroll_down(self,count=1):
        for _ in range(max(1,int(count))): self.lines.pop(self.scroll_bottom); self.lines.insert(self.scroll_top,self._blank_line());

    def _insert_lines(self,count=1):
        count=max(1,int(count));
        if not self.scroll_top<=self.row<=self.scroll_bottom: return;
        for _ in range(count):
            self.lines.insert(self.row,self._blank_line()); self.lines.pop(self.scroll_bottom+1);

    def _delete_lines(self,count=1):
        count=max(1,int(count));
        if not self.scroll_top<=self.row<=self.scroll_bottom: return;
        for _ in range(count):
            self.lines.pop(self.row); self.lines.insert(self.scroll_bottom,self._blank_line());

    def _linefeed(self):
        if self.row==self.scroll_bottom: self._scroll_up(1);
        else: self.row=min(self.rows-1,self.row+1);

    def _put(self,char):
        if self.col>=self.columns:
            if not self.autowrap: self.col=self.columns-1;
            else: self.col=0; self._linefeed();
        if self.insert_mode:
            line=self.lines[self.row]; line.insert(self.col,self._blank_cell()); del line[-1];
        self.lines[self.row][self.col]=Cell(char,self.fg,self.bg,self.bold,self.underline,self.inverse); self.col+=1;
        if self.col>=self.columns: self.col=self.columns;

    def _erase_line(self,mode):
        if mode==0: start,end=self.col,self.columns;
        elif mode==1: start,end=0,min(self.columns,self.col+1);
        else: start,end=0,self.columns;
        for index in range(start,end): self.lines[self.row][index]=self._blank_cell();

    def _erase_display(self,mode):
        if mode==2 or mode==3:
            for row in range(self.rows): self.lines[row]=self._blank_line();
            if mode==3: self.scrollback=[];
            return;
        if mode==0:
            self._erase_line(0);
            for row in range(self.row+1,self.rows): self.lines[row]=self._blank_line();
        elif mode==1:
            self._erase_line(1);
            for row in range(0,self.row): self.lines[row]=self._blank_line();

    def _params(self,text,default=0):
        if not text: return [default];
        values=[];
        for item in text.split(";"):
            try: values.append(int(item) if item else default);
            except ValueError: values.append(default);
        return values;

    def _sgr(self,params):
        if not params: params=[0];
        index=0;
        while index<len(params):
            code=params[index];
            if code==0: self.fg=self.default_fg; self.bg=self.default_bg; self.bold=False; self.underline=False; self.inverse=False;
            elif code==1: self.bold=True;
            elif code==4: self.underline=True;
            elif code==7: self.inverse=True;
            elif code==22: self.bold=False;
            elif code==24: self.underline=False;
            elif code==27: self.inverse=False;
            elif 30<=code<=37: self.fg=self.ansi16[code-30];
            elif 90<=code<=97: self.fg=self.ansi16[8+code-90];
            elif 40<=code<=47: self.bg=self.ansi16[code-40];
            elif 100<=code<=107: self.bg=self.ansi16[8+code-100];
            elif code==39: self.fg=self.default_fg;
            elif code==49: self.bg=self.default_bg;
            elif code in (38,48):
                target="fg" if code==38 else "bg";
                if index+2<len(params) and params[index+1]==5:
                    setattr(self,target,_xterm_color(params[index+2],self.ansi16)); index+=2;
                elif index+4<len(params) and params[index+1]==2:
                    rgb=tuple(max(0,min(255,int(value))) for value in params[index+2:index+5]); setattr(self,target,rgb); index+=4;
            index+=1;

    def _set_keyboard_flags(self,value):
        value=max(0,int(value)); self._keyboard_flags_by_screen[bool(self._alternate)]=value; self.keyboard_flags=value;

    def _alternate_mode(self,enabled):
        if enabled and not self._alternate:
            self._keyboard_flags_by_screen[False]=self.keyboard_flags;
            self._saved_primary=([[cell.copy() for cell in line] for line in self.lines],self.row,self.col,self.saved,self.scroll_top,self.scroll_bottom);
            self._alternate=True; self.modes.alternate_screen=True; self.lines=[self._blank_line() for _ in range(self.rows)]; self.row=0; self.col=0; self.scroll_top=0; self.scroll_bottom=self.rows-1; self.keyboard_flags=self._keyboard_flags_by_screen[True];
        elif not enabled and self._alternate:
            self._keyboard_flags_by_screen[True]=self.keyboard_flags;
            if self._saved_primary is not None: self.lines,self.row,self.col,self.saved,self.scroll_top,self.scroll_bottom=self._saved_primary;
            self._saved_primary=None; self._alternate=False; self.modes.alternate_screen=False; self.keyboard_flags=self._keyboard_flags_by_screen[False];

    def _handle_csi(self,sequence):
        if not sequence: return;
        final=sequence[-1]; body=sequence[:-1]; private=body.startswith("?"); greater=body.startswith(">"); equal=body.startswith("="); less=body.startswith("<");
        if private or greater or equal or less: body=body[1:];
        params=self._params(body,0);
        first=params[0] if params else 0;
        if final in ("H","f"):
            row=params[0] if len(params)>0 and params[0] else 1; col=params[1] if len(params)>1 and params[1] else 1; base=self.scroll_top if self.origin_mode else 0; limit=self.scroll_bottom if self.origin_mode else self.rows-1; self.row=max(base,min(limit,base+row-1)); self.col=max(0,min(self.columns-1,col-1));
        elif final=="A": self.row=max(self.scroll_top,self.row-max(1,first));
        elif final=="B": self.row=min(self.scroll_bottom,self.row+max(1,first));
        elif final=="C": self.col=min(self.columns-1,self.col+max(1,first));
        elif final=="D": self.col=max(0,self.col-max(1,first));
        elif final=="E": self.row=min(self.scroll_bottom,self.row+max(1,first)); self.col=0;
        elif final=="F": self.row=max(self.scroll_top,self.row-max(1,first)); self.col=0;
        elif final=="G": self.col=max(0,min(self.columns-1,max(1,first)-1));
        elif final=="d": self.row=max(0,min(self.rows-1,max(1,first)-1));
        elif final=="J": self._erase_display(first);
        elif final=="K": self._erase_line(first);
        elif final=="m": self._sgr(params);
        elif final=="s": self.saved=(self.row,self.col);
        elif final=="u" and private:
            self.pending_replies.append("\x1b[?{}u".format(self.keyboard_flags).encode("ascii"));
        elif final=="u" and greater:
            stack=self._keyboard_stacks[bool(self._alternate)]; stack.append(self.keyboard_flags);
            if len(stack)>32: del stack[0];
        elif final=="u" and equal:
            flags=max(0,int(first)); mode=params[1] if len(params)>1 and params[1] else 1;
            if mode==2: flags=self.keyboard_flags|flags;
            elif mode==3: flags=self.keyboard_flags & ~flags;
            self._set_keyboard_flags(flags);
        elif final=="u" and less:
            count=max(1,int(first or 1)); stack=self._keyboard_stacks[bool(self._alternate)]; value=self.keyboard_flags;
            for _ in range(count): value=stack.pop() if stack else 0;
            self._set_keyboard_flags(value);
        elif final=="u": self.row,self.col=self.saved;
        elif final=="r":
            top=(params[0] if len(params)>0 and params[0] else 1)-1; bottom=(params[1] if len(params)>1 and params[1] else self.rows)-1; self.scroll_top=max(0,min(self.rows-1,top)); self.scroll_bottom=max(self.scroll_top,min(self.rows-1,bottom)); self.row=self.scroll_top; self.col=0;
        elif final=="S": self._scroll_up(max(1,first));
        elif final=="T": self._scroll_down(max(1,first));
        elif final=="P":
            count=max(1,first); line=self.lines[self.row]; del line[self.col:self.col+count]; line.extend(self._blank_cell() for _ in range(count));
        elif final=="@":
            count=max(1,first); line=self.lines[self.row]; line[self.col:self.col]=[self._blank_cell() for _ in range(count)]; del line[self.columns:];
        elif final=="L": self._insert_lines(max(1,first));
        elif final=="M": self._delete_lines(max(1,first));
        elif final=="X":
            for index in range(self.col,min(self.columns,self.col+max(1,first))): self.lines[self.row][index]=self._blank_cell();
        elif final=="n":
            if first==5: self.pending_replies.append(b"\x1b[0n");
            elif first==6: self.pending_replies.append("\x1b[{};{}R".format(self.row+1,self.col+1).encode("ascii"));
        elif final=="c":
            if private: self.pending_replies.append(b"\x1b[?1;2c");
            else: self.pending_replies.append(b"\x1b[?1;2c");
        elif final in ("h","l") and not private:
            enabled=final=="h";
            for mode in params:
                if mode==4: self.insert_mode=enabled;
        elif final in ("h","l") and private:
            enabled=final=="h";
            for mode in params:
                if mode==1: self.application_cursor_keys=enabled;
                elif mode==6: self.origin_mode=enabled; self.row=self.scroll_top if enabled else 0; self.col=0;
                elif mode==7: self.autowrap=enabled;
                elif mode==25: self.cursor_visible=enabled;
                elif mode in (47,1047,1049): self._alternate_mode(enabled);
                elif mode in (1000,1002,1003): self.mouse_tracking=mode if enabled else (0 if self.mouse_tracking==mode else self.mouse_tracking);
                elif mode==1006: self.mouse_sgr=enabled;
                elif mode==2004: self.bracketed_paste=enabled;

    def _handle_osc(self,text):
        if ";" not in text: return;
        code,value=text.split(";",1);
        if code in ("0","2") and value: self.title=value;

    def feed(self,text):
        for char in str(text or ""):
            if self._state=="normal":
                if char=="\x1b": self._state="esc";
                elif char=="\r": self.col=0;
                elif char=="\n": self._linefeed();
                elif char=="\b": self.col=max(0,self.col-1);
                elif char=="\t": self.col=min(self.columns-1,((self.col//8)+1)*8);
                elif char=="\x07": pass;
                elif ord(char)>=32: self._put(char);
            elif self._state=="esc":
                if char=="[": self._state="csi"; self._buffer="";
                elif char=="]": self._state="osc"; self._buffer="";
                elif char=="7": self.saved=(self.row,self.col); self._state="normal";
                elif char=="8": self.row,self.col=self.saved; self._state="normal";
                elif char=="c": self.reset();
                elif char=="=": self.application_keypad=True; self._state="normal";
                elif char==">": self.application_keypad=False; self._state="normal";
                elif char=="D": self._linefeed(); self._state="normal";
                elif char=="E": self._linefeed(); self.col=0; self._state="normal";
                elif char=="M":
                    if self.row==self.scroll_top: self._scroll_down(1);
                    else: self.row=max(0,self.row-1);
                    self._state="normal";
                elif char in ("(",")","*","+"): self._state="charset";
                else: self._state="normal";
            elif self._state=="csi":
                self._buffer+=char;
                if "@"<=char<="~": self._handle_csi(self._buffer); self._buffer=""; self._state="normal";
            elif self._state=="osc":
                if char=="\x07": self._handle_osc(self._buffer); self._buffer=""; self._state="normal";
                elif char=="\x1b": self._state="osc_esc";
                else: self._buffer+=char;
            elif self._state=="osc_esc":
                if char=="\\": self._handle_osc(self._buffer); self._buffer=""; self._state="normal";
                else: self._buffer+="\x1b"+char; self._state="osc";
            elif self._state=="charset": self._state="normal";
        return self;

    def text_lines(self):
        return ["".join(cell.char for cell in line).rstrip() for line in self.lines];
