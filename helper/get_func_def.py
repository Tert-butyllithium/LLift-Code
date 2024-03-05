import glob
import subprocess
import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
import sys
from diskcache import Cache
from helper.interact import interactive_func_def
from common.config import LINUX_PATH, SUP_PROJ, ENABLE_INTERACTIVE, ENABLE_CODEQUERY

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

base_url = 'https://elixir.bootlin.com/linux/'
# url = urljoin(base_url, 'A/ident/sscanf')
base_url2 = 'https://elixir.bootlin.com/linux/'
cache_dir = "cache"
_special_cases = json.load(
    open(__location__ + os.sep + "special_cases.json", 'r'))


def read_function_definition(file_path: str, line_number, proj_path=LINUX_PATH):
    if file_path.startswith("source/"):
        file_path = file_path[7:]

    version = proj_path.split(os.sep)[-1]

    with Cache(cache_dir+"/cache_defs", size_limit=1 * 1024 ** 3) as cache:
        # Create a cache key using the function name and version, with size limit = 1GB
        cache_key = f"{version}:{file_path}:{line_number}"

        # Check if the result is already in the cache
        if cache_key in cache:
            func_def = cache[cache_key]
            return func_def

    with open(os.path.join(proj_path, file_path), 'r', errors='ignore') as f:
        lines = f.readlines()

        # Find the starting line of the comments by searching for '*/' before the function definition
        comment_start = line_number - 1
        comments_found = False
        while line_number - 3 < comment_start or comments_found:
            if (not comments_found) and lines[comment_start - 1].strip().startswith('*'):
                comments_found = True

            if lines[comment_start - 1].strip().startswith('/*'):
                comments_found = True
                break
            comment_start -= 1

        # Combine comments (if any) and function definition
        if comments_found:
            function_definition = lines[comment_start - 1:line_number]
        else:
            function_definition = [lines[line_number - 1]]

        # Include the implementation code up to the closing brace of the function
        i = line_number
        while i < len(lines):
            line = lines[i]
            function_definition.append(line)
            if line.startswith('}'):
                break
            i += 1

        res_def = ''.join(function_definition)
        cache[cache_key] = res_def
        return res_def


def read_special_case(file_path, line_no):
    line_start = line_no[0]
    line_end = line_no[1]
    with open(LINUX_PATH + os.sep + file_path, 'r', errors='ignore') as f:
        lines = f.readlines()
        return ''.join(lines[line_start-1:line_end])


def get_func_loc(func_name, version="v4.14"):
    with Cache(cache_dir, size_limit=1 * 1024 ** 3) as cache:
        # Create a cache key using the function name and version, with size limit = 1GB
        cache_key = f"{version}:{func_name}"

        # Check if the result is already in the cache
        if cache_key in cache:
            func_locs = cache[cache_key]
            if len(func_locs) > 0:
                return func_locs

    if "->" in func_name:
        return []

    url = urljoin(base_url+version+"/", f'A/ident/{func_name}')
    response = requests.get(url, timeout=50)

    func_locs = []
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        h2_tags = soup.find_all('h2')

        for h2_tag in h2_tags:
            if 'Defined in' in h2_tag.text and 'as a function' in h2_tag.text:
                ul_tag = h2_tag.find_next_sibling('ul')
                li_tags = ul_tag.find_all('li')

                for li_tag in li_tags:
                    file_location = li_tag.find('a').get('href')[
                        len(version)+1:]
                    func_locs.append(file_location)

    else:
        print("Error: Unable to fetch the content from the function: ",
              func_name, file=sys.stderr)
    cache[cache_key] = func_locs
    return func_locs


def split_func_loc(func_loc: str):
    res = func_loc.split("#L")
    return res[0], int(res[1])


def get_func_def_easy(func_name: str, version="v4.14", linux_path=LINUX_PATH):
    if func_name in _special_cases:
        if _special_cases[func_name]["version"] == version:
            file_path = _special_cases[func_name]["file"]
            line_number = _special_cases[func_name]["lineno"]
            return read_special_case(file_path, line_number)
    func_locs = get_func_loc(func_name, version)
    if len(func_locs) == 0:
        return None
    for func_loc in func_locs:
        if ".c" in func_loc:
            file_path, line_number = split_func_loc(func_loc)
            return read_function_definition(file_path, line_number, linux_path)
    file_path, line_number = split_func_loc(func_locs[0])
    return read_function_definition(file_path, line_number, linux_path)


def __find_latest_db_file(project_root_path):
    # Construct the pattern to match all .db files in the project root
    search_pattern = os.path.join(project_root_path, '*.db')
    
    # List all matching .db files
    db_files = glob.glob(search_pattern)
    
    # Sort the files by modification time, newest first
    db_files.sort(key=os.path.getmtime, reverse=True)
    
    # Return the newest .db file if there are any, otherwise None
    return db_files[0] if db_files else None

def __get_func_cq(project_path, function_name):
    # def find_function_location(function_name, cqsearch_db, project_path):
    # Construct the cqsearch command
    cqsearch_db = __find_latest_db_file(project_path)
    if cqsearch_db is None:
        print(f"Error: No .db file found in {project_path}", file=sys.stderr)
        return None
    command = [
        'cqsearch', 
        '-s', cqsearch_db, 
        '-p', '2', 
        '-u', 
        '-e', 
        '-t', function_name
    ]
    res = []
    
    # Run the cqsearch command and capture its output
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing cqsearch: {e}")
        return res
    
    
    # Extract the relevant file path from the output
    output_lines = result.stdout.splitlines()

    for line in output_lines:
        line = line.split('\t')[1]
        if '$HOME' in line:
            # Extract the path after the project base dir
            base_dir_pattern = os.path.basename(project_path)
            start_index = line.find(base_dir_pattern)
            if start_index != -1:
                # Adjust to get the path relative to the project's base directory
                # relative_path = line[start_index + len(base_dir_pattern) + 1:].split(':')[0]
                # return line[start_index + len(base_dir_pattern) + 1:].split(':')
                res.append(line[start_index + len(base_dir_pattern) + 1:].split(':'))
        else:
            base_dir_pattern = os.path.basename(project_path)
            relative_path_start_index = line.find(base_dir_pattern) + len(base_dir_pattern)
            relative_path = line[relative_path_start_index:].split(':')
            # return relative_path
            res.append(relative_path)

    return res

def get_func_def_codequery(proj, req_func):
    if proj not in SUP_PROJ:
        return None

    with Cache(cache_dir+"/cache_cq", size_limit=1 * 1024 ** 3) as cache:
        # Create a cache key using the function name and version, with size limit = 1GB
        cache_key = f"{proj}:{req_func}"
        if cache_key not in cache:
            res = __get_func_cq(SUP_PROJ[proj], req_func)
            if res is None or len(res) == 0:
                return None
            cache[cache_key] = res
        return cache[cache_key]
    
def ask_which_function(try_cq_res, req_func):
    #TODO: implement it, and move it to interact.py
    return 0


def get_func_def(proj, cur_func, req_func):
    if proj == 'linux':
        return get_func_def_easy(req_func)
    else:
        if ENABLE_CODEQUERY:
            try_cq_res = get_func_def_codequery(proj, req_func)
            if try_cq_res is not None:
                if len(try_cq_res) > 1:
                    if ENABLE_INTERACTIVE:
                        index = ask_which_function(try_cq_res, req_func)
                    else:
                        index = 0
                    res = try_cq_res[index]
                    return read_function_definition(res[0], int(res[1]), SUP_PROJ[proj])
                elif len(try_cq_res) == 1:
                    res = try_cq_res[0] 
                    return read_function_definition(res[0], int(res[1]), SUP_PROJ[proj])

        if not ENABLE_INTERACTIVE:
            return "unknown"
        with Cache(cache_dir+"/cache_interact", size_limit=1 * 1024 ** 3) as cache:
            # Create a cache key using the function name and version, with size limit = 1GB
            cache_key = f"{proj}:{req_func}"
            if cache_key not in cache:
                res = interactive_func_def(proj, cur_func, req_func)
                cache[cache_key] = res
            return cache[cache_key]

# if __name__ == "__main__":

#     # parser = argparse.ArgumentParser(description="Fetch the function definition from the Linux kernel source code.")
#     # parser.add_argument("function_name", help="Name of the function you want to fetch the definition for")
#     # args = parser.parse_args()

#     # func_name = args.function_name

#     file_path = 'lib/vsprintf.c'
#     line_number = 3021
#     # print(read_function_definition(file_path, line_number))
#     print(read_function_definition("skbuff.h", 284))
