
class Prompt:
    def __init__(self, system, json_gen, interacion_heading=None):
        self.system = system
        self.json_gen = json_gen
        self.interacion_heading = interacion_heading

# preprocess: version v2.8.2 (May 15, 2023)
__preprocess_system_text = """
Given the context and the suspicious variable and its usage site (always the last line), tell me which function that could initialize the variable before its use. Additionally, points out the postcondition of the function if any.

The postcondition is something must happen to reach our usage site (i.e., the last line of context I give to you). The postcondition can be found in the following ways:

A. checks before using the values
if (sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n) >= 4) { // use of a, b, c, d }

Using "ret_val" to repredent the return value of `sscanf`, the post-condition "ret_val>=4" indicates that when this condition is true, the first four parameters (a, b, c, and d) must be initialized. And the postcondition is “ret_val>=4”.

There’s an alternative: switch(...) and the usages under some “case case1”. For example,
switch(ret_val = func(..., &a)){
 case big_failure:
   …
   break
   case big_success:
   // use of a
}

Since we only care about the use of a. We can say the postcondition here is only “big_success”

B. Return code failure check. E.g., if(func(..)<0) return

ret_val = func(...); if (ret_val) { return/break; }
…
// use of suspicious variable
In these scenarios, you should consider what makes the code run to the use site (i.e., the postcondition is `!ret_val`).
If you see some if(...) after the function call but don't observe any early returns that affect the control flow, you should say there's no postcondition (postcondition: None). For example:
if(...){//you don’t find any break or return}
A function may have many disjoint postconditions, you need only consider the condition that could reach the use site. You should use boolean logics to connect multiple conditions if any, for example, “cond1&cond2”.
All context I give you is complete and sufficient, you shouldn’t assume there are some hidden breaks or returns. Think step by step and you should only consider the single path that could reach the usage site.
"""

__preprocess_json_gen = """
the postcondition should be expressed in the return value and/or parameters of the Initializer function.   And then write the result in a json format

{
   "initializer": "res = sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n)",
   "suspicious": ["a", "b", "c", "d"],
   "postcondition": "sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n) >=4"
}
the initializer should include the return value, if any
if there's no postcondition (or can be expressed in terms of ret_val/params), say "postcondition": null

"""

# analyze: version v2.7.4 (May 31, 2023)
# upd: define "intialization" more clearly: we don't 

__analyze_system_text = """
I am working on analyzing the Linux kernel for a specific type of bug called "use-before-initialization." I will need your assistance in determining if a given function initializes the specified suspicious variables. 
Here, I don't care if a variable is meaningfully assigned, we only care that no potentially garbage values are passed in that could become exploitable.
Additionally, I will give you the postcondition, which says something will hold after the function execution.

For example, with postcondition “sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n)>=4”, we can conclude that function sscanf must initialize a,b,c,d, but don’t know for “n”, so “may_init” for n.

If the variable's initialization is unconditional, categorize it as "must_init." Otherwise, “may_init”.

Thinking step by step. Postcondtion could imply more information beyond exact matches the condition,
for example, with postcondtion "ret_val != -1" and you see the code as follow:
```
if(some_condition){
   return -1;
}
a = ... // init var a
```
In this case, although you don't know what the condition here it is or match the postcondition, but if this happens, you know the return value is -1 and conflicts with the postcondition. 
Hence, this early return won't happen and the "a" is "must_init".

If you find that you cannot arrive at an answer without more information, such as a function definition, I will ask you to provide these additional details. In this case, you should end your answer with a JSON object in the following format

{ "ret": "need_more_info", "response": [ { "type": "function_def", "name": "func1" } ] }
And I’ll give you what you want, to let you analyze it again.


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