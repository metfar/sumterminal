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
from .crashlog import crash_log_path, log_exception;
from .ipc import DropdownIPCServer;
from .input import TerminalInputEncoder;
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
        self.encoder=TerminalInputEncoder(self.screen.modes);
        self.eof=False;
        self.exit_code=None;
        self.scroll_offset=0;


class GuiTerminalView:
    """SUM-owned graphical terminal view over one or more TerminalSession objects.""";

    def __init__(self,session,preferences=None,drop_down=False,start_hidden=False,trace_input=False):
        self.preferences=(preferences or load_preferences()).normalized();
        self.drop_down=bool(drop_down);
        self.start_hidden=bool(start_hidden);
        self.visible=not self.start_hidden;
        self.running=False;
        self.trace_input=bool(trace_input or os.environ.get("SUMTERMINAL_TRACE_INPUT"));
        self.poll_hz=max(30,min(1000,int(os.environ.get("SUMTERMINAL_POLL_HZ","144") or 144)));
        self._force_redraw=True;
        self._last_render_signature=None;
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
        self._runtime_error=None;
        self._runtime_error_context="";
        self._runtime_error_log=str(crash_log_path());
        self._last_error_signature=None;
        self._last_error_count=0;
        self._apply_theme_to_screens();

    def _record_runtime_error(self,context,exc):
        signature=(str(context),type(exc).__name__,str(exc));
        if signature==self._last_error_signature:
            self._last_error_count+=1;
        else:
            self._last_error_signature=signature;
            self._last_error_count=1;
        self._runtime_error=(type(exc).__name__,str(exc));
        self._runtime_error_context=str(context);
        self._runtime_error_log=str(log_exception(context,exc));
        self._force_redraw=True;
        self._trace("ERROR context={} type={} message={}".format(context,type(exc).__name__,exc));
        return False;

    def _dismiss_runtime_error(self):
        self._runtime_error=None;
        self._runtime_error_context="";
        self._force_redraw=True;
        return True;

    def _draw_runtime_error_overlay(self,pygame,surface):
        if self._runtime_error is None:
            return False;
        error_type,message=self._runtime_error;
        message=str(message or "").replace("\n"," ").strip();
        text="{} in {}: {}".format(error_type,self._runtime_error_context,message or "unexpected error");
        hint="Esc dismisses this message; details: {}".format(self._runtime_error_log);
        width=max(1,int(surface.get_width()));
        line_height=max(18,int(getattr(self.header_font,"get_linesize",lambda:18)()));
        box_height=min(surface.get_height(),line_height*2+10);
        top=max(0,surface.get_height()-box_height);
        pygame.draw.rect(surface,self.theme.error,(0,top,width,box_height));
        renderer=self.header_font or self.font;
        if renderer is not None:
            max_chars=max(8,int(width/max(1,self.cell_width))-2);
            line1=renderer.render(text[:max_chars],True,self.theme.button_text);
            line2=renderer.render(hint[:max_chars],True,self.theme.button_text);
            surface.blit(line1,(6,top+3));
            surface.blit(line2,(6,top+3+line_height));
        return True;

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

    def _trace(self,message):
        if not self.trace_input: return;
        try: print("sumterminal[trace]: {}".format(message),file=sys.stderr,flush=True);
        except Exception: pass;

    @staticmethod
    def _mode_signature(screen):
        modes=screen.modes;
        return (bool(modes.application_cursor),bool(modes.application_keypad),int(modes.keyboard_flags),bool(modes.bracketed_paste),int(modes.mouse_tracking),bool(modes.mouse_sgr),bool(modes.alternate_screen));

    @staticmethod
    def _hex(data):
        return " ".join("{:02x}".format(value) for value in bytes(data or b""));

    def _render_signature(self):
        return (self._active_index,tuple((tab.screen.revision,tab.screen.title,tab.eof,tab.exit_code,tab.scroll_offset) for tab in self._tabs),bool(self.visible),self.preferences.general.theme,self.effective_font_name,int(self.preferences.general.font_size));

    @staticmethod
    def _max_scroll_offset(tab):
        if tab.screen.modes.alternate_screen: return 0;
        return max(0,len(tab.screen.scrollback));

    def _scroll_view(self,delta):
        tab=self.active_tab; maximum=self._max_scroll_offset(tab); old=tab.scroll_offset; tab.scroll_offset=max(0,min(maximum,int(old)+int(delta)));
        if tab.scroll_offset!=old: self._force_redraw=True;
        return tab.scroll_offset;

    def _viewport_lines(self,tab=None):
        tab=tab or self.active_tab; screen=tab.screen; offset=max(0,min(self._max_scroll_offset(tab),int(tab.scroll_offset)));
        if offset<=0: return screen.lines;
        history=list(screen.scrollback)+list(screen.lines); end=max(0,len(history)-offset); start=max(0,end-screen.rows); lines=history[start:end];
        if len(lines)<screen.rows: lines=[screen._blank_line() for _ in range(screen.rows-len(lines))]+lines;
        return lines[-screen.rows:];

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
        self._last_title=""; self._force_redraw=True;
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
        self._last_title=""; self._force_redraw=True;

    def _switch_tab(self,index):
        if not self._tabs: return;
        value=max(0,min(len(self._tabs)-1,int(index)));
        if value!=self._active_index:
            self._active_index=value;
            self._last_title=""; self._force_redraw=True;

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
        requested=bool(value);
        if requested==self.visible: return;
        self.visible=requested; self._force_redraw=True; window=self._sdl_window();
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
        sample="iMW0@#_";
        widths=[self.font.size(char)[0] for char in sample];
        if self.bold_font is not None: widths.extend(self.bold_font.size(char)[0] for char in sample);
        self.cell_width=max(1,max(widths));
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
        self._update_size(pygame,self.font,self.header_height); self._force_redraw=True;

    def _open_preferences(self):
        if self._preferences_process is not None and self._preferences_process.poll() is None: return;
        executable=shutil.which("sumterminal");
        command=[executable,"--preferences"] if executable else [sys.executable,"-m","sumterminal","--preferences"];
        self._preferences_reload_pending=False;
        try: self._preferences_process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True);
        except OSError: raise;
        def wait_preferences():
            try: self._preferences_process.wait();
            except Exception: pass;
            self._preferences_finished=True;
        threading.Thread(target=wait_preferences,name="sumterminal-preferences",daemon=True).start();

    @staticmethod
    def _semantic_key(pygame,key):
        mapping={pygame.K_RETURN:"return",pygame.K_BACKSPACE:"backspace",pygame.K_TAB:"tab",pygame.K_ESCAPE:"escape",pygame.K_UP:"up",pygame.K_DOWN:"down",pygame.K_RIGHT:"right",pygame.K_LEFT:"left",pygame.K_HOME:"home",pygame.K_END:"end",pygame.K_PAGEUP:"pageup",pygame.K_PAGEDOWN:"pagedown",pygame.K_INSERT:"insert",pygame.K_DELETE:"delete",pygame.K_F1:"f1",pygame.K_F2:"f2",pygame.K_F3:"f3",pygame.K_F4:"f4",pygame.K_F5:"f5",pygame.K_F6:"f6",pygame.K_F7:"f7",pygame.K_F8:"f8",pygame.K_F9:"f9",pygame.K_F10:"f10",pygame.K_F11:"f11",pygame.K_F12:"f12",pygame.K_SPACE:"space"};
        keypad=(("K_KP0","kp0"),("K_KP1","kp1"),("K_KP2","kp2"),("K_KP3","kp3"),("K_KP4","kp4"),("K_KP5","kp5"),("K_KP6","kp6"),("K_KP7","kp7"),("K_KP8","kp8"),("K_KP9","kp9"),("K_KP_PERIOD","kp_period"),("K_KP_DIVIDE","kp_divide"),("K_KP_MULTIPLY","kp_multiply"),("K_KP_MINUS","kp_minus"),("K_KP_PLUS","kp_plus"),("K_KP_ENTER","kp_enter"),("K_KP_EQUALS","kp_equals"));
        for attribute,name in keypad:
            value=getattr(pygame,attribute,None);
            if value is not None: mapping[value]=name;
        if key in mapping: return mapping[key];
        name=pygame.key.name(key);
        return name.casefold() if isinstance(name,str) else "";

    def _key_bytes(self,pygame,event):
        key=event.key; mod=event.mod;
        if (mod & pygame.KMOD_CTRL) and key==pygame.K_F12 and self.drop_down: self.toggle_visible(); return b"";
        if (mod & pygame.KMOD_CTRL) and key==pygame.K_COMMA: self._open_preferences(); return b"";
        if (mod & pygame.KMOD_CTRL) and (mod & pygame.KMOD_SHIFT) and key==pygame.K_t: self._new_tab(); return b"";
        shift=bool(mod & pygame.KMOD_SHIFT); alt=bool(mod & pygame.KMOD_ALT); ctrl=bool(mod & pygame.KMOD_CTRL); semantic=self._semantic_key(pygame,key); text=getattr(event,"unicode","");
        if shift and semantic=="pageup": self._scroll_view(max(1,self.screen_model.rows-1)); return b"";
        if shift and semantic=="pagedown": self._scroll_view(-max(1,self.screen_model.rows-1)); return b"";
        data=self.active_tab.encoder.encode_key(semantic,shift=shift,alt=alt,ctrl=ctrl,text=text); modes=self.screen_model.modes;
        if data and self.active_tab.scroll_offset: self.active_tab.scroll_offset=0; self._force_redraw=True;
        self._trace("KEYDOWN key={} semantic={} mod={} shift={} alt={} ctrl={} text={!r} app_cursor={} app_keypad={} kitty_flags={} send={}".format(key,semantic,mod,shift,alt,ctrl,text,modes.application_cursor,modes.application_keypad,modes.keyboard_flags,self._hex(data)));
        return data;

    def _mouse_bytes(self,pygame,event,pressed=True):
        screen=self.screen_model;
        if not screen.mouse_tracking or not screen.mouse_sgr: return b"";
        if not hasattr(event,"pos"): return b"";
        x,y=event.pos;
        if y<self.header_height: return b"";
        column=max(1,min(screen.columns,(int(x)//max(1,self.cell_width))+1)); row=max(1,min(screen.rows,((int(y)-self.header_height)//max(1,self.cell_height))+1));
        mod=pygame.key.get_mods(); modifier=(4 if mod & pygame.KMOD_SHIFT else 0)+(8 if mod & pygame.KMOD_ALT else 0)+(16 if mod & pygame.KMOD_CTRL else 0);
        button_map={1:0,2:1,3:2,4:64,5:65}; button=int(getattr(event,"button",1)); code=button_map.get(button,0)+modifier;
        final="M" if pressed or button in (4,5) else "m";
        return "\x1b[<{};{};{}{}".format(code,column,row,final).encode("ascii");

    def _mouse_motion_bytes(self,pygame,event):
        screen=self.screen_model;
        if screen.mouse_tracking not in (1002,1003) or not screen.mouse_sgr: return b"";
        buttons=tuple(getattr(event,"buttons",()));
        if screen.mouse_tracking==1002 and not any(buttons): return b"";
        base=3;
        if buttons:
            if len(buttons)>0 and buttons[0]: base=0;
            elif len(buttons)>1 and buttons[1]: base=1;
            elif len(buttons)>2 and buttons[2]: base=2;
        x,y=event.pos;
        if y<self.header_height: return b"";
        column=max(1,min(screen.columns,(int(x)//max(1,self.cell_width))+1)); row=max(1,min(screen.rows,((int(y)-self.header_height)//max(1,self.cell_height))+1));
        mod=pygame.key.get_mods(); modifier=(4 if mod & pygame.KMOD_SHIFT else 0)+(8 if mod & pygame.KMOD_ALT else 0)+(16 if mod & pygame.KMOD_CTRL else 0); code=32+base+modifier;
        return "\x1b[<{};{};{}M".format(code,column,row).encode("ascii");

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
        y0=header_height; tab=self.active_tab; viewport=self._viewport_lines(tab);
        for row,line in enumerate(viewport):
            y=y0+row*cell_h;
            for column,cell in enumerate(line):
                x=column*cell_w; fg,bg=(cell.bg,cell.fg) if cell.inverse else (cell.fg,cell.bg); shown_fg=_display_fg(self.screen_model,fg,cell.bold);
                if bg!=self.screen_model.default_bg: pygame.draw.rect(surface,bg,(x,y,cell_w,cell_h));
                char=cell.char or " ";
                if char!=" ":
                    renderer=self.bold_font if cell.bold and self.bold_font is not None else font; rendered=renderer.render(char,True,shown_fg); surface.blit(rendered,(x,y+self.glyph_offset_y));
                if cell.underline: pygame.draw.line(surface,shown_fg,(x,y+cell_h-2),(x+cell_w,y+cell_h-2),1);
        if tab.scroll_offset==0 and self.screen_model.cursor_visible and 0<=self.screen_model.row<self.screen_model.rows:
            col=min(self.screen_model.columns-1,max(0,self.screen_model.col)); x=col*cell_w; y=y0+self.screen_model.row*cell_h+self.glyph_offset_y; cursor_h=min(cell_h,self.glyph_height); pygame.draw.rect(surface,theme.cursor,(x,y,cell_w,cursor_h));
            try: cell=self.screen_model.lines[self.screen_model.row][col]; char=cell.char;
            except (IndexError,AttributeError): cell=None; char=" ";
            if char and char!=" ":
                renderer=self.bold_font if cell is not None and cell.bold and self.bold_font is not None else font; rendered=renderer.render(char,True,self.screen_model.default_bg); surface.blit(rendered,(x,y));

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
            before=self._mode_signature(tab.screen); chunks=0; total=0;
            while chunks<128:
                event=tab.session.read_event(65536);
                if event is None: break;
                chunks+=1; total+=len(getattr(event,"raw",b"") or b"");
                if event.kind=="output":
                    before_scrollback=len(tab.screen.scrollback); was_scrolled=tab.scroll_offset>0; tab.screen.feed(event.text);
                    if tab.screen.modes.alternate_screen: tab.scroll_offset=0;
                    elif was_scrolled:
                        added=max(0,len(tab.screen.scrollback)-before_scrollback); tab.scroll_offset=min(self._max_scroll_offset(tab),tab.scroll_offset+added);
                    while tab.screen.pending_replies:
                        reply=tab.screen.pending_replies.pop(0);
                        try: tab.session.write(reply);
                        except Exception: break;
                elif event.kind=="eof": tab.eof=True; break;
                elif event.kind=="exit": tab.exit_code=int(event.exit_code or 0);
                try: more,_,_=select.select([fd],[],[],0);
                except (OSError,ValueError): more=[];
                if not more: break;
            after=self._mode_signature(tab.screen);
            if before!=after: self._trace("MODES app_cursor={} app_keypad={} kitty_flags={} bracketed={} mouse={} sgr={} alternate={}".format(*after));
            if chunks>1: self._trace("PTY burst chunks={} bytes={}".format(chunks,total));
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

    def _handle_pygame_event(self,pygame,event):
        if event.type==pygame.KEYDOWN and self._runtime_error is not None and event.key==pygame.K_ESCAPE:
            return self._dismiss_runtime_error();
        if event.type==pygame.QUIT:
            self.running=False;
            return True;
        if event.type==pygame.VIDEORESIZE:
            self._update_size(pygame,self.font,self.header_height);
            self._force_redraw=True;
            return True;
        if event.type==getattr(pygame,"MOUSEWHEEL",-999):
            if self.screen_model.mouse_tracking and self.screen_model.mouse_sgr:
                button=4 if int(getattr(event,"y",0))>0 else 5;
                synthetic=type("WheelEvent",(),{"button":button,"pos":pygame.mouse.get_pos()})();
                data=self._mouse_bytes(pygame,synthetic,True);
                if data and self.running: self.session.write(data);
            else:
                amount=int(getattr(event,"y",0) or 0);
                self._scroll_view(amount*3);
            return True;
        if event.type==pygame.MOUSEBUTTONDOWN:
            handled=event.button==1 and self._handle_header_click(event.pos);
            if not handled:
                data=self._mouse_bytes(pygame,event,True);
                if data and self.running: self.session.write(data);
                elif not hasattr(pygame,"MOUSEWHEEL") and event.button==4: self._scroll_view(3);
                elif not hasattr(pygame,"MOUSEWHEEL") and event.button==5: self._scroll_view(-3);
            return True;
        if event.type==pygame.MOUSEBUTTONUP:
            data=self._mouse_bytes(pygame,event,False);
            if data and self.running: self.session.write(data);
            return True;
        if event.type==pygame.MOUSEMOTION:
            data=self._mouse_motion_bytes(pygame,event);
            if data and self.running: self.session.write(data);
            return True;
        if event.type==pygame.KEYDOWN:
            data=self._key_bytes(pygame,event);
            if data and self.running: self.session.write(data);
            return True;
        if event.type==pygame.TEXTINPUT:
            modifiers=pygame.key.get_mods();
            if event.text and self.running and not (modifiers & (pygame.KMOD_CTRL | pygame.KMOD_ALT | pygame.KMOD_GUI)):
                self.session.write(event.text.encode("utf-8"));
            return True;
        if self.drop_down and self.preferences.dropdown.hide_on_focus_loss and event.type==getattr(pygame,"WINDOWFOCUSLOST",-999):
            self._set_visible(False);
            return True;
        return False;

    def _render_frame(self,pygame):
        signature=self._render_signature();
        redraw=self._force_redraw or signature!=self._last_render_signature;
        if not self.visible or not redraw:
            return False;
        surface=pygame.display.get_surface();
        theme=self.theme;
        surface.fill(theme.bg);
        cell_w,cell_h=self._update_size(pygame,self.font,self.header_height);
        self._draw_header(pygame,surface,self.header_font,theme,self.header_height);
        pygame.draw.rect(surface,self.screen_model.default_bg,(0,self.header_height,surface.get_width(),max(0,surface.get_height()-self.header_height)));
        self._draw_screen(pygame,surface,self.font,theme,self.header_height,cell_w,cell_h);
        self._draw_runtime_error_overlay(pygame,surface);
        pygame.display.flip();
        self._last_render_signature=self._render_signature();
        self._force_redraw=False;
        return True;

    def _render_emergency_frame(self,pygame):
        try:
            surface=pygame.display.get_surface();
            if surface is None: return False;
            surface.fill((0,0,0));
            self._draw_runtime_error_overlay(pygame,surface);
            pygame.display.flip();
            self._force_redraw=False;
            return True;
        except Exception:
            return False;

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
                clock.tick(self.poll_hz);
                try:
                    if self._preferences_finished:
                        self._preferences_finished=False;
                        self._preferences_process=None;
                        self._reload_preferences(pygame);
                        self._preferences_reload_pending=False;
                except Exception as exc:
                    self._record_runtime_error("preferences reload",exc);
                if self.ipc is not None:
                    try:
                        commands=self.ipc.pending();
                    except Exception as exc:
                        self._record_runtime_error("dropdown IPC",exc);
                        commands=[];
                    for command in commands:
                        try:
                            if command=="toggle": self.toggle_visible();
                            elif command=="show": self._set_visible(True);
                            elif command=="hide": self._set_visible(False);
                            elif command=="reload":
                                if self._preferences_process is not None and self._preferences_process.poll() is None: self._preferences_reload_pending=True;
                                else: self._reload_preferences(pygame);
                            elif command=="quit": self.running=False;
                        except Exception as exc:
                            self._record_runtime_error("dropdown command {}".format(command),exc);
                try:
                    events=pygame.event.get();
                except Exception as exc:
                    self._record_runtime_error("pygame event queue",exc);
                    events=[];
                for event in events:
                    try:
                        self._handle_pygame_event(pygame,event);
                    except Exception as exc:
                        self._record_runtime_error("input event",exc);
                try:
                    self._service_sessions();
                except Exception as exc:
                    self._record_runtime_error("PTY/session service",exc);
                if not self._tabs:
                    self.running=False;
                    continue;
                exit_code=int(self.active_tab.exit_code or 0);
                try:
                    if self.screen_model.title!=self._last_title:
                        pygame.display.set_caption(self.screen_model.title or "SUM Terminal");
                        self._last_title=self.screen_model.title;
                except Exception as exc:
                    self._record_runtime_error("window title",exc);
                try:
                    self._render_frame(pygame);
                except Exception as exc:
                    self._record_runtime_error("terminal renderer",exc);
                    self._render_emergency_frame(pygame);
        finally:
            if self.ipc is not None: self.ipc.close();
            for tab in list(self._tabs):
                if tab.session.poll() is None: tab.session.terminate();
                try: tab.session.wait(timeout=1.0);
                except Exception: pass;
                tab.session.close();
            pygame.quit();
        return exit_code;
