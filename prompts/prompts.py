
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

Another important aspect you must highlight is the "postcondition" of the initializer. The postcondition comprises constraints that must be met in order to progress from the initializer function to the variable use point. Here are the methods to identify postconditions:

Type A. Prior to Variable Use:
Consider a scenario where a variable is used after a function check, such as:

```
if (sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n) >= 4) { // use of a, b, c, d }
```
Here, the postcondition would be "ret_val>=4". Another variant (Type A') can be the use of switch(...) and the variable uses under a specific case:

```
switch(ret_val = func(..., &a)){
   case some_condi:
   …
   break;
   case critical_condi:
      use(a) // use of a
}
```
In this instance, since we're focused on the use of 'a', the postcondition here is "critical_condi".

Type B. Return Code Failures:
In some cases, the function check happens before a return code failure, such as:

```
ret_val = func(..., &a); 
if (ret_val < 0) { return/break/ goto .../...; }
…
use(a) // use of a
```

In this scenario, the postcondition is "ret_val>=0".

If there's NO explicit control change (like return, break, or goto) that prevents reaching the variable's use point, you should disregard it as it provides no guarantees. The function can be assumed to never fail or crash but can return any values.

For multiple checks, list them along with their relationships, i.e., && or ||.

Please remember that the context provided is complete and sufficient. You should not assume any hidden breaks or returns. Think step by step, analyze each code block thoroughly and establish the postcondition according to these rules.
"""

__preprocess_continue_text = """
looking at the above analysis, thinking critique for the postcondition with its context, consider the following:
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

# analyze: version v3.2 (Jun 23, 2023)
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

There're some facts that we assume are always satisfied
- A return value of a function is always initialized
- the `adress` of parameters are always "not NULL", unless it is explicitly "NULL" passed in

You should think step by step.
Anytime you feel uncertain due to unknown functions, you should stop analysis and ask me to provide its definition(s) in this way:
{ "ret": "need_more_info", "response": [ { "type": "function_def", "name": "some_func" } ] }
And I’ll give you what you want to let you analyze it again.
"""


__analyze_continue_text = """
Review the analysis above carefully, initialized is defined with "assigned"; so NULL and error code are considered as valid initialization.
you should NOT assume a function could never return; and the system never goes crash, trap in a while(1) loop, or null pointer dereference.
All functions are callable, and must return with something and never crash.

For unknown functions, if it is called under a return code check, you could assume this function must init when it return 0, and must no init when it returns non-zero;
if it is called without any checks, then we can't have any assumpton.

"may_init" is a safe answer, if you find some condition to make it not init, or you can't determine (say "confidence": false), you can say "may_init"
if the condition of "may_init" is the the postcondition, or something must be true (e.g, sizeof(int)>0), you should classify it as "must_init".

reconsider the "may_init" and "must_init" and think step by step.
"""

__analyze_json_gen = """
based on our final result to json format. You should tell me if "must_init", "may_init", or "must_no_init" for each suspicious variable.

For each "may_init",  you should indicates its condition (if applicable, or say "condition": "unknown" if you can't determine):
For instance:
{
"ret": "success",
"confidence": "true",
"response": {
 "must_init": ["a", "b", "c", "d"],
 "may_init": [{"name":"n", "condition": "ret_val > 4"}],
 "must_no_init": []
}
}
"""

__analyze_json_haading = 'Since `{}` is an unknown function, I will need its definition to continue the analysis. \n{{"ret": "need_more_info", "response": [{{"type": "function_def", "name": "{}"}}]}}'



####################

PreprocessPrompt = Prompt(__preprocess_system_text, __preprocess_json_gen, continue_text=__preprocess_continue_text)
AnalyzePrompt = Prompt(__analyze_system_text, __analyze_json_gen, __analyze_json_haading, continue_text=__analyze_continue_text)