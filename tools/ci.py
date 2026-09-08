#!/usr/bin/env python3
"""Sovereign Zero-Dependency GitHub Actions Status Query Tool.

Fetches real-time GitHub Actions CI status for the bible repository
using Python standard library urllib (zero external dependencies).
"""

import argparse
import json
import sys
import urllib.request
import urllib.error

REPO = 'mrmarkwell/bible'
API_URL = f'https://api.github.com/repos/{REPO}/actions/runs'

def get_runs(limit=5):
    url = f'{API_URL}?per_page={limit}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Bible-Engine-CI'})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, Exception) as e:
        print(f'Error fetching GitHub Actions status: {e}', file=sys.stderr)
        return None

def get_jobs(run_id):
    url = f'{API_URL}/{run_id}/jobs'
    req = urllib.request.Request(url, headers={'User-Agent': 'Bible-Engine-CI'})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, Exception) as e:
        print(f'Error fetching jobs for run {run_id}: {e}', file=sys.stderr)
        return None

def main():
    parser = argparse.ArgumentParser(description='Query GitHub Actions CI status')
    parser.add_argument('--limit', '-n', type=int, default=5, help='Number of runs to inspect')
    parser.add_argument('--details', '-d', action='store_true', help='Show detailed step status for the latest run')
    args = parser.parse_args()

    data = get_runs(args.limit)
    if not data or 'workflow_runs' not in data:
        print('Could not retrieve workflow runs.')
        sys.exit(1)

    runs = data['workflow_runs']
    print('=' * 72)
    print(f' GitHub Actions CI Status: {REPO}')
    print('=' * 72)
    for r in runs:
        sha = r['head_sha'][:7]
        msg = r['head_commit']['message'].splitlines()[0] if r.get('head_commit') else 'N/A'
        status = r['status']
        conclusion = r.get('conclusion') or 'in_progress'
        icon = '✅' if conclusion == 'success' else ('❌' if conclusion == 'failure' else '⏳')
        print(f' {icon} Run #{r["id"]} [{status}/{conclusion}]')
        print(f'    Commit: {sha} - "{msg}"')
        print(f'    URL:    {r["html_url"]}')
        print()

    if args.details and runs:
        latest = runs[0]
        jobs_data = get_jobs(latest['id'])
        if jobs_data and 'jobs' in jobs_data:
            print('-' * 72)
            print(f' Detailed Steps for Run #{latest["id"]}:')
            print('-' * 72)
            for j in jobs_data['jobs']:
                j_icon = '✅' if j.get('conclusion') == 'success' else '❌'
                print(f'  {j_icon} {j["name"]}: {j["status"]} ({j.get("conclusion", "-")})')
                for s in j.get('steps', []):
                    s_icon = '✓' if s.get('conclusion') == 'success' else ('✗' if s.get('conclusion') == 'failure' else '○')
                    print(f'     [{s_icon}] {s["name"]}')
            print()

if __name__ == '__main__':
    main()
