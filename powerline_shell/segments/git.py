import re
import stat
import subprocess
import os
from ..utils import RepoStats, ThreadedSegment

# `time` segment shadows time module, but exposes it
from time import time

FETCH_HEAD_PATH = os.path.join('.git', 'FETCH_HEAD')

def get_PATH():
    """Normally gets the PATH from the OS. This function exists to enable
    easily mocking the PATH in tests.
    """
    return os.getenv("PATH")


def git_subprocess_env():
    return {
        # LANG is specified to ensure git always uses a language we are expecting.
        # Otherwise we may be unable to parse the output.
        "LANG": "C",

        # https://github.com/milkbikis/powerline-shell/pull/126
        "HOME": os.getenv("HOME"),

        # https://github.com/milkbikis/powerline-shell/pull/153
        "PATH": get_PATH(),
    }


def parse_git_branch_info(status):
    info = re.search('^## (?P<local>\S+?)''(\.{3}(?P<remote>\S+?)( \[(ahead (?P<ahead>\d+)(, )?)?(behind (?P<behind>\d+))?\])?)?$', status[0])
    return info.groupdict() if info else None


def _get_git_detached_branch():
    p = subprocess.Popen(['git', 'describe', '--tags', '--always'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         env=git_subprocess_env())
    detached_ref = p.communicate()[0].decode("utf-8").rstrip('\n')
    if p.returncode == 0:
        branch = u'{} {}'.format(RepoStats.symbols['detached'], detached_ref)
    else:
        branch = 'Big Bang'
    return branch


def parse_git_stats(status):
    stats = RepoStats()
    for statusline in status[1:]:
        code = statusline[:2]
        if code == '??':
            stats.new += 1
        elif code in ('DD', 'AU', 'UD', 'UA', 'DU', 'AA', 'UU'):
            stats.conflicted += 1
        else:
            if code[1] != ' ':
                stats.changed += 1
            if code[0] != ' ':
                stats.staged += 1

    return stats


def build_stats(powerline):
    env = git_subprocess_env()
    try:
        p = subprocess.Popen(['git', 'status', '--porcelain', '-b'],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=env)
    except OSError:
        # Popen will throw an OSError if git is not found
        return (None, None)

    pdata = p.communicate()
    if p.returncode != 0:
        return (None, None)

    status = pdata[0].decode("utf-8").splitlines()
    stats = parse_git_stats(status)
    branch_info = parse_git_branch_info(status)

    if branch_info:
        stats.ahead = branch_info["ahead"]
        stats.behind = branch_info["behind"]
        branch = branch_info['local']
    else:
        branch = _get_git_detached_branch()

    if powerline.segment_conf("git", "fetch_auto", True):
        try:
            p = subprocess.Popen(['git', 'rev-parse', '--show-toplevel'],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 env=env)
            fetch_head_path = os.path.join(p.communicate()[0].strip(), FETCH_HEAD_PATH)
            mtime = os.stat(fetch_head_path)[stat.ST_MTIME]
            timeout = powerline.segment_conf("git", "fetch_timeout", 15 * 60)
            if time.time() - mtime > timeout:
                print "Fetching! FETCH_HEAD is too old: ", time.time() - mtime
                subprocess.Popen(['git fetch --all --quiet &'], shell=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 env=env)
            else:
                print "Cool! FETCH_HEAD is recent: ", time.time() - mtime
        except OSError as e:
            print "Oops", e
            pass

    return stats, branch


class Segment(ThreadedSegment):
    def run(self):
        self.stats, self.branch = build_stats(self.powerline)

    def add_to_powerline(self):
        self.join()
        if not self.stats:
            return
        bg = self.powerline.theme.REPO_CLEAN_BG
        fg = self.powerline.theme.REPO_CLEAN_FG
        if self.stats.dirty:
            bg = self.powerline.theme.REPO_DIRTY_BG
            fg = self.powerline.theme.REPO_DIRTY_FG

        self.powerline.append(" " + self.branch + " ", fg, bg)
        self.stats.add_to_powerline(self.powerline)
