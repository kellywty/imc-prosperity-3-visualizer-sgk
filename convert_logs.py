#!/usr/bin/env python3
"""Convert Prosperity JSON log exports to visualizer-compatible plain text."""

import argparse
import json
import os
import sys


def convert_json_logs(json_file: str, output_file: str) -> None:
    """Convert JSON logs to plain text format for the visualizer."""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    out_lines = []

    # Write Activities log header
    out_lines.append('Activities log:')
    out_lines.append('')

    activities_log = data.get('activitiesLog') if isinstance(data, dict) else None
    if isinstance(activities_log, str) and activities_log.strip():
        out_lines.extend(activities_log.strip().splitlines())
        out_lines.append('')

    # Write Sandbox logs header
    out_lines.append('Sandbox logs:')

    if isinstance(data, dict):
        logs = data.get('logs', [])
        for entry in logs:
            sandbox_log = entry.get('sandboxLog', '')
            if sandbox_log:
                out_lines.append(f'  "sandboxLog": {json.dumps(sandbox_log)},')
            if 'lambdaLog' in entry:
                lambda_log = entry['lambdaLog'] or ''
                out_lines.append(f'  "lambdaLog": {json.dumps(lambda_log)},')

    with open(output_file, 'w', encoding='utf-8') as out:
        out.write('\n'.join(out_lines))
        out.write('\n')

    print(f'✓ Converted {json_file} → {output_file}')


def default_output_path(input_path: str) -> str:
    base, ext = os.path.splitext(input_path)
    if not ext:
        ext = '.log'
    return f'{base}_converted{ext}'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Convert Prosperity JSON log exports to the IMC Prosperity visualizer format.',
    )
    parser.add_argument('input', help='Path to the Prosperity JSON log file')
    parser.add_argument(
        'output',
        nargs='?', 
        help='Output path for the converted log file. Defaults to <input>_converted.log',
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    input_path = args.input
    output_path = args.output or default_output_path(input_path)

    if not os.path.exists(input_path):
        print(f'Error: input file not found: {input_path}', file=sys.stderr)
        sys.exit(1)

    convert_json_logs(input_path, output_path)
