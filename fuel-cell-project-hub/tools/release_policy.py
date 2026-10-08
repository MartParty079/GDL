"""Fail closed before builds and publication; development never publishes Stable."""
import argparse
import json
import re
import subprocess
from pathlib import Path


def validate(channel, branch, commit, approval=None):
    if channel == 'beta':
        if branch != 'develop':raise ValueError('Beta builds require develop.')
    elif channel == 'stable':
        if branch != 'main':raise ValueError('Stable builds require main.')
        if not approval or approval.get('approved_commit') != commit or approval.get('production_release_order') != 'APPROVED':
            raise ValueError('Stable requires an explicit Production Release Order approving this exact commit.')
    else:raise ValueError('Unknown release channel.')


def check(channel, approval_file=None):
    branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise ValueError('Builds require a clean committed source tree.')
    approval=json.loads(Path(approval_file).read_text()) if approval_file else None
    validate(channel,branch,commit,approval)
    return commit


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--channel',choices=['beta','stable'],default='beta');parser.add_argument('--approval-file')
    args=parser.parse_args();print(check(args.channel,args.approval_file))
