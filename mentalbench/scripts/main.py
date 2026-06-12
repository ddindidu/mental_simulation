
import time, argparse, json
from tqdm import tqdm
import os

from prompts import (get_system_prompt_medium, get_system_prompt_low, get_type_A_user_prompt,  
            get_system_prompt_high_clear, get_system_prompt_high_ambiguous, get_type_B_ambiguous_user_prompt, get_type_B_clear_user_prompt)
from knowledge_graph import KnowledgeGraph
from question_setter import QuestionSetter
from demographics import get_demographics


from models import get_generative_model, request




def get_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('--data_dir', type=str, default='./../resources/dataset/{}')
    parser.add_argument('--knowledge_graph_dir', type=str, default='./../resources/knowledge_graph/EN/')
    parser.add_argument('--seed_dir', type=str, default='./../resources/features/variation/')

    

    
    # generation parameter
    parser.add_argument('--mode', type=str, default='pilot')
    #parser.add_argument('--mode', type=str, default='main')
    parser.add_argument('--sam_num', type=int, default=10)
    #parser.add_argument('--difficulty', type=str, default='low')
    #parser.add_argument('--difficulty', type=str, default='medium')
    parser.add_argument('--difficulty', type=str, default='high')


    # Model settings
    parser.add_argument('--model', type=str, default='gpt5')
    #parser.add_argument('--model', type=str, default='qwen235')
    #parser.add_argument('--model', type=str, default='gemini')


    parser.add_argument('--api_key', type=int, default=3)
    parser.add_argument('--save_point', type=int, default=10)
    parser.add_argument('--gpu_id', type=str, default='0')


    # Instruction settings
    parser.add_argument('--instruction_k', type=int, default=5)
    parser.add_argument('--temperature', type=int, default=0)

    parser.add_argument('--toy', type=int, default=0)


    return parser.parse_args()



def generate_qa_type_A(args, client, features):
    difficulty = args.difficulty

    demographics = get_demographics(args)
    

    message = get_type_A_user_prompt(args, features['question']['sampled_features'], features['option']['options'], demographics)

    
    if difficulty == 'low':
        system_message = get_system_prompt_low(args)
        
    elif difficulty == 'medium':
        system_message = get_system_prompt_medium(args)
        
    res = request(args, client, message, system_message, tokenizer)
    
    return res, features, message



def generate_qa_type_B(args, client, features, knowledge_graph_obj):
    difficulty = args.difficulty

    main_disease = knowledge_graph_obj.convert_code_to_name(features['question_both']['main_disease'])
    sub_disease = knowledge_graph_obj.convert_code_to_name(features['question_both']['sub_disease'])

    additional_condition = features['question_both']['additional_condition']
    key_difference = features['question_both']['key_difference']
    rule_main = features['question_a']['rule']
    rule_sub = features['question_b']['rule']

    demographics = get_demographics(args)
    
    
    #### clear ####
    system_message = get_system_prompt_high_clear(args)
    #### main ####
    clear_message_main = get_type_B_clear_user_prompt(args, features, features['option_both']['options'], demographics, main_disease, sub_disease,
                            additional_condition, key_difference, rule_main, rule_sub)
    clear_res_main = request(args, client, clear_message_main, system_message, tokenizer)
    
    #### sub ####
    clear_message_sub = get_type_B_clear_user_prompt(args, features, features['option_both']['options'], demographics, sub_disease, main_disease,
                            additional_condition, key_difference, rule_sub, rule_main)
    clear_res_sub = request(args, client, clear_message_sub, system_message, tokenizer)
    

    #### ambiguous ####
    ambiguous_system_message = get_system_prompt_high_ambiguous(args)
    ambiguous_message = get_type_B_ambiguous_user_prompt(args, features, features['option_both']['options'], demographics, main_disease, sub_disease,
                            additional_condition, key_difference, rule_main, rule_sub)
    ambiguous_res = request(args, client, ambiguous_message, ambiguous_system_message, tokenizer)
    
    #import IPython; IPython.embed(); exit(1)
    import IPython; IPython.embed(); exit(1)
    return ambiguous_res, clear_res_main, clear_res_sub, features, ambiguous_message, clear_message_main, clear_message_sub





def save_files(args, file_name, samples, feature_file_name, samples_wFeatures):
    print('**saving files: {} samples at {}'.format(len(samples), file_name))
    full_path = args.data_dir.format(file_name)
    feature_full_path = args.data_dir.format(feature_file_name)

    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    os.makedirs(os.path.dirname(feature_full_path), exist_ok=True)

    with open(full_path, 'w') as fp:
        json.dump(samples, fp, indent=4, sort_keys=False, ensure_ascii=False)

    with open(feature_full_path, 'w') as fp:
        json.dump(samples_wFeatures, fp, indent=4, sort_keys=False, ensure_ascii=False)



    #with open(args.data_dir.format('{}_features_{}.json'.format(args.difficulty, args.sam_num)), 'w') as fp:
    #    json.dump(features, fp, indent=4, sort_keys=False, ensure_ascii=False)

def get_answer_options(args, features):
    option_list = features['options']
    answer_index = features['answer_index']

    indexes = ['A', 'B', 'C', 'D']

    options = """
    A. {}
    B. {}
    C. {}
    D. {}
    """.format(option_list[0], option_list[1], option_list[2], option_list[3])

    if len(answer_index) == 1:
        answer = indexes[answer_index[0]] + '. ' + option_list[answer_index[0]]

    elif len(answer_index) > 1:
        answer = ' & '.join([indexes[i] for i in answer_index]) + '. ' + ' & '.join([option_list[i] for i in answer_index])

    return options, answer




if __name__ == "__main__":
    args = get_args()
    print(args)


    client, tokenizer=get_generative_model(args)
    

    knowledge_graph_obj = KnowledgeGraph(args)
    qs = QuestionSetter(knowledge_graph_obj)
    

    
    
    samples_wFeatures = dict()


    ### Type A  ###
    if args.difficulty == 'low' or args.difficulty == 'medium':
        nodes = knowledge_graph_obj.get_disease_nodes()
    ### Type B  ###
    elif args.difficulty == 'high':
        nodes = knowledge_graph_obj.get_differential_diagnosis_nodes()


    # iterate by number of disease codes
    #for disease_code in nodes:
    for idx, disease_code in enumerate(tqdm(nodes, desc='QA Generation', mininterval=0.01, leave=True)):

        disease_code = 'D007-D005'

        file_name = '{}/{}/{}_{}.json'.format(args.difficulty, disease_code, args.mode, args.model)
        full_path = args.data_dir.format(file_name)
        feature_file_name = '{}/{}/features/{}_{}.json'.format(args.difficulty, disease_code, args.mode, args.model)
        feature_full_path = args.data_dir.format(feature_file_name)


        if os.path.exists(full_path):
            '''
            file_name_ambig = '{}/{}/ambig_{}_{}.json'.format(args.difficulty, disease_code, args.mode, args.model)
            full_path_ambig = args.data_dir.format(file_name_ambig)
            with open(full_path_ambig, 'r', encoding='utf-8') as f:
                samples_ambig = json.load(f)
            file_name_cleara = '{}/{}/ambig_{}_{}.json'.format(args.difficulty, disease_code, args.mode, args.model)
            full_path_cleara = args.data_dir.format(file_name_cleara)
            with open(full_path_cleara, 'r', encoding='utf-8') as f:
                samples_cleara = json.load(f)
            file_name_clearb = '{}/{}/ambig_{}_{}.json'.format(args.difficulty, disease_code, args.mode, args.model)
            full_path_clearb = args.data_dir.format(file_name_clearb)
            with open(full_path_clearb, 'r', encoding='utf-8') as f:
                samples_clearb = json.load(f)
            '''

            with open(feature_full_path, 'r', encoding='utf-8') as f:
                samples_wFeatures = json.load(f)
        else: 
            '''
            samples_ambig = dict()
            samples_cleara = dict()
            samples_clearb = dict()
            '''
            samples_wFeatures = dict()
            samples = dict()


        # iterate by number of samples per disease code
        #for idx in range(args.sam_num):
        question_data = qs.call_questions(disease_code, args.difficulty, args.seed_dir)
        for idx, expression_code in enumerate(tqdm(question_data, desc='{}'.format(disease_code), mininterval=0.01, leave=True)):
            features = question_data[expression_code]

            ### Type A  ###
            if args.difficulty == 'low' or args.difficulty == 'medium':
                sample_id = disease_code+'_{}{:03d}'.format(args.difficulty[0], idx+1)
                if sample_id in samples:
                    print('skipping')
                    continue

                #if idx ==5:
                #    break

                res, features, message = generate_qa_type_A(args, client, features)
                options, answer = get_answer_options(args, features['option'])

                samples_wFeatures[sample_id] = {'question': res,
                            'options': options,
                            'answer': answer,
                            'features': features,
                            'prompt': message
                        }

                samples[sample_id] = {'question': res,
                            'options': options,
                            'answer': answer
                        }
                

            ### Type B  ###
            elif args.difficulty == 'high':
                sample_id_ambiguous = disease_code+'_{}{:03d}'.format(args.difficulty[0], idx+1)
                sample_id = disease_code+'_{}{:03d}'.format(args.difficulty[0], idx+1)
                if sample_id in samples_wFeatures:
                    print('skipping')
                    continue
                
                res_ambig, res_cleara, res_clearb, features, ambiguous_message, clear_message_main, clear_message_sub = generate_qa_type_B(args, client, features, knowledge_graph_obj)
                


                options_ambig, answer_ambig = get_answer_options(args, features['option_both'])
                options_cleara, answer_cleara = get_answer_options(args, features['option_a'])
                options_clearb, answer_clearb = get_answer_options(args, features['option_b'])

                samples_wFeatures[sample_id] = {'question_both': res_ambig,
                            'question_a': res_cleara,
                            'question_b': res_clearb,
                            'options': options_ambig,
                            'answer_both': answer_ambig,
                            'answer_a': answer_cleara,
                            'answer_b': answer_clearb,
                            'features': features,
                            'prompt': ambiguous_message
                        }

                samples_ambig[sample_id] = {'question': res_ambig,
                            'options': options_ambig,
                            'answer': answer_ambig
                        }
                samples_cleara[sample_id] = {'question': res_cleara,
                            'options': options_cleara,
                            'answer': answer_cleara
                        }
                samples_clearb[sample_id] = {'question': res_clearb,
                            'options': options_clearb,
                            'answer': answer_clearb
                        }
                import IPython; IPython.embed(); exit(1)


            
            
            #samples_wFeatures[sample_id] = {'features':features, 'prompt':message}        


            

            if idx%args.save_point==0 and idx!=0:
                save_files(args, file_name, samples, feature_file_name, samples_wFeatures)

        

        save_files(args, file_name, samples, feature_file_name, samples_wFeatures)
   
    #import IPython; IPython.embed(); exit(1)
