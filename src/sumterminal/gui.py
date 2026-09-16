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
import shlex;
import shutil;
import subprocess;
import sys;
import threading;
import warnings;

from .config import load_preferences;
from .ipc import DropdownIPCServer;
from .model import TerminalSize;
from .screen import TerminalScreen;
from .session import TerminalSession;
from .theme import gui_theme, resolve_theme, terminal_ansi16, terminal_colors;


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT","1");


def _prepare_pygame_runtime():
    warnings.filterwarnings("ignore",message=r"Your system is avx2 capable.*",category=RuntimeWarning);
    warnings.filterwarnings("ignore",message=r"pkg_resources is deprecated as an API.*",category=UserWarning);


def _display_fg(screen,color,bold):
    value=tuple(color);
    if bold:
        try:
            index=screen.ansi16.index(value);
            if 0<=index<8: return screen.ansi16[index+8];
        except ValueError: pass;
    return value;


class _TerminalTab:
    def __init__(self,session):
        self.session=session;
        self.screen=TerminalScreen(session.size.rows,session.size.columns);
        self.eof=False;
        self.exit_code=None;


class GuiTerminalView:
    """SUM-owned graphical terminal view over one or more TerminalSession objects.""";

    def __init__(self,session,preferences=None,drop_down=False,start_hidden=False):
        self.preferences=(preferences or load_preferences()).normalized();
        self.drop_down=bool(drop_down);
        self.start_hidden=bool(start_hidden);
        self.visible=not self.start_hidden;
        self.running=False;
        self._tabs=[_TerminalTab(session)];
        self._active_index=0;
        self.ipc=DropdownIPCServer() if self.drop_down else None;
        self._last_title="";
        self.font=None;
        self.bold_font=None;
        self.header_font=None;
        self.toolbar_height=28;
        self.tabbar_height=30;
        self.header_height=58;
        self.cell_width=8;
        self.cell_height=16;
        self.glyph_height=16;
        self.glyph_offset_y=0;
        self.effective_font_name=self.preferences.general.font_name;
        self._flags=0;
        self._preferences_process=None;
        self._preferences_finished=False;
        self._preferences_reload_pending=False;
        self._preferences_rect=None;
        self._new_tab_rect=None;
        self._tab_rects=[];
        self._tab_close_rects=[];
        self.sum_theme=resolve_theme(self.preferences.general.theme);
        self.theme=None;
        self._apply_theme_to_screens();

    def _apply_theme_to_screens(self):
        foreground,background,_cursor,_selection_bg,_selection_text=terminal_colors(self.sum_theme);
        palette=terminal_ansi16(self.sum_theme);
        for tab in self._tabs: tab.screen.set_palette(palette,default_fg=foreground,default_bg=background,remap=True);
        return self.theme;

    def _reload_theme(self,include_gui=True):
        self.sum_theme=resolve_theme(self.preferences.general.theme);
        if include_gui: self.theme=gui_theme(self.sum_theme);
        self._apply_theme_to_screens();
        return self.theme;

    @property
    def active_tab(self):
        return self._tabs[self._active_index];

    @property
    def session(self):
        return self.active_tab.session;

    @property
    def screen_model(self):
        return self.active_tab.screen;

    @property
    def tab_count(self):
        return len(self._tabs);

    @staticmethod
    def available():
        try:
            _prepare_pygame_runtime();
            import pygame;
            import sumgui;
            return True;
        except ImportError: return False;

    def _preferred_shell_command(self):
        text=str(self.preferences.general.shell or "sumbash").strip();
        if not text or text.casefold()=="sumbash": return None;
        command=shlex.split(text);
        return command or None;

    def _new_tab(self):
        source=self.active_tab;
        try:
            command=self._preferred_shell_command();
            session=TerminalSession(command=command,cwd=source.session.logical_cwd,rows=source.screen.rows,columns=source.screen.columns).start();
        except (OSError,RuntimeError,ValueError) as exc:
            source.screen.feed("\r\nsumterminal: could not open new tab: {}\r\n".format(exc));
            return None;
        self._tabs.append(_TerminalTab(session));
        foreground,background,_cursor,_selection_bg,_selection_text=terminal_colors(self.sum_theme); self._tabs[-1].screen.set_palette(terminal_ansi16(self.sum_theme),default_fg=foreground,default_bg=background,remap=False);
        self._active_index=len(self._tabs)-1;
        self._last_title="";
        return self.active_tab;

    def _close_tab(self,index=None):
        if not self._tabs: return;
        value=self._active_index if index is None else max(0,min(len(self._tabs)-1,int(index)));
        if len(self._tabs)==1:
            self.running=False;
            return;
        tab=self._tabs.pop(value);
        if tab.session.poll() is None: tab.session.terminate();
        try: tab.session.wait(timeout=0.25);
        except Exception: pass;
        tab.session.close();
        if self._active_index>value: self._active_index-=1;
        elif self._active_index>=len(self._tabs): self._active_index=len(self._tabs)-1;
        self._last_title="";

    def _switch_tab(self,index):
        if not self._tabs: return;
        value=max(0,min(len(self._tabs)-1,int(index)));
        if value!=self._active_index:
            self._active_index=value;
            self._last_title="";

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

    def _make_fonts(self,pygame):
        name=self.preferences.general.font_name; size=self.preferences.general.font_size;
        def make_font(font_name,font_size,bold=False):
            path=None;
            try:
                if os.path.isfile(str(font_name)): path=str(font_name);
                else: path=pygame.font.match_font(str(font_name),bold=bold);
            except Exception: path=None;
            return pygame.font.Font(path,font_size) if path else pygame.font.SysFont(str(font_name),font_size,bold=bold);
        self.font=make_font(name,size,False);
        widths=[self.font.size(char)[0] for char in "iMW0@"];
        if max(widths)-min(widths)>1:
            self.effective_font_name="monospace";
            self.font=make_font("monospace",size,False);
            self.bold_font=make_font("monospace",size,True);
        else:
            self.effective_font_name=name;
            self.bold_font=make_font(name,size,True);
        self.header_font=pygame.font.SysFont("sans",max(12,min(18,size-2)));
        self.toolbar_height=max(28,self.header_font.get_linesize()+8);
        self.tabbar_height=max(28,self.header_font.get_linesize()+8);
        self.header_height=self.toolbar_height+self.tabbar_height;
        self.cell_width=max(1,self.font.size("M")[0]);
        self.cell_height=max(1,self.font.get_linesize());
        self.glyph_height=max(1,self.font.get_height());
        self.glyph_offset_y=max(0,(self.cell_height-self.glyph_height)//2);
        return self.font;

    def _reload_preferences(self,pygame):
        previous=self.preferences; surface=pygame.display.get_surface(); previous_size=surface.get_size() if surface is not None else None;
        self.preferences=load_preferences().normalized(); self._reload_theme(); self._make_fonts(pygame); width,height,_,_=self._geometry(pygame); target_size=(width,height);
        geometry_changed=previous_size!=target_size; opacity_changed=float(previous.dropdown.opacity)!=float(self.preferences.dropdown.opacity); position_changed=str(previous.dropdown.position)!=str(self.preferences.dropdown.position);
        if geometry_changed: pygame.display.set_mode(target_size,self._flags);
        if geometry_changed or opacity_changed or position_changed: self._apply_window_properties(pygame);
        self._update_size(pygame,self.font,self.header_height);

    def _open_preferences(self):
        if self._preferences_process is not None and self._preferences_process.poll() is None: return;
        executable=shutil.which("sumterminal");
        command=[executable,"--preferences"] if executable else [sys.executable,"-m","sumterminal","--preferences"];
        self._preferences_reload_pending=False;
        if self.drop_down: self._set_visible(False);
        try: self._preferences_process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True);
        except OSError:
            self._set_visible(True); raise;
        def wait_preferences():
            try: self._preferences_process.wait();
            except Exception: pass;
            self._preferences_finished=True;
        threading.Thread(target=wait_preferences,name="sumterminal-preferences",daemon=True).start();

    def _key_bytes(self,pygame,event):
        key=event.key; mod=event.mod;
        if (mod & pygame.KMOD_CTRL) and key==pygame.K_F12 and self.drop_down: self.toggle_visible(); return b"";
        if (mod & pygame.KMOD_CTRL) and key==pygame.K_COMMA: self._open_preferences(); return b"";
        if (mod & pygame.KMOD_CTRL) and (mod & pygame.KMOD_SHIFT) and key==pygame.K_t: self._new_tab(); return b"";
        special={pygame.K_RETURN:b"\r",pygame.K_KP_ENTER:b"\r",pygame.K_BACKSPACE:b"\x7f",pygame.K_TAB:b"\t",pygame.K_ESCAPE:b"\x1b",pygame.K_UP:b"\x1b[A",pygame.K_DOWN:b"\x1b[B",pygame.K_RIGHT:b"\x1b[C",pygame.K_LEFT:b"\x1b[D",pygame.K_HOME:b"\x1b[H",pygame.K_END:b"\x1b[F",pygame.K_PAGEUP:b"\x1b[5~",pygame.K_PAGEDOWN:b"\x1b[6~",pygame.K_INSERT:b"\x1b[2~",pygame.K_DELETE:b"\x1b[3~",pygame.K_F1:b"\x1bOP",pygame.K_F2:b"\x1bOQ",pygame.K_F3:b"\x1bOR",pygame.K_F4:b"\x1bOS",pygame.K_F5:b"\x1b[15~",pygame.K_F6:b"\x1b[17~",pygame.K_F7:b"\x1b[18~",pygame.K_F8:b"\x1b[19~",pygame.K_F9:b"\x1b[20~",pygame.K_F10:b"\x1b[21~",pygame.K_F11:b"\x1b[23~",pygame.K_F12:b"\x1b[24~"};
        if key in special:
            data=special[key]; return b"\x1b"+data if (mod & pygame.KMOD_ALT) and data!=b"\x1b" else data;
        if mod & pygame.KMOD_CTRL:
            name=pygame.key.name(key);
            if len(name)==1 and "a"<=name.casefold()<="z": return bytes([ord(name.casefold())-96]);
            if key==pygame.K_SPACE: return b"\x00";
        return b"";

    def _update_size(self,pygame,font,header_height):
        surface=pygame.display.get_surface(); width,height=surface.get_size(); cell_w=self.cell_width; cell_h=self.cell_height; columns=max(1,width//cell_w); rows=max(1,(height-header_height)//cell_h); desired=TerminalSize(rows,columns);
        for tab in self._tabs:
            if rows!=tab.screen.rows or columns!=tab.screen.columns: tab.screen.resize(rows,columns);
            if tab.session.poll() is None and getattr(tab.session,"size",None)!=desired:
                try: tab.session.resize(rows,columns);
                except Exception: pass;
        return cell_w,cell_h;

    def _tab_label(self,tab,index):
        title=str(tab.screen.title or "").strip();
        if title and title!="SUM Terminal": return title;
        argv=tuple(tab.session.argv or ());
        if len(argv)>=3 and argv[1:3]==("-m","sumbash"): return "sumbash";
        if argv: return os.path.basename(argv[0]) or argv[0];
        return "Tab {}".format(index+1);

    @staticmethod
    def _fit_text(font,text,max_width):
        value=str(text or "");
        if font.size(value)[0]<=max_width: return value;
        suffix="…";
        while value and font.size(value+suffix)[0]>max_width: value=value[:-1];
        return value+suffix if value else suffix;

    def _draw_header(self,pygame,surface,font,theme,height):
        toolbar=self.toolbar_height; tabbar=self.tabbar_height;
        pygame.draw.rect(surface,theme.panel,(0,0,surface.get_width(),toolbar)); pygame.draw.line(surface,theme.line,(0,toolbar-1),(surface.get_width(),toolbar-1),1);
        title="SUM Terminal" + (" — drop-down" if self.drop_down else ""); text=font.render(title,True,theme.text); surface.blit(text,(10,max(2,(toolbar-text.get_height())//2)));
        pref="Preferences"; pref_text=font.render(pref,True,theme.text); pref_rect=pref_text.get_rect(); pref_rect.right=surface.get_width()-12; pref_rect.centery=toolbar//2; surface.blit(pref_text,pref_rect); self._preferences_rect=pref_rect.inflate(16,8);
        if self.drop_down:
            hint=font.render("Ctrl+F12 hide/show",True,theme.muted); hint_rect=hint.get_rect(); hint_rect.right=self._preferences_rect.left-14; hint_rect.centery=toolbar//2; surface.blit(hint,hint_rect);
        y=toolbar; pygame.draw.rect(surface,theme.bg,(0,y,surface.get_width(),tabbar)); pygame.draw.line(surface,theme.line,(0,y+tabbar-1),(surface.get_width(),y+tabbar-1),1);
        self._tab_rects=[]; self._tab_close_rects=[]; self._new_tab_rect=None;
        plus_w=34; left=8; right=max(left+1,surface.get_width()-plus_w-8); available=max(80,right-left); count=max(1,len(self._tabs)); tab_w=max(88,min(220,available//count)); x=left;
        for index,tab in enumerate(self._tabs):
            if x>=right: break;
            width=min(tab_w,right-x); rect=pygame.Rect(x,y+3,width,max(20,tabbar-6)); active=index==self._active_index;
            pygame.draw.rect(surface,theme.button_alt if active else theme.panel,rect,border_radius=4); pygame.draw.rect(surface,theme.line,rect,1,border_radius=4);
            close_text=font.render("×",True,theme.text if active else theme.muted); close_rect=close_text.get_rect(); close_rect.right=rect.right-7; close_rect.centery=rect.centery; surface.blit(close_text,close_rect);
            max_label=max(12,close_rect.left-rect.left-12); label=self._fit_text(font,self._tab_label(tab,index),max_label); label_text=font.render(label,True,theme.text if active else theme.muted); label_rect=label_text.get_rect(); label_rect.left=rect.left+7; label_rect.centery=rect.centery; surface.blit(label_text,label_rect);
            self._tab_rects.append((index,rect)); self._tab_close_rects.append((index,close_rect.inflate(10,8))); x+=width+4;
        plus_rect=pygame.Rect(min(x,right+2),y+3,30,max(20,tabbar-6)); plus_text=font.render("+",True,theme.text); text_rect=plus_text.get_rect(center=plus_rect.center); pygame.draw.rect(surface,theme.panel,plus_rect,border_radius=4); pygame.draw.rect(surface,theme.line,plus_rect,1,border_radius=4); surface.blit(plus_text,text_rect); self._new_tab_rect=plus_rect;

    def _handle_header_click(self,pos):
        if self._preferences_rect is not None and self._preferences_rect.collidepoint(pos): self._open_preferences(); return True;
        if self._new_tab_rect is not None and self._new_tab_rect.collidepoint(pos): self._new_tab(); return True;
        for index,rect in self._tab_close_rects:
            if rect.collidepoint(pos): self._close_tab(index); return True;
        for index,rect in self._tab_rects:
            if rect.collidepoint(pos): self._switch_tab(index); return True;
        return False;

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
                text="".join(chars); width=(end-index)*cell_w; shown_fg=_display_fg(self.screen_model,fg,bold);
                if bg!=self.screen_model.default_bg: pygame.draw.rect(surface,bg,(x,y0+row*cell_h,width,cell_h));
                renderer=self.bold_font if bold and self.bold_font is not None else font; rendered=renderer.render(text,True,shown_fg); surface.blit(rendered,(x,y0+row*cell_h+self.glyph_offset_y));
                if underline: pygame.draw.line(surface,shown_fg,(x,y0+(row+1)*cell_h-2),(x+width,y0+(row+1)*cell_h-2),1);
                x+=width; index=end;
        if self.screen_model.cursor_visible and 0<=self.screen_model.row<self.screen_model.rows:
            col=min(self.screen_model.columns-1,max(0,self.screen_model.col)); x=col*cell_w; y=y0+self.screen_model.row*cell_h+self.glyph_offset_y; cursor_h=min(cell_h,self.glyph_height); pygame.draw.rect(surface,theme.cursor,(x,y,cell_w,cursor_h));
            try: char=self.screen_model.lines[self.screen_model.row][col].char;
            except (IndexError,AttributeError): char=" ";
            if char and char!=" ":
                rendered=font.render(char,True,self.screen_model.default_bg); surface.blit(rendered,(x,y));

    def _service_sessions(self):
        running=[]; mapping={};
        for tab in self._tabs:
            if not tab.eof:
                try: fd=tab.session.fileno;
                except Exception: continue;
                running.append(fd); mapping[fd]=tab;
        try: ready,_,_=select.select(running,[],[],0) if running else ([],[],[]);
        except (OSError,ValueError): ready=[];
        for fd in ready:
            tab=mapping.get(fd);
            if tab is None: continue;
            event=tab.session.read_event(65536);
            if event is None: continue;
            if event.kind=="output": tab.screen.feed(event.text);
            elif event.kind=="eof": tab.eof=True;
            elif event.kind=="exit": tab.exit_code=int(event.exit_code or 0);
        exited=[];
        for index,tab in enumerate(self._tabs):
            code=tab.session.poll();
            if code is not None:
                tab.exit_code=int(code);
                if tab.eof: exited.append(index);
        for index in reversed(exited):
            if len(self._tabs)==1:
                self.running=False;
                break;
            self._close_tab(index);

    def run(self):
        try:
            _prepare_pygame_runtime();
            import pygame;
            from sumgui.display import set_default_icon;
        except ImportError as exc: raise RuntimeError("sumTerminal GUI requires sumGUI/Pygame") from exc;
        if self.session.state.value=="created": self.session.start();
        pygame.init(); pygame.key.set_repeat(400,35); width,height,x,y=self._geometry(pygame); os.environ.setdefault("SDL_VIDEO_WINDOW_POS","{},{}".format(x,y)); self._flags=pygame.RESIZABLE | (pygame.NOFRAME if self.drop_down else 0); pygame.display.set_mode((width,height),self._flags); set_default_icon(); self._apply_window_properties(pygame);
        self._reload_theme(); theme=self.theme; self._make_fonts(pygame); self._preferences_rect=pygame.Rect(0,0,0,0); self._new_tab_rect=pygame.Rect(0,0,0,0); self._update_size(pygame,self.font,self.header_height);
        if self.ipc is not None: self.ipc.start();
        if self.start_hidden: self._set_visible(False);
        clock=pygame.time.Clock(); self.running=True; exit_code=0;
        try:
            while self.running:
                clock.tick(60);
                if self._preferences_finished:
                    self._preferences_finished=False; self._preferences_process=None; self._set_visible(True); self._reload_preferences(pygame); self._preferences_reload_pending=False;
                if self.ipc is not None:
                    for command in self.ipc.pending():
                        if command=="toggle": self.toggle_visible();
                        elif command=="show": self._set_visible(True);
                        elif command=="hide": self._set_visible(False);
                        elif command=="reload":
                            if self._preferences_process is not None and self._preferences_process.poll() is None: self._preferences_reload_pending=True;
                            else: self._reload_preferences(pygame);
                        elif command=="quit": self.running=False;
                for event in pygame.event.get():
                    if event.type==pygame.QUIT: self.running=False;
                    elif event.type==pygame.VIDEORESIZE: self._update_size(pygame,self.font,self.header_height);
                    elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1: self._handle_header_click(event.pos);
                    elif event.type==pygame.KEYDOWN:
                        data=self._key_bytes(pygame,event);
                        if data and self.running: self.session.write(data);
                    elif event.type==pygame.TEXTINPUT:
                        modifiers=pygame.key.get_mods();
                        if event.text and self.running and not (modifiers & (pygame.KMOD_CTRL | pygame.KMOD_ALT | pygame.KMOD_GUI)): self.session.write(event.text.encode("utf-8"));
                    elif self.drop_down and self.preferences.dropdown.hide_on_focus_loss and event.type==getattr(pygame,"WINDOWFOCUSLOST",-999): self._set_visible(False);
                self._service_sessions();
                if not self._tabs: self.running=False; continue;
                exit_code=int(self.active_tab.exit_code or 0);
                if self.screen_model.title!=self._last_title:
                    pygame.display.set_caption(self.screen_model.title or "SUM Terminal"); self._last_title=self.screen_model.title;
                if self.visible:
                    surface=pygame.display.get_surface(); theme=self.theme; surface.fill(theme.bg); cell_w,cell_h=self._update_size(pygame,self.font,self.header_height); self._draw_header(pygame,surface,self.header_font,theme,self.header_height); pygame.draw.rect(surface,self.screen_model.default_bg,(0,self.header_height,surface.get_width(),max(0,surface.get_height()-self.header_height))); self._draw_screen(pygame,surface,self.font,theme,self.header_height,cell_w,cell_h); pygame.display.flip();
        finally:
            if self.ipc is not None: self.ipc.close();
            for tab in list(self._tabs):
                if tab.session.poll() is None: tab.session.terminate();
                try: tab.session.wait(timeout=1.0);
                except Exception: pass;
                tab.session.close();
            pygame.quit();
        return exit_code;
