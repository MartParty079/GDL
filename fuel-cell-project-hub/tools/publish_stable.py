"""Dispatch and approve an explicitly authorized exact-commit solo-maintainer release."""
import argparse
import json
import subprocess
import time
import re
from pathlib import Path


def promotion_question(beta_version, stable_version):
    return (f'Beta version {beta_version} has passed the required release checks and is ready for Production. '
            f'Do you approve promoting this exact build to Stable version {stable_version} and publishing it for all Capstone Hub users?')


def validate_confirmation(commit, beta_tag, confirmation):
    match = re.fullmatch(r'v(\d+\.\d+\.\d+)-beta\.(\d+)', beta_tag)
    if not match:
        raise ValueError('A tested Beta tag is required.')
    stable = match[1]
    expected = promotion_question(beta_tag.removeprefix('v'), stable)
    if not confirmation or confirmation.get('approved_commit') != commit or confirmation.get('beta_tag') != beta_tag or confirmation.get('stable_version') != stable or confirmation.get('question') != expected or confirmation.get('response') != 'YES':
        raise ValueError('New explicit human confirmation of this exact Beta, commit and Stable version is required. Rejection cancels promotion.')
    return stable


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True).strip()


def publish(commit, beta_tag, beta_run, authorization, confirmation=None):
    if authorization != 'APPROVE PRODUCTION RELEASE':
        raise ValueError('A new explicit human Stable release instruction is required.')
    stable = validate_confirmation(commit, beta_tag, confirmation)
    repo='MartParty079/GDL'
    if gh('api','user','--jq','.login') != 'MartParty079':
        raise ValueError('Only the authorized sole maintainer may dispatch production.')
    branch=json.loads(gh('api',f'repos/{repo}/branches/develop'))
    if branch['commit']['sha'] != commit:
        raise ValueError('Develop changed; obtain approval for the exact current tested commit.')
    beta=json.loads(gh('run','view',str(beta_run),'--repo',repo,'--json','conclusion,headSha,headBranch'))
    if beta != {'conclusion':'success','headBranch':'develop','headSha':commit}:
        raise ValueError('Successful matching Beta run required.')
    # workflow_dispatch, never a direct main/tag push from this helper.
    output=gh('workflow','run','production-promotion.yml','--repo',repo,'--ref','develop',
              '-f','approved_commit='+commit,'-f','beta_tag='+beta_tag,
              '-f','beta_run_id='+str(beta_run),'-f','production_release_order='+authorization,
              '-f','confirmation_response=YES','-f','proposed_stable_version='+stable,
              '-f','confirmation_question='+confirmation['question'])
    print(output,flush=True)
    run_id=output.rstrip('/').split('/')[-1]
    if not run_id.isdigit():
        raise ValueError('Cannot identify the dispatched run; inspect GitHub Actions before retrying.')
    for _ in range(12):
        pending=json.loads(gh('api',f'repos/{repo}/actions/runs/{run_id}/pending_deployments'))
        if pending:
            production=[row for row in pending if row['environment']['name']=='production']
            if len(production)!=1 or not production[0]['current_user_can_approve']:
                raise ValueError('GitHub does not permit this maintainer to approve the run. No gate will be bypassed.')
            payload={'environment_ids':[production[0]['environment']['id']], 'state':'approved',
                     'comment':'Explicit human Production Release Order approving exact tested commit '+commit}
            subprocess.run(['gh','api','--method','POST',f'repos/{repo}/actions/runs/{run_id}/pending_deployments','--input','-'],input=json.dumps(payload),text=True,check=True)
            print('Production approval submitted. Publication is not complete; verify the run and published assets.',flush=True)
            return run_id
        time.sleep(5)
    raise ValueError('Approval is not ready yet. Inspect the dispatched run; do not dispatch a duplicate.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit',required=True)
    parser.add_argument('--beta-tag',required=True)
    parser.add_argument('--beta-run',required=True)
    parser.add_argument('--production-release-order',required=True)
    parser.add_argument('--confirmation-file',required=True,help='Local exact-build receipt recorded only after the human answers the required question YES')
    args=parser.parse_args()
    publish(args.commit,args.beta_tag,args.beta_run,args.production_release_order,
            json.loads(Path(args.confirmation_file).read_text(encoding='utf-8')))
