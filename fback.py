import os
import tldextract
import pathlib
import argparse
import json
import sys
from urllib.parse import urlparse

currentPath = os.path.dirname(os.path.realpath(__file__))

def setup_argparse():
    """
    Parse Command line arguments
    """
    parser = argparse.ArgumentParser(description="Fback")
    parser.add_argument('-l', help='List of urls', required=True if sys.stdin.isatty() else False)
    parser.add_argument('-p', help='Patterns file path')
    parser.add_argument('-o', help='Output file path')
    parser.add_argument('-w', help='Wordlist file path')
    parser.add_argument('-n', help='Numbers ranges in wordlist', type=int, default=3)
    parser.add_argument('-e', help='Extension file path')
    parser.add_argument('-yr', help='Years ranges in wordlist')
    parser.add_argument('-mr', help='Months ranges in wordlist')
    parser.add_argument('-dr', help='Days ranges in wordlist')
    parser.add_argument('-r', '--relative', action='store_true',
                        help='Output only the path/filename (no scheme://domain prefix)')
    return parser.parse_args()

def extract_url_parts(url):
    """
    Extract $domain_name, $subdomain, $tld, $full_domain, $full_path, $path, $file_name
    """
    extractUrl = tldextract.extract(url)
    parsed = urlparse(url)

    domain_name = extractUrl.domain
    subdomain = extractUrl.subdomain
    tld = extractUrl.suffix
    scheme = parsed.scheme

    if subdomain:
        full_domain = f"{subdomain}.{domain_name}.{tld}"
    else:
        full_domain = f"{domain_name}.{tld}"

    path = os.path.dirname(parsed.path)
    full_path = pathlib.Path(parsed.path)
    file_name = os.path.basename(parsed.path)
    if '.' not in file_name:
        file_name = ''

    return {
        "domain_name": domain_name,
        "scheme": scheme,
        "subdomain": subdomain,
        "tld": tld,
        "full_domain": full_domain,
        "path": path,
        "full_path": str(full_path),
        "file_name": file_name
    }

def generateVariablesList(arg_str):
    """
    Generate a List for numerical variables Ex : "1999-2002" -> ["1999","2000","2001","2002"]
    """
    if arg_str:
        if "-" in arg_str:
            start, end = arg_str.split("-", 1)
            return [str(x) for x in range(int(start), int(end) + 1)]
        return [arg_str]
    return None

def readFile(filename, filetype):
    """
    Read JSON or txt files
    """
    full = os.path.join(currentPath, filename)
    with open(full, "r", encoding="utf-8") as f:
        if filetype == "list":
            return [line.rstrip() for line in f]
        if filetype == "json":
            return json.load(f)

def loadPatterns(args):
    """
    Load Pattern file
    """
    filePath = args.p if args.p else "res/patterns.json"
    patterns = readFile(filePath, filetype="json")
    all_patterns = []
    for key, lst in patterns.items():
        all_patterns.extend(lst)
    return all_patterns

def loadUrls(args):
    """
    Load Urls from stdin or arguments
    """
    if not args.l:
        data = sys.stdin.read()
        urls = data.rstrip().splitlines()
    else:
        urls = readFile(args.l, filetype="list")
    return urls

def staticReplace(patterns, vars_dict):
    """
    Store Static Variables into Patterns
    """
    out = []
    for p in patterns:
        s = p.replace('$domain_name', vars_dict["domain_name"])
        s = s.replace('$full_domain', vars_dict["full_domain"])
        s = s.replace('$subdomain', vars_dict["subdomain"])
        s = s.replace('$path', vars_dict["path"])
        s = s.replace('$full_path', vars_dict["full_path"])
        s = s.replace('$file_name', vars_dict["file_name"])
        if s not in out:
            out.append(s)
    return out

def dynamicReplace(patterns, repList, placeholder):
    """
    Store Dynamic Variables into Patterns
    """
    out = []
    for p in patterns:
        for x in repList:
            s = p.replace(placeholder, str(x))
            if s not in out:
                out.append(s)
    return out

def checkPatternsExtension(patterns):
    """
    Check for $b_ext or $c_ext in pattern
    """
    return {
        "b_ext": any('$b_ext' in p for p in patterns),
        "c_ext": any('$c_ext' in p for p in patterns)
    }

def cleanResult(result, scheme, domain, relative=False):
    """
    Clean results and optionally prepend scheme://domain.
    If relative=True, just strip leading "/" and output the tail.
    """
    cleaned = []
    for word in result:
        # normalize double slashes
        word = word.replace("//", "/")
        if relative:
            cleaned.append(word.lstrip("/"))
        else:
            if not word.startswith("/"):
                word = "/" + word
            cleaned.append(f"{scheme}://{domain}{word}")
    return cleaned

def createWordlist(patterns, wordlist, ext, b_ext, c_ext, args, vars_dict, years, months, days):
    """
    Create wordlist with pattern and all variables
    """
    pats = staticReplace(patterns, vars_dict)
    pats = dynamicReplace(pats, wordlist, "$word")
    pats = dynamicReplace(pats, ext, "$ext")
    pats = dynamicReplace(pats, range(1, args.n + 1), "$num")
    if years:
        pats = dynamicReplace(pats, years, "%y")
    if months:
        pats = dynamicReplace(pats, months, "%m")
    if days:
        pats = dynamicReplace(pats, days, "%d")

    flags = checkPatternsExtension(pats)
    if flags["b_ext"]:
        pats = dynamicReplace(pats, b_ext, "$b_ext")
    if flags["c_ext"]:
        pats = dynamicReplace(pats, c_ext, "$c_ext")

    return cleanResult(pats, vars_dict["scheme"], vars_dict["full_domain"], relative=args.relative)

def saveResults(results, args):
    """
    Save results to a file (only if -o was provided)
    """
    if args.o:
        with open(args.o, 'w', encoding="utf-8") as f:
            for item in results:
                if "%" not in item and "$" not in item:
                    f.write(item + "\n")

def main():
    args = setup_argparse()
    patterns = loadPatterns(args)
    wordlist = readFile(args.w, "list") if args.w else [
        "web", "fullbackup", "backup", "data", "site", "assets",
        "logs", "debug", "install"
    ]
    b_ext = ["bpa", "bak", "swp", "~", "tmp", "bckp", "new", "spg", "acp",
             "bkup", "backup", "bak3", "bkz", "abu", "bdb", "blend",
             "backupdb", "sav", "save", "orig", "tig", "sh", "bck",
             "bk", "bash", "copy", "backup1", "bakx", "npf", "log",
             "old", "bundle", "adi", "mbk", "ba", "bak2", "bps",
             "pack", "abk", "back"]
    c_ext = ["zip", "rar", "7z", "tar", "gzip", "bzip", "bz",
             "tar.xz", "pkg.tar.xz", "tg", "tar.gz", "tar.bzip",
             "tsv.gz", "gz", "dz", "tbz", "pkg"]
    ext = b_ext + c_ext

    years = generateVariablesList(args.yr)
    months = generateVariablesList(args.mr)
    days = generateVariablesList(args.dr)
    urls = loadUrls(args)

    all_results = []
    for url in urls:
        vars_dict = extract_url_parts(url)
        wl = createWordlist(patterns, wordlist, ext, b_ext, c_ext,
                             args, vars_dict, years, months, days)
        all_results.extend(wl)

    unique = set(all_results)
    saveResults(unique, args)

    for entry in unique:
        if "%" not in entry and "$" not in entry:
            print(entry)

if __name__ == "__main__":
    main()
