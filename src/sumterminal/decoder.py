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
import codecs;


class TerminalDecoder:
    """Incremental UTF-8 decoder; raw terminal bytes remain authoritative.""";

    def __init__(self,encoding="utf-8",errors="replace"):
        self.encoding=str(encoding);
        self.errors=str(errors);
        self._decoder=codecs.getincrementaldecoder(self.encoding)(errors=self.errors);

    def feed(self,data,final=False):
        return self._decoder.decode(bytes(data),final=bool(final));

    def reset(self):
        self._decoder.reset();
