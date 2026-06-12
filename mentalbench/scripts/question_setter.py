

import os
from random import random
from knowledge_graph import KnowledgeGraph
import random
import copy
# pretty print
from pprint import pprint
import json
from collections import defaultdict

class QuestionSetter:
    def __init__(self, knowledge_graph_obj):
        self.knowledge_graph_obj = knowledge_graph_obj
        
        # parameters for method 1
        ## diagnostic criteria sampling        
        self.include_all_diagnostic_criteria = True  # 모든 진단 기준 포함 여부
        self.include_duration = True  # 기간 포함 여부
        self.include_additional_requirements = True  # 추가 요구사항 포함 여부
        self.min_count_contained_diagnostic_criteria = 0    # 최소 포함 진단 기준 개수  (duration 관련 기준과는 상관없이)
        self.max_count_contained_diagnostic_criteria = 2    # 최대 포함 진단 기준 개수
        
        ## symptom group sampling
        self.include_all_symptom_groups = True    # 모든 증상군 포함 여부
        self.min_count_contained_symptom_groups = 1         # 최소 포함 증상군 개수
        self.max_count_contained_symptom_groups = 3         # 최대 포함 증상군 개수
        
        ## symptom group내 feature sampling
        #### 현재 valid key 모두 포함하도록 구현됨
        
        ## symptom sampling per group
        self.follow_min_count_per_group = True      # 증상군 당 최소 포함 증상 개수 준수 여부
        self.min_count_contained_symptoms_per_group = 3    # 증상군 당 최소 포함 증상 개수  # self.follow_min_count_per_group 이 False일 때만 적용
        self.max_count_contained_symptoms_per_group = 6    # 증상군 당 최대 포함 증상 개수  # self.follow_min_count_per_group 이 False일 때 혹은 True이면서 min_count보다 더 클 때 적용
        
        # duration sampling
        self.min_duration_buffer = 14     # 최소 기간 버퍼 (days)
        self.max_duration_buffer = 910   # 최대 기간 버퍼 (days) ... 2년 6개월

        # initialize disease features lookup
        self.disease_features_lookup = self.knowledge_graph_obj.get_disease_features_lookup()
        
        # initialize validity check
        self.check_validity_of_parameters()


    def check_validity_of_parameters(self):
        assert self.min_count_contained_diagnostic_criteria >= 0, AssertionError(f"In QuestionSetter Class, Minimum count of contained diagnostic criteria {self.min_count_contained_diagnostic_criteria} cannot be negative.")
        assert self.max_count_contained_diagnostic_criteria >= 0, AssertionError(f"In QuestionSetter Class, Maximum count of contained diagnostic criteria {self.max_count_contained_diagnostic_criteria} cannot be negative.")
        assert self.min_count_contained_symptom_groups >= 0, AssertionError(f"In QuestionSetter Class, min # symptom groups {self.min_count_contained_symptom_groups} < 0.")
        assert self.max_count_contained_symptom_groups >= 0, AssertionError(f"In QuestionSetter Class, max # symptom groups {self.max_count_contained_symptom_groups} < 0.")
        assert self.min_count_contained_symptoms_per_group >= 0, AssertionError(f"In QuestionSetter Class, min # symptoms_per_group {self.min_count_contained_symptoms_per_group} < 0.")
        assert self.max_count_contained_symptoms_per_group >= 0, AssertionError(f"In QuestionSetter Class, max # symptoms_per_group {self.max_count_contained_symptoms_per_group} < 0.")
        assert self.min_count_contained_diagnostic_criteria <= self.max_count_contained_diagnostic_criteria, AssertionError("In QuestionSetter Class, Minimum count of contained diagnostic criteria cannot be greater than maximum count.")
            
        assert self.min_count_contained_symptom_groups <= self.max_count_contained_symptom_groups, AssertionError("In QuestionSetter Class, Minimum count of contained symptom groups cannot be greater than maximum count.")
    
        assert self.min_count_contained_symptoms_per_group <= self.max_count_contained_symptoms_per_group, AssertionError("In QuestionSetter Class, Minimum count of contained symptoms per group cannot be greater than maximum count.")
    
    def set_parameters_based_on_difficulty(self, difficulty_level):
        if difficulty_level == 'low':
            self.include_all_diagnostic_criteria = True  # 모든 진단 기준 포함 여부
            self.include_duration = True  # 기간 포함 여부
            self.include_additional_requirements = True
            self.include_all_symptom_groups = True    # 모든 증상군 포함 여부
            self.follow_min_count_per_group = True      # 증상군 당 최소 포함 증상 개수 준수 여부
            self.min_count_contained_symptoms_per_group = 3    # 증상군 당 최소 포함 증상 개수  # self.follow_min_count_per_group 이 False일 때만 적용
            self.max_count_contained_symptoms_per_group = 6    # 증상군 당 최대 포함 증상 개수  # self.follow_min_count_per_group 이 False일 때 혹은 True이면서 min_count보다 더 클 때 적용
            self.check_validity_of_parameters()
        elif difficulty_level == 'medium':
            self.include_all_diagnostic_criteria = False  
            self.include_duration = True  # 기간 포함 여부
            self.include_additional_requirements = True
            self.min_count_contained_diagnostic_criteria = 0    # 최소 포함 진단 기준 개수  (duration이랑 additional requirements 제외)
            self.max_count_contained_diagnostic_criteria = 1    # 최대 포함 진단 기준 개수
            self.include_all_symptom_groups = True    
            self.follow_min_count_per_group = False
            self.min_count_contained_symptoms_per_group = 2    # 증상군 당 최소 포함 증상 개수  # self.follow_min_count_per_group 이 False일 때만 적용
            self.max_count_contained_symptoms_per_group = 3    # 증상군 당 최대 포함 증상 개수  # self.follow_min_count_per_group 이 False일 때 혹은 True이면서 min_count보다 더 클 때 적용      
            self.check_validity_of_parameters()
        elif difficulty_level == 'high':
            self.include_all_diagnostic_criteria = False  
            self.include_duration = False  # 기간 포함 여부
            self.include_additional_requirements = False
            self.min_count_contained_diagnostic_criteria = 0    # 최소 포함 진단 기준 개수  (duration 관련 기준과는 상관없이)
            self.max_count_contained_diagnostic_criteria = 0    # 최대 포함 진단 기준 개수
            self.include_all_symptom_groups = True    
            self.follow_min_count_per_group = False     
            self.min_count_contained_symptoms_per_group = 2    
            self.max_count_contained_symptoms_per_group = 3  
            self.check_validity_of_parameters()

        else:
            raise ValueError("Invalid difficulty level. Choose from 'low', 'medium', or 'high'.")
        
    
    def call_questions(self, code, difficulty_level, resource_path):
        path = os.path.join(resource_path, difficulty_level, "json", f"{code}.json")
        if os.path.exists(path):
            with open(path, 'r') as f:
                question_data = json.load(f)
            return question_data
        else:
            raise FileNotFoundError(path)
        return
    
    def get_contain_and_remove_options_for_special_cases(self, disease_code, must_contain_option_list=[]):
        must_contain_options = copy.deepcopy(must_contain_option_list)
        must_remove_options = []

        _must_contain_option_codes = []
        if disease_code == "D007":
            must_remove_options = ["D006"]
        elif disease_code == "D009":
            must_remove_options = ["D008"]
        elif disease_code == "D011":
            random_k = random.randint(1, 3)
            _must_contain_option_codes = random.sample(["D001", "D002", "D003", "D015", "D012", "D018", "D020"], random_k)  # no must contain options for D011
            must_remove_options = ["D006", "D007", "D008", "D009", "D010"]
        elif disease_code == "D012":
            random_k = random.randint(1, 3)
            _must_contain_option_codes = random.sample(["D011", "D018", "D019"], random_k)
        elif disease_code == "D018":
            must_remove_options = ["D019"]
        elif disease_code == "D019":
            must_remove_options = ["D018"]

        for oc in _must_contain_option_codes:
            must_contain_options.append({
                'disease_code': oc,
                'disease_name': self.knowledge_graph_obj.convert_code_to_name(oc)
            })
            
        return must_contain_options, must_remove_options

    # TODO: make method 1 - make 문제 from one disease node
    def create_questions_from_disease(self, disease_code, difficulty_level='low',
                                      n_options=4, n_highly_likely=1, n_moderately_likely=1, n_less_likely=1):
        disease_features = self.disease_features_lookup[disease_code]
        sampled_features = self.sample_features_from_disease(disease_features, difficulty_level=difficulty_level)
    
        option_candidates = self.list_options_for_question(sampled_features)

        must_contain_options, must_remove_options = self.get_contain_and_remove_options_for_special_cases(disease_code)
        mcq_option_dict = self.sample_options_for_mcq(option_candidates,
                                                      must_contain_option_list=must_contain_options,
                                                      must_remove_option_list=must_remove_options,
                                                      n_options=n_options,
                                                      n_highly_likely = 0, n_moderately_likely=0, n_less_likely=0)
        
        questions_for_disease = {
            'question': {
                'disease_code': disease_code,
                'disease_name': disease_features['name'],
                'sampled_features': sampled_features
            },
            'option': {
                'options': mcq_option_dict['options'],
                'answer_index': mcq_option_dict['answer_index'],
                'index_types': mcq_option_dict['index_types'],
                'options_info': mcq_option_dict['options_info']
            }
        }

        return questions_for_disease
    

    # TODO: make method 2 - make 3 문제 from differential diagnosis node
    def create_questions_from_differential_diagnosis(self, diff_diag_id, difficulty_level='high',
                                                     n_options=4, n_highly_likely=1, n_moderately_likely=1, n_less_likely=0):
        disease_codes = self.knowledge_graph_obj.extract_disease_from_differential_diagnosis(diff_diag_id)
        main_disease_code = disease_codes[0]
        sub_disease_codes = disease_codes[1]

        # extract disease feature of main disease
        main_disease_features = self.disease_features_lookup[main_disease_code]
        main_disease_features_sampled = self.sample_features_from_disease(main_disease_features, difficulty_level=difficulty_level)

        # traverse all sampled features and remove all duration info from sampled features
        duration_keys = ['min_duration', 'max_duration', 'duration']
        for key in duration_keys:
            main_disease_features_sampled['sampled_diagnostic_criteria'].pop(key, None)
            
        for sg_key, sg_info in main_disease_features_sampled['sampled_symptom_groups'].items():
            for key in duration_keys:
                main_disease_features_sampled['sampled_symptom_groups'][sg_key].pop(key, None)


        # extract differential diagnosis disease features
        diff_diag_info = self.knowledge_graph_obj.get_differential_diagnosis_info(diff_diag_id) # keys: [main_disease, comparison_disease, additional_condition, key_difference, rules]

        option_candidates = self.list_options_for_question(main_disease_features_sampled)
        must_contain_options = [
            {"disease_code": sub_disease_codes,
             "disease_name": self.knowledge_graph_obj.convert_code_to_name(sub_disease_codes)}
             ]
        must_contain_options, must_remove_options = self.get_contain_and_remove_options_for_special_cases(disease_code, must_contain_option_list=must_contain_options)
        mcq_option_dict = self.sample_options_for_mcq(option_candidates,
                                                      must_contain_option_list=must_contain_options,
                                                      must_remove_option_list=must_remove_options,
                                                      n_options=n_options,
                                                      n_highly_likely = 0, n_moderately_likely=0, n_less_likely=0)
        # 'options': (list of str),
        # 'answer_index': (list of int),
        # 'must_contain_option_index': (list of int),
        # 'index_types': (list of str) # 'answer', 'must_contain_option', 'High likely option', 'Moderately likely option', 'Less likely option'
        # 'options_info': (list of dict) # detailed info about each option

        index_types_both = ['answer' if t == 'must_contain_option' else t for t in mcq_option_dict['index_types']]  
        index_types_option_b = ['must_contain_option' if t == 'answer' 
                                else 'answer' if t == 'must_contain_option' 
                                else t for t in mcq_option_dict['index_types']]

        questions_for_diff_diag = {
            "question_both": {
                'main_disease': main_disease_code,
                'sub_diseases': sub_disease_codes,
                'sampled_features': main_disease_features_sampled,
                'additional_condition': diff_diag_info['additional_condition'],
                'key_difference': diff_diag_info['key_difference']
            },
            "question_a": {
                "rule": diff_diag_info['rules'][main_disease_code]
            },
            "question_b": {
                "rule": diff_diag_info['rules'][sub_disease_codes]
            },
            "option_both": {
                'options': mcq_option_dict['options'],
                'answer_index': mcq_option_dict['answer_index'] + mcq_option_dict['must_contain_option_index'],
                'index_types': index_types_both,
                'options_info': mcq_option_dict['options_info']
            },
            "option_a": {
                'options': mcq_option_dict['options'],
                'answer_index': mcq_option_dict['answer_index'],
                'index_types': mcq_option_dict['index_types'],
                'options_info': mcq_option_dict['options_info']
            },
            "option_b": {
                'options': mcq_option_dict['options'],
                'answer_index': mcq_option_dict['must_contain_option_index'],
                'index_types': index_types_option_b,
                'options_info': mcq_option_dict['options_info']
            }
        }

        return questions_for_diff_diag


    def sample_features_from_disease(self, disease_features, difficulty_level='low'):
        # name
        # diagnostic_criteria
        #   - min_duration
        #   - max_duration
        #   - additional_requirements
        #   - functional_impairment_required
        #   - traumatic_stressor_required
        #   - psychosocial_stressor_required
        # symptom_groups
        #   - min_count
        #   - symptom group 1
        #   - symptom group 2
        # full_symptom_pool

        self.set_parameters_based_on_difficulty(difficulty_level)
        
        target_disease_code = disease_features['code']
        target_disease_name = disease_features['name']
        
        # sample features from diagnostic criteria
        diagnostic_criteria = disease_features['diagnostic_criteria']
        valid_criteria = {k:v for k, v in diagnostic_criteria.items() if v is not None and v != []}
        n_valid_criteria = len(valid_criteria)    # 총 진단 기준 개수
        ## number of diagnostic criteria to sample
        if self.include_all_diagnostic_criteria:    # 모든 진단 기준 포함
            sampled_diag_keys = list(valid_criteria.keys())
        else:   # 일부 진단 기준 샘플링
            sampled_diag_keys = []
            # duration 관련 기준 반드시 포함
            if self.include_duration:
                for key in valid_criteria.keys():
                    if 'duration' in key:
                        sampled_diag_keys.append(key)
                        
            if self.include_additional_requirements:
                if 'additional_requirements' in valid_criteria and (valid_criteria['additional_requirements'] != [] or valid_criteria['additional_requirements'] is not None):
                    sampled_diag_keys.append('additional_requirements')

            # sample remaining criteria
            n_remaining_criteria = n_valid_criteria - len(sampled_diag_keys)

            n_criteria_to_sample_min = min(self.min_count_contained_diagnostic_criteria, n_remaining_criteria)
            n_criteria_to_sample_max = min(self.max_count_contained_diagnostic_criteria, n_remaining_criteria)
            n_criteria_to_sample = random.randint(n_criteria_to_sample_min, n_criteria_to_sample_max)

            random_sorted_key = valid_criteria.keys()
            random.shuffle(list(random_sorted_key))
            i = 0
            for key in random_sorted_key:
                if key not in sampled_diag_keys:
                    sampled_diag_keys.append(key)
                    i += 1
                if i >= n_criteria_to_sample:
                    break

        sampled_diagnostic_criteria = {k: valid_criteria[k] for k in sampled_diag_keys}


        # sample features from symptom groups
        must_include_symptom_groups = disease_features['symptom_groups']['must_include_groups']
        optional_symptom_groups = disease_features['symptom_groups']['optional_groups']
        symptom_groups = {**must_include_symptom_groups, **optional_symptom_groups}
        # every symptom group is valid
        try:
            if self.include_all_symptom_groups:
                # _sampled_symptom_groups = {**must_include_symptom_groups, **optional_symptom_groups}  # 모든 증상군 포함 (must + optional)
                _sampled_symptom_groups = must_include_symptom_groups.copy()
                # randomly sample from optional symptom groups
                n_optional_groups_to_sample = random.randint(0, len(optional_symptom_groups))
                if n_optional_groups_to_sample > 0:
                    sampled_optional_groups = random.sample(list(optional_symptom_groups.keys()), k=n_optional_groups_to_sample)
                    _sampled_symptom_groups.update({k: optional_symptom_groups[k] for k in sampled_optional_groups})
            else:
                n_symptom_groups = len(symptom_groups)    # 총 증상군 개수
                n_groups_to_sample_min = min(self.min_count_contained_symptom_groups, n_symptom_groups)
                n_groups_to_sample_max = min(self.max_count_contained_symptom_groups, n_symptom_groups)
                n_groups_to_sample = random.randint(n_groups_to_sample_min, n_groups_to_sample_max)    # 샘플링할 증상군 개수

                # randomly decide how many must_include symptom groups to include                
                n_must_include_groups = random.randint(1, 
                                                       min(len(must_include_symptom_groups), n_groups_to_sample))
                sampled_must_include_groups = random.sample(list(must_include_symptom_groups.keys()), k=n_must_include_groups)
                # the number of samples from optional symptom groups
                remaining_groups_to_sample = n_groups_to_sample - n_must_include_groups
                sampled_optional_groups = random.sample(
                    list(optional_symptom_groups.keys()), 
                    k=min(remaining_groups_to_sample, len(optional_symptom_groups))
                )
                # randomly sampled symptom groups
                sampled_group_keys = sampled_must_include_groups + sampled_optional_groups
                _sampled_symptom_groups = {k: symptom_groups[k] for k in sampled_group_keys}
        except Exception as e:
            raise Exception("Error in sampling symptom groups:", e)

        sampled_symptom_groups = dict()   # to store final sampled symptom groups with sampled symptoms
        sampled_symptoms_set = set()    # considering overlapping symptoms across groups     
        for group_key, group_info in _sampled_symptom_groups.items():
            sampled_symptoms_in_group = []

            # 1. sample from must_include symptoms
            must_include_type = group_info['must_include']  # 'all', 'one_of', None

            must_include_symptom_list = group_info.get('must_include_symptoms', [])
            if must_include_type == 'all':
                # include all symptoms in this group
                sampled_symptoms_in_group.extend(must_include_symptom_list)
            elif must_include_type == 'one_of':
                # randomly include one or more symptoms from must_include_symptoms
                n_must_include_symptom = len(must_include_symptom_list)
                n_must_include_symptom_to_sample = random.randint(1, n_must_include_symptom)
                chosen_symptom = random.sample(must_include_symptom_list, k=n_must_include_symptom_to_sample)
                sampled_symptoms_in_group.extend(chosen_symptom)
            else:
                # no must_include symptoms
                pass

            # 2. sample from optional symptoms
            optional_symptom_list = group_info.get('include_symptoms', [])
        
            min_count = group_info.get('min_count', 0)

            # Calculate the minimum number of symptoms to sample
            if self.follow_min_count_per_group and min_count > 0:
                n_symptoms_to_sample_min = max(0, min(min_count - len(sampled_symptoms_in_group), len(optional_symptom_list)))
            else:
                n_symptoms_to_sample_min = max(0, min(self.min_count_contained_symptoms_per_group - len(sampled_symptoms_in_group), len(optional_symptom_list)))

            # Calculate the maximum number of symptoms to sample
            if self.follow_min_count_per_group and min_count > 0:
                n_symptoms_to_sample_max = max(
                    n_symptoms_to_sample_min,
                    min(self.max_count_contained_symptoms_per_group, len(optional_symptom_list)) # self.max_count_contained_symptoms_per_group = 4    # 증상군 당 최대 포함 증상 개수  # self.follow_min_count_per_group 이 False일 때 혹은 True이면서 min_count보다 더 클 때 적용
                )
            else:
                n_symptoms_to_sample_max = min(self.max_count_contained_symptoms_per_group, len(optional_symptom_list))

            # Sample optional symptoms
            if optional_symptom_list and n_symptoms_to_sample_min <= n_symptoms_to_sample_max:
                n_symptoms_to_sample = random.randint(n_symptoms_to_sample_min, n_symptoms_to_sample_max)
                sampled_optional_symptoms = random.sample(optional_symptom_list, k=n_symptoms_to_sample)
                sampled_symptoms_in_group.extend(sampled_optional_symptoms)
                # print(f"Range({n_symptoms_to_sample_min}, {n_symptoms_to_sample_max}) ... {n_symptoms_to_sample} in group {group_key}")
            

            sampled_symptoms_in_group = list(set(sampled_symptoms_in_group))    # remove duplicates within group
            sampled_symptoms_set.update(sampled_symptoms_in_group)
            
            # construct symptom group info with sampled symptoms
            symptom_group_keys = ['name', 'min_duration', 'functional_impairment_required'] # , 'frequency']
            sampled_symptom_groups[group_key] = {k:group_info[k] for k in symptom_group_keys if group_info[k] is not None and group_info[k] != []}  # 현재 있는 정보는 모두 포함
            sampled_symptom_groups[group_key]['symptoms'] = sorted(sampled_symptoms_in_group)
        
        # Special handling for specific disease codes
        if target_disease_code in ["D001", "D002", "D003"]:
            sampled_symptom_groups, sampled_symptoms_set = self.handle_adhd_symptom_counts(target_disease_code, sampled_symptom_groups)
        sampled_symptoms_set = sorted(list(sampled_symptoms_set))    # 전체 증상 중복 제거 후 정렬

        # symptom descriptions
        sampled_symptoms_descriptions = dict()
        for symptom_code in sampled_symptoms_set:
            symptom_info = self.knowledge_graph_obj.get_symptom_info(symptom_code)
            # 여기 examples, subtypes 가 있다면 random으로 한 개 선택해서 넣기
            # sampled_symptoms_descriptions[symptom_code] = self.sample_symptom_expression_type(symptom_info) # 나중에 symptom expression type도 같이 sampling하도록 수정 필요
            sampled_symptoms_descriptions[symptom_code] = symptom_info

        sampled_features = {
            'disease_code': target_disease_code,
            'disease_name': target_disease_name,
            'sampled_diagnostic_criteria': sampled_diagnostic_criteria,
            'sampled_symptom_groups': sampled_symptom_groups,
            'sampled_symptoms': sampled_symptoms_set,
            'sampled_symptoms_descriptions': sampled_symptoms_descriptions
        }

        # refined_sampled_features = self.refine_sampled_features(sampled_features) # instantiate functional impairment, stressor
        refined_sampled_features = self.instantiate_min_max_duration(sampled_features)

        return refined_sampled_features

    
    def handle_adhd_symptom_counts(self, target_disease_code, sampled_symptom_groups):
        inattention_symptoms = [
            symptom for group, group_info in sampled_symptom_groups.items()
            if "inattention" in group.lower()
            for symptom in group_info.get("symptoms", [])
        ]
        hyperactivity_symptoms = [
            symptom for group, group_info in sampled_symptom_groups.items()
            if "hyperactivity_impulsivity" in group.lower()
            for symptom in group_info.get("symptoms", [])
        ]
        sampled_symptoms_set = list(set(inattention_symptoms + hyperactivity_symptoms))

        if target_disease_code == "D001":
            # Ensure #inattention symptoms == #hyperactivity symptoms
            min_count = min(len(inattention_symptoms), len(hyperactivity_symptoms))
            sampled_symptom_groups['inattention']['symptoms'] = inattention_symptoms[:min_count]
            sampled_symptom_groups['hyperactivity_impulsivity']['symptoms'] = hyperactivity_symptoms[:min_count]
            sampled_symptoms_set = list(
                set(inattention_symptoms[:min_count] + hyperactivity_symptoms[:min_count])
            )
        elif target_disease_code == "D002":
            if 'hyperactivity_impulsivity' not in sampled_symptom_groups:
                pass
            # Ensure #inattention symptoms > #hyperactivity symptoms
            if len(inattention_symptoms) <= len(hyperactivity_symptoms):
                random_num = random.randint(1, len(hyperactivity_symptoms)-1)
                sampled_symptom_groups['hyperactivity_impulsivity']['symptoms'] = hyperactivity_symptoms[:random_num]
                sampled_symptoms_set = list(
                    set(inattention_symptoms + hyperactivity_symptoms[:random_num])
                )
        elif target_disease_code == "D003":
            if 'inattention' not in sampled_symptom_groups:
                pass
        # Ensure #inattention symptoms < #hyperactivity symptoms
            if len(inattention_symptoms) >= len(hyperactivity_symptoms):
                random_num = random.randint(1, len(inattention_symptoms)-1)
                sampled_symptom_groups['inattention']['symptoms'] = inattention_symptoms[:random_num]
                sampled_symptoms_set = list(
                    set(inattention_symptoms[:random_num]+hyperactivity_symptoms)
                )
        return sampled_symptom_groups, sampled_symptoms_set
    
    
    def list_options_for_question(self, disease_features):
        """
        Generate diagnostic options based on the sampled features.
        
        Args:
            features: Dictionary containing 'disease_name', 'sampled_symptom_groups', 
                     and 'sampled_symptoms' from sample_features_from_disease()
        
        Returns:
            Dictionary with three categories of options:
            - 'Highly likely option': Diseases sharing symptom groups
            - 'Moderately likely option': Diseases sharing symptoms but not groups
            - 'Less likely option': Unrelated diseases
        """
        target_disease_code = disease_features['disease_code']
        target_disease_name = disease_features['disease_name']
        target_symptom_groups = set(disease_features['sampled_symptom_groups'].keys())
        target_symptoms = set(disease_features['sampled_symptoms'])
        
        # Get all disease nodes
        all_diseases = self.knowledge_graph_obj.get_disease_nodes()
        
        highly_likely = []
        moderately_likely = []
        less_likely = []
        
        for disease_code, disease_name in all_diseases.items():
            # Skip the target disease itself
            if disease_name == target_disease_name:
                continue
            
            try:
                # Extract features for this disease
                disease_features = self.knowledge_graph_obj.extract_features_for_disease(disease_code)
                disease_symptom_groups = set([sg for group_relation in disease_features['symptom_groups'].keys() for sg in disease_features['symptom_groups'][group_relation].keys()])
                disease_symptoms = set(disease_features['full_symptom_pool'])
                
                # Check for symptom group overlap
                shared_groups = target_symptom_groups.intersection(disease_symptom_groups)
                
                # Check for symptom overlap
                shared_symptoms = target_symptoms.intersection(disease_symptoms)
                
                if shared_groups:
                    # Diseases sharing symptom groups are highly likely options
                    highly_likely.append({
                        'disease_code': disease_code,
                        'disease_name': disease_name,
                        'shared_symptom_groups': list(shared_groups),
                        'shared_symptoms': list(shared_symptoms)
                    })
                elif shared_symptoms:
                    # Diseases sharing symptoms but not groups are moderately likely
                    moderately_likely.append({
                        'disease_code': disease_code,
                        'disease_name': disease_name,
                        'shared_symptoms': list(shared_symptoms)
                    })
                else:
                    # Diseases with no overlap are less likely
                    less_likely.append({
                        'disease_code': disease_code,
                        'disease_name': disease_name
                    })
            except Exception as e:
                # Skip diseases that cause errors during feature extraction
                print(f"Warning: Could not process disease {disease_code}: {e}")
                continue

            # sort options by shared groups/symptoms count
        _buckets = defaultdict(list)
        for item in highly_likely:
            _buckets[len(item.get('shared_symptom_groups', []))].append(item)
        for bucket in _buckets.values():
            random.shuffle(bucket)
        highly_likely = [itm for k in sorted(_buckets.keys(), reverse=True) for itm in _buckets[k]]
        
        _buckets = defaultdict(list)
        for item in moderately_likely:
            _buckets[len(item.get('shared_symptoms', []))].append(item)
        for bucket in _buckets.values():
            random.shuffle(bucket)
        moderately_likely = [itm for k in sorted(_buckets.keys(), reverse=True) for itm in _buckets[k]]

        less_likely = random.sample(less_likely, len(less_likely))

        return {
            'answer': [{
                'disease_code': target_disease_code,
                'disease_name': target_disease_name,
            }],
            'Highly likely option': highly_likely,
            'Moderately likely option': moderately_likely,
            'Less likely option': less_likely,
        }

    def sample_options_for_mcq(self, options_dict:dict, 
                               must_contain_option_list:list=[],
                               must_remove_option_list:list=[],
                               n_options=4,
                               n_highly_likely=1,
                               n_moderately_likely=1,
                               n_less_likely=1):
        """
        Unified sampler:
        - If n_highly_likely == n_moderately_likely == n_less_likely == 0 -> behave like sample_options_for_mcq_by_relatedness
        - Otherwise -> behave like the stratified sample_options_for_mcq
        """
        
        correct_answer = options_dict['answer'][0]
        sampled_options = [correct_answer]  # Start with the correct answer
        option_index = ['answer']

        # Add must contain options if exists
        for must_option in must_contain_option_list:
            sampled_options.append(must_option)
            option_index.append('must_contain_option')
            must_remove_option_list.append(must_option.get('disease_code'))

        # remove must remove options from candidates
        _opts_dict = copy.deepcopy(options_dict)
        for remove_code in must_remove_option_list:
            for category in ['Highly likely option', 'Moderately likely option', 'Less likely option']:
                _opts_dict[category] = [opt for opt in _opts_dict[category] if opt.get('disease_code') != remove_code]


        if n_highly_likely == 0 and n_moderately_likely == 0 and n_less_likely == 0:
            # RELATEDNESS-BASED MODE

            # Sort in a list by relatedness
            sorted_options = []
            sorted_option_types = []
            for category in ['Highly likely option', 'Moderately likely option', 'Less likely option']:
                for option in _opts_dict[category]:
                    if not any(option.get('disease_name') == sampled_opt.get('disease_name') for sampled_opt in sampled_options):
                        sorted_options.append(option)
                        sorted_option_types.append(category)
                        
            # Fill options up to n_options
            n_to_sample = n_options - len(sampled_options)
            sampled_options.extend(sorted_options[:n_to_sample])
            option_index.extend(sorted_option_types[:n_to_sample])
            
        else:
            # STRATIFIED MODE (original sample_options_for_mcq behavior)

            # Highly likely
            highly_likely_options = _opts_dict['Highly likely option']
            n_sampled_highly = min(n_highly_likely, len(highly_likely_options), n_options - len(sampled_options))
            for option in highly_likely_options:
                if not any(opt.get('disease_name') == option.get('disease_name') for opt in sampled_options):
                    sampled_options.append(option)
                    option_index.append('Highly likely option')
                    n_sampled_highly -= 1
                if n_sampled_highly <= 0 or len(sampled_options) >= n_options:
                    break


            # Moderately likely
            moderately_likely_options = _opts_dict['Moderately likely option']
            n_sampled_moderately = min(n_moderately_likely, len(moderately_likely_options), n_options - len(sampled_options))
            for option in moderately_likely_options:
                if not any(opt.get('disease_name') == option.get('disease_name') for opt in sampled_options):
                    sampled_options.append(option)
                    option_index.append('Moderately likely option')
                    n_sampled_moderately -= 1
                if n_sampled_moderately <= 0 or len(sampled_options) >= n_options:
                    break

            # Less likely
            less_likely_options = _opts_dict['Less likely option']
            n_sampled_less = n_options - len(sampled_options)
            for option in less_likely_options:
                if not any(opt.get('disease_name') == option.get('disease_name') for opt in sampled_options):
                    sampled_options.append(option)
                    option_index.append('Less likely option')
                    n_sampled_less -= 1
                if n_sampled_less <= 0 or len(sampled_options) >= n_options:
                    break


        # randomize order
        random_index = list(range(len(sampled_options)))
        random.shuffle(random_index)
        sampled_options = [sampled_options[i] for i in random_index]
        option_indices = [option_index[i] for i in random_index]
        answer_index = option_indices.index('answer')
        must_contain_option_indices = [i for i, idx in enumerate(option_indices) if idx == 'must_contain_option']

        return {
            'options': [opt['disease_name'] for opt in sampled_options],
            'answer_index': [answer_index],
            'must_contain_option_index': must_contain_option_indices,
            'index_types': option_indices,
            'options_info': sampled_options
        }
    

    # keep alias for backward compatibility
    def sample_options_for_mcq_by_relatedness(self, options_dict:dict, must_contain_option_list:list=[], must_remove_option_list:list=[], n_options=4):
        return self.sample_options_for_mcq(options_dict, must_contain_option_list=must_contain_option_list, must_remove_option_list=must_remove_option_list, n_options=n_options, n_highly_likely=0, n_moderately_likely=0, n_less_likely=0)  

    def instantiate_min_max_duration(self, sampled_features):
        # instantiate min_duration and max_duration to arbitrary duration within the range
        diagnostic_criteria = sampled_features['sampled_diagnostic_criteria']

        ## if min_duration == '1 month', -> instantiate as duration == '1 month and 2 weeks'
        def duration_to_days(duration_str):
            duration_parts = duration_str.split()
            if len(duration_parts) != 2:
                return 6*30  # default to 6 months if unit is unrecognized
            try:
                value = int(duration_parts[0])
            except ValueError:
                print("Invalid duration value:", duration_parts)
                return 6*30  # default to 6 months if unit is unrecognized
            
            unit = duration_parts[1]
            if unit in ['day', 'days']:
                return value
            elif unit in ['week', 'weeks']:
                return value * 7
            elif unit in ['month', 'months']:
                return value * 30
            elif unit in ['year', 'years']:
                return value * 365
            else:
                return 6*30  # default to 6 months if unit is unrecognized
        def days_to_duration_string(days):
            if days < 7:
                return f"{days} days"
            elif days < 30:
                weeks = days // 7
                return f"{weeks} weeks"
            elif days < 365:
                months = days // 30
                if months == 1:
                    return f"{months} month"
                else:
                    return f"{months} months"
            else:
                years = days // 365
                months = (days % 365) // 30
                if years == 1:
                    if months == 0:
                        return f"{years} year"
                    else:
                        return f"{years} year and {months} months"
                else:
                    return f"{years} years and {months} months"

        #### instantiate durations for each symptom group
        if 'max_duration' in diagnostic_criteria:
            _max_duration = diagnostic_criteria['max_duration']
            total_max_duration_days = duration_to_days(_max_duration)
        else:
            total_max_duration_days = self.max_duration_buffer

        total_max_duration_days_divided_by_groups = total_max_duration_days // len(sampled_features['sampled_symptom_groups'])
        total_duration = 0
        for sg_key, sg_info in sampled_features['sampled_symptom_groups'].items():
            min_duration_days, max_duration_days = None, None

            if 'min_duration' in sg_info:
                min_duration = sg_info['min_duration']
                if isinstance(min_duration, str):
                    # parse duration string
                    min_duration_days = duration_to_days(min_duration)
                    
            if 'max_duration' in sg_info:
                max_duration = sg_info['max_duration']
                if isinstance(max_duration, str):
                    # parse duration string
                    max_duration_days = duration_to_days(max_duration)

            if min_duration_days is None and max_duration_days is None:
                continue
            elif min_duration_days is not None and max_duration_days is None:
                instantiated_duration = random.randint(
                    min_duration_days,
                    total_max_duration_days_divided_by_groups
                )
            elif min_duration_days is None and max_duration_days is not None:
                instantiated_duration = random.randint(
                    self.min_duration_buffer,
                    max_duration_days
                )
            else:   # both min and max are defined
                if min_duration_days > max_duration_days:
                    instantiated_duration = min_duration_days
                else:
                    instantiated_duration = random.randint(
                        min_duration_days,
                        max_duration_days
                    )
            instantiated_duration_str = days_to_duration_string(instantiated_duration)
            # update sampled features with instantiated duration
            sampled_features['sampled_symptom_groups'][sg_key]['duration'] = instantiated_duration_str
            # remove min_duration and max_duration keys
            sampled_features['sampled_symptom_groups'][sg_key].pop('min_duration', None)
            sampled_features['sampled_symptom_groups'][sg_key].pop('max_duration', None)

            total_duration += instantiated_duration
        
        #### instantiate total duration at diagnostic criteria level
        if 'min_duration' in diagnostic_criteria or 'max_duration' in diagnostic_criteria:
            pass
            if 'min_duration' in diagnostic_criteria:
                min_duration = diagnostic_criteria['min_duration']
                if isinstance(min_duration, str):
                    min_duration_days = duration_to_days(min_duration)
            else: 
                min_duration_days = self.min_duration_buffer

            if 'max_duration' in diagnostic_criteria:
                max_duration = diagnostic_criteria['max_duration']
                if isinstance(max_duration, str):
                    max_duration_days = duration_to_days(max_duration)
            else:
                max_duration_days = duration_to_days(diagnostic_criteria.get('max_duration', '')) if diagnostic_criteria.get('max_duration', None) else self.max_duration_buffer

            min_duration_days = max(total_duration, min_duration_days) if 'min_duration' in diagnostic_criteria else total_duration
            
            try:
                instantiated_duration = random.randint(min_duration_days, max_duration_days)
            except ValueError:
                instantiated_duration = max(min_duration_days, total_duration)
            instantiated_duration_str = days_to_duration_string(instantiated_duration)
            sampled_features['sampled_diagnostic_criteria']['duration'] = instantiated_duration_str
            sampled_features['sampled_diagnostic_criteria'].pop('min_duration', None)
            sampled_features['sampled_diagnostic_criteria'].pop('max_duration', None)
        return sampled_features
    

    def variate_question(self, sampled_features):
        # Variate question by modifying symptom expression types
        # Input: sampled_features from sample_features_from_disease()
        # - disease_code
        # - disease_name
        # - sampled_diagnostic_criteria
        # - sampled_symptom_groups
        # - sampled_symptoms
        # - sampled_symptoms_descriptions

        # instantiate functional impairment, traumatic_stressor, psychosocial_stressor
        sampled_features = self.refine_sampled_features(sampled_features)

        variated_sampled_symptoms_descriptions = dict()
        for symptom_code, symptom_info in sampled_features['sampled_symptoms_descriptions'].items():
            variated_symptom_info = self.sample_symptom_expression_type(symptom_info)
            variated_sampled_symptoms_descriptions[symptom_code] = variated_symptom_info

        sampled_features['sampled_symptoms_descriptions'] = variated_sampled_symptoms_descriptions

        # symptom descriptions
        # sampled_symptoms_descriptions = dict()
        # for symptom_code in sampled_symptoms_set:
        #     symptom_info = self.knowledge_graph_obj.get_symptom_info(symptom_code)
            # 여기 examples, subtypes 가 있다면 random으로 한 개 선택해서 넣기
            # sampled_symptoms_descriptions[symptom_code] = self.sample_symptom_expression_type(symptom_info) # 나중에 symptom expression type도 같이 sampling하도록 수정 필요

        return sampled_features

    def refine_sampled_features(self, sampled_features):
        # refine sampled features
        # 1. sample events for functional impairment, traumatic stressor, psychosocial stressor 
        diagnostic_criteria = sampled_features['sampled_diagnostic_criteria']
        ## traumatic_stressor_required
        if 'traumatic_stressor_required' in diagnostic_criteria:
            if diagnostic_criteria['traumatic_stressor_required'] is not None:
                sampled_event = self.sample_event('traumatic_stressor_required')
                # update sampled features
                refined_traumatic_stressor = {
                    'required': True, 
                    'event': sampled_event
                }
            else:
                refined_traumatic_stressor = {
                    'required': False
                }
            sampled_features['sampled_diagnostic_criteria']['traumatic_stressor_required'] = refined_traumatic_stressor

        ## psychosocial_stressor_required
        if 'psychosocial_stressor_required' in diagnostic_criteria:
            if diagnostic_criteria['psychosocial_stressor_required'] is not None:
                sampled_event = self.sample_event('psychosocial_stressor_required')
                # update sampled features
                refined_psychosocial_stressor = {
                    'required': True, 
                    'event': sampled_event
                }
            else:
                refined_psychosocial_stressor = {
                    'required': False, 
                }
            sampled_features['sampled_diagnostic_criteria']['psychosocial_stressor_required'] = refined_psychosocial_stressor

        ## functional_impairment_required
        flag = 0
        if 'functional_impairment_required' in diagnostic_criteria:
            if diagnostic_criteria['functional_impairment_required'] == True:
                sampled_event = self.sample_event('functional_impairment_required')
                # update sampled features
                refined_functional_impairment = {
                    'required': True, # True
                    'event': sampled_event
                }

                flag = 1
            else:
                refined_functional_impairment = {
                    'required': False, 
                }

            sampled_features['sampled_diagnostic_criteria']['functional_impairment_required'] = refined_functional_impairment
        
        symptom_groups = sampled_features['sampled_symptom_groups']
        for symptom_group in symptom_groups:
            sg_info = symptom_groups[symptom_group]
            if 'functional_impairment_required' in sg_info:
                if flag == 1:
                    # already sampled from diagnostic criteria level
                    sg_info.pop('functional_impairment_required', None)
                else:   # flag == 0 -> not yet sampled
                    if 'functional_impairment_required' in sg_info:
                        if sg_info['functional_impairment_required'] == True:
                            sampled_event = self.sample_event('functional_impairment_required')
                            
                            # update sampled features at diagnostic criteria level
                            sampled_features['sampled_diagnostic_criteria'].update({
                                'functional_impairment_required': {
                                    'required': True,  # True
                                    'event': sampled_event
                                }
                            })
                            
                            # pop from symptom group level
                            sampled_features['sampled_symptom_groups'][symptom_group].pop('functional_impairment_required', None)
                            flag = 1

        return sampled_features
    
    def sample_symptom_expression_type(self, symptom_info):
        # symptom_info: dictionary containing symptom details
        if 'subtypes' in symptom_info:
            subtypes = symptom_info['subtypes']
            if subtypes is not None:
                if isinstance(subtypes, dict):
                    selected_subtype = random.choice(list(subtypes.keys()))
                else:
                    selected_subtype = random.choice(subtypes)
                symptom_info['subtypes'] = {selected_subtype: subtypes[selected_subtype]} if isinstance(subtypes, dict) else selected_subtype
            else:
                symptom_info.pop('subtypes', None)


        if 'examples' in symptom_info:
            examples = symptom_info['examples'] # list            
            if examples is not None:
                if isinstance(examples, list):
                    selected_example = random.choice(examples)
                    symptom_info['examples'] = selected_example
                else:
                    print("Type Error) Examples is not list:", symptom_info["name"], examples, type(examples))
            else:
                symptom_info.pop('examples', None)
            
        return symptom_info

    def sample_event(self, event_key):
        event_dict = self.knowledge_graph_obj.get_event_mapping_dictionary(event_key)
        assert event_dict is not None, AssertionError(f"In QuestionSetter.sample_event: Event key '{event_key}' not found in event mapping data.")
        event_name = event_dict.get('name', None)
        event_description = event_dict.get('description', None)
        event_examples = event_dict.get('examples', None)
        event_types = event_dict.get('types', None)
        
        if event_types:
            selected_type_key = random.choice(list(event_types.keys()))
            selected_types = {selected_type_key: event_types[selected_type_key]}
        if event_examples:
            selected_example_key = random.choice(list(event_examples.keys()))
            selected_example = {selected_example_key: event_examples[selected_example_key]}
       
        selected_event = {
            'name': event_name,
        }
        if event_key == 'functional_impairment_required' or event_key == 'traumatic_stressor_required':
            selected_event["type"] = selected_types
        if event_key == 'traumatic_stressor_required' or event_key == 'psychosocial_stressor_required':
            selected_event["example"] = selected_example
        if event_description is not None:
            selected_event["description"] = event_description

        return selected_event
    
# utils
def test_list_options(knowledge_graph_obj, qs, disease_code="D007"):
    # Test with Schizoaffective Disorder (Depressive Type)
    print("\n" + "="*80)
    print("Test: list_options_for_question")
    print("="*80)

    print(f"\nTarget Disease Code: {disease_code}")

    # Extract features and sample from them
    disease_features = knowledge_graph_obj.extract_features_for_disease(disease_code)
    sampled_features = qs.sample_features_from_disease(disease_features)

    # Generate options for the question
    print("\n" + "-"*80)
    print("Generating diagnostic options...")
    print("-"*80)

    options = qs.list_options_for_question(sampled_features)

    # Display results
    print(f"\n✓ Target Disease: {sampled_features['disease_name']}")
    print(f"  Sampled Symptom Groups: {list(sampled_features['sampled_symptom_groups'].keys())}")
    print(f"  Sampled Symptoms: {len(sampled_features['sampled_symptoms'])} symptoms")

    print(f"\n✓ HIGHLY LIKELY OPTIONS ({len(options['Highly likely option'])} diseases)")
    print("  (Diseases sharing symptom groups with the target)")
    for i, opt in enumerate(options['Highly likely option'][:5], 1):
        print(f"  {i}. {opt['disease_name']}")
        print(f"     - Shared groups: {', '.join(opt['shared_symptom_groups'])}")
        print(f"     - Shared symptoms: {len(opt['shared_symptoms'])} symptoms")

    print(f"\n✓ MODERATELY LIKELY OPTIONS ({len(options['Moderately likely option'])} diseases)")
    print("  (Diseases sharing symptoms but not symptom groups)")
    for i, opt in enumerate(options['Moderately likely option'][:5], 1):
        print(f"  {i}. {opt['disease_name']}")
        print(f"     - Shared symptoms: {len(opt['shared_symptoms'])} symptoms")

    print(f"\n✓ LESS LIKELY OPTIONS ({len(options['Less likely option'])} diseases)")
    print("  (Diseases with no overlap)")
    for i, opt in enumerate(options['Less likely option'][:5], 1):
        print(f"  {i}. {opt['disease_name']}")

    print("\n" + "="*80)
    print("Test completed successfully!")
    print("="*80)

    return options

def test_sample_features(knowledge_graph_obj, qs, disease_code="D020", difficulty_level='medium'):
    # Extract features for the disease
    disease_features = knowledge_graph_obj.extract_features_for_disease(disease_code)

    # Sample features from the disease
    sampled_features = qs.sample_features_from_disease(disease_features, difficulty_level=difficulty_level)

    # Display results
    print("\nSampled Features:")
    sampled_features.pop('sampled_symptoms', None)  # 너무 길어서 제외
    sampled_features.pop('sampled_symptoms_descriptions', None)  # 너무 길어서 제외
    print(json.dumps(sampled_features, indent=2))

    return sampled_features

if __name__ == "__main__":
    args = None
    knowledge_graph_obj = KnowledgeGraph(args)
    qs = QuestionSetter(knowledge_graph_obj)

    disease_code = "D020"
    differential_disease_code = "D020-D013"

    # for code in knowledge_graph_obj.get_disease_nodes():
    #     question_data = qs.call_questions(code, 'medium', './../resources/features/variation/')
    #     print(question_data.keys())

    # 단일타입 - easy
    qna_easy = qs.create_questions_from_disease(disease_code, difficulty_level='low',
                                                n_options=4, n_highly_likely=1, n_moderately_likely=1, n_less_likely=1)
    # 단일타입 - medium
    qna_medium = qs.create_questions_from_disease(disease_code, difficulty_level='medium',
                                                  n_options=4, n_highly_likely=1, n_moderately_likely=1, n_less_likely=1)
    
    # 단일타입 키
    # {'question': {
    #       'disease_code': str,
    #       'disease_name': str,
    #       'sampled_features': dict,
    #   },
    #  'options': {
    #      'options': [str],
    #      'answer_index': [int],
    #      'must_contain_option_index': [int],
    #      'index_types': [str],
    #      'options_info': [dict]},
    #   }
    # }
    
    # 혼재타입
    qna_high = qs.create_questions_from_differential_diagnosis(differential_disease_code, difficulty_level='high',
                                                n_options=4, n_highly_likely=1, n_moderately_likely=1, n_less_likely=0) # 혼재타입에서는 comparison disease가 option에 포함되어서

    # 혼재타입 키
    # {
        # "question_both": {
        #     'main_disease': str,
        #     'sub_diseases': str,
        #     'sampled_features': dict,
        #     'additional_condition': str,
        # },
        # "question_a": {
        #     "rule": [str]
        # },
        # "question_b": {
        #     "rule": [str]
        # },
        # "option_both": {
        #     'options': [str],
        #     'answer_index':[int],
        #     'index_types': [str],
        #     'options_info': [dict]
        # },
        # "option_a": {
        #     ...
        # },
        # "option_b": {
        #     ...
        # }
    # }

    
    

    # test_list_options(knowledge_graph_obj, qs, disease_code)
    # sampling test for all diseases
    # for disease_num in range(1, 24):
    #     disease_code = f"D{disease_num:03d}"
    #     print(f"\n{'='*30} Testing sample_features for disease code: {disease_code} {'='*30}\n")
    #     for level in ['low', 'medium']:
    #         for _ in range(10):  # 각 난이도별로 2회 테스트
    #             try:
    #                 test_sample_features(knowledge_graph_obj, qs, disease_code=disease_code, difficulty_level=level)
    #             except Exception as e:
    #                 raise Exception(f"Error during testing for disease code {disease_code} at level {level}: {e}")
                
    