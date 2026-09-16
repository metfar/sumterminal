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
import select;
import shutil;
import subprocess;
import sys;
import time;

from .config import load_preferences;
from .ipc import DropdownIPCServer;
from .screen import TerminalScreen;


class GuiTerminalView:
    """SUM-owned graphical terminal view over the presentation-neutral TerminalSession.""";

    def __init__(self,session,preferences=None,drop_down=False,start_hidden=False):
        self.session=session; self.preferences=(preferences or load_preferences()).normalized(); self.drop_down=bool(drop_down); self.start_hidden=bool(start_hidden); self.visible=not self.start_hidden; self.running=False; self.screen_model=TerminalScreen(session.size.rows,session.size.columns); self.ipc=DropdownIPCServer() if self.drop_down else None; self._last_title="";

    @staticmethod
    def available():
        try:
            import pygame;
            import sumgui;
            return True;
        except ImportError: return False;

    def _geometry(self,pygame):
        sizes=getattr(pygame.display,"get_desktop_sizes",lambda:[])();
        desktop=sizes[0] if sizes else (1280,800); dw=max(320,int(desktop[0])); dh=max(240,int(desktop[1]));
        if self.drop_down:
            width=max(320,int(round(dw*self.preferences.dropdown.width/100.0))); height=max(180,int(round(dh*self.preferences.dropdown.height/100.0))); x=max(0,(dw-width)//2); y=0 if self.preferences.dropdown.position=="top" else max(0,dh-height); return width,height,x,y;
        width=min(1100,max(720,int(dw*0.72))); height=min(760,max(480,int(dh*0.72))); return width,height,max(0,(dw-width)//2),max(0,(dh-height)//3);

    def _sdl_window(self):
        try:
            from pygame._sdl2 import Window;
            return Window.from_display_module();
        except Exception: return None;

    def _apply_window_properties(self,pygame):
        width,height,x,y=self._geometry(pygame); window=self._sdl_window();
        if window is not None:
            try: window.position=(x,y);
            except Exception: pass;
            if self.drop_down:
                try: window.always_on_top=True;
                except Exception: pass;
            try: window.opacity=float(self.preferences.dropdown.opacity if self.drop_down else 1.0);
            except Exception: pass;
        return width,height;

    def _set_visible(self,value):
        self.visible=bool(value); window=self._sdl_window();
        if window is not None:
            try:
                if self.visible:
                    window.show();
                    try: window.focus();
                    except Exception: pass;
                else: window.hide();
                return;
            except Exception: pass;
        if not self.visible:
            try:
                import pygame;
                pygame.display.iconify();
            except Exception: pass;

    def toggle_visible(self):
        self._set_visible(not self.visible);

    def _reload_preferences(self,pygame):
        self.preferences=load_preferences().normalized(); width,height,x,y=self._geometry(pygame); window=self._sdl_window();
        if window is not None:
            try: window.size=(width,height); window.position=(x,y); window.opacity=float(self.preferences.dropdown.opacity if self.drop_down else 1.0);
            except Exception: pass;

    def _open_preferences(self):
        executable=shutil.which("sumterminal");
        command=[executable,"--preferences"] if executable else [sys.executable,"-m","sumterminal","--preferences"];
        subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True);

    def _key_bytes(self,pygame,event):
        key=event.key; mod=event.mod;
        if (mod & pygame.KMOD_CTRL) and key==pygame.K_F12 and self.drop_down: self.toggle_visible(); return b"";
        if (mod & pygame.KMOD_CTRL) and key==pygame.K_COMMA: self._open_preferences(); return b"";
        special={pygame.K_RETURN:b"\r",pygame.K_KP_ENTER:b"\r",pygame.K_BACKSPACE:b"\x7f",pygame.K_TAB:b"\t",pygame.K_ESCAPE:b"\x1b",pygame.K_UP:b"\x1b[A",pygame.K_DOWN:b"\x1b[B",pygame.K_RIGHT:b"\x1b[C",pygame.K_LEFT:b"\x1b[D",pygame.K_HOME:b"\x1b[H",pygame.K_END:b"\x1b[F",pygame.K_PAGEUP:b"\x1b[5~",pygame.K_PAGEDOWN:b"\x1b[6~",pygame.K_INSERT:b"\x1b[2~",pygame.K_DELETE:b"\x1b[3~",pygame.K_F1:b"\x1bOP",pygame.K_F2:b"\x1bOQ",pygame.K_F3:b"\x1bOR",pygame.K_F4:b"\x1bOS",pygame.K_F5:b"\x1b[15~",pygame.K_F6:b"\x1b[17~",pygame.K_F7:b"\x1b[18~",pygame.K_F8:b"\x1b[19~",pygame.K_F9:b"\x1b[20~",pygame.K_F10:b"\x1b[21~",pygame.K_F11:b"\x1b[23~",pygame.K_F12:b"\x1b[24~"};
        if key in special:
            data=special[key]; return b"\x1b"+data if (mod & pygame.KMOD_ALT) and data!=b"\x1b" else data;
        if mod & pygame.KMOD_CTRL:
            name=pygame.key.name(key);
            if len(name)==1 and "a"<=name.casefold()<="z": return bytes([ord(name.casefold())-96]);
            if key==pygame.K_SPACE: return b"\x00";
        return b"";

    def _update_size(self,pygame,font,header_height):
        surface=pygame.display.get_surface(); width,height=surface.get_size(); cell_w=max(1,font.size("M")[0]); cell_h=max(1,font.get_linesize()); columns=max(1,width//cell_w); rows=max(1,(height-header_height)//cell_h);
        if rows!=self.screen_model.rows or columns!=self.screen_model.columns:
            self.screen_model.resize(rows,columns); self.session.resize(rows,columns);
        return cell_w,cell_h;

    def _draw_header(self,pygame,surface,font,theme,height):
        pygame.draw.rect(surface,theme.panel,(0,0,surface.get_width(),height)); pygame.draw.line(surface,theme.line,(0,height-1),(surface.get_width(),height-1),1);
        title="SUM Terminal" + (" — drop-down" if self.drop_down else ""); text=font.render(title,True,theme.text); surface.blit(text,(10,max(2,(height-text.get_height())//2)));
        pref="Preferences"; pref_text=font.render(pref,True,theme.text); pref_rect=pref_text.get_rect(); pref_rect.right=surface.get_width()-12; pref_rect.centery=height//2; surface.blit(pref_text,pref_rect); self._preferences_rect=pref_rect.inflate(16,8);
        if self.drop_down:
            hint=font.render("Ctrl+F12 hide/show",True,theme.muted); hint_rect=hint.get_rect(); hint_rect.right=self._preferences_rect.left-14; hint_rect.centery=height//2; surface.blit(hint,hint_rect);

    def _draw_screen(self,pygame,surface,font,theme,header_height,cell_w,cell_h):
        y0=header_height;
        for row,line in enumerate(self.screen_model.lines):
            x=0; index=0;
            while index<len(line):
                cell=line[index]; fg,bg=(cell.bg,cell.fg) if cell.inverse else (cell.fg,cell.bg); bold=cell.bold; underline=cell.underline; chars=[cell.char]; end=index+1;
                while end<len(line):
                    other=line[end]; ofg,obg=(other.bg,other.fg) if other.inverse else (other.fg,other.bg);
                    if (ofg,obg,other.bold,other.underline)!=(fg,bg,bold,underline): break;
                    chars.append(other.char); end+=1;
                text="".join(chars); width=(end-index)*cell_w;
                if bg!=self.screen_model.default_bg: pygame.draw.rect(surface,bg,(x,y0+row*cell_h,width,cell_h));
                rendered=font.render(text,True,fg); surface.blit(rendered,(x,y0+row*cell_h));
                if underline: pygame.draw.line(surface,fg,(x,y0+(row+1)*cell_h-2),(x+width,y0+(row+1)*cell_h-2),1);
                x+=width; index=end;
        if self.screen_model.cursor_visible and 0<=self.screen_model.row<self.screen_model.rows:
            col=min(self.screen_model.columns-1,max(0,self.screen_model.col)); x=col*cell_w; y=y0+self.screen_model.row*cell_h; pygame.draw.rect(surface,theme.cursor,(x,y,cell_w,cell_h),2);

    def run(self):
        try:
            import pygame;
            from sumgui.display import set_default_icon;
            from sumgui.theme import make_theme;
        except ImportError as exc: raise RuntimeError("sumTerminal GUI requires sumGUI/Pygame") from exc;
        if self.session.state.value=="created": self.session.start();
        pygame.init(); pygame.key.set_repeat(400,35); width,height,x,y=self._geometry(pygame); os.environ.setdefault("SDL_VIDEO_WINDOW_POS","{},{}".format(x,y)); flags=pygame.RESIZABLE | (pygame.NOFRAME if self.drop_down else 0); pygame.display.set_mode((width,height),flags); set_default_icon(); self._apply_window_properties(pygame);
        theme=make_theme(self.preferences.general.theme); font=pygame.font.SysFont(self.preferences.general.font_name,self.preferences.general.font_size); header_font=pygame.font.SysFont(self.preferences.general.font_name,max(12,self.preferences.general.font_size-2)); header_height=max(28,header_font.get_linesize()+8); self._preferences_rect=pygame.Rect(0,0,0,0); self._update_size(pygame,font,header_height);
        if self.ipc is not None: self.ipc.start();
        if self.start_hidden: self._set_visible(False);
        clock=pygame.time.Clock(); self.running=True; exit_code=0; pty_eof=False;
        try:
            while self.running:
                clock.tick(60);
                if self.ipc is not None:
                    for command in self.ipc.pending():
                        if command=="toggle": self.toggle_visible();
                        elif command=="show": self._set_visible(True);
                        elif command=="hide": self._set_visible(False);
                        elif command=="reload": self._reload_preferences(pygame);
                        elif command=="quit": self.running=False;
                for event in pygame.event.get():
                    if event.type==pygame.QUIT: self.running=False;
                    elif event.type==pygame.VIDEORESIZE: self._update_size(pygame,font,header_height);
                    elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1 and self._preferences_rect.collidepoint(event.pos): self._open_preferences();
                    elif event.type==pygame.KEYDOWN:
                        data=self._key_bytes(pygame,event);
                        if data: self.session.write(data);
                    elif event.type==pygame.TEXTINPUT:
                        if event.text: self.session.write(event.text.encode("utf-8"));
                    elif self.drop_down and self.preferences.dropdown.hide_on_focus_loss and event.type==getattr(pygame,"WINDOWFOCUSLOST",-999): self._set_visible(False);
                try: ready,_,_=select.select([self.session.fileno],[],[],0);
                except (OSError,ValueError): ready=[];
                if ready:
                    event=self.session.read_event(65536);
                    if event is not None:
                        if event.kind=="output": self.screen_model.feed(event.text);
                        elif event.kind=="eof": pty_eof=True;
                        elif event.kind=="exit": exit_code=int(event.exit_code or 0);
                code=self.session.poll();
                if code is not None:
                    exit_code=int(code);
                    if pty_eof or not ready: self.running=False;
                if self.screen_model.title!=self._last_title:
                    pygame.display.set_caption(self.screen_model.title or "SUM Terminal"); self._last_title=self.screen_model.title;
                if self.visible:
                    surface=pygame.display.get_surface(); surface.fill(theme.bg); cell_w,cell_h=self._update_size(pygame,font,header_height); self._draw_header(pygame,surface,header_font,theme,header_height); self._draw_screen(pygame,surface,font,theme,header_height,cell_w,cell_h); pygame.display.flip();
        finally:
            if self.ipc is not None: self.ipc.close();
            if self.session.poll() is None: self.session.terminate();
            try: self.session.wait(timeout=1.0);
            except Exception: pass;
            self.session.close(); pygame.quit();
        return exit_code;
