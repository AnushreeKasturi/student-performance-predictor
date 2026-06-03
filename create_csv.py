import pandas as pd

data = {
    "attendance": [92, 80, 60, 95, 70, 85],
    "study_hours": [5, 3, 1, 6, 2, 4],
    "internal_marks": [85, 70, 50, 90, 65, 78],
    "assignments": [90, 75, 55, 92, 60, 80],
    "final_score": [88, 72, 52, 94, 63, 79]
}

df = pd.DataFrame(data)

df.to_csv("student_data.csv", index=False)

print("CSV file created successfully!")