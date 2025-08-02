#import git 

import os
import requests

print(f"Running Script...")
   # Run in the terminal:
   # export TOGETHER_API_KEY="642e67dafec91ef10ce54cf830e7af8d8112a17587b4941c470f8f5e34671514"
   # Add this at the top of your show_custom_gui function


def together_api_input(UserAnswer, QuestionToAsk):
    #api_key = os.environ.get("TOGETHER_API_KEY")
    api_key = "642e67dafec91ef10ce54cf830e7af8d8112a17587b4941c470f8f5e34671514"
    if not api_key:
        raise Exception("TOGETHER_API_KEY environment variable not set.")

    url = "https://api.together.xyz/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-ai/DeepSeek-V3",
        "messages": [
            {
                "role": "system",
               "content": (
    "You are an expert reviewer, and serve to grade the user's response. "
    "You should critique the user's response, and highlight any misunderstandings or potential oversights. "
    "There is no need to include any disclaimers or additional information. "
    "Keep your responses simple and avoid the use of over styled text. Based on the degree to which the user's response is correct, you must give a '%' score between 0 and 100. "
    f"You are testing the user's knowledge on the following question: {QuestionToAsk}")
            },
            {
                "role": "user",
                "content": UserAnswer
            }
        ]
    }
    ##DEBUG PRINTS
    #check how many tokens were used
    #print(f"Total tokens used: {response.usage.total_tokens}")
    #check how many tokens were used for the prompt
    #print(f"Prompt tokens used: {response.usage.prompt_tokens}")

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()
    output = result["choices"][0]["message"]["content"]
    total_tokens = result.get("usage", {}).get("total_tokens", 0)
    print(f"API returned total_tokens: {total_tokens}")  # Debug logging
    
    # Update token count in auth client
    if total_tokens > 0:
        from . import auth_client
        if auth_client and auth_client.is_authenticated():
            success = auth_client.add_tokens(total_tokens)
            print(f"Token update success: {success}")  # Debug logging
        else:
            print("Warning: auth_client not available or not authenticated")
    total_tokens = result["usage"]["total_tokens"]
    
    # Track token usage
    from .ClientAuth import AuthClient
    auth_client = AuthClient()
    if total_tokens > 0:
        auth_client.add_tokens(total_tokens)


        
    return output, total_tokens
