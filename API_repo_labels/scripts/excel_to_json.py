import os
import pandas as pd

script_dir = os.path.dirname(os.path.abspath(__file__))

input_path = os.path.join(script_dir, '..', 'data', 'excel_labels_data.xlsx')
output_path = os.path.join(script_dir, '..', 'data', 'labels_data.json')

df = pd.read_excel(input_path, sheet_name='all labels')
df = df.fillna('')

# filter to only include "sure" labels
df = df[df['Sure/Unsure'].str.strip().str.lower() == 'sure']

# create required fields using for labelling
df['label_name'] = df['Label Name = (Label Series: Concept)'].str.strip()
df['description'] = df['Description'].str.strip()
df['label_series'] = df['Label Series'].str.strip()

# create key words using name and description -> used to assign labels
df['keywords'] = (
    df['Concept']
    .fillna('')
    .str.lower()
    .str.split(r'[/,]')   
    .apply(lambda lst: [x.strip() for x in lst])  
)

# label colours
series_colors = {
    "Approach": "1f77b4",
    "Framework": "ff7f0e",
    "Database": "2ca02c",
    "Testing & QA": "d62728",
    "Workflow": "9467bd",
    "Security": "8c564b",
    "Documentation": "e377c2",
    "Language & File Type": "bcbd22",
    "Syntax": "17becf",
    "Statistics": "aec7e8",
    "Skill": "ffbb78",
    "Method": "98df8a",
    "Paradigm": "c5b0d5",
    "Scrum": "f7b6d2",
    "Kanban": "c49c94",
    "Lean": "dbdb8d",
    "BDD": "9edae5",
    "XP": "7f7f7f",
    "FDD": "c7c7c7",
    "SAFe": "ff9896",
    "DDD": "bcbd22",
    "TDD": "1f77b4"
}

df['color'] = df['label_series'].map(series_colors).fillna("cccccc")

final_df = df[['label_name', 'description', 'keywords', 'label_series', 'color']]

json_data = final_df.to_json(orient='records', indent=2)

# writes to labels_data.json
with open(output_path, 'w') as f:
    f.write(json_data)


    
