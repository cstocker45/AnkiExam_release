#import git 
import os

print(f"Running Script...")

#import subprocess
#need to install some specific versions for anki addon development...
#subprocess.check_call(["pip3", "install", "--upgrade", "pip"])
#subprocess.check_call(["pip3", "install", "mypy", "aqt[qt6]"])

import anki
from anki import hooks
#hooks.()

#hooks worked... now trying running the gui end

from aqt import gui_hooks

def myfunc() -> None:
  print("myfunc")

#gui_hooks.reviewer_did_show_answer.append(myfunc)

from anki.cards import Card

def myfunc(card: Card) -> None:
  print("myfunc")






RunTogether_Debug = False
if RunTogether_Debug:
# Run in the terminal:
# export TOGETHER_API_KEY="642e67dafec91ef10ce54cf830e7af8d8112a17587b4941c470f8f5e34671514"

# testing to see if the environment variable is set correctly
    print(os.environ.get("TOGETHER_API_KEY"))

    from together import Together   

    client = Together() # auth defaults to os.environ.get("TOGETHER_API_KEY")

    response = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-V3",
        messages=[
         {
          "system": "You are a task-oriented assistant that provides consise answers to queries. There is no need to include any disclaimers or additional information. Keep headings simple and "
          "avoid the use of over styled text.",
           "role": "user",
          "content": "What are some fun things to do in New York?"
          }
     ]
    )
    print(response.choices[0].message.content)
    
    #check how many tokens were used
    print(f"Total tokens used: {response.usage.total_tokens}")
    #check how many tokens were used for the prompt
    print(f"Prompt tokens used: {response.usage.prompt_tokens}")
else:
    print("RunTogether_Debug is set to False, skipping Together API call.")


