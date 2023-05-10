# Note: you need to be using OpenAI Python v0.27.0 for the code below to work
import logging
import openai
import json

from prompts.prompts import *
from dao.preprocess import Preprocess
from dao.logs import PrepLog

api_key = "../openai.key"


def _do_request(model, temperature, max_tokens, openai, formatted_messages):
    response = openai.ChatCompletion.create(
        model=model,
        messages=formatted_messages,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=0.9,
        frequency_penalty=0,
        presence_penalty=0,
    )

    return response


def call_gpt_preprocess(message, item_id, prompt=PreprocessPrompt, model="gpt-3.5-turbo", temperature=0.7, max_tokens=2048):
    openai.api_key_path = api_key

    # Format conversation messages
    formatted_messages = [
        {"role": "system", "content": ""},
        {"role": "user", "content": prompt.system},
        # {"role": "assistant","content": start_str},
        {"role": "user", "content": message}
    ]

    # Call the OpenAI API
    response = _do_request(model, temperature, max_tokens,
                           openai, formatted_messages)

    # Extract the assistant's response
    assistant_message = response["choices"][0]["message"]["content"]

    print(assistant_message)

    # Extend the conversation via:
    formatted_messages.extend([response["choices"][0]["message"],
                               {"role": "user", "content": prompt.json_gen}
                               ])
    response = _do_request(model, temperature, max_tokens,
                           openai, formatted_messages)

    assistant_message2 = response["choices"][0]["message"]["content"]

    plog = PrepLog(item_id, assistant_message, assistant_message2, model)
    plog.commit()

    return assistant_message2.strip()

def call_gpt_analysis(prep:Preprocess, prompt=AnalyzePrompt, model="gpt-3.5-turbo", temperature=0.7, max_tokens=2048):
    pass


def parse_json_response(response):
    """
    the response would be like:
    Based on the analysis above, the JSON format result is:
    {
        "callsite": "v4l2_subdev_call(cx->sd_av, vbi, decode_vbi_line, &vbi)",
        "suspicous": ["vbi.type"],
        "afc": null
    }
    """

    lines = response.split("\n")
    json_start, json_end = -1, -1
    for i, line in enumerate(lines):
        if json_start == -1 and line.startswith("{"):
            json_start = i
        if json_end == -1 and line.startswith("}"):
            json_end = i
            break

    if json_start == -1 or json_end == -1:
        raise Exception("invalid json response")

    json_str = "\n".join(lines[json_start:json_end+1])
    logging.info(f"json_str: {json_str}")
    return json.loads(json_str)


def do_preprocess(prep: Preprocess):
    if prep.preprocess is not None:
        return

    message = f"your first case is: \nsuspicous varaible: {prep.var_name}\n{prep.raw_ctx}"
    responce = call_gpt_preprocess(message, prep.id, PreprocessPrompt, model="gpt-4")
    print(responce)
    prep.preprocess = json.dumps(parse_json_response(responce))
    print(prep.preprocess)


def do_analysis(prep:Preprocess):
    if prep.analysis is not None:
        return