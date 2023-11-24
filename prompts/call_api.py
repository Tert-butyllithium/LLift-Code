# Note: you need to be using OpenAI Python v0.27.0 for the code below to work
import logging
from time import sleep
import openai
import json

from prompts.prompts import *
from dao.preprocess import Preprocess
from dao.logs import PreprocessLog, AnalysisLog
from helper.get_func_def import get_func_def_easy
from helper.parse_json import parse_json

from common.config import PREPROCESS_ONLY, SELF_VALIDATE, ENABLE_PP, SIMPLE_MODE

# it may not be a real openai key
api_key = "../anyscale.key"
openai.api_key = open(api_key, "r").read().strip()
openai.api_base = 'https://api.endpoints.anyscale.com/v1'
trivial_funcs = json.load(open("prompts/trivial_funcs.json", "r"))
exclusive_funcs = json.load(open("prompts/exclusive_funcs.json", "r"))



# if enable pp:
_provide_func_heading_with_pp = "Here is the function of {}, you can continue asking for other functions with that json format I mentioned .\n"
_provide_func_heading = "Here is the function of {}\n" if not ENABLE_PP else _provide_func_heading_with_pp
_system_ending_with_pp = """
Anytime you feel uncertain due to unknown functions, you should stop analysis and ask me to provide its definition(s) in this way:
{ "ret": "need_more_info", "response": [ { "type": "function_def", "name": "some_func" } ] }
"""
AnalyzePrompt.system += _system_ending_with_pp if ENABLE_PP else ''


__split_str = "\n--------\n"

class PreprocessRequest:
    def __init__(self, var_name, use_point, code_context):
        self.var_name = var_name
        self.use_point = use_point
        self.code_context = code_context
    
    def __str__(self):
        return f"suspicious varaible: {self.var_name}\nuse: {self.use_point}\n\nCode:\n{self.code_context}"


def _do_request(model, temperature, max_tokens, formatted_messages, _retry=0, last_emsg=None):
    sleep(0.01) # avoid rate limit
    if "--" in model:
        model = model.split("--")[0]
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=formatted_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.9,
            frequency_penalty=1.02,
            presence_penalty=1.02,
        )
    except Exception as e:
        logging.error(e)
        emsg = str(e)
    
        if "502 Bad Gateway" in emsg and _retry < 3:
            sleep(1)
            logging.info(f"Retrying {_retry + 1} time(s)...")
            return _do_request(model, temperature, max_tokens, formatted_messages, _retry + 1, emsg)
        
        if "PromptTooLongError" or "maximum context length" in emsg:
            return '{"ret": "failed", "response":  "Too long"}'

        if last_emsg is not None and emsg[:60] == last_emsg[:60]:
            logging.info("Same error")
            return '{"ret": "failed", "response": "' + emsg[:20] + '"}'
        

        if _retry < 3 and ("context_length_exceeded" not in emsg):
            sleep(1)
            logging.info(f"Retrying {_retry + 1} time(s)...")
            return _do_request(model, temperature, max_tokens, formatted_messages, _retry + 1, emsg)
        else:
            return '{"ret": "failed", "response": "' + emsg[:200] + '"}'

    return response["choices"][0]["message"]["content"]

from prompts.prompts import __initializer_extract_prompt, __initializer_json_gen, __preprocess_system_text,  __preprocess_json_gen
from prompts.prompts import __analyze_system_summary, __preprocess_system_summary, __preprocess_continue_text

def call_gpt_preprocess(message, item_id, prompt, model, temperature, max_tokens=2048):
    initalize_prompt = __initializer_extract_prompt.format(
        var_name=message.var_name, use_point=message.use_point, code_context=message.code_context)
    

    # Format conversation messages
    formatted_messages = [
        {"role": "user", "content": initalize_prompt},
    ]

    # Call the OpenAI API
    assistant_message = _do_request(
        model, temperature, max_tokens, formatted_messages)

    # Extract the assistant's response
    # assistant_message = response["choices"][0]["message"]["content"]

    logging.info(assistant_message)


    ## let itself generate the json


    # Step 1: get the initalizer
    new_prompt = initalize_prompt + __split_str + "The analysis result: " + assistant_message + __split_str + __initializer_json_gen
    formatted_messages= [{"role": "user", "content": new_prompt},
                               ]
    assistant_message2 = _do_request(
        model, temperature, max_tokens, formatted_messages)

    plog = PreprocessLog()
    plog.commit(item_id, assistant_message, assistant_message2, model)


    # Step 2: get the postconstraint
    
    formatted_messages = [{"role": "user", "content": 
                           __preprocess_system_text + __split_str + assistant_message2 + __split_str + initalize_prompt }]
    

    assistant_message3 = _do_request(
         model, temperature, max_tokens, formatted_messages)
    
    logging.info(assistant_message3)

    plog = PreprocessLog()
    plog.commit(item_id, "[LOC PC]"+ formatted_messages[0]["content"], assistant_message3, model)


    if SELF_VALIDATE:
        prompt = __preprocess_system_summary + __split_str + __initializer_extract_prompt.format(
            var_name=message.var_name, use_point=message.use_point, code_context=message.code_context
            ) + __split_str + "The analysis result: " + assistant_message3 + __split_str + __preprocess_continue_text
        
        formatted_messages = [{"role": "user", "content": prompt}]
        assistant_message3 = _do_request(
            model, temperature, max_tokens, formatted_messages)
        logging.debug(assistant_message3)
        plog = PreprocessLog()
        plog.commit(item_id, "[SV]"+ prompt, assistant_message3, model)

    # logging.info(assistant_message2)
    # Step 4: get the json
    formatted_messages = [{"role": "user", "content": 
                           __preprocess_system_summary + __split_str + assistant_message2 + __split_str + initalize_prompt + __split_str + assistant_message3 + __preprocess_json_gen }]
    logging.debug(formatted_messages[0]["content"])
    assistant_message4 = _do_request(
         model, temperature, max_tokens, formatted_messages)
    logging.info(assistant_message4)


    plog = PreprocessLog()
    plog.commit(item_id, assistant_message, assistant_message4, model)

    return assistant_message4.strip()


def call_gpt_analysis(prep, case, prompt, round, model, temperature, max_tokens=2048):
    if PREPROCESS_ONLY:
        return '{"ret": "failed", "response": "PREPROCESS_ONLY"}'

    if SIMPLE_MODE:
        use_site = case.raw_ctx.strip().split("\n")[-1].strip()
        system_prompt = simple_prompt.format(var_name=case.var_name, use_point=use_site, code_context=case.raw_ctx)
        prep_res_str = system_prompt
        _provide_func_heading = ""
    else:
        _provide_func_heading = "Here is the function of {}\n"
        prep_res = json.loads(prep.initializer)

        # cs = prep_res["initializer"] if "initializer" in prep_res else prep_res["initializers"]
        if "initializer" in prep_res:
            cs = prep_res["initializer"]
        elif "initializers" in prep_res:
            cs = prep_res["initializers"]
        else:
            logging.error(f"no call site info!")
            return {"ret": "failed", "response": "no call site info!"}

        if type(cs) == list and len(cs) > 0:
            cs = cs[0]
        if cs == None:
            logging.error(f"no call site info!")
            return {"ret": "failed", "response": "no call site info!"}
        # remove the return value
        if '=' in cs:
            cs = cs[len(cs.split("=")[0])+1:].strip()
        if type(cs) != str:
            logging.error(f"callsite info with wrong format!")
            return {"ret": "failed", "response": "no call site info!"}
        func_name = cs.split("(")[0]
        func_def = get_func_def_easy(func_name)
        if func_def is None:
            logging.error(f"Cannot find function definition in {cs}")
            return {"ret": "failed", "response": f"Cannot find function definition in {cs}"}

        # not adding more context
        # ctx = case.raw_ctx.split("\n")
        # call_ctx_lines = min(10, len(ctx))
        # calling_ctx = "\n".join(ctx[:-call_ctx_lines])
        # prep_res_str = str(prep_res) + "\nCall Context: ...\n" + calling_ctx
        prep_res_str = str(prep_res)

        # formatted_messages = [
        #     {"role": "system", "content": prompt.system},
        #     # {"role": "user", "content": prompt.system},
        #     {"role": "user", "content": prep_res_str},
        # ]
        system_prompt = prompt.system + __split_str  + prep_res_str 

        _provide_func_heading = "\nand the function of {} is:\n".format(func_name)
        if func_name not in trivial_funcs:
            _provide_func_heading += func_def
            system_prompt += _provide_func_heading
        else:
            _provide_func_heading = ""
    

    # logging.info(formatted_messages[-1])
    logging.info(system_prompt)

    formatted_messages = [{"role": "user", "content": system_prompt}]

    # Call the OpenAI API
    assistant_message = _do_request(
        model, temperature, max_tokens, formatted_messages)
    # assistant_message = response["choices"][0]["message"]["content"]
    dialog_id = 0

    if assistant_message.startswith('{"ret": "failed", "response": "'):
        # logging.error(assistant_message)
        return json.loads(assistant_message)

    logging.info(assistant_message)
    alog = AnalysisLog()
    alog.commit(prep.id, round, dialog_id,
                prep_res_str[:50], assistant_message, model)
    

    # formatted_messages.extend(
    #     [{"role": "assistant", "content": assistant_message}])
    
    # formatted_messages = [{"role": "user", "content": second_prompt}]

    # interactive process
    while ENABLE_PP:
        json_res = parse_json(assistant_message)
        if json_res is None or "ret" not in json_res:  # finish the analysis
            break
        if json_res["ret"] == "need_more_info":
            is_func_def = False
            provided_defs = ""
            for require in json_res["response"]:
                if require["type"] == "function_def":
                    is_func_def = True
                    required_func = require["name"]
                    if 'name' not in require:
                        logging.error(f"function '{required_func}' doesn't have a 'name'")
                        provided_defs += f"No function in your request, please directly perfrom analysis\n"
                        continue

                    func_def = get_func_def_easy(require["name"])
                    if func_def is not None:
                        provided_defs += func_def + "\n"
                    else:
                        logging.error(f"function {require['name']} not found")
                        provided_defs += f"Sorry, I don't find function {require['name']}, try to analysis with your expertise in Linux kernel\n \
                                           If this function is called under a return code check, you could assume this function must init when it return 0, and must no init when it returns non-zero \n"
                else:
                    provided_defs += f"Sorry, no information of {require} I can provide, try to analysis with your expertise in Linux kernel\n"

            if is_func_def:
                provided_defs = _provide_func_heading_with_pp.format(required_func) + provided_defs
            else:
                provided_defs = "" + provided_defs

            # formatted_messages.extend([
            #     {"role": "user", "content": provided_defs}
            # ])
            pp_prompt =  system_prompt  +  __split_str + provided_defs
            formatted_messages = [{"role": "user", "content": pp_prompt}]

            
            assistant_message = _do_request(
                model, temperature, max_tokens, formatted_messages)
            logging.info(assistant_message)
            dialog_id += 1
            alog = AnalysisLog()
            alog.commit(prep.id, round, dialog_id,
                        provided_defs[:100], assistant_message, model)

            # formatted_messages.append(
            #     {"role": "assistant", "content": assistant_message})
        else:
            break

    # let it generate a json output, and save the result
    # ignore interative messages
    # json_gen_msg = formatted_messages[:3] 
    # json_gen_msg += formatted_messages[-2:]
    
    # json_gen_msg += [
    #     {"role": "assistant", "content": assistant_message_final},
    #     {"role": "user", "content": prompt.json_gen}
    # ]
    # formatted_messages.extend([
    #     {"role": "user", "content": prompt.json_gen}
    # ])
    # second_prompt = assistant_message + __split_str + "Ananlysis result: \n" + assistant_message + __split_str + prompt.json_gen

    if SELF_VALIDATE:
        # self-validate the previous result
        self_valid_prompt = __analyze_system_summary+ __split_str + prep_res_str + _provide_func_heading + __split_str +  "Ananlysis result: \n" 

        self_valid_prompt += assistant_message + __split_str + prompt.continue_text

        logging.debug(self_valid_prompt)
        formatted_messages = [{"role": "user", "content": self_valid_prompt}]
        assistant_message = _do_request(
            model, temperature, max_tokens, formatted_messages)
        logging.info(assistant_message)
        dialog_id += 1

        alog = AnalysisLog()
        alog.commit(prep.id, round, dialog_id, self_valid_prompt[:40], assistant_message, model)


    second_prompt =  "Summarize the analysis below: " +  __split_str +  "Analysis request: \n" + prep_res_str + _provide_func_heading
    second_prompt +=  __split_str +   "Ananlysis result: \n" +  assistant_message +  __split_str + prompt.json_gen
    formatted_messages = [{"role": "user", "content": second_prompt}]
    logging.info(second_prompt)
    assistant_message = _do_request(
        model, temperature, max_tokens, formatted_messages)
    # assistant_message = response["choices"][0]["message"]["content"]
    dialog_id += 1
    alog = AnalysisLog()
    alog.commit(prep.id, round, dialog_id,
                prompt.json_gen[:40], assistant_message, model)
    return parse_json(assistant_message)




# TODO bug: if the return value reuses the parameter name
# TODO: do we really needs it?
def wrap_postconstraint(postconstraint: str, initializer):
    """
    wrap the postconstraint if:
    - the initializer retutrn a value and save it to a variable
    - the postconstraint use the variable
    """
    if postconstraint is None:
        return None

    if initializer is None or '=' not in initializer:
        return postconstraint
    if initializer[-1] == ';':
        initializer = initializer[:-1]



    ret_val_name = initializer.split("=")[0].strip()

    if " " in ret_val_name:  # contains type
        ret_val_name = ret_val_name.split(" ")[-1].strip()
    initializer_call = initializer.split("=")[1].strip()

    # init_call_func_name = initializer_call.split("(")[0]

    # Workaround: if return value reuses a parameter
    # if ret_val_name in initializer_call[len(init_call_func_name):]:
    #     return postconstraint

    if type(postconstraint) == str:
        return postconstraint.replace(ret_val_name, initializer_call)
    else:
        return postconstraint



# change the name of return_value to `func_ret_val` and change them in postconstraint and suspicious_vars
def wrap_ret_value(suspicious_vars: list, initializer: str, postconstraint: str):
    """
    wrap the ret_value if:
    - return value is the suspicious variable
    - @param suspicious_vars: list of suspicious variables
    - @param initializer: the initializer
    - @return: the new suspicious variables and the new initializer
    """
    if suspicious_vars is None or initializer is None:
        return suspicious_vars, initializer, postconstraint
    
    if type(suspicious_vars) is str:
        suspicious_vars = [suspicious_vars]

    if '=' not in initializer:
        return suspicious_vars, initializer, postconstraint

    if initializer[-1] == ';':
        initializer = initializer[:-1]

    ret_val_name = initializer.split("=")[0].strip()


    initializer = initializer.replace(ret_val_name, "func_ret_val", 1)
    
    if ret_val_name in suspicious_vars:
        suspicious_vars.remove(ret_val_name)
        suspicious_vars.append("func_ret_val")
    
    if type(postconstraint) == list:
        for i, post in enumerate(postconstraint):
            if ret_val_name in post:
                postconstraint[i] = post.replace(ret_val_name, "func_ret_val", 1)
    elif type(postconstraint) == str:
        if ret_val_name in postconstraint:
            postconstraint = postconstraint.replace(ret_val_name, "func_ret_val", 1)

    return suspicious_vars, initializer, postconstraint


def do_preprocess(prep,  model, temperature):
    if SIMPLE_MODE:
        return '{"initializer": "__simple_mode_dummy(var)", "suspicious": ["var"], "postconstraint": null}'

    use_site = prep.raw_ctx.strip().split("\n")[-1].strip()
    message = PreprocessRequest(prep.var_name, use_site, prep.raw_ctx)
    print(message)
    responce = call_gpt_preprocess(
        message, prep.id, PreprocessPrompt, model, max_tokens=1024, temperature=temperature)
    print(responce)

    responce = parse_json(responce)
    # if "initializer" in responce:
    #     responce = responce["initializer"]
    if "initializers" in responce:
        responce = responce["initializers"]

    if 'postconstraints' in responce:
        responce['postconstraint'] = responce['postconstraints']
    


    # try not do the wrap
    if 'postconstraint' not in responce:
        try_found = False
        try:
            if type(responce) == list:
                response_iterator = responce
            else:
                # {"intializers":[{...}, {...}]}
                response_iterator = next(responce.values())
            if type(response_iterator) == list and 'postconstraint' in response_iterator[-1]:
                response_iterator.reverse()
                for item in response_iterator:
                    func_call = item['initializer']
                    exclude = False
                    for exclus in exclusive_funcs:
                        if exclus in func_call:
                            exclude = True
                            break
                    if exclude:
                        continue
                    responce = item
                    # responce['postconstraint'] = wrap_postconstraint(
                    #     responce['postconstraint'], responce['initializer'])
                    try_found = True
                    break
            # assert responce['postconstraint'] is None or type(responce['postconstraint']) == str
            # try_found = True
        except Exception:
            pass

        if not try_found:
            logging.error("ChatGPT not output in our format: ", responce)
            return json.dumps(responce)
    
    
    # if 'postconstraint' in responce and 'initializer' in responce and 'suspicous_variable' in responce:
    #     # responce['suspicious'], responce['initializer'], responce['postconstraint'] = wrap_ret_value(
    #     #     responce['suspicious'], responce['initializer'], responce['postconstraint'])
    #     pass
    # else:
    #     logging.error("ChatGPT not output in our format: ", responce)
    return json.dumps(responce)


def do_analysis(prep, round, case, model, temperature):
    response = call_gpt_analysis(
        prep, case, AnalyzePrompt, round, model, max_tokens=1024, temperature=temperature)
    print(response)
    return json.dumps(response)
