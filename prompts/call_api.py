# Note: you need to be using OpenAI Python v0.27.0 for the code below to work
import logging
import openai
import json

from prompts.prompts import *
from dao.preprocess import Preprocess
from dao.logs import PrepLog, AnalyzeLog
from helper.get_func_def import get_func_def_easy
from helper.parse_json import parse_json

api_key = "../openai.key"
openai.api_key_path = api_key


def _do_request(model, temperature, max_tokens, formatted_messages, _retry=0):
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
        if _retry < 3:
            return _do_request(model, temperature, max_tokens, formatted_messages, _retry + 1)
        return None

    return response


def call_gpt_preprocess(message, item_id, prompt=PreprocessPrompt, model="gpt-3.5-turbo", temperature=0.7, max_tokens=2048):

    # Format conversation messages
    formatted_messages = [
        {"role": "system", "content": ""},
        {"role": "user", "content": prompt.system},
        # {"role": "assistant","content": start_str},
        {"role": "user", "content": message}
    ]

    # Call the OpenAI API
    response = _do_request(model, temperature, max_tokens, formatted_messages)

    # Extract the assistant's response
    assistant_message = response["choices"][0]["message"]["content"]

    logging.info(assistant_message)

    # Extend the conversation via:
    formatted_messages.extend([{"role": "assistant", "content": assistant_message},
                               {"role": "user", "content": prompt.json_gen}
                               ])
    response = _do_request(model, temperature, max_tokens, formatted_messages)

    assistant_message2 = response["choices"][0]["message"]["content"]

    plog = PrepLog(item_id, assistant_message, assistant_message2, model)
    plog.commit()

    return assistant_message2.strip()


def call_gpt_analysis(prep: Preprocess, prompt=AnalyzePrompt, round=0, model="gpt-3.5-turbo", temperature=0.7, max_tokens=2048):
    prep_res = json.loads(prep.preprocess)
    # start with the result of preprocess

    cs = prep_res["callsite"]
    if type(cs) == list:
        cs = cs[0]
    func_def = get_func_def_easy(cs.split("(")[0])

    if func_def is None:
        return None

    formatted_messages = [
        {"role": "system", "content": ""},
        {"role": "user", "content": prompt.system},
        {"role": "user", "content": prep.preprocess},
        {"role": "user", "content": func_def}
    ]

    # for round in range(1):
    # Call the OpenAI API
    response = _do_request(model, temperature, max_tokens, formatted_messages)
    assistant_message = response["choices"][0]["message"]["content"]
    dialog_id = 0

    logging.info(assistant_message)
    alog = AnalyzeLog(prep.id, round, dialog_id,
                      prep.preprocess[:40], assistant_message, model)
    alog.commit()

    # interactive process
    while True:
        json_res = parse_json(assistant_message)
        if json_res is None:  # finish the analysis
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

            if not func_def_not_null:
                break

            formatted_messages.extend([{"role": "assistant", "content": assistant_message},
                                       {"role": "user", "content": provided_defs}
                                       ])
            response = _do_request(
                model, temperature, max_tokens, formatted_messages)
            assistant_message = response["choices"][0]["message"]["content"]
            dialog_id += 1
            alog = AnalyzeLog(prep.id, round, dialog_id,
                              provided_defs[:40], assistant_message, model)
            alog.commit()

    # let it generate a json output, and save the result
    # Extend the conversation via:
    formatted_messages.extend([response["choices"][0]["message"],
                               {"role": "user", "content": prompt.json_gen}
                               ])
    response = _do_request(model, temperature, max_tokens, formatted_messages)
    dialog_id += 1
    alog = AnalyzeLog(prep.id, round, dialog_id,
                      prompt.json_gen[:40], assistant_message, model)
    alog.commit()
    return parse_json(response["choices"][0]["message"]["content"])


def do_preprocess(prep: Preprocess):
    if prep.preprocess is not None:
        return

    message = f"your first case is: \nsuspicous varaible: {prep.var_name} that being used in the line of \n{prep.raw_ctx}"
    responce = call_gpt_preprocess(
        message, prep.id, PreprocessPrompt, model="gpt-4")
    print(responce)
    prep.preprocess = json.dumps(parse_json(responce))
    print(prep.preprocess)


def do_analysis(prep: Preprocess):
    if prep.analysis is not None:
        return
    response = call_gpt_analysis(prep, AnalyzePrompt, model="gpt-4")
    print(response)
    prep.analysis = json.dumps(response)
