# Note: you need to be using OpenAI Python v0.27.0 for the code below to work
import openai

from prompts.prompts import Prompt

api_key = "../openai.key"


def chat_with_gpt(message,  prompt:Prompt, model="gpt-3.5-turbo", temperature=0.7, max_tokens=2048):
    import openai

    openai.api_key_path = api_key

    # Format conversation messages
    formatted_messages = [
        {"role": "system", "content": ""},
        {"role": "user", "content": prompt.system},
        # {"role": "assistant","content": start_str},
        {"role": "user", "content": message}
    ]

    # Call the OpenAI API
    response = openai.ChatCompletion.create(
        model=model,
        messages=formatted_messages,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=0.9,
        frequency_penalty=0,
        presence_penalty=0,
    )

    # Extract the assistant's response
    assistant_message = response["choices"][0]["message"]["content"]

    print(assistant_message)

    # Extend the conversation via:
    formatted_messages.extend([response["choices"][0]["message"],
                               {"role": "user", "content": json_prompt}
                               ])
    response = openai.ChatCompletion.create(
        model=model,
        messages=formatted_messages,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=0.9,
        frequency_penalty=0,
        presence_penalty=0,
    )

    assistant_message = response["choices"][0]["message"]["content"]

    return assistant_message.strip()
