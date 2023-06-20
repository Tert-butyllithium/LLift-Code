
class Prompt:
    def __init__(self, system, json_gen, heading=None, continue_text=None):
        self.system = system
        self.json_gen = json_gen
        self.heading = heading
        self.continue_text = continue_text


# version v3.1 (June 17, 2023)
__preprocess_system_text = """
As a Linux kernel specialist, your task is to identify the function or functions, referred to as initializers, that may initialize a particular suspicious variable prior to its use, given the provided context and variable use.

If you encounter an asynchronous call like wait_for_completion, make sure to point out the "actual" initializer, which is typically delivered as a callback parameter.

Another important aspect you must highlight is the "postcondition" of the initializer. The postcondition comprises constraints that must be met in order to progress from the initializer function to the variable use point:

If there's NO explicit control change (like return, break, or goto) that prevents reaching the variable's use point, you should disregard it as it provides no guarantees. The function can be assumed to never fail or crash but can return any values.

For multiple checks, list them along with their relationships, i.e., && or ||.

Please remember that the context provided is complete and sufficient. You should not assume any hidden breaks or returns. Think step by step, analyze each code block thoroughly and establish the postcondition according to these rules.
"""

__preprocess_continue_text = """
looking back at the analysis, thinking more carefully for the postconidtion with its context, consider the following:
- substitute the postcondition with the context of use, is it complete for both prior to use and return code failure?
- We only consider cases the initializer should be a function, if it's not, ignore it
- the postcondition should be expressed in the return value and/or parameters of the initializer function, if can't, ignore it
- the postcondition should not come from the use itself, if it does, remove it
- the initializer should include the return value, if it was refered in the postcondition or suspicious variable
- You should mention the the type of each postcondition: "prior_use", "return_code_failure", or "both"
- if there's no postcondition (or can be expressed in terms of return value/params), say "postcondition": null
- Thinking step by step, if there are multiple initializations, you should respond with a list.
"""

__preprocess_json_gen = """
Conclude your analysis in a json format; for example:
{
   "initializer": "res = sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n)",
   "suspicious": ["a", "b", "c", "d"],
   "postcondition": "res >=4",
   "postcondition_type": "prior_use"
}

For multiple initializations, respond as:
[
 {"initializer":..., "suspicious": ..., "postcondition":... }, 
 {"initializer":...,  "suspicious": ..., "postcondition":... }
]

If not any initializer, albeit rare, you should return an empty list:
{[]}

"""

# analyze: version v3.0 (Jun 14, 2023)
# upd: using `system` instead of `user`, adapting for gpt-4-0613

__analyze_system_text = """
You are an experienced Linux program analysis expert. I am working on analyzing the Linux kernel for a specific type of bug called "use-before-initialization." I need your assistance determining if a given function initializes the suspicious variables. 
Additionally, I will give you the postcondition, which says something will hold after the function execution.

For example, with the postcondition “sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n)>=4", we can conclude that function sscanf must initialize a,b,c,d, but don’t know for “n", so “may_init" for n.

If you find any early returns before the assignment statement that possibly makes it unreachable:
```
if(some_condition){
   return -1;
}
a = ... // init var a
```
In this case,  
- if we don't have any postcondition, directly mark "a" as may_init since it could be unreachable
- if we have a postcondition, we have two things to determine whether this branch can be taken:
    1. if the postcondition conflicts with the "some_conditon", makes the early return must not take
    2. if the final return statement in the if-body () conflicts with our postcondition; for example, with postcondition (return value != -1), we can infer this branch was never taken.
Once all early returns are unreachable, you can mark the variable as "must_init".

You should think step by step.
Anytime you feel uncertain due to unknown functions, you should stop analysis and ask me to provide its definition(s) in this way:
{ "ret": "need_more_info", "response": [ { "type": "function_def", "name": "some_func" } ] }
And I’ll give you what you want to let you analyze it again.
"""

__analyze_json_gen = """
Looking back your analysis, "must_init" means the variable must be initialized with the postconidtion, initialized is defined with "assigned"; so NULL and error code are considered as initialization.
"may_init" is a safe answer, if you find some condition to make it not init, or you can't determine (say "confidence": false), you can say "may_init"

Then, based on the whole discussion above, convert the analysis result to json format. You should tell me if "must_init", "may_init", or "must_no_init" for each suspicious variable.
For each "may_init",  you should indicates its condition (if applicable)):
For instance:

{
"ret": "success",
"confidence": "true",
"response": {
 "must_init": ["a", "b", "c", "d"],
 "may_init": ["n", "condition": "ret_val > 4"],
 "must_no_init": []
}
}
"""

__analyze_json_haading = 'Since `{}` is an unknown function, I will need its definition to continue the analysis. \n{{"ret": "need_more_info", "response": [{{"type": "function_def", "name": "{}"}}]}}'



####################

PreprocessPrompt = Prompt(__preprocess_system_text, __preprocess_json_gen, continue_text=__preprocess_continue_text)
AnalyzePrompt = Prompt(__analyze_system_text, __analyze_json_gen, __analyze_json_haading)