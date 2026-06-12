import os, json


def read_json(file_path):
        if type(file_path) == str:
            with open(file_path, 'r') as f:
                data = json.load(f)
        elif type(file_path) == list:
            data = {}
            for fp in file_path:
                with open(fp, 'r') as f:
                    obj = json.load(f)
                    data.update(obj)
        return data


def load_data(dir_kg):
        # read file from: args.knowledge_graph_dir
        ## file path
        path_kg_disorder = 'disorder.json'
        path_kg_mapping = 'diagnostic_criteria.json'
        dir_kg_symptom = os.path.join(dir_kg, 'symptom')
        dir_kg_diff_diagnosis = os.path.join(dir_kg, 'differential_diagnosis')
        path_kg_symptom = os.listdir(dir_kg_symptom)
        path_kg_diff_diagnosis = os.listdir(dir_kg_diff_diagnosis)

        ## read json files
        # process to read knowledge graph
        data_disorder = read_json(os.path.join(dir_kg, path_kg_disorder))
        data_symptom = read_json([os.path.join(dir_kg_symptom, fn) for fn in path_kg_symptom])
        data_mapping = read_json(os.path.join(dir_kg, path_kg_mapping))
        data_diff_diagnosis = read_json([os.path.join(dir_kg_diff_diagnosis, fn) for fn in path_kg_diff_diagnosis])

        return data_disorder, data_symptom, data_mapping, data_diff_diagnosis


def aggregate(data_disorder, data_symptom, data_mapping):
    # aggregate knowledge graph readably
    output_dir = './KR/readable_kg'
    os.makedirs(output_dir, exist_ok=True)

    for disorder_key, mapping_key in zip(data_disorder.keys(), data_mapping.keys()):
        assert disorder_key == mapping_key, f"Disorder key and mapping key do not match. {disorder_key} {mapping_key}"
        assert data_disorder[disorder_key]['name'] == data_mapping[mapping_key]['name'], f"Disorder name and mapping disorder name do not match. {data_disorder[disorder_key]['name']} {data_mapping[mapping_key]['disorder_name']}"

        disorder_name = data_disorder[disorder_key]['name']
        map_info = data_mapping[mapping_key]

        for symptom_group, group_info in map_info["required_criteria"].items():
            if type(group_info) == dict:
                symptom_pool_list = group_info.get("symptom_pool", [])
                map_info["required_criteria"][symptom_group]["symptom_pool"] = {
                    s_code: data_symptom[s_code] for s_code in symptom_pool_list
                }

                if "must_include_all" in group_info:
                    must_include_all_list = group_info["must_include_all"]
                    map_info["required_criteria"][symptom_group]["must_include_all"] = {
                            s_code: data_symptom[s_code] for s_code in must_include_all_list
                        }
                
                if "must_include_one_of" in group_info:
                    must_include_one_of_list = group_info["must_include_one_of"]
                    map_info["required_criteria"][symptom_group]["must_include_one_of"] = {
                            s_code: data_symptom[s_code] for s_code in must_include_one_of_list
                        }

        # save aggregated readable knowledge graph
        output_path = os.path.join(output_dir, f"{disorder_key}_{disorder_name.replace('/', '-')}.json")
        with open(output_path, 'w') as f:
            json.dump(map_info, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    dir_kg = './KR'
    data_disorder, data_symptom, data_mapping, data_diff_diagnosis = load_data(dir_kg)

    aggregate(data_disorder, data_symptom, data_mapping)



    
    