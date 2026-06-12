
import time, argparse, json
import os
from tqdm import tqdm
from prompts import get_eval_prompt, get_eval_prompt_single
from knowledge_graph import KnowledgeGraph # get_kg

from models import get_generative_model, request




def get_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('--data_dir', type=str, default='./../resources/dataset/{}')
    parser.add_argument('--output_dir', type=str, default='./../output/{}')

    # Model settings
    parser.add_argument('--model', type=str, default='qwen3')
    #parser.add_argument('--model', type=str, default='qwen2.5')
    #parser.add_argument('--model', type=str, default='llama-3')
    #parser.add_argument('--model', type=str, default='mentallama')
    #parser.add_argument('--model', type=str, default='gpt5')
    

    # generation parameter
    #parser.add_argument('--mode', type=str, default='pilot')
    parser.add_argument('--mode', type=str, default='main')
    parser.add_argument('--difficulty', type=str, default='low')
    #parser.add_argument('--difficulty', type=str, default='medium')
    #parser.add_argument('--difficulty', type=str, default='high')



    parser.add_argument('--question_type', type=str, default='single')
    #parser.add_argument('--question_type', type=str, default='multiple')




    parser.add_argument('--api_key', type=int, default=0)
    parser.add_argument('--save_point', type=int, default=100)
    parser.add_argument('--gpu_id', type=str, default='0')


    # Instruction settings
    parser.add_argument('--instruction_k', type=int, default=5)
    parser.add_argument('--temperature', type=int, default=0)

    parser.add_argument('--toy', type=int, default=0)


    return parser.parse_args()


import re

def extract_answer(text):
    if not isinstance(text, str): return set()
    text = text.upper()
    
    # 1. Remove common prefixes (e.g., "Answer:") to prevent misinterpretation
    text = re.sub(r'^(?:ANSWER|OUTPUT|SELECTION|THE ANSWER IS)[:\s-]*', '', text.strip())

    # 2. [Core Regex] Find the first valid answer sequence.
    #    It looks for an initial letter (A-D) followed optionally by separators (&, ,, and) and more letters.
    #    This captures patterns like "A", "A & B", "A, B", "A and C".
    #    re.search stops at the first match, effectively ignoring subsequent text like "But B is..."
    match = re.search(r'([A-D](?:\s*(?:,|&|and)\s*[A-D])*)', text)

    if match:
        # Extract only the alphabets from the matched chunk (e.g., "A & B" -> {'A', 'B'}) and return as a set
        return set(re.findall(r'[A-D]', match.group(1)))
    
    return set()


def generate_gt(text):
    """
    Extracts the option letters from the Ground Truth (GT) text.
    Supports both period (.) and closing parenthesis ()) as separators.
    
    Examples:
        "C. Bipolar II" -> {'C'}
        "A) Major Depressive" -> {'A'}
        "A & B) Both Conditions" -> {'A', 'B'}
    """
    if not isinstance(text, str):
        return set()
    
    text = text.upper().strip()
    
    # 1. Split the text at the first occurrence of either a period (.) or a closing parenthesis ())
    #    and take the first part (the prefix).
    #    This removes the disease name following the option (e.g., "Vitamin A" in the text).
    text = re.split(r'[.)]', text, 1)[0]
        
    # 2. Extract option letters (A, B, C, D) from the prefix.
    #    Using \b (word boundary) ensures we don't match parts of other words.
    return set(re.findall(r'\b[A-D]\b', text))


def save_files(args, file_name, samples):
    print('**saving files: {} samples at {}'.format(len(samples), file_name))
    full_path = args.output_dir.format(file_name)

    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    with open(full_path, 'w') as fp:
        json.dump(samples, fp, indent=4, sort_keys=False, ensure_ascii=False)


def print_eval_stats(eval_stats):
    """
    Prints the evaluation statistics in a formatted table.
    Calculates accuracy per disease code and the overall total.
    """
    # 1. Define header format with fixed widths for alignment
    # :<10 (Left align, 10 spaces), :>8 (Right align, 8 spaces)
    header = f"| {'Disease':<10} | {'Correct':>8} | {'Wrong':>8} | {'Total':>8} | {'Accuracy':>10} |"
    divider = "-" * len(header)
    
    print("=" * len(header))
    print(header)
    print(divider)

    # 2. Variables to aggregate total statistics dynamically
    # (In case eval_stats['all'] was not updated during the loop)
    agg_correct = 0
    agg_wrong = 0
    agg_total = 0

    # 3. Sort keys alphabetically, excluding 'all' for now
    disease_codes = sorted([k for k in eval_stats.keys() if k != "all"])

    for code in disease_codes:
        stat = eval_stats[code]
        
        # Safely get values, defaulting to 0 if missing
        corr = stat.get('correct', 0)
        wrong = stat.get('incorrect', 0)
        tot = stat.get('total', 0)

        # Accumulate for the final 'TOTAL' row
        agg_correct += corr
        agg_wrong += wrong
        agg_total += tot

        # Calculate accuracy (Prevent ZeroDivisionError)
        acc = (corr / tot * 100) if tot > 0 else 0.0

        # Print the row for the current disease code
        print(f"| {code:<10} | {corr:>8} | {wrong:>8} | {tot:>8} | {acc:>9.2f}% |")

    print(divider)

    # 4. Handle the 'TOTAL' row
    # Use 'all' key from input if it has data; otherwise, use aggregated values
    if 'all' in eval_stats and eval_stats['all']['total'] > 0:
        final_corr = eval_stats['all']['correct']
        final_wrong = eval_stats['all']['incorrect']
        final_total = eval_stats['all']['total']
    else:
        final_corr = agg_correct
        final_wrong = agg_wrong
        final_total = agg_total

    # Calculate overall accuracy
    final_acc = (final_corr / final_total * 100) if final_total > 0 else 0.0

    # Print the summary row with emphasis
    print(f"| {'TOTAL':<10} | {final_corr:>8} | {final_wrong:>8} | {final_total:>8} | {final_acc:>9.2f}% |")
    print("=" * len(header))



if __name__ == "__main__":
    args = get_args()
    print(args)
    knowledge_graph_obj = KnowledgeGraph(args)


    ### Type A  ###
    if args.difficulty == 'low' or args.difficulty == 'medium':
        nodes = knowledge_graph_obj.get_disease_nodes()
    ### Type B  ###
    elif args.difficulty == 'high':
        nodes = knowledge_graph_obj.get_differential_diagnosis_nodes()


    generative_models = ['gemini', 'gpt5', 'qwen235']
    client, tokenizer=get_generative_model(args)



    eval_stats = {"all": {
            "correct": 0,
            "incorrect": 0,
            "total": 0
        }
    }

    for idx, disease_code in enumerate(tqdm(nodes, desc='evaluation on {}'.format(args.model), mininterval=0.01, leave=True)):

        eval_stats[disease_code] = {
                "correct": 0,
                "incorrect": 0,
                "total": 0
            }

        for generative_model in generative_models:
            file_name = '{}/{}/{}_{}.json'.format(args.difficulty, disease_code, args.mode, generative_model)
            full_path = args.data_dir.format(file_name)
            

            if os.path.exists(full_path):
                with open(full_path, 'r', encoding='utf-8') as f:
                    datas = json.load(f)
            else:
                print('No such file: {}\n'.format(file_name))
                continue


            results = dict()

            wrong = dict()
            for idx, data in enumerate(tqdm(datas, desc='evaluation {}'.format(disease_code), mininterval=0.01, leave=True)):
                
                question, option, answer = datas[data]['question'], datas[data]['options'], datas[data]['answer']
                
                if args.question_type == 'single':
                    message = get_eval_prompt_single(args, question, option, answer)
                else: 
                    message = get_eval_prompt(args, question, option, answer)




                system_message = ""
                res = request(args, client, message, system_message, tokenizer).strip()

                results[data] = {'question':question, 'option':option, 'answer':answer, 'response':res}


                res_answer_set = extract_answer(res)
                gt_set = generate_gt(answer)
         

                eval_stats['all']['total']+=1
                eval_stats[disease_code]['total']+=1
                if gt_set == res_answer_set and len(gt_set) > 0:
                    eval_stats['all']['correct']+=1
                    eval_stats[disease_code]['correct']+=1

                else:
                    eval_stats['all']['incorrect']+=1
                    eval_stats[disease_code]['incorrect']+=1
                    wrong[data] = {'answer':answer, 'res':res}
                    print(f'\n[Wrong] "{data}" GT Prefix: "{gt_set}" | Res: "{res_answer_set}"')
                    print('\n{}/{}\n'.format(eval_stats[disease_code]['incorrect'], eval_stats[disease_code]['total']))

                
                output_file_name = '{}/{}/{}/{}_{}.json'.format(args.model, args.difficulty, disease_code, args.mode, generative_model)
                save_files(args, output_file_name, results)

            print('Tested on: {}/{}'.format(args.difficulty, disease_code))
            print('result (accuracy) by {}: {} out of {}'.format(args.model, eval_stats[disease_code]['correct']/eval_stats[disease_code]['total'], eval_stats[disease_code]['total']))
            print(wrong.keys())
            

    print('Tested on: {}'.format(args.difficulty))
    print('result (accuracy) by {}: {} out of {}'.format(args.model, eval_stats['all']['correct']/eval_stats['all']['total'], eval_stats['all']['total']))
    print(wrong.keys())
    print_eval_stats(eval_stats)

    #import IPython; IPython.embed(); exit(1)


    
    
    
