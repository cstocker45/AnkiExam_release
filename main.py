#import git 

import os
from .shared import get_model_name

print(f"Running Script...")
   # Run in the terminal:
   # export TOGETHER_API_KEY="642e67dafec91ef10ce54cf830e7af8d8112a17587b4941c470f8f5e34671514"
   # Add this at the top of your show_custom_gui function


def together_api_input(UserAnswer, QuestionToAsk):
    # Route grading through the server to enforce model access and metering
    from . import auth_client as global_auth_client
    from .ClientAuth import AuthClient
    client = global_auth_client if global_auth_client and global_auth_client.is_authenticated() else AuthClient()
    if not client.is_authenticated():
        raise Exception("Not authenticated. Please log in first.")

    system_prompt = (
        "You are an expert reviewer, and serve to grade the user's response. "
        "You should critique the user's response, and highlight any misunderstandings or potential oversights. "
        "There is no need to include any disclaimers or additional information. "
        "Keep your responses simple and avoid the use of over styled text. Based on the degree to which the user's response is correct, you must give a '%' score between 0 and 100. "
        f"You are testing the user's knowledge on the following question: {QuestionToAsk}"
    )
    # Send to server; server chooses model based on plan
    output, total_tokens = client.grade_answer(QuestionToAsk, UserAnswer, model_hint=get_model_name())
    return output, total_tokens
