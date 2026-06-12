
# openai
from openai import OpenAI
import openai


# utils
import time, argparse, json
from tqdm import tqdm


from api_keys import get_api_keys, get_router_key

import os





def get_generative_model(args):
    '''
    :param      args: get args with openai/google API key
    :return:    openai client (obj)
    '''
    import os
    os.environ ['CUDA_LAUNCH_BLOCKING'] = args.gpu_id
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu_id


    model = None

    if args.model == 'llama-3':
        model_name = 'meta-llama/Llama-3.1-8B-Instruct'
    elif args.model == 'mistral':
        model_name = 'mistralai/Mistral-7B-Instruct-v0.1'
    elif args.model == 'llama-2':
        model_name = 'meta-llama/Llama-2-7b-chat-hf'
    elif args.model == 'mentallama':
        model_name = 'klyang/MentaLLaMA-chat-7B'
    elif args.model == 'qwen2.5':
        model_name = "Qwen/Qwen2.5-7B-Instruct"
    elif args.model == 'qwen2.5-small':
        model_name = "Qwen/Qwen2.5-1.5B-Instruct"
    elif args.model == 'qwen3':
        model_name = "Qwen/Qwen3-8B"

    tokenizer = None

    if 'gpt' in  args.model:
        api_key = get_api_keys(args)
        model = OpenAI(api_key=api_key)

    elif 'gemini' in args.model or args.model == 'qwen235':
        api_key = get_router_key(args)
        model = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
    elif args.model == 'qwen3':
        from vllm import LLM, SamplingParams
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-8B")
        model = LLM(model=model_name)
    else:
        from vllm import LLM, SamplingParams
        model = LLM(model=model_name)

    return model, tokenizer



def generate_openai_model(args, client, messages):
    cnt=0
    response = None
    if args.model == 'gpt35':
        model_name = 'gpt-3.5-turbo-1106'
    elif args.model == 'gpt-4o':
        model_name = 'gpt-4o'
    elif args.model == 'gpt5':
        model_name = 'gpt-5.1'
    elif args.model == 'gpt5-mini':
        model_name = 'gpt-5-mini'


    while True:
        try:
            cnt+=1
            if cnt==5:
                break
            response = client.chat.completions.create(
                model=model_name,
                messages=messages
            )
            break
            
        except Exception as e:
            print("Exception: ", e)
            time.sleep(10)

    if response == None:
        return None
    res = response.choices[0].message.content
    return res



def generate_gemini(model, system_prompt, user_prompt):
    while True:
        try:
            response = model.chat.completions.create(
                model='google/gemini-2.5-flash',
                reasoning_effort = 'none',
                messages= [
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": user_prompt
                                }
                            ]
                        }
                    ],
                )

            break
        except Exception as e:
            print(f"Fail to generate response with error: {e}")
            sleep(10)
    
    text = response.choices[0].message.content

    # # Post-process the text if needed
    # text = text.strip("`")
    # text = text.rstrip("]\n}")
    # text = text.replace("}\n}", "}")
    # text = text.lstrip("json")
    # if not text.endswith("}"):
    #     text += "}"
    return text


def generate_qwen235(model, system_prompt, user_prompt):
    while True:
        try:
            response = model.chat.completions.create(
                    model='qwen/qwen3-235b-a22b-2507',
                    messages= [
                            {
                                "role": "system",
                                "content": system_prompt
                            },
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": user_prompt
                                    }
                                ]
                            }
                        ],
                )

            break
        except Exception as e:
            print(f"Fail to generate response with error: {e}")
            sleep(10)
    
    text = response.choices[0].message.content

    return text



def request(args, client, message, system_message, tokenizer): 
    messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": message},
        ]


    if 'gpt' in args.model:
        res = generate_openai_model(args, client, messages)
    elif 'gemini' in args.model:
        res = generate_gemini(client, system_message, message)
    elif args.model == 'qwen235':
        res = generate_qwen235(client, system_message, message)

    elif args.model == 'qwen3':
        from vllm import LLM, SamplingParams
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,  # Set to False to strictly disable thinking
        )
        sampling_params = SamplingParams(top_p=0.95,  max_tokens=300)
        output = client.generate([text], sampling_params)
        res = output[0].outputs[0].text


    else:
        from vllm import LLM, SamplingParams
        sampling_params = SamplingParams(top_p=0.95,  max_tokens=300)
        output = client.generate(message, sampling_params)
        res = output[0].outputs[0].text
    return res

    #import IPython; IPython.embed(); exit(1)
