# Note: you need to be using OpenAI Python v0.27.0 for the code below to work
import logging
from time import sleep
import openai
import json

from prompts.prompts import *
from dao.preprocess import Preprocess
from dao.logs import PrepLog, AnalyzeLog
from helper.get_func_def import get_func_def_easy
from helper.parse_json import parse_json

api_key = "../openai.key"
openai.api_key_path = api_key
trivial_funcs = json.load(open("prompts/trivial_funcs.json", "r"))


def _do_request(model, temperature, max_tokens, formatted_messages, _retry=0, last_emsg=None):
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=formatted_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.9,
            frequency_penalty=0,
            presence_penalty=0,
        )
    except Exception as e:
        logging.error(e)
        emsg = str(e)
        # if "error_code=None" in emsg: # ???
        #     return emsg
        if last_emsg is not None and emsg[:60] == last_emsg[:60]:
            logging.info("Same error")
            return '{"ret": "failed", "response": "'+ emsg[:200] + '"}'


        if _retry < 3 and ("context_length_exceeded" not in emsg):
            # if last_emsg is not None and str(e)[:60] == str(last_emsg)[:60]:
            #     logging.info("Same error")
            #     return '{"ret": "failed", "response": "'+ str(e)[:200] + '"}'
            sleep(1)
            logging.info(f"Retrying {_retry + 1} time(s)...")
            return _do_request(model, temperature, max_tokens, formatted_messages, _retry + 1, emsg)
        else:
            return '{"ret": "failed", "response": "'+ emsg[:200] + '"}'

    return response["choices"][0]["message"]["content"]


def call_gpt_preprocess(message, item_id, prompt=PreprocessPrompt, model="gpt-3.5-turbo", temperature=0.7, max_tokens=2048):

    # Format conversation messages
    formatted_messages = [
        {"role": "system", "content": ""},
        {"role": "user", "content": prompt.system},
        # {"role": "assistant","content": start_str},
        {"role": "user", "content": message}
    ]

    # Call the OpenAI API
    assistant_message = _do_request(model, temperature, max_tokens, formatted_messages)

    # Extract the assistant's response
    # assistant_message = response["choices"][0]["message"]["content"]

    logging.info(assistant_message)

    # Extend the conversation via:
    formatted_messages.extend([{"role": "assistant", "content": assistant_message},
                               {"role": "user", "content": prompt.json_gen}
                               ])
    assistant_message2 = _do_request(model, temperature, max_tokens, formatted_messages)

    # assistant_message2 = response["choices"][0]["message"]["content"]

    plog = PrepLog(item_id, assistant_message, assistant_message2, model)
    plog.commit()

    return assistant_message2.strip()


def call_gpt_analysis(prep: Preprocess, prompt=AnalyzePrompt, round=0, model="gpt-3.5-turbo", temperature=0.7, max_tokens=2048):
    prep_res = json.loads(prep.preprocess)
    # start with the result of preprocess

    # some ugly code to make compatible
    if "initializer" in prep_res:
        prep_res["callsite"] = prep_res["initializer"]
        prep_res.pop("initializer")

    cs = prep_res["callsite"]
    if type(cs) == list:
        cs = cs[0]
    if cs == None:
        logging.error(f"no call site info!")
        # return '{"ret": "failed", "response": "no call site info!"}'
        return {"ret": "failed", "response": "no call site info!"}
    
    # remove the return value 
    if '=' in cs:
        cs = cs[len(cs.split("=")[0])+1:].strip()
    func_name = cs.split("(")[0]
    func_def = get_func_def_easy(func_name)

    if func_def is None:
        logging.error(f"Cannot find function definition in {cs}")
        # return '{"ret": "failed", "response": ' + f"Cannot find function definition in {cs}" + '}'
        return {"ret": "failed", "response": f"Cannot find function definition in {cs}"}

    prep_res_str = str(prep_res)

    formatted_messages = [
        {"role": "system", "content": ""},
        {"role": "user", "content": prompt.system},
        {"role": "user", "content": prep_res_str},    
    ]
    if func_name not in trivial_funcs:
        formatted_messages.append({"role": "user", "content": func_def})

    # for round in range(1):
    # Call the OpenAI API
    assistant_message = _do_request(model, temperature, max_tokens, formatted_messages)
    # assistant_message = response["choices"][0]["message"]["content"]
    dialog_id = 0

    if  assistant_message.startswith('{"ret": "failed", "response": "'):
        # logging.error(assistant_message)
        return json.loads(assistant_message)

    logging.info(assistant_message)
    alog = AnalyzeLog(prep.id, round, dialog_id,
                      prep_res_str[:50], assistant_message, model)
    alog.commit()
    formatted_messages.extend([{"role": "assistant", "content": assistant_message}])

    

    # interactive process
    while True:
        json_res = parse_json(assistant_message)
        if json_res is None or "ret" not in json_res:  # finish the analysis
            break
        if json_res["ret"] == "need_more_info":
            provided_defs = "Here it is, you can continue asking for more functions.\n"
            func_def_not_null = False
            for require in json_res["response"]:
                if require["type"] == "function_def":
                    func_def = get_func_def_easy(require["name"])
                    if func_def is not None:
                        func_def_not_null = True
                        provided_defs += func_def + "\n"
                    else:
                        logging.error(f"function {require['name']} not found")
                        #TODO(need to handle when the function is not found)
                        pass

            if not func_def_not_null:
                break

            formatted_messages.extend([
                                       {"role": "user", "content": provided_defs}
                                       ])
            assistant_message = _do_request(
                model, temperature, max_tokens, formatted_messages)
            # assistant_message = response["choices"][0]["message"]["content"]
            dialog_id += 1
            alog = AnalyzeLog(prep.id, round, dialog_id,
                              provided_defs[:40], assistant_message, model)
            alog.commit()
            formatted_messages.append({"role": "assistant", "content": assistant_message})

    # let it generate a json output, and save the result
    # Extend the conversation via:
    formatted_messages.extend([
                               {"role": "user", "content": prompt.json_gen}
                               ])
    assistant_message = _do_request(model, temperature, max_tokens, formatted_messages)
    # assistant_message = response["choices"][0]["message"]["content"]
    dialog_id += 1
    alog = AnalyzeLog(prep.id, round, dialog_id,
                      prompt.json_gen[:40], assistant_message, model)
    alog.commit()
    return parse_json(assistant_message)

#TODO bug: if the return value reuses the parameter name
def warp_postcondition(postcondition:str, initializer):
    """
    warp the postcondition if:
    - the initializer retutrn a value and save it to a variable
    - the postcondition use the variable
    """
    if postcondition is None:
        return None
    
    if '=' not in initializer:
        return postcondition
    if initializer[-1] == ';':
        initializer = initializer[:-1]
    
    ret_val_name = initializer.split("=")[0].strip()

    if " " in ret_val_name: # contains type
        ret_val_name = ret_val_name.split(" ")[-1].strip()
    initializer_call = initializer.split("=")[1].strip()

    # Workaround: if return value reuses a parameter
    if ret_val_name in initializer_call:
        return postcondition

    return postcondition.replace(ret_val_name, initializer_call)

    
    

def do_preprocess(prep: Preprocess, retry=0):
    if retry > 3:
        logging.error("ChatGPT not output in our format with tries > 3")
        return "failed > 3"

    use_site = prep.raw_ctx.strip().split("\n")[-1].strip()
    message = f"suspicous varaible: {prep.var_name}\nusage site: {use_site}\n\nCode:\n{prep.raw_ctx}"
    print(message)
    responce = call_gpt_preprocess(
        message, prep.id, PreprocessPrompt, model="gpt-4")
    print(responce)
    # try:
    responce = parse_json(responce)
    responce['postcondition'] = warp_postcondition(responce['postcondition'], responce['initializer'])

    return json.dumps(responce)
    # except:
    #     logging.error("ChatGPT not output in our format, try again", retry)
    #     return do_preprocess(prep, retry+1)


def do_analysis(prep: Preprocess):
    response = call_gpt_analysis(prep, AnalyzePrompt, model="gpt-4", max_tokens=3000, temperature=0.7)
    print(response)
    return json.dumps(response)
