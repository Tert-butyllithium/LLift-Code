from diskcache import Cache
from helper.interact import interactive_func_def

cache_dir = "cache"

if __name__ == "__main__":
    cache_key = f"edk2:{'alg_module_init'}"
    with Cache(cache_dir+"/cache_interact", size_limit=1 * 1024 ** 3) as cache:
        # print(cache[cache_key])
        cache[cache_key] = interactive_func_def('edk2', '?', 'alg_module_init')
