
class Prompt:
    def __init__(self, system, json_gen, interacion_heading=None):
        self.system = system
        self.json_gen = json_gen
        self.interacion_heading = interacion_heading

# preprocess: version v2.6 (May 6, 2023)
__preprocess_system_text = """
Given the context and the suspicious variable, tell me which function that could initialize the variable before its use. Additionally, points out the after function calling check of the function if any.
The after function check (AFC) is defined as follow:
A. If a function call is executed within/after an immediate boolean condition judgment, as they may impact the initialization of the variables in question. For example:
if (sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n) >= 4) { // use of a, b, c, d }
Here, the post-condition ">=4" indicates that when this condition is true, the first four parameters (a, b, c, and d) must be initialized.
B. "earlier return" may occur due to a failed function call. For example,
ret_val = func(...); if (ret_val) { return/break; }
In these scenarios, you should consider that the function has run successfully (i.e., the AFC is `!ret_val`).
If you see some if(...) after the function call but don't observe any early returns that affect the control flow, you should say there's no AFC (AFC: None). For example:
if(...){//you don’t find any break or return}
All context I give you is complete and sufficient, you shouldn’t assume there are some hidden break or returns.
"""

__preprocess_json_gen = """
Based on you analyze above, generate a json format result like this:
{
   "callsite": "sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n)",
   "suspicous": ["a", "b", "c", "d"],
   "afc": "ret_val >=4"
}
if there's no afc, say "afc": null
"""

# analyze: version v2.6 (May 6, 2023)

__analyze_system_text = """
I am working on analyzing the Linux kernel for a specific type of bug called "use-before-initialization." I will need your assistance in determining if a given function initializes the specified suspicious variables. 
Additionally, I will give you the AFC(after call check), which says something will happen after the function execution.

For example, with afc “ret_val>=4”, for function call sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n),  we can conclude that function sscanf must initialize a,b,c,d, but don’t know for “n”, so “may_init” for n.

If the variable's initialization is unconditional, categorize it as "must_init." Otherwise, “may_init”.
Thinking step by step. After locating the initialization code, you should look backward for each “if-condition” that could make “early return” so that the program may not reach the line of initialization. You shouldn’t assume some function will always execute successfully; instead,  for example:
if(some_cond)
    break/return;
Var = …. // you see an initialization.

you should always assume both true and false branches are possible. The only exception is when the condition is equivalent to the afc we have. otherwise we can only say the var is “may_init” because we don’t know more about whether some_cond happens.

If you find that you cannot arrive at an answer without more information, such as a function definition, I will ask you to provide these additional details. In this case, you should end your answer with a JSON object in the following format

{ "ret": "need_more_info", "response": [ { "type": "function_def", "name": "func1" } ] }
And I’ll give you what you want, to do the analysis again. You can keep requests unless you have all your needs.

"""
__analyze_json_gen = """
Based on our discussion above, convert the analysis result to json format. You should tell me if "must_init", "may_init", or "must_no_init" for each suspicious variable.
If each "may_init",  you should indicates its condition (if applicable)):
For instance:

{
“ret”: “success”,
“response”: {
 "must_init": ["a", "b", "c", "d"],
 "may_init": ["n", "condition": "ret_val > 4"],
 "must_no_init": [],
}
}
"""


####################

PreprocessPrompt = Prompt(__preprocess_system_text, __preprocess_json_gen)
AnalyzePrompt = Prompt(__analyze_system_text, __analyze_json_gen)