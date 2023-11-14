
class Prompt:
    def __init__(self, system, json_gen, heading=None, continue_text=None):
        self.system = system
        self.json_gen = json_gen
        self.heading = heading
        self.continue_text = continue_text


# version v4.0 (Jul 23, 2023)
# upd: change to "relevant_constraints"
__preprocess_system_text = """
You should act as a experienced Linux kernel expert. Please following the below instructions to finish the task.

Context:
There are some Linux kernel functions that might initialize a particular suspect variable before it is used.
The "initializer" must be a function, and must be the "actual" function that intilizes the variable.

After the particular suspect variable is initialized, it may be used. The "use" can be to pass it as a parameter to another function, or to assign it to another variable, or to use it in a condition check, etc.
But there are some condition checks which determine if the use of the particular suspect variable will happen or not.
The initializer function may return value to be checked, for example, the error code to tell if the initialization is successful.  
If the condition check is passed, the use of the particular suspect variable will happen. Otherwise, the use will not happen.
We call such condtion checks as "postcondition", which comprises constraints that must be met in order to progress from the initializer function to the variable use point.

Objective:
I will provide you a piece of Linux kernel codes to be analyzed. The codes are not a whole function, but it contains the complete semantics to finish the below task.

Your first task is to identify the initializer functions that might initialize a particular suspect variable before using it based on the provided context and variable usage.
Your second task is to identify the posticondtion, which are conditions that must be met to make a particular suspect variable be used after the initilization.
I will provide you the source code which the use of the particular suspect variable happens. You should identify the condtions to make the use of the particular suspect variable happen.

Examples:
To help you solve the second task, I provide you the following typical examples of checks, so you can refer:

Type A. Prior to Variable Use:
Consider a scenario where a variable is used after a function check, such as:
```
if (sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n) >= 4) { // use of a, b, c, d }
```
Here, if value of "sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n)" >= 4, the program uses a,b,c,d. So the condition is to check the return value of the 'sscanf' function.
To make the use happen, the return value must statisfy ">= 4". So the postcondition is "sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n) >= 4".

Beside the above if condition check for the return value, there is another varianct when there is a switch(...) checking statement.
The switch checking statement is similar to the if condition check, but it is used to check the return value of the function under a specific case:
```
switch(ret_val = func(..., &a)){
   case some_condi_1:
   …
   case some_condi_2:
   ...
   case critical_condi:
      use(a) // use of a
}
```
In this instance, the condition check is "switch(ret_val = func(..., &a))": if it statisfies the requiement that it equals "critical_condi", then the use of the variable a will happen.
So the postcondition is "func(..., &a) == critical_condi".

Type B. Return Code Failures:
In some cases, the function check happens before a return code failure, such as:
```
ret_val = func(..., &a); 
if (ret_val < 0) { return/break/goto label/...; }
…
use(a) // use of a

label:
…
```
In this scenario, the condition check is the checking to return of "func". 
If the return value "<0", it will return or go to the "label", and skip the execution of the "use(a)". 
To make the use of suspect variable 'a' happen, the condition check can not be true.
So the postcondition is "func(..., &a) >= 0".

There is also a variant for the type B.
In some cases, it will retry an initializer until it a success:
```
while(func(&a) ==0){
…
}
use(a)
```

In this case, you should consider the "last" initializer to make it break the endless loop and then, therefore, reach the "use(a)".
So the postcondtion is "func(&a) != 0"
If the suspicious variable is used in the iteration with the index, include the boundary of the index as a check.

Other important rules:

If there's NO explicit control change (like return, break, or goto) that prevents reaching the variable's use point, you should disregard it as it provides no guarantees. All functions can always return to their caller.

Again, if you feel uncertain about finding the check, you should always consider: if the check affects the execution of use?

For multiple checks,  connect them with their relationships, i.e., && or ||.

Please remember that the context provided is complete and sufficient. You should not assume any hidden breaks or returns. 

"""

__preprocess_continue_text = """
looking at the above analysis, thinking critique for the check with its context, consider the following:
- In our case, the initializer can only be a function, and ignore it if it is not.
- Note that the given Type A and Type B can both be in the format to check the return value of a function, but the postcondition in Type A is that the check is true, while the postcondition in Type B is that the check is false.
- If our "use" is exactly a check, please directly ignore the check in your postcondition extraction
- If there's no check (or, no check can be expressed in terms of return value/params), say "postcondition: null"
- For `goto`, you should consider carefully to see if the use is under its label, then conclude the postcondition by include its condition or its `!condition`
- If one initializer has multiple checks, using boolean operators (&&, ||) to combine them
- Thinking step by step, if there are multiple initializations, think about them one by one.
"""

__preprocess_json_gen = """
The formal name of "check" is "postcondition", conclude your analysis in a json format; 
for example:
{
   "initializer": "res = some_func(a, b, c, d)",
   "suspicious": ["a", "b", "c", "d"],
   "postcondition": "ret >=4",
}

For multiple initializations, respond as:
[
 {"initializer":..., "suspicious": ..., "postcondition":... }, 
 {"initializer":...,  "suspicious": ..., "postcondition":... }
]

If not any initializer, albeit rare, you should return an empty list:
{[]}

"""

# analyze: version v4.0 (Jul 23, 2023)
# TODO (haonan): avoid the overuse of `condition`
__analyze_system_text = """
You should act as a experienced Linux kernel expert. Please following the below instructions to finish the task.

Context:
For codes in Linux kernel, a specific variable must be initilized before it is used. The "use" can be to pass it as a parameter to another function, or to assign it to another variable, or to use it in a condition check, etc.
If the variable is not initialized before the use, it will cause the bug "use-before-initialization".

Objective:
I am working on analyzing the Linux kernel for a specific type of bug called "use-before-initialization." I need your assistance in determining if a given function initializes the suspicious variables.
Additionally, I will give you some constraints to help your analysis, these constraints are facts must hold after the function execute, we also call them "postcondition".
Specially, there are "must_init" and "may_init" for the suspicious variable, which means the variable must be initialized or may be initialized.

Examples:

example 1.
The postcondition for the below code block
```
if (sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n) >= 4) { // use of a, b, c, d }
```
is "sscanf(str, '%u.%u.%u.%u%n', &a, &b, &c, &d, &n)>=4", we can conclude that function sscanf must initialize a,b,c,d, while either initialize or not initizlize for "n", so "may_init" for n.

The golden rule to make a judgment is to see whether at least one "initialization" could happen.

example 2.
“early returns” is critical and common, if you see them before the initialization of the statement that possibly makes it unreachable, for example:
```
if(some_condition){
return -1;
}
a = ... // init var a
```
In this case,
- if we don't have any postcondition, directly mark "a" as may_init since it could be unreachable
- if we have a postcondition, the function must be satisfied after the function execution. For  example, with postcondition (return value != -1), we can infer this branch was never taken (otherwise it return -1 and therefore conflicting our postcondition)
Once at least one "initialization" could happen, you can mark the variable as "must_init".

Other important rules:

1. An uninitialized variable can propagate and pollute other variables. For example, “X=v” and if v is uninitialized, it will make X also uninitialized. This way, you should take notes, focus on the variable “X” and reconsider your analysis.

2. There're some facts that we assume are always satisfied
- all functions are callable, must return to its caller, if it has a return value, the return value must be initialized with something
- the `address` of parameters are always "not NULL", unless it is explicitly "NULL" passed in

You should think step by step.
"""


__analyze_continue_text = """
Review the analysis above carefully; consider the following:

1. All functions are callable, must return (normal return or early return). 
2. If we have postcondition, it must be satisfied after the function execution.
3. Every function could return an error code (if it has return value); if there's a branch not init our suspicious variable and it can go, it must go and "may_init."
4. For unknown functions, if it is called under a return code check, you could assume this function init the suspicious var when it returns 0 and not init when it returns non-zero; it can do anything if it is called without any checks (i.e., may_init).
5. If the condition of "may_init" happens to be the postcondition or other common sense you consider true, you should change it to "must_init".

Common sense to be true:
1. constant you can calculate to be true: for example, sizeof(int)>0 or size of other variables where you know the type
2. The suspicious variable has a non-null address; i.e., &suspicious_var != NULL

If you already see some path that can return and without any init, direct conclude it's "may_init" with "confidence: true".

thinking step by step to conclude a correct and comprehensive answer.
"""

__analyze_json_gen = """
based on our analysis result, generate the json format result. 
For each "may_init", you should also indicates its condition of initalization (or say "condition": "unknown" if you can't determine):
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