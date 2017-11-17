from __future__ import absolute_import
from ..utils import BasicSegment
import time


class Segment(BasicSegment):
    def add_to_powerline(self):
        powerline = self.powerline
        if powerline.args.shell == 'bash':
            time_ = ' \\A '
        elif powerline.args.shell == 'zsh':
            time_ = ' %* '
        else:
            time_ = ' %s ' % time.strftime('%H:%M')
        powerline.append(time_,
                         powerline.theme.HOSTNAME_FG,
                         powerline.theme.HOSTNAME_BG)
