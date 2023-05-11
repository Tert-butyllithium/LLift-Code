import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os, sys
from diskcache import Cache
from common.config import LINUX_PATH

base_url = 'https://elixir.bootlin.com/linux/'
# url = urljoin(base_url, 'A/ident/sscanf')
base_url2 = 'https://elixir.bootlin.com/linux/'
cache_dir = "cache"

def read_function_definition(file_path:str, line_number, linux_path=LINUX_PATH):
    if file_path.startswith("source/"):
        file_path = file_path[7:]
    
    version = linux_path.split(os.sep)[-1]

    with Cache(cache_dir+"/cache_defs", size_limit=1 * 1024 ** 3) as cache:
        # Create a cache key using the function name and version, with size limit = 1GB
        cache_key = f"{version}:{file_path}:{line_number}"

        # Check if the result is already in the cache
        # if cache_key in cache:
        #     func_def = cache[cache_key]
        #     return func_def
    
    with open(os.path.join(linux_path, file_path), 'r') as f:
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



def get_func_loc(func_name, version="v4.14"):
    with Cache(cache_dir, size_limit=1 * 1024 ** 3) as cache:
        # Create a cache key using the function name and version, with size limit = 1GB
        cache_key = f"{version}:{func_name}"

        # Check if the result is already in the cache
        if cache_key in cache:
            func_locs = cache[cache_key]
            if len(func_locs) > 0:
                return func_locs
    

    url = urljoin(base_url+version+"/", f'A/ident/{func_name}')
    response = requests.get(url, timeout=5)

    func_locs = []
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        h2_tags = soup.find_all('h2')

        for h2_tag in h2_tags:
            if 'Defined in' in h2_tag.text and 'as a function' in h2_tag.text:
                ul_tag = h2_tag.find_next_sibling('ul')
                li_tags = ul_tag.find_all('li')

                for li_tag in li_tags:
                    file_location = li_tag.find('a').get('href')[len(version)+1:]
                    func_locs.append(file_location)
    else:
        print("Error: Unable to fetch the content from the function: ", func_name, file=sys.stderr)
    cache[cache_key] = func_locs
    return func_locs


def split_func_loc(func_loc:str):
    res =  func_loc.split("#L")
    return res[0], int(res[1])

def get_func_def_easy(func_name:str, version="v4.14", linux_path=LINUX_PATH):
    func_locs = get_func_loc(func_name, version)
    if len(func_locs) == 0:
        return None
    for func_loc in func_locs:
        if ".c" in func_loc:
            file_path, line_number = split_func_loc(func_loc)
            return read_function_definition(file_path, line_number, linux_path)
    file_path, line_number = split_func_loc(func_locs[0])
    return read_function_definition(file_path, line_number, linux_path)

# if __name__ == "__main__":

#     # parser = argparse.ArgumentParser(description="Fetch the function definition from the Linux kernel source code.")
#     # parser.add_argument("function_name", help="Name of the function you want to fetch the definition for")
#     # args = parser.parse_args()

#     # func_name = args.function_name

#     file_path = 'lib/vsprintf.c'
#     line_number = 3021
#     # print(read_function_definition(file_path, line_number))
#     print(read_function_definition("skbuff.h", 284))
