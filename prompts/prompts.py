
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
B. "earlier return" may occur due to a failed function call. In these scenarios, you need to analyze the code considering that the function has run successfully (i.e., the AFC is `!ret_val`). For example,
ret_val = func(...); if (ret_val) { return/break; }
If you don't observe any early returns that affect the control flow, assume there's no AFC. For example:
if(ret_val){//you don’t find any break or return}
"""

__preprocess_json_gen = """
Based on you analyze above, generate a json format result like this:
{
   "callsite": "sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n)",
   "suspicous": ["a", "b", "c", "d"],
   "afc": "ret_val >=4"
}
"""

# analyze: version v2.6 (May 6, 2023)

__analyze_system_text = """
I am working on analyzing the Linux kernel for a specific type of bug called "use-before-initialization." I will need your assistance in determining if a given function initializes the specified suspicious variables. 
Additionally, when you provide this information, please consider The after function check (AFC), which means something would happen after the function executed.
For example, with afc “ret_val>=4”, function sscanf must initialize a,b,c,d, but don’t know for “n”
if (sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n) >= 4) { // use of a, b, c, d }
If a variable's initialization depends on specific conditions or fields of other parameters, categorize it as "may_init." If the variable's initialization is unconditional, categorize it as "must_init." To do this, first analyze the post-condition, then examine the code that initializes the variable, and finally, determine if it is a "may_init" or "must_init."
Thinking step by step. You should look at them carefully for each “if-condition”, you should always assume both true and false branches are possible. Unless the condition is equivalent to the afc you have.
If you cannot analyze certain fields or variables without more information, such as a function definition, I will request that you provide these additional details. In such cases,  you should include a JSON object at the end of your response, formatted as follows
{ "ret": "need_more_info", "response": [ { "type": "function_def", "name": "func1" } ] }

"""
__analyze_json_gen = """
Based on our discussion above, convert the analysis result to json format. You should tell me if "must_init", "may_init", or "must_no_init" for each suspious varaiable. 
If each "may_init",  you should indicates its condition:
For instance:

{
“ret”: “success”,
“response”: {
  "func_call": "sscanf(str, \"%u.%u.%u.%u%n\", &a, &b, &c, &d, &n) >= 4",
  "varaibles": ["&a", "&b", "&c", "&d", "&n"],
  "must_init": ["&a", "&b", "&c", "&d"],
  "may_init": ["&n", "condition": "ret_val > 4"],
  "must_no_init": [],
}
}



"""


####################

preprocess_prompt = Prompt(__preprocess_system_text, __preprocess_json_gen)
analyze_prompt = Prompt(__analyze_system_text, __analyze_json_gen)