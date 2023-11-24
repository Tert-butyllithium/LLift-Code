
class Prompt:
    def __init__(self, system, json_gen, heading=None, continue_text=None):
        self.system = system
        self.json_gen = json_gen
        self.heading = heading
        self.continue_text = continue_text


simple_prompt = """
as a Linux kernel specialist, your task is to identify if there's any use-before-initialization bug 
in the provided context and variable use.

You should think step by step, analyze each code block thoroughly.

--------
suspicious variable: {var_name}
use point: {use_point}
code: 
{code_context}

"""



# version (v4.1-L) Nov 24, 2023

__initializer_extract_prompt = """
As a Linux kernel specialist, your task is to identify the function or functions, referred to as initializers, 
that may initialize a particular suspicious variable prior to its use, given the provided context and variable use.
If you encounter an asynchronous call like wait_for_completion, make sure to point out the "actual" initializer, which is typically delivered as a callback parameter.


Thinking step by step

--------
suspicious variable: {var_name}
use point: {use_point}
code: 
{code_context}
"""

__initializer_json_gen = """
----------------
Beased on the result, summerize it with a json format like:

{
   "initializer": "res = sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n)",
   "suspicious_variables": ["a", "b", "c", "d"],
}

For multiple initializations, respond as a list of the above objects.
"""



__preprocess_system_text = """
As a Linux kernel specialist, your task is to identify the postconstraint of a initializer (a function that may initialize a particular suspicious variable prior to its use) given the provided context and variable use.
 The postconstraint comprises constraints that must be met in order to progress from the initializer function to the variable use point. Here are the methods to identify postconstraints:

Type A. Prior to Variable Use:
Consider a scenario where a variable is used after a function check, such as:

```
if (sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n) >= 4) { // use of a, b, c, d }
```
Here, the postconstraint would be "ret_val>=4". Another variant (Type A') can be the use of switch(...) and the variable uses under a specific case:

```
switch(ret_val = func(..., &a)){
   case some_condi:
   …
   break;
   case critical_condi:
      use(a) // use of a
}
```
In this instance, since we're focused on the use of 'a', the postconstraint here is "critical_condi".

Type B. Return Code Failures:
In some cases, the function check happens before a return code failure, such as:

```
ret_val = func(..., &a); 
if (ret_val < 0) { return/break/ goto .../...; }
…
use(a) // use of a
```

In this scenario, the check is "ret_val>=0". For “goto,” you should also see the label and the the use point is under the label

Type B’. Retry:
In some cases, it will retry an initializer until it a success:


```
while(func(&a) ==0){
…
}
use(a)
```


In this case, you should consider the “last” initializer to make it break the endless loop and then, therefore, reach the “use.” Hence, the check is “func(&a) != 0).

If the suspicious variable is used in the iteration with the index, include the boundary of the index as a check

If there's NO explicit control change (like return, break, or goto) that prevents reaching the variable's use point, you should disregard it as it provides no guarantees. All functions can always return to their caller.

Again, if you feel uncertain about finding the check, you should always consider our “golden rule”: if it affects the reachability of use?

For multiple checks,  connect them with their relationships, i.e., && or ||.

Please remember that the context provided is complete and sufficient. You should not assume any hidden breaks or returns. Think step by step, analyze each code block thoroughly and establish the postconstraint according to these rules.

"""

__preprocess_system_summary = """
You are an Linux expert and you are required to identify the postconstraint of a initializer (a function that may initialize a particular suspicious variable prior to its use) given the provided context and variable use.

"""


__preprocess_continue_text = """
looking at the above analysis, thinking critique for the postconstraint with its context, consider the following:
- We only consider the case where the initializer is a function, and ignore it if it is not.
- if the initializer has a return value, you must include it assigning to its return value
- if our "use" is exactly a check, please directly ignore the check in your postconstraint extraction
- if there's no check (or, no check can be expressed in terms of return value/params), say "postconstraint": null
- for `goto`, you should consider carefully to see if the use is under its label, then conclude the postconstraint by include its condition or its `!condition`
- if one initializer has multiple checks, using boolean operators (&&, ||) to combine them
- Thinking step by step, and output the correct postconstraint
"""

__preprocess_json_gen = """
Conclude your analysis in a json format; for example:
{
   "initializer": "res = sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n)",
   "suspicious": ["a", "b", "c", "d"],
   "postconstraint": "res >=4"
}

For multiple initializations, respond as a list of the above objects.

If not any initializer, albeit rare, you should return an empty list:
{[]}

For initializer without any postconstraint, respond with "postconstraint": null

"""

# analyze: version v3.5 (Jul 5, 2023)
# upd: tweak self-refinement, listing some "always true" facts
__analyze_system_text = """
You are an experienced Linux program analysis expert. I am working on analyzing the Linux kernel for a specific type of bug called "use-before-initialization." I need your assistance in determining if a given function initializes the suspicious variables. 
Additionally, I will give you the postconstraint, which says something will hold after the function execution.

For example, with the postconstraint “sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n)>=4", we can conclude that function sscanf must initialize a,b,c,d, but don’t know for “n", so “may_init" for n.

If you find any early returns before the assignment statement that possibly makes it unreachable:
```
if(some_condition){
   return -1;
}
a = ... // init var a
```
In this case,  
- if we don't have any postconstraint, directly mark "a" as may_init since it could be unreachable
- if we have a postconstraint, the function must be satisfied after the function execution. For example, 
    1. if the postconstraint conflicts with the "some_conditon", makes the early return must not take
    2. if the final return statement in the if-body () conflicts with our postconstraint; for example, with postconstraint (return value != -1), we can infer this branch was never taken.
Once all non_init branches are unreachable, you can mark the variable as "must_init".

An uninitialized variable can propagate and pollute other variables, so you should consider the following:
If you see the suspicious variable to be assigned with another stack variable that is probably to be uninitialized, you should also figure out that variable's initialization.

There're some facts that we assume are always satisfied
- A return value of a function is always initialized
- the `address` of parameters are always "not NULL", unless it is explicitly "NULL" passed in

You should think step by step.
"""

__analyze_system_summary = """
As a Linux expert, you are required to summarize a function behavior, which is a function that may initialize a particular suspicious variable prior to its use,
 given the provided context and variable use, and the "post-constraint" that must be satisfied after the function execution.
"""


__analyze_continue_text = """
Review the analysis above carefully; consider the following:

1. All functions are callable, must return to the caller, and never crash. The system won't panic, trap in a while(1) loop or null pointer dereference.
2. If we have postconstraint, it must be satisfied after the function execution.
3. every function could return an error code (if it has return value); if there's a branch not init our suspicious variable and it can go, it must go and "may_init."

For unknown functions, if it is called under a return code check, you could assume this function init the suspicious var when it returns 0 and not init when it returns non-zero;
It can do anything if it is called without any checks (i.e., may_init).

If the condition of "may_init" happens to be the postconstraint or other common sense you consider true, you should change it to "must_init".

Common sense to be true:
1. constant you can calculate to be true: for example, sizeof(int)>0 or size of other variables where you know the type
2. The suspicious variable has a non-null address; i.e., &suspicious_var != NULL

If you already see some path can return and without any init, direct conclude it's "may_init" with "confidence: true".

thinking step by step,  conclude a correct and comprehensive answer
"""

__analyze_json_gen = """
based on the initialization analysis on a suspicious variable, convert it to json result. 
For each "may_init", you should also indicates its condition of initalization (or say "condition": "unknown" if you can't determine): 
The result should be simialr to the following format (NOTE: DON'T copy the comments in your result):
{
"ret": "success",
"response": {
 "must_init": ["a", "b", "c", "d"],
 "may_init": [{"name":"n", "condition": "ret_val > 4"}],
 "must_no_init": []
}
}
"""

__analyze_json_heading = 'Since `{}` is an unknown function, I will need its definition to continue the analysis. \n{{"ret": "need_more_info", "response": [{{"type": "function_def", "name": "{}"}}]}}'



####################

PreprocessPrompt = Prompt(__preprocess_system_text, __preprocess_json_gen, continue_text=__preprocess_continue_text)
AnalyzePrompt = Prompt(__analyze_system_text, __analyze_json_gen, __analyze_json_heading, continue_text=__analyze_continue_text)