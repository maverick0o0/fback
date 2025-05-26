#!/usr/bin/env python3
import os
import sys
import json
import argparse
from urllib.parse import urlparse
import tldextract

# Module-level constants to avoid rebuilding lists in loops
B_EXT = [
    "bpa", "bak", "swp", "~", "tmp", "bckp", "new", "spg", "acp",
    "bkup", "backup", "bak3", "bkz", "abu", "bdb", "blend",
    "backupdb", "sav", "save", "orig", "tig", "sh", "bck",
    "bk", "bash", "copy", "backup1", "bakx", "npf", "log",
    "old", "bundle", "adi", "mbk", "ba", "bak2", "bps",
    "pack", "abk", "back"
]
C_EXT = [
    "zip", "rar", "7z", "tar", "gzip", "bzip", "bz",
    "tar.xz", "pkg.tar.xz", "tg", "tar.gz", "tar.bzip",
    "tsv.gz", "gz", "dz", "tbz", "pkg"
]
EXT_LIST = B_EXT + C_EXT

# Determine base directory once
BASE_DIR = os.path.dirname(os.path.realpath(__file__))


def setup_argparse():
    parser = argparse.ArgumentParser(description="Fback")
    parser.add_argument('-l', help='List of urls', required=True if sys.stdin.isatty() else False)
    parser.add_argument('-p', help='Patterns file path')
    parser.add_argument('-o', help='Output file path')
    parser.add_argument('-w', help='Wordlist file path')
    parser.add_argument('-n', help='Numbers ranges in wordlist', type=int, default=3)
    parser.add_argument('-yr', help='Years ranges in wordlist')
    parser.add_argument('-mr', help='Months ranges in wordlist')
    parser.add_argument('-dr', help='Days ranges in wordlist')
    parser.add_argument('-r', '--relative', action='store_true',
                        help='Output only the path/filename (no scheme://domain prefix)')
    return parser.parse_args()


def read_file(path, mode):
    """Read a text list or JSON file from BASE_DIR."""
    full = os.path.join(BASE_DIR, path)
    with open(full, 'r', encoding='utf-8') as f:
        return [line.rstrip() for line in f] if mode == 'list' else json.load(f)


def generate_variables(arg_str):
    """Expand 'start-end' into a list of strings, or single value list."""
    if arg_str and '-' in arg_str:
        start, end = arg_str.split('-', 1)
        return [str(x) for x in range(int(start), int(end) + 1)]
    return [arg_str] if arg_str else []


def load_patterns(pattern_path):
    """Load and flatten patterns JSON."""
    data = read_file(pattern_path, 'json')
    return [item for sub in data.values() for item in sub]


def load_urls(list_arg):
    """Read URLs either from a file or stdin."""
    if list_arg:
        return read_file(list_arg, 'list')
    return sys.stdin.read().rstrip().splitlines()


def extract_url_parts(url):
    """Parse URL into its components."""
    ext = tldextract.extract(url)
    parsed = urlparse(url)
    domain, sub, suffix = ext.domain, ext.subdomain, ext.suffix
    scheme = parsed.scheme
    full_domain = f"{sub + '.' if sub else ''}{domain}.{suffix}"
    path = parsed.path
    return {
        'domain_name': domain,
        'scheme': scheme,
        'subdomain': sub,
        'tld': suffix,
        'full_domain': full_domain,
        'path': os.path.dirname(path),
        'full_path': path,
        'file_name': os.path.basename(path) if '.' in os.path.basename(path) else ''
    }


def static_replace(patterns, vars_dict):
    """Replace static placeholders in patterns."""
    mapping = {
        '$domain_name': vars_dict['domain_name'],
        '$subdomain': vars_dict['subdomain'],
        '$tld': vars_dict['tld'],
        '$full_domain': vars_dict['full_domain'],
        '$path': vars_dict['path'],
        '$full_path': vars_dict['full_path'],
        '$file_name': vars_dict['file_name'],
    }
    out = []
    seen = set()
    for p in patterns:
        s = p
        for key, val in mapping.items():
            s = s.replace(key, val)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def dynamic_replace(patterns, values, placeholder):
    """Replace one dynamic placeholder with all provided values."""
    out = []
    seen = set()
    for p in patterns:
        for v in values:
            s = p.replace(placeholder, str(v))
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out


def clean_result(results, scheme, domain, relative=False):
    """Normalize slashes and add prefix if needed."""
    out = []
    prefix = f"{scheme}://{domain}"
    for w in results:
        w = w.replace('//', '/')
        if relative:
            out.append(w.lstrip('/'))
        else:
            if not w.startswith('/'):
                w = '/' + w
            out.append(f"{prefix}{w}")
    return out


def create_wordlist(patterns, wordlist, args, vars_dict, years, months, days):
    """Generate complete wordlist for a single URL."""
    pats = static_replace(patterns, vars_dict)
    pats = dynamic_replace(pats, wordlist, '$word')
    pats = dynamic_replace(pats, EXT_LIST, '$ext')
    pats = dynamic_replace(pats, range(1, args.n + 1), '$num')
    if years:
        pats = dynamic_replace(pats, years, '%y')
    if months:
        pats = dynamic_replace(pats, months, '%m')
    if days:
        pats = dynamic_replace(pats, days, '%d')
    # Additional extensions
    if any('$b_ext' in p for p in pats):
        pats = dynamic_replace(pats, B_EXT, '$b_ext')
    if any('$c_ext' in p for p in pats):
        pats = dynamic_replace(pats, C_EXT, '$c_ext')
    return clean_result(pats, vars_dict['scheme'], vars_dict['full_domain'], args.relative)


def main():
    args = setup_argparse()
    patterns = load_patterns(args.p or 'res/patterns.json')
    wordlist = read_file(args.w, 'list') if args.w else [
        'web','fullbackup','backup','data','site','assets','logs','debug','install'
    ]
    years = generate_variables(args.yr)
    months = generate_variables(args.mr)
    days = generate_variables(args.dr)
    urls = load_urls(args.l)

    unique = set()
    for url in urls:
        vars_dict = extract_url_parts(url)
        wl = create_wordlist(patterns, wordlist, args, vars_dict, years, months, days)
        unique.update(wl)

    # Save to file if requested
    if args.o:
        with open(args.o, 'w', encoding='utf-8') as f:
            f.write('\n'.join(u for u in unique if '%' not in u and '$' not in u))

    # Output to stdout
    write = sys.stdout.write
    for u in unique:
        if '%' not in u and '$' not in u:
            write(u + '\n')


if __name__ == '__main__':
    main()
