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


_ANSI16=((0,0,0),(205,0,0),(0,205,0),(205,205,0),(0,0,238),(205,0,205),(0,205,205),(229,229,229),(127,127,127),(255,0,0),(0,255,0),(255,255,0),(92,92,255),(255,0,255),(0,255,255),(255,255,255));


def _xterm_color(index):
    index=max(0,min(255,int(index)));
    if index<16: return _ANSI16[index];
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
        self.ansi16=_ANSI16; self.rows=max(1,int(rows)); self.columns=max(1,int(columns)); self.scrollback_limit=max(0,int(scrollback));
        self.default_fg=_ANSI16[7]; self.default_bg=_ANSI16[0]; self.scrollback=[]; self.title="SUM Terminal";
        self._alternate=False; self._saved_primary=None; self.reset();

    def _blank_cell(self):
        return Cell(" ",self.default_fg,self.default_bg,False,False,False);

    def _blank_line(self):
        return [self._blank_cell() for _ in range(self.columns)];

    def reset(self):
        self.lines=[self._blank_line() for _ in range(self.rows)]; self.row=0; self.col=0; self.saved=(0,0); self.scroll_top=0; self.scroll_bottom=self.rows-1; self.cursor_visible=True;
        self.fg=self.default_fg; self.bg=self.default_bg; self.bold=False; self.underline=False; self.inverse=False; self._state="normal"; self._buffer="";

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

    def _linefeed(self):
        if self.row==self.scroll_bottom: self._scroll_up(1);
        else: self.row=min(self.rows-1,self.row+1);

    def _put(self,char):
        if self.col>=self.columns:
            self.col=0; self._linefeed();
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
            elif 30<=code<=37: self.fg=_ANSI16[code-30];
            elif 90<=code<=97: self.fg=_ANSI16[8+code-90];
            elif 40<=code<=47: self.bg=_ANSI16[code-40];
            elif 100<=code<=107: self.bg=_ANSI16[8+code-100];
            elif code==39: self.fg=self.default_fg;
            elif code==49: self.bg=self.default_bg;
            elif code in (38,48):
                target="fg" if code==38 else "bg";
                if index+2<len(params) and params[index+1]==5:
                    setattr(self,target,_xterm_color(params[index+2])); index+=2;
                elif index+4<len(params) and params[index+1]==2:
                    rgb=tuple(max(0,min(255,int(value))) for value in params[index+2:index+5]); setattr(self,target,rgb); index+=4;
            index+=1;

    def _alternate_mode(self,enabled):
        if enabled and not self._alternate:
            self._saved_primary=([[cell.copy() for cell in line] for line in self.lines],self.row,self.col,self.saved,self.scroll_top,self.scroll_bottom);
            self._alternate=True; self.lines=[self._blank_line() for _ in range(self.rows)]; self.row=0; self.col=0; self.scroll_top=0; self.scroll_bottom=self.rows-1;
        elif not enabled and self._alternate:
            if self._saved_primary is not None: self.lines,self.row,self.col,self.saved,self.scroll_top,self.scroll_bottom=self._saved_primary;
            self._saved_primary=None; self._alternate=False;

    def _handle_csi(self,sequence):
        if not sequence: return;
        final=sequence[-1]; body=sequence[:-1]; private=body.startswith("?");
        if private: body=body[1:];
        params=self._params(body,0);
        first=params[0] if params else 0;
        if final in ("H","f"):
            row=params[0] if len(params)>0 and params[0] else 1; col=params[1] if len(params)>1 and params[1] else 1; self.row=max(0,min(self.rows-1,row-1)); self.col=max(0,min(self.columns-1,col-1));
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
        elif final=="u": self.row,self.col=self.saved;
        elif final=="r":
            top=(params[0] if len(params)>0 and params[0] else 1)-1; bottom=(params[1] if len(params)>1 and params[1] else self.rows)-1; self.scroll_top=max(0,min(self.rows-1,top)); self.scroll_bottom=max(self.scroll_top,min(self.rows-1,bottom)); self.row=self.scroll_top; self.col=0;
        elif final=="S": self._scroll_up(max(1,first));
        elif final=="T": self._scroll_down(max(1,first));
        elif final=="P":
            count=max(1,first); line=self.lines[self.row]; del line[self.col:self.col+count]; line.extend(self._blank_cell() for _ in range(count));
        elif final=="X":
            for index in range(self.col,min(self.columns,self.col+max(1,first))): self.lines[self.row][index]=self._blank_cell();
        elif final in ("h","l") and private:
            enabled=final=="h";
            for mode in params:
                if mode==25: self.cursor_visible=enabled;
                elif mode in (47,1047,1049): self._alternate_mode(enabled);

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
        return self;

    def text_lines(self):
        return ["".join(cell.char for cell in line).rstrip() for line in self.lines];
