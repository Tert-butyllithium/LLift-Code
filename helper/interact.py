from PyInquirer import prompt
from plyer import notification

# This is a helper function to interact with the user

#TODO: 1) add a timeout, 2) check if the `req_func` is in the user input
def interactive_func_def(proj, cur_func, req_func):

    questions = [
        {
            'type': 'input',
            'name': 'user_input',
            'message': f'Project: {proj}; current func: {cur_func}; requested func `{req_func}`:\n'
        }
    ]

    __notify(req_func)
    answers = prompt(questions)
    print(answers)
    res = answers['user_input']

    if len(res) < 15:
        return None
    return res


def __notify(func):
    notification.notify(
        title='LLift: Function Request',
        message='The definition of `{func}`? 🙏'.format(func=func),
    )


if __name__ == '__main__':
    a = interactive_func_def('edk2', 'a', 'b')
    print('='*10)
    print(a)
    print('='*10)
