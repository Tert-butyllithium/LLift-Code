
class Prompt:
    def __init__(self, system, json_gen, heading=None, continue_text=None):
        self.system = system
        self.json_gen = json_gen
        self.heading = heading
        self.continue_text = continue_text


# version v3.0 (June 4, 2023)
__preprocess_system_text = """
Given the context, the suspicious variable, and its usage site, tell me which function(s) could initialize the variable before its use.
Additionally, you are required to point out the 
the postcondition of each initialization function by a simple reachability analysis.

The postcondition is constraints that must be satisfied to make the path from the initialization func to reach the usage site. The postcondition can be found in the following ways:

A. after function check, before its usage. E.g.,
if (sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n) >= 4) { // use of a, b, c, d }

And the postcondition is “ret_val>=4”.

An alternative is switch(...) and the usages under some “case case1”. For example,
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

B. after function check, return code failures. E.g., if(func(..)<0) return

```
ret_val = func(..., &a); 
if (ret_val) { return/break/ goto ...; }
…
// use of a
```

if it doesn't contain any explicit change the control (such as return, break, or goto) that stops reaching the usage site, you should directly ignore it cause it guarantees nothing. You should assume the function never fails/crashes but can return with any values. For example:
```
if(some_check){
do_something(...);
//you don’t find any break or return
}
```
This `some_check` should be ignored,

If there are multiple checks, you should list them and also indicate their relationships: && or ||

All context I give you is complete and sufficient; you shouldn’t assume there are some hidden breaks or returns. Think step by step. 
"""

__preprocess_continue_text = """
looking back at the analysis, consider the following:
- the postcondition should be expressed in the return value and/or parameters of the initializer function, if can't, ignore it
- the initializer should include the return value, if it was refered in the postcondition or suspicious variable
- A postcondtion must dirrectly affect the reachablity of the usage site; so for failure check, if there's no explicit return/break/goto... that makes the following use impossible, it should be ignored.
- if there's no postcondition (or can be expressed in terms of return value/params), say "postcondition": null
- Thinking step by step, if there are multiple initializations, you should respond with a list.
"""

__preprocess_json_gen = """
Conclude your analysis in a json format; for example:
{
   "initializer": "res = sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n)",
   "suspicious": ["a", "b", "c", "d"],
   "postcondition": "res >=4"
}

For multiple initializations, respond as:
[
 {"initializer":..., "postcondition":... }, 
 {"initializer":..., "postcondition":... }, 
]

"""

# analyze: version v2.7.4 (May 31, 2023)
# upd: define "intialization" more clearly: we don't 

__analyze_system_text = """
I am working on analyzing the Linux kernel for a specific type of bug called "use-before-initialization." I need your assistance determining if a given function initializes the suspicious variables. 
Additionally, I will give you the postcondition, which says something will hold after the function execution.

For example, with the postcondition “sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n)>=4”, we can conclude that function sscanf must initialize a,b,c,d, but don’t know for “n”, so “may_init” for n.

If you find any early returns before the assignment statement that possibly makes it unreachable:
```
if(some_condition){
   return -1;
}
a = ... // init var a
```
In this case,  
- if we don't have any postcondition, directly mark "a" as may_init since it could be unreachable
- if we have postcondition, we have two things to determine whether this branch can be taken:
    1. if the postcondition conflicts with the "some_conditon", makes the early return must not take
    2. if the final return statement in the if-body () conflicts with our postcondition; for example, with postcondition (return value != -1), we can infer this branch was never taken.
Once you find all early returns are unreachable, you can mark the variable as "must_init".

Thinking step by step.
Anytime you feel uncerten due to unknown functions, you should stop analysis, and ask me to provide its definition(s) in this way:
{ "ret": "need_more_info", "response": [ { "type": "function_def", "name": "some_func" } ] }
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

__analyze_json_haading = 'Since `{}` is an unknown function, I will need its definition to continue the analysis. \n{{"ret": "need_more_info", "response": [{{"type": "function_def", "name": "{}"}}]}}'



####################

PreprocessPrompt = Prompt(__preprocess_system_text, __preprocess_json_gen, continue_text=__preprocess_continue_text)
AnalyzePrompt = Prompt(__analyze_system_text, __analyze_json_gen, __analyze_json_haading)