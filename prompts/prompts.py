
class Prompt:
    def __init__(self, system, json_gen, interacion_heading=None):
        self.system = system
        self.json_gen = json_gen
        self.interacion_heading = interacion_heading

# preprocess: version v2.9 (Jun 3, 2023)
__preprocess_system_text = """
Given the context and the suspicious variable and its usage site (always the last line), tell me which function that could initialize the variable before its use. Additionally, you are required to perfrom a reachable analysis to point out the postcondition of the function.

The postcondition is something must happen to make the usage site reachable. The postcondition can be found in the following ways:

A. checks before using the values
if (sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n) >= 4) { // use of a, b, c, d }

Using "ret_val" to repredent the return value of `sscanf`, the post-condition "ret_val>=4" indicates that when this condition is true, the first four parameters (a, b, c, and d) must be initialized. And the postcondition is “ret_val>=4”.

There’s an alternative: switch(...) and the usages under some “case case1”. For example,
```
switch(ret_val = func(..., &a)){
 case big_failure:
   …
   break
   case big_success:
   // use of a
}
```

Since we only care about the use of a. We can say the postcondition here is only “big_success”

B. Return code failure check. E.g., if(func(..)<0) return

```
ret_val = func(..., &a); 
if (ret_val) { return/break; }
…
// use of a
```

In these scenarios, you should pay attention to  the if body; if it doesn't contain any explicit "early return" (return or break) that stops the program reaching the usage site, you should say there's no postcondition (postcondition: None). For example:
```
if(...){
do_something(...);
//you don’t find any break or return
}
```

if there mutiple checks, you should use boolean logics to connect multiple conditions, for example, “cond1&cond2”.

Think step by step.
"""

#upd (Jun 3, 2023): trying to add consideration for multiple initializations
__preprocess_json_gen = """
the postcondition should be expressed in the return value and/or parameters of the Initializer function.   And then write the result in a json format; for example:
{
   "initializer": "res = sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n)",
   "suspicious": ["a", "b", "c", "d"],
   "postcondition": "res >=4"
}
the initializer should include the return value, if any
if there's no postcondition (or can be expressed in terms of return value/params), say "postcondition": null
Thinking step by step, if there's multiple intialization, you should condier the varaible reuse; recall where the varaible being used, you should consider the exact one being used in our usage

"""

# analyze: version v2.7.4 (May 31, 2023)
# upd: define "intialization" more clearly: we don't 

__analyze_system_text = """
I am working on analyzing the Linux kernel for a specific type of bug called "use-before-initialization." I need your assistance determining if a given function initializes the suspicious variables. 
assigned to NULL should be considered as a valid initialization.
Additionally, I will give you the postcondition, which says something will hold after the function execution.

For example, with the postcondition “sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n)>=4”, we can conclude that function sscanf must initialize a,b,c,d, but don’t know for “n”, so “may_init” for n.

If the variable's initialization is unconditional, categorize it as "must_init." Otherwise, “may_init”.

If you find any early returns before the assignment statement that possibly makes it unreachable:
```
if(some_condition){
   return -1;
}
a = ... // init var a
```
In this case,  
- if we don't have any postcondition, directly mark "a" as may_init since it could be unreachable
- if we have postcondition, we have two things to determine whether this branch is being taken:
    1. if the postcondition conflicts with the "some_conditon", makes the early return must not take
    2. if the final return statement in the if-body () conflicts with our postcondition; for example, with postcondition (return value != -1), we can infer this branch was never taken.

Thinking step by step.
If you cannot arrive at an answer without more information, such as a function definition, I will ask you to provide these additional details. In this case, you should end your answer with a JSON object in the following format.

{ "ret": "need_more_info", "response": [ { "type": "function_def", "name": "func1" } ] }
And I’ll give you what you want to let you analyze it again.
"""
__analyze_json_gen = """
Based on our discussion above, convert the analysis result to json format. You should tell me if "must_init", "may_init", or "must_no_init" for each suspicious variable.
For each "may_init",  you should indicates its condition (if applicable)):
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